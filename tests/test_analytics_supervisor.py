"""Smoke tests for analytics_supervisor.

These tests avoid any real network I/O by monkeypatching the collector's
HTTP helper. They verify:

  * exit code 0 on a clean run
  * exit code 3 when the token is missing
  * exit code 3 when collect raises
  * exit code 2 when an alert threshold is breached
  * GITHUB_STEP_SUMMARY is written when set
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ANALYTICS_DIR = Path(__file__).resolve().parents[1] / "analytics"
sys.path.insert(0, str(ANALYTICS_DIR))

import analytics_supervisor as sup  # noqa: E402
import github_traffic_analytics as gta  # noqa: E402


def _fake_api(views_counts: list[int]):
    """Return a fake github_get that serves deterministic payloads."""

    def _get(url: str, token: str):
        if url.endswith("/traffic/views"):
            return {
                "views": [
                    {
                        "timestamp": f"2026-05-{20 + i:02d}T00:00:00Z",
                        "count": c,
                        "uniques": max(c // 2, 1),
                    }
                    for i, c in enumerate(views_counts)
                ]
            }
        if url.endswith("/traffic/clones"):
            return {"clones": []}
        if url.endswith("/traffic/popular/referrers"):
            return []
        if url.endswith("/traffic/popular/paths"):
            return []
        if "/releases" in url:
            return []
        raise AssertionError(f"unexpected URL: {url}")

    return _get


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("INPUT_REPOS", raising=False)
    monkeypatch.delenv("DEFAULT_REPO", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.chdir(tmp_path)


def _run(monkeypatch, tmp_path, *, views, token="x"):
    if token is None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.setattr(gta, "github_get", _fake_api(views))
    monkeypatch.setattr(gta, "github_paginated", lambda url, tok: [])
    db = tmp_path / "t.db"
    return sup.main(
        [
            "--db",
            str(db),
            "--repos",
            "octo/repo",
            "--window",
            "3",
            "--drop-threshold",
            "0.40",
            "--spike-threshold",
            "1.00",
        ]
    )


def test_clean_run_exits_zero(monkeypatch, tmp_path):
    code = _run(monkeypatch, tmp_path, views=[10, 11, 9, 10, 12])
    assert code == sup.EXIT_OK


def test_missing_token_exits_collect_fail(monkeypatch, tmp_path):
    code = _run(monkeypatch, tmp_path, views=[1], token=None)
    assert code == sup.EXIT_COLLECT_FAIL


def test_collect_failure_exits_three(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    def _boom(url, token):
        raise RuntimeError("boom")

    monkeypatch.setattr(gta, "github_get", _boom)
    monkeypatch.setattr(gta, "github_paginated", lambda url, tok: [])
    code = sup.main(["--db", str(tmp_path / "t.db"), "--repos", "octo/repo"])
    assert code == sup.EXIT_COLLECT_FAIL


def test_spike_breach_exits_two(monkeypatch, tmp_path):
    # Baseline ~10, latest 100 => spike well over 1.0.
    code = _run(monkeypatch, tmp_path, views=[10, 10, 10, 10, 100])
    assert code == sup.EXIT_ALERT


def test_step_summary_written(monkeypatch, tmp_path):
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    code = _run(monkeypatch, tmp_path, views=[10, 11, 9, 10, 12])
    assert code == sup.EXIT_OK
    assert summary_file.exists()
    text = summary_file.read_text(encoding="utf-8")
    assert "Traffic analytics run" in text
    assert "octo/repo" in text


def test_repo_resolution_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("DEFAULT_REPO", "octo/repo")
    monkeypatch.setattr(gta, "github_get", _fake_api([10, 10, 10, 10, 10]))
    monkeypatch.setattr(gta, "github_paginated", lambda url, tok: [])
    code = sup.main(["--db", str(tmp_path / "t.db")])
    assert code == sup.EXIT_OK


def test_json_summary_emitted(monkeypatch, tmp_path, capsys):
    _run(monkeypatch, tmp_path, views=[10, 11, 9, 10, 12])
    out = capsys.readouterr().out
    # The JSON block is printed after the "=== summary ===" header.
    blob = out.split("=== summary ===", 1)[1].strip()
    parsed = json.loads(blob)
    assert parsed["repos"][0]["repo"] == "octo/repo"
    assert parsed["repos"][0]["collect_ok"] is True
