# -*- coding: utf-8 -*-
"""
setup_token.py — помощник для настройки токена Telegram-бота "Keep".

Что делает:
1. Берёт токен из аргумента командной строки (или просит ввести вручную).
2. Проверяет его через официальный метод Bot API getMe.
3. Если токен корректный — пишет его в файл .env, который НЕ попадает в git
   (уже добавлен в .gitignore), и bot.py подхватит его автоматически.

Запуск:
    python setup_token.py 123456789:AAE_ваш_токен
или просто:
    python setup_token.py
(скрипт сам попросит вставить токен)
"""

import sys
import os
import urllib.request
import json

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def check_token(token: str) -> dict | None:
    """Проверяет токен через метод getMe. Возвращает данные бота или None."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("ok"):
            return data["result"]
        print(f"❌ Telegram отклонил токен: {data.get('description')}")
    except Exception as exc:  # сеть/таймаут/некорректный формат токена
        print(f"❌ Ошибка проверки токена: {exc}")
    return None


def save_env(token: str) -> None:
    """Сохраняет токен в файл .env (строка BOT_TOKEN=...), не светя его в репозитории."""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("# Файл с секретами. Не коммитить в git!\n")
        f.write(f"BOT_TOKEN={token}\n")
    print(f"💾 Токен сохранён в {ENV_FILE}")


def main() -> int:
    # Токен можно передать аргументом или ввести интерактивно
    if len(sys.argv) > 1:
        token = sys.argv[1].strip()
    else:
        token = input("Вставь токен от @BotFather: ").strip()

    if not token or ":" not in token:
        print("⚠️  Похоже, это не токен. Формат: 123456789:AAA... (получить у @BotFather)")
        return 1

    print("🔍 Проверяю токен через Telegram Bot API...")
    bot = check_token(token)
    if not bot:
        return 1

    print(f"✅ Всё отлично! Бот: @{bot['username']} ({bot['first_name']})")
    save_env(token)
    print("\n🚀 Теперь можно запускать бота:")
    print("   pip install -r requirements.txt")
    print("   python bot.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
