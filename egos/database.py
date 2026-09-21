"""SQLite database setup and small persistence helpers."""

from __future__ import annotations

import logging
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base, User


logger = logging.getLogger(__name__)


def _engine_url(database_url: str) -> str:
    """Normalize a relative SQLite URL so it works from the project root."""
    if database_url.startswith("sqlite:///") and not database_url.startswith(
        "sqlite:////"
    ):
        return database_url
    return database_url


engine = create_engine(
    _engine_url(get_settings().database_url),
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables when the bot starts."""
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite database initialized")


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for FastAPI dependencies."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_or_create_user(
    session: Session, telegram_id: int, name: str | None
) -> User:
    """Find a Telegram user or create their first local profile."""
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(
            telegram_id=telegram_id,
            name=name or "Фермер",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    elif name and user.name != name:
        user.name = name
        session.commit()
    return user