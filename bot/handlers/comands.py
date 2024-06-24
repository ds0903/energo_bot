import asyncio
from icmplib import async_ping
from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aioping
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import (insert_data, list_user_ip, delete_data, update_user_ip, list_user_ip_by_id)

# from handlers.photos.photo_manager import photo_clas

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


"""Логіка головного меню"""


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    text = "Привіт я створений для інформування чи є світло в твоєму домі.\nПереглянути повну інформацію про бота ти можеш у вкладці Допомога"
    await message.answer(text)
    await asyncio.sleep(1)
    await cmd_menu(message)


@router.message(lambda message: message.text == "Меню")
async def cmd_menu(message: types.Message):
    text1 = "Оберіть потрібну вам дію"

    kb = [
        [KeyboardButton(text="Увімкнути бота"), KeyboardButton(text="Вимкнути бота")],
        [KeyboardButton(text="Допомога"), KeyboardButton(text="Мої ip адреси")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)


@router.message(lambda message: message.text == "Допомога")
async def process_with_puree(message: types.Message):
    text1 = "Бот працює по принципу того що ви вказуєте свою власну ip адресу, і бот відслідковує по ній світло. наприклад ipv4 16.211.99.114"
    text2 = "\nВ залежності від вашого провайдера ip адреса може бути динамічна тому бажано принайні раз в тиждень ї моніторити, в іншому випадку бот працюватиме не точно."
    text3 = "\nДля отримання допомоги напишіть розробнику @ds0903\nТакож ви можете підтримати розробника донатом це не обовязково але бот працює не безкоштовно, mono 9999.1111.3333.4444"
    kb = [
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text1+text2)
    await asyncio.sleep(2)
    await message.answer("👨‍💻")
    await asyncio.sleep(0.10)
    await message.answer(text3, reply_markup=keyboard)


@router.message(lambda message: message.text == "Мої ip адреси")
async def cmd_ip(message: types.Message, state: FSMContext):
    text1 = "Оберіть потрібну вам дію"

    kb = [
        [KeyboardButton(text="Змінити ip"), KeyboardButton(text="Встановити ip")],
        [KeyboardButton(text="Видалити ip"), KeyboardButton(text="Список моїх ip адрес")],
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)

    @router.message(lambda message: message.text == "Встановити ip")
    async def set_ip(message: types.Message):
        kb = [[KeyboardButton(text="Назад")],]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Введіть ip адресу яку бажаєте відслідковувати в форматі ipv4\nНаприклад: 38.0.101.76\n\nДізнатись свою ip адресу можна перейшовши за посиланням https://whatismyipaddress.com/ru/index ", reply_markup=keyboard)
        await state.set_state(Form.ip)

    @router.message(Form.ip)
    async def ip(message: types.Message):
        if message.text == "Назад":
            await state.clear()
            await cmd_ip(message, state)
        else:
            ip = message.text
            if len(ip) > 12:
                await message.answer("Завеликий ip адрес. Спробуйте ще раз")
                await state.clear()
                await set_ip(message)
            else:
                await state.update_data(ip=ip)
                await message.reply(
                    f"ip адреса встановленна: {ip}"
                )
                await asyncio.sleep(1)
                await message.reply(
                f"Напишіть тепер опис ip адреси\nНаприклад: Будинок"
                )
                await state.set_state(Form.ip_description)

    @router.message(Form.ip_description)
    async def set_ip_description(message: types.Message):
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        username = message.from_user.username
        language_code = message.from_user.language_code
        is_premium = message.from_user.is_premium
        ip_description = message.text
        await state.update_data(ip_description1=ip_description)
        await message.reply(
            f"опис встановленно: {ip_description}"
        )
        user_data = await state.get_data()
        ip = user_data["ip"]
        data_full = (ip, ip_description)
        await insert_data(user_id, ip, ip_description, first_name, last_name, username, language_code, is_premium,)
        await asyncio.sleep(1)
        await message.answer(f"Данні записано:{data_full}")
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)

    @router.message(lambda message: message.text == "Видалити ip")
    async def delete_ip(message: types.Message):
        kb = [[KeyboardButton(text="Назад")],]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Напишіть номер ip адресу який бажаєте видалити\nНаприклад №3 ", reply_markup=keyboard)
        data = message.from_user.id
        result = await list_user_ip(data)
        await asyncio.sleep(0.5)
        try:
            for i in result:
                id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
                result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
                await message.answer(result1)
                await asyncio.sleep(0.5)
            await state.set_state(Form.delete_ip)
        except TypeError:
            await asyncio.sleep(0.5)
            await message.answer("Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці Встановити ip")
            await state.clear()
            await asyncio.sleep(1)
            await cmd_ip(message, state)

    @router.message(Form.delete_ip)
    async def delete_ip1(message: types.Message):
        if message.text == "Назад":
            await state.clear()
            await cmd_ip(message, state)
        else:
            id1 = message.text
            data = message.from_user.id
            result = await list_user_ip(data)
            for i in result:
                id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
                id1 = int(id1)
            if id1 != id:
                await message.answer("Такого ip адресу не існує")
                await asyncio.sleep(1)
                await state.clear()
                await delete_ip(message)
            elif id1 == id:
                data1 = await delete_data(id1)
                await message.answer(data1)
                await asyncio.sleep(1)
                await state.clear()
                await cmd_ip(message, state)

    @router.message(lambda message: message.text == "Змінити ip")
    async def change_ip(message: types.Message):
        kb = [[KeyboardButton(text="Назад")],]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Виберіть номер ip адресу який бажаєте змінити", reply_markup=keyboard)

        data = message.from_user.id
        result = await list_user_ip(data)
        
        try:
            for i in result:
                id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
                result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
                await asyncio.sleep(0.5)
                await message.answer(result1)
            else:
                await state.set_state(Form.change_ip)
        except TypeError:
            await asyncio.sleep(0.5)
            await message.answer("Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці Встановити ip")
            await state.clear()
            await asyncio.sleep(1)
            await cmd_ip(message, state)

    @router.message(Form.change_ip)
    async def change_ip1(message: types.Message):
        if message.text == "Назад":
            await state.clear()
            await cmd_ip(message, state)
        else:
            id1 = message.text
            data = message.from_user.id
            result = await list_user_ip(data)
            for i in result:
                id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
                id1 = int(id1)
            if id != id1:
                await message.answer("Такого ip адресу не існує")
                await state.clear()
                await asyncio.sleep(1)
                await change_ip(message)
            elif id == id1:
                await message.answer("Напишіть новий ip адрес")
                await state.update_data(id1=id1)
                await asyncio.sleep(1)
                await state.set_state(Form.change_ip_adress)

    @router.message(Form.change_ip_adress)
    async def change_ip2(message: types.Message):
        ip = message.text
        await state.update_data(ip=ip)
        await message.reply(f"ip адреса встановленна: {ip}")
        await asyncio.sleep(1)
        await message.reply(
        f"Напишіть тепер опис ip адреси\nНаприклад: Будинок"
        )
        await state.set_state(Form.change_ip_description)
        
    @router.message(Form.change_ip_description)
    async def change_ip3(message: types.Message):
        ip_description = message.text
        user_data = await state.get_data()
        ip = user_data["ip"]
        id = user_data["id1"]
        await message.reply(f"опис встановленно: {ip_description}")
        data_full = (id, ip, ip_description)
        await update_user_ip(data_full)
        await asyncio.sleep(1)
        await message.answer(f"Нова ip адреса: {data_full}")
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)

    @router.message(lambda message: message.text == "Список моїх ip адрес")
    async def list_my_ip(message: types.Message):
        kb = [[KeyboardButton(text="Назад")],]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

        await message.answer("Список ваших ip адрес", reply_markup=keyboard)

        data = message.from_user.id
        result = await list_user_ip(data)
        if result:
            for i in result:
                id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
                result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
                await asyncio.sleep(0.5)
                await message.answer(result1)
            await asyncio.sleep(0.5)
            await cmd_ip(message, state)
        else:
            await message.answer("Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці Встановити ip")
            await state.clear()
            await asyncio.sleep(1)
            await cmd_ip(message, state)


