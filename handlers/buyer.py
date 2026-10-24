# handlers/buyer.py — покупатель: каталог, фильтры, пагинация, карточка, избранное, заказы

import logging
from html import escape
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database as db
import keyboards as kb
from states import BuyerSearchStates
from utils.filters import build_catalog_text

logger = logging.getLogger(__name__)
router = Router(name="buyer")

PAGE_SIZE = 5  # товаров на страницу каталога


# ------------------------------ Хелперы ------------------------------ #


async def _show_catalog(callback_or_message, page: int, filters: Optional[dict]) -> None:
    """Рисует страницу каталога (edit для callback, новый текст для messages)."""
    total = db.count_products(filters)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 1), total_pages)
    products = db.list_products(filters, offset=(page - 1) * PAGE_SIZE, limit=PAGE_SIZE)
    text = build_catalog_text(products, page, total_pages, filters, total)
    markup = kb.catalog_pagination_kb(page, total_pages)
    # добавляем кнопки-карточки товаров
    for pid, species, price, *_ in products:
        markup.insert(
            InlineKeyboardButton(text=f"🐜 {species} — {price}₽", callback_data=f"prod:{pid}")
        )
    if isinstance(callback_or_message, CallbackQuery):
        try:
            await callback_or_message.message.edit_text(text, reply_markup=markup)
        except Exception as e:
            # Telegram не ругается, если контент не изменился
            if "message is not modified" not in str(e).lower():
                raise
    else:
        await callback_or_message.answer(text, reply_markup=markup)


def _product_card_text(p: dict) -> str:
    """HTML-текст карточки товара."""
    diff_map = {"easy": "лёгкий 🟢", "medium": "средний 🟡", "hard": "сложный 🔴"}
    lines = [
        f"🐜 <b>{escape(p['species'])}</b>"
        + (f" ({escape(p['category_name'])})" if p.get("category_name") else ""),
        f"👑 {p['queen_count']} матка(и) | 👷 {p['worker_count']} рабочих",
        f"💰 <b>{p['price']}₽</b>",
    ]
    if p.get("difficulty"):
        lines.append(f"🎯 Сложность содержания: {diff_map.get(p['difficulty'], p['difficulty'])}")
    if p.get("description"):
        lines.append(f"📝 {escape(p['description'])}")
    lines.append(f"🏪 Продавец: <b>{escape(p['community_name'] or '—')}</b>")
    lines.append(f"👁 Просмотров: {p['views']}")
    return "\n".join(lines)


# ------------------------------ Каталог ------------------------------ #


@router.message(F.text.in_({"📋 Каталог", "/catalog"}))
@router.message(Command("catalog"))
async def cmd_catalog(message: Message, state: FSMContext) -> None:
    """Открывает первую страницу каталога (фильтры сбрасываются)."""
    try:
        await state.update_data(filters={})
        await _show_catalog(message, page=1, filters={})
    except Exception:
        logger.exception("Ошибка каталога")
        await message.answer("😔 Каталог временно недоступен.")


@router.callback_query(F.data == "filters")
async def cb_filters(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает панель фильтров (текущие — из FSM-данных)."""
    data = await state.get_data()
    active = data.get("draft_filters", {})
    try:
        await callback.message.edit_text(
            "🔍 <b>Фильтры</b>\nНажмите нужные значения, затем «Показать каталог».",
            reply_markup=kb.catalog_filters_kb(active),
        )
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.exception("Ошибка панели фильтров")
    await callback.answer()


@router.callback_query(F.data.startswith("flt:"))
async def cb_filter_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключение значений фильтров (повторное нажатие снимает фильтр)."""
    _, kind, value = callback.data.split(":")
    data = await state.get_data()
    draft: dict = data.get("draft_filters", {})

    if kind == "apply":
        await state.update_data(filters=draft)
        await _show_catalog(callback, page=1, filters=draft)
        await callback.answer("Фильтры применены")
        return
    if kind == "reset":
        draft = {}
        await state.update_data(draft_filters={})
    else:
        draft[kind] = None if draft.get(kind) == value else value
        draft = {k: v for k, v in draft.items() if v}  # убираем пустые
        await state.update_data(draft_filters=draft)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=kb.catalog_filters_kb(draft)
        )
    except Exception:
        logger.debug("Markup не изменён")
    await callback.answer()


@router.callback_query(F.data.startswith("pg:"))
async def cb_pagination(callback: CallbackQuery, state: FSMContext) -> None:
    """Переход по страницам каталога."""
    _, page_s = callback.data.split(":")
    if page_s == "noop":
        await callback.answer()
        return
    data = await state.get_data()
    await _show_catalog(callback, page=int(page_s), filters=data.get("filters", {}))
    await callback.answer()


