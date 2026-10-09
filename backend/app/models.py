"""Relational ownership and immutable evaluation snapshots.

An account owns its inventory records. Every query must enforce that relationship rather
than treating an unpredictable UUID as authorization.
"""

import time
from uuid import uuid4
from sqlalchemy import String, Text, Float, ForeignKey, JSON, UniqueConstraint, Numeric, Date, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def new_id():
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[float] = mapped_column(Float)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), default="")


class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("user_id", "sku"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(20), default="unit")
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    unit_cost: Mapped[object] = mapped_column(Numeric(28, 4))
    selling_price: Mapped[object] = mapped_column(Numeric(28, 4))
    lead_days: Mapped[int] = mapped_column(Integer, default=7)
    safety_days: Mapped[int] = mapped_column(Integer, default=7)
    review_days: Mapped[int] = mapped_column(Integer, default=7)
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    minimum_order: Mapped[int] = mapped_column(Integer, default=1)


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id"),
        CheckConstraint("quantity >= 0", name="nonnegative_stock"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity: Mapped[object] = mapped_column(Numeric(28, 4), default=0)


class Movement(Base):
    __tablename__ = "movements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    quantity_delta: Mapped[object] = mapped_column(Numeric(28, 4))
    kind: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[float] = mapped_column(Float, default=time.time)


class DemandObservation(Base):
    __tablename__ = "demand_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    day: Mapped[object] = mapped_column(Date, index=True)
    quantity: Mapped[object] = mapped_column(Numeric(28, 4))
    revenue: Mapped[object] = mapped_column(Numeric(28, 4))
    source: Mapped[str] = mapped_column(String(40))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey("warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="ordered")
    ordered_date: Mapped[object] = mapped_column(Date)
    expected_date: Mapped[object] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="USD")


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    __table_args__ = (CheckConstraint("received >= 0 AND received <= quantity", name="valid_received_quantity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[object] = mapped_column(Numeric(28, 4))
    received: Mapped[object] = mapped_column(Numeric(28, 4), default=0)
    unit_cost: Mapped[object] = mapped_column(Numeric(28, 4))


class ReceiptEvent(Base):
    __tablename__ = "receipt_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    day: Mapped[object] = mapped_column(Date)
    quantity: Mapped[object] = mapped_column(Numeric(28, 4))


class RequestRecord(Base):
    __tablename__ = "request_records"
    __table_args__ = (UniqueConstraint("user_id", "scope", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    inputs: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
