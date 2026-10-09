"""Inventory HTTP contracts; durable mutations require a request replay key."""

import csv
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select, update
from .database import get_db
from .security import current_user
from .models import (
    Supplier,
    Warehouse,
    Product,
    Balance,
    Movement,
    DemandObservation,
    PurchaseOrder,
    PurchaseLine,
    ReceiptEvent,
    Analysis,
)
from .schemas import (
    SupplierInput,
    WarehouseInput,
    ProductInput,
    MovementInput,
    PurchaseInput,
    ReceiveInput,
    AnalysisInput,
    CsvInput,
    ApplyDemandInput,
)
from .services import owned, mutation, post_movement, order_view, snapshot
from .engine import calculate, ENGINE_VERSION
from .imports import preview_demand

router = APIRouter(prefix="/api/v1")
Key = Header(min_length=1, max_length=100)


def product_view(p):
    return {
        name: (str(getattr(p, name)) if name in ["unit_cost", "selling_price"] else getattr(p, name))
        for name in [
            "id",
            "sku",
            "name",
            "unit",
            "supplier_id",
            "unit_cost",
            "selling_price",
            "lead_days",
            "safety_days",
            "review_days",
            "pack_size",
            "minimum_order",
        ]
    }


@router.get("/suppliers")
def suppliers(user=Depends(current_user), db=Depends(get_db)):
    return [
        dict(id=x.id, name=x.name, email=x.email)
        for x in db.scalars(select(Supplier).where(Supplier.user_id == user.id))
    ]


