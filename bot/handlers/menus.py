from aiogram import types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import (MODE_EXTENDED, MODE_STANDARD, get_notifications,
                            get_user_mode)
from settings import ip_check_minutes, tuya_location

BTN_STANDARD_MODE = "🏠 Стандартний режим"
BTN_EXTENDED_MODE = "🛠 Розширений режим"
BTN_CHANGE_MODE = "Змінити режим"
BTN_NOTIFY_ON = "🔔 Увімкнути сповіщення"
BTN_NOTIFY_OFF = "🔕 Вимкнути сповіщення"


def mode_choice_text() -> str:
    return (
        "Оберіть режим роботи бота:\n\n"
        f"🏠 Стандартний — моніторинг світла за адресою {tuya_location()}\n\n"
        "🛠 Розширений — моніторинг IP-адрес (роутер, камера тощо): "
        f"бот пінгує їх кожні {ip_check_minutes()} хв.\n\n"
        "Режим можна змінити в будь-який момент у меню."
    )


def _keyboard(rows):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
    )


def mode_choice_keyboard():
    return _keyboard([[BTN_STANDARD_MODE], [BTN_EXTENDED_MODE]])


def standard_menu_keyboard(notifications_on: bool):
    notify_button = BTN_NOTIFY_OFF if notifications_on else BTN_NOTIFY_ON
    return _keyboard(
        [
            ["Статус світла", notify_button],
            [BTN_CHANGE_MODE],
        ]
    )


def extended_menu_keyboard():
    return _keyboard(
        [
            ["Увімкнути бота", "Вимкнути бота"],
            ["Допомога", "Мої IP-адреси"],
            [BTN_CHANGE_MODE],
        ]
    )


async def send_mode_choice(message: types.Message):
    await message.answer(mode_choice_text(), reply_markup=mode_choice_keyboard())


async def send_menu(message: types.Message, text: str = "Оберіть потрібну вам дію"):
    """Головне меню відповідно до режиму користувача (або вибір режиму, якщо його ще немає)."""
    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode == MODE_STANDARD:
        keyboard = standard_menu_keyboard(await get_notifications(user_id))
        await message.answer(text, reply_markup=keyboard)
    elif mode == MODE_EXTENDED:
        await message.answer(text, reply_markup=extended_menu_keyboard())
    else:
        await send_mode_choice(message)
