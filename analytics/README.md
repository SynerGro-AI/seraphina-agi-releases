# GitHub Traffic Analytics MVP

This directory contains a lightweight analytics collector + CLI for GitHub traffic and release download metrics.

## Metrics captured

- Traffic views (`count`, `uniques`) via `/traffic/views`
- Clone activity (`count`, `uniques`) via `/traffic/clones`
- Popular referrers via `/traffic/popular/referrers`
- Popular paths via `/traffic/popular/paths`
- Release asset download counts via `/releases`

## Data model

All metrics are stored in a normalized snapshot table in SQLite:

- `repositories(owner, name)`
- `metric_snapshots(repo_id, day, metric, source, dimension, count_value, uniques_value, metadata_json, collected_at)`

This enables cross-repo comparison by `(repo, day, metric, source)` while preserving dimensions (path/referrer/asset).

## Authentication and permissions

Use `GH_ANALYTICS_TOKEN` as either:

1. A GitHub App installation token (recommended), or
2. A fine-grained PAT for pilot testing.

Recommended minimum repository permissions for GitHub App installation:

- **Metadata**: Read
- **Contents**: Read
- **Administration**: Read (required for traffic endpoints)

Install the app only on repositories you want to track.

## CLI usage

Initialize DB:

```bash
python analytics/github_traffic_analytics.py init-db --db analytics/traffic_analytics.db
```

Collect snapshots:

```bash
export GITHUB_TOKEN="<token>"
python analytics/github_traffic_analytics.py collect --db analytics/traffic_analytics.db --repos SynerGro-AI/seraphina-agi-releases
```

Show report:

```bash
python analytics/github_traffic_analytics.py report --db analytics/traffic_analytics.db --repo SynerGro-AI/seraphina-agi-releases --days 14
```

Compare repositories:

```bash
python analytics/github_traffic_analytics.py compare --db analytics/traffic_analytics.db --repos owner/repo1 owner/repo2 --metric views --days 14
```

Alert checks:

```bash
python analytics/github_traffic_analytics.py alerts --db analytics/traffic_analytics.db --repo SynerGro-AI/seraphina-agi-releases --metric views --window 7 --drop-threshold 0.40 --spike-threshold 1.00
```

Exit status for `alerts`:

- `0`: no threshold breach
- `2`: threshold breached (spike/drop)

## Scheduled collection

Workflow: `.github/workflows/traffic-analytics.yml`

- Runs daily and on manual dispatch.
- Stores SQLite DB as an artifact for dashboard/CLI consumption.
- Uses `GH_ANALYTICS_TOKEN` secret.

## Pilot scope

Use this repo as the initial pilot (`SynerGro-AI/seraphina-agi-releases`), then add more repos in workflow dispatch input.
