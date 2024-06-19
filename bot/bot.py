import asyncio
import logging
import os
import time
from aiogram import Bot, Dispatcher
from handlers import comands

logging.basicConfig(level=logging.INFO)
# Объект бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
# # Змінна що відповідає за таймер потім розповім
# dp["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

dp.include_router(comands.router)


# ## НЕ ЧІПАЙ бо буде торба !!! ###
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

# ## НЕ ЧІПАЙ бо буде торба !!! ###
