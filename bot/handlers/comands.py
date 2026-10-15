import asyncio
import logging
import socket

import aioping
from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from handlers.logic import (delete_active_user_ip, delete_data,
                            insert_active_user_ip, insert_data,
                            list_user_active_ip, list_user_ip,
                            list_user_ip_by_id, update_user_status)
from handlers.menus import (EXT_ADD, EXT_DELETE, EXT_HELP, EXT_IPS, EXT_MENU,
                            EXT_OFF, EXT_ON, HELP_TEXT, back_keyboard,
                            cancel_keyboard, extended_keyboard, ips_keyboard,
                            pick_keyboard)
from settings import ip_check_minutes
from ui import delete_quietly, edit_panel, send_panel

router = Router()
logger = logging.getLogger(__name__)

ADD_IP_PROMPT = (
    "➕ Введіть IP-адресу, яку бажаєте відслідковувати, у форматі IPv4.\n"
    "Наприклад: 38.0.101.76\n\n"
    "Дізнатися свою IP-адресу можна, перейшовши за посиланням: https://2ip.ua/ru/"
)
NO_IPS_TEXT = "Ви не маєте жодних IP-адрес ;(\nДодайте першу кнопкою «➕ Додати IP»"


class Form(StatesGroup):
    ip = State()
    ip_description = State()


def ip_label(ip, description) -> str:
    label = f"{ip} · {description}" if description else str(ip)
    return label[:50]


def with_notice(notice: str, body: str) -> str:
    return f"{notice}\n\n{body}" if notice else body