@router.post("/suppliers", status_code=201)
def create_supplier(data: SupplierInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    def work():
        obj = Supplier(user_id=user.id, **data.model_dump())
        db.add(obj)
        db.flush()
        return dict(id=obj.id, name=obj.name, email=obj.email)

    return mutation(db, user, "supplier", idempotency_key, data.model_dump(mode="json"), work)


@router.get("/warehouses")
def warehouses(user=Depends(current_user), db=Depends(get_db)):
    return [dict(id=x.id, name=x.name) for x in db.scalars(select(Warehouse).where(Warehouse.user_id == user.id))]


@router.post("/warehouses", status_code=201)
def create_warehouse(data: WarehouseInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    def work():
        obj = Warehouse(user_id=user.id, **data.model_dump())
        db.add(obj)
        db.flush()
        return dict(id=obj.id, name=obj.name)

    return mutation(db, user, "warehouse", idempotency_key, data.model_dump(mode="json"), work)


@router.get("/products")
def products(user=Depends(current_user), db=Depends(get_db)):
    return [
        product_view(x) for x in db.scalars(select(Product).where(Product.user_id == user.id).order_by(Product.sku))
    ]


@router.post("/products", status_code=201)
def create_product(data: ProductInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    if data.supplier_id:
        owned(db, Supplier, data.supplier_id, user)

    def work():
        p = Product(user_id=user.id, **data.model_dump())
        db.add(p)
        db.flush()
        return product_view(p)

    return mutation(db, user, "product", idempotency_key, data.model_dump(mode="json"), work)


@router.patch("/products/{identifier}")
def edit_product(
    identifier: str, data: ProductInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)
):
    obj = owned(db, Product, identifier, user)
    if data.supplier_id:
        owned(db, Supplier, data.supplier_id, user)

    def work():
        for key, value in data.model_dump().items():
            setattr(obj, key, value)
        db.flush()
        return product_view(obj)

    return mutation(db, user, "edit:" + identifier, idempotency_key, data.model_dump(mode="json"), work)


@router.get("/balances")
def balances(user=Depends(current_user), db=Depends(get_db)):
    return [
        dict(product_id=x.product_id, warehouse_id=x.warehouse_id, quantity=str(x.quantity))
        for x in db.scalars(
            select(Balance).join(Product, Balance.product_id == Product.id).where(Product.user_id == user.id)
        )
    ]


@router.get("/movements")
def movements(user=Depends(current_user), db=Depends(get_db)):
    return [
        dict(
            id=x.id,
            product_id=x.product_id,
            warehouse_id=x.warehouse_id,
            quantity_delta=str(x.quantity_delta),
            kind=x.kind,
            note=x.note,
            posted_at=x.posted_at,
        )
        for x in db.scalars(
            select(Movement).where(Movement.user_id == user.id).order_by(Movement.posted_at.desc()).limit(500)
        )
    ]


@router.post("/movements", status_code=201)
def movement(data: MovementInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    p = owned(db, Product, data.product_id, user)
    owned(db, Warehouse, data.warehouse_id, user)
    if data.kind == "transfer":
        if not data.destination_id or data.destination_id == data.warehouse_id:
            raise HTTPException(422, "Choose a different destination warehouse.")
        owned(db, Warehouse, data.destination_id, user)
    elif data.destination_id:
        raise HTTPException(422, "Only transfers accept a destination.")

    def work():
        delta = data.quantity if data.kind in ["receipt", "adjustment_in"] else -data.quantity
        # Transfer deltas share one database transaction and replay key.
        m = post_movement(db, user, p.id, data.warehouse_id, delta, data.kind, data.note)
        if data.kind == "transfer":
            post_movement(db, user, p.id, data.destination_id, data.quantity, "transfer_in", data.note)
        if data.kind == "sale":
            db.add(
                DemandObservation(
                    user_id=user.id,
                    product_id=p.id,
                    warehouse_id=data.warehouse_id,
                    day=date.today(),
                    quantity=data.quantity,
                    revenue=data.quantity * p.selling_price,
                    source="stock_sale",
                )
            )
        db.flush()
        return dict(id=m.id, message="Stock movement saved. Transfers are atomic; sale issues also record demand.")

    return mutation(db, user, "movement", idempotency_key, data.model_dump(mode="json"), work)


@router.get("/purchase-orders")
def orders(user=Depends(current_user), db=Depends(get_db)):
    return [
        order_view(db, x)
        for x in db.scalars(
            select(PurchaseOrder).where(PurchaseOrder.user_id == user.id).order_by(PurchaseOrder.ordered_date.desc())
        )
    ]


@router.post("/purchase-orders", status_code=201)
def create_order(data: PurchaseInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Supplier, data.supplier_id, user)
    owned(db, Warehouse, data.warehouse_id, user)
    for line in data.lines:
        p = owned(db, Product, line.product_id, user)
        if p.supplier_id != data.supplier_id:
            raise HTTPException(422, "Every product must use the selected supplier.")

    def work():
        order = PurchaseOrder(
            user_id=user.id,
            supplier_id=data.supplier_id,
            warehouse_id=data.warehouse_id,
            ordered_date=date.today(),
            expected_date=data.expected_date,
            currency=data.currency,
        )
        db.add(order)
        db.flush()
        for line in data.lines:
            db.add(PurchaseLine(order_id=order.id, **line.model_dump()))
        db.flush()
        return order_view(db, order)

    return mutation(db, user, "purchase_order", idempotency_key, data.model_dump(mode="json"), work)


@router.post("/purchase-orders/{identifier}/receive")
def receive(
    identifier: str, data: ReceiveInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)
):
    def work():
        # Lock the order before reading remaining quantities on PostgreSQL.
        order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == identifier, PurchaseOrder.user_id == user.id)
            .with_for_update()
        )
        if order is None:
            raise HTTPException(404, "Purchase order not found.")
        if order.status not in ["ordered", "partial"]:
            raise HTTPException(409, "This purchase order is closed.")
        total = Decimal(0)
        for entry in data.lines:
            line = db.scalar(
                select(PurchaseLine).where(PurchaseLine.id == entry.line_id, PurchaseLine.order_id == order.id)
            )
            if line is None:
                raise HTTPException(404, "Order line not found.")
            changed = db.execute(
                update(PurchaseLine)
                .where(PurchaseLine.id == line.id, PurchaseLine.received + entry.quantity <= PurchaseLine.quantity)
                .values(received=PurchaseLine.received + entry.quantity)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Receipt exceeds the remaining ordered quantity.")
            post_movement(
                db,
                user,
                line.product_id,
                order.warehouse_id,
                entry.quantity,
                "purchase_receipt",
                "Purchase order " + order.id,
            )
            total += entry.quantity
        db.add(ReceiptEvent(order_id=order.id, day=date.today(), quantity=total))
        db.flush()
        db.expire_all()
        all_lines = list(db.scalars(select(PurchaseLine).where(PurchaseLine.order_id == identifier)))
        order.status = "received" if all(x.received == x.quantity for x in all_lines) else "partial"
        db.flush()
        return order_view(db, order)

    return mutation(db, user, "receive:" + identifier, idempotency_key, data.model_dump(mode="json"), work)


@router.post("/purchase-orders/{identifier}/cancel")
def cancel(identifier: str, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    def work():
        order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == identifier, PurchaseOrder.user_id == user.id)
            .with_for_update()
        )
        if order is None:
            raise HTTPException(404, "Purchase order not found.")
        if order.status not in ["ordered", "partial"]:
            raise HTTPException(409, "Only open orders can be cancelled.")
        order.status = "cancelled"
        db.flush()
        return order_view(db, order)

    return mutation(db, user, "cancel:" + identifier, idempotency_key, {}, work)


