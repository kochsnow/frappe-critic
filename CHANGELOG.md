# Changelog

## [0.1.0] - 2026-08-03

- Added safe Finding-to-Harbor 1.3 task conversion from the Dashboard.
- Added private task directories and downloadable ZIP artifacts with SHA-256
  checksums and source-drift protection.
- Added isolated source snapshots, bundled Semgrep rules, and generated syntax
  and finding-specific verification scripts.
- Added the Critic Remediation Task DocType and remediation state on findings.
- Added explicit preparation-only UI states and visible backend errors; task
  preparation does not run an agent or modify scanned source.
- Restored Critic Settings as app metadata and added an experimental review-only
  online AI preview backend.
- Added unit coverage for Harbor task structure, verifier generation, source
  drift, safe paths, and AI response parsing.

## [0.0.1] - 2026-07-31

- Added Docker-based Frappe v15 local development environment.
- Added Critic Dashboard page.
- Added Semgrep scan flow for installed Frappe apps.
- Added Critic Audit Log and Critic Finding doctypes.
- Added findings table rendering in Desk.
- Fixed dashboard scan button event handling.
- Fixed initial `ai_status` values to match DocType options.
- Added open-source readiness docs and ignore rules.
