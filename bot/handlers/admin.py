import asyncio
import hmac
import logging
import os
import time

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile
from handlers.common import main_screen
from handlers.logic import list_admin_info, list_mode_user_ids
from handlers.menus import (ADM_ACTIVE, ADM_GUESTS, ADM_USERS, admin_keyboard,
                            back_keyboard)
from openpyxl import Workbook
from settings import refresh_password
from ui import delete_quietly, send_panel

router = Router()
logger = logging.getLogger(__name__)

ADMIN_USERNAME = "ds0903"
DENIED_TEXT = "Доступ заборонено !"
DEFAULT_REFRESH_NOTICE = "🆕 Бот оновлено"
# пауза між користувачами: Telegram дозволяє ~30 повідомлень на секунду
BROADCAST_PAUSE_SECONDS = 0.05
# захист пароля від підбору: після 5 невдалих спроб користувач блокується на 15 хвилин
MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
_failed_attempts: dict[int, list[float]] = {}

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


async def refresh_panel(bot: Bot, user_id: int, notice: str):
    """Нова панель користувачу (стара видаляється). True, якщо надіслано."""
    for attempt in range(2):
        try:
            text, markup = await main_screen(user_id, notice)
            await send_panel(bot, user_id, text, markup)
            return True
        except TelegramRetryAfter as error:
            # Telegram просить трохи зачекати: чекаємо і пробуємо ще раз
            await asyncio.sleep(error.retry_after + 1)
        except TelegramAPIError:
            # наприклад, користувач заблокував бота
            logger.info("Не вдалося надіслати панель користувачу %s", user_id)
            return False
    return False


def password_accepted(user_id: int, given: str) -> bool:
    """Перевіряє пароль /refresh; після кількох невдалих спроб користувача блокує."""
    now = time.monotonic()
    attempts = [t for t in _failed_attempts.get(user_id, []) if now - t < LOCK_SECONDS]
    _failed_attempts[user_id] = attempts
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        return False  # заблоковано: навіть правильний пароль не приймається

    expected = refresh_password()
    # compare_digest: порівняння за сталий час, щоб пароль не вгадували по затримці
    if expected and hmac.compare_digest(given.encode(), expected.encode()):
        _failed_attempts.pop(user_id, None)
        return True
    attempts.append(now)
    return False


@router.message(Command("refresh", "remind"))
async def cmd_refresh(message: types.Message, command: CommandObject, bot: Bot):
    """Розсилає кожному користувачу свіжу панель (з новими кнопками).

    Формат: /refresh ПАРОЛЬ [текст примітки]. Пароль задає REFRESH_PASSWORD у .env.
    Стара панель у кожного видаляється, нова приходить зі звуком. Виконується лише за
    командою, а не при кожному перезапуску бота. Текст після пароля (необов'язковий)
    стає приміткою над статусом: /refresh 1234 Додали нову кнопку.
    """
    # повідомлення з паролем видаляємо одразу, щоб воно не лишалося в чаті
    await delete_quietly(bot, message.chat.id, message.message_id)
    password, _, rest = (command.args or "").strip().partition(" ")
    if not password_accepted(message.from_user.id, password):
        await send_panel(bot, message.from_user.id, DENIED_TEXT, back_keyboard())
        return

    notice = rest.strip() or DEFAULT_REFRESH_NOTICE
    user_ids = await list_mode_user_ids()
    sent = failed = 0
    for user_id in user_ids:
        if await refresh_panel(bot, user_id, notice):
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(BROADCAST_PAUSE_SECONDS)

    # звіт окремим повідомленням: панель адміна вже оновлена розсилкою
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Розіслано: {sent}\n⚠️ Не вдалося (заблокували бота): {failed}",
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
