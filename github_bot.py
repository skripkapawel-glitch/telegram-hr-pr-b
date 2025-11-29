import os
import requests
import datetime
import random
import sys
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@hr_na_dache"
ZEN_CHANNEL_ID = -1003322670507
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: ДИАГНОСТИЧЕСКАЯ ВЕРСИЯ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.author = "Маркетолог • SMM • PR • Копирайтер (40 лет опыта)"
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        
        self.theme_images = {
            "HR и управление персоналом": [
                "https://source.unsplash.com/1200x630/?office,team,meeting,hr",
                "https://source.unsplash.com/1200x630/?recruitment,interview,workplace",
                "https://source.unsplash.com/1200x630/?leadership,management,corporate"
            ],
            "PR и коммуникации": [
                "https://source.unsplash.com/1200x630/?media,press,communication,pr",
                "https://source.unsplash.com/1200x630/?public,relations,marketing,branding", 
                "https://source.unsplash.com/1200x630/?social,media,network,advertising"
            ],
            "ремонт и строительство": [
                "https://source.unsplash.com/1200x630/?renovation,construction,repair",
                "https://source.unsplash.com/1200x630/?building,architecture,design",
                "https://source.unsplash.com/1200x630/?interior,home,apartment"
            ]
        }
        
        self.knowledge_base = {
            "HR и управление персоналом": [
                "В 2024 году компании активно внедряют AI в процессы рекрутинга",
                "Тренд 2024: развитие soft skills становится приоритетом",
                "Diversity & Inclusion: 65% компаний внедрили программы разнообразия"
            ],
            "PR и коммуникации": [
                "Видеоконтент доминирует в 2024: short-form видео увеличивает вовлеченность",
                "LinkedIn становится ключевой B2B платформой",
                "AI-генерация контента: 45% PR-специалистов используют ChatGPT"
            ],
            "ремонт и строительство": [
                "Эко-тренды 2024: натуральные материалы и энергоэффективные решения",
                "Умный дом становится стандартом",
                "Модульные конструкции сокращают сроки строительства на 40%"
            ]
        }
    
    def load_post_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")
            return {}
    
    def generate_simple_post(self, theme, is_tg=True):
        """Простой генератор постов для тестирования"""
        facts = random.sample(self.knowledge_base[theme], 2)
        
        if is_tg:
            return f"""🚀 {theme.upper()} 2024

{facts[0]}

⸻

{facts[1]}

⸻

• Практический совет 1
• Практический совет 2  
• Практический совет 3

⸻

Что думаете о этих трендах?

#{theme.replace(' ', '')} #тренды2024"""
        else:
            return f"""Актуальные тенденции {theme.lower()} 2024

{facts[0]}

⸻

{facts[1]}

⸻

Современные вызовы требуют новых решений. Компании адаптируются к изменяющимся условиям.

⸻

Ключевые направления:

Цифровая трансформация
Внедрение современных технологических решений

Оптимизация процессов
Пересмотр традиционных подходов

Развитие компетенций  
Непрерывное обучение персонала"""

    def send_to_telegram(self, chat_id, text, image_url):
        """Отправляет пост в Telegram"""
        print(f"📤 Попытка отправки в chat_id: {chat_id}")
        print(f"📝 Текст: {text[:100]}...")
        print(f"🖼️ Фото: {image_url}")
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML"
        }
        
        try:
            print("🔄 Отправка запроса к Telegram API...")
            response = requests.post(url, json=payload, timeout=15)
            print(f"📡 Ответ API: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Пост успешно отправлен!")
                return True
            else:
                print(f"❌ Ошибка API: {response.status_code}")
                print(f"❌ Тело ответа: {response.text}")
                return False
                
        except Exception as e:
            print(f"💥 Исключение при отправке: {e}")
            return False
    
    def send_test_posts(self):
        """Тестовая отправка постов"""
        theme = random.choice(self.themes)
        print(f"🎯 Тема: {theme}")
        
        # Простые посты для теста
        tg_post = self.generate_simple_post(theme, is_tg=True)
        zen_post = self.generate_simple_post(theme, is_tg=False)
        
        # Тестовое фото
        test_image = "https://source.unsplash.com/1200x630/?office,work"
        
        print("=" * 50)
        print("🧪 ТЕСТОВАЯ ОТПРАВКА")
        print("=" * 50)
        
        # Пробуем отправить в оба канала
        tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, test_image)
        zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, test_image)
        
        return tg_success and zen_success

def main():
    print("🔍 ДИАГНОСТИКА ПЕРЕМЕННЫХ:")
    print(f"BOT_TOKEN: {'✅ УСТАНОВЛЕН' if BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
    print(f"GEMINI_API_KEY: {'✅ УСТАНОВЛЕН' if GEMINI_API_KEY else '❌ ОТСУТСТВУЕТ'}")
    print(f"MAIN_CHANNEL_ID: {MAIN_CHANNEL_ID}")
    print(f"ZEN_CHANNEL_ID: {ZEN_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        print("💥 КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не установлен!")
        print("💡 Проверь Secrets в настройках GitHub репозитория")
        return
    
    bot = SmartPostGenerator()
    success = bot.send_test_posts()
    
    if success:
        print("\n🎉 ТЕСТ ПРОЙДЕН! Посты должны быть в каналах.")
    else:
        print("\n💥 ТЕСТ НЕ ПРОЙДЕН! Проверь логи выше.")

if __name__ == "__main__":
    main()
