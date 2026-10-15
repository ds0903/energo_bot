"""Налаштування з .env. Читаються під час роботи, бо .env підвантажується в bot.py."""

import os

DEFAULT_LOCATION = "Богдана Хмельницького 67а"


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name) or default))
    except ValueError:
        return default


def extended_mode_enabled() -> bool:
    """Чи доступний розширений режим (моніторинг IP). Код збережено, але за замовчуванням вимкнено."""
    return (os.getenv("EXTENDED_MODE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ip_check_minutes() -> int:
    """Як часто пінгувати IP-адреси в розширеному режимі (N хвилин)."""
    return env_int("IP_CHECK_MINUTES", 10)


def tuya_location() -> str:
    """Адреса, за якою стежить стандартний режим."""
    return (os.getenv("TUYA_LOCATION") or "").strip() or DEFAULT_LOCATION


def tuya_push_enabled() -> bool:
    """Чи слухати push-події Tuya. За замовчуванням вимкнено: для цього проєкту Tuya
    подій не надсилає, тож канал лише витрачав би запити на оновлення конфігу."""
    return (os.getenv("TUYA_PUSH") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def schedule_enabled() -> bool:
    """Чи показувати графік відключень ДТЕК (SCHEDULE_ENABLED=1; потрібен playwright)."""
    return (os.getenv("SCHEDULE_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def schedule_refresh_minutes() -> int:
    """Як часто робити новий знімок графіка (хвилини)."""
    return env_int("SCHEDULE_REFRESH_MINUTES", 60)


def schedule_city() -> str:
    return (os.getenv("SCHEDULE_CITY") or "").strip() or "Боярка"


def schedule_street() -> str:
    return (os.getenv("SCHEDULE_STREET") or "").strip() or "Хмельницького Богдана"


def schedule_house() -> str:
    # будь-який номер: графік залежить від черги вулиці, а не від конкретного будинку
    return (os.getenv("SCHEDULE_HOUSE") or "").strip() or "6"


def refresh_password() -> str:
    """Пароль команди /refresh (REFRESH_PASSWORD у .env). Порожній - команда вимкнена."""
    return (os.getenv("REFRESH_PASSWORD") or "").strip()


def push_log_raw() -> bool:
    """Чи писати в лог сирий JSON кожного push-повідомлення (TUYA_PUSH_LOG_RAW=0 вимикає)."""
    return (os.getenv("TUYA_PUSH_LOG_RAW") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def tuya_device_ids() -> set[str]:
    """Необов'язковий фільтр: стежити лише за цими пристроями (TUYA_DEVICE_ID через кому)."""
    raw = os.getenv("TUYA_DEVICE_ID") or ""
    return {part.strip() for part in raw.split(",") if part.strip()}
