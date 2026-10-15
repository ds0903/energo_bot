import logging
from datetime import datetime

from aiogram import F, Router, types
from handlers.logic import get_notifications, get_tuya_state, set_notifications
from handlers.menus import STD_NOTIFY_OFF, STD_NOTIFY_ON, standard_keyboard
from monitor import device_suffix, fetch_watched, poll_seconds
from settings import tuya_location
from tuya import get_client
from ui import edit_panel

router = Router()
logger = logging.getLogger(__name__)

NOT_CONFIGURED_TEXT = (
    "Стандартний режим тимчасово недоступний: на сервері не налаштовано доступ до Tuya.\n"
    "Зверніться до розробника @ds0903."
)


async def status_text() -> str:
    """Поточний стан світла за даними Tuya (або пояснення, чому його немає)."""
    client = get_client()
    if client is None:
        return NOT_CONFIGURED_TEXT

    try:
        # беремо відповідь останнього опитування бота, а не питаємо Tuya щоразу: так
        # жодні дії користувачів не витрачають квоту запитів. До API іде лише запит,
        # якщо опитування давно не відбувалось (наприклад, бот щойно запущено).
        devices = await fetch_watched(client, max_age=poll_seconds() + 60)
    except Exception:
        logger.warning("Не вдалося отримати статус з Tuya", exc_info=True)
        return "⚠️ Не вдалося отримати статус світла. Спробуйте пізніше."

    if not devices:
        return f"Пристрій для моніторингу за адресою {tuya_location()} не знайдено."

    blocks = []
    for device in devices:
        lines = ["🟢 Світло є" if device["online"] else "🔴 Світла немає"]
        lines.append(f"📍 {tuya_location()}{device_suffix(device, len(devices) > 1)}")
        state = await get_tuya_state(device["id"])
        if state is not None and state[0] == device["online"]:
            since = datetime.fromisoformat(state[1]).strftime("%d.%m %H:%M")
            lines.append(f"з {since}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


async def standard_screen(user_id: int, notice: str = ""):
    """(текст, кнопки) головного екрана стандартного режиму."""
    # стан сповіщень видно за кнопкою (вона перемикається), тож окремого рядка немає
    notifications_on = await get_notifications(user_id)
    parts = [notice] if notice else []
    parts.append(await status_text())
    return "\n\n".join(parts), standard_keyboard(notifications_on)


async def show_standard(callback: types.CallbackQuery, notice: str = ""):
    text, markup = await standard_screen(callback.from_user.id, notice)
    await edit_panel(
        callback.bot,
        callback.from_user.id,
        text,
        markup,
        message_id=callback.message.message_id if callback.message else None,
    )


@router.callback_query(F.data.in_({STD_NOTIFY_ON, STD_NOTIFY_OFF}))
async def toggle_notifications(callback: types.CallbackQuery):
    enabled = callback.data == STD_NOTIFY_ON
    await set_notifications(callback.from_user.id, enabled)
    await callback.answer(
        "🔔 Сповіщення увімкнено" if enabled else "🔕 Сповіщення вимкнено"
    )
    await show_standard(callback)
