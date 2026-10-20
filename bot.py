# -*- coding: utf-8 -*-
"""
bot.py — главный файл бота "Keep" (Бот для муравьёв).

Запуск: python bot.py
Токен берётся из config.py (или из переменной окружения BOT_TOKEN).
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database
from handlers import router

# Настраиваем логирование: уровень INFO, вывод в консоль с датой и временем
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    """Регистрирует список команд в меню Telegram (для русскоязычных пользователей)."""
    from aiogram.types import BotCommand

    commands = [
        BotCommand(command="start", description="Приветствие"),
        BotCommand(command="help", description="Список команд"),
        BotCommand(command="keep", description="Сохранить заметку"),
        BotCommand(command="list", description="Показать все заметки"),
        BotCommand(command="delete", description="Удалить заметку"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """Точка входа: создаёт бота, инициализирует БД и запускает long polling."""
    # Проверяем, что токен задан
    if not config.BOT_TOKEN or config.BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise RuntimeError(
            "Токен бота не задан! Укажите его в config.py или в переменной окружения BOT_TOKEN."
        )

    # Инициализация базы данных SQLite
    database.init_db()

    # Создаём экземпляр бота с режимом разметки HTML по умолчанию
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Диспетчер (роутер сообщений) и подключение обработчиков из handlers.py
    dp = Dispatcher()
    dp.include_router(router)

    # Регистрируем команды в меню бота
    await set_bot_commands(bot)

    logger.info("Бот Keep запущен. Долгождания (long polling)...")
    try:
        # Запускаем long polling; delete_webhook нужен при переходе с вебхука
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        # Корректно закрываем сессию бота при остановке
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен пользователем.")
    except Exception:
        # Логируем любые фатальные ошибки перед выходом
        logger.exception("Бот аварийно завершился из-за непредвиденной ошибки.")
        raise
