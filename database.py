# database.py — работа с SQLite для бота-маркетплейса муравьёв Keep
# Таблицы: users, categories, products, favorites, orders (+ старые notes для совместимости)

import logging
import sqlite3
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)


# ------------------------------ Соединение ------------------------------ #


@contextmanager
def get_conn():
    """Контекстный менеджер соединения: commit при успехе, rollback при ошибке."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # доступ к колонкам по именам
    conn.execute("PRAGMA foreign_keys = ON")  # включаем контроль внешних ключей
    try:
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        logger.exception("Ошибка базы данных (rollback выполнен)")
        raise
    finally:
        conn.close()


# ------------------------------ Схема БД ------------------------------ #

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    role TEXT NOT NULL DEFAULT 'buyer',       -- 'buyer' | 'seller' | 'admin'
    community_name TEXT,                      -- название сообщества (для продавцов)
    contact TEXT,                             -- контакт продавца для покупателей
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,                -- 'Messor', 'Camponotus', ...
    difficulty TEXT DEFAULT 'easy'            -- 'easy' | 'medium' | 'hard'
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER REFERENCES categories(id),
    species TEXT NOT NULL,                    -- 'Messor structor'
    queen_count INTEGER DEFAULT 1,            -- количество маток
    worker_count INTEGER DEFAULT 0,           -- количество рабочих
    price INTEGER NOT NULL DEFAULT 0,         -- цена в рублях
    description TEXT,
    photo_file_id TEXT,                       -- file_id фото в Telegram
    is_active BOOLEAN DEFAULT 1,              -- товар в продаже
    views INTEGER DEFAULT 0,                  -- просмотры карточки
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    status TEXT DEFAULT 'new',                -- 'new' | 'contacted' | 'closed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Совместимость с первой версией бота (заметки): не удаляем исторические данные
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Справочник родов муравьёв со сложностью содержания (заполняется один раз)
DEFAULT_CATEGORIES = [
    ("Messor", "easy"),        # жнецы — идеальный старт для новичков
    ("Lasius", "easy"),
    ("Pheidole", "easy"),
    ("Formica", "medium"),
    ("Camponotus", "medium"),  # плотники
    ("Atta", "hard"),          # листорезы
    ("Odontomachus", "hard"),  # муравьи с ловчими жвалами
    ("Myrmecia", "hard"),      # бульдоговые — опасные
]


def init_db() -> None:
    """Создаёт таблицы и справочник категорий. Идемпотентно, вызывается при старте."""
    try:
        with get_conn() as conn:
            conn.executescript(SCHEMA)
            count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if count == 0:
                conn.executemany(
                    "INSERT INTO categories (name, difficulty) VALUES (?, ?)",
                    DEFAULT_CATEGORIES,
                )
                logger.info("Добавлено %d категорий по умолчанию", len(DEFAULT_CATEGORIES))
        logger.info("База данных инициализирована: %s", DB_PATH)
    except sqlite3.Error:
        logger.exception("Критическая ошибка инициализации БД")
        raise


# ------------------------------ Пользователи ------------------------------ #


def get_user(telegram_id: int) -> Optional[dict]:
    """Находит пользователя по telegram_id; возвращает dict или None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def upsert_user(telegram_id: int, username: Optional[str]) -> dict:
    """Создаёт пользователя при первом обращении, всегда возвращает актуальную запись."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, role) VALUES (?, ?, 'buyer')",
            (telegram_id, username),
        )
        conn.execute(
            "UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id)
        )
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row)


def set_role(telegram_id: int, role: str) -> None:
    """Меняет роль пользователя ('buyer' | 'seller')."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id))


def set_seller_profile(telegram_id: int, community_name: str, contact: str) -> None:
    """Сохраняет название сообщества и контакт, ставит роль 'seller'."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = 'seller', community_name = ?, contact = ? "
            "WHERE telegram_id = ?",
            (community_name, contact, telegram_id),
        )


def get_user_by_internal_id(internal_id: int) -> Optional[dict]:
    """Внутренний id пользователя -> запись (для связей products/orders)."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (internal_id,)).fetchone()
        return dict(row) if row else None


# ------------------------------ Категории ------------------------------ #


