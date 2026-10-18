import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto
from dtek_schedule import MISSING, UNPUBLISHED, WRONG_DAY, pick_snapshot
from handlers.logic import (get_notifications, get_panel, get_tuya_state,
                            pop_secondary_message, set_notifications,
                            set_secondary_message)
from handlers.menus import (SCH_CLOSE, SCH_SHOW, SCH_TODAY, SCH_TOMORROW,
                            STD_NOTIFY_OFF, STD_NOTIFY_ON, schedule_keyboard,
                            standard_keyboard)
from monitor import device_suffix, fetch_watched, poll_seconds
from settings import tuya_location
from tuya import get_client
from ui import delete_quietly, edit_panel

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
        return f"Пристрій для моніторингу ({tuya_location()}) не знайдено."

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


# ---- графік відключень ДТЕК (картинка, яку раз на N хвилин знімає dtek_schedule)

DAY_LABELS = {"today": "на сьогодні", "tomorrow": "на завтра"}
# що сказати користувачеві, коли показати графік неможливо (за причиною з pick_snapshot)
SCHEDULE_UNAVAILABLE = {
    MISSING: "Графік ще завантажується, спробуйте за хвилину",
    UNPUBLISHED: "ДТЕК ще не опублікував графік на завтра. Зазвичай він з'являється ввечері",
    WRONG_DAY: "Графік тимчасово недоступний. Перевірте його на сайті ДТЕК",
}
# file_id вже завантаженої в Telegram картинки: (файл, час зміни файлу) -> file_id
_file_ids: dict[tuple[str, int], str] = {}


def schedule_caption(day: str, pick) -> str:
    lines = [f"📅 Графік відключень {DAY_LABELS[day]}"]
    if pick.site_updated:
        lines.append(f"Оновлено ДТЕК: {pick.site_updated}")
    if pick.stale:
        # новіший знімок зробити не вдалося: чесно кажемо, наскільки він старий
        lines.append(
            f"⚠️ Знімок зроблено о {pick.updated.strftime('%d.%m %H:%M')}, "
            "актуальність уточніть на сайті ДТЕК"
        )
    return "\n".join(lines)


def schedule_media(day: str):
    """(файл або file_id, ключ кешу, підпис, None) або (None, None, None, причина)."""
    pick, reason = pick_snapshot(day)
    if pick is None:
        return None, None, None, reason
    key = (pick.path.name, pick.path.stat().st_mtime_ns)
    media = _file_ids.get(key) or FSInputFile(pick.path)
    return media, key, schedule_caption(day, pick), None


def remember_file_id(key: tuple[str, int], message: types.Message | bool):
    if isinstance(message, types.Message) and message.photo:
        _file_ids[key] = message.photo[-1].file_id


@router.callback_query(F.data == SCH_SHOW)
async def show_schedule(callback: types.CallbackQuery):
    media, key, caption, reason = schedule_media("today")
    if media is None:
        await callback.answer(SCHEDULE_UNAVAILABLE[reason], show_alert=True)
        return
    await callback.answer()

    user_id = callback.from_user.id
    # вторинне повідомлення лише одне: графік замінює попереднє (фото чи попередження)
    old = await pop_secondary_message(user_id)
    if old:
        await delete_quietly(callback.bot, user_id, old)
    # кнопку натиснули під попередженням, якого немає в базі (наприклад, воно застаріло):
    # прибираємо й його, щоб графік відкрився «замість» нього; основну панель не чіпаємо
    pressed = callback.message.message_id if callback.message else None
    if pressed and pressed != old and pressed != await get_panel(user_id):
        await delete_quietly(callback.bot, user_id, pressed)
    sent = await callback.bot.send_photo(
        chat_id=user_id,
        photo=media,
        caption=caption,
        reply_markup=schedule_keyboard("today"),
    )
    await set_secondary_message(user_id, sent.message_id)
    remember_file_id(key, sent)


@router.callback_query(F.data.in_({SCH_TODAY, SCH_TOMORROW}))
async def switch_schedule_day(callback: types.CallbackQuery):
    day = "today" if callback.data == SCH_TODAY else "tomorrow"
    media, key, caption, reason = schedule_media(day)
    if media is None:
        await callback.answer(SCHEDULE_UNAVAILABLE[reason], show_alert=True)
        return
    await callback.answer()
    if callback.message is None:
        return

    try:
        edited = await callback.message.edit_media(
            InputMediaPhoto(media=media, caption=caption),
            reply_markup=schedule_keyboard(day),
        )
    except TelegramBadRequest as error:
        # натиснули вже відкритий день: Telegram відповідає "message is not modified"
        if "not modified" not in str(error).lower():
            logger.warning("Не вдалося змінити графік: %s", error)
        return
    remember_file_id(key, edited)


@router.callback_query(F.data == SCH_CLOSE)
async def close_schedule(callback: types.CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return
    await delete_quietly(
        callback.bot, callback.from_user.id, callback.message.message_id
    )
    await pop_secondary_message(
        callback.from_user.id, only_message_id=callback.message.message_id
    )
