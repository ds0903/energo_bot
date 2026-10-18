"""Повідомлення за графіком ДТЕК: «графік змінився» (працює) і «через годину вимкнуть
світло» (код збережено, але вимкнено в bot.py: alerts_loop не запускається).

Це вторинні повідомлення: кожне нове замінює попереднє (фото графіка чи старе
попередження), а основну панель «світло є / немає» вони не чіпають. Під ними є кнопка
«📅 Графік відключень», що відкриває графік на місці попередження.
"""

import asyncio
import logging
import math
from datetime import date, datetime
from datetime import time as dt_time
from datetime import timedelta

import dtek_schedule
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from handlers.logic import claim_alert, list_notify_user_ids, purge_alerts
from handlers.menus import alert_keyboard
from outage_data import (day_intervals, fmt_interval, fmt_intervals,
                         slots_by_date, two_day_intervals)
from settings import outage_warn_minutes, tuya_location
from ui import send_secondary

logger = logging.getLogger(__name__)

KYIV = dtek_schedule.KYIV
CHECK_EVERY_SECONDS = 30
# якщо до початку відключення лишилось менше стількох хвилин, попереджати вже запізно
MIN_MINUTES_LEFT = 3
KEEP_ALERTS_DAYS = 3
DAY_LABELS = {"today": "на сьогодні", "tomorrow": "на завтра"}


def warning_text(minutes_left: int, start: int, end: int) -> str:
    """Попередження перед відключенням (start/end - хвилини від сьогоднішньої 00:00)."""
    if minutes_left >= 55:
        head = "⏰ Через годину вимкнуть світло"
    else:
        head = f"⏰ Через {minutes_left} хв вимкнуть світло"
    return f"{head}\n🕒 {fmt_interval(start, end)} (за графіком)\n📍 {tuya_location()}"


def change_text(change: dict) -> str:
    """Повідомлення про зміну графіка або про те, що з'явився графік на завтра."""
    new = fmt_intervals(day_intervals(change["new"]))
    if change["kind"] == "published":
        if day_intervals(change["new"]):
            body = f"📅 З'явився графік відключень на завтра\n🕒 {new}"
        else:
            body = "📅 З'явився графік відключень на завтра\nВідключень не заплановано"
    else:
        old = fmt_intervals(day_intervals(change["old"]))
        body = (
            f"⚠️ Графік відключень {DAY_LABELS[change['day']]} змінився\n"
            f"Було: {old}\nСтало: {new}\nБудьте уважні"
        )
    return f"{body}\n📍 {tuya_location()}"


async def _send_to_all(bot, text: str) -> int:
    """Надсилає вторинне повідомлення всім, хто має сповіщення; повертає, скільком дійшло."""
    delivered = 0
    for user_id in await list_notify_user_ids():
        try:
            await send_secondary(bot, user_id, text, alert_keyboard())
            delivered += 1
        except TelegramForbiddenError:
            logger.info("Користувач %s заблокував бота", user_id)
        except TelegramAPIError:
            logger.warning(
                "Не вдалося надіслати попередження %s", user_id, exc_info=True
            )
    return delivered


async def notify_changes(bot, changes: list[dict]):
    """Повідомляє про зміни графіка, знайдені черговим знімком."""
    for change in changes:
        logger.info("Графік ДТЕК: %s (%s)", change["kind"], DAY_LABELS[change["day"]])
        await _send_to_all(bot, change_text(change))


def upcoming_outages(meta: dict | None, now: datetime):
    """Відключення, що ще не почались: [(початок, кінець, хв_початку, хв_кінця)].

    Хвилини відраховуються від сьогоднішньої 00:00, відключення на межі діб склеєні.
    Без графіка на сьогодні список порожній: попереджати за невідомими даними не можна.
    """
    by_date = slots_by_date(meta)
    today = by_date.get(now.date().isoformat())
    if today is None:
        return []
    tomorrow = by_date.get((now.date() + timedelta(days=1)).isoformat())
    midnight = datetime.combine(now.date(), dt_time(0, 0), tzinfo=KYIV)
    result = []
    for start, end in two_day_intervals(today, tomorrow):
        start_dt = midnight + timedelta(minutes=start)
        if start_dt > now:
            result.append((start_dt, midnight + timedelta(minutes=end), start, end))
    return result


async def check_warnings(bot, now: datetime | None = None) -> int:
    """Одна перевірка: надсилає попередження про відключення, що почнуться найближчим часом."""
    now = now or datetime.now(KYIV)
    warn_seconds = outage_warn_minutes() * 60
    sent = 0
    for start_dt, _, start, end in upcoming_outages(dtek_schedule.read_meta(), now):
        seconds_left = (start_dt - now).total_seconds()
        if seconds_left > warn_seconds:
            continue
        minutes_left = math.ceil(seconds_left / 60)
        if minutes_left < MIN_MINUTES_LEFT:
            continue
        # кожне відключення попереджається один раз (навіть після перезапуску бота)
        key = f"warn:{start_dt.isoformat(timespec='minutes')}"
        if not await claim_alert(key, now.isoformat()):
            continue
        await _send_to_all(bot, warning_text(minutes_left, start, end))
        sent += 1
    return sent


async def alerts_loop(bot):
    logger.info(
        "Попередження про відключення: за %s хв до початку (перевірка раз на %s с)",
        outage_warn_minutes(),
        CHECK_EVERY_SECONDS,
    )
    purged_on: date | None = None
    while True:
        try:
            now = datetime.now(KYIV)
            if purged_on != now.date():
                await purge_alerts((now - timedelta(days=KEEP_ALERTS_DAYS)).isoformat())
                purged_on = now.date()
            await check_warnings(bot, now)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Попередження про відключення: збій перевірки")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
