import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from dtek_schedule import schedule_loop
from handlers import admin, comands, common, standard
from handlers.logic import init_db
from monitor import tuya_monitor
from settings import extended_mode_enabled, schedule_enabled
from tuya import get_client

load_dotenv()  # токени та ключі беруться з файлу .env у корені проєкту

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.environ["BOT_TOKEN"])
dp = Dispatcher()

# порядок важливий: команди раніше за хендлери станів, а fallback - останнім
dp.include_router(common.router)
dp.include_router(standard.router)
if extended_mode_enabled():
    # розширений режим (моніторинг IP): код збережено, але за замовчуванням вимкнено
    dp.include_router(comands.router)
dp.include_router(admin.router)
dp.include_router(common.fallback_router)


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

    # знімок графіка відключень ДТЕК раз на SCHEDULE_REFRESH_MINUTES (потрібен playwright)
    schedule_task = None
    if schedule_enabled():
        schedule_task = asyncio.create_task(schedule_loop())

    try:
        await dp.start_polling(bot)
    finally:
        for task in (monitor_task, schedule_task):
            if task is not None:
                task.cancel()
        if client is not None:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
