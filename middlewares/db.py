# middlewares/db.py — middleware, регистрирующий пользователя в БД при любом апдейте

import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

logger = logging.getLogger(__name__)


class DbUserMiddleware(BaseMiddleware):
    """
    Подмешивает в data обработчиков ключ 'db_user' — запись пользователя из SQLite.
    При первом обращении автоматически создаёт пользователя (роль buyer по умолчанию).
    Работает для message и callback_query.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        from database import get_user, upsert_user  # локальный импорт против цикла

        user: User | None = data.get("event_from_user")
        if user is not None and not user.is_bot:
            try:
                db_user = get_user(user.id)
                if db_user is None:
                    db_user = upsert_user(user.id, user.username)
                    logger.info("Новый пользователь в БД: id=%s @%s", user.id, user.username)
                data["db_user"] = db_user
            except Exception:
                logger.exception("Ошибка middleware БД для пользователя %s", user.id)
                data["db_user"] = None

        # Глобальная блокировка: забаненные пользователи не доходят до хендлеров
        db_user = data.get("db_user")
        if db_user and db_user.get("role") == "blocked":
            logger.info("Заблокированный пользователь %s обслужен не был", user.id)
            return

        return await handler(event, data)
