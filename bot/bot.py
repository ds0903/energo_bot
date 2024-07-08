import asyncio
import logging
# import os

# import time
from aiogram import Bot, Dispatcher
from handlers import comands
from handlers import admin

# from handlers.comands import start_main


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


# async def start_main_check(message: types.Message):
#     await start_main(message)


async def main():
    await delete_webhook()
    await dp.start_polling(bot)
    # await start_main_check(message=None)


if __name__ == "__main__":
    asyncio.run(main())
