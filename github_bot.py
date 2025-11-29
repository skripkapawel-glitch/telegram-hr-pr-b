import os
import requests
import time
import sys
from dotenv import load_dotenv

print("🐛 START: Бот запущен")
sys.stdout.flush()

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"      # ⬅️ ИСПРАВИЛ
ZEN_CHANNEL_ID = "@tehdzenm"      # ⬅️ ИСПРАВИЛ

print("=" * 80)
print("🧪 ТЕСТ БОТА - ПРАВИЛЬНЫЕ КАНАЛЫ")
print("=" * 80)
sys.stdout.flush()

def debug_log(message):
    print(f"🔍 {message}")
    sys.stdout.flush()
    time.sleep(0.1)

def test_bot():
    debug_log("Начало тестирования")
    debug_log(f"BOT_TOKEN: {'✅ ЕСТЬ' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    debug_log(f"MAIN_CHANNEL_ID: {MAIN_CHANNEL_ID}")
    debug_log(f"ZEN_CHANNEL_ID: {ZEN_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        debug_log("❌ BOT_TOKEN пустой!")
        return False

    test_text = """🧪 ТЕСТОВЫЙ ПОСТ ОТ БОТА

Дата: 2024 год  
Время: тестирование

✅ Если вы видите этот пост - бот работает корректно!

#тест #бот #работает"""
    
    test_image = "https://source.unsplash.com/1200x630/?office,team,work"
    
    debug_log("Попытка отправки в ОСНОВНОЙ канал @da4a_hr...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": MAIN_CHANNEL_ID,
        "photo": test_image,
        "caption": test_text,
        "parse_mode": "HTML"
    }

    try:
        debug_log("Отправка запроса к Telegram API...")
        response = requests.post(url, json=payload, timeout=30)
        debug_log(f"Получен ответ: {response.status_code}")
        
        if response.status_code == 200:
            debug_log("✅ УСПЕХ: Пост отправлен в @da4a_hr!")
            
            debug_log("Попытка отправки в ДЗЕН канал @tehdzenm...")
            payload["chat_id"] = ZEN_CHANNEL_ID
            response2 = requests.post(url, json=payload, timeout=30)
            debug_log(f"Ответ второго канала: {response2.status_code}")
            
            if response2.status_code == 200:
                debug_log("✅ УСПЕХ: Пост отправлен в @tehdzenm!")
                return True
            else:
                debug_log(f"⚠️ Дзен канал: {response2.text}")
                return True
        else:
            debug_log(f"❌ ОШИБКА: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        debug_log(f"💥 ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    debug_log("🚀 ЗАПУСК С ПРАВИЛЬНЫМИ КАНАЛАМИ")
    success = test_bot()
    
    if success:
        print("\n🎉 ТЕСТ ПРОЙДЕН! Проверь каналы @da4a_hr и @tehdzenm")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН!")
    
    sys.stdout.flush()
