import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@hr_na_dache"
ZEN_CHANNEL_ID = -1003322670507

print("=" * 60)
print("🧪 ТЕСТОВЫЙ БОТ - ДИАГНОСТИКА")
print("=" * 60)

def test_bot():
    # Проверяем переменные
    print("🔍 ПРОВЕРКА ПЕРЕМЕННЫХ:")
    print(f"BOT_TOKEN: {'✅' if BOT_TOKEN else '❌ НЕТ!'}")
    print(f"MAIN_CHANNEL_ID: {MAIN_CHANNEL_ID}")
    print(f"ZEN_CHANNEL_ID: {ZEN_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        print("💥 ОШИБКА: BOT_TOKEN не найден!")
        print("💡 Проверь Secrets в настройках GitHub репозитория:")
        print("   - BOT_TOKEN")
        print("   - CHANNEL_ID") 
        print("   - GEMINI_API_KEY")
        return False
    
    # Тестовое сообщение
    test_text = "🧪 Тестовый пост от бота\n\nДата: 2024\nВремя: тест\n\n✅ Если видишь это - бот работает!"
    test_image = "https://source.unsplash.com/1200x630/?office,work"
    
    print(f"\n📤 ОТПРАВКА ТЕСТОВОГО ПОСТА...")
    print(f"Текст: {test_text}")
    print(f"Фото: {test_image}")
    
    # Пробуем отправить в основной канал
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": MAIN_CHANNEL_ID,
        "photo": test_image,
        "caption": test_text,
        "parse_mode": "HTML"
    }
    
    try:
        print(f"\n🔄 Запрос к: {url}")
        response = requests.post(url, json=payload, timeout=10)
        print(f"📡 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 УСПЕХ! Пост отправлен в основной канал!")
            
            # Пробуем отправить во второй канал
            payload["chat_id"] = ZEN_CHANNEL_ID
            response2 = requests.post(url, json=payload, timeout=10)
            print(f"📡 Статус второго канала: {response2.status_code}")
            
            if response2.status_code == 200:
                print("🎉 УСПЕХ! Пост отправлен во второй канал!")
                return True
            else:
                print(f"⚠️ Второй канал: {response2.text}")
                return True
                
        else:
            print(f"❌ ОШИБКА TELEGRAM API: {response.text}")
            return False
            
    except Exception as e:
        print(f"💥 ИСКЛЮЧЕНИЕ: {e}")
        return False

if __name__ == "__main__":
    print("🚀 ЗАПУСК ТЕСТОВОГО БОТА...")
    success = test_bot()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ ТЕСТ ПРОЙДЕН! Проверь каналы Telegram.")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ ТЕСТ НЕ ПРОЙДЕН! Смотри ошибки выше.")
        print("=" * 50)
