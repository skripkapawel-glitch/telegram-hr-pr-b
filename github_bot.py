import os
import requests
import time
import sys
from dotenv import load_dotenv

print("🐛 START: Бот запущен")
sys.stdout.flush()

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"

print("=" * 80)
print("🧪 ТЕСТ БОТА - БЕЗ ПРОБЛЕМ С ИЗОБРАЖЕНИЕМ")
print("=" * 80)

def debug_log(message):
    print(f"🔍 {message}")
    sys.stdout.flush()
    time.sleep(0.1)

def test_bot():
    debug_log("Начало тестирования")
    debug_log(f"BOT_TOKEN: {'✅ ЕСТЬ' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    
    if not BOT_TOKEN:
        return False

    test_text = """🧪 ТЕСТОВЫЙ ПОСТ ОТ БОТА

Дата: 2024 год  
Время: тестирование

✅ Если вы видите этот пост - бот работает корректно!

#тест #бот #работает"""
    
    # ИСПРАВЛЕННЫЕ URL изображений (более надежные)
    test_images = [
        "https://picsum.photos/1200/630",  # Lorem Picsum - всегда работает
        "https://placekitten.com/1200/630", # Котята - надежный сервис
        "https://picsum.photos/1200/630?random=1"
    ]
    
    test_image = test_images[0]  # Используем первый вариант
    
    debug_log(f"Используем изображение: {test_image}")

    # Сначала пробуем отправить БЕЗ изображения (текстовый пост)
    debug_log("🔄 Пробуем отправить ТЕКСТОВЫЙ пост...")
    url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload_text = {
        "chat_id": MAIN_CHANNEL_ID,
        "text": "📝 ТЕКСТОВЫЙ ТЕСТ: " + test_text,
        "parse_mode": "HTML"
    }
    
    try:
        response_text = requests.post(url_text, json=payload_text, timeout=30)
        debug_log(f"Текстовый пост: {response_text.status_code}")
        
        if response_text.status_code == 200:
            debug_log("✅ Текстовый пост отправлен!")
        else:
            debug_log(f"❌ Текстовый пост: {response_text.text}")
    except Exception as e:
        debug_log(f"❌ Ошибка текстового поста: {e}")

    # Теперь пробуем с изображением
    debug_log("🔄 Пробуем отправить пост С ИЗОБРАЖЕНИЕМ...")
    url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload_photo = {
        "chat_id": MAIN_CHANNEL_ID,
        "photo": test_image,
        "caption": test_text,
        "parse_mode": "HTML"
    }

    try:
        debug_log("Отправка фото-поста...")
        response = requests.post(url_photo, json=payload_photo, timeout=30)
        debug_log(f"Ответ фото-поста: {response.status_code}")
        
        if response.status_code == 200:
            debug_log("✅ Фото-пост отправлен в @da4a_hr!")
            
            # Пробуем во второй канал
            payload_photo["chat_id"] = ZEN_CHANNEL_ID
            response2 = requests.post(url_photo, json=payload_photo, timeout=30)
            
            if response2.status_code == 200:
                debug_log("✅ Фото-пост отправлен в @tehdzenm!")
                return True
            else:
                debug_log(f"⚠️ Дзен канал: {response2.text}")
                return True
        else:
            debug_log(f"❌ Фото-пост: {response.text}")
            return False
            
    except Exception as e:
        debug_log(f"💥 Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_bot()
    
    if success:
        print("\n🎉 УСПЕХ! Проверь каналы!")
    else:
        print("\n⚠️ Возможны проблемы с изображениями, но текстовые посты могли отправиться")
    
    sys.stdout.flush()
