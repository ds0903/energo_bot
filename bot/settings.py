"""Налаштування з .env. Читаються під час роботи, бо .env підвантажується в bot.py."""

import os

DEFAULT_LOCATION = "Богдана Хмельницького 67а"


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name) or default))
    except ValueError:
        return default


def ip_check_minutes() -> int:
    """Як часто пінгувати IP-адреси в розширеному режимі (N хвилин)."""
    return env_int("IP_CHECK_MINUTES", 10)


def tuya_location() -> str:
    """Адреса, за якою стежить стандартний режим."""
    return (os.getenv("TUYA_LOCATION") or "").strip() or DEFAULT_LOCATION


def tuya_device_ids() -> set[str]:
    """Необов'язковий фільтр: стежити лише за цими пристроями (TUYA_DEVICE_ID через кому)."""
    raw = os.getenv("TUYA_DEVICE_ID") or ""
    return {part.strip() for part in raw.split(",") if part.strip()}
