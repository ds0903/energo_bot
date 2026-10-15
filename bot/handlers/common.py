"""Спільні команди, вибір режиму та головне меню."""

from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from handlers.comands import extended_main_screen, start_ip_check, with_notice
from handlers.logic import (
    MODE_EXTENDED,
    MODE_STANDARD,
    add_gosti,
    get_user_mode,
    set_user_mode,
)
from handlers.menus import (
    CB_MODE_CHOOSE,
    CB_MODE_EXTENDED,
    CB_MODE_STANDARD,
    MENU_MAIN,
    VERSION_TEXT,
    back_keyboard,
    mode_choice_keyboard,
    mode_choice_text,
)
from handlers.standard import standard_screen
from settings import extended_mode_enabled
from ui import delete_quietly, edit_panel, remove_reply_keyboard, send_panel

router = Router()
# реєструється останнім: ловить усе, що не підійшло жодному іншому хендлеру
fallback_router = Router()

GREETING = "Привіт, я створений для інформування стану електроенергії :)"


def extended_on(event) -> bool:
    """Фільтр: хендлер працює, лише якщо розширений режим увімкнено."""
    return extended_mode_enabled()


async def main_screen(user_id: int, notice: str = ""):
    """(текст, кнопки) головного екрана відповідно до режиму користувача."""
    if not extended_mode_enabled():
        # розширений режим вимкнено: усі, зокрема колишні користувачі IP-моніторингу,
        # працюють у стандартному і вибору режиму не бачать
        if await get_user_mode(user_id) != MODE_STANDARD:
            await set_user_mode(user_id, MODE_STANDARD)
        return await standard_screen(user_id, notice)

    mode = await get_user_mode(user_id)
    if mode == MODE_STANDARD:
        return await standard_screen(user_id, notice)
    if mode == MODE_EXTENDED:
        return await extended_main_screen(user_id, notice)
    return with_notice(notice, mode_choice_text()), mode_choice_keyboard()


def message_id_of(callback: types.CallbackQuery):
    return callback.message.message_id if callback.message else None


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    await delete_quietly(bot, message.chat.id, message.message_id)
    await remove_reply_keyboard(bot, message.chat.id)
    await add_gosti(
        user.id,
        user.is_bot,
        user.first_name,
        user.last_name,
        user.username,
        user.language_code,
        user.is_premium,
        user.added_to_attachment_menu,
        user.can_join_groups,
        user.can_read_all_group_messages,
        user.supports_inline_queries,
        user.can_connect_to_business,
        str(datetime.now()),
    )
    first_time = await get_user_mode(user.id) is None
    text, markup = await main_screen(user.id, GREETING if first_time else "")
    await send_panel(bot, user.id, text, markup)


@router.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    await delete_quietly(bot, message.chat.id, message.message_id)
    text, markup = await main_screen(message.from_user.id)
    await send_panel(bot, message.from_user.id, text, markup)


@router.message(Command("version"))
async def cmd_version(message: types.Message, bot: Bot):
    await delete_quietly(bot, message.chat.id, message.message_id)
    await send_panel(bot, message.from_user.id, VERSION_TEXT, back_keyboard())


@router.message(Command("restart"))
async def cmd_restart(message: types.Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    await delete_quietly(bot, message.chat.id, message.message_id)
    notice = ""
    if extended_mode_enabled():
        start_ip_check(bot, user_id)
        notice = (
            "🔁 Функції бота перезавантажено\n"
            "Для зупинення роботи бота вимкніть IP: ⏹ Вимкнути бота"
        )
    text, markup = await main_screen(user_id, notice)
    await send_panel(bot, user_id, text, markup)


@router.callback_query(F.data == MENU_MAIN)
async def show_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    text, markup = await main_screen(user_id)
    await edit_panel(
        callback.bot, user_id, text, markup, message_id=message_id_of(callback)
    )


@router.callback_query(F.data == CB_MODE_CHOOSE, extended_on)
async def choose_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    can_go_back = await get_user_mode(user_id) is not None
    await edit_panel(
        callback.bot,
        user_id,
        mode_choice_text(),
        mode_choice_keyboard(can_go_back),
        message_id=message_id_of(callback),
    )


@router.callback_query(F.data.in_({CB_MODE_STANDARD, CB_MODE_EXTENDED}), extended_on)
async def set_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    mode = MODE_STANDARD if callback.data == CB_MODE_STANDARD else MODE_EXTENDED
    await set_user_mode(user_id, mode)
    text, markup = await main_screen(user_id)
    await edit_panel(
        callback.bot, user_id, text, markup, message_id=message_id_of(callback)
    )


@fallback_router.callback_query()
async def stale_callback(callback: types.CallbackQuery, state: FSMContext):
    """Кнопка зі старої панелі (наприклад, розширеного режиму): повертаємо головний екран."""
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    text, markup = await main_screen(user_id)
    await edit_panel(
        callback.bot, user_id, text, markup, message_id=message_id_of(callback)
    )


@fallback_router.message(StateFilter(None), F.chat.type == "private")
async def fallback(message: types.Message, bot: Bot):
    """Будь-який текст поза діалогом (зокрема кнопки старої клавіатури): повертаємо панель."""
    await delete_quietly(bot, message.chat.id, message.message_id)
    await remove_reply_keyboard(bot, message.chat.id)
    text, markup = await main_screen(message.from_user.id)
    await send_panel(bot, message.from_user.id, text, markup)
