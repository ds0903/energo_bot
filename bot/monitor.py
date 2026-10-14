"""Фоновий моніторинг світла через Tuya: один цикл на всіх користувачів стандартного режиму."""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from handlers.logic import get_tuya_state, list_notify_user_ids, set_tuya_state
from settings import env_int, tuya_device_ids, tuya_location

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")

# device_id -> (стан, що спостерігається, скільки разів підряд)
_pending: dict[str, tuple[bool, int]] = {}


def poll_seconds() -> int:
    # Tuya і так бачить розрив зв'язку із запізненням в 1-3 хв, а безкоштовна квота API
    # обмежена, тож частіше за раз на пару хвилин опитувати немає сенсу
    return env_int("TUYA_POLL_SECONDS", 120)


def confirm_polls() -> int:
    # скільки опитувань підряд має показати нову зміну, перш ніж про неї повідомити
    return env_int("TUYA_CONFIRM_POLLS", 2)


def now_kyiv() -> datetime:
    return datetime.now(KYIV)


def format_duration(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} год")
    if minutes or not parts:
        parts.append(f"{minutes} хв")
    return " ".join(parts)


def format_time(moment: datetime) -> str:
    return moment.astimezone(KYIV).strftime("%H:%M")


async def fetch_watched(client):
    """Пристрої, за якими стежимо: усі з акаунта або лише з TUYA_DEVICE_ID."""
    devices = await client.list_devices()
    wanted = tuya_device_ids()
    return [device for device in devices if not wanted or device["id"] in wanted]


def device_suffix(device: dict, several: bool) -> str:
    # назву пристрою показуємо лише коли їх кілька, інакше вистачає адреси
    return f"\nПристрій: {device['name']}" if several and device["name"] else ""


async def process_reading(bot, device: dict, now: datetime, several: bool = False):
    """Порівнює свіже показання зі збереженим станом і за потреби сповіщає користувачів."""
    device_id, online = device["id"], device["online"]
    state = await get_tuya_state(device_id)
    if state is None:
        # перше показання пристрою: просто запам'ятовуємо, без сповіщення
        await set_tuya_state(device_id, online, now.isoformat())
        _pending.pop(device_id, None)
        return

    previous_online, since = state
    if online == previous_online:
        _pending.pop(device_id, None)
        return

    seen, count = _pending.get(device_id, (online, 0))
    count = count + 1 if seen == online else 1
    if count < confirm_polls():
        _pending[device_id] = (online, count)
        return
    _pending.pop(device_id, None)

    duration = format_duration(now - datetime.fromisoformat(since))
    await set_tuya_state(device_id, online, now.isoformat())

    if online:
        head = f"🟢 Світло з'явилось о {format_time(now)}"
        tail = f"Не було {duration}"
    else:
        head = f"🔴 Світло зникло о {format_time(now)}"
        tail = f"Світло було {duration}"
    text = f"{head}\n📍 {tuya_location()}{device_suffix(device, several)}\n{tail}"

    for user_id in await list_notify_user_ids():
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except TelegramForbiddenError:
            logger.info("Користувач %s заблокував бота", user_id)
        except TelegramAPIError:
            logger.warning("Не вдалося надіслати сповіщення %s", user_id, exc_info=True)


async def poll_once(bot, client):
    try:
        devices = await fetch_watched(client)
    except Exception:
        # помилка мережі чи Tuya - стан не чіпаємо, щоб не було хибних "світла немає"
        logger.warning("Не вдалося опитати Tuya", exc_info=True)
        return

    now = now_kyiv()
    for device in devices:
        try:
            await process_reading(bot, device, now, several=len(devices) > 1)
        except Exception:
            logger.exception("Помилка обробки пристрою %s", device["id"])


async def tuya_monitor(bot, client):
    logger.info("Моніторинг Tuya запущено (опитування кожні %s с)", poll_seconds())
    while True:
        try:
            await poll_once(bot, client)
        except Exception:
            logger.exception("Збій циклу моніторингу Tuya")
        await asyncio.sleep(poll_seconds())