@router.message(lambda message: message.text == "Увімкнути бота")
async def turn_on(message: types.Message, state: FSMContext):
    kb = [[KeyboardButton(text="Назад")],]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    # await message.answer("Виберіть № ip адреси яку бажаєте увімкнути", reply_markup=keyboard)
    data = message.from_user.id
    result = await list_user_ip(data)
    if result:
        await message.answer("Виберіть № ip адреси яку бажаєте вимкнути", reply_markup=keyboard)
        for i in result:
            id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
            result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
            await asyncio.sleep(0.5)
            await message.answer(result1)
        await state.set_state(Form.turn_on)
    else:
        await message.answer("Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці (Список ip адрес -> Встановити ip)")
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)

    @router.message(Form.turn_on)
    async def turn_on2(message: types.Message, state: FSMContext):
        data = message.text
        result = await list_user_ip_by_id(data)
        await message.reply(f"Ви отримали: {result}")
        # user_data = await state.get_data()
        # id1 = user_data["id1"]
        # await message.reply(f"Ви ввели: {id}")
        # if id == "Назад":
        #     await state.clear()

# @router.message(lambda message: message.text == "Вимкнути бота")
# async def turn_off(message: types.Message, state: FSMContext):
#     kb = [[KeyboardButton(text="Назад")],]
#     keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
#     data = message.from_user.id
#     result = await list_user_ip(data)
#     if result:
#         await message.answer("Виберіть № ip адреси яку бажаєте вимкнути", reply_markup=keyboard)
#         for i in result:
#             id, user_id, ip, description, first_name, last_name, username, language_code, is_premium = i
#             result1 = f"№: {id}, ip адрес: {ip}, Опис: {description}"
#             await asyncio.sleep(0.5)
#             await message.answer(result1)
#         await asyncio.sleep(0.5)
#         await cmd_ip(message, state)
#     else:
#         await message.answer("Ви не маєте жодних ip адрес ;(\nСтворіть нову ip адресу в вкладці (Список ip адрес -> Встановити ip)")
#         await state.clear()
#         await asyncio.sleep(1)
#         await cmd_ip(message, state)


# https://whatismyipaddress.com/ru/index

#########
    # ip_address = "46.211.95.114"
    # async def check_light(ip_address): #user_id, 
    #     while True:
    #         try:
    #             delay = await aioping.ping(ip_address)
    #             await message.answer(f"Свет есть! Задержка: {delay} мс")
    #         except TimeoutError:
    #             await message.answer("Света нет!")
    #         await asyncio.sleep(5) 
    # await check_light(ip_address)
###########

# def set_ip(update: Update, context: CallbackContext) -> None:
#     user_id = update.message.chat_id
#     ip_address = context.args[0]
#     user_ips[user_id] = ip_address
#     update.message.reply_text(f'IP-адрес установлен: {ip_address}')
#     check_light(user_id, ip_address, context)

# def check_light(user_id, ip_address, context: CallbackContext) -> None:
#     def ping_ip():
#         while True:
#             host = ping(ip_address, count=1, interval=1)
#             if host.is_alive:
#                 context.bot.send_message(chat_id=user_id, text="Свет есть!")
#             else:
#                 context.bot.send_message(chat_id=user_id, text="Света нет!")
#             threading.Event().wait(300)  # Ждем 5 минут перед следующим пингом

#     thread = threading.Thread(target=ping_ip)
#     thread.start()