def get_categories() -> list:
    """Список категорий [(id, name, difficulty), ...]."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, difficulty FROM categories ORDER BY name"
        ).fetchall()
        return [tuple(r) for r in rows]


def get_category_difficulty(category_id: Optional[int]) -> str:
    """Сложность категории по id (для отображения в карточке)."""
    if not category_id:
        return "unknown"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT difficulty FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return row["difficulty"] if row else "unknown"


# ------------------------------ Товары ------------------------------ #


def add_product(seller_internal_id: int, category_id: Optional[int], species: str,
                queen_count: int, worker_count: int, price: int,
                description: str, photo_file_id: Optional[str]) -> int:
    """Публикует новый товар, возвращает его id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO products
               (seller_id, category_id, species, queen_count, worker_count,
                price, description, photo_file_id, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (seller_internal_id, category_id, species, queen_count,
             worker_count, price, description, photo_file_id),
        )
        logger.info("Товар #%s '%s' опубликован (продавец internal_id=%s)",
                    cur.lastrowid, species, seller_internal_id)
        return cur.lastrowid


def get_product(product_id: int) -> Optional[dict]:
    """Карточка товара + данные продавца + категория (один JOIN-запрос)."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT p.*, u.telegram_id AS seller_telegram_id,
                      u.username AS seller_username, u.community_name,
                      u.contact AS seller_contact,
                      c.name AS category_name, c.difficulty
               FROM products p
               JOIN users u ON u.id = p.seller_id
               LEFT JOIN categories c ON c.id = p.category_id
               WHERE p.id = ?""",
            (product_id,),
        ).fetchone()
        return dict(row) if row else None


def increment_views(product_id: int) -> None:
    """+1 просмотр карточки товара."""
    with get_conn() as conn:
        conn.execute("UPDATE products SET views = views + 1 WHERE id = ?", (product_id,))


def _apply_filters(filters: Optional[dict]) -> tuple:
    """Строит SQL-условия и параметры для фильтров каталога."""
    sql = ""
    params: list = []
    if filters:
        if filters.get("difficulty"):
            sql += " AND c.difficulty = ?"
            params.append(filters["difficulty"])
        if filters.get("price") == "low":
            sql += " AND p.price < 500"
        elif filters.get("price") == "mid":
            sql += " AND p.price BETWEEN 500 AND 1500"
        elif filters.get("price") == "high":
            sql += " AND p.price > 1500"
        if filters.get("size") == "small":
            sql += " AND p.worker_count <= 50"
        elif filters.get("size") == "medium":
            sql += " AND p.worker_count BETWEEN 51 AND 500"
        elif filters.get("size") == "big":
            sql += " AND p.worker_count > 500"
    return sql, params


_BASE_SELECT = """FROM products p
                  LEFT JOIN categories c ON c.id = p.category_id
                  WHERE p.is_active = 1"""


def list_products(filters: Optional[dict] = None, offset: int = 0, limit: int = 5) -> list:
    """
    Активные товары с фильтрами и пагинацией.
    Возвращает [(id, species, price, queen_count, worker_count, category_name, difficulty), ...]
    """
    cond, params = _apply_filters(filters)
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT p.id, p.species, p.price, p.queen_count, p.worker_count,
                       c.name AS category_name, c.difficulty
                {_BASE_SELECT} {cond}
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()
        return [tuple(r) for r in rows]


def count_products(filters: Optional[dict] = None) -> int:
    """Число активных товаров под текущие фильтры (для пагинации)."""
    cond, params = _apply_filters(filters)
    with get_conn() as conn:
        return conn.execute(
            f"SELECT COUNT(*) {_BASE_SELECT} {cond}", params
        ).fetchone()[0]


def search_products(query: str, limit: int = 20) -> list:
    """Поиск по названию вида / описанию / категории (без учёта регистра)."""
    # Экранируем спецсимволы LIKE (% и _), чтобы пользовательский запрос
    # не мог подменить шаблон поиска; экранирование через ESCAPE '\'.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped}%"
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.id, p.species, p.price, p.queen_count, p.worker_count,
                      c.name AS category_name, c.difficulty
               FROM products p LEFT JOIN categories c ON c.id = p.category_id
               WHERE p.is_active = 1 AND (p.species LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')
               ORDER BY p.price ASC LIMIT ?""",
            (like, like, like, limit),
        ).fetchall()
        return [tuple(r) for r in rows]


def seller_products(internal_user_id: int) -> list:
    """Все товары продавца [(id, species, price, is_active), ...]."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, species, price, is_active FROM products WHERE seller_id = ? "
            "ORDER BY created_at DESC",
            (internal_user_id,),
        ).fetchall()
        return [tuple(r) for r in rows]


