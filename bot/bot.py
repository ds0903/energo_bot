import asyncio
import logging
from aiogram.filters.command import Command
from handlers.logic import list_admin_info
# import time
from aiogram import Bot, Dispatcher, types
from handlers import comands
from handlers import admin


logging.basicConfig(level=logging.INFO)

# bot = Bot(token=os.getenv("BOT_TOKEN"))
bot = Bot(token="6739109992:AAFGEIXK2knrwgLL8V2_a8r6wOdgFaMab6o")
# bot = Bot(token='7068876850:AAFZxGPnwORoVuATWMPnhS9xCaYr8UaaolQ') # На серваке
dp = Dispatcher()


async def delete_webhook():
    await bot.delete_webhook()


# dp["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

dp.include_router(comands.router)
dp.include_router(admin.router)


@dp.message(Command("remind"))
async def remind(message: types.Message):
    if message.from_user.username == "ds0903":
        data = await list_admin_info(status="3")
        for i in data:
            (
                id,
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
                current_time

            ) = i

            # user_id = 5987399475
            await bot.send_message(chat_id=user_id, text="Вийшла нова версія бота\nБудьласка перезавантажте функції бота вводом команди /restart\n\nДля перегляду змін, введіть команду /version")
    else:
        await message.answer("Доступ заборонено")

async def main():
    await delete_webhook()
    await dp.start_polling(bot)
    # await start_main_check(message=None)


if __name__ == "__main__":
    asyncio.run(main())
