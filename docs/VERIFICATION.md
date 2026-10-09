# Release verification - v1.0.0

25 backend tests passed, covering reference analytics, replenishment edges, stock-negative guard, transfers, purchase receiving/replay, multi-line rollback, cancellation, demand import replay, unknown SKUs, owner isolation, product editing/snapshot preservation, CSRF/origin/authentication and exports.

Python lint and formatting passed. React production build passed. SQLite migration upgrade and Alembic metadata/schema check passed. Browser workflow passed with Chromium: account registration, demo data, analysis, recommendation-based purchase order, partial receipt, warehouse creation, transfer, invalid and valid CSV import, report download, mobile overflow check, session reload and logout. No JavaScript page errors occurred. Screenshots in docs come from the running application.

Docker is unavailable locally: Docker image/Compose startup and PostgreSQL-specific runtime/concurrency were not verified. CI includes a Docker image build but its remote outcome has not been checked. Dependencies emit one TestClient deprecation warning while tests pass.

No billing, shared teams/RBAC, true accounting valuation, statistical forecasting or external storefront connector is included. This is a functional inventory ERP first release for local evaluation and further development.
