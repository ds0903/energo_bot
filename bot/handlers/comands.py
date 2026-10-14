import asyncio
import logging
import socket
from datetime import datetime

import aioping
from aiogram import Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import (add_gosti, delete_active_user_ip, delete_data,
                            insert_active_user_ip, insert_data,
                            list_user_active_ip, list_user_ip,
                            list_user_ip_by_id, update_user_status)
from handlers.menus import send_menu
from settings import ip_check_minutes

router = Router()
logger = logging.getLogger(__name__)


class Form(StatesGroup):
    ip = State()
    ip_description = State()
    delete_ip = State()
    turn_on = State()
    turn_off = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    text = "Привіт я створений для інформування стану електроенергії.\nПереглянути інструкцію та повну інформацію про бота ти можеш у вкладці Допомога"
    text2 = "Для перегляду версії бота введіть команду /version"
    await message.answer(text)
    await asyncio.sleep(1)
    await message.answer(text2)
    await asyncio.sleep(1)
    await cmd_menu(message)
    current_time = str(datetime.now())
    user_id = message.from_user.id
    is_bot = message.from_user.is_bot
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    username = message.from_user.username
    language_code = message.from_user.language_code
    is_premium = message.from_user.is_premium
    added_to_attachment_menu = message.from_user.added_to_attachment_menu
    can_join_groups = message.from_user.can_join_groups
    can_read_all_group_messages = message.from_user.can_read_all_group_messages
    supports_inline_queries = message.from_user.supports_inline_queries
    can_connect_to_business = message.from_user.can_connect_to_business

    await add_gosti(
        user_id,
        is_bot,
        first_name,
        last_name,
        username,
        language_code,
        is_premium,
        added_to_attachment_menu,
        can_join_groups,
        can_read_all_group_messages,
        supports_inline_queries,
        can_connect_to_business,
        current_time,
    )


@router.message(Command("version"))
async def version(message: types.Message):
    await message.reply(
        "v1.0.4. При виявленні помилок напишіть, будь ласка, розробнику @ds0903.\n\nСписок змін:\nВирішена проблема із зависанням бота при додаванні опису до IP-адреси.\nВиправленна помилка при видаленні IP-адреси.\nВиправлені синтаксичні помилки.\n\nДата виходу оновлення 22.07.2024"
    )


@router.message(Command("restart"))
async def reload(message: types.Message):
    await message.reply("Функції бота перезавантажено")
    await asyncio.sleep(1)
    await message.answer(
        "Для зупинення роботи бота видаліть активні ip в вкладці Меню -> Вимкнути бота"
    )
    # цикл перевірки нескінченний, тому запускаємо його останнім
    await main_ip_check(message)


@router.message(lambda message: message.text == "Меню")
async def cmd_menu(message: types.Message, state: FSMContext = None):
    if state is not None:
        await state.clear()
    await asyncio.sleep(1)
    await send_menu(message)


@router.message(lambda message: message.text == "Допомога")
async def process_with_puree(message: types.Message):
    text1 = "Повна інструкція до телеграм-бота знаходиться за посиланням https://t.me/energo_bot_info"
    text2 = """Ви можете підтримати проект донатом; це не обов'язково, але бот працює на сервері не безкоштовно.\n\nMonobank: `5375.4141.2663.2131`\n\nРозробка телеграм-ботів для вашого бізнесу під ключ @ds0903"""
    kb = [
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text1)
    await asyncio.sleep(2)
    await message.answer(text2, reply_markup=keyboard, parse_mode="Markdown")


@router.message(lambda message: message.text == "Мої IP-адреси")
async def cmd_ip(message: types.Message, state: FSMContext):
    text1 = "Оберіть потрібну вам дію"

    kb = [
        [KeyboardButton(text="Змінити IP"), KeyboardButton(text="Додати IP")],
        [
            KeyboardButton(text="Видалити IP"),
            KeyboardButton(text="Список моїх IP-адрес"),
        ],
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)


@router.message(lambda message: message.text == "Додати IP")
async def set_ip(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Введіть IP-адресу, яку бажаєте відслідковувати, у форматі IPv4.\nНаприклад: 38.0.101.76\n\nДізнатися свою IP-адресу можна, перейшовши за посиланням: https://2ip.ua/ru/",
        reply_markup=keyboard,
    )
    await state.set_state(Form.ip)


