"""Знімок графіка відключень ДТЕК.

Справжній браузер (Playwright + Chromium) відкриває сторінку «Відсутня електроенергія?»,
вибирає населений пункт, вулицю й будинок із налаштувань і зберігає дві картинки: графік
«на сьогодні» і «на завтра». Робиться це раз на півгодини (settings.schedule_refresh_minutes), а користувачам
віддається вже готова картинка, тож сайт ДТЕК навантажує лише бот, а не кожен користувач.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime
from datetime import time as dt_time
from datetime import timedelta
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from outage_data import detect_changes, slots_from_cells
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
# знімок застарів, якщо новішого не вдавалось зробити так довго (користувач бачить попередження)
STALE_AFTER_MINUTES = 180
# спроб за один цикл (з паузою між ними) і після скількох невдалих циклів підряд писати ERROR
CAPTURE_ATTEMPTS = 2
RETRY_PAUSE_SECONDS = 20
ERROR_AFTER_FAILURES = 3
# додатковий знімок одразу після півночі, щоб «на сьогодні» не лишалось із вчорашньою датою
MIDNIGHT_CAPTURE = dt_time(0, 5)
# у таблиці графіка: клітинка-підпис + 24 години
TABLE_COLUMNS = 25
UPDATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}")

_lock = asyncio.Lock()
_failures = 0  # невдалих циклів знімка підряд
_pending_changes: list[dict] = []  # зміни графіка, про які ще не повідомили

# зчитуємо зі сторінки лише те, що потрібно для перевірки (дати вкладок, розміри таблиць)
PAGE_DATA_JS = """() => {
  const root = document.querySelector('#discon-fact');
  const dates = [...root.querySelectorAll('.dates .date span[rel="date"]')]
      .map(e => e.textContent.trim());
  const tables = [...root.querySelectorAll('.discon-fact-table')].map(t => {
    const rows = [...t.querySelectorAll('table tr')];
    const update = t.querySelector('.update');
    return {
      head: rows[0] ? rows[0].children.length : 0,
      body: rows[1] ? rows[1].children.length : 0,
      update: update ? update.textContent.trim() : null,
      // класи 24 клітинок рядка графіка (без першої клітинки-підпису)
      cells: rows[1] ? [...rows[1].children].slice(1).map(c => c.className || '') : [],
    };
  });
  return { dates, tables };
}"""


class ScheduleError(Exception):
    """Знімок зробити не вдалося (немає Playwright, сторінка не відкрилась, захист тощо)."""


class ScheduleSetupError(ScheduleError):
    """Проблема налаштування (не встановлено Playwright): повтор нічого не змінить."""


def image_path(day: str) -> Path:
    return CACHE_DIR / DAYS[day]


def read_meta() -> dict | None:
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Pick(NamedTuple):
    path: Path
    updated: datetime  # коли бот зробив знімок
    site_updated: str | None  # дата оновлення, яку показує сам графік ДТЕК
    stale: bool  # знімок давно не оновлювався


# чому графіка немає: "missing" - знімка ще не було, "unpublished" - ДТЕК не опублікував
# графік на завтра, "wrong_day" - збережені картинки не на ту дату, що потрібна зараз
MISSING, UNPUBLISHED, WRONG_DAY = "missing", "unpublished", "wrong_day"


def pick_snapshot(
    day: str, now: datetime | None = None
) -> tuple[Pick | None, str | None]:
    """Картинка графіка саме на потрібну дату: (Pick, None) або (None, причина).

    Дату беремо з вкладок самої сторінки ДТЕК, тож вчорашній графік ніколи не видається
    за сьогоднішній. Після півночі «сьогодні» береться з картинки, що була «завтра».
    """
    now = now or datetime.now(KYIV)
    meta = read_meta()
    if not meta:
        return None, MISSING
    try:
        updated = datetime.fromisoformat(meta["updated"])
    except (KeyError, ValueError):
        return None, MISSING

    stale = now - updated > timedelta(minutes=STALE_AFTER_MINUTES)
    dates = meta.get("dates") or {}
    if not dates:
        # знімок без записаних дат (стара версія): віримо назві файла
        path = image_path(day)
        if path.exists():
            return Pick(path, updated, meta.get("site_updated"), stale), None
        return None, MISSING

    wanted = (now.date() + timedelta(days=0 if day == "today" else 1)).isoformat()
    for source in ("today", "tomorrow"):
        path = image_path(source)
        if dates.get(source) == wanted and path.exists():
            return Pick(path, updated, meta.get("site_updated"), stale), None

    if day == "tomorrow" and dates.get("today") == now.date().isoformat():
        return (
            None,
            UNPUBLISHED,
        )  # сьогоднішній знімок свіжий, а завтрашнього графіка ще немає
    return None, WRONG_DAY


def _table_ok(table: dict) -> bool:
    return table.get("head") == TABLE_COLUMNS and table.get("body") == TABLE_COLUMNS


def _validate_page_data(data: dict, today: date) -> bool:
    """Перевіряє, що графік справді завантажився й він на сьогоднішню дату.

    Кидає ScheduleError, якщо ні (тоді попередній знімок лишається). Повертає, чи є вже
    готовий графік на завтра: ДТЕК публікує його лише ввечері.
    """
    try:
        dates = [datetime.strptime(text, "%d.%m.%y").date() for text in data["dates"]]
    except (KeyError, ValueError) as error:
        raise ScheduleError(
            f"Не вдалося прочитати дати вкладок: {data.get('dates')}"
        ) from error
    tables = data.get("tables") or []
    if not dates or not tables:
        raise ScheduleError("На сторінці немає графіка відключень")
    if dates[0] != today:
        raise ScheduleError(f"Сайт показує графік на {dates[0]}, а сьогодні {today}")
    first = tables[0]
    if not _table_ok(first):
        raise ScheduleError(
            f"Таблиця графіка неповна: {first.get('head')}/{first.get('body')} "
            f"клітинок замість {TABLE_COLUMNS}"
        )
    if not UPDATE_RE.fullmatch(first.get("update") or ""):
        raise ScheduleError("У графіку немає дати останнього оновлення")
    return (
        len(dates) > 1
        and len(tables) > 1
        and dates[1] == today + timedelta(days=1)
        and _table_ok(tables[1])
    )


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
        raise ScheduleSetupError(
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
                # таблиця з'явилась, але чи справді в ній дані на сьогодні?
                today = datetime.now(KYIV).date()
                page_data = await page.evaluate(PAGE_DATA_JS)
                has_tomorrow = _validate_page_data(page_data, today)
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

            # графік на завтра ДТЕК публікує лише ввечері: його відсутність не є помилкою
            if has_tomorrow:
                try:
                    await page.locator("#discon-fact .dates .date").nth(1).click()
                    await page.wait_for_selector(
                        '#discon-fact .discon-fact-table[tab="1"].active table',
                        state="visible",
                        timeout=20000,
                    )
                    images["tomorrow"] = await block.screenshot(type="png")
                except PlaywrightTimeout:
                    logger.info(
                        "Графік ДТЕК: вкладка «на завтра» не відкрилась, пропускаю"
                    )
        finally:
            await browser.close()

    for day, data in images.items():
        _write_atomically(image_path(day), data)
    if "tomorrow" not in images:
        # стара картинка «на завтра» тепер була б на іншу дату
        image_path("tomorrow").unlink(missing_ok=True)
    # графік по годинах (з класів клітинок): з нього бот знає, коли вимкнуть світло
    slots = {
        "today": slots_from_cells(page_data["tables"][0].get("cells")),
        "tomorrow": (
            slots_from_cells(page_data["tables"][1].get("cells"))
            if "tomorrow" in images
            else None
        ),
    }
    for day in ("today", "tomorrow"):
        if (day == "today" or day in images) and slots[day] is None:
            logger.warning(
                "Графік ДТЕК: не вдалося розібрати клітинки таблиці (%s): "
                "попередження про відключення за цей день не надсилатимуться",
                day,
            )
    meta = {
        "updated": datetime.now(KYIV).isoformat(),
        "site_updated": site_updated,
        "address": f"{city}, {street}, {house}",
        "group": (group or "").replace("GPV", ""),
        # на які дати ці картинки (за вкладками самої сторінки)
        "dates": {
            "today": today.isoformat(),
            "tomorrow": (
                (today + timedelta(days=1)).isoformat()
                if "tomorrow" in images
                else None
            ),
        },
        "slots": slots,
    }
    # що змінилось порівняно з попереднім знімком (до того, як перезапишемо метадані)
    changes = detect_changes(read_meta(), meta)
    _write_atomically(META_FILE, json.dumps(meta, ensure_ascii=False).encode("utf-8"))
    return {**meta, "changes": changes}


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
    """Робить новий знімок. Невдача лише логується, а попередні картинки лишаються.

    У межах одного циклу робиться кілька спроб (сайт міг тимчасово не відкритись). Після
    кількох невдалих циклів підряд у лог іде ERROR, а користувачі бачать попередження, що
    знімок застарів.
    """
    global _failures
    async with _lock:
        started = time.monotonic()
        meta = None
        for attempt in range(1, CAPTURE_ATTEMPTS + 1):
            try:
                meta = await asyncio.to_thread(_capture_in_own_loop)
                break
            except asyncio.CancelledError:
                raise
            except ScheduleSetupError as error:
                logger.error("Графік ДТЕК: %s", error)
                return False  # повтор нічого не змінить
            except ScheduleError as error:
                logger.warning(
                    "Графік ДТЕК: знімок не зроблено (спроба %s з %s): %s",
                    attempt,
                    CAPTURE_ATTEMPTS,
                    error,
                )
            except TimeoutError:
                logger.warning(
                    "Графік ДТЕК: знімок не вкладається в %s с (спроба %s з %s)",
                    CAPTURE_TIMEOUT_SECONDS,
                    attempt,
                    CAPTURE_ATTEMPTS,
                )
            except Exception:
                logger.warning(
                    "Графік ДТЕК: збій під час знімка (спроба %s з %s)",
                    attempt,
                    CAPTURE_ATTEMPTS,
                    exc_info=True,
                )
            if attempt < CAPTURE_ATTEMPTS:
                await asyncio.sleep(RETRY_PAUSE_SECONDS)

        if meta is None:
            _failures += 1
            logger.log(
                logging.ERROR if _failures >= ERROR_AFTER_FAILURES else logging.WARNING,
                "Графік ДТЕК: не вдалося оновити знімок (циклів підряд: %s). "
                "Користувачі бачать попередній знімок із позначкою, що він застарів",
                _failures,
            )
            return False

        _failures = 0
        _pending_changes.extend(meta.get("changes") or [])
        logger.info(
            "Графік ДТЕК: знімок оновлено за %.0f с (на сайті: %s, є «на завтра»: %s, змін графіка: %s)",
            time.monotonic() - started,
            meta.get("site_updated"),
            bool(meta.get("dates", {}).get("tomorrow")),
            len(meta.get("changes") or []),
        )
        return True


def take_changes() -> list[dict]:
    """Зміни графіка, знайдені останніми знімками (і забуває їх: кожна зміна лише раз)."""
    changes = list(_pending_changes)
    _pending_changes.clear()
    return changes


def seconds_until_midnight_capture(now: datetime | None = None) -> float:
    """Скільки секунд до найближчих 00:05 за Києвом."""
    now = now or datetime.now(KYIV)
    target = datetime.combine(now.date(), MIDNIGHT_CAPTURE, tzinfo=KYIV)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def next_interval_minutes(ok: bool, now: datetime | None = None) -> int:
    """Через скільки хвилин робити наступний знімок.

    Завжди рівно один інтервал (30 хв), у будь-яку пору доби, без прискорень. Єдині
    виключення: після невдалого знімка пробуємо раніше, і один знімок о 00:05
    (див. seconds_until_midnight_capture).
    """
    interval = schedule_refresh_minutes()
    if not ok:
        return min(interval, RETRY_AFTER_FAILURE_MINUTES)
    return interval


def seconds_until_next_refresh() -> float:
    """Скільки чекати до наступного знімка (з урахуванням свіжості картинок на диску)."""
    interval = next_interval_minutes(True) * 60
    pick, _ = pick_snapshot("today")
    if pick is None:
        return 0  # знімка немає або він не на сьогоднішню дату
    age = (datetime.now(KYIV) - pick.updated).total_seconds()
    return max(0.0, interval - age)


async def schedule_loop(on_changes=None):
    """Раз на інтервал робить знімок; on_changes(список змін) викликається, коли
    графік на сьогодні чи завтра змінився або з'явився графік на завтра."""
    logger.info(
        "Графік ДТЕК: знімок раз на %s хв (%s, %s, %s)",
        schedule_refresh_minutes(),
        schedule_city(),
        schedule_street(),
        schedule_house(),
    )
    # після перезапуску бота не знімаємо наново, якщо картинки на диску ще свіжі
    await asyncio.sleep(
        min(seconds_until_next_refresh(), seconds_until_midnight_capture())
    )
    while True:
        try:
            ok = await refresh_schedule()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Графік ДТЕК: збій циклу")
            ok = False
        changes = take_changes()
        if changes and on_changes is not None:
            try:
                await on_changes(changes)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Графік ДТЕК: не вдалося повідомити про зміну графіка")
        minutes = next_interval_minutes(ok)
        # додатковий знімок одразу після півночі: нова дата й, можливо, нова вкладка
        await asyncio.sleep(min(minutes * 60, seconds_until_midnight_capture()))
