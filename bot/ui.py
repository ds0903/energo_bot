"""Єдина "панель": бот тримає в чаті одне повідомлення з інлайн-кнопками.

Дія користувача змінює це повідомлення на місці, а сповіщення замінюють його новим
(щоб прийшов звуковий сигнал), тож у чаті завжди одне-два повідомлення.
"""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import LinkPreviewOptions, ReplyKeyboardRemove
from handlers.logic import get_panel, set_panel

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


async def delete_quietly(bot: Bot, chat_id: int, message_id: int):
    """Видаляє повідомлення; помилку (вже видалене, старше 48 годин) ігноруємо."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError:
        pass


async def send_panel(bot: Bot, user_id: int, text: str, markup, parse_mode=None):
    """Нова панель унизу чату; попередню панель видаляємо."""
    old = await get_panel(user_id)
    sent = await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=markup,
        parse_mode=parse_mode,
        link_preview_options=NO_PREVIEW,
    )
    await set_panel(user_id, sent.message_id)
    if old and old != sent.message_id:
        await delete_quietly(bot, user_id, old)


async def edit_panel(
    bot: Bot, user_id: int, text: str, markup, parse_mode=None, message_id=None
):
    """Змінює панель на місці (message_id - повідомлення, на кнопку якого натиснули).

    Якщо повідомлення зникло або його не можна редагувати, надсилає нову панель.
    """
    stored = await get_panel(user_id)
    target = message_id or stored
    if target:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=user_id,
                message_id=target,
                reply_markup=markup,
                parse_mode=parse_mode,
                link_preview_options=NO_PREVIEW,
            )
        except TelegramBadRequest as error:
            if "not modified" not in str(error).lower():
                target = None
        if target:
            if stored != target:
                # панеллю стало інше повідомлення, зайву копію прибираємо
                await set_panel(user_id, target)
                if stored:
                    await delete_quietly(bot, user_id, stored)
            return
    await send_panel(bot, user_id, text, markup, parse_mode)


async def remove_reply_keyboard(bot: Bot, chat_id: int):
    """Прибирає стару клавіатуру під полем вводу (з попередньої версії бота)."""
    try:
        sent = await bot.send_message(
            chat_id=chat_id, text="⏳", reply_markup=ReplyKeyboardRemove()
        )
    except TelegramAPIError:
        return
    await delete_quietly(bot, chat_id, sent.message_id)
