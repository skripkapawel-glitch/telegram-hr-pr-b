import os
import requests
import time
import sys
from dotenv import load_dotenv

# Принудительно включаем логирование
print("🐛 START: Бот запущен")
sys.stdout.flush()

load_dotenv()

print("🐛 DOTENV: Загружены переменные")
sys.stdout.flush()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@hr_na_dache" 
ZEN_CHANNEL_ID = -1003322670507

print("=" * 80)
print("🧪 ТЕСТ БОТА - ДЕТАЛЬНАЯ ДИАГНОСТИКА")
print("=" * 80)
sys.stdout.flush()

def debug_log(message):
    """Детальное логирование с принудительным выводом"""
    print(f"🔍 {message}")
    sys.stdout.flush()
    time.sleep(0.1)  # Небольшая пауза для гарантии вывода

def test_bot():
    debug_log("Начало тестирования")
    
    # Проверяем переменные окружения
    debug_log("Проверка переменных...")
    debug_log(f"BOT_TOKEN: {'✅ ЕСТЬ' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    debug_log(f"MAIN_CHANNEL_ID: {MAIN_CHANNEL_ID}")
    debug_log(f"ZEN_CHANNEL_ID: {ZEN_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        debug_log("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN пустой!")
        debug_log("Проверь Secrets в GitHub:")
        debug_log("1. BOT_TOKEN")
        debug_log("2. CHANNEL_ID")
        debug_log("3. GEMINI_API_KEY")
        return False

    # Тестовые данные
    test_text = """🧪 ТЕСТОВЫЙ ПОСТ ОТ БОТА

Дата: 2024 год
Время: тестирование

✅ Если вы видите этот пост - бот работает корректно!

#тест #бот #работает"""
    
    test_image = "https://source.unsplash.com/1200x630/?office,team,work"
    
    debug_log(f"Текст поста: {test_text}")
    debug_log(f"URL изображения: {test_image}")

    # Пробуем отправить в основной канал
    debug_log("Попытка отправки в основной канал...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": MAIN_CHANNEL_ID,
        "photo": test_image, 
        "caption": test_text,
        "parse_mode": "HTML"
    }
    
    debug_log(f"URL API: {url.split('/bot')[0]}/botXXX...")
    debug_log(f"Payload: {payload}")

    try:
        debug_log("Отправка запроса к Telegram API...")
        response = requests.post(url, json=payload, timeout=30)
        debug_log(f"Получен ответ: {response.status_code}")
        
        if response.status_code == 200:
            debug_log("✅ УСПЕХ: Пост отправлен в основной канал!")
            
            # Пробуем отправить во второй канал
            debug_log("Попытка отправки во второй канал...")
            payload["chat_id"] = ZEN_CHANNEL_ID
            response2 = requests.post(url, json=payload, timeout=30)
            debug_log(f"Ответ второго канала: {response2.status_code}")
            
            if response2.status_code == 200:
                debug_log("✅ УСПЕХ: Пост отправлен во второй канал!")
                return True
            else:
                debug_log(f"⚠️ Второй канал не ответил: {response2.text}")
                return True
        else:
            debug_log(f"❌ ОШИБКА TELEGRAM: {response.status_code}")
            debug_log(f"❌ ТЕЛО ОТВЕТА: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        debug_log("💥 ТАЙМАУТ: Запрос к Telegram превысил время ожидания")
        return False
    except requests.exceptions.ConnectionError:
        debug_log("💥 ОШИБКА ПОДКЛЮЧЕНИЯ: Не удалось соединиться с Telegram")
        return False
    except Exception as e:
        debug_log(f"💥 НЕИЗВЕСТНАЯ ОШИБКА: {str(e)}")
        return False

if __name__ == "__main__":
    debug_log("🚀 ЗАПУСК ГЛАВНОЙ ФУНКЦИИ")
    
    success = test_bot()
    
    debug_log("ЗАВЕРШЕНИЕ РАБОТЫ БОТА")
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 ТЕСТ ПРОЙДЕН! Проверь каналы Telegram.")
        print("=" * 80)
    else:
        print("\n" + "=" * 80) 
        print("❌ ТЕСТ НЕ ПРОЙДЕН! Смотри ошибки выше.")
        print("=" * 80)
    
    sys.stdout.flush()
    time.sleep(2)  # Пауза чтобы гарантировать вывод всех логов
