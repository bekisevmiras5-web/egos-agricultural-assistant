"""Start, demo, and primary navigation entry points."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from ..config import get_settings
from ..database import SessionLocal, get_or_create_user
from ..keyboards.keyboards import main_menu_keyboard


logger = logging.getLogger(__name__)
router = Router(name="start")


WELCOME_TEXT = (
    "🌱 EGOS\n"
    "«Цифровой помощник для планирования урожая.»\n\n"
    "Я помогу собрать данные о поле, получить прогноз погоды для его координат "
    "и подготовить осторожную демонстрационную оценку урожайности."
)


def _remember_user(message: Message) -> None:
    """Persist Telegram user metadata for every entry point."""
    if not message.from_user:
        return
    with SessionLocal() as session:
        get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
        )


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    """Show the main menu and reset an interrupted survey."""
    await state.clear()
    _remember_user(message)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("demo"))
async def demo_handler(message: Message, state: FSMContext) -> None:
    """Run the prepared presentation flow."""
    await state.clear()
    _remember_user(message)
    settings = get_settings()
    if not settings.demo_mode:
        await message.answer(
            "Демо-режим выключен. Установите DEMO_MODE=true в .env для презентации.",
            reply_markup=main_menu_keyboard(),
        )
        return
    from .forecast import run_demo_scenario

    await run_demo_scenario(message)