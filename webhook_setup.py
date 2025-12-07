# webhook_setup.py - настройка вебхука Telegram
import os
import requests
import sys

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # URL вашего вебхука

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not WEBHOOK_URL:
    print("⚠️ WEBHOOK_URL не установлен, использую GitHub Actions URL")
    # Для GitHub Actions можно использовать ngrok или другой сервис
    print("📝 Для работы вставьте URL вебхука в переменную WEBHOOK_URL")
    sys.exit(1)

def set_webhook():
    """Устанавливает вебхук для бота"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    data = {
        "url": WEBHOOK_URL,
        "drop_pending_updates": True,
        "allowed_updates": ["callback_query", "message"]
    }
    
    print(f"🔗 Устанавливаю вебхук: {WEBHOOK_URL}")
    
    response = requests.post(url, json=data, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("✅ Вебхук успешно установлен!")
            print(f"📊 Результат: {result.get('description', 'Успешно')}")
        else:
            print(f"❌ Ошибка: {result.get('description', 'Неизвестная ошибка')}")
    else:
        print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")

def delete_webhook():
    """Удаляет вебхук"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    print("🗑️ Удаляю вебхук...")
    
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("✅ Вебхук удален!")
        else:
            print(f"❌ Ошибка: {result.get('description', 'Неизвестная ошибка')}")
    else:
        print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")

def get_webhook_info():
    """Получает информацию о текущем вебхуке"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    print("📊 Получаю информацию о вебхуке...")
    
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            info = result.get("result", {})
            print(f"✅ URL: {info.get('url', 'Не установлен')}")
            print(f"✅ Ожидающих обновлений: {info.get('pending_update_count', 0)}")
            print(f"✅ Последняя ошибка: {info.get('last_error_message', 'Нет ошибок')}")
        else:
            print(f"❌ Ошибка: {result.get('description', 'Неизвестная ошибка')}")
    else:
        print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")

if __name__ == "__main__":
    print("🤖 Настройка вебхука Telegram Bot")
    print("=" * 50)
    
    while True:
        print("\nВыберите действие:")
        print("1. Установить вебхук")
        print("2. Удалить вебхук")
        print("3. Получить информацию о вебхуке")
        print("4. Выход")
        
        choice = input("\nВведите номер: ").strip()
        
        if choice == "1":
            set_webhook()
        elif choice == "2":
            delete_webhook()
        elif choice == "3":
            get_webhook_info()
        elif choice == "4":
            print("👋 Выход...")
            break
        else:
            print("❌ Неверный выбор")
