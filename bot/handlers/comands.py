import asyncio

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import (insert_data)
# from handlers.photos.photo_manager import photo_clas

router = Router()


class Form(StatesGroup):
    ip = State()
    ip_description = State()


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
        [KeyboardButton(text="Допомога"), KeyboardButton(text="Налаштування ip")],
        # [KeyboardButton(text="Пошук рецептів за інгрідієнтами")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)



@router.message(lambda message: message.text == "Допомога")
async def process_with_puree(message: types.Message):
    text1 = "Бот працює по принципу того що ви вказуєте свою власну ip адресу, і бот відслідковує по ній коли є світло а коли немає. "
    text2 = "\nДля отримання допомоги напишіть розробнику @ds0903\nТакож ви можете підтримати розробника донатом це не обовязково але бот працює не безкоштовно, mono 9999111133334444"
    kb = [
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text1)
    await asyncio.sleep(2)
    await message.answer("👨‍💻")
    await asyncio.sleep(0.25)
    await message.answer(text2, reply_markup=keyboard)



@router.message(lambda message: message.text == "Налаштування ip")
async def cmd_ip(message: types.Message, state: FSMContext):
    text1 = "Оберіть потрібну вам дію"

    kb = [
        [KeyboardButton(text="Змінити ip"), KeyboardButton(text="Встановити ip")],
        [KeyboardButton(text="Видалити ip"), KeyboardButton(text="Допомога")],
        [KeyboardButton(text="Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await asyncio.sleep(1)
    await message.answer(text1, reply_markup=keyboard)


    @router.message(lambda message: message.text == "Встановити ip")
    async def set_ip(message: types.Message):
        await message.answer("Введіть ip адресу яку бажаєте відслідковувати в форматі ipv4\nНаприклад: 38.0.101.76\n\nДізнатись свою ip адресу можна перейшовши за посиланням https://whatismyipaddress.com/ru/index ", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Form.ip)

    @router.message(Form.ip)
    async def ip(message: types.Message):
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
    
        username = message.from_user.username
        ip_description = message.text
        await state.update_data(ip_description1=ip_description)
        await message.reply(
            f"опис встановленно: {ip_description}"
        )
        user_data = await state.get_data()
        ip = user_data["ip"]
        data_full = (ip, ip_description, user_id)
        await insert_data(user_id, ip, ip_description, first_name, username)
        await message.answer(f"Данні записано:{data_full}")
        await state.clear()
        await asyncio.sleep(1)
        await cmd_ip(message, state)

    @router.message(lambda message: message.text == "Видалити ip")
    async def set_ip(message: types.Message):
        await message.answer("Виберіть ip адресу яку бажаєте видалити", reply_markup=types.ReplyKeyboardRemove())
        # await state.set_state(Form.ip)


    @router.message(lambda message: message.text == "Змінити ip")
    async def set_ip(message: types.Message):
        await message.answer("Виберіть ip адресу яку бажаєте змінити", reply_markup=types.ReplyKeyboardRemove())
        # await state.set_state(Form.ip)



# https://whatismyipaddress.com/ru/index





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