# README.md — маркетплейс муравьёв "Keep" 🐜

Бот-витрина, где сообщества-продавцы выставляют колонии муравьёв, а покупатели
ищут нужные виды через каталог с фильтрами и поиском. Стек: **Python 3 + aiogram 3.x + SQLite**.

## Возможности

### 👤 Покупатель
- `/start` — выбор роли (🛒 покупатель / 🏪 продавец)
- `/catalog` — витрина с пагинацией (5 товаров на страницу)
- 🔍 Фильтры inline-кнопками: сложность (easy/medium/hard), цена (до 500₽ / 500–1500₽ / 1500₽+), размер колонии
- `/search <вид>` — поиск по названию вида, описанию и роду
- Карточка товара: фото, 👑 матки, 👷 рабочие, 💰 цена, описание, продавец
- `🛒 Хочу купить` — создаёт запрос (order) и уведомляет продавца в личку
- `⭐ В избранное` / `/favorites`
- `📞 Связаться` — показывает контакт продавца, заказ переходит в статус `contacted`
- `/my_orders` — история запросов со статусами

### 🏪 Продавец
- Регистрация: название сообщества + контакт (@username / t.me / телефон, с валидацией)
- `/add_product` — FSM из 7 шагов: категория → вид → матки → рабочие → цена → описание → фото (file_id)
- `/my_products` — управление: снять/разместить, удалить
- `/stats` — просмотры карточек и число запросов
- `/settings` — изменить название сообщества и контакт

### 👑 Админ (`ADMIN_IDS`)
- `/admin` — панель: пользователи, товары, заказы
- `/recent_orders` — последние лиды сети
- `/hide <id>` — модерация: снять товар с витрины
- `/ban <telegram_id>` — блокировка пользователя и скрытие его товаров

## Структура проекта

```
bot.py            # запуск, логирование, middleware, подключение роутеров
config.py         # BOT_TOKEN, DB_PATH, ADMIN_IDS (из .env / окружения)
database.py       # SQLite: users, categories, products, favorites, orders (+notes)
keyboards.py      # все inline/reply клавиатуры
states.py         # FSM: SellerRegStates, AddProductStates, BuyerSearchStates
handlers/         # start.py, buyer.py, seller.py, admin.py (по роутерам)
middlewares/db.py # авторегистрация пользователя в БД на каждый апдейт
utils/            # filters.py (фильтрация/формат), validators.py (валидация ввода)
```

## Запуск

```bash
pip install -r requirements.txt        # aiogram>=3.4
python bot.py                          # токен берётся из .env (BOT_TOKEN=...)
```

Переменные окружения (`.env`):
- `BOT_TOKEN` — токен от @BotFather
- `KEEP_DB_PATH` — путь к SQLite (по умолчанию keep.db)
- `ADMIN_IDS` — telegram id админов через запятую

При первом запуске создаются таблицы и справочник родов муравьёв
(Messor, Camponotus, Atta… с меткой сложности easy/medium/hard).

## Схема БД

| Таблица | Назначение |
|---|---|
| users | telegram_id, role (buyer/seller/admin/blocked), community_name, contact |
| categories | род муравьёв + difficulty |
| products | вид, 👑/👷 состав, цена ₽, описание, photo_file_id, is_active, views |
| favorites | избранное покупателя |
| orders | лиды: new → contacted → closed |

## Логика фильтров

- Цена: low `< 500`, mid `500–1500`, high `> 1500`
- Размер колонии: small `≤ 50` рабочих, medium `51–500`, big `> 500`
- Сложность берётся из категории товара

Все ошибки логируются в `bot.log`. Пагинация и все действия — через `callback_query`.
