# Contributing

Use Python3.12 and Node24. Separate API validation, transaction rules and pure analytics. Comments should explain stock invariants, transaction timing, replay scope and analytical assumptions. Avoid comments that only restate assignments.

Backend checks from backend: pytest -q; ruff check app tests migrations; ruff format --check app tests migrations; alembic upgrade head; alembic check. Frontend: npm ci; npm run format:check; npm run build. GitHub Actions includes these and a Docker build. Changes to database fields require a new Alembic revision; never rewrite a deployed migration.

Add tests for negative-stock/race risks, tenant boundaries, partial receipt rollback and changed formulas. Use only synthetic records. Never commit .env, passwords, databases, node_modules or personal data. Document a feature's observable behavior, validation and remaining limits in each PR.
