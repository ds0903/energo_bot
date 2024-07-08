import asyncio

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from handlers.logic import list_admin_info

router = Router()


class Form(StatesGroup):
    ip = State()


@router.message(lambda message: message.text == "cmd_admin")
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.username == "ds0903":
        kb = [[KeyboardButton(text="Всі активні ip користувачів")],[KeyboardButton(text="Всі користувачі в базі")],
              [KeyboardButton(text="Відвідувачі")],[KeyboardButton(text="Змінити значення")],
              [KeyboardButton(text="Забанить користувача")],[KeyboardButton(text="Видалити значення")],
              ]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Ти потрапив в севкретне меню", reply_markup=keyboard)
    else:
        await message.answer("хуй тобі а не консоль адміна гніда ти йобана !")

    @router.message(lambda message: message.text == "Всі активні ip користувачів")
    async def cmd_all_data(message: types.Message, state: FSMContext):
        await message.answer("Всі активні ip які тільки є в базі")
        data = await list_admin_info(status="1")
        for i in data:
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
            await message.answer(f"{id}, {user_id}, {ip}, {description}, {first_name}, {last_name}, {username}, {language_code}, {is_premium}, {is_active}")

    @router.message(lambda message: message.text == "Всі користувачі в базі")
    async def cmd_all_users(message: types.Message, state: FSMContext):
        await message.answer("Всі користувачі і їхні ip які тільки є в базі")

    @router.message(lambda message: message.text == "Відвідувачі")
    async def cmd_all_users(message: types.Message, state: FSMContext):
        await message.answer("Всі користувачі і їхні ip які тільки є в базі")

    @router.message(lambda message: message.text == "Забанить користувача")
    async def cmd_ban_user(message: types.Message, state: FSMContext):
        await message.answer("Вибери користувача який буде заблокований")


    @router.message(lambda message: message.text == "Видалити значення")
    async def cmd_delete_data(message: types.Message, state: FSMContext):
        await message.answer("Вибери значення як потрібно видалити")


    @router.message(lambda message: message.text == "Змінити значення")
    async def cmd_change_data(message: types.Message, state: FSMContext):
        await message.answer("Вибери значення яке буде змінино")