"""Seven-day crop care plan generated from normalized weather data."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from .weather_api import ForecastDay, WeatherData


class CareDay(BaseModel):
    """One actionable day in the crop care plan."""

    date: date
    weather: str
    risk: str
    action: str
    reason: str


def _risk_for(day: ForecastDay) -> str:
    """Create a cautious risk label from forecast signals."""
    if day.precipitation_mm >= 10 or day.precipitation_probability >= 75:
        return "Дождь и переувлажнение"
    if day.max_temperature >= 30 and day.precipitation_mm < 2:
        return "Тепловой стресс и пересыхание"
    if day.min_temperature <= 3:
        return "Понижение температуры"
    if day.wind_kph >= 35:
        return "Сильный ветер"
    return "Существенных рисков не видно"


def _action_for(
    day: ForecastDay, crop: str, irrigation: str, fertilizer: str, index: int
) -> tuple[str, str]:
    """Choose a simple inspection-first action and its reason."""
    del crop
    if day.precipitation_mm >= 5 or day.precipitation_probability >= 65:
        return (
            "🌧 Оценить состояние поля после осадков",
            "Осадки могут изменить влажность почвы и доступность техники.",
        )
    if day.max_temperature >= 28 and day.precipitation_mm < 3:
        if irrigation.strip().lower() == "да":
            return (
                "💧 Проверить необходимость полива",
                "Тепло и малое количество осадков повышают потребность в наблюдении.",
            )
        return (
            "🔍 Проверить признаки водного стресса",
            "Орошение не указано, поэтому решение нужно принимать по состоянию растений.",
        )
    if index == 0:
        return (
            "🔍 Проверить состояние растений",
            "Начните план с осмотра поля и отметьте фактическую влажность почвы.",
        )
    if fertilizer.strip().lower() == "нет" and index == 1:
        return (
            "🧪 Проверить доступность питательных веществ",
            "Не указано применение удобрений; внесение следует решать после агрономической оценки.",
        )
    return (
        "🌱 Осмотреть культуру и междурядья",
        "Регулярный осмотр помогает вовремя заметить сорняки, вредителей и стресс.",
    )


def generate_care_plan(
    crop: str,
    sowing_date: date,
    weather_data: WeatherData,
    irrigation: str,
    fertilizer: str,
) -> list[CareDay]:
    """Create at least seven cautious, weather-aware care recommendations."""
    del sowing_date
    days = weather_data.forecast[:7]
    while len(days) < 7:
        previous = days[-1] if days else ForecastDay(
            date=date.today(),
            min_temperature=10,
            max_temperature=20,
            precipitation_mm=0,
            precipitation_probability=0,
            humidity=50,
            wind_kph=10,
            condition="Нет данных",
        )
        days.append(
            previous.model_copy(update={"date": previous.date + timedelta(days=1)})
        )
    plan: list[CareDay] = []
    for index, day in enumerate(days):
        action, reason = _action_for(day, crop, irrigation, fertilizer, index)
        plan.append(
            CareDay(
                date=day.date,
                weather=(
                    f"{day.condition}, {day.min_temperature:.0f}–{day.max_temperature:.0f} °C, "
                    f"осадки {day.precipitation_mm:.1f} мм"
                ),
                risk=_risk_for(day),
                action=action,
                reason=f"{reason} Вероятность осадков: {day.precipitation_probability}%.",
            )
        )
    return plan