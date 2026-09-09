import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    station_code: Mapped[str] = mapped_column(
        String(16),
        index=True,
    )

    forecast_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    model_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    source_latitude: Mapped[float] = mapped_column(Float)
    source_longitude: Mapped[float] = mapped_column(Float)

    member_highs_f: Mapped[list[float]] = mapped_column(JSONB)

    mean_high_f: Mapped[float] = mapped_column(Float)
    minimum_high_f: Mapped[float] = mapped_column(Float)
    maximum_high_f: Mapped[float] = mapped_column(Float)
    standard_deviation_f: Mapped[float] = mapped_column(Float)

    fingerprint: Mapped[str] = mapped_column(
        String(64),
    )

    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "station_code",
            "forecast_date",
            "fingerprint",
            name="uq_forecast_station_date_fingerprint",
        ),
        CheckConstraint(
            "jsonb_array_length(member_highs_f) = 64",
            name="ck_forecast_has_64_members",
        ),
    )

class TemperatureSettlement(Base):
    __tablename__ = "temperature_settlements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    series_ticker: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    event_ticker: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    station_code: Mapped[str] = mapped_column(
        String(16),
        index=True,
    )

    observation_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    temperature_f: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
    )

    source_name: Mapped[str] = mapped_column(
        String(128),
    )

    source_url: Mapped[str] = mapped_column(
        String(512),
    )

    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class MarketQuoteSnapshot(Base):
    __tablename__ = "market_quote_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    event_ticker: Mapped[str] = mapped_column(
        String(128),
        index=True,
    )

    market_ticker: Mapped[str] = mapped_column(
        String(128),
        index=True,
    )

    target_date: Mapped[date] = mapped_column(
        Date,
        index=True,
    )

    lower_f: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    upper_f: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    yes_bid_cents: Mapped[int] = mapped_column(Integer)
    yes_ask_cents: Mapped[int] = mapped_column(Integer)
    no_bid_cents: Mapped[int] = mapped_column(Integer)
    no_ask_cents: Mapped[int] = mapped_column(Integer)

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "market_ticker",
            "retrieved_at",
            name="uq_market_quote_ticker_retrieved",
        ),
        CheckConstraint(
            "lower_f IS NOT NULL OR upper_f IS NOT NULL",
            name="ck_market_quote_has_bound",
        ),
        CheckConstraint(
            "yes_bid_cents BETWEEN 0 AND 100",
            name="ck_market_quote_yes_bid",
        ),
        CheckConstraint(
            "yes_ask_cents BETWEEN 0 AND 100",
            name="ck_market_quote_yes_ask",
        ),
        CheckConstraint(
            "no_bid_cents BETWEEN 0 AND 100",
            name="ck_market_quote_no_bid",
        ),
        CheckConstraint(
            "no_ask_cents BETWEEN 0 AND 100",
            name="ck_market_quote_no_ask",
        ),
    )

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    market_ticker: Mapped[str] = mapped_column(String(128), index=True)
    side: Mapped[str] = mapped_column(String(8))
    price_cents: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    filled_count: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Fill(Base):
    __tablename__ = "fills"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_fill_id: Mapped[str] = mapped_column(String(128), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    count: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Position(Base):
    __tablename__ = "positions"
    market_ticker: Mapped[str] = mapped_column(String(128), primary_key=True)
    net_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    realized_pnl_cents: Mapped[int] = mapped_column(Integer, default=0)


class Settlement(Base):
    __tablename__ = "settlements"
    market_ticker: Mapped[str] = mapped_column(String(128), primary_key=True)
    result: Mapped[str] = mapped_column(String(8))
    payout_cents: Mapped[int] = mapped_column(Integer)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LatencySample(Base):
    __tablename__ = "latency_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    market_ticker: Mapped[str | None] = mapped_column(String(128), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    elapsed_ms: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

