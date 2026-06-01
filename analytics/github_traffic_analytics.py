#!/usr/bin/env python3
"""GitHub traffic and release analytics collector + CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS repositories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,
  name TEXT NOT NULL,
  UNIQUE(owner, name)
);

CREATE TABLE IF NOT EXISTS metric_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  metric TEXT NOT NULL,
  source TEXT NOT NULL,
  dimension TEXT NOT NULL DEFAULT '',
  count_value INTEGER NOT NULL DEFAULT 0,
  uniques_value INTEGER,
  metadata_json TEXT,
  collected_at TEXT NOT NULL,
  FOREIGN KEY(repo_id) REFERENCES repositories(id),
  UNIQUE(repo_id, day, metric, source, dimension)
);

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_repo_day
  ON metric_snapshots(repo_id, day);
CREATE INDEX IF NOT EXISTS idx_metric_snapshots_metric
  ON metric_snapshots(metric, source);
"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def get_repo_id(conn: sqlite3.Connection, owner: str, repo: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO repositories (owner, name) VALUES (?, ?)",
        (owner, repo),
    )
    row = conn.execute(
        "SELECT id FROM repositories WHERE owner = ? AND name = ?", (owner, repo)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not resolve repository id for {owner}/{repo}")
    return int(row[0])


def to_day(timestamp: str) -> str:
    if not timestamp:
        return dt.date.today().isoformat()
    return timestamp.split("T", 1)[0]


def insert_snapshot(
    conn: sqlite3.Connection,
    repo_id: int,
    day: str,
    metric: str,
    source: str,
    dimension: str,
    count_value: int,
    uniques_value: int | None,
    metadata: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO metric_snapshots
          (repo_id, day, metric, source, dimension, count_value, uniques_value, metadata_json, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id, day, metric, source, dimension)
        DO UPDATE SET
          count_value = excluded.count_value,
          uniques_value = excluded.uniques_value,
          metadata_json = excluded.metadata_json,
          collected_at = excluded.collected_at
        """,
        (
            repo_id,
            day,
            metric,
            source,
            dimension,
            int(count_value),
            None if uniques_value is None else int(uniques_value),
            json.dumps(metadata or {}, separators=(",", ":")),
            utc_now(),
        ),
    )


