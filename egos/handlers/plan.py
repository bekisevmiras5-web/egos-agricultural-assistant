"""History, weather detail, plan detail, and informational screens."""

from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import desc, select

from ..config import get_settings
from ..database import SessionLocal, get_or_create_user
from ..keyboards.keyboards import main_menu_keyboard, result_keyboard
from ..models import Field, YieldForecast
from ..services.care_plan import generate_care_plan
from ..services.weather_api import WeatherAPIError, get_demo_weather, get_weather
from ..utils.validation import format_date


logger = logging.getLogger(__name__)
router = Router(name="plan")


def _latest_pair(message: Message) -> tuple[Field, YieldForecast] | None:
    """Return the user's latest field and its latest forecast."""
    if not message.from_user:
        return None
    with SessionLocal() as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
        )
        row = session.execute(
            select(Field, YieldForecast)
            .join(YieldForecast, YieldForecast.field_id == Field.id)
            .where(Field.user_id == user.id)
            .order_by(desc(YieldForecast.created_at))
            .limit(1)
        ).first()
        return row if row else None


async def _latest_weather(message: Message) -> tuple[Field, YieldForecast, object] | None:
    """Fetch fresh weather for the latest saved field."""
    pair = _latest_pair(message)
    if pair is None:
        return None
    field, forecast = pair
    try:
        weather = (
            get_demo_weather(field.latitude, field.longitude)
            if get_settings().demo_mode
            else await get_weather(field.latitude, field.longitude)
        )
    except WeatherAPIError as exc:
        await message.answer(f"Погоду получить не удалось.\n\n{exc}", reply_markup=main_menu_keyboard())
        return None
    return field, forecast, weather


@router.message(F.text == "🏠 Главное меню")
async def main_menu(message: Message, state: FSMContext) -> None:
    """Return to navigation and cancel any active state."""
    await state.clear()
    await message.answer("Главное меню EGOS.", reply_markup=main_menu_keyboard())


@router.message(F.text == "ℹ️ О проекте")
async def about_project(message: Message) -> None:
    """Explain the MVP boundaries and data handling."""
    await message.answer(
        "ℹ️ EGOS — Agricultural Yield & Care Assistant\n\n"
        "Бот получает прогноз для координат поля, показывает риски погоды и "
        "создаёт план наблюдений за культурой.\n\n"
        "Расчёт урожайности в этой версии — прозрачная демонстрационная модель "
        "с базовыми коэффициентами культур. Это не научный прогноз и не заменяет "
        "обследование поля агрономом.\n\n"
        "Погодные координаты и история прогнозов сохраняются в локальной SQLite.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.in_({"📋 Мой план", "📋 Полный план"}))
async def full_plan(message: Message) -> None:
    """Show a seven-day care plan based on the latest field."""
    latest = await _latest_weather(message)
    if latest is None:
        await message.answer(
            "История пока пуста. Сначала создайте прогноз.",
            reply_markup=main_menu_keyboard(),
        )
        return
    field, _forecast, weather = latest
    plan = generate_care_plan(
        field.crop,
        field.sowing_date,
        weather,
        field.irrigation,
        field.fertilizer,
    )
    lines = ["🌱 ПЛАН УХОДА НА 7 ДНЕЙ", f"Культура: {field.crop}", ""]
    for day in plan:
        lines.extend(
            [
                f"📅 {format_date(day.date)}",
                f"🌦 {day.weather}",
                f"⚠️ Риск: {day.risk}",
                f"🌱 Действие: {day.action}",
                f"💡 Причина: {day.reason}",
                "",
            ]
        )
    lines.append("Рекомендации не являются гарантированным агрономическим решением.")
    await message.answer("\n".join(lines), reply_markup=result_keyboard())


@router.message(F.text.in_({"🌦 Погода", "🌦 Подробная погода"}))
async def detailed_weather(message: Message) -> None:
    """Show the live or prepared seven-day weather forecast."""
    latest = await _latest_weather(message)
    if latest is None:
        await message.answer(
            "Сначала создайте прогноз, чтобы привязать погоду к полю.",
            reply_markup=main_menu_keyboard(),
        )
        return
    field, _forecast, weather = latest
    lines = [
        "🌦 ПОДРОБНАЯ ПОГОДА",
        f"📍 {weather.location_name}",
        f"Координаты поля: {field.latitude:.6f}, {field.longitude:.6f}",
        "",
    ]
    for day in weather.forecast:
        lines.append(
            f"📅 {format_date(day.date)} · {day.condition}\n"
            f"🌡 {day.min_temperature:.0f}–{day.max_temperature:.0f} °C · "
            f"🌧 {day.precipitation_mm:.1f} мм · шанс {day.precipitation_probability}% · "
            f"💧 {day.humidity}%"
        )
    await message.answer("\n\n".join(lines), reply_markup=result_keyboard())


@router.message(F.text == "📈 Урожайность")
async def yield_history(message: Message) -> None:
    """Show the latest estimate plus a short historical list."""
    if not message.from_user:
        return
    with SessionLocal() as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
        )
        rows = session.execute(
            select(Field, YieldForecast)
            .join(YieldForecast, YieldForecast.field_id == Field.id)
            .where(Field.user_id == user.id)
            .order_by(desc(YieldForecast.created_at))
            .limit(5)
        ).all()
    if not rows:
        await message.answer("История пока пуста. Сначала создайте прогноз.", reply_markup=main_menu_keyboard())
        return
    lines = ["📈 ПОСЛЕДНИЕ ОЦЕНКИ УРОЖАЙНОСТИ", ""]
    for field, forecast in rows:
        lines.append(
            f"🌾 {field.crop} · {field.area:.2f} га\n"
            f"   {forecast.yield_min:.2f}–{forecast.yield_max:.2f} т/га · "
            f"{forecast.total_min:.2f}–{forecast.total_max:.2f} т\n"
            f"   Создано: {forecast.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
    lines.append(f"\n{ '⚠️ Демонстрационная оценка MVP.' }")
    await message.answer("\n\n".join(lines), reply_markup=result_keyboard())


@router.message(F.text == "📊 История")
async def forecast_history(message: Message) -> None:
    """List previous forecasts in the requested date/crop/area format."""
    if not message.from_user:
        return
    with SessionLocal() as session:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
        )
        rows = session.execute(
            select(Field, YieldForecast)
            .join(YieldForecast, YieldForecast.field_id == Field.id)
            .where(Field.user_id == user.id)
            .order_by(desc(YieldForecast.created_at))
            .limit(10)
        ).all()
    if not rows:
        await message.answer(
            "📊 История пуста. Создайте первый прогноз.",
            reply_markup=main_menu_keyboard(),
        )
        return
    lines = ["📊 ИСТОРИЯ ПРОГНОЗОВ", ""]
    for field, forecast in rows:
        lines.append(
            f"{forecast.created_at.strftime('%d.%m.%Y')} → {field.crop} → "
            f"{field.area:.2f} га → {forecast.yield_min:.2f}–"
            f"{forecast.yield_max:.2f} т/га"
        )
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())