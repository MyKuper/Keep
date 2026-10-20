# states.py — FSM-состояния для многошаговых сценариев бота Keep
# Использование: aiogram.fsm (State, StatesGroup)

from aiogram.fsm.state import State, StatesGroup


class SellerRegStates(StatesGroup):
    """Состояния регистрации продавца (сообщества)."""

    community_name = State()   # Шаг 1: название сообщества
    contact = State()          # Шаг 2: контакт для связи (@username или телефон)


class AddProductStates(StatesGroup):
    """Состояния добавления товара продавцом."""

    category = State()         # Шаг 1: выбор категории (inline-кнопки)
    species = State()          # Шаг 2: вид муравья (текст)
    queen_count = State()      # Шаг 3: количество маток (число)
    worker_count = State()     # Шаг 4: количество рабочих (число)
    price = State()            # Шаг 5: цена в рублях (число)
    description = State()      # Шаг 6: описание товара (текст)
    photo = State()            # Шаг 7: фото (document/фото или пропуск)


class BuyerSearchStates(StatesGroup):
    """Состояние поиска товара покупателем (после нажатия кнопки 🔍 Поиск)."""

    query = State()            # ожидание текстового запроса
