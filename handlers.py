# -*- coding: utf-8 -*-
"""
handlers.py — обработчики команд бота "Keep" (Бот для муравьёв).

Команды:
    /start          — приветствие
    /help           — список команд
    /keep <текст>   — сохранить заметку
    /list           — показать все заметки
    /delete <номер> — удалить заметку по порядковому номеру
"""

import html
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import config
import database

logger = logging.getLogger(__name__)

# Роутер для всех хэндлеров бота
router = Router()

# Текст справки со списком команд
HELP_TEXT = (
    "🐜 <b>Keep — бот для муравьёв и не только!</b>\n\n"
    "Мои команды:\n"
    "/start — приветствие\n"
    "/help — этот список команд\n"
    "/keep &lt;текст&gt; — сохранить заметку\n"
    "/list — показать все заметки\n"
    "/delete &lt;номер&gt; — удалить заметку по номеру из /list\n\n"
    "Пример: <code>/keep Купить аренибарбуса для колонии</code>"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start — отправляет приветствие."""
    user_name = message.from_user.first_name or "друг"
    try:
        await message.answer(
            f"👋 Привет, {html.escape(user_name)}!\n\n"
            "Я <b>Keep</b> — бот для муравьёв 🐜. "
            "Сохраняй заметки о своих колониях, кормёжках и планах — я ничего не забуду!\n\n"
            f"Напиши {HELP_TEXT}",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка в обработчике /start (chat_id=%s)", message.chat.id)
        await message.answer("Произошла ошибка. Попробуйте ещё раз позже.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help — показывает список команд."""
    try:
        await message.answer(HELP_TEXT, parse_mode="HTML")
    except Exception:
        logger.exception("Ошибка в обработчике /help (chat_id=%s)", message.chat.id)
        await message.answer("Произошла ошибка. Попробуйте ещё раз позже.")


@router.message(Command("keep"))
async def cmd_keep(message: Message) -> None:
    """Обработчик команды /keep <текст> — сохраняет заметку в SQLite."""
    try:
        # Извлекаем текст после команды: "/keep мой текст" -> "мой текст"
        text = message.text.split(maxsplit=1)[1].strip() if " " in (message.text or "") else ""

        if not text:
            await message.answer(
                "⚠️ Укажите текст заметки, например:\n"
                "<code>/keep Покормить колонию мёдом</code>",
                parse_mode="HTML",
            )
            return

        if len(text) > config.MAX_NOTE_LENGTH:
            await message.answer(
                f"⚠️ Заметка слишком длинная (максимум {config.MAX_NOTE_LENGTH} символов)."
            )
            return

        note_id = database.add_note(message.from_user.id, text)
        total = database.count_notes(message.from_user.id)
        await message.answer(
            f"✅ Заметка №{note_id} сохранена! "
            f"Всего у вас заметок: {total}."
        )
    except Exception:
        logger.exception("Ошибка в обработчике /keep (chat_id=%s)", message.chat.id)
        await message.answer("❌ Не удалось сохранить заметку. Попробуйте ещё раз позже.")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    """Обработчик команды /list — показывает все заметки пользователя."""
    try:
        notes = database.get_notes(message.from_user.id)

        if not notes:
            await message.answer("📭 У вас пока нет заметок. Сохраните первую: /keep <текст>")
            return

        lines = [f"📒 <b>Ваши заметки ({len(notes)}):</b>\n"]
        for index, note in enumerate(notes, start=1):
            # Экранируем HTML, чтобы текст заметки не сломал разметку сообщения
            safe_text = html.escape(note["text"])
            lines.append(
                f"<b>{index}.</b> {safe_text}\n"
                f"<i>🗓 {note['created_at']}</i>\n"
            )

        # Telegram ограничивает длину сообщения 4096 символами — режем при необходимости
        result = "\n".join(lines)
        if len(result) > config.MAX_NOTE_LENGTH:
            result = result[: config.MAX_NOTE_LENGTH - 3] + "..."
            lines.append("⚠️ Список обрезан из-за ограничения длины сообщения.")

        await message.answer(result, parse_mode="HTML")
    except Exception:
        logger.exception("Ошибка в обработчике /list (chat_id=%s)", message.chat.id)
        await message.answer("❌ Не удалось получить список заметок. Попробуйте ещё раз позже.")


@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    """Обработчик команды /delete <номер> — удаляет заметку по порядковому номеру."""
    try:
        args = (message.text or "").split(maxsplit=1)

        if len(args) < 2:
            await message.answer(
                "⚠️ Укажите номер заметки, например:\n"
                "<code>/delete 2</code>\n\nНомера видны в команде /list.",
                parse_mode="HTML",
            )
            return

        # Проверяем, что аргумент — целое положительное число
        try:
            number = int(args[1].strip())
            if number < 1:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Номер заметки должен быть целым числом больше нуля.")
            return

        deleted_text = database.delete_note(message.from_user.id, number)

        if deleted_text is None:
            total = database.count_notes(message.from_user.id)
            await message.answer(
                f"⚠️ Заметки с номером {number} не найдено.\n"
                f"У вас всего заметок: {total}. Посмотреть список: /list"
            )
            return

        await message.answer(
            f"🗑 Заметка №{number} удалена:\n<i>{html.escape(deleted_text)}</i>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка в обработчике /delete (chat_id=%s)", message.chat.id)
        await message.answer("❌ Не удалось удалить заметку. Попробуйте ещё раз позже.")


@router.message()
async def fallback_handler(message: Message) -> None:
    """Обработчик всех прочих сообщений — подсказывает, как пользоваться ботом."""
    try:
        await message.answer(
            "🤔 Я вас не понял. Напишите /help, чтобы посмотреть список моих команд."
        )
    except Exception:
        logger.exception("Ошибка в fallback-обработчике (chat_id=%s)", message.chat.id)
