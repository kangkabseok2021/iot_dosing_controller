from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    desc,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    region: Mapped[str | None] = mapped_column(String(64))
    meter_type: Mapped[str] = mapped_column(String(16), default="residential")
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    readings: Mapped[list["LoadReading"]] = relationship(
        "LoadReading", cascade="all, delete-orphan", lazy="selectin"
    )
    forecast: Mapped["NodeForecast | None"] = relationship(
        "NodeForecast", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class LoadReading(Base):
    __tablename__ = "load_readings"
    __table_args__ = (
        CheckConstraint("kwh > 0", name="ck_readings_kwh_positive"),
        Index("idx_readings_node_ts", "node_id", desc("ts")),
        Index("idx_readings_ts", desc("ts")),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("nodes.node_id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kwh: Mapped[float] = mapped_column(Float, nullable=False)
    meter_type: Mapped[str] = mapped_column(String(16), nullable=False, default="residential")
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NodeForecast(Base):
    __tablename__ = "node_forecasts"

    node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("nodes.node_id", ondelete="CASCADE"), primary_key=True
    )
    forecast_kwh: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_size: Mapped[int] = mapped_column(Integer, default=12)
