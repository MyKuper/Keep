# utils/filters.py — логика фильтрации и форматирования товаров каталога

from html import escape
from typing import Optional

# Человекочитаемые подписи значений фильтров
DIFFICULTY_LABELS = {"easy": "лёгкие 🟢", "medium": "средние 🟡", "hard": "сложные 🔴"}
PRICE_LABELS = {"low": "до 500₽", "mid": "500–1500₽", "high": "от 1500₽"}
SIZE_LABELS = {"small": "маленькие", "medium": "средние", "big": "крупные"}


def describe_filters(filters: Optional[dict]) -> str:
    """Строит человекочитаемую строку активных фильтров для заголовка каталога."""
    if not filters:
        return ""
    parts = []
    if filters.get("difficulty"):
        parts.append(DIFFICULTY_LABELS.get(filters["difficulty"], filters["difficulty"]))
    if filters.get("price"):
        parts.append(PRICE_LABELS.get(filters["price"], filters["price"]))
    if filters.get("size"):
        parts.append(SIZE_LABELS.get(filters["size"], filters["size"]))
    return f" | Фильтры: {', '.join(parts)}" if parts else ""


def format_product_line(product: tuple) -> str:
    """
    Одна строка списка каталога.
    product = (id, species, price, queen_count, worker_count, category_name, difficulty)
    """
    pid, species, price, queens, workers, cat, diff = product
    diff_tag = DIFFICULTY_LABELS.get(diff, "")
    return (
        f"<b>{escape(species)}</b> — {price}₽ 👑{queens} 👷{workers}"
        + (f" <i>[{escape(cat)} · {diff_tag}]</i>" if cat else "")
    )


def build_catalog_text(products: list, page: int, total_pages: int,
                       filters: Optional[dict], total: int) -> str:
    """Текст страницы каталога с пагинацией и учётом фильтров."""
    header = f"🐜 <b>Каталог муравьёв</b> (стр. {page}/{total_pages}, всего {total})"
    desc = describe_filters(filters)
    if desc:
        header += "\n" + desc.replace("| ", "")
    lines = [format_product_line(p) for p in products]
    body = "\n\n".join(lines) if lines else "😔 Пока нет товаров по этим фильтрам."
    return header + "\n\n" + body
