import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AssetType(enum.StrEnum):
    WIND = "wind"
    SOLAR = "solar"


class ScheduleStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    type: Mapped[AssetType] = mapped_column(Enum(AssetType))
    capacity_mw: Mapped[float] = mapped_column(Float)
    ramp_rate_mw_per_min: Mapped[float] = mapped_column(Float, default=999.0)


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (UniqueConstraint("asset_id", "measured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    power_mw: Mapped[float] = mapped_column(Float)


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_h: Mapped[int] = mapped_column(Integer)
    mape: Mapped[float] = mapped_column(Float)
    model_params_json: Mapped[str] = mapped_column(String, default="{}")

    intervals: Mapped[list["ForecastInterval"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ForecastInterval(Base):
    __tablename__ = "forecast_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id"), nullable=False)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mean_mw: Mapped[float] = mapped_column(Float)
    std_mw: Mapped[float] = mapped_column(Float)

    run: Mapped["ForecastRun"] = relationship(back_populates="intervals")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    portfolio_id: Mapped[int] = mapped_column(Integer)
    date: Mapped[str] = mapped_column(String)  # ISO date string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    intervals: Mapped[list["ScheduleIntervalDB"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


class ScheduleIntervalDB(Base):
    __tablename__ = "schedule_intervals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("schedules.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_mw: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String, default=ScheduleStatus.DRAFT.value
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="intervals")