@router.get("/supplier-performance")
def supplier_performance(user=Depends(current_user), db=Depends(get_db)):
    orders = list(db.scalars(select(PurchaseOrder).where(PurchaseOrder.user_id == user.id)))
    events = list(
        db.scalars(
            select(ReceiptEvent)
            .join(PurchaseOrder, ReceiptEvent.order_id == PurchaseOrder.id)
            .where(PurchaseOrder.user_id == user.id)
        )
    )
    result = []
    for supplier in db.scalars(select(Supplier).where(Supplier.user_id == user.id)):
        own = {x.id: x for x in orders if x.supplier_id == supplier.id}
        receipts = [x for x in events if x.order_id in own]
        lead = sum((x.day - own[x.order_id].ordered_date).days for x in receipts) / len(receipts) if receipts else None
        result.append(
            dict(
                supplier_id=supplier.id,
                name=supplier.name,
                receipt_count=len(receipts),
                average_receipt_lead_days=lead,
                overdue_open_orders=sum(
                    x.status in ["ordered", "partial"] and x.expected_date < date.today() for x in own.values()
                ),
            )
        )
    return result


@router.post("/imports/demand/preview")
def preview(data: CsvInput, user=Depends(current_user)):
    return preview_demand(data.csv_text)


@router.post("/imports/demand/apply")
def apply_import(data: ApplyDemandInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    owned(db, Warehouse, data.warehouse_id, user)
    reviewed = preview_demand(data.csv_text)
    if not reviewed["valid"]:
        raise HTTPException(422, "Correct the CSV row errors before applying the file.")
    mapping = {p.sku: p for p in db.scalars(select(Product).where(Product.user_id == user.id))}
    if any(x["sku"] not in mapping for x in reviewed["rows"]):
        raise HTTPException(422, "Every CSV SKU must exist in your catalog.")

    def work():
        for row in reviewed["rows"]:
            db.add(
                DemandObservation(
                    user_id=user.id,
                    product_id=mapping[row["sku"]].id,
                    warehouse_id=data.warehouse_id,
                    day=date.fromisoformat(row["date"]),
                    quantity=Decimal(row["quantity"]),
                    revenue=Decimal(row["revenue"]),
                    source="csv_history",
                )
            )
        return dict(
            imported=len(reviewed["rows"]), message="Historical demand imported. Physical stock was not changed."
        )

    # Same bytes + warehouse replay the original receipt even with a new client key.
    import hashlib

    content_key = hashlib.sha256((data.warehouse_id + data.csv_text).encode()).hexdigest()
    return mutation(db, user, "demand_import", content_key, data.model_dump(mode="json"), work)


@router.post("/analyses", status_code=201)
def run_analysis(data: AnalysisInput, idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    def work():
        frozen = snapshot(db, user, data)
        obj = Analysis(user_id=user.id, inputs=frozen, results=calculate(frozen), engine_version=ENGINE_VERSION)
        db.add(obj)
        db.flush()
        return analysis_view(obj)

    return mutation(db, user, "analysis", idempotency_key, data.model_dump(mode="json"), work)


def analysis_view(obj):
    return dict(
        id=obj.id, inputs=obj.inputs, results=obj.results, engine_version=obj.engine_version, created_at=obj.created_at
    )


@router.get("/analyses")
def analyses(user=Depends(current_user), db=Depends(get_db)):
    return [
        analysis_view(x)
        for x in db.scalars(
            select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).limit(100)
        )
    ]


@router.get("/analyses/{identifier}/report")
def report(identifier: str, format: str = "json", user=Depends(current_user), db=Depends(get_db)):
    obj = owned(db, Analysis, identifier, user)
    if format == "json":
        text = json.dumps(analysis_view(obj), indent=2)
        media = "application/json"
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "sku",
                "stock",
                "incoming",
                "daily_demand",
                "coverage_days",
                "abc",
                "suggested_order",
                "estimated_order_cost",
            ]
        )
        for row in obj.results["products"]:
            writer.writerow(
                [
                    row[k]
                    for k in [
                        "sku",
                        "stock",
                        "incoming",
                        "daily_demand",
                        "coverage_days",
                        "abc",
                        "suggested_order",
                        "estimated_order_cost",
                    ]
                ]
            )
        text = output.getvalue()
        media = "text/csv"
    else:
        raise HTTPException(422, "Use json or csv report format.")
    return Response(
        text,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="inventory-analysis-{obj.id}.{format}"'},
    )


