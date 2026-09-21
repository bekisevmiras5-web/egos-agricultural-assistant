"""Step-by-step field survey implemented with aiogram FSM."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from ..keyboards.keyboards import (
    crop_keyboard,
    location_keyboard,
    main_menu_keyboard,
    skip_keyboard,
    yes_no_unknown_keyboard,
)
from ..utils.validation import (
    ValidationError,
    normalize_choice,
    parse_area,
    parse_coordinates,
    parse_sowing_date,
)


logger = logging.getLogger(__name__)
router = Router(name="survey")


class SurveyStates(StatesGroup):
    """FSM states for required field data and optional notes."""

    location = State()
    manual_location = State()
    crop = State()
    area = State()
    sowing_date = State()
    irrigation = State()
    fertilizer = State()
    notes = State()


def _start_survey_text() -> str:
    return (
        "Создадим прогноз по вашему полю.\n\n"
        "1 из 7 — 📍 Отправьте геолокацию поля кнопкой ниже. "
        "Telegram передаст координаты автоматически.\n\n"
        "Если отправка недоступна, выберите ручной ввод."
    )


@router.message(F.text == "🌾 Создать прогноз")
async def begin_survey(message: Message, state: FSMContext) -> None:
    """Start a fresh survey regardless of a previous incomplete one."""
    await state.clear()
    await state.set_state(SurveyStates.location)
    await message.answer(_start_survey_text(), reply_markup=location_keyboard())


@router.message(SurveyStates.location, F.location)
async def receive_location(message: Message, state: FSMContext) -> None:
    """Accept Telegram's native location payload."""
    if not message.location:
        await message.answer("Не удалось прочитать геолокацию.", reply_markup=location_keyboard())
        return
    await state.update_data(
        latitude=round(message.location.latitude, 6),
        longitude=round(message.location.longitude, 6),
    )
    await state.set_state(SurveyStates.crop)
    await message.answer(
        "Геолокация получена.\n\n2 из 7 — 🌾 Выберите культуру.",
        reply_markup=crop_keyboard(),
    )


@router.message(SurveyStates.location, F.text == "Ввести координаты вручную")
async def request_manual_location(message: Message, state: FSMContext) -> None:
    """Switch to the manual coordinate text input."""
    await state.set_state(SurveyStates.manual_location)
    await message.answer(
        "Введите широту и долготу через запятую или пробел.\n"
        "Пример: 43.2389, 76.8897",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(SurveyStates.location, F.text == "🏠 Главное меню")
@router.message(SurveyStates.manual_location, F.text == "🏠 Главное меню")
async def cancel_location(message: Message, state: FSMContext) -> None:
    """Allow a user to leave the first step safely."""
    await state.clear()
    await message.answer("Опрос отменён.", reply_markup=main_menu_keyboard())


@router.message(SurveyStates.location)
async def invalid_location(message: Message) -> None:
    """Handle text accidentally sent instead of a location."""
    await message.answer(
        "Нужна геолокация Telegram или ручной ввод координат.",
        reply_markup=location_keyboard(),
    )


@router.message(SurveyStates.manual_location)
async def receive_manual_location(message: Message, state: FSMContext) -> None:
    """Validate and store manually entered coordinates."""
    try:
        latitude, longitude = parse_coordinates(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(latitude=latitude, longitude=longitude)
    await state.set_state(SurveyStates.crop)
    await message.answer(
        "Координаты сохранены.\n\n2 из 7 — 🌾 Выберите культуру.",
        reply_markup=crop_keyboard(),
    )


@router.message(SurveyStates.crop)
async def receive_crop(message: Message, state: FSMContext) -> None:
    """Accept a predefined crop or a custom crop name."""
    crop = (message.text or "").strip()
    if not crop:
        await message.answer("Введите название культуры или выберите кнопку.", reply_markup=crop_keyboard())
        return
    if normalize_choice(crop) == "другая культура":
        await message.answer("Введите название культуры текстом.")
        return
    await state.update_data(crop=crop)
    await state.set_state(SurveyStates.area)
    await message.answer(
        "3 из 7 — 📐 Укажите площадь поля в гектарах.\n"
        "Например: 25.5",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(SurveyStates.area)
async def receive_area(message: Message, state: FSMContext) -> None:
    """Validate a positive hectare amount."""
    try:
        area = parse_area(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(area=area)
    await state.set_state(SurveyStates.sowing_date)
    await message.answer(
        "4 из 7 — 📅 Укажите дату посева.\n"
        "Формат: ДД.ММ.ГГГГ, например 15.04.2026",
    )


@router.message(SurveyStates.sowing_date)
async def receive_sowing_date(message: Message, state: FSMContext) -> None:
    """Validate a sowing date without silently coercing invalid input."""
    try:
        sowing_date = parse_sowing_date(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(sowing_date=sowing_date.isoformat())
    await state.set_state(SurveyStates.irrigation)
    await message.answer(
        "5 из 7 — 💧 Есть ли орошение?",
        reply_markup=yes_no_unknown_keyboard(),
    )


@router.message(SurveyStates.irrigation)
async def receive_irrigation(message: Message, state: FSMContext) -> None:
    """Accept one of three irrigation answers."""
    answer = (message.text or "").strip()
    if normalize_choice(answer) not in {"да", "нет", "не знаю"}:
        await message.answer("Выберите «Да», «Нет» или «Не знаю».", reply_markup=yes_no_unknown_keyboard())
        return
    await state.update_data(irrigation=answer)
    await state.set_state(SurveyStates.fertilizer)
    await message.answer(
        "6 из 7 — 🧪 Использовались ли удобрения?",
        reply_markup=yes_no_unknown_keyboard(),
    )


@router.message(SurveyStates.fertilizer)
async def receive_fertilizer(message: Message, state: FSMContext) -> None:
    """Accept one of three fertilizer answers."""
    answer = (message.text or "").strip()
    if normalize_choice(answer) not in {"да", "нет", "не знаю"}:
        await message.answer("Выберите «Да», «Нет» или «Не знаю».", reply_markup=yes_no_unknown_keyboard())
        return
    await state.update_data(fertilizer=answer)
    await state.set_state(SurveyStates.notes)
    await message.answer(
        "7 из 7 — 📝 Дополнительная информация о поле (необязательно).\n"
        "Напишите её или нажмите «Пропустить».",
        reply_markup=skip_keyboard(),
    )


@router.message(SurveyStates.notes)
async def receive_notes(message: Message, state: FSMContext) -> None:
    """Finish the survey and hand data to the forecast service."""
    notes = (message.text or "").strip()
    if normalize_choice(notes) == "🏠 главное меню":
        await state.clear()
        await message.answer("Опрос отменён.", reply_markup=main_menu_keyboard())
        return
    await state.update_data(notes="" if normalize_choice(notes) == "пропустить" else notes)
    data = await state.get_data()
    from .forecast import create_forecast_from_survey

    await create_forecast_from_survey(message, state, data)