# keyboards.py — Inline и Reply клавиатуры маркетплейса муравьёв Keep

from typing import Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ------------------------------ Главное меню ------------------------------ #


def role_select_kb() -> InlineKeyboardMarkup:
    """Выбор роли при первой команде /start."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="🛒 Я покупатель", callback_data="role:buyer"),
        InlineKeyboardButton(text="🏪 Я продавец", callback_data="role:seller"),
    )
    return kb


def buyer_menu_kb() -> ReplyKeyboardMarkup:
    """Reply-меню покупателя: Каталог / Поиск / Избранное / Мои запросы."""
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add(
        KeyboardButton(text="📋 Каталог"),
        KeyboardButton(text="🔍 Поиск"),
        KeyboardButton(text="⭐ Избранное"),
        KeyboardButton(text="📦 Мои запросы"),
    )
    return kb


def seller_menu_kb() -> ReplyKeyboardMarkup:
    """Reply-меню продавца: Добавить / Мои товары / Статистика / Настройки."""
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add(
        KeyboardButton(text="➕ Добавить"),
        KeyboardButton(text="📦 Мои товары"),
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="⚙️ Настройки"),
    )
    return kb


# ------------------------------ Каталог ------------------------------ #


def catalog_filters_kb(active: Optional[dict] = None) -> InlineKeyboardMarkup:
    """
    Панель фильтров каталога.
    active — текущие активные фильтры {ключ: значение}, подсвечиваются галочкой.
    """
    active = active or {}
    rows = [
        # Сложность
        [
            InlineKeyboardButton(
                text=("✅ " if active.get("difficulty") == d else "") + label,
                callback_data=f"flt:difficulty:{d}",
            )
            for d, label in [("easy", "Лёгкие"), ("medium", "Средние"), ("hard", "Сложные")]
        ],
        # Цена
        [
            InlineKeyboardButton(
                text=("✅ " if active.get("price") == p else "") + label,
                callback_data=f"flt:price:{p}",
            )
            for p, label in [("low", "до 500₽"), ("mid", "500–1500₽"), ("high", "1500₽+")]
        ],
        # Размер колонии
        [
            InlineKeyboardButton(
                text=("✅ " if active.get("size") == s else "") + label,
                callback_data=f"flt:size:{s}",
            )
            for s, label in [("small", "Маленькие"), ("medium", "Средние"), ("big", "Крупные")]
        ],
        # Действия
        [
            InlineKeyboardButton(text="📋 Показать каталог", callback_data="flt:apply"),
            InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="flt:reset"),
        ],
    ]
    kb = InlineKeyboardMarkup()
    for row in rows:
        kb.row(*row)
    return kb


def catalog_pagination_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Пагинация списка товаров: ◀ назад / страница / вперёд ▶ / фильтр."""
    kb = InlineKeyboardMarkup(row_width=3)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"pg:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pg:noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"pg:{page + 1}"))
    kb.row(*nav_row)
    kb.row(InlineKeyboardButton(text="🔍 Фильтры", callback_data="filters"))
    return kb


def product_buttons_kb(product_id: int, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Кнопки карточки товара: купить / избранное / связаться / назад."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="🛒 Хочу купить", callback_data=f"buy:{product_id}"),
        InlineKeyboardButton(
            text="⭐ Убрать из избранного" if is_favorite else "⭐ В избранное",
            callback_data=f"fav:{product_id}",
        ),
        InlineKeyboardButton(text="📞 Связаться", callback_data=f"contact:{product_id}"),
        InlineKeyboardButton(text="◀ К каталогу", callback_data="back:catalog"),
    )
    return kb


def categories_kb(categories: list) -> InlineKeyboardMarkup:
    """Выбор категории при добавлении товара (список [(id, name), ...])."""
    kb = InlineKeyboardMarkup(row_width=2)
    for cid, name in categories:
        kb.insert(InlineKeyboardButton(text=name, callback_data=f"cat:{cid}"))
    return kb


def skip_kb(next_callback: str = "skip:photo") -> InlineKeyboardMarkup:
    """Кнопка 'пропустить' для необязательных шагов (например, фото)."""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="⏭ Пропустить", callback_data=next_callback))
    return kb


def my_products_kb(products: list) -> InlineKeyboardMarkup:
    """Список собственных товаров продавца с кнопками управления."""
    kb = InlineKeyboardMarkup(row_width=1)
    for pid, species, is_active in products:
        status = "🟢" if is_active else "🔴"
        kb.add(InlineKeyboardButton(f"{status} {species}", callback_data=f"myp:{pid}"))
    return kb


def manage_product_kb(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Управление одним товаром: снять/разместить, удалить, назад."""
    toggle_label = "🔴 Снять с продажи" if is_active else "🟢 Разместить снова"
    toggle_action = "off" if is_active else "on"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text=toggle_label, callback_data=f"tog:{toggle_action}:{product_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{product_id}"),
        InlineKeyboardButton(text="◀ Назад к списку", callback_data="seller:products"),
    )
    return kb