@router.post("/demo", status_code=201)
def demo(idempotency_key: str = Key, user=Depends(current_user), db=Depends(get_db)):
    def work():
        if db.scalar(select(Product).where(Product.user_id == user.id)):
            raise HTTPException(409, "Demo data can only be added to an empty catalog.")
        supplier = Supplier(user_id=user.id, name="North Supply", email="demo@example.com")
        warehouse = Warehouse(user_id=user.id, name="Main warehouse")
        db.add_all([supplier, warehouse])
        db.flush()
        for sku, name, cost, price, stock, daily in [
            ("SKU-A", "Wireless keyboard", 20, 45, 18, 3),
            ("SKU-B", "USB-C hub", 15, 35, 80, 1),
            ("SKU-C", "Legacy adapter", 5, 12, 40, 0),
        ]:
            p = Product(
                user_id=user.id,
                sku=sku,
                name=name,
                supplier_id=supplier.id,
                unit_cost=cost,
                selling_price=price,
                lead_days=10,
                safety_days=5,
                review_days=7,
                pack_size=10,
                minimum_order=10,
            )
            db.add(p)
            db.flush()
            post_movement(db, user, p.id, warehouse.id, Decimal(stock), "demo_opening", "Synthetic opening balance")
            if daily:
                for offset in range(90):
                    db.add(
                        DemandObservation(
                            user_id=user.id,
                            product_id=p.id,
                            warehouse_id=warehouse.id,
                            day=date.today() - timedelta(days=offset),
                            quantity=daily,
                            revenue=daily * price,
                            source="synthetic_demo",
                        )
                    )
        return dict(
            warehouse_id=warehouse.id,
            message="Synthetic catalog, stock and demand created. No external supplier was contacted.",
        )

    return mutation(db, user, "demo", idempotency_key, {}, work)
