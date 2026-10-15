"""Знімок графіка відключень ДТЕК.

Справжній браузер (Playwright + Chromium) відкриває сторінку «Відсутня електроенергія?»,
вибирає населений пункт, вулицю й будинок із налаштувань і зберігає дві картинки: графік
«на сьогодні» і «на завтра». Робиться це раз на SCHEDULE_REFRESH_MINUTES, а користувачам
віддається вже готова картинка, тож сайт ДТЕК навантажує лише бот, а не кожен користувач.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from settings import (schedule_city, schedule_house, schedule_refresh_minutes,
                      schedule_street)

logger = logging.getLogger(__name__)

URL = "https://www.dtek-krem.com.ua/ua/shutdowns"
KYIV = ZoneInfo("Europe/Kyiv")
CACHE_DIR = Path(__file__).resolve().parent.parent / "schedule_cache"
META_FILE = CACHE_DIR / "meta.json"
DAYS = {"today": "today.png", "tomorrow": "tomorrow.png"}
BLOCK = ".discon-schedule-interact"
CAPTURE_TIMEOUT_SECONDS = 180
# після невдалої спроби пробуємо знову раніше, ніж за повний інтервал
RETRY_AFTER_FAILURE_MINUTES = 10

_lock = asyncio.Lock()


class ScheduleError(Exception):
    """Знімок зробити не вдалося (немає Playwright, сторінка не відкрилась, захист тощо)."""


def image_path(day: str) -> Path:
    return CACHE_DIR / DAYS[day]


def read_meta() -> dict | None:
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def get_snapshot(day: str):
    """(шлях до картинки, коли зроблено) або None, якщо знімка ще немає."""
    meta = read_meta()
    path = image_path(day)
    if not meta or not path.exists():
        return None
    try:
        updated = datetime.fromisoformat(meta["updated"])
    except (KeyError, ValueError):
        return None
    return path, updated, meta.get("site_updated")


def _write_atomically(path: Path, data: bytes):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _first_word(text: str) -> str:
    return text.split()[0] if text.split() else text


async def _close_popups(page):
    # інформаційне вікно «Шановні клієнти!» (якщо показане) закриваємо кнопкою
    close = page.locator(".m-attention__close")
    try:
        if await close.first.is_visible():
            await close.first.click(timeout=3000)
    except Exception:
        pass


async def _pick(
    page, field_id: str, query: str, wanted: str, exact: bool
) -> str | None:
    """Вводить текст у поле й вибирає підказку зі списку. Повертає код черги (напр. GPV2.2).

    exact=False: підказка має містити wanted; exact=True: підказка має дорівнювати wanted,
    а якщо такої немає, береться перша (так «6» вибирає будинок «6», а за відсутності
    потрібного будинку підійде будь-який: графік залежить лише від черги вулиці).
    """
    field = page.locator(f"#discon_form #{field_id}")
    # id на сторінці дублюються (є ще приховані форми), тому підказки беремо
    # відносно самого поля, як сусідній блок autocomplete-items
    items = field.locator(
        "xpath=following-sibling::div[contains(@class,'autocomplete-items')]/div"
    )
    # логіка автодоповнення підключається скриптом сторінки не одразу, тож якщо підказок
    # немає, очищаємо поле й вводимо знову (до трьох спроб)
    for attempt in range(3):
        await field.click()
        if attempt:
            # очищаємо лише при повторі: порожнє поле після введення дає червону помилку
            await field.fill("")
            await page.wait_for_timeout(300)
        await field.press_sequentially(query, delay=90)
        try:
            await items.first.wait_for(state="visible", timeout=8000)
            break
        except Exception:
            if attempt == 2:
                raise ScheduleError(
                    f"Для поля «{field_id}» не з'явились підказки після введення «{query}»"
                )
            await page.wait_for_timeout(1500)

    wanted_norm = wanted.strip().lower()
    labels = []
    chosen = None
    for index in range(await items.count()):
        item = items.nth(index)
        hidden = item.locator("input[type=hidden]")
        value = (
            await hidden.first.get_attribute("value") if await hidden.count() else None
        )
        label = (value or await item.inner_text()).strip()
        labels.append(label)
        label_norm = label.lower()
        matches = (label_norm == wanted_norm) if exact else (wanted_norm in label_norm)
        if matches and chosen is None:
            chosen = index
    if chosen is None and exact and labels:
        chosen = 0  # потрібного будинку немає: беремо першу підказку
    if chosen is None:
        raise ScheduleError(f"У підказках поля «{field_id}» немає «{wanted}»: {labels}")

    item = items.nth(chosen)
    hidden = item.locator("input[type=hidden]")
    group = (
        await hidden.first.get_attribute("data-key-group")
        if await hidden.count()
        else None
    )
    await item.click()
    return group


async def _capture() -> dict:
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise ScheduleError(
            "Не встановлено playwright: pip install playwright && playwright install chromium"
        ) from error

    city, street, house = schedule_city(), schedule_street(), schedule_house()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage"]
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1100, "height": 900},
                locale="uk-UA",
                timezone_id="Europe/Kyiv",
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            try:
                await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                await page.locator("#discon_form #city").wait_for(
                    state="visible", timeout=45000
                )
            except PlaywrightTimeout as error:
                title = await page.title() if not page.is_closed() else ""
                raise ScheduleError(
                    f"Сторінка ДТЕК не показала форму адреси (захист від ботів або "
                    f"зміна сторінки), заголовок: {title!r}"
                ) from error

            try:
                # сторінка спершу віддає голий HTML (а захист може ще й перезавантажити її),
                # тож чекаємо, поки справді підключаться стилі та скрипт автодоповнення
                await page.wait_for_function(
                    """() => document.readyState === 'complete' && !!window.jQuery
                        && document.styleSheets.length >= 2""",
                    timeout=60000,
                )
            except PlaywrightTimeout as error:
                raise ScheduleError(
                    "Сторінка ДТЕК не догрузила стилі й скрипти (можливо, блокування)"
                ) from error
            await page.wait_for_timeout(1500)
            await _close_popups(page)

            house_digits = re.match(r"\d+", house)
            try:
                await _pick(page, "city", _first_word(city), city, exact=False)
                await _pick(page, "street", _first_word(street), street, exact=False)
                group = await _pick(
                    page,
                    "house_num",
                    house_digits.group(0) if house_digits else house,
                    house,
                    exact=True,
                )
                await page.wait_for_selector(
                    "#discon-fact .discon-fact-table.active table",
                    state="visible",
                    timeout=45000,
                )
            except Exception:
                # знімок сторінки в момент помилки допомагає зрозуміти причину
                try:
                    await page.screenshot(path=str(CACHE_DIR / "last_error.png"))
                except Exception:
                    pass
                raise
            # плаваючі елементи (кнопка чату, шапка) не мають налазити на знімок
            await page.evaluate("""() => {
                    const target = document.querySelector('.discon-schedule-interact');
                    for (const el of document.querySelectorAll('body *')) {
                        const pos = getComputedStyle(el).position;
                        if ((pos === 'fixed' || pos === 'sticky') && !el.contains(target) && !target.contains(el)) {
                            el.style.setProperty('display', 'none', 'important');
                        }
                    }
                    // підписи-помилки валідації форми на знімку зайві
                    for (const el of target.querySelectorAll('.span-error')) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                }""")

            block = page.locator(BLOCK)
            site_updated = None
            update_label = page.locator(
                "#discon-fact .discon-fact-table.active .update"
            )
            if await update_label.count():
                site_updated = (await update_label.first.inner_text()).strip()

            images = {"today": await block.screenshot(type="png")}

            tabs = page.locator("#discon-fact .dates .date")
            if await tabs.count() > 1:
                await tabs.nth(1).click()
                await page.wait_for_selector(
                    '#discon-fact .discon-fact-table[tab="1"].active table',
                    state="visible",
                    timeout=20000,
                )
                images["tomorrow"] = await block.screenshot(type="png")
        finally:
            await browser.close()

    if "tomorrow" not in images:
        raise ScheduleError("На сторінці немає вкладки «на завтра»")
    for day, data in images.items():
        _write_atomically(image_path(day), data)
    meta = {
        "updated": datetime.now(KYIV).isoformat(),
        "site_updated": site_updated,
        "address": f"{city}, {street}, {house}",
        "group": (group or "").replace("GPV", ""),
    }
    _write_atomically(META_FILE, json.dumps(meta, ensure_ascii=False).encode("utf-8"))
    return meta


def _capture_in_own_loop() -> dict:
    """Виконує знімок в окремому потоці зі своїм циклом подій.

    Playwright запускає браузер окремим процесом, а на Windows це вміє лише
    ProactorEventLoop. Бібліотека aioping при імпорті перемикає глобальний цикл на
    «селекторний» (їй так потрібно), тож у цьому потоці цикл створюємо явно, незалежно
    від того, який цикл у решти бота. На Linux це звичайний новий цикл.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            asyncio.wait_for(_capture(), timeout=CAPTURE_TIMEOUT_SECONDS)
        )
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()


