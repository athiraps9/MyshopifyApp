"""CRM tables. Shopify stays the source of truth for products, inventory and orders."""
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CRMCustomer(Base):
    __tablename__ = "crm_customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopify_customer_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))  # name only, no email/phone
    internal_notes: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    interactions: Mapped[list["CRMInteraction"]] = relationship(back_populates="customer")
    follow_ups: Mapped[list["CRMFollowUp"]] = relationship(back_populates="customer")


class CRMInteraction(Base):
    __tablename__ = "crm_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    crm_customer_id: Mapped[int] = mapped_column(ForeignKey("crm_customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    customer: Mapped[CRMCustomer] = relationship(back_populates="interactions")


class CRMFollowUp(Base):
    __tablename__ = "crm_follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    crm_customer_id: Mapped[int] = mapped_column(ForeignKey("crm_customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | done | cancelled
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    customer: Mapped[CRMCustomer] = relationship(back_populates="follow_ups")


class ShopifyWebhookEvent(Base):
    """Only metadata is stored, never the webhook body (it holds customer data)."""

    __tablename__ = "shopify_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    topic: Mapped[str] = mapped_column(String(100))
    shop_domain: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="received")  # received | processed | failed
    error: Mapped[str | None] = mapped_column(String(200))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ShopifyProductSnapshot(Base):
    __tablename__ = "shopify_products"

    shopify_product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    handle: Mapped[str | None] = mapped_column(String(255))
    vendor: Mapped[str | None] = mapped_column(String(255))
    product_type: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    updated_at: Mapped[str | None] = mapped_column(String(40))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    variants: Mapped[list["ShopifyProductVariantSnapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ShopifyProductVariantSnapshot(Base):
    __tablename__ = "shopify_product_variants"

    shopify_variant_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shopify_product_id: Mapped[int] = mapped_column(
        ForeignKey("shopify_products.shopify_product_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    inventory_quantity: Mapped[int | None] = mapped_column(Integer)

    product: Mapped[ShopifyProductSnapshot] = relationship(back_populates="variants")


class ShopifyCustomerSnapshot(Base):
    __tablename__ = "shopify_customers"

    shopify_customer_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    orders_count: Mapped[int | None] = mapped_column(Integer)
    total_spent: Mapped[float | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[str | None] = mapped_column(String(40))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ShopifyOrderSnapshot(Base):
    __tablename__ = "shopify_orders"

    shopify_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    customer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_at: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[str | None] = mapped_column(String(40))
    financial_status: Mapped[str | None] = mapped_column(String(50))
    fulfillment_status: Mapped[str | None] = mapped_column(String(50))
    total_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    line_items: Mapped[list["ShopifyOrderLineItemSnapshot"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ShopifyOrderLineItemSnapshot(Base):
    __tablename__ = "shopify_order_line_items"

    shopify_line_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shopify_order_id: Mapped[int] = mapped_column(
        ForeignKey("shopify_orders.shopify_order_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))

    order: Mapped[ShopifyOrderSnapshot] = relationship(back_populates="line_items")