@router.message(Form.ip)
async def ip(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
    else:
        ip = (message.text or "").strip()
        if len(ip) > 16 or len(ip) < 6:
            await message.answer("Не правильний формат IP-адреси. Спробуйте ще раз!")
            await state.clear()
            await set_ip(message, state)
        else:
            await state.update_data(ip=ip)
            await message.reply(f"IP-адреса встановленна: {ip}")
            await asyncio.sleep(1)
            await message.reply("Напишіть тепер опис IP-адреси\nНаприклад: Будинок")

            await state.set_state(Form.ip_description)


@router.message(Form.ip_description)
async def set_ip_description(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
    elif not message.text:
        await message.answer("Опис має бути текстом. Спробуйте ще раз!")
    else:
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        username = message.from_user.username
        language_code = message.from_user.language_code
        is_premium = message.from_user.is_premium
        ip_description = message.text
        await state.update_data(ip_description1=ip_description)
        await message.reply(f"Опис встановленно: {ip_description}")
        user_data = await state.get_data()
        ip = user_data["ip"]
        data_full = (ip, ip_description)
        await insert_data(
            user_id,
            ip,
            ip_description,
            first_name,
            last_name,
            username,
            language_code,
            is_premium,
        )
        await asyncio.sleep(1)
        await message.answer(f"Данні записано: {data_full}")
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)


@router.message(lambda message: message.text == "Видалити IP")
async def delete_ip(message: types.Message, state: FSMContext):
    result = await list_user_ip(message.from_user.id)
    if not result:
        await asyncio.sleep(0.5)
        await message.answer(
            "Ви не маєте жодних IP-адрес ;(\nСтворіть нову IP-адресу в вкладці Встановити ip -> Додати IP"
        )
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)
        return

    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Напишіть номер IP-адреси яку бажаєте видалити\nНаприклад № 3 ",
        reply_markup=keyboard,
    )
    await asyncio.sleep(0.5)
    for id, user_id, ip, description, *_ in result:
        await message.answer(f"№: {id}, IP-адрес: {ip}, Опис: {description}")
        await asyncio.sleep(0.5)
    await state.set_state(Form.delete_ip)


@router.message(Form.delete_ip)
async def delete_ip1(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
        return

    try:
        id1 = int(message.text or "")
    except ValueError:
        await message.answer("Будь ласка, введіть число!")
        return

    result = await list_user_ip(message.from_user.id)
    for id, *_ in result:
        if id == id1:
            data1 = await delete_data(id)
            await message.answer(data1)
            await asyncio.sleep(1)
            await state.clear()
            await cmd_ip(message, state)
            return

    await message.answer(f"IP адресу №{id1} не знайдено. Спробуйте ще раз.")
    await asyncio.sleep(1)
    await delete_ip(message, state)


@router.message(lambda message: message.text == "Змінити IP")
async def change_ip(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Поки в розробці!", reply_markup=keyboard)

    await cmd_ip(message, state)


@router.message(lambda message: message.text == "Список моїх IP-адрес")
async def list_my_ip(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Список ваших IP-адрес", reply_markup=keyboard)
    result = await list_user_ip(message.from_user.id)
    if result:
        for id, user_id, ip, description, *_ in result:
            await asyncio.sleep(0.5)
            await message.answer(f"№: {id}, IP-адрес: {ip}, Опис: {description}")
        await asyncio.sleep(0.5)
    else:
        await asyncio.sleep(1)
        await message.answer(
            "Ви не маєте жодних IP-адрес ;(\nСтворіть нову IP-адресу в вкладці Додати IP"
        )
        await state.clear()
        await asyncio.sleep(1)
    await cmd_ip(message, state)


@router.message(lambda message: message.text == "Увімкнути бота")
async def turn_on(message: types.Message, state: FSMContext):
    result = await list_user_ip(message.from_user.id)
    if not result:
        await asyncio.sleep(0.5)
        await message.answer(
            "Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці (Список моїх ip адрес -> Додати ip)"
        )
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)
        return

    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Виберіть № ip адреси яку бажаєте увімкнути", reply_markup=keyboard
    )
    await state.set_state(Form.turn_on)
    for id, user_id, ip, description, *_ in result:
        await asyncio.sleep(0.5)
        await message.answer(f"№: {id}, ip адрес: {ip}, Опис: {description}")


@router.message(lambda message: message.text == "Вимкнути бота")
async def turn_off(message: types.Message, state: FSMContext):
    result = await list_user_active_ip(message.from_user.id)
    if not result:
        await asyncio.sleep(0.5)
        await message.answer(
            "Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці (Список моїх ip адрес -> Додати ip)"
        )
        await state.clear()
        await asyncio.sleep(1)
        await cmd_menu(message)
        return

    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Виберіть № ip адреси яку бажаєте вимкнути", reply_markup=keyboard
    )
    await state.set_state(Form.turn_off)
    for id, user_id, ip, description, *_ in result:
        await asyncio.sleep(0.5)
        await message.answer(f"№: {id}, IP-адрес: {ip}, Опис: {description}")


