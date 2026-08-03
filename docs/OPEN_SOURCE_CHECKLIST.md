# Open-source readiness checklist

## Done

- Local Docker development stack starts.
- Frappe site can be opened at `http://localhost:8000`.
- `frappe_critic` installs alongside Frappe, ERPNext, and HRMS.
- Critic Dashboard loads at `/app/critic-dashboard`.
- Scan flow reaches `Done`.
- Findings API returns results.
- Generated files and local backups are ignored by `.gitignore`.
- Basic README, contributing notes, changelog, and security policy are present.
- MIT repository license is present.
- Publisher and license package metadata are filled.
- Dashboard remediation prepares Harbor artifacts without calling an AI provider
  or modifying source; direct online AI preview remains experimental.
- `Critic Settings` is included in app metadata and migrates cleanly.
- Private notes remain outside the repository and are not tracked.
- Tracked files were checked for generated archives, database files, site
  configuration, and non-development credentials.

## Before public launch

- Add a public project contact email when one is available.
- Run a fresh clone smoke test:

```bash
docker compose up
```

Then verify:

- login works with `Administrator / admin`
- setup wizard completes
- `/app/critic-dashboard` loads
- scan on `hrms` reaches `Done`
- findings render

## Recommended first release scope

Ship `v0.1.0` with this positioning:

> Developer preview of a Semgrep-based security review dashboard for Frappe apps.

Present Harbor task preparation as the supported remediation boundary. Do not
present direct online AI preview or automatic patch application as stable.
