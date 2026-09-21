"""All Telegram keyboards used by EGOS."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent main navigation."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌾 Создать прогноз")],
            [KeyboardButton(text="📋 Мой план"), KeyboardButton(text="🌦 Погода")],
            [
                KeyboardButton(text="📈 Урожайность"),
                KeyboardButton(text="📊 История"),
            ],
            [KeyboardButton(text="ℹ️ О проекте")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def location_keyboard() -> ReplyKeyboardMarkup:
    """Location request keyboard with a manual coordinate fallback."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="Ввести координаты вручную")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def crop_keyboard() -> ReplyKeyboardMarkup:
    """Common crop choices."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пшеница"), KeyboardButton(text="Кукуруза")],
            [KeyboardButton(text="Подсолнечник"), KeyboardButton(text="Картофель")],
            [KeyboardButton(text="Другая культура")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def yes_no_unknown_keyboard() -> ReplyKeyboardMarkup:
    """Three-state answer keyboard used for irrigation and fertilizer."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
            [KeyboardButton(text="Не знаю")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_keyboard() -> ReplyKeyboardMarkup:
    """Optional notes input keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def result_keyboard() -> ReplyKeyboardMarkup:
    """Actions available after a forecast is generated."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Полный план")],
            [
                KeyboardButton(text="🌦 Подробная погода"),
                KeyboardButton(text="📈 Урожайность"),
            ],
            [KeyboardButton(text="🔄 Новый прогноз")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
    )