async def refresh_schedule() -> bool:
    """Робить новий знімок. Невдача лише логується, а попередні картинки лишаються."""
    async with _lock:
        started = time.monotonic()
        try:
            meta = await asyncio.to_thread(_capture_in_own_loop)
        except asyncio.CancelledError:
            raise
        except ScheduleError as error:
            logger.warning("Графік ДТЕК: знімок не зроблено: %s", error)
            return False
        except TimeoutError:
            logger.warning(
                "Графік ДТЕК: знімок не вкладається в %s с, пропускаю",
                CAPTURE_TIMEOUT_SECONDS,
            )
            return False
        except Exception:
            logger.warning("Графік ДТЕК: збій під час знімка", exc_info=True)
            return False
        logger.info(
            "Графік ДТЕК: знімок оновлено за %.0f с (на сайті: %s)",
            time.monotonic() - started,
            meta.get("site_updated"),
        )
        return True


def seconds_until_next_refresh() -> float:
    """Скільки чекати до наступного знімка (з урахуванням свіжості картинок на диску)."""
    interval = schedule_refresh_minutes() * 60
    snapshot = get_snapshot("today")
    if snapshot is None:
        return 0
    age = (datetime.now(KYIV) - snapshot[1]).total_seconds()
    return max(0.0, interval - age)


async def schedule_loop():
    logger.info(
        "Графік ДТЕК: знімок раз на %s хв (%s, %s, %s)",
        schedule_refresh_minutes(),
        schedule_city(),
        schedule_street(),
        schedule_house(),
    )
    # після перезапуску бота не знімаємо наново, якщо картинки на диску ще свіжі
    await asyncio.sleep(seconds_until_next_refresh())
    while True:
        try:
            ok = await refresh_schedule()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Графік ДТЕК: збій циклу")
            ok = False
        minutes = (
            schedule_refresh_minutes()
            if ok
            else min(schedule_refresh_minutes(), RETRY_AFTER_FAILURE_MINUTES)
        )
        await asyncio.sleep(minutes * 60)
