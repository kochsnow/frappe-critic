# Security Policy

Frappe Critic is itself a security-oriented developer tool, but it is still in developer preview.

## Supported versions

No stable release line exists yet. Until the first public release, security fixes should target the main development branch.

## Reporting a vulnerability

If this repository is published publicly, add a private reporting path here before launch, such as:

- GitHub private vulnerability reporting, or
- a dedicated security email address.

Please avoid publishing exploit details publicly before a fix or mitigation is available.

## Current security notes

- The included Docker Compose setup uses development credentials and is not production-safe.
- The AI Fix flow is experimental and should not receive secrets or proprietary code until the settings and data-handling model are reviewed.
- Semgrep findings are advisory and should be manually reviewed.