def github_get(url: str, token: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "seraphina-agi-traffic-analytics",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc


def github_paginated(base_url: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}per_page=100&page={page}"
        data = github_get(url, token)
        if not isinstance(data, list) or not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
        page += 1
    return items


def collect_repo(conn: sqlite3.Connection, owner: str, repo: str, token: str) -> None:
    repo_id = get_repo_id(conn, owner, repo)
    today = dt.date.today().isoformat()
    api = f"https://api.github.com/repos/{owner}/{repo}"

    views = github_get(f"{api}/traffic/views", token).get("views", [])
    for row in views:
        ts = str(row.get("timestamp", ""))
        insert_snapshot(
            conn,
            repo_id,
            to_day(ts),
            metric="views",
            source="traffic/views",
            dimension="",
            count_value=int(row.get("count", 0)),
            uniques_value=int(row.get("uniques", 0)),
            metadata={"timestamp": ts},
        )

    clones = github_get(f"{api}/traffic/clones", token).get("clones", [])
    for row in clones:
        ts = str(row.get("timestamp", ""))
        insert_snapshot(
            conn,
            repo_id,
            to_day(ts),
            metric="clones",
            source="traffic/clones",
            dimension="",
            count_value=int(row.get("count", 0)),
            uniques_value=int(row.get("uniques", 0)),
            metadata={"timestamp": ts},
        )

    referrers = github_get(f"{api}/traffic/popular/referrers", token)
    for row in referrers:
        referrer = str(row.get("referrer", "unknown"))
        insert_snapshot(
            conn,
            repo_id,
            today,
            metric="referrers",
            source="traffic/referrers",
            dimension=referrer,
            count_value=int(row.get("count", 0)),
            uniques_value=int(row.get("uniques", 0)),
            metadata=None,
        )

    paths = github_get(f"{api}/traffic/popular/paths", token)
    for row in paths:
        path = str(row.get("path", "unknown"))
        insert_snapshot(
            conn,
            repo_id,
            today,
            metric="paths",
            source="traffic/paths",
            dimension=path,
            count_value=int(row.get("count", 0)),
            uniques_value=int(row.get("uniques", 0)),
            metadata={"title": row.get("title", "")},
        )

    releases = github_paginated(f"{api}/releases", token)
    for release in releases:
        tag = str(release.get("tag_name", "untagged"))
        release_id = int(release.get("id", 0))
        assets = release.get("assets", []) or []
        for asset in assets:
            name = str(asset.get("name", "asset"))
            insert_snapshot(
                conn,
                repo_id,
                today,
                metric="release_downloads",
                source="releases/assets",
                dimension=f"{tag}:{name}",
                count_value=int(asset.get("download_count", 0)),
                uniques_value=None,
                metadata={
                    "release_id": release_id,
                    "asset_id": asset.get("id"),
                    "published_at": release.get("published_at"),
                    "updated_at": asset.get("updated_at"),
                },
            )

    conn.commit()


def parse_repo(repo_slug: str) -> tuple[str, str]:
    if "/" not in repo_slug:
        raise ValueError(f"Expected owner/repo format, got: {repo_slug}")
    owner, repo = repo_slug.split("/", 1)
    if not owner or not repo:
        raise ValueError(f"Expected owner/repo format, got: {repo_slug}")
    return owner, repo


def print_report(conn: sqlite3.Connection, repo_slug: str, days: int) -> None:
    owner, repo = parse_repo(repo_slug)
    row = conn.execute(
        "SELECT id FROM repositories WHERE owner = ? AND name = ?", (owner, repo)
    ).fetchone()
    if row is None:
        print(f"No data for {repo_slug}")
        return
    repo_id = int(row[0])

    start_day = (dt.date.today() - dt.timedelta(days=max(days - 1, 0))).isoformat()
    traffic_rows = conn.execute(
        """
        SELECT day, metric, SUM(count_value), SUM(COALESCE(uniques_value, 0))
        FROM metric_snapshots
        WHERE repo_id = ?
          AND day >= ?
          AND source IN ('traffic/views', 'traffic/clones')
        GROUP BY day, metric
        ORDER BY day DESC, metric
        """,
        (repo_id, start_day),
    ).fetchall()

    print(f"\n== Traffic summary for {repo_slug} (last {days} day(s)) ==")
    if not traffic_rows:
        print("No traffic data yet.")
    else:
        for day, metric, count_value, uniques in traffic_rows:
            print(f"{day}  {metric:6s}  count={count_value:4d}  uniques={uniques:4d}")

    print("\n== Latest release asset download counts ==")
    release_rows = conn.execute(
        """
        SELECT s.dimension, s.count_value
        FROM metric_snapshots s
        JOIN (
          SELECT dimension, MAX(day) AS max_day
          FROM metric_snapshots
          WHERE repo_id = ? AND source = 'releases/assets'
          GROUP BY dimension
        ) x
        ON s.dimension = x.dimension AND s.day = x.max_day
        WHERE s.repo_id = ? AND s.source = 'releases/assets'
        ORDER BY s.count_value DESC
        LIMIT 20
        """,
        (repo_id, repo_id),
    ).fetchall()
    if not release_rows:
        print("No release download snapshots yet.")
    else:
        for dimension, count_value in release_rows:
            print(f"{dimension}  downloads={count_value}")


def compare_repos(conn: sqlite3.Connection, repos: list[str], metric: str, days: int) -> None:
    start_day = (dt.date.today() - dt.timedelta(days=max(days - 1, 0))).isoformat()
    print(f"\n== Repo comparison for metric={metric} (last {days} day(s)) ==")
    for slug in repos:
        owner, repo = parse_repo(slug)
        row = conn.execute(
            "SELECT id FROM repositories WHERE owner = ? AND name = ?", (owner, repo)
        ).fetchone()
        if row is None:
            print(f"{slug:40s} no data")
            continue
        repo_id = int(row[0])
        total = conn.execute(
            """
            SELECT COALESCE(SUM(count_value), 0)
            FROM metric_snapshots
            WHERE repo_id = ?
              AND metric = ?
              AND day >= ?
            """,
            (repo_id, metric, start_day),
        ).fetchone()[0]
        print(f"{slug:40s} total={int(total)}")


def check_alerts(conn: sqlite3.Connection, repo_slug: str, metric: str, window: int, drop: float, spike: float) -> int:
    owner, repo = parse_repo(repo_slug)
    row = conn.execute(
        "SELECT id FROM repositories WHERE owner = ? AND name = ?", (owner, repo)
    ).fetchone()
    if row is None:
        print(f"No data for {repo_slug}")
        return 1
    repo_id = int(row[0])

    series = conn.execute(
        """
        SELECT day, SUM(count_value) AS total
        FROM metric_snapshots
        WHERE repo_id = ? AND metric = ?
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
        """,
        (repo_id, metric, window + 1),
    ).fetchall()
    if len(series) < window + 1:
        print(f"Not enough data for {repo_slug} metric={metric}. Need at least {window + 1} daily points.")
        return 1

    latest_day, latest_value = series[0]
    baseline = [int(v) for _, v in series[1:]]
    avg = sum(baseline) / len(baseline)
    if avg <= 0:
        print("Baseline average is zero; skipping alert evaluation.")
        return 0

    change_ratio = (float(latest_value) - avg) / avg
    print(
        f"{repo_slug} metric={metric} latest={int(latest_value)} baseline_avg={avg:.2f} "
        f"change={change_ratio * 100:.1f}%"
    )

    if change_ratio <= -drop:
        print(f"ALERT: drop threshold breached on {latest_day} ({change_ratio * 100:.1f}%).")
        return 2
    if change_ratio >= spike:
        print(f"ALERT: spike threshold breached on {latest_day} ({change_ratio * 100:.1f}%).")
        return 2

    print("No alert thresholds breached.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect and report GitHub traffic/release analytics into SQLite."
    )
    parser.add_argument(
        "--db",
        default="analytics/traffic_analytics.db",
        help="Path to SQLite DB file.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize analytics database schema.")

    collect = sub.add_parser("collect", help="Collect snapshots for one or more repos.")
    collect.add_argument(
        "--repos",
        required=True,
        nargs="+",
        help="Repository slugs in owner/repo form.",
    )
    collect.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing GitHub token.",
    )

    report = sub.add_parser("report", help="Print traffic + release report for a repo.")
    report.add_argument("--repo", required=True, help="Repository in owner/repo form.")
    report.add_argument("--days", type=int, default=14, help="Number of days for traffic rollup.")

    compare = sub.add_parser("compare", help="Compare a metric across repos.")
    compare.add_argument("--repos", required=True, nargs="+", help="Repos to compare.")
    compare.add_argument(
        "--metric",
        default="views",
        choices=["views", "clones", "referrers", "paths", "release_downloads"],
    )
    compare.add_argument("--days", type=int, default=14)

    alerts = sub.add_parser("alerts", help="Check traffic alert thresholds for a repo.")
    alerts.add_argument("--repo", required=True)
    alerts.add_argument("--metric", default="views", choices=["views", "clones"])
    alerts.add_argument("--window", type=int, default=7)
    alerts.add_argument(
        "--drop-threshold",
        type=float,
        default=0.40,
        help="Alert when latest value is this fraction below baseline average.",
    )
    alerts.add_argument(
        "--spike-threshold",
        type=float,
        default=1.00,
        help="Alert when latest value exceeds this fraction above baseline average.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    db_path = args.db
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        ensure_db(conn)

        if args.command == "init-db":
            print(f"Initialized DB schema: {db_path}")
            return 0

        if args.command == "collect":
            token = os.getenv(args.token_env)
            if not token:
                parser.error(f"Missing token: set environment variable {args.token_env}. See analytics/README.md for authentication setup.")
            for slug in args.repos:
                owner, repo = parse_repo(slug)
                print(f"Collecting {slug}...")
                collect_repo(conn, owner, repo, token)
            print("Collection complete.")
            return 0

        if args.command == "report":
            print_report(conn, args.repo, max(args.days, 1))
            return 0

        if args.command == "compare":
            compare_repos(conn, args.repos, args.metric, max(args.days, 1))
            return 0

        if args.command == "alerts":
            return check_alerts(
                conn,
                repo_slug=args.repo,
                metric=args.metric,
                window=max(args.window, 2),
                drop=max(args.drop_threshold, 0.0),
                spike=max(args.spike_threshold, 0.0),
            )

        parser.error(f"Unknown command: {args.command}")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
