import logging
from datetime import datetime

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from handlers.logic import (MODE_EXTENDED, MODE_STANDARD, get_notifications,
                            get_tuya_state, set_notifications, set_user_mode)
from handlers.menus import (BTN_CHANGE_MODE, BTN_EXTENDED_MODE, BTN_NOTIFY_OFF,
                            BTN_NOTIFY_ON, BTN_STANDARD_MODE, send_menu,
                            send_mode_choice)
from monitor import device_suffix, fetch_watched
from settings import tuya_location
from tuya import get_client

router = Router()
logger = logging.getLogger(__name__)

NOT_CONFIGURED_TEXT = (
    "Стандартний режим тимчасово недоступний: на сервері не налаштовано доступ до Tuya.\n"
    "Зверніться до розробника @ds0903."
)


@router.message(Command("mode"))
@router.message(lambda message: message.text == BTN_CHANGE_MODE)
async def change_mode(message: types.Message, state: FSMContext):
    await state.clear()
    await send_mode_choice(message)


@router.message(lambda message: message.text == BTN_STANDARD_MODE)
async def choose_standard_mode(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    await set_user_mode(user_id, MODE_STANDARD)
    if await get_notifications(user_id):
        notify = "🔔 Сповіщення увімкнено"
    else:
        notify = "🔕 Сповіщення вимкнено"
    await send_menu(
        message,
        f"Стандартний режим увімкнено\nМоніторинг світла за адресою {tuya_location()}\n{notify}",
    )
    await light_status(message)


@router.message(lambda message: message.text == BTN_NOTIFY_ON)
async def notifications_on(message: types.Message):
    await set_notifications(message.from_user.id, True)
    await send_menu(
        message,
        "🔔 Сповіщення увімкнено. Бот напише, коли світло зникне і коли воно з'явиться.",
    )


@router.message(lambda message: message.text == BTN_NOTIFY_OFF)
async def notifications_off(message: types.Message):
    await set_notifications(message.from_user.id, False)
    await send_menu(
        message,
        "🔕 Сповіщення вимкнено. Дізнатися про світло можна кнопкою «Статус світла».",
    )


@router.message(lambda message: message.text == BTN_EXTENDED_MODE)
async def choose_extended_mode(message: types.Message, state: FSMContext):
    await state.clear()
    await set_user_mode(message.from_user.id, MODE_EXTENDED)
    await message.answer("Розширений режим увімкнено")
    await send_menu(message)


@router.message(lambda message: message.text == "Статус світла")
async def light_status(message: types.Message):
    client = get_client()
    if client is None:
        await message.answer(NOT_CONFIGURED_TEXT)
        return

    try:
        devices = await fetch_watched(client)
    except Exception:
        logger.warning("Не вдалося отримати статус з Tuya", exc_info=True)
        await message.answer("Не вдалося отримати статус світла. Спробуйте пізніше.")
        return

    if not devices:
        await message.answer(
            f"Пристрій для моніторингу за адресою {tuya_location()} не знайдено."
        )
        return

    for device in devices:
        if device["online"]:
            line = "🟢 Світло є"
        else:
            line = "🔴 Світла немає"
        line += f"\n📍 {tuya_location()}{device_suffix(device, len(devices) > 1)}"

        state = await get_tuya_state(device["id"])
        if state is not None and state[0] == device["online"]:
            since = datetime.fromisoformat(state[1]).strftime("%d.%m %H:%M")
            line += f"\nз {since}"
        await message.answer(line)
