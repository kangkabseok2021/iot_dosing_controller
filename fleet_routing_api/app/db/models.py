from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    plate = Column(String(32), unique=True, nullable=False)
    capacity_kg = Column(Float, nullable=False)

    drivers = relationship("Driver", back_populates="vehicle")
    deliveries = relationship("Delivery", back_populates="vehicle")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    license_number = Column(String(64), unique=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))

    vehicle = relationship("Vehicle", back_populates="drivers")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)
    description = Column(String(256))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vehicle = relationship("Vehicle", back_populates="deliveries")
    waypoints = relationship("Waypoint", back_populates="delivery")


class Waypoint(Base):
    __tablename__ = "waypoints"

    id = Column(Integer, primary_key=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    address = Column(String(256))
    sequence_order = Column(Integer)

    delivery = relationship("Delivery", back_populates="waypoints")
