"""Фоновий моніторинг світла через Tuya: один цикл на всіх користувачів стандартного режиму."""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from handlers.logic import get_tuya_state, list_notify_user_ids, set_tuya_state
from handlers.menus import standard_keyboard
from push import TuyaPush
from settings import env_int, tuya_device_ids, tuya_location, tuya_push_enabled
from ui import send_panel

logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")

# стан пристрою читається й змінюється під замком: регулярне опитування і перевірка
# після push можуть працювати одночасно, і сповіщення не має дублюватися
_state_lock = asyncio.Lock()
# остання відповідь API: at - монотонний час (для віку), wall - час на годиннику
_cache: dict = {"at": 0.0, "wall": None, "devices": None}
# перевірки після push-події, по одній на пристрій
_verify_tasks: dict[str, asyncio.Task] = {}


def poll_seconds() -> int:
    # Як часто питаємо Tuya про стан. Побачивши зміну, опитування одразу підтверджує її
    # контрольною перевіркою через паузу, тож затримка сповіщення = інтервал + ~15 с.
    # Безкоштовна квота API обмежена (26 тис. запитів на місяць).
    return env_int("TUYA_POLL_SECONDS", 120)


def verify_pause() -> int:
    # пауза (с) між перевірками стану в API після push-події: перша перевірка теж
    # через цю паузу, а не одразу, щоб відсікти короткі збої зв'язку
    return env_int("TUYA_PUSH_VERIFY_SECONDS", 15)


def verify_checks() -> int:
    # скільки перевірок поспіль мають підтвердити зміну, перш ніж про неї повідомити
    return env_int("TUYA_PUSH_CHECKS", 1)


# скільки додаткових перевірок дозволено, якщо API ще показує старий стан
MAX_EXTRA_VERIFY_CHECKS = 4


def now_kyiv() -> datetime:
    return datetime.now(KYIV)


def last_check_time() -> datetime | None:
    """Коли востаннє отримано відповідь від Tuya (None, якщо ще не було)."""
    return _cache["wall"]


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


async def fetch_watched(client, max_age: float = 0):
    """Пристрої, за якими стежимо: усі з акаунта або лише з TUYA_DEVICE_ID.

    max_age > 0 дозволяє віддати відповідь, отриману не давніше за стільки секунд,
    щоб показ статусу користувачам не витрачав квоту запитів до Tuya.
    """
    now = time.monotonic()
    if max_age and _cache["devices"] is not None and now - _cache["at"] < max_age:
        devices = _cache["devices"]
    else:
        devices = await client.list_devices()
        _cache.update(at=now, wall=now_kyiv(), devices=devices)
    wanted = tuya_device_ids()
    return [device for device in devices if not wanted or device["id"] in wanted]


def device_suffix(device: dict, several: bool) -> str:
    # назву пристрою показуємо лише коли їх кілька, інакше вистачає адреси
    return f"\nПристрій: {device['name']}" if several and device["name"] else ""


async def _register_reading(device_id: str, online: bool, now: datetime):
    """Оновлює збережений стан; повертає тривалість попереднього стану, якщо він змінився."""
    async with _state_lock:
        state = await get_tuya_state(device_id)
        if state is None:
            # перше показання пристрою: просто запам'ятовуємо, без сповіщення
            await set_tuya_state(device_id, online, now.isoformat())
            return None

        previous_online, since = state
        if online == previous_online:
            return None

        await set_tuya_state(device_id, online, now.isoformat())
        return now - datetime.fromisoformat(since)


