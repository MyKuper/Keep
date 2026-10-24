# handlers/admin.py — панель администратора: статистика, модерация, блокировка

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

import database as db
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin(message: Message) -> bool:
    """Проверка доступа: telegram_id должен быть в ADMIN_IDS (config.py / .env)."""
    return message.from_user is not None and message.from_user.id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Общая панель: статистика маркетплейса + подсказки команд."""
    if not _is_admin(message):
        await message.answer("⛔ Доступ только для администраторов.")
        return
    s = db.stats_overall()
    await message.answer(
        "👑 <b>Панель администратора Keep</b>\n\n"
        f"👤 Пользователей: <b>{s['users']}</b> (продавцов: {s['sellers']})\n"
        f"🐜 Активных товаров: <b>{s['products']}</b>\n"
        f"🛒 Всего запросов: <b>{s['orders']}</b> (новых: {s['new_orders']})\n\n"
        "<b>Команды:</b>\n"
        "/stats_all — статистика ещё раз\n"
        "/recent_orders — последние 10 запросов\n"
        "/hide &lt;id товара&gt; — снять товар с витрины\n"
        "/ban &lt;telegram_id&gt; — заблокировать пользователя"
    )


@router.message(Command("stats_all"))
async def cmd_stats_all(message: Message) -> None:
    """Быстрый доступ к общей статистике."""
    if not _is_admin(message):
        return
    s = db.stats_overall()
    await message.answer(
        f"📊 users={s['users']} sellers={s['sellers']} "
        f"products={s['products']} orders={s['orders']} (new={s['new_orders']})"
    )


@router.message(Command("recent_orders"))
async def cmd_recent_orders(message: Message) -> None:
    """Последние запросы на покупку (лиды сети сообществ)."""
    if not _is_admin(message):
        return
    from database import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT o.id, p.species, p.price, o.status, u.community_name, b.username
               FROM orders o
               JOIN products p ON p.id = o.product_id
               JOIN users u ON u.id = p.seller_id
               JOIN users b ON b.id = o.buyer_id
               ORDER BY o.created_at DESC LIMIT 10"""
        ).fetchall()
    if not rows:
        await message.answer("Запросов пока нет 🤷")
        return
    lines = [
        f"№{r['id']} · {escape(r['species'])} ({r['price']}₽) · продавец «{escape(r['community_name'] or '—')}» "
        f"· покупатель @{r['username'] or '—'} · {r['status']}"
        for r in rows
    ]
    await message.answer("🧾 <b>Последние запросы:</b>\n\n" + "\n".join(lines))


@router.message(Command("hide"))
async def cmd_hide(message: Message, command=None) -> None:
    """/hide <id> — админ может снять любой товар с витрины (модерация)."""
    if not _is_admin(message):
        return
    from aiogram.filters import CommandObject
    # аргумент команды вытаскиваем из текста вручную (проще и надёжнее)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /hide 12")
        return
    product_id = int(parts[1].strip())
    product = db.get_product(product_id)
    if not product:
        await message.answer("Товар не найден 😔")
        return
    db.set_product_active(product_id, False)
    logger.info("Админ %s скрыл товар #%s", message.from_user.id, product_id)
    await message.answer(f"🔴 Товар «{escape(product['species'])}» снят с витрины.")


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    """/ban <telegram_id> — понижает роль до blocked (бот перестанет его обслуживать)."""
    if not _is_admin(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Использование: /ban 123456789")
        return
    tg_id = int(parts[1].strip())
    user = db.get_user(tg_id)
    if not user:
        await message.answer("Пользователь не найден в базе.")
        return
    db.set_role(tg_id, "blocked")
    # снимаем все его активные товары — модерация сети
    from database import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE products SET is_active = 0 WHERE seller_id = ?", (user["id"],))
    logger.info("Админ %s заблокировал пользователя %s", message.from_user.id, tg_id)
    await message.answer(f"⛔ Пользователь {tg_id} заблокирован, его товары скрыты.")
