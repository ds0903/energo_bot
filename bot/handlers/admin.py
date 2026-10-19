import os

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, FSInputFile
from handlers.logic import list_admin_info, list_all_users
from handlers.menus import (ADM_ACTIVE, ADM_GUESTS, ADM_LIST, ADM_TEST,
                            ADM_USERS, admin_keyboard, alert_keyboard,
                            back_keyboard, standard_keyboard)
from handlers.standard import device_block, standard_screen
from monitor import notification_text, now_kyiv
from openpyxl import Workbook
from outages import change_text  # , warning_text (попередження вимкнено)
from ui import delete_quietly, send_panel

router = Router()

ADMIN_USERNAME = "ds0903"
DENIED_TEXT = "Доступ заборонено !"
ADMIN_TEXT = "🛠 Адмін-панель"

# callback -> (статус для list_admin_info, ім'я файлу, заголовок, скільки перших колонок пропустити)
EXPORTS = {
    ADM_ACTIVE: (
        "1",
        "all_user_active_ip.xlsx",
        [
            "ID",
            "User ID",
            "IP",
            "Description",
            "First Name",
            "Last Name",
            "Username",
            "Language Code",
            "Is Premium",
            "Is Active",
        ],
        0,
    ),
    ADM_USERS: (
        "2",
        "all_users.xlsx",
        [
            "id",
            "user_id",
            "ip",
            "description",
            "first_name",
            "last_name",
            "username",
            "language_code",
            "is_premium",
        ],
        0,
    ),
    ADM_GUESTS: (
        "3",
        "gosti.xlsx",
        [
            "user_id",
            "is_bot",
            "first_name",
            "last_name",
            "username",
            "language_code",
            "is_premium",
            "added_to_attachment_menu",
            "can_join_groups",
            "can_read_all_group_messages",
            "supports_inline_queries",
            "can_connect_to_business",
            "current_time",
        ],
        1,  # без першої колонки id
    ),
}


def is_admin(event: types.Message | types.CallbackQuery) -> bool:
    return event.from_user.username == ADMIN_USERNAME


async def send_xlsx(bot: Bot, chat_id: int, filename, header, rows):
    wb = Workbook()
    sheet = wb.active
    sheet.append(header)
    for row in rows:
        sheet.append(list(row))
    wb.save(filename)

    try:
        await bot.send_document(chat_id=chat_id, document=FSInputFile(filename))
    finally:
        os.remove(filename)


@router.message(Command("admin"))
@router.message(lambda message: message.text == "cmd_admin")
async def cmd_admin(message: types.Message, bot: Bot):
    await delete_quietly(bot, message.chat.id, message.message_id)
    user_id = message.from_user.id
    if not is_admin(message):
        await send_panel(bot, user_id, DENIED_TEXT, back_keyboard())
        return
    await send_panel(bot, user_id, ADMIN_TEXT, admin_keyboard())


def hours(*off):
    return ["off" if hour in off else "ok" for hour in range(24)]


@router.callback_query(F.data == ADM_TEST)
async def test_messages(callback: types.CallbackQuery, bot: Bot):
    """Зразки повідомлень бота: надсилаються лише адміну, нічого не міняється в базі чи в інших.

    Тексти будуються тим самим кодом, що й справжні сповіщення.
    """
    if not is_admin(callback):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return

    await callback.answer()
    user_id = callback.from_user.id
    now = now_kyiv()
    device = {"id": "preview", "name": "Тестовий пристрій", "online": True}
    await bot.send_message(user_id, "🧪 Приклади повідомлень (тест, бачите лише ви)")
    # основні повідомлення: світло зникло / з'явилось (їх замінює лише зміна стану світла)
    primary = (
        notification_text(False, now, "5 год 40 хв", device),
        notification_text(True, now, "3 год 25 хв", device),
    )
    for text in primary:
        await bot.send_message(user_id, text, reply_markup=standard_keyboard(True))

    # вторинні: про графік (нове замінює попереднє, є кнопка графіка)
    secondary = (
        # попередження «через годину вимкнуть світло» вимкнено:
        # warning_text(60, 12 * 60, 16 * 60),
        change_text(
            {
                "kind": "changed",
                "day": "today",
                "old": hours(13, 14, 15, 16),
                "new": hours(12, 13, 14, 15),
            }
        ),
        change_text(
            {
                "kind": "published",
                "day": "tomorrow",
                "old": None,
                "new": hours(10, 11, 18, 19, 20, 21),
            }
        ),
    )
    for text in secondary:
        await bot.send_message(user_id, text, reply_markup=alert_keyboard())
    # зразки панелі статусу: рядок про минулий стан з'являється після першої зміни світла
    for online, seconds in ((True, 3 * 3600 + 25 * 60), (False, 5 * 3600 + 40 * 60)):
        text = device_block({**device, "online": online}, False, seconds, now)
        await bot.send_message(user_id, text, reply_markup=standard_keyboard(True))
    # і поточний екран статусу такий, яким його бачить користувач
    text, markup = await standard_screen(user_id)
    await bot.send_message(user_id, text, reply_markup=markup)


def users_text(users) -> str:
    """Рядок на користувача: номер, юзернейм, коли підключився."""
    lines = []
    for number, (user_id, username, connected) in enumerate(users, 1):
        who = f"@{username}" if username else f"(без юзернейма, id {user_id})"
        when = (connected or "невідомо")[:19]  # без частки секунди
        lines.append(f"{number}. {who} {when}")
    return "\n".join(lines)


@router.callback_query(F.data == ADM_LIST)
async def users_list(callback: types.CallbackQuery, bot: Bot):
    if not is_admin(callback):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return

    users = await list_all_users()
    if not users:
        await callback.answer("Користувачів ще немає", show_alert=True)
        return

    await callback.answer("Файл формується")
    await bot.send_document(
        chat_id=callback.from_user.id,
        document=BufferedInputFile(users_text(users).encode("utf-8"), "users.txt"),
        caption=f"Усього користувачів: {len(users)}",
    )


@router.callback_query(F.data.in_(set(EXPORTS)))
async def export(callback: types.CallbackQuery, bot: Bot):
    if not is_admin(callback):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return

    await callback.answer("Файл формується")
    status, filename, header, skip = EXPORTS[callback.data]
    data = await list_admin_info(status=status)
    await send_xlsx(
        bot,
        callback.from_user.id,
        filename,
        header,
        (row[skip:] for row in data),
    )
