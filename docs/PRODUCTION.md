# Deployment and limitations

Functional first release with private account storage. Not a complete enterprise suite: no billing, shared team/RBAC, accounting, manufacturing/BOM, lots/expiry, reservations/backorders, barcode devices, customer orders, external storefront integration, or automatic purchasing emails.

Before public use: verify Docker/PostgreSQL migrations and concurrent receipt/stock workflows against the actual PostgreSQL server; use HTTPS/COOKIE_SECURE=true, exact allowed origins, backups and restore tests, email verification/password recovery, centralized auth rate limits and account audit/retention policies. Restrict request body/row sizes at the proxy and monitor slow snapshot queries. Read lists currently have bounded history limits but not full pagination. Improve transaction-consistent reporting with a read isolation policy and materialized aggregation when data volume grows.

Compose exposes only localhost:8083. PostgreSQL is private. Use a secret manager and do not commit .env or data. The app container runs as a non-root user and executes migrations before startup. The included CI builds the image; local Docker was unavailable during authoring.

Stocks must be corrected using compensating movements, not by editing history. Imported CSV cannot prove external-source completeness; keep source records and avoid overlapping feeds. Prototype concurrency controls use conditional SQL and a unique replay receipt; test real multi-client workloads before release.
