from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from app.engine import calculate
from app.imports import preview_demand


def write(client, path, body=None, key=None):
    return client.post("/api/v1" + path, json=body, headers={"Idempotency-Key": key or uuid4().hex})


def register(client, email="owner@example.com"):
    response = client.post("/api/auth/register", json={"email": email, "password": "test-long-password"})
    assert response.status_code == 201
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def setup(client):
    register(client)
    supplier = write(client, "/suppliers", {"name": "Supply"}).json()
    warehouse = write(client, "/warehouses", {"name": "Main"}).json()
    product = write(
        client,
        "/products",
        {
            "sku": "A",
            "name": "Item A",
            "supplier_id": supplier["id"],
            "unit_cost": "10",
            "selling_price": "20",
            "lead_days": 10,
            "safety_days": 5,
            "review_days": 7,
            "pack_size": 10,
            "minimum_order": 10,
        },
    ).json()
    return supplier, warehouse, product


def stock(client, w, p, qty, kind="receipt", **kwargs):
    return write(
        client,
        "/movements",
        {
            "product_id": p["id"],
            "warehouse_id": w["id"],
            "quantity": str(qty),
            "kind": kind,
            "note": "test movement",
            **kwargs,
        },
    )


def test_stock_sale_and_negative_guard(client):
    s, w, p = setup(client)
    assert stock(client, w, p, 5).status_code == 201
    assert stock(client, w, p, 2, "sale").status_code == 201
    assert stock(client, w, p, 4, "issue").status_code == 409
    assert Decimal(client.get("/api/v1/balances").json()[0]["quantity"]) == 3
    analysis = write(client, "/analyses", {"warehouse_id": w["id"], "lookback_days": 7}).json()
    assert Decimal(analysis["results"]["products"][0]["sold"]) == 2


def test_transfer_atomicity(client):
    s, w, p = setup(client)
    stock(client, w, p, 5)
    w2 = write(client, "/warehouses", {"name": "Branch"}).json()
    assert stock(client, w, p, 6, "transfer", destination_id=w2["id"]).status_code == 409
    assert stock(client, w, p, 3, "transfer", destination_id=w2["id"]).status_code == 201
    balances = {x["warehouse_id"]: Decimal(x["quantity"]) for x in client.get("/api/v1/balances").json()}
    assert balances == {w["id"]: 2, w2["id"]: 3}
    assert stock(client, w, p, 1, "transfer", destination_id=w["id"]).status_code == 422


def order(client, s, w, p, qty=20):
    return write(
        client,
        "/purchase-orders",
        {
            "supplier_id": s["id"],
            "warehouse_id": w["id"],
            "expected_date": str(date.today() + timedelta(days=10)),
            "lines": [{"product_id": p["id"], "quantity": str(qty), "unit_cost": "10"}],
        },
    ).json()


def test_partial_receive_replay_and_over_receipt(client):
    s, w, p = setup(client)
    po = order(client, s, w, p)
    path = f"/purchase-orders/{po['id']}/receive"
    body = {"lines": [{"line_id": po["lines"][0]["id"], "quantity": "5"}]}
    a = write(client, path, body, key="receipt-1")
    assert a.status_code == 200
    assert a.json()["status"] == "partial"
    assert write(client, path, body, key="receipt-1").json() == a.json()
    bad = {"lines": [{"line_id": po["lines"][0]["id"], "quantity": "16"}]}
    assert write(client, path, bad).status_code == 409
    assert Decimal(client.get("/api/v1/balances").json()[0]["quantity"]) == 5
    last = {"lines": [{"line_id": po["lines"][0]["id"], "quantity": "15"}]}
    assert write(client, path, last).json()["status"] == "received"
    assert write(client, path, body).status_code == 409
    assert client.get("/api/v1/supplier-performance").json()[0]["receipt_count"] == 2


