import os
import sys
import requests
from dotenv import load_dotenv

print("🚀 СТАРТ БОТА - ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ")

try:
    # Загружаем настройки
    print("1. Загрузка переменных окружения...")
    load_dotenv()
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MAIN_CHANNEL_ID = "@hr_na_dache"
    ZEN_CHANNEL_ID = -1003322670507
    
    print(f"2. BOT_TOKEN: {'ЕСТЬ' if BOT_TOKEN else 'НЕТ'}")
    print(f"3. MAIN_CHANNEL_ID: {MAIN_CHANNEL_ID}")
    print(f"4. ZEN_CHANNEL_ID: {ZEN_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден")
        sys.exit(1)
    
    # Простой тестовый пост
    print("5. Подготовка тестового поста...")
    test_post = "🧪 Тестовый пост от бота\n\nПроверка работы системы.\n\n#тест #2025"
    test_image = "https://source.unsplash.com/1200x630/?office,team"
    
    # Отправка в основной канал
    print("6. Отправка в основной канал...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": MAIN_CHANNEL_ID,
        "photo": test_image,
        "caption": test_post,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=payload, timeout=15)
    print(f"7. Ответ от ТГ: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ ПОСТ ОТПРАВЛЕН В ОСНОВНОЙ КАНАЛ!")
    else:
        print(f"❌ Ошибка ТГ: {response.text}")
    
    # Отправка в Дзен канал
    print("8. Отправка в Дзен канал...")
    payload["chat_id"] = ZEN_CHANNEL_ID
    response = requests.post(url, json=payload, timeout=15)
    print(f"9. Ответ от Дзен: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ ПОСТ ОТПРАВЛЕН В ДЗЕН КАНАЛ!")
    else:
        print(f"❌ Ошибка Дзен: {response.text}")
        
    print("🎉 ВСЕ ОПЕРАЦИИ ЗАВЕРШЕНЫ!")

except Exception as e:
    print(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    import traceback
    print(f"📋 Детали: {traceback.format_exc()}")
