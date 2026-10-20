#!/usr/bin/env bash
# deploy.sh — быстрый запуск бота Keep на сервере/VPS
# Использование: BOT_TOKEN=123:abc ./deploy.sh
set -e

# 1. Проверяем, что токен передан
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Не задан BOT_TOKEN. Пример: BOT_TOKEN=123:abc ./deploy.sh"
    exit 1
fi

# 2. Сохраняем токен в .env (если ещё не сохранён)
if [ ! -f .env ]; then
    echo "BOT_TOKEN=$BOT_TOKEN" > .env
    echo "✅ Токен сохранён в .env"
else
    echo "ℹ️  Файл .env уже существует, пропускаю"
fi

# 3. Создаём виртуальное окружение и ставим зависимости
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
echo "✅ Зависимости установлены"

# 4. Инициализируем базу данных (создаёт keep.db с таблицей notes)
python database.py
echo "✅ База данных готова"

# 5. Запускаем бота в фоне, логи — в bot.log
nohup python bot.py > bot.log 2>&1 &
echo "🚀 Бот запущен (PID $!). Логи: tail -f bot.log"
