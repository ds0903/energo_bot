import os

from aiogram import Router, types
from aiogram.types import FSInputFile, KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import list_admin_info
from openpyxl import Workbook

router = Router()

ADMIN_USERNAME = "ds0903"


def is_admin(message: types.Message) -> bool:
    return message.from_user.username == ADMIN_USERNAME


async def send_xlsx(message: types.Message, filename, header, rows):
    wb = Workbook()
    sheet = wb.active
    sheet.append(header)
    for row in rows:
        sheet.append(list(row))
    wb.save(filename)

    try:
        await message.answer_document(FSInputFile(filename))
    finally:
        os.remove(filename)


@router.message(lambda message: message.text == "cmd_admin")
async def cmd_admin(message: types.Message):
    if not is_admin(message):
        await message.answer("Доступ заборонено !")
        return

    kb = [
        [KeyboardButton(text="Всі активні ip користувачів")],
        [KeyboardButton(text="Всі користувачі в базі")],
        [KeyboardButton(text="Відвідувачі")],
        [KeyboardButton(text="Змінити значення")],
        [KeyboardButton(text="Забанить користувача")],
        [KeyboardButton(text="Видалити значення")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Ти потрапив в секретне меню", reply_markup=keyboard)


@router.message(lambda message: message.text == "Всі активні ip користувачів")
async def cmd_all_data(message: types.Message):
    if not is_admin(message):
        await message.answer("Доступ заборонено !")
        return

    await message.answer("Всі активні ip які тільки є в базі")
    data = await list_admin_info(status="1")
    await send_xlsx(
        message,
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
        data,
    )


@router.message(lambda message: message.text == "Всі користувачі в базі")
async def cmd_all_users(message: types.Message):
    if not is_admin(message):
        await message.answer("Доступ заборонено !")
        return

    await message.answer("Всі користувачі які тільки є в базі")
    data = await list_admin_info(status="2")
    await send_xlsx(
        message,
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
        data,
    )


@router.message(lambda message: message.text == "Відвідувачі")
async def gosti(message: types.Message):
    if not is_admin(message):
        await message.answer("Доступ заборонено !")
        return

    await message.answer("Відвідувачі")
    data = await list_admin_info(status="3")
    await send_xlsx(
        message,
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
        # без першої колонки id
        (row[1:] for row in data),
    )
