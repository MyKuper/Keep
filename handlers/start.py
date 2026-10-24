# handlers/start.py — /start, /help, выбор роли, регистрация продавца

import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import ADMIN_IDS
from keyboards import buyer_menu_kb, role_select_kb, seller_menu_kb
from states import SellerRegStates
from utils.validators import valid_contact, normalize_contact, MAX_NAME_LEN

logger = logging.getLogger(__name__)
router = Router(name="start")


# ------------------------------ /start ------------------------------ #


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие и выбор роли. Если роль уже выбрана — сразу своё меню."""
    try:
        await state.clear()  # сбрасываем незавершённые сценарии
        user = db.get_user(message.from_user.id)

        if user and user["role"] == "seller":
            await message.answer(
                f"🏪 С возвращением, <b>{escape(user['community_name'] or 'продавец')}</b>!\n"
                "Ваше меню продавца:",
                reply_markup=seller_menu_kb(),
            )
            return
        if user and user["role"] == "buyer":
            await message.answer(
                "🛒 Привет! Рад видеть снова.\nВыберите действие в меню ниже 👇",
                reply_markup=buyer_menu_kb(),
            )
            return

        # Новый пользователь — предлагаем выбрать роль
        await message.answer(
            "🐜 <b>Добро пожаловать в Keep — маркетплейс муравьёв!</b>\n\n"
            "Здесь можно найти колонии муравьёв для дома у проверенных сообществ,\n"
            "а если вы разводите муравьёв — продавать их через единую витрину.\n\n"
            "Кто вы?",
            reply_markup=role_select_kb(),
        )
    except Exception:
        logger.exception("Ошибка в /start")
        await message.answer("😔 Что-то пошло не так, попробуйте позже.")


# ------------------------------ Выбор роли ------------------------------ #


@router.callback_query(F.data == "role:buyer")
async def cb_role_buyer(callback: CallbackQuery, state: FSMContext) -> None:
    """Покупатель: ставим роль и показываем меню."""
    try:
        db.set_role(callback.from_user.id, "buyer")
        await state.clear()
        await callback.message.edit_text(
            "🛒 Отлично! Вы покупатель.\nМеню открыто внизу 👇"
        )
        await callback.message.answer(
            "📋 <b>Каталог</b> — витрина всех муравьёв\n"
            "🔍 <b>Поиск</b> — найти конкретный вид\n"
            "⭐ <b>Избранное</b> — отложенные товары\n"
            "📦 <b>Мои запросы</b> — история «хочу купить»",
            reply_markup=buyer_menu_kb(),
        )
    except Exception:
        logger.exception("Ошибка role:buyer")
        await callback.answer("😔 Ошибка, повторите позже", show_alert=True)
        return
    await callback.answer("Роль покупателя выбрана!")


@router.callback_query(F.data == "role:seller")
async def cb_role_seller(callback: CallbackQuery, state: FSMContext) -> None:
    """Продавец: запускаем FSM регистрации сообщества."""
    try:
        await state.set_state(SellerRegStates.community_name)
        await callback.message.edit_text(
            "🏪 Отлично, вы продавец!\n\n"
            "<b>Шаг 1/2.</b> Введите название вашего сообщества "
            f"(до {MAX_NAME_LEN} символов):"
        )
    except Exception:
        logger.exception("Ошибка role:seller")
        await callback.answer("😔 Ошибка, повторите позже", show_alert=True)
        return
    await callback.answer()


@router.message(SellerRegStates.community_name)
async def seller_community_name(message: Message, state: FSMContext) -> None:
    """Сохраняем название сообщества, переходим к контакту."""
    name = message.text.strip()
    if not (1 <= len(name) <= MAX_NAME_LEN):
        await message.answer(f"❌ Название должно быть от 1 до {MAX_NAME_LEN} символов. Повторите:")
        return
    await state.update_data(community_name=name)
    await state.set_state(SellerRegStates.contact)
    await message.answer(
        "<b>Шаг 2/2.</b> Введите контакт для связи с покупателями:\n"
        "• @username\n"
        "• https://t.me/username\n"
        "• или телефон +7 900 000-00-00"
    )


@router.message(SellerRegStates.contact)
async def seller_contact(message: Message, state: FSMContext) -> None:
    """Проверяем контакт, сохраняем профиль продавца и открываем меню."""
    ok, err = valid_contact(message.text)
    if not ok:
        await message.answer(err + "\n\nПовторите ввод контакта:")
        return
    data = await state.get_data()
    contact = normalize_contact(message.text)
    try:
        db.set_seller_profile(message.from_user.id, data["community_name"], contact)
        await state.clear()
        await message.answer(
            f"✅ <b>Продавец зарегистрирован!</b>\n"
            f"Сообщество: <b>{escape(data['community_name'])}</b>\n"
            f"Контакт: <code>{contact}</code>\n\n"
            "Меню продавца внизу 👇 Нажмите «➕ Добавить», чтобы выставить первый товар.",
            reply_markup=seller_menu_kb(),
        )
        logger.info("Продавец зарегистрирован: tg_id=%s, %s",
                    message.from_user.id, data["community_name"])
    except Exception:
        logger.exception("Ошибка сохранения профиля продавца")
        await message.answer("😔 Не удалось сохранить данные, попробуйте позже.")


# ------------------------------ /help ------------------------------ #


@router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    """Справка по командам с учётом роли пользователя."""
    try:
        user = db.get_user(message.from_user.id)
        role = user["role"] if user else "buyer"

        common = (
            "🐜 <b>Keep — маркетплейс муравьёв</b>\n\n"
            "<b>Общие команды:</b>\n"
            "/start — начать / сменить меню\n"
            "/help — эта справка\n"
        )
        if role == "seller":
            body = (
                "<b>Продавец:</b>\n"
                "➕ Добавить (/add_product) — выставить муравьёв\n"
                "📦 Мои товары (/my_products) — управление витриной\n"
                "📊 Статистика (/stats) — просмотры и запросы\n"
                "⚙️ Настройки (/settings) — изменить контакт/сообщество\n"
            )
        else:
            body = (
                "<b>Покупатель:</b>\n"
                "📋 Каталог (/catalog) — все товары с фильтрами\n"
                "🔍 Поиск (/search &lt;вид&gt;) — например: /search messor\n"
                "⭐ Избранное (/favorites) — сохранённые товары\n"
                "📦 Мои запросы (/my_orders) — «хочу купить»\n"
            )
        admin = ""
        if message.from_user.id in ADMIN_IDS:
            admin = "\n<b>Админ:</b> /admin — панель модерации и статистика\n"
        await message.answer(common + body + admin)
    except Exception:
        logger.exception("Ошибка в /help")
        await message.answer("😔 Ошибка показа справки.")