def test_cancellation_removes_incoming(client):
    s, w, p = setup(client)
    po = order(client, s, w, p)
    a = write(client, "/analyses", {"warehouse_id": w["id"]}).json()
    assert Decimal(a["results"]["products"][0]["incoming"]) == 20
    assert write(client, f"/purchase-orders/{po['id']}/cancel").json()["status"] == "cancelled"
    b = write(client, "/analyses", {"warehouse_id": w["id"]}).json()
    assert Decimal(b["results"]["products"][0]["incoming"]) == 0
    assert client.get("/api/v1/analyses").json()[1]["inputs"] == a["inputs"]


def test_import_preview_apply_replay(client):
    s, w, p = setup(client)
    text = f"date,sku,quantity,revenue\n{date.today()},A,30,600\n"
    body = {"warehouse_id": w["id"], "csv_text": text}
    assert write(client, "/imports/demand/preview", {"csv_text": text}).json()["valid"]
    assert write(client, "/imports/demand/apply", body).json()["imported"] == 1
    assert write(client, "/imports/demand/apply", body).json()["imported"] == 1
    a = write(client, "/analyses", {"warehouse_id": w["id"], "lookback_days": 30}).json()
    assert Decimal(a["results"]["products"][0]["sold"]) == 30
    assert client.get("/api/v1/balances").json() == []


def test_unknown_import_atomic(client):
    s, w, p = setup(client)
    text = f"date,sku,quantity,revenue\n{date.today()},A,30,600\n{date.today()},UNKNOWN,1,20"
    assert write(client, "/imports/demand/apply", {"warehouse_id": w["id"], "csv_text": text}).status_code == 422
    a = write(client, "/analyses", {"warehouse_id": w["id"]}).json()
    assert Decimal(a["results"]["products"][0]["sold"]) == 0


def test_account_isolation(client):
    s, w, p = setup(client)
    a = write(client, "/analyses", {"warehouse_id": w["id"]}).json()
    client.post("/api/auth/logout")
    register(client, "other@example.com")
    assert client.get("/api/v1/products").json() == []
    assert stock(client, w, p, 1).status_code == 404
    assert write(client, "/analyses", {"warehouse_id": w["id"]}).status_code == 404
    assert client.get(f"/api/v1/analyses/{a['id']}/report").status_code == 404


def test_idempotency_conflict(client):
    register(client)
    a = write(client, "/warehouses", {"name": "One"}, key="same")
    b = write(client, "/warehouses", {"name": "One"}, key="same")
    assert a.json() == b.json()
    assert write(client, "/warehouses", {"name": "Two"}, key="same").status_code == 409
    assert client.post("/api/v1/warehouses", json={"name": "No key"}).status_code == 422


