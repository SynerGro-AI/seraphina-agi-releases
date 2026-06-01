# Organization Setup: GitHub Traffic Analytics

This document captures the one-time organization setup for running `.github/workflows/traffic-analytics.yml` across all non-archived repositories in `SynerGro-AI`.

## 1) Create the fine-grained PAT

1. Go to <https://github.com/settings/personal-access-tokens/new>.
2. Configure:
   - **Resource owner**: `SynerGro-AI`
   - **Repository access**: `All repositories`
3. Set repository permissions to **Read-only**:
   - **Metadata**: Read
   - **Contents**: Read
   - **Administration**: Read
4. Generate and copy the token value.

## 2) Store as organization Actions secret

1. Go to <https://github.com/organizations/SynerGro-AI/settings/secrets/actions/new>.
2. Set:
   - **Name**: `GH_ANALYTICS_TOKEN`
   - **Value**: paste the fine-grained PAT
   - **Repository access**: `All repositories`
3. Save the secret.

## 3) Approve PAT if org policy requires it

If the token is pending approval, approve it at:

- <https://github.com/organizations/SynerGro-AI/settings/personal-access-tokens>

## 4) Run workflow manually

1. Open the repository Actions tab.
2. Select **Traffic Analytics**.
3. Click **Run workflow**.
4. Optionally set `extra_repos` as a space-separated list of `owner/repo` values.

## 5) Download and inspect artifacts

1. Open the workflow run.
2. Download artifact `traffic-analytics-<run_id>`.
3. Query locally:

```bash
sqlite3 analytics/traffic_analytics.db '.tables'
sqlite3 analytics/traffic_analytics.db 'SELECT owner, name FROM repositories ORDER BY owner, name;'
```

## Notes

- Archived repositories in `SynerGro-AI` are skipped automatically.
- Use `extra_repos` to include repositories outside the org for one-off collection runs.