def set_product_active(product_id: int, active: bool) -> None:
    """Снять товар с продажи / разместить снова."""
    with get_conn() as conn:
        conn.execute("UPDATE products SET is_active = ? WHERE id = ?",
                     (int(active), product_id))


def delete_product(product_id: int) -> None:
    """Полное удаление товара вместе с избранным и заказами на него."""
    with get_conn() as conn:
        conn.execute("DELETE FROM favorites WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ------------------------------ Избранное ------------------------------ #


def toggle_favorite(user_internal_id: int, product_id: int) -> bool:
    """Добавляет/убирает избранное. True = товар теперь В избранном."""
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_internal_id, product_id),
        ).fetchone()
        if exists:
            conn.execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
                         (user_internal_id, product_id))
            return False
        conn.execute("INSERT INTO favorites (user_id, product_id) VALUES (?, ?)",
                     (user_internal_id, product_id))
        return True


def is_favorite(user_internal_id: int, product_id: int) -> bool:
    """В избранном ли товар у пользователя."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_internal_id, product_id),
        ).fetchone() is not None


def favorite_products(user_internal_id: int) -> list:
    """Избранные товары пользователя (только активные)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.id, p.species, p.price, p.queen_count, p.worker_count,
                      c.name AS category_name, c.difficulty
               FROM favorites f
               JOIN products p ON p.id = f.product_id
               LEFT JOIN categories c ON c.id = p.category_id
               WHERE f.user_id = ? AND p.is_active = 1
               ORDER BY f.created_at DESC""",
            (user_internal_id,),
        ).fetchall()
        return [tuple(r) for r in rows]


# ------------------------------ Запросы на покупку (лиды) ------------------------------ #


def create_order(buyer_internal_id: int, product_id: int) -> int:
    """Создаёт запрос 'хочу купить', возвращает id заказа."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (buyer_id, product_id) VALUES (?, ?)",
            (buyer_internal_id, product_id),
        )
        return cur.lastrowid


def find_order(buyer_internal_id: int, product_id: int) -> Optional[dict]:
    """Ищет существующий заказ покупателя на товар (чтобы не дублировать)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE buyer_id = ? AND product_id = ? "
            "AND status != 'closed' ORDER BY id DESC LIMIT 1",
            (buyer_internal_id, product_id),
        ).fetchone()
        return dict(row) if row else None


def get_orders_for_buyer(buyer_internal_id: int) -> list:
    """Запросы покупателя [(order_id, species, price, status, community), ...]."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT o.id, p.species, p.price, o.status, COALESCE(u.community_name, 'Продавец')
               FROM orders o
               JOIN products p ON p.id = o.product_id
               JOIN users u ON u.id = p.seller_id
               WHERE o.buyer_id = ? ORDER BY o.created_at DESC""",
            (buyer_internal_id,),
        ).fetchall()
        return [tuple(r) for r in rows]


def mark_order_contacted(order_id: int) -> None:
    """Статус заказа -> 'contacted' (покупатель получил контакты)."""
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status = 'contacted' WHERE id = ?", (order_id,))


# ------------------------------ Статистика ------------------------------ #


def stats_overall() -> dict:
    """Общая статистика маркетплейса (для админа)."""
    with get_conn() as conn:
        return {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "sellers": conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='seller'").fetchone()[0],
            "products": conn.execute(
                "SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "new_orders": conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0],
        }


def stats_for_seller(seller_internal_id: int) -> dict:
    """Статистика конкретного продавца: товары, просмотры, запросы."""
    with get_conn() as conn:
        return {
            "products": conn.execute(
                "SELECT COUNT(*) FROM products WHERE seller_id=?",
                (seller_internal_id,)).fetchone()[0],
            "active": conn.execute(
                "SELECT COUNT(*) FROM products WHERE seller_id=? AND is_active=1",
                (seller_internal_id,)).fetchone()[0],
            "views": conn.execute(
                "SELECT COALESCE(SUM(views),0) FROM products WHERE seller_id=?",
                (seller_internal_id,)).fetchone()[0],
            "orders": conn.execute(
                """SELECT COUNT(*) FROM orders o
                   JOIN products p ON p.id=o.product_id
                   WHERE p.seller_id=?""",
                (seller_internal_id,)).fetchone()[0],
        }
