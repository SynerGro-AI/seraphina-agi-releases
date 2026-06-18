#!/usr/bin/env python3
"""Analytics supervisor: orchestrate collect -> report -> alerts for one or more repos.

Designed to be the single entrypoint invoked by the scheduled
`.github/workflows/traffic-analytics.yml` workflow. Wraps
`analytics/github_traffic_analytics.py` so the workflow stays declarative.

Behavior:
  1. Ensure the analytics DB exists (init schema if missing).
  2. Collect snapshots for every requested repo (continues past per-repo failures).
  3. Print a per-repo report (last N days).
  4. Run alert checks for views + clones against each repo.
  5. Emit a JSON summary to stdout and (when available) to
     ``$GITHUB_STEP_SUMMARY`` as Markdown.
  6. Exit codes:
       0 - all collects succeeded, no alerts breached
       2 - one or more alert thresholds breached
       3 - one or more collects failed (token, network, permissions, ...)
       Both conditions -> exit 3 (collect failure dominates).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from typing import Any

# Reuse primitives from the collector module so we have one source of truth
# for schema, HTTP, and DB helpers.
from github_traffic_analytics import (  # type: ignore[import-not-found]
    check_alerts,
    collect_repo,
    compare_repos,
    ensure_db,
    parse_repo,
    print_report,
)

EXIT_OK = 0
EXIT_ALERT = 2
EXIT_COLLECT_FAIL = 3


def _split_repos(raw: str | None) -> list[str]:
    if not raw:
        return []
    # Accept whitespace- or comma-separated lists.
    parts = [p.strip() for chunk in raw.split(",") for p in chunk.split()]
    return [p for p in parts if p]


def _resolve_repos(args: argparse.Namespace) -> list[str]:
    repos: list[str] = []
    repos.extend(args.repos or [])
    repos.extend(_split_repos(os.getenv("INPUT_REPOS")))
    if not repos:
        default = os.getenv("DEFAULT_REPO") or os.getenv("GITHUB_REPOSITORY")
        if default:
            repos.append(default)
    # De-dupe, preserve order, validate.
    seen: set[str] = set()
    out: list[str] = []
    for slug in repos:
        if slug in seen:
            continue
        parse_repo(slug)  # raises on bad slug
        seen.add(slug)
        out.append(slug)
    return out


def _write_step_summary(summary: dict[str, Any]) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines: list[str] = ["# Traffic analytics run", ""]
    lines.append(f"- Run started: `{summary['started_at']}`")
    lines.append(f"- Repos: {len(summary['repos'])}")
    lines.append(
        f"- Collect failures: {summary['collect_failures']} | "
        f"Alerts breached: {summary['alerts_breached']}"
    )
    lines.append("")
    lines.append("| repo | collect | views alert | clones alert |")
    lines.append("| --- | --- | --- | --- |")
    for entry in summary["repos"]:
        lines.append(
            "| {repo} | {collect} | {views} | {clones} |".format(
                repo=entry["repo"],
                collect="ok" if entry["collect_ok"] else f"FAIL: {entry.get('collect_error', '?')}",
                views=_fmt_alert(entry.get("alerts", {}).get("views")),
                clones=_fmt_alert(entry.get("alerts", {}).get("clones")),
            )
        )
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as exc:
        print(f"warn: could not write step summary: {exc}", file=sys.stderr)


def _fmt_alert(code: int | None) -> str:
    if code is None:
        return "-"
    if code == EXIT_OK:
        return "ok"
    if code == EXIT_ALERT:
        return "BREACH"
    return f"err({code})"


def supervise(args: argparse.Namespace) -> int:
    token = os.getenv(args.token_env)
    if not token:
        print(
            f"error: missing token; set environment variable {args.token_env} "
            "(see analytics/README.md).",
            file=sys.stderr,
        )
        return EXIT_COLLECT_FAIL

    repos = _resolve_repos(args)
    if not repos:
        print("error: no repositories supplied; pass --repos or set INPUT_REPOS/DEFAULT_REPO.", file=sys.stderr)
        return EXIT_COLLECT_FAIL

    db_dir = os.path.dirname(args.db)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    summary: dict[str, Any] = {
        "started_at": started_at,
        "db": args.db,
        "repos": [],
        "collect_failures": 0,
        "alerts_breached": 0,
    }

    conn = sqlite3.connect(args.db)
    try:
        ensure_db(conn)

        for slug in repos:
            entry: dict[str, Any] = {"repo": slug, "collect_ok": False, "alerts": {}}
            owner, repo = parse_repo(slug)
            print(f"\n=== {slug} ===")
            try:
                collect_repo(conn, owner, repo, token)
                entry["collect_ok"] = True
            except Exception as exc:  # noqa: BLE001 - report and continue across repos
                summary["collect_failures"] += 1
                entry["collect_error"] = str(exc)
                print(f"collect failed for {slug}: {exc}", file=sys.stderr)
                summary["repos"].append(entry)
                continue

            try:
                print_report(conn, slug, max(args.days, 1))
            except Exception as exc:  # noqa: BLE001
                print(f"report failed for {slug}: {exc}", file=sys.stderr)

            for metric in ("views", "clones"):
                try:
                    code = check_alerts(
                        conn,
                        repo_slug=slug,
                        metric=metric,
                        window=max(args.window, 2),
                        drop=max(args.drop_threshold, 0.0),
                        spike=max(args.spike_threshold, 0.0),
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"alert check failed for {slug}/{metric}: {exc}", file=sys.stderr)
                    code = 1
                entry["alerts"][metric] = code
                if code == EXIT_ALERT:
                    summary["alerts_breached"] += 1

            summary["repos"].append(entry)

        if len(repos) > 1:
            try:
                compare_repos(conn, repos, metric="views", days=max(args.days, 1))
            except Exception as exc:  # noqa: BLE001
                print(f"compare failed: {exc}", file=sys.stderr)
    finally:
        conn.close()

    print("\n=== summary ===")
    print(json.dumps(summary, indent=2, sort_keys=True))
    _write_step_summary(summary)

    if summary["collect_failures"]:
        return EXIT_COLLECT_FAIL
    if summary["alerts_breached"]:
        return EXIT_ALERT
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Supervise scheduled GitHub traffic analytics: collect, report, alert, "
            "and emit a structured summary."
        ),
    )
    parser.add_argument(
        "--db",
        default=os.getenv("ANALYTICS_DB", "analytics/traffic_analytics.db"),
        help="Path to SQLite DB file.",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        default=None,
        help="Repos in owner/repo form. Falls back to INPUT_REPOS, then DEFAULT_REPO/GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable holding the GitHub token (default: GITHUB_TOKEN).",
    )
    parser.add_argument("--days", type=int, default=14, help="Report window in days.")
    parser.add_argument("--window", type=int, default=7, help="Alert baseline window in days.")
    parser.add_argument("--drop-threshold", type=float, default=0.40, help="Drop alert fraction.")
    parser.add_argument("--spike-threshold", type=float, default=1.00, help="Spike alert fraction.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return supervise(args)


if __name__ == "__main__":
    sys.exit(main())
