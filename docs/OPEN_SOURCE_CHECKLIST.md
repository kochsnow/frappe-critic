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

## Before public launch

- Choose and add a repository license.
- Fill package metadata:
  - publisher / author
  - contact email
  - license field
- Decide whether AI Fix is included in the first public release or marked hidden/experimental.
- Verify `Critic Settings` is installed and migrated cleanly.
- Remove or archive private notes outside the public repository.
- Confirm no secrets, database dumps, local credentials, or generated artifacts are tracked.
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

Ship as `v0.1.0-dev` or `v0.1.0-alpha` with this positioning:

> Developer preview of a Semgrep-based security review dashboard for Frappe apps.

Do not present AI Fix as stable until settings, data handling, and error states are complete.
