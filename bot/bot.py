import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters.command import Command
from dotenv import load_dotenv
from handlers import admin, comands, standard
from handlers.logic import init_db, list_admin_info
from monitor import tuya_monitor
from tuya import get_client

load_dotenv()  # токени та ключі беруться з файлу .env у корені проєкту

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.environ["BOT_TOKEN"])
dp = Dispatcher()

dp.include_router(comands.router)
dp.include_router(standard.router)
dp.include_router(admin.router)


@dp.message(Command("remind"))
async def remind(message: types.Message):
    if not admin.is_admin(message):
        await message.answer("Доступ заборонено")
        return

    for row in await list_admin_info(status="3"):
        user_id = row[1]
        try:
            await bot.send_message(
                chat_id=user_id,
                text="Вийшла нова версія бота!\nДля перегляду змін введіть команду /version.\nБудь ласка, перезавантажте функції бота, ввівши команду /restart.\n",
            )
        except TelegramAPIError:
            # наприклад, користувач заблокував бота - не зупиняємо розсилку
            logger.exception("Не вдалося надіслати нагадування користувачу %s", user_id)


async def main():
    await init_db()
    await bot.delete_webhook()

    client = get_client()
    monitor_task = None
    if client is None:
        logger.warning(
            "TUYA_ACCESS_ID / TUYA_ACCESS_SECRET не задані в .env - "
            "моніторинг розеток Tuya (стандартний режим) вимкнено"
        )
    else:
        monitor_task = asyncio.create_task(tuya_monitor(bot, client))

    try:
        await dp.start_polling(bot)
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
