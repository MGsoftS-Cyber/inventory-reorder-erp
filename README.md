# InventoryIQ - Inventory & Reorder ERP

A standalone inventory and purchasing application with explainable replenishment analytics. Built for online stores, wholesalers and small industrial stock operations. This is an inventory ERP module, not a complete accounting or manufacturing suite.

## Languages and tools

Python 3.12 / FastAPI: validation, authenticated workflows and pure Decimal calculations. JavaScript / React 19: responsive dashboard. SQL / PostgreSQL 17: production-oriented relational storage. SQLite: local development/tests. SQLAlchemy / Alembic: persistence and migrations. CSS: responsive layout. YAML: Docker Compose and GitHub Actions.

## Docker quick start

Install Docker Desktop (WSL2 backend on Windows). From the project root:

```bash
# PowerShell: Copy-Item .env.example .env
# Linux/macOS:
cp .env.example .env
# Edit .env and set a long URL-safe POSTGRES_PASSWORD
# Do not commit .env
docker compose up --build
```

Open http://localhost:8083. Register an account using a password of at least 12 characters. There is no default login or password. In an empty catalog, **Load demo data**, then **Run inventory analysis**. The first demo product needs 50 units. Choose **Create order**, receive part of it, and rerun analytics to see how stock and incoming quantities change. Demo data is synthetic; no external supplier is contacted.

`docker compose down` retains the database volume. Adding `-v` deletes its data. The database port is not exposed publicly. This application has its own cookie, port and database volume so it can run alongside the three finance projects.

## Local development

Use Python 3.12 and Node 24. In backend:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8003
```

In another terminal, in frontend:

```bash
npm ci
npm run dev
```

Open http://localhost:5176. SQLite is the default; set DATABASE_URL for PostgreSQL. The Vite proxy keeps browser requests same-origin. Swagger documentation: http://localhost:8003/docs.

## Screens and capabilities

- Overview: demand rate, stock coverage, ABC, slow-moving items and pack-rounded order suggestions.
- Catalog: create suppliers/warehouses/products and edit replenishment policies.
- Stock: receipts, issues, sales, adjustments, transfers and ledger history.
- Purchasing: internal orders, partial receiving, cancellation of unreceived quantities and supplier receipt lead times.
- Demand imports: preview and apply historical demand CSVs without changing physical stock.
- Reports: immutable input/result snapshots with JSON and CSV downloads.

API supports multi-line purchase orders and multi-line receipt transactions. The initial dashboard creates one product line per order. Private records belong to the signed-in account; shared team roles are not included.

## Financial and analytical conventions

All monetary amounts use USD. Cost values are estimates at current standard cost, not FIFO/weighted-average accounting valuation. Replenishment uses observed sold units divided by calendar days, configured lead/safety/review days, outstanding purchases, minimum order and pack size. It has no trained AI model. Stockouts can hide demand. No reservations/backorders/seasonality or multi-warehouse pooling. Current-stock unit turnover is explicitly labeled a proxy.

CSV header: `date,sku,quantity,revenue`. Demand imports are separate from the stock ledger. Do not import sales already recorded as sale movements. Identical bytes + warehouse replay the existing import; changed/overlapping files need review. All units are treated as product base units, without conversion.

## Verification and development documentation

See docs/VERIFICATION.md, docs/ARCHITECTURE.md, docs/METHODOLOGY.md, docs/API.md, docs/PRODUCTION.md and CONTRIBUTING.md. The separate PDF delivery provides the detailed conception and programming walkthrough. Docker/PostgreSQL startup is not verified in the authoring environment; verify it locally before deployment.

## Optional browser check

With the API serving built frontend assets on port8003 and a disposable database, install Playwright Core in frontend (`npm install --no-save --package-lock=false playwright-core`), set CHROMIUM_EXECUTABLE to a compatible Chromium path, then run `node browser_smoke.cjs` from frontend. Do not target a production account/database. This script creates synthetic records and screenshots.
