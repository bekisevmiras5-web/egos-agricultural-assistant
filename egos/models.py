"""SQLAlchemy models for users, fields, and yield forecasts."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all EGOS database models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="Фермер")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    fields: Mapped[list[Field]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    crop: Mapped[str] = mapped_column(String(255))
    area: Mapped[float] = mapped_column(Float)
    sowing_date: Mapped[date] = mapped_column(Date)
    irrigation: Mapped[str] = mapped_column(String(32))
    fertilizer: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="fields")
    forecasts: Mapped[list[YieldForecast]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class YieldForecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    yield_min: Mapped[float] = mapped_column(Float)
    yield_max: Mapped[float] = mapped_column(Float)
    total_min: Mapped[float] = mapped_column(Float)
    total_max: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    field: Mapped[Field] = relationship(back_populates="forecasts")