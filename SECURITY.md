# Security Policy

Frappe Critic is itself a security-oriented developer tool, but it is still in developer preview.

## Supported versions

`0.1.x` is the currently supported developer-preview release line. Security
fixes target the latest release and the `main` branch.

## Reporting a vulnerability

Use [GitHub Security Advisories](https://github.com/kochsnow/frappe-critic/security/advisories/new)
to report vulnerabilities privately. If private reporting is unavailable,
open a minimal issue requesting a private contact channel without including
exploit details.

Please avoid publishing exploit details publicly before a fix or mitigation is available.

## Current security notes

- The included Docker Compose setup uses development credentials and is not production-safe.
- The AI Fix flow is experimental and should not receive secrets or proprietary code until the settings and data-handling model are reviewed.
- Semgrep findings are advisory and should be manually reviewed.
