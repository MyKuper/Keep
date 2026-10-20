# -*- coding: utf-8 -*-
"""
bot.py — главный файл бота-маркетплейса муравьёв "Keep".

Запуск:  python bot.py
Токен берётся из .env / переменной окружения BOT_TOKEN (см. config.py).
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

import database as db
from config import BOT_TOKEN
from handlers import routers          # все роутеры (start/admin/seller/buyer)
from middlewares.db import DbUserMiddleware

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Настраивает логирование: уровень INFO, формат с временем и модулем."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),                          # вывод в консоль
            logging.FileHandler("bot.log", encoding="utf-8"),  # и в файл
        ],
    )


async def set_bot_commands(bot: Bot) -> None:
    """Регистрирует меню команд для всех пользователей."""
    commands = [
        BotCommand(command="start", description="🚀 Начать / выбрать роль"),
        BotCommand(command="help", description="❓ Справка по командам"),
        BotCommand(command="catalog", description="📋 Каталог муравьёв"),
        BotCommand(command="search", description="🔍 Поиск по виду"),
        BotCommand(command="favorites", description="⭐ Избранное"),
        BotCommand(command="my_orders", description="📦 Мои запросы"),
        BotCommand(command="add_product", description="➕ Добавить товар (продавец)"),
        BotCommand(command="my_products", description="📦 Мои товары (продавец)"),
        BotCommand(command="stats", description="📊 Статистика (продавец)"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Меню команд установлено")
    except Exception:
        logger.exception("Не удалось установить меню команд (не критично)")


async def main() -> None:
    """Точка входа: бот, диспетчер, middleware, роутеры, запуск polling."""
    setup_logging()

    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit(
            "❌ Токен не задан! Положите его в файл .env (BOT_TOKEN=...) "
            "или задайте переменную окружения."
        )

    # Инициализация SQLite (создание таблиц + справочника категорий)
    db.init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),  # HTML по умолчанию
    )
    dp = Dispatcher()

    # Middleware: каждый апдейт автоматически регистрирует пользователя в БД
    dp.message.middleware(DbUserMiddleware())
    dp.callback_query.middleware(DbUserMiddleware())

    # Подключаем все роутеры (start -> admin -> seller -> buyer)
    for router in routers:
        dp.include_router(router)

    await set_bot_commands(bot)

    logger.info("🐜 Бот Keep (маркетплейс муравьёв) запущен. Ожидаю сообщения...")
    try:
        await dp.start_polling(bot)   # long polling — без вебсервера и белого IP
    finally:
        await bot.session.close()
        logger.info("Бот остановлен, сессия закрыта")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем.")
