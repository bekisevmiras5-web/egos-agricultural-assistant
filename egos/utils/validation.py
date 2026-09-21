"""Input validation used by Telegram survey handlers."""

from __future__ import annotations

import re
from datetime import date, datetime


class ValidationError(ValueError):
    """A user-facing validation error."""


def parse_coordinates(value: str) -> tuple[float, float]:
    """Parse `latitude, longitude` or whitespace-separated coordinates."""
    cleaned = value.strip().replace(";", ",")
    parts = [part for part in re.split(r"[\s,]+", cleaned) if part]
    if len(parts) != 2:
        raise ValidationError(
            "Введите две координаты в формате: 43.2389, 76.8897"
        )
    try:
        latitude, longitude = (float(part.replace(",", ".")) for part in parts)
    except ValueError as exc:
        raise ValidationError("Координаты должны быть числами.") from exc
    if not -90 <= latitude <= 90:
        raise ValidationError("Широта должна быть от -90 до 90.")
    if not -180 <= longitude <= 180:
        raise ValidationError("Долгота должна быть от -180 до 180.")
    return round(latitude, 6), round(longitude, 6)


def parse_area(value: str) -> float:
    """Parse a positive field area in hectares."""
    try:
        area = float(value.strip().replace(",", "."))
    except ValueError as exc:
        raise ValidationError("Площадь должна быть числом, например 25.5.") from exc
    if area <= 0:
        raise ValidationError("Площадь должна быть больше нуля.")
    if area > 1_000_000:
        raise ValidationError("Проверьте площадь: значение выглядит слишком большим.")
    return round(area, 2)


def parse_sowing_date(value: str) -> date:
    """Parse an ISO or common Russian date format."""
    normalized = value.strip()
    formats = ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d")
    for date_format in formats:
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue
    raise ValidationError(
        "Дата не распознана. Используйте формат ДД.ММ.ГГГГ, например 15.04.2026."
    )


def format_date(value: date) -> str:
    """Format a date for a Russian Telegram message."""
    return value.strftime("%d.%m.%Y")


def normalize_choice(value: str) -> str:
    """Normalize button text without changing its meaning."""
    return " ".join(value.strip().lower().split())