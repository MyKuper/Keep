# -*- coding: utf-8 -*-
"""
config.py — настройки бота "Keep" (Бот для муравьёв).

Здесь хранятся токен Telegram-бота и прочие конфигурационные параметры.
Токен лучше задавать через переменную окружения, чтобы не светить его в репозитории.
"""

import os

# Загружаем файл .env (если он есть) в переменные окружения.
# Так запуск бота сводится к: python bot.py  (токен берётся из .env).
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                # срезаем пробелы и возможные кавычки вокруг значения (BOT_TOKEN="...")
                os.environ.setdefault(_key.strip(), _val.strip().strip("'\""))

# Токен бота, полученный у @BotFather.
# Приоритет: переменная окружения BOT_TOKEN (или .env), иначе — значение по умолчанию ниже.
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

# Путь к файлу базы данных SQLite
DB_PATH = os.getenv("KEEP_DB_PATH", "keep.db")

# Максимальная длина одной заметки (в символах) — наследие первой версии бота
MAX_NOTE_LENGTH = 4096

# Telegram ID администраторов маркетплейса (через запятую в env ADMIN_IDS).
# Например: ADMIN_IDS=123456789,987654321
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
