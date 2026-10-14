"""Тексти та інлайн-клавіатури бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from settings import extended_mode_enabled, ip_check_minutes, tuya_location

# callback_data кнопок
MENU_MAIN = "menu:main"
CB_MODE_CHOOSE = "mode:choose"
CB_MODE_STANDARD = "mode:standard"
CB_MODE_EXTENDED = "mode:extended"
STD_NOTIFY_ON = "std:notify:on"
STD_NOTIFY_OFF = "std:notify:off"
EXT_MENU = "ext:menu"
EXT_IPS = "ext:ips"
EXT_ADD = "ext:add"
EXT_DELETE = "ext:del"
EXT_ON = "ext:on"
EXT_OFF = "ext:off"
EXT_HELP = "ext:help"
ADM_ACTIVE = "adm:active"
ADM_USERS = "adm:users"
ADM_GUESTS = "adm:guests"

VERSION_TEXT = (
    "v1.0.4. При виявленні помилок напишіть, будь ласка, розробнику @ds0903.\n\n"
    "Список змін:\nВирішена проблема із зависанням бота при додаванні опису до IP-адреси.\n"
    "Виправленна помилка при видаленні IP-адреси.\nВиправлені синтаксичні помилки.\n\n"
    "Дата виходу оновлення 22.07.2024"
)

# parse_mode="HTML": номер картки можна скопіювати дотиком
HELP_TEXT = (
    "Повна інструкція до телеграм-бота знаходиться за посиланням https://t.me/energo_bot_info\n\n"
    "Ви можете підтримати проект донатом; це не обов'язково, але бот працює на сервері не безкоштовно.\n\n"
    "Monobank: <code>5375.4141.2663.2131</code>\n\n"
    "Розробка телеграм-ботів для вашого бізнесу під ключ @ds0903"
)


def mode_choice_text() -> str:
    return (
        "Оберіть режим роботи бота:\n\n"
        f"🏠 Стандартний — моніторинг світла за адресою {tuya_location()}\n\n"
        "🛠 Розширений — моніторинг IP-адрес (роутер, камера тощо): "
        f"бот пінгує їх кожні {ip_check_minutes()} хв.\n\n"
        "Режим можна змінити в будь-який момент."
    )


def _keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def mode_choice_keyboard(can_go_back: bool = False):
    rows = [
        [("🏠 Стандартний режим", CB_MODE_STANDARD)],
        [("🛠 Розширений режим", CB_MODE_EXTENDED)],
    ]
    if can_go_back:
        rows.append([("◀️ Назад", MENU_MAIN)])
    return _keyboard(rows)


def standard_keyboard(notifications_on: bool):
    if notifications_on:
        notify = ("🔕 Вимкнути сповіщення", STD_NOTIFY_OFF)
    else:
        notify = ("🔔 Увімкнути сповіщення", STD_NOTIFY_ON)
    rows = [[notify]]
    if extended_mode_enabled():
        # поки розширений режим вимкнено, змінювати режим немає на що
        rows.append([("⚙️ Змінити режим", CB_MODE_CHOOSE)])
    return _keyboard(rows)


def extended_keyboard():
    return _keyboard(
        [
            [("▶️ Увімкнути бота", EXT_ON), ("⏹ Вимкнути бота", EXT_OFF)],
            [("🌐 Мої IP-адреси", EXT_IPS), ("❓ Допомога", EXT_HELP)],
            [("⚙️ Змінити режим", CB_MODE_CHOOSE)],
        ]
    )


def ips_keyboard():
    return _keyboard(
        [
            [("➕ Додати IP", EXT_ADD), ("🗑 Видалити IP", EXT_DELETE)],
            [("◀️ Назад", EXT_MENU)],
        ]
    )


def back_keyboard(data: str = MENU_MAIN):
    return _keyboard([[("◀️ Назад", data)]])


def cancel_keyboard():
    return _keyboard([[("✖️ Скасувати", EXT_IPS)]])


def pick_keyboard(prefix: str, items, back_data: str = EXT_MENU):
    """По кнопці на кожен елемент (id, підпис); callback_data: "<prefix>:<id>"."""
    rows = [[(label, f"{prefix}:{item_id}")] for item_id, label in items]
    rows.append([("◀️ Назад", back_data)])
    return _keyboard(rows)


def admin_keyboard():
    return _keyboard(
        [
            [("📊 Всі активні ip користувачів", ADM_ACTIVE)],
            [("👥 Всі користувачі в базі", ADM_USERS)],
            [("👀 Відвідувачі", ADM_GUESTS)],
            [("◀️ Назад", MENU_MAIN)],
        ]
    )