@router.message(Form.turn_off)
async def turn_off2(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_menu(message)
        return

    try:
        ip_id = int(message.text or "")
    except ValueError:
        await message.answer("Будь ласка, введіть число!")
        return

    # шукаємо серед власних активних IP-адрес користувача
    active = await list_user_active_ip(message.from_user.id)
    row = next((r for r in active if r[0] == ip_id), None)
    if row is None:
        await message.reply(
            "Ви вибрали не правильний IP-адрес\nзвірьте номер вибраного IP-адресу з наявними"
        )
        return

    id, user_id, ip, description, *_ = row
    result1 = f"\n№: {id}, адрес: {ip}, Опис: {description}"
    result_2 = await delete_active_user_ip(id)
    if result_2 == "IP-адресу успішно видаленно":
        await message.reply(f"IP-адресу успішно деактивовано: {result1}")
        await state.clear()
        await cmd_menu(message)
    elif result_2 == "IP-адреси не існує":
        await message.reply(
            f"IP-адреса вже була деактивована, виберіть іншу: {result1}"
        )
        await turn_off(message, state)


# Хендлер стану Form.turn_on має стояти після кнопок меню: aiogram перебирає хендлери
# у порядку реєстрації, і інакше текст кнопки сприймався б як номер IP-адреси
@router.message(Form.turn_on)
async def turn_on2(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_menu(message)
        return

    try:
        ip_id = int(message.text or "")
    except ValueError:
        await message.reply("Виберіть інший ip адрес")
        await turn_on(message, state)
        return

    result = await list_user_ip_by_id(ip_id)
    # можна вмикати лише власні IP-адреси
    if result is None or result[1] != message.from_user.id:
        await message.reply("Виберіть інший ip адрес")
        await turn_on(message, state)
        return

    id, user_id, ip, description, *_ = result
    result1 = f"\n№: {id}, адрес: {ip}, Опис: {description}"

    result_2 = await insert_active_user_ip(*result)
    if result_2 == "ip адрес успішно додано":
        await message.reply(f"ip адресу активовано: {result1}")
        await state.clear()
        await cmd_menu(message)
        await main_ip_check(message)
    elif result_2 == "ip адрес вже інсує":
        await message.reply(f"ip адреса вже була активована, виберіть іншу: {result1}")
        await turn_on(message, state)
        await main_ip_check(message)


async def check_light(message: types.Message, id, user_id, ip, description, is_active):
    try:
        await aioping.ping(ip)
        status = True
    except TimeoutError:
        status = False
    except socket.gaierror:
        await message.answer(
            f"Не правильний формат IP-адреси! №: {id} адрес: {ip}\nВпевніться чи він відповідає стандарту ipv4\nНаприклад 81.20.204.106 "
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
        await message.answer(f"🟢 Світло є!\nАдрес: {ip}\nОпис: {description}\n№: {id}")
    else:
        await message.answer(
            f"🔴 Світла немає!\nАдрес: {ip}\nОпис: {description}\n№: {id}"
        )


# номер поточного запуску циклу перевірки для кожного користувача:
# новий запуск робить попередній застарілим, тож працює лише один цикл на користувача
check_generation: dict[int, int] = {}


async def main_ip_check(message: types.Message):
    user_id = message.from_user.id
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
                await check_light(message, id, user_id, ip, description, is_active)
            except TelegramForbiddenError:
                # користувач заблокував бота
                return
            except Exception:
                logger.exception("Помилка перевірки ip %s (№ %s)", ip, id)

        await asyncio.sleep(ip_check_minutes() * 60)
        if check_generation[user_id] != generation:
            return