def test_csrf_origin_auth(client):
    assert client.get("/api/v1/products").status_code == 401
    register(client)
    token = client.headers.pop("X-CSRF-Token")
    assert write(client, "/warehouses", {"name": "No CSRF"}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert (
        client.post(
            "/api/v1/warehouses",
            json={"name": "Origin"},
            headers={"Idempotency-Key": "x", "Origin": "https://evil.example"},
        ).status_code
        == 403
    )


def test_demo_exports(client):
    register(client)
    demo = write(client, "/demo", key="demo").json()
    assert write(client, "/demo", key="demo").json() == demo
    a = write(client, "/analyses", {"warehouse_id": demo["warehouse_id"]}).json()
    rows = a["results"]["products"]
    assert Decimal(rows[0]["suggested_order"]) == 50
    assert a["results"]["summary"]["reorder_count"] == 1
    assert client.get(f"/api/v1/analyses/{a['id']}/report").status_code == 200
    assert "suggested_order" in client.get(f"/api/v1/analyses/{a['id']}/report?format=csv").text


def base_snapshot(stock="18", incoming="0", sold="270"):
    return dict(
        lookback_days=90,
        slow_days=30,
        products=[
            dict(
                id="a",
                sku="A",
                name="A",
                stock=stock,
                incoming=incoming,
                sold=sold,
                revenue="12150",
                days_since_sale=0,
                lead_days=10,
                safety_days=5,
                review_days=7,
                pack_size=10,
                minimum_order=10,
                supplier_id="s",
                unit_cost="20",
            )
        ],
    )


def test_reference_engine():
    row = calculate(base_snapshot())["products"][0]
    assert Decimal(row["daily_demand"]) == 3
    assert Decimal(row["reorder_point"]) == 45
    assert Decimal(row["target_stock"]) == 66
    assert Decimal(row["suggested_order"]) == 50
    assert Decimal(row["coverage_days"]) == 6


@pytest.mark.parametrize(
    "stock,incoming,sold,expected",
    [("18", "50", "270", 0), ("100", "0", "270", 0), ("0", "0", "0", 0), ("45", "0", "270", 30), ("0", "0", "270", 70)],
)
def test_reorder_cases(stock, incoming, sold, expected):
    assert Decimal(calculate(base_snapshot(stock, incoming, sold))["products"][0]["suggested_order"]) == expected


@pytest.mark.parametrize(
    "text",
    [
        "wrong",
        "date,sku,quantity,revenue\n2026-01-01,A,-1,2",
        "date,sku,quantity,revenue\n2026-01-01,A,NaN,2",
        "date,sku,quantity,revenue\n2999-01-01,A,1,2",
    ],
)
def test_invalid_csv(text):
    assert not preview_demand(text)["valid"]


def test_multi_line_receipt_rolls_back_all_stock(client):
    s, w, p = setup(client)
    p2 = write(
        client,
        "/products",
        {"sku": "B", "name": "Item B", "supplier_id": s["id"], "unit_cost": "5", "selling_price": "10"},
    ).json()
    po = write(
        client,
        "/purchase-orders",
        {
            "supplier_id": s["id"],
            "warehouse_id": w["id"],
            "expected_date": str(date.today()),
            "lines": [
                {"product_id": p["id"], "quantity": "10", "unit_cost": "10"},
                {"product_id": p2["id"], "quantity": "5", "unit_cost": "5"},
            ],
        },
    ).json()
    body = {
        "lines": [
            {"line_id": po["lines"][0]["id"], "quantity": "2"},
            {"line_id": po["lines"][1]["id"], "quantity": "6"},
        ]
    }
    assert write(client, f"/purchase-orders/{po['id']}/receive", body).status_code == 409
    assert client.get("/api/v1/balances").json() == []
    assert all(Decimal(x["received"]) == 0 for x in client.get("/api/v1/purchase-orders").json()[0]["lines"])


def test_purchase_supplier_validation(client):
    s, w, p = setup(client)
    other = write(client, "/suppliers", {"name": "Other"}).json()
    response = write(
        client,
        "/purchase-orders",
        {
            "supplier_id": other["id"],
            "warehouse_id": w["id"],
            "expected_date": str(date.today()),
            "lines": [{"product_id": p["id"], "quantity": "1", "unit_cost": "1"}],
        },
    )
    assert response.status_code == 422


def test_product_edit_preserves_analysis(client):
    s, w, p = setup(client)
    write(client, "/analyses", {"warehouse_id": w["id"]}).json()
    fields = {k: v for k, v in p.items() if k != "id"}
    fields["lead_days"] = 99
    response = client.patch("/api/v1/products/" + p["id"], json=fields, headers={"Idempotency-Key": "edit"})
    assert response.status_code == 200
    assert client.get("/api/v1/analyses").json()[0]["inputs"]["products"][0]["lead_days"] == 10


def test_abc_zero_sales():
    row = calculate(base_snapshot(sold="0"))["products"][0]
    assert row["coverage_days"] is None
    # Revenue drives ABC, independently of stock quantities.
    assert row["abc"] == "A"
    snapshot = base_snapshot(sold="0")
    snapshot["products"][0]["revenue"] = "0"
    assert calculate(snapshot)["products"][0]["abc"] == "C"


def test_pack_and_minimum():
    snapshot = base_snapshot(stock="44")
    snapshot["products"][0]["minimum_order"] = 55
    assert Decimal(calculate(snapshot)["products"][0]["suggested_order"]) == 60
