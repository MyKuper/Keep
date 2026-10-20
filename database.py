# -*- coding: utf-8 -*-
"""
database.py — слой работы с базой данных SQLite для бота "Keep".

Таблица notes:
    id         — уникальный номер заметки (AUTOINCREMENT)
    user_id    — Telegram ID пользователя
    text       — текст заметки
    created_at — дата и время создания
"""

import logging
import sqlite3
from typing import List, Optional, Tuple

import config

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Возвращает соединение с базой данных SQLite."""
    conn = sqlite3.connect(config.DB_PATH)
    # Возвращаем строки как dict-подобные записи, чтобы обращаться по именам колонок
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создаёт таблицу notes, если её ещё нет."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    text       TEXT    NOT NULL,
                    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
                """
            )
            # Индекс для быстрого поиска заметок конкретного пользователя
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id)"
            )
        logger.info("База данных инициализирована: %s", config.DB_PATH)
    except sqlite3.Error:
        logger.exception("Ошибка при инициализации базы данных")
        raise


def add_note(user_id: int, text: str) -> int:
    """
    Сохраняет новую заметку.

    :param user_id: Telegram ID пользователя
    :param text: текст заметки
    :return: id созданной записи
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (user_id, text) VALUES (?, ?)",
                (user_id, text),
            )
            note_id = cursor.lastrowid
            logger.info("Добавлена заметка id=%s для пользователя %s", note_id, user_id)
            return note_id
    except sqlite3.Error:
        logger.exception("Ошибка при добавлении заметки (user_id=%s)", user_id)
        raise


def get_notes(user_id: int) -> List[sqlite3.Row]:
    """Возвращает все заметки пользователя в порядке добавления."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, text, created_at FROM notes WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
            return rows
    except sqlite3.Error:
        logger.exception("Ошибка при получении заметок (user_id=%s)", user_id)
        raise


def delete_note(user_id: int, note_number: int) -> Optional[str]:
    """
    Удаляет заметку по её порядковому номеру у данного пользователя.

    :param user_id: Telegram ID пользователя
    :param note_number: порядковый номер заметки (1, 2, 3...) из списка /list
    :return: текст удалённой заметки или None, если заметка не найдена
    """
    try:
        with get_connection() as conn:
            # Находим id реальной записи по порядковому номеру среди заметок пользователя
            row: Optional[sqlite3.Row] = conn.execute(
                """
                SELECT id, text FROM notes
                WHERE user_id = ?
                ORDER BY id
                LIMIT 1 OFFSET ?
                """,
                (user_id, note_number - 1),
            ).fetchone()

            if row is None:
                return None

            conn.execute("DELETE FROM notes WHERE id = ?", (row["id"],))
            logger.info(
                "Удалена заметка id=%s (номер %s) у пользователя %s",
                row["id"], note_number, user_id,
            )
            return row["text"]
    except sqlite3.Error:
        logger.exception(
            "Ошибка при удалении заметки (user_id=%s, номер=%s)", user_id, note_number
        )
        raise


def count_notes(user_id: int) -> int:
    """Возвращает количество заметок пользователя."""
    try:
        with get_connection() as conn:
            (total,) = conn.execute(
                "SELECT COUNT(*) FROM notes WHERE user_id = ?", (user_id,)
            ).fetchone()
            return total
    except sqlite3.Error:
        logger.exception("Ошибка при подсчёте заметок (user_id=%s)", user_id)
        raise
