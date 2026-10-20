# handlers/seller.py — продавец: добавление товара (FSM), витрина, статистика, настройки

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from states import AddProductStates, SellerRegStates
from utils.validators import (
    valid_count,
    valid_description,
    valid_price,
    valid_species,
    valid_contact,
    normalize_contact,
)

logger = logging.getLogger(__name__)
router = Router(name="seller")


# ------------------------------ Старт добавления ------------------------------ #


@router.message(F.text.in_({"➕ Добавить", "/add_product"}))
@router.message(Command("add_product"))
async def start_add_product(message: Message, state: FSMContext) -> None:
    """Шаг 1 FSM: выбор категории из inline-кнопок (справочник родов)."""
    user = db.get_user(message.from_user.id)
    if not user or user["role"] != "seller":
        await message.answer("🏪 Чтобы продавать, нужно выбрать роль продавца. Нажмите /start")
        return
    categories = db.get_categories()
    await state.set_state(AddProductStates.category)
    await message.answer(
        "➕ <b>Добавление товара — шаг 1/7</b>\nВыберите род муравьёв:",
        reply_markup=kb.categories_kb([(c[0], c[1]) for c in categories]),
    )


@router.callback_query(AddProductStates.category, F.data.startswith("cat:"))
async def step_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Категория выбрана -> запрашиваем вид."""
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AddProductStates.species)
    await callback.message.edit_text(
        "<b>Шаг 2/7.</b> Введите точное название вида, например:\n"
        "<code>Messor structor</code>"
    )
    await callback.answer()


@router.message(AddProductStates.species)
async def step_species(message: Message, state: FSMContext) -> None:
    """Вид муравья -> количество маток."""
    ok, err = valid_species(message.text)
    if not ok:
        await message.answer(err + "\nПовторите:")
        return
    await state.update_data(species=message.text.strip())
    await state.set_state(AddProductStates.queen_count)
    await message.answer("<b>Шаг 3/7.</b> Сколько маток 👑 в колонии? (целое число)")


@router.message(AddProductStates.queen_count)
async def step_queens(message: Message, state: FSMContext) -> None:
    """Матки -> рабочие."""
    ok, err = valid_count(message.text, "количество маток")
    if not ok:
        await message.answer(err + "\nПовторите:")
        return
    await state.update_data(queen_count=int(message.text.strip()))
    await state.set_state(AddProductStates.worker_count)
    await message.answer("<b>Шаг 4/7.</b> Сколько рабочих 👷? (например: 25)")


@router.message(AddProductStates.worker_count)
async def step_workers(message: Message, state: FSMContext) -> None:
    """Рабочие -> цена."""
    ok, err = valid_count(message.text, "количество рабочих")
    if not ok:
        await message.answer(err + "\nПовторите:")
        return
    await state.update_data(worker_count=int(message.text.strip()))
    await state.set_state(AddProductStates.price)
    await message.answer("<b>Шаг 5/7.</b> Цена в рублях 💰 (например: 800)")


@router.message(AddProductStates.price)
async def step_price(message: Message, state: FSMContext) -> None:
    """Цена -> описание."""
    ok, err = valid_price(message.text)
    if not ok:
        await message.answer(err + "\nПовторите:")
        return
    await state.update_data(price=int(message.text.strip()))
    await state.set_state(AddProductStates.description)
    await message.answer(
        "<b>Шаг 6/7.</b> Краткое описание товара 📝\n"
        "(формарий, особенности, условия доставки... до 1000 символов)"
    )


@router.message(AddProductStates.description)
async def step_description(message: Message, state: FSMContext) -> None:
    """Описание -> фото (или пропуск)."""
    ok, err = valid_description(message.text)
    if not ok:
        await message.answer(err + "\nПовторите:")
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(AddProductStates.photo)
    await message.answer(
        "<b>Шаг 7/7.</b> Прикрепите фото колонии 📷 (обычным сообщением с фото)\n"
        "или нажмите «Пропустить»:",
        reply_markup=kb.skip_kb(),
    )


@router.callback_query(AddProductStates.photo, F.data == "skip:photo")
async def step_photo_skip(callback: CallbackQuery, state: FSMContext) -> None:
    """Фото не нужно -> публикуем товар."""
    await _publish(state, callback.from_user.id, photo_file_id=None)
    await callback.message.edit_text("⏭ Фото пропущено.")
    await _finish_publish(callback.message, state)
    await callback.answer()


@router.message(AddProductStates.photo, F.photo)
async def step_photo(message: Message, state: FSMContext) -> None:
    """Сохраняем file_id наибольшего размера фото и публикуем."""
    file_id = message.photo[-1].file_id  # самое высокое разрешение
    await _publish(state, message.from_user.id, photo_file_id=file_id)
    await _finish_publish(message, state)


async def _publish(state: FSMContext, telegram_id: int, photo_file_id) -> int:
    """Записывает собранные данные FSM в таблицу products, возвращает id товара."""
    data = await state.get_data()
    user = db.get_user(telegram_id)
    product_id = db.add_product(
        seller_internal_id=user["id"],
        category_id=data.get("category_id"),
        species=data["species"],
        queen_count=data["queen_count"],
        worker_count=data["worker_count"],
        price=data["price"],
        description=data["description"],
        photo_file_id=photo_file_id,
    )
    await state.clear()
    return product_id


async def _finish_publish(target_message: Message, state: FSMContext) -> None:
    """Финальное сообщение об успехе (данные уже очищены, берём из последнего состояния)."""
    # state уже cleared, поэтому перечитаем последний товар продавца из БД
    user = db.get_user(target_message.from_user.id)
    last = db.seller_products(user["id"])
    name = last[0][1] if last else "товар"
    await target_message.answer(
        f"✅ <b>Товар опубликован!</b>\n🐜 {escape(name)} теперь виден покупателям в каталоге.",
        reply_markup=kb.seller_menu_kb(),
    )


# ------------------------------ Мои товары ------------------------------ #


@router.message(F.text.in_({"📦 Мои товары", "/my_products"}))
@router.message(Command("my_products"))
async def cmd_my_products(message: Message) -> None:
    """Список товаров продавца с кнопками управления."""
    user = db.get_user(message.from_user.id)
    if not user or user["role"] != "seller":
        await message.answer("🏪 Эта команда доступна продавцам. Нажмите /start")
        return
    items = db.seller_products(user["id"])
    if not items:
        await message.answer("📦 У вас пока нет товаров. Нажмите «➕ Добавить»!")
        return
    lines = [
        f"{'🟢' if active else '🔴'} <b>{escape(sp)}</b> — {price}₽"
        for _, sp, price, active in items
    ]
    products_for_kb = [(pid, sp, act) for pid, sp, _, act in items]
    await message.answer(
        "📦 <b>Мои товары</b> (нажмите на товар для управления):\n\n" + "\n".join(lines),
        reply_markup=kb.my_products_kb(products_for_kb),
    )


@router.callback_query(F.data.startswith("myp:"))
async def cb_manage_product(callback: CallbackQuery) -> None:
    """Экран управления одним товаром."""
    product_id = int(callback.data.split(":")[1])
    product = db.get_product(product_id)
    me = db.get_user(callback.from_user.id)
    if not product or not me or product["seller_id"] != me["id"]:
        await callback.answer("Это не ваш товар 😅", show_alert=True)
        return
    try:
        await callback.message.answer(
            f"Управление: <b>{escape(product['species'])}</b> ({product['price']}₽)\n"
            f"👁 просмотров: {product['views']}",
            reply_markup=kb.manage_product_kb(product_id, bool(product["is_active"])),
        )
    except Exception:
        logger.exception("Ошибка экрана управления #%s", product_id)
    await callback.answer()


@router.callback_query(F.data.startswith("tog:"))
async def cb_toggle_active(callback: CallbackQuery) -> None:
    """Снять/разместить товар."""
    _, action, pid_s = callback.data.split(":")
    product_id = int(pid_s)
    product = db.get_product(product_id)
    me = db.get_user(callback.from_user.id)
    if not product or not me or product["seller_id"] != me["id"]:
        await callback.answer("Не ваш товар", show_alert=True)
        return
    db.set_product_active(product_id, action == "on")
    await callback.message.edit_reply_markup(
        reply_markup=kb.manage_product_kb(product_id, action == "on")
    )
    await callback.answer("🟢 Размещен!" if action == "on" else "🔴 Снят с продажи")


@router.callback_query(F.data.startswith("del:"))
async def cb_delete_product(callback: CallbackQuery) -> None:
    """Удаляет товар навсегда."""
    product_id = int(callback.data.split(":")[1])
    product = db.get_product(product_id)
    me = db.get_user(callback.from_user.id)
    if not product or not me or product["seller_id"] != me["id"]:
        await callback.answer("Не ваш товар", show_alert=True)
        return
    db.delete_product(product_id)
    try:
        await callback.message.edit_text(f"🗑 Товар «{escape(product['species'])}» удалён.")
    except Exception:
        logger.debug("Сообщение не обновлено")
    await callback.answer("Товар удалён")


@router.callback_query(F.data == "seller:products")
async def cb_back_to_products(callback: CallbackQuery) -> None:
    """Возврат к списку своих товаров."""
    me = db.get_user(callback.from_user.id)
    if not me:
        await callback.answer("Нажмите /start", show_alert=True)
        return
    items = db.seller_products(me["id"])
    products_for_kb = [(pid, sp, act) for pid, sp, _, act in items]
    try:
        await callback.message.edit_reply_markup(reply_markup=kb.my_products_kb(products_for_kb))
    except Exception:
        logger.debug("Список товаров не обновлён")
    await callback.answer()


# ------------------------------ Статистика ------------------------------ #


@router.message(F.text.in_({"📊 Статистика", "/stats"}))
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Статистика продавца: товары, просмотры, запросы."""
    user = db.get_user(message.from_user.id)
    if not user or user["role"] != "seller":
        await message.answer("📊 Статистика доступна только продавцам.")
        return
    s = db.stats_for_seller(user["id"])
    await message.answer(
        f"📊 <b>Статистика сообщества «{escape(user['community_name'] or '')}»</b>\n\n"
        f"📦 Товаров всего: <b>{s['products']}</b> (активных: {s['active']})\n"
        f"👁 Просмотры карточек: <b>{s['views']}</b>\n"
        f"🛒 Запросов на покупку: <b>{s['orders']}</b>"
    )


# ------------------------------ Настройки ------------------------------ #


@router.message(F.text.in_({"⚙️ Настройки", "/settings"}))
@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    """Перерегистрация продавца: меняем название сообщества, затем контакт."""
    user = db.get_user(message.from_user.id)
    if not user or user["role"] != "seller":
        await message.answer("⚙️ Настройки доступны только продавцам.")
        return
    await state.set_state(SellerRegStates.community_name)
    await message.answer(
        f"Текущие данные:\n"
        f"• Сообщество: <b>{escape(user['community_name'] or '—')}</b>\n"
        f"• Контакт: <code>{escape(user['contact'] or '—')}</code>\n\n"
        "✏️ Введите новое название сообщества:"
    )
