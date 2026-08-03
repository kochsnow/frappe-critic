# Frappe Critic

Frappe Critic is a developer-preview Frappe app that runs Semgrep-based checks against installed Frappe/ERPNext/HRMS apps and displays the findings inside a Frappe Desk page.

Current status: MVP / developer preview. Scanning and the first safe remediation step work end-to-end: an individual finding can be exported as a private Harbor task package without running an agent or changing source code.

## What works today

- Docker-based local development environment for Frappe v15.
- Installs Frappe, ERPNext, HRMS, and this app into a local bench.
- Critic Dashboard at `/app/critic-dashboard`.
- Select installed apps and run a Semgrep scan.
- View findings with app, file path, line number, severity, and message.
- Convert a finding into a Harbor 1.3 task with an isolated source snapshot,
  bundled Semgrep verifier, metadata, checksums, and a private ZIP download.
- Reuse a previously prepared task from the findings table.

## What is not finished yet

- Direct online AI preview settings remain experimental and are not the default
  Dashboard flow.
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

Click **Prepare AI Fix** on a finding to create the Harbor task artifact. The
result dialog shows its private path and SHA-256 checksum and offers the ZIP for
download. This action is preparation-only: it does not call an AI provider or
modify the scanned app.

The ZIP follows Harbor's task layout:

```text
<task>/
├── instruction.md
├── task.toml
├── environment/
│   ├── Dockerfile
│   └── workspace/       # source snapshot
├── tests/
│   ├── test.sh
│   ├── verify.py
│   └── rules/           # bundled Frappe Critic rules
└── context/
    └── finding.json
```

## Remediation with Harbor agents

The downloaded ZIP can be used with the broader
[Harbor agent ecosystem](https://www.harborframework.com/docs/agents), so agent
selection and execution stay outside Frappe Critic. A typical workflow is:

```text
Download and extract the Harbor task ZIP
→ run the task with a Harbor-supported agent
→ let the agent modify the isolated source snapshot
→ run the included tests/test.sh verifier
→ review the resulting changes and verification reward
→ apply the approved patch to the original app or repository
→ run Frappe Critic again to confirm the finding is resolved
```

For example, from a machine with Harbor and its container runtime configured:

```bash
harbor run -p /path/to/extracted/task -a <agent> -m <model>
```

Frappe Critic deliberately does not embed an agent runner or automatically apply
generated changes. This keeps source modification under user control and avoids
duplicating Harbor's agent orchestration. The included development Frappe
container therefore does not require Harbor, a Docker CLI, or a Docker socket.

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

Prepare a finding as a Harbor task:

```bash
bench --site hrms.localhost execute frappe_critic.api.prepare_harbor_task --kwargs '{"finding_name": "YOUR_FINDING_NAME"}'
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

Frappe Critic is licensed under the [MIT License](LICENSE).

Bundled rules under `frappe_critic/rules/` retain their original copyright and
MIT license notices.
