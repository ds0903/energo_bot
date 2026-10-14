import os

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from handlers.logic import list_admin_info
from handlers.menus import (ADM_ACTIVE, ADM_GUESTS, ADM_USERS, admin_keyboard,
                            back_keyboard)
from openpyxl import Workbook
from ui import delete_quietly, send_panel

router = Router()

ADMIN_USERNAME = "ds0903"
DENIED_TEXT = "Доступ заборонено !"

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
    await send_panel(bot, user_id, "Ти потрапив в секретне меню", admin_keyboard())


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
