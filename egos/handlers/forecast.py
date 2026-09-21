"""Forecast orchestration and result rendering."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal, get_or_create_user
from ..keyboards.keyboards import main_menu_keyboard, result_keyboard
from ..models import Field, YieldForecast
from ..services.care_plan import CareDay, generate_care_plan
from ..services.irrigation import IrrigationAdvice, calculate_irrigation_plan
from ..services.weather_api import (
    WeatherAPIError,
    WeatherData,
    get_demo_weather,
    get_weather,
)
from ..services.yield_model import YieldEstimate, calculate_yield
from ..utils.validation import format_date


logger = logging.getLogger(__name__)
router = Router(name="forecast")

DISCLAIMER = (
    "⚠️ Демонстрационная оценка MVP. Не заменяет агрономическое обследование "
    "или валидированную модель."
)


async def _load_weather(latitude: float, longitude: float) -> WeatherData:
    """Choose demo or live weather without hiding live API failures."""
    settings = get_settings()
    if settings.demo_mode:
        return get_demo_weather(latitude, longitude)
    return await get_weather(latitude, longitude)


def _save_forecast(
    message: Message, data: dict[str, Any], estimate: YieldEstimate
) -> None:
    """Persist the field and the resulting estimate in one transaction."""
    if not message.from_user:
        raise ValueError("Telegram user is missing.")
    with SessionLocal() as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
        )
        field = Field(
            user_id=user.id,
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            crop=str(data["crop"]),
            area=float(data["area"]),
            sowing_date=date.fromisoformat(str(data["sowing_date"])),
            irrigation=str(data["irrigation"]),
            fertilizer=str(data["fertilizer"]),
            notes=str(data.get("notes", "")) or None,
        )
        session.add(field)
        session.flush()
        session.add(
            YieldForecast(
                field_id=field.id,
                yield_min=estimate.yield_min,
                yield_max=estimate.yield_max,
                total_min=estimate.total_min,
                total_max=estimate.total_max,
            )
        )
        session.commit()


def _risk_line(weather: WeatherData) -> str:
    """Return a short first-look risk line for the summary."""
    first_day = weather.forecast[0]
    if first_day.precipitation_mm >= 5 or first_day.precipitation_probability >= 65:
        return "🌧 Ожидаются осадки — проверьте влажность и проходимость поля."
    if first_day.max_temperature >= 30 and first_day.precipitation_mm < 3:
        return "🔥 Жарко и сухо — наблюдайте за признаками водного стресса."
    if first_day.wind_kph >= 35:
        return "💨 Ветер — проверьте устойчивость растений после усиления."
    return "✅ Выраженных погодных рисков в ближайший день не видно."


def _render_summary(
    data: dict[str, Any],
    weather: WeatherData,
    estimate: YieldEstimate,
    irrigation: IrrigationAdvice,
    plan: list[CareDay],
) -> str:
    """Render the compact result shown immediately after the survey."""
    next_action = plan[0].action if plan else "Осмотреть поле"
    tomorrow_action = plan[1].action if len(plan) > 1 else next_action
    return (
        "🌱 EGOS — ПРОГНОЗ\n\n"
        f"📍 Местоположение: {weather.location_name}\n"
        f"   Координаты: {float(data['latitude']):.6f}, {float(data['longitude']):.6f}\n"
        f"🌾 Культура: {data['crop']}\n"
        f"📐 Площадь: {float(data['area']):.2f} га\n"
        f"📅 Посев: {format_date(date.fromisoformat(str(data['sowing_date'])))}\n\n"
        "━━━━━━━━━━━━\n\n"
        "📈 УРОЖАЙНОСТЬ\n"
        f"Ожидаемая: {estimate.yield_min:.2f}–{estimate.yield_max:.2f} т/га\n\n"
        "🌾 ОБЩИЙ УРОЖАЙ\n"
        f"{estimate.total_min:.2f}–{estimate.total_max:.2f} тонн\n\n"
        "━━━━━━━━━━━━\n\n"
        "🌦 ПОГОДА\n"
        f"Температура: {weather.current_temperature:.1f} °C "
        f"(днём до {weather.max_temperature:.1f} °C)\n"
        f"Осадки: {weather.precipitation_mm:.1f} мм, вероятность "
        f"{weather.precipitation_probability}%\n"
        f"Влажность: {weather.humidity}% · Ветер: {weather.wind_kph:.1f} км/ч\n"
        f"Риск: {_risk_line(weather)}\n\n"
        "💧 ПОЛИВ\n"
        f"{irrigation.title}: {irrigation.recommendation}\n\n"
        "🌱 ПЛАН УХОДА\n"
        f"Сегодня: {next_action}\n"
        f"Завтра: {tomorrow_action}\n\n"
        f"{DISCLAIMER}"
    )


async def create_forecast_from_survey(
    message: Message, state: FSMContext, data: dict[str, Any]
) -> None:
    """Run weather, analysis, persistence, and result messaging."""
    required = ("latitude", "longitude", "crop", "area", "sowing_date", "irrigation", "fertilizer")
    missing = [key for key in required if key not in data]
    if missing:
        logger.error("Survey data missing required keys: %s", missing)
        await state.clear()
        await message.answer(
            "Не хватает обязательных данных. Начните прогноз заново.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer("⏳ Получаю погоду именно для координат поля и анализирую данные...")
    try:
        weather = await _load_weather(float(data["latitude"]), float(data["longitude"]))
        estimate = calculate_yield(
            crop=str(data["crop"]),
            area=float(data["area"]),
            sowing_date=date.fromisoformat(str(data["sowing_date"])),
            irrigation=str(data["irrigation"]),
            fertilizer=str(data["fertilizer"]),
            weather_data=weather,
        )
        irrigation = calculate_irrigation_plan(
            weather, str(data["crop"]), str(data["irrigation"])
        )
        plan = generate_care_plan(
            str(data["crop"]),
            date.fromisoformat(str(data["sowing_date"])),
            weather,
            str(data["irrigation"]),
            str(data["fertilizer"]),
        )
        _save_forecast(message, data, estimate)
    except WeatherAPIError as exc:
        logger.warning("Weather request failed: %s", exc)
        await message.answer(
            f"Не удалось получить погоду для поля.\n\n{exc}\n\n"
            "Проверьте ключ и доступность сервиса, затем повторите прогноз.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return
    except (ValueError, KeyError) as exc:
        logger.exception("Forecast data processing failed: %s", exc)
        await message.answer(
            "Не удалось обработать данные поля. Начните прогноз заново.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return
    await state.clear()
    await message.answer(
        _render_summary(data, weather, estimate, irrigation, plan),
        reply_markup=result_keyboard(),
    )


async def run_demo_scenario(message: Message) -> None:
    """Show a complete prepared flow without requiring an external API key."""
    data: dict[str, Any] = {
        "latitude": 43.2389,
        "longitude": 76.8897,
        "crop": "Пшеница",
        "area": 50.0,
        "sowing_date": date.today().replace(month=4, day=15).isoformat(),
        "irrigation": "Да",
        "fertilizer": "Да",
        "notes": "Демонстрационное поле",
    }
    stages = (
        "1/6 📍 Геолокация: 43.238900, 76.889700",
        "2/6 🌾 Культура: пшеница · площадь: 50 га",
        "3/6 📅 Дата посева: 15.04",
        "4/6 🌦 API: подготовленный погодный ответ для точки поля",
        "5/6 🔬 Анализ: демонстрационная модель урожайности",
        "6/6 📋 Формирую персональный план ухода",
    )
    for stage in stages:
        await message.answer(stage)
        await asyncio.sleep(0.15)
    weather = get_demo_weather(data["latitude"], data["longitude"])
    estimate = calculate_yield(
        data["crop"],
        data["area"],
        date.fromisoformat(data["sowing_date"]),
        data["irrigation"],
        data["fertilizer"],
        weather,
    )
    irrigation = calculate_irrigation_plan(weather, data["crop"], data["irrigation"])
    plan = generate_care_plan(
        data["crop"],
        date.fromisoformat(data["sowing_date"]),
        weather,
        data["irrigation"],
        data["fertilizer"],
    )
    _save_forecast(message, data, estimate)
    await message.answer(
        _render_summary(data, weather, estimate, irrigation, plan),
        reply_markup=result_keyboard(),
    )


@router.message(F.text == "🔄 Новый прогноз")
async def new_forecast(message: Message, state: FSMContext) -> None:
    """Delegate to the survey entry point."""
    from .survey import begin_survey

    await begin_survey(message, state)