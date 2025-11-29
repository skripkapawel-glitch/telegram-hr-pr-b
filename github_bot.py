import os
import requests
import datetime
import hashlib
import json
import random
import time
import sys
from dotenv import load_dotenv

load_dotenv()

# Получаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🔍 ДИАГНОСТИКА ЗАПУСКА")
print("=" * 80)
print(f"BOT_TOKEN: {'✅ Есть' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
print(f"CHANNEL_ID: {'✅ ' + CHANNEL_ID if CHANNEL_ID else '❌ ОТСУТСТВУЕТ'}")
print(f"GEMINI_API_KEY: {'✅ Есть' if GEMINI_API_KEY else '❌ ОТСУТСТВУЕТ'}")

if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_API_KEY]):
    print("💥 КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют необходимые переменные окружения!")
    sys.exit(1)

print("=" * 80)

class SimplePostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
    def get_time_of_day(self):
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12: return "morning"
        elif 12 <= hour < 18: return "afternoon" 
        else: return "evening"
    
    def generate_simple_post(self, theme, time_of_day):
        """Простая генерация поста через Gemini"""
        prompt = f"""
        Создай короткий пост для Telegram на тему "{theme}" в {time_of_day} время.
        Пост должен быть практичным и полезным. 3-4 абзаца.
        """
        
        try:
            print(f"🧠 Генерация поста: {theme}...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            response = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 500,
                        "temperature": 0.7,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"✅ Пост сгенерирован ({len(post_text)} символов)")
                return post_text
            else:
                print(f"❌ Ошибка Gemini: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return None
    
    def send_test_message(self):
        """Простая тестовая отправка"""
        print("📤 Тестовая отправка сообщения...")
        
        # Сначала пробуем отправить простое текстовое сообщение
        test_message = f"🧪 Тестовый пост\nВремя: {datetime.datetime.now().strftime('%H:%M')}\nТема: {random.choice(self.themes)}"
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": test_message,
            "parse_mode": "HTML"
        }
        
        try:
            print(f"🔗 URL: {url}")
            print(f"📝 Payload: {payload}")
            
            response = requests.post(url, json=payload, timeout=15)
            print(f"📡 Статус: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print("✅ ТЕСТОВОЕ СООБЩЕНИЕ ОТПРАВЛЕНО УСПЕШНО!")
                    return True
                else:
                    print(f"❌ Ошибка в ответе: {result}")
                    return False
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при отправке: {e}")
            return False
    
    def send_ai_post(self):
        """Отправка AI-поста"""
        theme = random.choice(self.themes)
        time_of_day = self.get_time_of_day()
        
        print(f"🎯 Тема: {theme}")
        print(f"⏰ Время: {time_of_day}")
        
        # Генерируем пост
        post_text = self.generate_simple_post(theme, time_of_day)
        
        if not post_text:
            # Fallback если AI не сработал
            post_text = f"""🚀 {theme}

Актуальные тренды 2024 года в этой сфере показывают рост эффективности на 30-40%.

💡 Практические советы:
• Внедряйте современные подходы
• Используйте аналитику данных  
• Обучайте команду регулярно
• Тестируйте новые методики

Реальный кейс показывает увеличение эффективности на 35%.

💬 Что думаете об этих трендах?"""
        
        # Добавляем хештеги
        hashtags = {
            "HR и управление персоналом": "#HR #управление #команда #2024",
            "PR и коммуникации": "#PR #коммуникации #бренд #2024", 
            "ремонт и строительство": "#ремонт #стройка #дизайн #2024"
        }
        
        full_post = f"{post_text}\n\n{hashtags.get(theme, '#2024')}"
        
        print(f"📝 Финальный пост ({len(full_post)} символов):")
        print("-" * 50)
        print(full_post[:200] + "..." if len(full_post) > 200 else full_post)
        print("-" * 50)
        
        # Отправляем в Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": full_post,
            "parse_mode": "HTML"
        }
        
        try:
            print("📤 Отправка AI-поста...")
            response = requests.post(url, json=payload, timeout=15)
            print(f"📡 Статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print("✅ AI-ПОСТ УСПЕШНО ОТПРАВЛЕН!")
                    return True
                else:
                    print(f"❌ Ошибка: {result}")
                    return False
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                print(f"📄 Текст ответа: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False

def main():
    print("\n🚀 ЗАПУСК ПРОСТОГО ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    
    bot = SimplePostGenerator()
    
    # Сначала тестовая отправка
    print("\n1. ТЕСТОВАЯ ОТПРАВКА:")
    test_success = bot.send_test_message()
    
    if test_success:
        print("\n2. ОТПРАВКА AI-ПОСТА:")
        ai_success = bot.send_ai_post()
        
        if ai_success:
            print("\n🎉 ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО!")
        else:
            print("\n💥 AI-ПОСТ НЕ ОТПРАВЛЕН!")
    else:
        print("\n💥 ТЕСТОВАЯ ОТПРАВКА НЕ УДАЛАСЯ!")
        print("Возможные причины:")
        print("• Неправильный BOT_TOKEN")
        print("• Неправильный CHANNEL_ID") 
        print("• Бот не добавлен в канал как администратор")
        print("• Проблемы с сетью")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
