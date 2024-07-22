import asyncio
import socket
from datetime import datetime

import aioping
from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import (add_gosti, delete_active_user_ip, delete_data,
                            get_is_active, insert_active_user_ip, insert_data,
                            list_admin_info, list_user_active_ip, list_user_ip,
                            list_user_ip_by_id, update_user_ip,
                            update_user_status)

router = Router()


class Form(StatesGroup):
    ip = State()
    ip_description = State()
    delete_ip = State()
    change_ip = State()
    change_ip_adress = State()
    turn_on = State()
    turn_off = State()
    change_ip_description = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    text = "Привіт я створений для інформування стану електроенергії.\nПереглянути інструкцію та повну інформацію про бота ти можеш у вкладці Допомога"
    text2 = "Для перегляду версії бота введіть команду /version"
    await message.answer(text)
    await asyncio.sleep(1)
    await message.answer(text2)
    await asyncio.sleep(1)
    await cmd_menu(message)
    current_time = datetime.now()
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

    data = await add_gosti(
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
    if data == 1:
        await message.answer("Ви успішно додали користувача до гостя")
    elif data == 2:
        await message.answer("хуй тобі")


@router.message(Command("version"))
async def version(message: types.Message):
    await message.reply(
        "v1.0.4. При виявленні помилок напишіть, будь ласка, розробнику @ds0903.\n\nСписок змін:\nВирішена проблема із зависанням бота при додаванні опису до IP-адреси.\nВиправлені синтаксичні помилки."
    )


@router.message(Command("restart"))
async def reload(message: types.Message):
    await message.reply("Функції бота перезавантажено")
    await main_ip_check(message)
    await asyncio.sleep(1)
    await message.answer(
        "Для зупинення роботи бота видаліть активні ip в вкладці Меню -> Вимкнути бота"
    )


@router.message(lambda message: message.text == "Меню")
async def cmd_menu(message: types.Message):
    text1 = "Оберіть потрібну вам дію"

    kb = [
        [KeyboardButton(text="Увімкнути бота"), KeyboardButton(text="Вимкнути бота")],
        [KeyboardButton(text="Допомога"), KeyboardButton(text="Мої IP-адреси")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)


@router.message(lambda message: message.text == "Допомога")
async def process_with_puree(message: types.Message):
    text1 = "Повна інструкція до телеграм-бота знаходиться за посиланням https://t.me/energo_bot_info"
    text2 = """Ви можете підтримати проект донатом; це не обов'язково, але бот працює на сервері не безкоштовно.\n\nMonobank: `5375.4141.2663.2131`\nРозробка телеграм-ботів для вашого бізнесу під ключ @ds0903"""
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
        ip = message.text
        try:
            ip = ip.strip()
            if len(ip) > 16 or len(ip) < 6:
                await message.answer(
                    "Не правильний формат IP-адреси. Спробуйте ще раз!"
                )
                await state.clear()
                await set_ip(message, state)
            else:
                await state.update_data(ip=ip)
                await message.reply(f"IP-адреса встановленна: {ip}")
                await asyncio.sleep(1)
                await message.reply(
                    f"Напишіть тепер опис IP-адреси\nНаприклад: Будинок"
                )

                await state.set_state(Form.ip_description)
        except ValueError:
            await message.answer("Не правильний формат IP-адреси. Спробуйте ще раз")


@router.message(Form.ip_description)
async def set_ip_description(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
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
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Напишіть номер IP-адреси яку бажаєте видалити\nНаприклад №3 ",
        reply_markup=keyboard,
    )
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
    else:
        data = message.from_user.id
        result = await list_user_ip(data)
        await asyncio.sleep(0.5)
        try:
            for i in result:
                (
                    id,
                    user_id,
                    ip,
                    description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                ) = i
                result1 = f"№: {id}, IP-адрес: {ip}, Опис: {description}"
                await message.answer(result1)
                await asyncio.sleep(0.5)
            await state.set_state(Form.delete_ip)
        except TypeError:
            await asyncio.sleep(0.5)
            await message.answer(
                "Ви не маєте жодних IP-адрес ;(\nСтворіть нову IP-адресу в вкладці Встановити ip"
            )
            await state.clear()
            await asyncio.sleep(1)
            await cmd_ip(message, state)


@router.message(Form.delete_ip)
async def delete_ip1(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
    else:
        id1 = message.text
        data = message.from_user.id
        result = await list_user_ip(data)
        id1 = int(id1)
        for i in result:
            (
                id,
                user_id,
                ip,
                description,
                first_name,
                last_name,
                username,
                language_code,
                is_premium,
            ) = i
            if id == id1:
                id2 = id
            else:
                continue
            # if id1 == id:
        

# Розібратися з вкладкобю змінити, код нке працює парвильно
@router.message(lambda message: message.text == "Змінити IP")
async def change_ip(message: types.Message):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Поки в розробці!", reply_markup=keyboard)
    await cmd_ip(message, state)
    #         await message.answer(
    #     "Виберіть номер ip адресу який бажаєте змінити", reply_markup=keyboard
    # )


#     data = message.from_user.id
#     result = await list_user_ip(data)

#     try:
#         for i in result:
#             (
#                 id,
#                 user_id,
#                 ip,
#                 description,
#                 first_name,
#                 last_name,
#                 username,
#                 language_code,
#                 is_premium,
#             ) = i
#             result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
#             await asyncio.sleep(0.5)
#             await message.answer(result1)
#         await state.set_state(Form.change_ip)
#     except TypeError:
#         await asyncio.sleep(0.5)
#         await message.answer(
#             "Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці Встановити ip"
#         )
#         await state.clear()
#         await asyncio.sleep(1)
#         await cmd_ip(message, state)

# @router.message(Form.change_ip)
# async def change_ip1(message: types.Message, state: FSMContext):
#     if message.text == "Назад":
#         await state.clear()
#         await cmd_ip(message, state)
#     else:
#         id1 = message.text
#         data = message.from_user.id
#         result = await list_user_ip(data)
#         for i in result:
#             (
#                 id,
#                 user_id,
#                 ip,
#                 description,
#                 first_name,
#                 last_name,
#                 username,
#                 language_code,
#                 is_premium,
#             ) = i
#             id1 = int(id1)
#         if id1 != id:
#             await message.answer("Такого ip адресу не існує")
#             await state.clear()
#             await asyncio.sleep(1)
#             await change_ip(message)
#         elif id == id1:
#             await message.answer("Напишіть новий ip адрес")
#             await state.update_data(id1=id1)
#             await asyncio.sleep(1)
#             await state.set_state(Form.change_ip_adress)

# @router.message(Form.change_ip_adress)
# async def change_ip2(message: types.Message, state: FSMContext):
#     if message.text == "Назад":
#         await state.clear()
#         await cmd_ip(message, state)
#     else:
#         ip = message.text
#         await state.update_data(ip=ip)
#         await message.reply(f"ip адреса встановленна: {ip}")
#         await asyncio.sleep(1)
#         await message.reply(f"Напишіть тепер опис ip адреси\nНаприклад: Будинок")
#         await state.set_state(Form.change_ip_description)

# @router.message(Form.change_ip_description)
# async def change_ip3(message: types.Message, state: FSMContext):
#     if message.text == "Назад":
#         await state.clear()
#         await cmd_ip(message, state)
#     else:
#         ip_description = message.text
#         user_data = await state.get_data()
#         ip = user_data["ip"]
#         id = user_data["id1"]
#         await message.reply(f"опис встановленно: {ip_description}")
#         data_full = (id, ip, ip_description)
#         await update_user_ip(data_full)
#         await asyncio.sleep(1)
#         await message.answer(f"Нова ip адреса: {data_full}")
#         await state.clear()
#         await asyncio.sleep(1)
#         await cmd_ip(message, state)


@router.message(lambda message: message.text == "Список моїх IP-адрес")
async def list_my_ip(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    if message.text == "Назад":
        await state.clear()
        await cmd_ip(message, state)
    else:
        await message.answer("Список ваших IP-адрес", reply_markup=keyboard)

        data = message.from_user.id
        result = await list_user_ip(data)
        if result:
            for i in result:
                (
                    id,
                    user_id,
                    ip,
                    description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                ) = i
                result1 = f"№: {id}, IP-адрес: {ip}, Опис: {description}"
                await asyncio.sleep(0.5)
                await message.answer(result1)
            await asyncio.sleep(0.5)
            await cmd_ip(message, state)
        else:
            await message.answer(
                "Ви не маєте жодних IP-адрес ;(\nСтворіть нову IP-адресу в вкладці Встановити IP"
            )
            await state.clear()
            await asyncio.sleep(1)
            await cmd_ip(message, state)


@router.message(lambda message: message.text == "Увімкнути бота")
async def turn_on(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    data = message.from_user.id
    result = await list_user_ip(data)
    try:
        await message.answer(
            "Виберіть № ip адреси яку бажаєте увімкнути", reply_markup=keyboard
        )
        await state.set_state(Form.turn_on)
        for i in result:
            (
                id,
                user_id,
                ip,
                description,
                first_name,
                last_name,
                username,
                language_code,
                is_premium,
            ) = i
            result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
            await asyncio.sleep(0.5)
            await message.answer(result1)

    except TypeError:
        asyncio.sleep(0.5)
        await message.answer(
            "Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці (Список моїх ip адрес -> Додати ip)"
        )
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)

    @router.message(Form.turn_on)
    async def turn_on2(message: types.Message, state: FSMContext):
        if message.text == "Назад":
            await state.clear()
            await cmd_menu(message)
        else:
            try:
                data = message.text
                result = await list_user_ip_by_id(data)
                (
                    id,
                    user_id,
                    ip,
                    description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                ) = result

                result1 = f"\n№: {id}, адрес: {ip}, Опис: {description}"

                result_2 = await insert_active_user_ip(
                    id,
                    user_id,
                    ip,
                    description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                )
                if result_2 == "ip адрес успішно додано":
                    await message.reply(f"ip адресу активовано: {result1}")
                    await state.clear()
                    await cmd_menu(message)
                    await main_ip_check(message)
                elif result_2 == "ip адрес вже інсує":
                    await message.reply(
                        f"ip адреса вже була активована, виберіть іншу: {result1}"
                    )
                    await turn_on(message, state)
                    await main_ip_check(message)
            except TypeError:
                await message.reply("Виберіть інший ip адрес")
                await turn_on(message, state)


@router.message(lambda message: message.text == "Вимкнути бота")
async def turn_off(message: types.Message, state: FSMContext):
    kb = [
        [KeyboardButton(text="Назад")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    data = message.from_user.id
    result = await list_user_active_ip(data)
    try:
        await message.answer(
            "Виберіть № ip адреси яку бажаєте вимкнути", reply_markup=keyboard
        )
        await state.set_state(Form.turn_off)
        for i in result:
            (
                id,
                user_id,
                ip,
                description,
                first_name,
                last_name,
                username,
                language_code,
                is_premium,
                is_active,
            ) = i
            result1 = f"№: {id}, IP-адрес: {ip}, Опис: {description}"
            await asyncio.sleep(0.5)
            await message.answer(result1)
    except TypeError:
        await asyncio.sleep(0.5)
        await message.answer(
            "Ви не маєте жодних IP-адрес ;(\nСтворіть нову IP-адресу в вкладці (Мої IP-адреси -> Додати IP)"
        )
        await state.clear()
        await asyncio.sleep(1)
        await cmd_menu(message)


@router.message(Form.turn_off)
async def turn_off2(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        await cmd_menu(message)
    else:
        user_id1 = message.from_user.id
        data = message.text
        result = await list_user_ip_by_id(data)
        (
            id,
            user_id,
            ip,
            description,
            first_name,
            last_name,
            username,
            language_code,
            is_premium,
        ) = result
        result1 = f"\n№: {id}, адрес: {ip}, Опис: {description}"
        if user_id1 == user_id:
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
        else:
            await message.reply(
                f"Ви вибрали не правильний IP-адрес\nзвірьте номер вибраного IP-адресу з наявними"
            )


#########
processed_ids = {}


async def check_light(message: types.Message, id, user_id, ip, description, is_active):
    if id not in processed_ids:
        processed_ids[id] = set()
    if id in processed_ids[id]:
        return
    try:
        await aioping.ping(ip)
        status = True
        if is_active != status and id not in processed_ids[id]:
            await update_user_status(status, user_id, id, ip)
            processed_ids[id].add(id)
            await asyncio.sleep(1)
            current_is_active = await get_is_active(user_id, id)
            if current_is_active != status:
                await message.answer(
                    f"🟢 Світло є!\nАдрес: {ip}\nОпис: {description}\n№: {id}"
                )

    except TimeoutError:
        status = False
        if is_active != status and id not in processed_ids[id]:
            await update_user_status(status, user_id, id, ip)
            processed_ids[id].add(id)
            await asyncio.sleep(1)
            current_is_active = await get_is_active(user_id, id)
            if current_is_active != status:
                await asyncio.sleep(1)
                await message.answer(
                    f"🔴 Світла немає!\nАдрес: {ip}\nОпис: {description}\n№: {id}"
                )

    except socket.gaierror:

        if id not in processed_ids[id]:
            processed_ids[id].add(id)
            await asyncio.sleep(1)
            await message.answer(
                f"Не правильний формат IP-адреси! №: {id} адрес: {ip}\nВпевніться чи він відповідає стандарту ipv4\nНаприклад 81.20.204.106 "
            )
            await delete_active_user_ip(id)
        else:
            print("Error")
    except Exception:
        if id not in processed_ids[id]:
            processed_ids[id].add(id)
            await message.answer(
                "Похибка, спробуйте інший IP-адрес, або зверніться за допомогою до адміністратора в вкладці Допомога"
            )
            await delete_active_user_ip(id)
        else:
            print("Error")


##########


async def main_ip_check(message: types.Message):
    user_id = message.from_user.id
    while True:
        data_active = await list_user_active_ip(user_id)
        if data_active:
            try:
                for i in data_active:
                    (
                        id,
                        user_id,
                        ip,
                        description,
                        first_name,
                        last_name,
                        username,
                        language_code,
                        is_premium,
                        is_active,
                    ) = i
                    await check_light(message, id, user_id, ip, description, is_active)
                processed_ids[id].clear()

                # await asyncio.sleep(30)
                await asyncio.sleep(10 * 60)
            except TypeError:
                break
        else:
            break


##########
# https://whatismyipaddress.com/ru/index
# https://2ip.ua/ru/
