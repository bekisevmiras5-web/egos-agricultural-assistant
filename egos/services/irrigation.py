"""Recommendation-only irrigation planning."""

from __future__ import annotations

from pydantic import BaseModel

from .weather_api import WeatherData


class IrrigationAdvice(BaseModel):
    """A readable recommendation and its reasoning."""

    title: str
    recommendation: str
    reason: str


def calculate_irrigation_plan(
    weather_data: WeatherData, crop: str, irrigation: str
) -> IrrigationAdvice:
    """Recommend whether to inspect irrigation needs; never claim certainty."""
    del crop  # Crop-specific thresholds can be calibrated later.
    next_days = weather_data.forecast[:2]
    expected_rain = sum(day.precipitation_mm for day in next_days)
    max_probability = max(
        (day.precipitation_probability for day in next_days),
        default=weather_data.precipitation_probability,
    )
    max_temperature = max(
        (day.max_temperature for day in next_days),
        default=weather_data.max_temperature,
    )
    has_irrigation = irrigation.strip().lower() == "да"
    if expected_rain >= 5 or max_probability >= 60:
        return IrrigationAdvice(
            title="Осадки ожидаются",
            recommendation=(
                "Полив может не потребоваться. Оцените состояние поля после осадков "
                "и решение принимайте по фактической влажности почвы."
            ),
            reason=f"В ближайшие дни ожидается до {expected_rain:.1f} мм осадков, "
            f"вероятность дождя до {max_probability}%.",
        )
    if max_temperature >= 28 and expected_rain < 3:
        if has_irrigation:
            return IrrigationAdvice(
                title="Жарко и мало осадков",
                recommendation=(
                    "Проверьте влажность почвы и необходимость полива по нормам "
                    "вашего хозяйства. Не поливайте автоматически."
                ),
                reason=f"Максимальная температура до {max_temperature:.1f} °C, "
                "значимых осадков не ожидается.",
            )
        return IrrigationAdvice(
            title="Жарко и мало осадков",
            recommendation=(
                "Искусственное орошение недоступно по указанным данным. "
                "Наблюдайте за признаками стресса растений и влажностью почвы."
            ),
            reason=f"Максимальная температура до {max_temperature:.1f} °C, "
            "осадков мало.",
        )
    return IrrigationAdvice(
        title="Наблюдение за влажностью",
        recommendation=(
            "Проверьте состояние растений и влажность почвы перед любым решением "
            "о поливе."
        ),
        reason="Прогноз не указывает на выраженную жару или значимые осадки.",
    )