# import logging
# from aiogram import Bot, Dispatcher
# from aiogram.filters.command import Command
# from aiogram.types import Message
# from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
# from aiohttp import web

# API_TOKEN = '7071404047:AAGzzQ961DiCb9tdypN9FndjwNxobfa7G4Q'
# WEBHOOK_PATH = '/test_bot/'
# WEBHOOK_URL = 'https://ds0903.alwaysdata.net/' + WEBHOOK_PATH

# logging.basicConfig(level=logging.INFO)

# bot = Bot(token=API_TOKEN)
# dp = Dispatcher()

# @dp.message(Command("start"))
# async def send_welcome(message: Message):
#     await message.reply("Привет! Я твой бот на вебхуках!")

# @dp.message(lambda message: message.text.lower() == 'привет')
# async def greet(message: Message):
#     await message.reply("Привет, как дела?")

# async def on_startup(app):
#     await bot.set_webhook(WEBHOOK_URL)

# async def on_shutdown(app):
#     await bot.delete_webhook()
#     await bot.session.close()

# app = web.Application()
# app.router.add_route('POST', WEBHOOK_PATH, SimpleRequestHandler(bot=bot, dispatcher=dp))
# app.on_startup.append(on_startup)
# app.on_shutdown.append(on_shutdown)

# if __name__ == '__main__':
#     setup_application(app, dp)
#     web.run_app(app, host='::', port=8080)