# ------------------------------ Карточка товара ------------------------------ #


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Открывает карточку товара (+1 просмотр)."""
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("⛔ Некорректный запрос", show_alert=True)
        return
    product = db.get_product(product_id)
    if not product:
        await callback.answer("Товар больше не доступен 😔", show_alert=True)
        return
    db.increment_views(product_id)
    # запоминаем товар, чтобы вернуться «К каталогу» корректно
    await state.update_data(last_product=product_id)

    uid = _internal_id(callback)
    markup = kb.product_buttons_kb(
        product_id,
        is_favorite=bool(uid) and db.is_favorite(uid, product_id),
    )
    try:
        if product.get("photo_file_id"):
            await callback.message.answer_photo(
                photo=product["photo_file_id"],
                caption=_product_card_text(product),
                reply_markup=markup,
            )
        else:
            await callback.message.answer(_product_card_text(product), reply_markup=markup)
    except Exception:
        logger.exception("Ошибка показа карточки #%s", product_id)
        await callback.answer("😔 Ошибка открытия карточки", show_alert=True)
        return
    await callback.answer()


def _internal_id(callback: CallbackQuery) -> Optional[int]:
    """Достаёт внутренний id пользователя из БД (middleware его гарантирует)."""
    u = db.get_user(callback.from_user.id)
    return u["id"] if u else None


@router.callback_query(F.data == "back:catalog")
async def cb_back_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к каталогу с последней страницы и фильтрами."""
    data = await state.get_data()
    await _show_catalog(callback, page=1, filters=data.get("filters", {}))
    await callback.answer()


# ------------------------------ Избранное ------------------------------ #


@router.callback_query(F.data.startswith("fav:"))
async def cb_favorite(callback: CallbackQuery) -> None:
    """Добавляет/убирает товар из избранного."""
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("⛔ Некорректный запрос", show_alert=True)
        return
    uid = _internal_id(callback)
    if not uid:
        await callback.answer("Сначала нажмите /start", show_alert=True)
        return
    added = db.toggle_favorite(uid, product_id)
    await callback.answer("⭐ Добавлено в избранное!" if added else "Убрано из избранного")
    # обновим кнопку в текущей карточке
    markup = kb.product_buttons_kb(product_id, is_favorite=added)
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        logger.debug("Карточка не требует обновления")


@router.message(F.text.in_({"⭐ Избранное", "/favorites"}))
@router.message(Command("favorites"))
async def cmd_favorites(message: Message) -> None:
    """Список избранных товаров."""
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Нажмите /start, чтобы начать 🙂")
        return
    items = db.favorite_products(user["id"])
    if not items:
        await message.answer("⭐ В избранном пока пусто. Нажимайте «В избранное» в карточках товаров!")
        return
    from utils.filters import format_product_line
    text = "⭐ <b>Избранное</b>\n\n" + "\n\n".join(format_product_line(i) for i in items)
    markup = InlineKeyboardMarkup(row_width=1)
    for pid, species, *_ in items:
        markup.insert(InlineKeyboardButton(text=f"🐜 {species}", callback_data=f"prod:{pid}"))
    await message.answer(text, reply_markup=markup)


# ------------------------------ Купить / Связаться ------------------------------ #


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, bot: Bot) -> None:
    """Создаёт заказ «хочу купить» и уведомляет продавца."""
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("⛔ Некорректный запрос", show_alert=True)
        return
    buyer = db.get_user(callback.from_user.id)
    product = db.get_product(product_id)
    if not buyer or not product:
        await callback.answer("😔 Сначала нажмите /start", show_alert=True)
        return

    existing = db.find_order(buyer["id"], product_id)
    if existing:
        await callback.answer("Вы уже отправляли запрос на этот товар 👌", show_alert=True)
        return

    order_id = db.create_order(buyer["id"], product_id)
    # Уведомляем продавца в личку (если бот ему пишет)
    try:
        await bot.send_message(
            product["seller_telegram_id"],
            f"🔔 <b>Новый запрос на покупку!</b>\n\n"
            f"Товар: <b>{escape(product['species'])}</b> ({product['price']}₽)\n"
            f"Покупатель: @{callback.from_user.username or callback.from_user.id}\n"
            f"Запрос №{order_id}. Нажмите кнопку «📞 Связаться» в карточке, "
            "чтобы получить контакт покупателя, или напишите ему первым.",
        )
    except Exception:
        # продавец мог заблокировать бота — это не критично для заказа
        logger.warning("Не удалось уведомить продавца tg_id=%s", product["seller_telegram_id"])

    await callback.answer("🎉 Запрос отправлен продавцу!")
    await callback.message.answer(
        "🛒 <b>Запрос на покупку отправлен!</b>\n"
        f"Продавец <b>{escape(product['community_name'] or '')}</b> получил уведомление.\n"
        "Он свяжется с вами. Ваш запрос виден в разделе «📦 Мои запросы»."
    )


