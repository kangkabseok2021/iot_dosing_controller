from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Index, String, desc, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SensorEvent(Base):
    __tablename__ = "sensor_events"
    __table_args__ = (
        Index("idx_events_plant_ts", "plant_id", desc("timestamp")),
        Index("idx_events_sensor_ts", "sensor_id", desc("timestamp")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    raw_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
