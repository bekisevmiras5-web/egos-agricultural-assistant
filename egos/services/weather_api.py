"""WeatherAPI.com client and deterministic demo weather data."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..config import get_settings


logger = logging.getLogger(__name__)
WEATHER_API_URL = "https://api.weatherapi.com/v1/forecast.json"


class WeatherAPIError(RuntimeError):
    """Raised for an expected, user-displayable weather API failure."""


class ForecastDay(BaseModel):
    """One normalized day from the weather provider."""

    date: date
    min_temperature: float
    max_temperature: float
    precipitation_mm: float = 0.0
    precipitation_probability: int = Field(default=0, ge=0, le=100)
    humidity: int = Field(default=0, ge=0, le=100)
    wind_kph: float = 0.0
    condition: str = "Нет данных"


class WeatherData(BaseModel):
    """Provider-independent weather data used by all analysis services."""

    latitude: float
    longitude: float
    location_name: str
    current_temperature: float
    min_temperature: float
    max_temperature: float
    precipitation_mm: float
    precipitation_probability: int = Field(default=0, ge=0, le=100)
    humidity: int = Field(default=0, ge=0, le=100)
    wind_kph: float = 0.0
    forecast: list[ForecastDay]

    @property
    def average_temperature(self) -> float:
        """Return the average temperature for the first forecast day."""
        return (self.min_temperature + self.max_temperature) / 2


def _number(value: Any, default: float = 0.0) -> float:
    """Convert an API value to a finite-ish float without leaking KeyErrors."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    """Convert an API value to a bounded integer."""
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def _weather_error(response: httpx.Response) -> WeatherAPIError:
    """Translate provider errors into concise Russian messages."""
    try:
        message = response.json().get("error", {}).get("message")
    except ValueError:
        message = None
    if response.status_code in (401, 403):
        return WeatherAPIError(
            "Weather API отклонил ключ. Проверьте WEATHER_API_KEY в файле .env."
        )
    return WeatherAPIError(
        f"Погодный сервис временно недоступен ({message or response.status_code}). "
        "Попробуйте ещё раз позже."
    )


async def get_weather(latitude: float, longitude: float) -> WeatherData:
    """Fetch a 7-day forecast for the exact field coordinates."""
    settings = get_settings()
    try:
        settings.require_weather_api_key()
    except ValueError as exc:
        raise WeatherAPIError(str(exc)) from exc
    query = f"{latitude:.6f},{longitude:.6f}"
    params = {
        "key": settings.weather_api_key,
        "q": query,
        "days": 7,
        "aqi": "no",
        "alerts": "no",
    }
    logger.info("Requesting weather for field coordinates %s", query)
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(WEATHER_API_URL, params=params)
    except httpx.TimeoutException as exc:
        raise WeatherAPIError(
            "Погодный сервис не ответил вовремя. Попробуйте ещё раз."
        ) from exc
    except httpx.HTTPError as exc:
        raise WeatherAPIError(
            "Не удалось подключиться к погодному сервису. Попробуйте позже."
        ) from exc

    if response.is_error:
        raise _weather_error(response)
    try:
        payload = response.json()
        if payload.get("error"):
            error_message = payload["error"].get("message", "неизвестная ошибка")
            raise WeatherAPIError(
                f"Weather API отклонил запрос: {error_message}. "
                "Проверьте WEATHER_API_KEY в файле .env."
            )
        location = payload["location"]
        current = payload["current"]
        forecast_days = payload["forecast"]["forecastday"]
    except (ValueError, KeyError, TypeError) as exc:
        raise WeatherAPIError(
            "Погодный сервис вернул неожиданный ответ. Попробуйте позже."
        ) from exc
    if not forecast_days:
        raise WeatherAPIError("Для этой точки пока нет прогноза погоды.")

    normalized: list[ForecastDay] = []
    for item in forecast_days:
        day = item.get("day", {})
        day_date = item.get("date")
        try:
            parsed_date = date.fromisoformat(day_date)
        except (TypeError, ValueError) as exc:
            raise WeatherAPIError("Погодный прогноз содержит некорректную дату.") from exc
        normalized.append(
            ForecastDay(
                date=parsed_date,
                min_temperature=_number(day.get("mintemp_c")),
                max_temperature=_number(day.get("maxtemp_c")),
                precipitation_mm=_number(day.get("totalprecip_mm")),
                precipitation_probability=_int(day.get("daily_chance_of_rain")),
                humidity=_int(day.get("avghumidity")),
                wind_kph=_number(day.get("maxwind_kph")),
                condition=str(day.get("condition", {}).get("text", "Нет данных")),
            )
        )
    today = normalized[0]
    parts = [str(location.get("name", "указанной точки"))]
    if location.get("region"):
        parts.append(str(location["region"]))
    if location.get("country"):
        parts.append(str(location["country"]))
    return WeatherData(
        latitude=latitude,
        longitude=longitude,
        location_name=", ".join(parts),
        current_temperature=_number(current.get("temp_c")),
        min_temperature=today.min_temperature,
        max_temperature=today.max_temperature,
        precipitation_mm=today.precipitation_mm,
        precipitation_probability=today.precipitation_probability,
        humidity=_int(current.get("humidity")),
        wind_kph=today.wind_kph,
        forecast=normalized,
    )


def get_demo_weather(latitude: float, longitude: float) -> WeatherData:
    """Return prepared data for presentations when DEMO_MODE=true."""
    today = date.today()
    conditions = (
        ("Переменная облачность", 0.0, 24),
        ("Небольшой дождь", 5.2, 72),
        ("Облачно", 1.1, 48),
        ("Солнечно", 0.0, 12),
        ("Солнечно", 0.0, 8),
        ("Кратковременный дождь", 3.5, 58),
        ("Переменная облачность", 0.4, 35),
    )
    forecast = [
        ForecastDay(
            date=today + timedelta(days=index),
            min_temperature=10 + (index % 2),
            max_temperature=23 + (index % 3),
            precipitation_mm=rain,
            precipitation_probability=chance,
            humidity=52 + index * 2,
            wind_kph=10 + index,
            condition=condition,
        )
        for index, (condition, rain, chance) in enumerate(conditions)
    ]
    return WeatherData(
        latitude=latitude,
        longitude=longitude,
        location_name="Алматы, Казахстан (демо)",
        current_temperature=forecast[0].max_temperature - 4,
        min_temperature=forecast[0].min_temperature,
        max_temperature=forecast[0].max_temperature,
        precipitation_mm=forecast[0].precipitation_mm,
        precipitation_probability=forecast[0].precipitation_probability,
        humidity=forecast[0].humidity,
        wind_kph=forecast[0].wind_kph,
        forecast=forecast,
    )