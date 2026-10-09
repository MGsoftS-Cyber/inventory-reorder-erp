"""Transaction rules: authorization, duplicate prevention, stock and purchasing."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .models import Product, Warehouse, Balance, Movement, DemandObservation, PurchaseOrder, PurchaseLine, RequestRecord


def owned(db, model, identifier, user):
    item = db.scalar(select(model).where(model.id == identifier, model.user_id == user.id))
    if item is None:
        raise HTTPException(404, "Record not found in your account.")
    return item


def mutation(db, user, scope, key, payload, work):
    """Commit the business changes and replay receipt in one transaction.

    A database unique constraint also protects concurrent repeated requests.
    Any failed work is rolled back when the request-scoped session closes.
    """
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(RequestRecord).where(
            RequestRecord.user_id == user.id, RequestRecord.scope == scope, RequestRecord.key == key
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise HTTPException(409, "This request key was used with different data.")
        return existing.response
    try:
        result = work()
        db.add(RequestRecord(user_id=user.id, scope=scope, key=key, payload_hash=fingerprint, response=result))
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        winner = db.scalar(
            select(RequestRecord).where(
                RequestRecord.user_id == user.id, RequestRecord.scope == scope, RequestRecord.key == key
            )
        )
        if winner and winner.payload_hash == fingerprint:
            return winner.response
        raise HTTPException(
            409, "A conflicting write occurred. Refresh the data and retry with a new request key."
        ) from None


def balance_change(db, product_id, warehouse_id, delta):
    """Atomic conditional SQL prevents two simultaneous issues overselling stock."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    db.execute(
        insert(Balance)
        .values(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        .on_conflict_do_nothing(index_elements=["product_id", "warehouse_id"])
    )
    statement = (
        update(Balance)
        .where(Balance.product_id == product_id, Balance.warehouse_id == warehouse_id, Balance.quantity + delta >= 0)
        .values(quantity=Balance.quantity + delta)
    )
    if db.execute(statement).rowcount != 1:
        raise HTTPException(409, "Insufficient stock. The transaction was not applied.")


def post_movement(db, user, product_id, warehouse_id, delta, kind, note):
    balance_change(db, product_id, warehouse_id, delta)
    movement = Movement(
        user_id=user.id, product_id=product_id, warehouse_id=warehouse_id, quantity_delta=delta, kind=kind, note=note
    )
    db.add(movement)
    return movement


def order_view(db, order):
    lines = list(db.scalars(select(PurchaseLine).where(PurchaseLine.order_id == order.id)))
    return dict(
        id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=order.warehouse_id,
        status=order.status,
        currency=order.currency,
        ordered_date=str(order.ordered_date),
        expected_date=str(order.expected_date),
        lines=[
            dict(
                id=x.id,
                product_id=x.product_id,
                quantity=str(x.quantity),
                received=str(x.received),
                unit_cost=str(x.unit_cost),
            )
            for x in lines
        ],
    )


def snapshot(db, user, settings):
    owned(db, Warehouse, settings.warehouse_id, user)
    today = date.today()
    start = today - timedelta(days=settings.lookback_days - 1)
    products = list(db.scalars(select(Product).where(Product.user_id == user.id).order_by(Product.sku)))
    balances = {
        x.product_id: x.quantity
        for x in db.scalars(select(Balance).where(Balance.warehouse_id == settings.warehouse_id))
    }
    observations = list(
        db.scalars(
            select(DemandObservation).where(
                DemandObservation.user_id == user.id, DemandObservation.warehouse_id == settings.warehouse_id
            )
        )
    )
    open_lines = list(
        db.execute(
            select(PurchaseLine)
            .join(PurchaseOrder, PurchaseLine.order_id == PurchaseOrder.id)
            .where(
                PurchaseOrder.user_id == user.id,
                PurchaseOrder.warehouse_id == settings.warehouse_id,
                PurchaseOrder.status.in_(["ordered", "partial"]),
            )
        ).scalars()
    )
    result = []
    for p in products:
        history = [x for x in observations if x.product_id == p.id]
        recent = [x for x in history if start <= x.day <= today]
        last = max((x.day for x in history), default=None)
        result.append(
            dict(
                id=p.id,
                sku=p.sku,
                name=p.name,
                supplier_id=p.supplier_id,
                unit_cost=str(p.unit_cost),
                stock=str(balances.get(p.id, 0)),
                incoming=str(sum((x.quantity - x.received for x in open_lines if x.product_id == p.id), Decimal(0))),
                sold=str(sum((x.quantity for x in recent), Decimal(0))),
                revenue=str(sum((x.revenue for x in recent), Decimal(0))),
                days_since_sale=(today - last).days if last else None,
                lead_days=p.lead_days,
                safety_days=p.safety_days,
                review_days=p.review_days,
                pack_size=p.pack_size,
                minimum_order=p.minimum_order,
            )
        )
    return dict(
        **settings.model_dump(),
        as_of=str(today),
        start_date=str(start),
        products=result,
        demand_rows=[
            dict(
                id=x.id,
                product_id=x.product_id,
                day=str(x.day),
                quantity=str(x.quantity),
                revenue=str(x.revenue),
                source=x.source,
            )
            for x in observations
        ],
    )
