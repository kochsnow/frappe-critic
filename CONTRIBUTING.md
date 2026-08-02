# Contributing

Thanks for taking a look at Frappe Critic.

This project is currently a developer-preview Frappe app. Before contributing, please assume APIs, doctypes, and UI details may still change.

## Local development

Start the local stack:

```bash
docker compose up
```

Open:

```text
http://localhost:8000/app/critic-dashboard
```

Default credentials:

```text
Administrator / admin
```

## Before opening a PR

- Keep generated files out of commits (`__pycache__`, `.egg-info`, database backups, logs).
- Run a dashboard smoke test:
  - select `hrms`
  - click **Start Scan**
  - confirm the scan reaches `Done`
  - confirm findings render in the table
- If you change DocTypes, run:

```bash
docker compose exec frappe bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate'
```

## Project boundaries

The included Docker Compose stack is for local development only. Do not treat it as a production deployment recipe.