@router.callback_query(F.data.startswith("contact:"))
async def cb_contact(callback: CallbackQuery) -> None:
    """Показывает контакт продавца и переводит заказ в 'contacted'.

    Телефон продавца показывается только покупателям с активным заказом на
    этот товар; остальным — только @username / ссылка t.me.
    """
    try:
        product_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("⛔ Некорректный запрос", show_alert=True)
        return
    product = db.get_product(product_id)
    buyer = db.get_user(callback.from_user.id)
    if not product:
        await callback.answer("Товар недоступен 😔", show_alert=True)
        return
    order = None
    if buyer:
        order = db.find_order(buyer["id"], product_id)
        if order:
            db.mark_order_contacted(order["id"])

    contact = product["seller_contact"] or ""
    is_phone = contact.startswith("+") or contact.replace("-", "").replace(" ", "").isdigit()
    has_order = order is not None
    tg_link = f"@{product['seller_username']}" if product["seller_username"] else f"t.me/{product['seller_telegram_id']}"

    if is_phone and not has_order:
        # без заказа телефон не раскрываем — только публичный контакт
        lines = [
            "📞 <b>Контакты продавца:</b>",
            f"Сообщество: <b>{escape(product['community_name'] or '—')}</b>",
            f"Telegram продавца: <code>{tg_link}</code>",
            "",
            "🔒 Телефон доступен только покупателям с отправленным запросом:",
            "нажмите «🛒 Хочу купить», затем «📞 Связаться» ещё раз.",
            "",
            f"Напишите про товар «<b>{escape(product['species'])}</b>» — продавец поймёт 😉",
        ]
    else:
        lines = [
            "📞 <b>Контакты продавца:</b>",
            f"Сообщество: <b>{escape(product['community_name'] or '—')}</b>",
            f"Контакт: <code>{escape(contact or 'не указан')}</code>",
            f"Telegram продавца: @{product['seller_username'] or product['seller_telegram_id']}",
            "",
            f"Напишите про товар «<b>{escape(product['species'])}</b>» — продавец поймёт 😉",
        ]
    await callback.message.answer("\n".join(lines))
    await callback.answer("Контакт получен ✅")


# ------------------------------ Поиск ------------------------------ #


@router.message(F.text.in_({"🔍 Поиск"}))
async def btn_search(message: Message, state: FSMContext) -> None:
    """Кнопка меню: просим ввести запрос."""
    await state.set_state(BuyerSearchStates.query)
    await message.answer("🔍 Введите название вида (например: <b>messor structor</b>):")


@router.message(Command("search"))
async def cmd_search(message: Message, command: Command) -> None:
    """/search <запрос> — мгновенный поиск."""
    query = (command.args or "").strip()
    if not query:
        await message.answer("Использование: /search messor")
        return
    _do_search(message, query)


@router.message(BuyerSearchStates.query)
async def fsm_search(message: Message, state: FSMContext) -> None:
    """FSM-поиск после нажатия кнопки."""
    await state.clear()
    _do_search(message, message.text.strip())


def _do_search(message: Message, query: str) -> None:
    """Общий код вывода результатов поиска."""
    results = db.search_products(query)
    if not results:
        message.answer(
            f"😔 По запросу «<b>{escape(query)}</b>» ничего не найдено.\n"
            "Попробуйте латинское название рода (Messor, Camponotus...) "
            "или загляните в 📋 Каталог."
        )
        return
    from utils.filters import format_product_line
    text = f"🔍 <b>Нашлось: {len(results)}</b> по «{escape(query)}»\n\n" + \
           "\n\n".join(format_product_line(r) for r in results)
    markup = InlineKeyboardMarkup(row_width=1)
    for pid, species, price, *_ in results:
        markup.insert(InlineKeyboardButton(text=f"🐜 {species} — {price}₽",
                                          callback_data=f"prod:{pid}"))
    message.answer(text, reply_markup=markup)


# ------------------------------ Мои запросы ------------------------------ #


@router.message(F.text.in_({"📦 Мои запросы", "/my_orders"}))
@router.message(Command("my_orders"))
async def cmd_my_orders(message: Message) -> None:
    """История запросов покупателя на покупку."""
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Нажмите /start, чтобы начать 🙂")
        return
    orders = db.get_orders_for_buyer(user["id"])
    if not orders:
        await message.answer("📦 У вас пока нет запросов. Нажмите «🛒 Хочу купить» в карточке товара!")
        return
    status_map = {"new": "🕙 новый", "contacted": "📞 связались", "closed": "✅ закрыт"}
    lines = []
    for oid, species, price, status, community in orders:
        lines.append(
            f"№{oid} · <b>{escape(species)}</b> ({price}₽) · {escape(community)} · "
            f"{status_map.get(status, status)}"
        )
    await message.answer("📦 <b>Мои запросы:</b>\n\n" + "\n".join(lines))
