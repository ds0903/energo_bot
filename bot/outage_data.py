"""Дані графіка відключень: розбір клітинок таблиці ДТЕК, інтервали, виявлення змін.

Лише чиста логіка (без мережі, браузера й Telegram), тож її легко перевіряти тестами.

Таблиця ДТЕК має 24 клітинки (по одній на годину). Клас клітинки каже, що з світлом:
  cell-non-scheduled  - світло є
  cell-scheduled      - світла немає всю годину
  cell-first-half     - світла немає перші 30 хвилин
  cell-second-half    - світла немає другі 30 хвилин
У метаданих стан зберігається словами: ok / off / first / second.
"""

CLASS_TO_STATE = {
    "cell-non-scheduled": "ok",
    "cell-scheduled": "off",
    "cell-first-half": "first",
    "cell-second-half": "second",
}
# відключена частина години: (з якої хвилини, до якої)
OFF_PART = {"off": (0, 60), "first": (0, 30), "second": (30, 60)}
HOURS = 24
DAY_MINUTES = 24 * 60


def slots_from_cells(cells) -> list[str] | None:
    """24 стани з класів клітинок рядка таблиці (без першої клітинки-підпису).

    Повертає None, якщо клітинок не 24 або є невідомий клас: краще не знати графіка,
    ніж попередити людину за хибними даними.
    """
    if not isinstance(cells, list) or len(cells) != HOURS:
        return None
    slots = []
    for class_name in cells:
        states = {
            CLASS_TO_STATE[token]
            for token in str(class_name or "").split()
            if token in CLASS_TO_STATE
        }
        if len(states) != 1:
            return None
        slots.append(states.pop())
    return slots


def valid_slots(slots) -> bool:
    return (
        isinstance(slots, list)
        and len(slots) == HOURS
        and all(state in ("ok", "off", "first", "second") for state in slots)
    )


def _raw_intervals(slots: list[str], offset: int = 0) -> list[tuple[int, int]]:
    result = []
    for hour, state in enumerate(slots):
        if state in OFF_PART:
            start, end = OFF_PART[state]
            result.append((offset + hour * 60 + start, offset + hour * 60 + end))
    return result


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Склеює інтервали, що торкаються (напр. 12-13 і 13-14 дають 12:00-14:00)."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def day_intervals(slots: list[str]) -> list[tuple[int, int]]:
    """Відключення одного дня в хвилинах від 00:00."""
    return merge(_raw_intervals(slots))


def two_day_intervals(
    today: list[str] | None, tomorrow: list[str] | None
) -> list[tuple[int, int]]:
    """Відключення сьогодні й завтра як одна лінія часу (хвилини від сьогоднішньої 00:00).

    Так відключення 22:00-24:00 і 00:00-02:00 стає одним: 22:00-02:00.
    """
    raw = _raw_intervals(today) if today else []
    if tomorrow:
        raw += _raw_intervals(tomorrow, DAY_MINUTES)
    return merge(raw)


def fmt_minute(minute: int, is_end: bool = False) -> str:
    """HH:MM для хвилини від початку відліку; кінець рівно опівночі пишемо як 24:00."""
    if is_end and minute == DAY_MINUTES:
        return "24:00"
    minute %= DAY_MINUTES
    return f"{minute // 60:02d}:{minute % 60:02d}"


def fmt_interval(start: int, end: int) -> str:
    return f"{fmt_minute(start)}–{fmt_minute(end, is_end=True)}"


def fmt_intervals(intervals: list[tuple[int, int]]) -> str:
    if not intervals:
        return "відключень немає"
    return ", ".join(fmt_interval(start, end) for start, end in intervals)


def slots_by_date(meta: dict | None) -> dict[str, list[str]]:
    """{дата ISO: 24 стани} із метаданих знімка (лише коректні записи)."""
    if not meta:
        return {}
    dates, slots = meta.get("dates") or {}, meta.get("slots") or {}
    result = {}
    for day in ("today", "tomorrow"):
        iso, value = dates.get(day), slots.get(day)
        if iso and valid_slots(value):
            result[iso] = value
    return result


def detect_changes(old_meta: dict | None, new_meta: dict) -> list[dict]:
    """Що змінилось у графіку між двома знімками.

    kind="changed"   - графік на цю дату відрізняється від того, що бот бачив раніше;
    kind="published" - з'явився графік на завтра, якого раніше не було.
    Без попереднього знімка (перший запуск) нічого не повідомляємо: порівнювати ні з чим.
    """
    old = slots_by_date(old_meta)
    if not old_meta:
        return []
    new = slots_by_date(new_meta)
    dates = new_meta.get("dates") or {}
    changes = []
    for day in ("today", "tomorrow"):
        iso = dates.get(day)
        if not iso or iso not in new:
            continue
        if iso in old:
            if old[iso] != new[iso]:
                changes.append(
                    {"kind": "changed", "day": day, "old": old[iso], "new": new[iso]}
                )
        elif day == "tomorrow":
            changes.append(
                {"kind": "published", "day": day, "old": None, "new": new[iso]}
            )
    return changes
