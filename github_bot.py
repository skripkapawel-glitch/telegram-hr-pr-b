import os
import requests
import datetime
import hashlib
import json
import random
import time
import re
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "post_history.json"

class AutoPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        
        self.main_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.time_configs = {
            "morning": {"min_chars": 300, "max_chars": 500, "description": "короткие, энергичные"},
            "afternoon": {"min_chars": 600, "max_chars": 900, "description": "подробные, аналитические"},
            "evening": {"min_chars": 500, "max_chars": 700, "description": "рефлексивные, вдохновляющие"}
        }

    def load_post_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
            
        return {
            "post_hashes": [],
            "daily_posts": {},
            "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
        }

    def save_post_history(self):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_time_of_day(self):
        current_hour = datetime.datetime.now().hour
        if 6 <= current_hour < 12:
            return "morning"
        elif 12 <= current_hour < 18:
            return "afternoon"
        else:
            return "evening"

    def select_todays_theme(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if today not in self.history["daily_posts"]:
            self.history["daily_posts"][today] = []
        
        used_themes_today = self.history["daily_posts"][today]
        available_themes = [theme for theme in self.main_themes if theme not in used_themes_today]
        
        if not available_themes:
            available_themes = self.main_themes
        
        return random.choice(available_themes)

    def generate_ai_post(self, theme, time_of_day):
        time_config = self.time_configs[time_of_day]
        
        prompt = f"""
        СОЗДАЙ УНИКАЛЬНЫЙ И ЦЕПЛЯЮЩИЙ ПОСТ ДЛЯ TELEGRAM КАНАЛА
        
        ТЕМА: {theme}
        ВРЕМЯ СУТОК: {time_of_day} ({time_config['description']})
        
        СТРОГО СОБЛЮДАЙ 7-БЛОЧНУЮ СТРУКТУРУ:
        
        1. HOOK (1-2 строки)
        Цепляющая фраза, эмоция, боль или интрига
        
        ⸻
        
        2. Контекст / что случилось
        1-3 строки, описываешь суть ситуации
        
        ⸻
        
        3. Главная мысль
        Одно предложение, суть поста
        
        ⸻
        
        4. Полезность (список)
        • пункт 1
        • пункт 2  
        • пункт 3
        • пункт 4
        • пункт 5 (опционально)
        
        ⸻
        
        5. Короткий опыт / мини-кейс
        1-2 строки реального опыта
        
        ⸻
        
        6. Итог / вывод
        Одно сильное предложение
        
        ⸻
        
        7. Лёгкий CTA
        Вопрос или приглашение к диалогу
        
        ТРЕБОВАНИЯ:
        - Длина: {time_config['min_chars']}-{time_config['max_chars']} символов
        - Только актуальная информация 2024-2025 года
        - Конкретные цифры, факты, исследования
        - Уникальный контент (не копируй чужие тексты)
        - Естественные эмодзи (2-3 штуки)
        - Практическая польза для читателя
        - Цепляющий заголовок (HOOK)
        - Тон: {time_config['description']}
        """

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 1500,
                        "temperature": 0.9,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                return None
                
        except Exception:
            return None

    def create_fallback_post(self, theme, time_of_day):
        hooks = {
            "HR и управление персоналом": [
                "🚀 Шок: 67% сотрудников готовы уйти за бОльшую зарплату",
                "💥 HR-бомба: найм стоит в 3 раза дороже удержания", 
                "🎯 Секрет Google: почему их сотрудники не уходят"
            ],
            "PR и коммуникации": [
                "📱 TikTok убил традиционный PR? Шокирующие цифры",
                "🔥 Кризис в соцсетях: как не потерять лицо за 15 минут",
                "💎 Бренд-медиа: почему СМИ теперь работают на вас"
            ],
            "ремонт и строительство": [
                "🏠 Ремонт-2025: цены взлетели, но есть лайфхаки",
                "💡 Умный дом: как сэкономить 50% на коммуналке",
                "📐 Дизайн-ход: перепланировка, которая увеличит стоимость квартиры"
            ]
        }
        
        hook = random.choice(hooks.get(theme, hooks["HR и управление персоналом"]))
        return f"{hook}\n\nПост временно недоступен. Возвращайтесь позже!"

    def is_content_unique(self, content):
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return content_hash not in self.history["post_hashes"]

    def mark_post_sent(self, content, theme):
        content_hash = hashlib.md5(content.encode()).hexdigest()
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        self.history["post_hashes"].append(content_hash)
        
        if today not in self.history["daily_posts"]:
            self.history["daily_posts"][today] = []
        
        self.history["daily_posts"][today].append(theme)
        
        if len(self.history["post_hashes"]) > 200:
            self.history["post_hashes"] = self.history["post_hashes"][-200:]
        
        self.save_post_history()

    def send_to_telegram(self, message):
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": CHANNEL_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=payload, timeout=30)
            return response.status_code == 200
            
        except Exception:
            return False

    def run(self):
        try:
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            time_config = self.time_configs[time_of_day]
            
            theme = self.select_todays_theme()
            
            post_text = self.generate_ai_post(theme, time_of_day)
            
            if not post_text or not self.is_content_unique(post_text):
                post_text = self.create_fallback_post(theme, time_of_day)
            
            success = self.send_to_telegram(post_text)
            
            if success:
                self.mark_post_sent(post_text, theme)
                print(f"✅ Пост отправлен! Тема: {theme}, Время: {time_of_day}, Символов: {len(post_text)}")
            else:
                print("❌ Ошибка отправки")
            
        except Exception as e:
            print(f"💥 Ошибка: {e}")

def main():
    bot = AutoPostGenerator()
    bot.run()

if __name__ == "__main__":
    main()