def parse_id(data: str):
    """Число з кінця callback_data виду "ext:on:12"; None, якщо там сміття."""
    try:
        return int(data.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None


async def extended_main_screen(user_id: int, notice: str = ""):
    ips = await list_user_ip(user_id)
    active = await list_user_active_ip(user_id)
    body = (
        "🛠 Розширений режим\n\n"
        f"IP-адрес: {len(ips)}, під наглядом: {len(active)}\n"
        "Оберіть потрібну вам дію"
    )
    return with_notice(notice, body), extended_keyboard()


async def ips_screen(user_id: int, notice: str = ""):
    ips = await list_user_ip(user_id)
    if ips:
        lines = [f"№{id} · {ip} · {description}" for id, _, ip, description, *_ in ips]
        body = "🌐 Мої IP-адреси\n\n" + "\n".join(lines)
    else:
        body = f"🌐 Мої IP-адреси\n\n{NO_IPS_TEXT}"
    return with_notice(notice, body), ips_keyboard()


async def render(callback: types.CallbackQuery, text, markup, parse_mode=None):
    """Змінює повідомлення, на кнопку якого натиснули."""
    await edit_panel(
        callback.bot,
        callback.from_user.id,
        text,
        markup,
        parse_mode=parse_mode,
        message_id=callback.message.message_id if callback.message else None,
    )


@router.callback_query(F.data == EXT_MENU)
async def show_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text, markup = await extended_main_screen(callback.from_user.id)
    await render(callback, text, markup)


@router.callback_query(F.data == EXT_HELP)
async def show_help(callback: types.CallbackQuery):
    await callback.answer()
    await render(callback, HELP_TEXT, back_keyboard(EXT_MENU), parse_mode="HTML")


@router.callback_query(F.data == EXT_IPS)
async def show_ips(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text, markup = await ips_screen(callback.from_user.id)
    await render(callback, text, markup)


# ---- додавання IP


@router.callback_query(F.data == EXT_ADD)
async def add_ip(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Form.ip)
    await render(callback, ADD_IP_PROMPT, cancel_keyboard())


@router.message(Form.ip)
async def set_ip(message: types.Message, state: FSMContext, bot: Bot):
    await delete_quietly(bot, message.chat.id, message.message_id)
    user_id = message.from_user.id
    ip = (message.text or "").strip()
    if len(ip) > 16 or len(ip) < 6:
        await edit_panel(
            bot,
            user_id,
            "❌ Не правильний формат IP-адреси. Спробуйте ще раз!\n\n" + ADD_IP_PROMPT,
            cancel_keyboard(),
        )
        return

    await state.update_data(ip=ip)
    await state.set_state(Form.ip_description)
    await edit_panel(
        bot,
        user_id,
        f"IP-адреса встановлена: {ip}\n\nНапишіть тепер опис IP-адреси\nНаприклад: Будинок",
        cancel_keyboard(),
    )


@router.message(Form.ip_description)
async def set_ip_description(message: types.Message, state: FSMContext, bot: Bot):
    await delete_quietly(bot, message.chat.id, message.message_id)
    user = message.from_user
    if not message.text:
        await edit_panel(
            bot,
            user.id,
            "❌ Опис має бути текстом. Спробуйте ще раз!\n\nНапишіть опис IP-адреси\nНаприклад: Будинок",
            cancel_keyboard(),
        )
        return

    ip = (await state.get_data())["ip"]
    await state.clear()
    await insert_data(
        user.id,
        ip,
        message.text,
        user.first_name,
        user.last_name,
        user.username,
        user.language_code,
        user.is_premium,
    )
    text, markup = await ips_screen(
        user.id, f"✅ Дані записано: ({ip}, {message.text})"
    )
    await edit_panel(bot, user.id, text, markup)


# ---- видалення IP


@router.callback_query(F.data == EXT_DELETE)
async def choose_ip_to_delete(callback: types.CallbackQuery):
    await callback.answer()
    ips = await list_user_ip(callback.from_user.id)
    if not ips:
        text, markup = await ips_screen(callback.from_user.id)
        await render(callback, text, markup)
        return
    items = [
        (id, "🗑 " + ip_label(ip, description)) for id, _, ip, description, *_ in ips
    ]
    await render(
        callback,
        "🗑 Оберіть IP-адресу, яку бажаєте видалити",
        pick_keyboard(EXT_DELETE, items, EXT_IPS),
    )


@router.callback_query(F.data.startswith(EXT_DELETE + ":"))
async def delete_ip(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    ip_id = parse_id(callback.data)
    # видаляти можна лише власні IP-адреси
    own = {row[0] for row in await list_user_ip(user_id)}
    if ip_id in own:
        notice = "✅ " + await delete_data(ip_id)
    else:
        notice = f"❌ IP адресу №{ip_id} не знайдено."
    text, markup = await ips_screen(user_id, notice)
    await render(callback, text, markup)


# ---- вмикання / вимикання моніторингу


@router.callback_query(F.data == EXT_ON)
async def choose_ip_to_enable(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    ips = await list_user_ip(user_id)
    if not ips:
        text, markup = await ips_screen(user_id)
        await render(callback, text, markup)
        return
    active = {row[0] for row in await list_user_active_ip(user_id)}
    items = [
        (id, ("✅ " if id in active else "▶️ ") + ip_label(ip, description))
        for id, _, ip, description, *_ in ips
    ]
    await render(
        callback,
        "▶️ Оберіть IP-адресу, яку бажаєте увімкнути\n(✅ - вже під наглядом)",
        pick_keyboard(EXT_ON, items, EXT_MENU),
    )


@router.callback_query(F.data.startswith(EXT_ON + ":"))
async def enable_ip(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    row = await list_user_ip_by_id(parse_id(callback.data) or 0)
    # вмикати можна лише власні IP-адреси
    if row is None or row[1] != user_id:
        notice = "❌ Такої IP-адреси немає. Виберіть іншу."
    else:
        id, _, ip, description, *_ = row
        info = f"№: {id}, адрес: {ip}, Опис: {description}"
        if await insert_active_user_ip(*row) == "ip адрес успішно додано":
            notice = f"✅ IP-адресу активовано:\n{info}"
        else:
            notice = f"ℹ️ IP-адреса вже була активована:\n{info}"
        start_ip_check(callback.bot, user_id)
    text, markup = await extended_main_screen(user_id, notice)
    await render(callback, text, markup)


@router.callback_query(F.data == EXT_OFF)
async def choose_ip_to_disable(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    active = await list_user_active_ip(user_id)
    if not active:
        text, markup = await extended_main_screen(
            user_id, "ℹ️ У вас немає IP-адрес під наглядом."
        )
        await render(callback, text, markup)
        return
    items = [
        (id, "⏹ " + ip_label(ip, description)) for id, _, ip, description, *_ in active
    ]
    await render(
        callback,
        "⏹ Оберіть IP-адресу, яку бажаєте вимкнути",
        pick_keyboard(EXT_OFF, items, EXT_MENU),
    )


@router.callback_query(F.data.startswith(EXT_OFF + ":"))
async def disable_ip(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    ip_id = parse_id(callback.data)
    # шукаємо серед власних активних IP-адрес користувача
    row = next((r for r in await list_user_active_ip(user_id) if r[0] == ip_id), None)
    if row is None:
        notice = "ℹ️ IP-адреса вже була деактивована."
    else:
        id, _, ip, description, *_ = row
        await delete_active_user_ip(id)
        notice = (
            f"✅ IP-адресу деактивовано:\n№: {id}, адрес: {ip}, Опис: {description}"
        )
    text, markup = await extended_main_screen(user_id, notice)
    await render(callback, text, markup)


# ---- перевірка наявності світла за IP


async def check_light(bot: Bot, id, user_id, ip, description, is_active):
    try:
        await aioping.ping(ip)
        status = True
    except TimeoutError:
        status = False
    except socket.gaierror:
        await send_panel(
            bot,
            user_id,
            f"Не правильний формат IP-адреси! №: {id} адрес: {ip}\n"
            "Впевніться чи він відповідає стандарту ipv4\nНаприклад 81.20.204.106 ",
            extended_keyboard(),
        )
        await delete_active_user_ip(id)
        return
    except Exception:
        # помилка на стороні сервера (мережа, права на ICMP) - не чіпаємо дані користувача
        logger.exception("Не вдалося перевірити ip %s (№ %s)", ip, id)
        return

    if is_active == status:
        return

    await update_user_status(status, user_id, id, ip)
    if status:
        text = f"🟢 Світло є!\nАдрес: {ip}\nОпис: {description}\n№: {id}"
    else:
        text = f"🔴 Світла немає!\nАдрес: {ip}\nОпис: {description}\n№: {id}"
    # сповіщення стає новою панеллю: старе повідомлення зникає, а кнопки лишаються під рукою
    await send_panel(bot, user_id, text, extended_keyboard())


# номер поточного запуску циклу перевірки для кожного користувача:
# новий запуск робить попередній застарілим, тож працює лише один цикл на користувача
check_generation: dict[int, int] = {}
_background_tasks: set[asyncio.Task] = set()


def start_ip_check(bot: Bot, user_id: int):
    """Запускає цикл перевірки у фоні (прикриваючи собою попередній цикл користувача)."""
    task = asyncio.create_task(_run_ip_check(bot, user_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_ip_check(bot: Bot, user_id: int):
    try:
        await main_ip_check(bot, user_id)
    except Exception:
        logger.exception("Цикл перевірки IP користувача %s зупинився", user_id)


async def main_ip_check(bot: Bot, user_id: int):
    generation = check_generation.get(user_id, 0) + 1
    check_generation[user_id] = generation

    while True:
        data_active = await list_user_active_ip(user_id)
        if not data_active:
            break
        for row in data_active:
            if check_generation[user_id] != generation:
                return
            id, _, ip, description = row[:4]
            is_active = row[-1]
            try:
                await check_light(bot, id, user_id, ip, description, is_active)
            except TelegramForbiddenError:
                # користувач заблокував бота
                return
            except Exception:
                logger.exception("Помилка перевірки ip %s (№ %s)", ip, id)

        await asyncio.sleep(ip_check_minutes() * 60)
        if check_generation[user_id] != generation:
            return
