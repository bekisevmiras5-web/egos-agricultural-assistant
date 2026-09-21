"""Transparent demonstration yield estimation model."""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .weather_api import WeatherData


@dataclass(frozen=True)
class CropProfile:
    """Editable baseline values and bounded MVP correction coefficients."""

    base_tons_per_hectare: float
    weather_weight: float = 0.08
    irrigation_bonus: float = 0.10
    fertilizer_bonus: float = 0.08


# Change these values when calibrated agronomic or local historical data becomes
# available. They are deliberately kept visible and easy to audit.
CROP_PROFILES: dict[str, CropProfile] = {
    "пшеница": CropProfile(3.4),
    "кукуруза": CropProfile(6.5),
    "подсолнечник": CropProfile(2.2),
    "картофель": CropProfile(18.0),
    "другая": CropProfile(3.0),
}


class YieldEstimate(BaseModel):
    """Yield range in tonnes per hectare and tonnes for the whole field."""

    yield_min: float = Field(ge=0)
    yield_max: float = Field(ge=0)
    total_min: float = Field(ge=0)
    total_max: float = Field(ge=0)


def _profile_for(crop: str) -> CropProfile:
    """Find a profile by tolerant case-insensitive matching."""
    normalized = crop.strip().lower()
    for name, profile in CROP_PROFILES.items():
        if name in normalized or normalized in name:
            return profile
    return CROP_PROFILES["другая"]


def _weather_factor(weather_data: WeatherData) -> float:
    """Apply a small, explicit correction based on the first 7 forecast days."""
    rain = sum(day.precipitation_mm for day in weather_data.forecast)
    average_temp = sum(
        (day.min_temperature + day.max_temperature) / 2
        for day in weather_data.forecast
    ) / max(len(weather_data.forecast), 1)
    factor = 0.0
    if rain < 5 and average_temp >= 25:
        factor -= 0.08
    elif 5 <= rain <= 45 and 12 <= average_temp <= 30:
        factor += 0.04
    elif rain > 80:
        factor -= 0.05
    if weather_data.precipitation_probability >= 80 and weather_data.max_temperature > 32:
        factor -= 0.03
    return factor


def calculate_yield(
    crop: str,
    area: float,
    sowing_date: date,
    irrigation: str,
    fertilizer: str,
    weather_data: WeatherData,
) -> YieldEstimate:
    """Calculate a transparent MVP estimate, never a validated agronomic forecast."""
    del sowing_date  # Kept in the contract for future phenology calibration.
    profile = _profile_for(crop)
    correction = _weather_factor(weather_data) * profile.weather_weight
    irrigation_normalized = irrigation.strip().lower()
    fertilizer_normalized = fertilizer.strip().lower()
    if irrigation_normalized in {"да", "yes"}:
        correction += profile.irrigation_bonus
    elif irrigation_normalized in {"нет", "no"}:
        correction -= 0.03
    if fertilizer_normalized in {"да", "yes"}:
        correction += profile.fertilizer_bonus
    elif fertilizer_normalized in {"нет", "no"}:
        correction -= 0.02
    center = max(0.05, profile.base_tons_per_hectare * (1 + correction))
    spread = max(0.05, center * (0.10 + abs(_weather_factor(weather_data)) * 0.5))
    estimate = YieldEstimate(
        yield_min=round(max(0.05, center - spread), 2),
        yield_max=round(center + spread, 2),
        total_min=round(max(0.05, center - spread) * area, 2),
        total_max=round((center + spread) * area, 2),
    )
    return estimate