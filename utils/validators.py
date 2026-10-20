# utils/validators.py — валидация пользовательского ввода (числа, тексты, контакты)

import re

# Диапазоны разумных значений для маркетплейса муравьёв
MIN_PRICE, MAX_PRICE = 1, 1_000_000          # цена в рублях
MIN_COUNT, MAX_COUNT = 0, 100_000            # матки/рабочие
MAX_TEXT_LEN = 1000                          # описание товара
MAX_NAME_LEN = 100                           # вид / название сообщества


def parse_int(text: str) -> int | None:
    """Превращает строку в целое число; None, если это не число."""
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None


def valid_price(text: str) -> tuple[bool, str]:
    """Проверяет цену. Возвращает (ok, сообщение_об_ошибке)."""
    n = parse_int(text)
    if n is None:
        return False, "❌ Введите цену целым числом, например: 800"
    if not (MIN_PRICE <= n <= MAX_PRICE):
        return False, f"❌ Цена должна быть от {MIN_PRICE} до {MAX_PRICE}₽"
    return True, ""


def valid_count(text: str, label: str) -> tuple[bool, str]:
    """Проверяет количество маток/рабочих."""
    n = parse_int(text)
    if n is None:
        return False, f"❌ Введите {label} целым числом"
    if not (MIN_COUNT <= n <= MAX_COUNT):
        return False, f"❌ {label} должно быть от {MIN_COUNT} до {MAX_COUNT}"
    return True, ""


def valid_species(text: str) -> tuple[bool, str]:
    """Проверяет название вида (непустой, без цифр-одиночек, разумная длина)."""
    t = text.strip()
    if not t:
        return False, "❌ Название вида не может быть пустым"
    if len(t) > MAX_NAME_LEN:
        return False, f"❌ Слишком длинно (макс. {MAX_NAME_LEN} символов)"
    return True, ""


def valid_description(text: str) -> tuple[bool, str]:
    """Проверяет описание товара."""
    if len(text) > MAX_TEXT_LEN:
        return False, f"❌ Описание длиннее {MAX_TEXT_LEN} символов, сократите"
    return True, ""


def valid_contact(text: str) -> tuple[bool, str]:
    """
    Контакт продавца: @username Telegram, ссылка t.me/... или телефон.
    """
    t = text.strip()
    tg_username = re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]{4,31}", t)
    tme_link = re.fullmatch(r"(https?://)?t\.me/[A-Za-z][A-Za-z0-9_]{4,31}", t)
    phone = re.fullmatch(r"\+?[\d\s\-()]{7,18}", t)
    if tg_username or tme_link or phone:
        return True, ""
    return False, (
        "❌ Контакт непонятен. Форматы:\n"
        "@username\nhttps://t.me/username\n+7 900 000-00-00"
    )


def normalize_contact(text: str) -> str:
    """Приводит контакт к единому виду (@username из t.me-ссылки и т.п.)."""
    t = text.strip()
    m = re.fullmatch(r"(https?://)?t\.me/([A-Za-z0-9_]+)", t)
    if m:
        return f"@{m.group(2)}"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", t):  # username без @
        return f"@{t}"
    return t
