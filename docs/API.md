# API contracts

Prefix /api/v1. Account endpoints use /api/auth/register, /login, /session, /logout. All account-authenticated writes require X-CSRF-Token. Browser Origin must match ALLOWED_ORIGINS. All durable inventory writes require Idempotency-Key (1-100 characters).

| Method | Endpoint | Purpose |
|---|---|---|
| GET/POST | /suppliers | List/create suppliers |
| GET/POST | /warehouses | List/create warehouses |
| GET/POST | /products | List/create product policies |
| PATCH | /products/{id} | Update a product |
| GET | /balances | Current quantities |
| GET/POST | /movements | Read ledger / post stock mutation |
| GET/POST | /purchase-orders | List/create purchase orders |
| POST | /purchase-orders/{id}/receive | Receive selected line quantities |
| POST | /purchase-orders/{id}/cancel | Cancel unreceived remainder |
| GET | /supplier-performance | Receipt lead times and overdue counts |
| POST | /imports/demand/preview | Validate CSV rows |
| POST | /imports/demand/apply | Add demand history, no physical stock changes |
| GET/POST | /analyses | List/create saved analytics |
| GET | /analyses/{id}/report?format=json or csv | Export |
| POST | /demo | Add synthetic data to an empty catalog |

Monetary and quantity decimals are transported as strings. Product policy integers are lead_days,safety_days,review_days,pack_size,minimum_order. Movement kinds are receipt,sale,issue,adjustment_in,adjustment_out,transfer. Transfer requires destination_id. Note is required.

Purchase request: supplier_id,warehouse_id,expected_date,lines:[{product_id,quantity,unit_cost}]. Receive request: lines:[{line_id,quantity}]. Product supplier must match order supplier. Partial receipt changes status to partial; complete receipt changes to received. Cancellation retains receipt history/stock and closes outstanding remainder.

Errors use {error:{code,message,fields?}}. 401: sign-in required;403: CSRF/origin;404: unknown/foreign record;409: insufficient stock, closed order, duplicate conflict;422: contract validation or over-limit inputs. Login throttling returns429.

Same durable key plus matching inputs returns the original response. A changed input returns409. Keys are scoped by user and operation. Demand import additionally fingerprints exact CSV bytes and warehouse; changed or overlapping file content is not automatically reconciled. GET ledger returns latest500; dashboard displays100. GET analyses returns latest100. Pagination is a future improvement.