async def process_reading(bot, device: dict, now: datetime, several: bool = False):
    """Записує показання (воно вже підтверджене) і за зміни стану сповіщає користувачів."""
    online = device["online"]
    elapsed = await _register_reading(device["id"], online, now)
    if elapsed is None:
        return
    duration = format_duration(elapsed)

    if online:
        head = f"🟢 Світло з'явилось о {format_time(now)}"
        tail = f"Не було {duration}"
    else:
        head = f"🔴 Світло зникло о {format_time(now)}"
        tail = f"Світло було {duration}"
    text = f"{head}\n📍 {tuya_location()}{device_suffix(device, several)}\n{tail}"

    for user_id in await list_notify_user_ids():
        try:
            # сповіщення стає новою панеллю: старе повідомлення зникає, кнопки лишаються під рукою
            await send_panel(bot, user_id, text, standard_keyboard(True))
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
    logger.info(
        "Опитування Tuya: %s",
        json.dumps(devices, ensure_ascii=False),
    )
    for device in devices:
        try:
            state = await get_tuya_state(device["id"])
            if state is not None and state[0] != device["online"]:
                # зміна стану: не чекаємо наступного опитування (через кілька хвилин), а
                # одразу підтверджуємо її контрольною перевіркою через паузу, як після push
                logger.info(
                    "Опитування побачило зміну стану …%s: %s -> %s, перевіряю",
                    device["id"][-4:],
                    state[0],
                    device["online"],
                )
                handle_push(bot, client, device["id"], device["online"])
                continue
            await process_reading(bot, device, now, several=len(devices) > 1)
        except Exception:
            logger.exception("Помилка обробки пристрою %s", device["id"])


async def verify_push(bot, client, device_id: str, expected_online: bool | None):
    """Після push-події чи зміни, помітної опитуванню, перевіряє стан у API з паузою.

    Сповіщення йде лише тоді, коли потрібну кількість перевірок підряд (за
    замовчуванням 1, через паузу 15 с) підтвердила зміну; будь-яка розбіжність
    скидає лічильник, і перевірка повторюється з тією ж паузою (до кількох
    спроб). Якщо expected_online=None (push не сказав, який стан), підтвердженням
    є однакова відповідь API потрібну кількість разів поспіль.
    """
    needed = verify_checks()
    confirmed = 0
    last_value = None
    for _ in range(needed + MAX_EXTRA_VERIFY_CHECKS):
        await asyncio.sleep(verify_pause())
        try:
            devices = await fetch_watched(client)
        except Exception:
            logger.warning("Не вдалося перевірити стан після push", exc_info=True)
            confirmed, last_value = 0, None
            continue

        device = next((d for d in devices if d["id"] == device_id), None)
        if device is None:
            return  # пристрій не з тих, за якими стежимо

        value = device["online"]
        if expected_online is None:
            confirmed = confirmed + 1 if value == last_value else 1
            last_value = value
        elif value != expected_online:
            confirmed = 0
        else:
            confirmed += 1
        logger.info(
            "Перевірка після push …%s: API online=%s (очікували %s), підтверджень %s/%s",
            device_id[-4:],
            value,
            "будь-який стан" if expected_online is None else expected_online,
            confirmed,
            needed,
        )
        if expected_online is not None and value != expected_online:
            continue

        if confirmed >= needed:
            await process_reading(bot, device, now_kyiv(), several=len(devices) > 1)
            return
    # API так і не підтвердив: розбереться регулярне опитування
    logger.info("Push Tuya: API не підтвердив зміну стану пристрою …%s", device_id[-4:])


def handle_push(bot, client, device_id: str, online: bool | None):
    """Викликається з push-каналу: запускає (єдину на пристрій) перевірку стану."""
    previous = _verify_tasks.pop(device_id, None)
    if previous is not None:
        previous.cancel()

    async def run():
        try:
            await verify_push(bot, client, device_id, online)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Помилка перевірки після push (пристрій …%s)", device_id[-4:]
            )

    task = asyncio.get_running_loop().create_task(run())
    _verify_tasks[device_id] = task
    task.add_done_callback(
        lambda t: _verify_tasks.get(device_id) is t and _verify_tasks.pop(device_id)
    )


async def tuya_monitor(bot, client):
    loop = asyncio.get_running_loop()
    push_task = None
    if tuya_push_enabled():
        push = TuyaPush(
            client,
            loop,
            lambda device_id, online: handle_push(bot, client, device_id, online),
        )
        push_task = asyncio.create_task(push.run())
    logger.info(
        "Моніторинг Tuya запущено (опитування кожні %s с, перевірка зміни через %s с, push: %s)",
        poll_seconds(),
        verify_pause(),
        "увімкнено" if push_task else "вимкнено",
    )
    try:
        while True:
            try:
                await poll_once(bot, client)
            except Exception:
                logger.exception("Збій циклу моніторингу Tuya")
            await asyncio.sleep(poll_seconds())
    finally:
        if push_task is not None:
            push_task.cancel()
        for task in list(_verify_tasks.values()):
            task.cancel()
