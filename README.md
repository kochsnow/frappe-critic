# Frappe Critic

Frappe Critic is a developer-preview Frappe app that runs Semgrep-based checks against installed Frappe/ERPNext/HRMS apps and displays the findings inside a Frappe Desk page.

Current status: MVP / developer preview. The scan flow works end-to-end; AI Fix is present in the UI but still needs the settings/configuration path to be completed before it is ready for general use.

## What works today

- Docker-based local development environment for Frappe v15.
- Installs Frappe, ERPNext, HRMS, and this app into a local bench.
- Critic Dashboard at `/app/critic-dashboard`.
- Select installed apps and run a Semgrep scan.
- View findings with app, file path, line number, severity, message, and an AI Fix action placeholder.

## What is not finished yet

- AI Fix configuration and `Critic Settings` need hardening before public use.
- Findings table has no pagination/filtering yet.
- Rules are early-stage and may produce noisy results.
- Production deployment is not supported by the included Docker Compose setup.

## Quick start

Prerequisites:

- Docker Desktop
- Images available locally or pullable from Docker Hub:
  - `frappe/bench:v5.25.8`
  - `mariadb:10.11`
  - `redis:alpine`

From this directory:

```bash
docker compose up
```

The first run can take a while because it initializes a Frappe bench, installs apps, creates a site, and installs Semgrep.

Open:

```text
http://localhost:8000
```

Default local credentials:

```text
User: Administrator
Password: admin
```

If Frappe shows the setup wizard, complete it with any local test company details. Then open:

```text
http://localhost:8000/app/critic-dashboard
```

Select `hrms` and click **Start Scan**. A successful local smoke test should transition through queued/running states, then show a completed scan with findings.

## Useful development commands

Open a shell in the Frappe container:

```bash
docker compose exec frappe bash
```

Then from inside the container:

```bash
cd /home/frappe/frappe-bench
bench --site hrms.localhost list-apps
bench --site hrms.localhost execute frappe_critic.api.get_scan_options
```

Run a scan from the command line:

```bash
bench --site hrms.localhost execute frappe_critic.api.start_scan --kwargs '{"selected_apps": "[\"hrms\"]", "scope": "Installed"}'
```

Check scan status:

```bash
bench --site hrms.localhost execute frappe_critic.api.get_scan_status --kwargs '{"audit_log_name": "YOUR_AUDIT_LOG_NAME"}'
```

## Resetting local state

This deletes the local database and bench volume:

```bash
docker compose down -v
```

Use it only when you intentionally want a fresh local environment.

## Repository layout

```text
.
├── docker-compose.yml          # Local development stack
├── init.sh                     # Bootstraps the Frappe bench in Docker
├── frappe_critic/
│   ├── setup.py                # Python package metadata for the Frappe app
│   ├── frappe_critic/          # Frappe app package
│   │   ├── api.py              # Whitelisted API methods and scan job
│   │   └── frappe_critic/
│   │       ├── doctype/        # Critic Audit Log / Finding / Settings doctypes
│   │       ├── page/           # Critic Dashboard page
│   │       └── scanner/        # Semgrep integration
│   └── rules/                  # Bundled Semgrep rules
└── docs/
```

## License

License is not selected yet. Choose one before publishing the repository publicly.
