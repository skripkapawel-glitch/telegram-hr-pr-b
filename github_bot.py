import os
import requests
import datetime
import hashlib
import json
import random
import time
import schedule
import re
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

HISTORY_FILE = "post_history.json"

class StructuredTelegramPostBot:
    def __init__(self):
        self.history = self.load_history()
        
    def load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {
            "post_hashes": [],
            "used_themes": [],
            "used_keywords": [],
            "channel_analysis": {}
        }
    
    def save_history(self):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_channel_posts(self, limit=50):
        """Получает последние посты из канала для анализа"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatHistory"
            payload = {
                "chat_id": CHANNEL_ID,
                "limit": limit
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                posts = []
                if data.get("ok") and data.get("result"):
                    for message in data["result"]:
                        content = ""
                        if "text" in message:
                            content = message["text"]
                        elif "caption" in message:
                            content = message["caption"]
                        
                        if content and len(content.strip()) > 30:
                            posts.append(content)
                return posts
        except:
            pass
        return []

    def analyze_channel_content(self, posts):
        """Анализирует контент канала для определения тем и стиля"""
        if not posts:
            return {"themes": ["HR", "PR", "ремонт"], "keywords": [], "style": "профессиональный"}
        
        all_text = " ".join(posts).lower()
        
        theme_keywords = {
            "HR": ["hr", "персонал", "сотрудник", "рекрутинг", "найм", "мотивация", "команда", "кадр"],
            "PR": ["pr", "коммуникация", "бренд", "репутац", "медиа", "публичный", "сми"],
            "ремонт": ["ремонт", "строитель", "квартир", "дом", "дизайн", "интерьер", "отделк", "материал"]
        }
        
        detected_themes = []
        for theme, keywords in theme_keywords.items():
            theme_count = sum(1 for keyword in keywords if keyword in all_text)
            if theme_count >= 2:
                detected_themes.append(theme)
        
        words = re.findall(r'\b[а-яa-z]{4,}\b', all_text)
        stop_words = {'этот', 'это', 'также', 'очень', 'можно', 'будет', 'есть'}
        word_freq = Counter([word for word in words if word not in stop_words])
        top_keywords = [word for word, count in word_freq.most_common(10)]
        
        return {
            "themes": detected_themes if detected_themes else ["HR", "PR", "ремонт"],
            "keywords": top_keywords,
            "style": "профессиональный" if any(word in all_text for word in ["компания", "бизнес", "проект"]) else "разговорный"
        }

    def get_fresh_topic(self, channel_analysis):
        """Находит свежую тему на основе анализа канала и актуальных трендов"""
        used_themes = self.history.get("used_themes", [])
        used_keywords = self.history.get("used_keywords", [])
        
        available_themes = channel_analysis["themes"]
        
        theme_counts = {theme: used_themes.count(theme) for theme in available_themes}
        min_count = min(theme_counts.values())
        fresh_themes = [theme for theme, count in theme_counts.items() if count == min_count]
        
        selected_theme = random.choice(fresh_themes)
        
        prompt = f"""
        Проанализируй актуальные тренды и новости в сфере {selected_theme} и предложи 3 самые свежие и интересные темы для поста в Telegram. 
        
        Учти что в канале уже обсуждались эти ключевые слова: {', '.join(used_keywords[-5:]) if used_keywords else 'пока нет истории'}
        
        Ищи самые новые тенденции, проблемы и решения в этой области. Темы должны быть максимально актуальными и полезными.
        
        Верни только темы, разделенные знаком | без дополнительного текста.
        """
        
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 300,
                        "temperature": 0.9,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                topics_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                topics = [t.strip() for t in topics_text.split('|') if t.strip()]
                if topics:
                    return selected_theme, random.choice(topics)
        except:
            pass
        
        # Fallback если API не сработало
        fallback_topics = {
            "HR": ["Современные подходы к управлению командой", "Эффективные методы мотивации", "Тренды в рекрутинге"],
            "PR": ["Новые инструменты коммуникации", "Стратегии построения репутации", "Эффективный контент-маркетинг"],
            "ремонт": ["Инновационные материалы и технологии", "Эффективное планирование ремонта", "Современные решения в дизайне"]
        }
        
        topic = random.choice(fallback_topics.get(selected_theme, fallback_topics["HR"]))
        return selected_theme, topic

    def get_time_config(self, time_type):
        configs = {
            "morning": {"min_length": 300, "max_length": 500, "tone": "энергичный, мотивирующий"},
            "afternoon": {"min_length": 600, "max_length": 900, "tone": "аналитический, углубленный"},
            "evening": {"min_length": 500, "max_length": 700, "tone": "рефлексивный, вдохновляющий"}
        }
        return configs.get(time_type, configs["morning"])

    def generate_structured_post(self, time_type):
        """Генерирует пост по строгой структуре с контролем длины"""
        
        posts = self.get_channel_posts()
        channel_analysis = self.analyze_channel_content(posts)
        theme, topic = self.get_fresh_topic(channel_analysis)
        config = self.get_time_config(time_type)
        
        structure_prompt = f"""
        СОЗДАЙ ПОСТ ДЛЯ TELEGRAM КАНАЛА СТРОГО ПО СЛЕДУЮЩЕЙ СТРУКТУРЕ:

        ТЕМА: {theme}
        ПОДТЕМА: {topic}
        СТИЛЬ: {config['tone']}
        ДИАПАЗОН ДЛИНЫ: {config['min_length']}-{config['max_length']} символов (соблюдай точно!)

        СТРУКТУРА (соблюдай точно):

        1. ЗАЦЕПКА (1-2 строки)
        {{цепляющая фраза, эмоция, боль или интрига}}

        ⸻

        2. КОНТЕКСТ / ЧТО СЛУЧИЛОСЬ (1-3 строки)
        {{описываешь суть ситуации}}

        ⸻

        3. ГЛАВНАЯ МЫСЛЬ (одно предложение)
        {{суть поста}}

        ⸻

        4. ПОЛЕЗНОСТЬ (формат списка)
        • {{пункт 1}}
        • {{пункт 2}} 
        • {{пункт 3}}
        • {{пункт 4}}

        ⸻

        5. КОРОТКИЙ ОПЫТ / МИНИ-КЕЙС (1-2 строки)
        {{практический пример}}

        ⸻

        6. ИТОГ / ВЫВОД (одно сильное предложение)
        {{финальный акцент}}

        ⸻

        7. ЛЁГКИЙ CTA (без напора)
        {{вопрос / приглашение к диалогу}}

        КРИТИЧЕСКИ ВАЖНО:
        - Сохраняй ВСЕ разделители "⸻" точно как в шаблоне
        - Длина поста ДОЛЖНА быть от {config['min_length']} до {config['max_length']} символов
        - Пиши естественно, как для умного друга
        - Используй только актуальные данные и тренды
        - Добавь 1-2 уместных эмодзи в зацепку или CTA
        - Избегай корпоративного жаргона
        - Сделай текст цепляющим и полезным
        - Основывайся на реальных практиках и современных подходах

        Канал уже обсуждал: {', '.join(channel_analysis['keywords'][:3]) if channel_analysis['keywords'] else 'разные темы'}
        Сделай этот пост свежим и уникальным!
        """
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": structure_prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": config['max_length'] + 100,
                            "temperature": 0.8,
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    if (self.is_content_unique(post_text) and 
                        self.validate_structure(post_text) and 
                        self.validate_length(post_text, config)):
                        
                        self.mark_content_used(post_text, theme, topic)
                        return post_text
                    else:
                        continue
                        
            except:
                pass
        
        return None

    def validate_structure(self, post_text):
        """Проверяет что пост соответствует структуре"""
        return post_text.count("⸻") >= 6

    def validate_length(self, post_text, config):
        """Проверяет что длина поста в нужном диапазоне"""
        length = len(post_text)
        return config['min_length'] <= length <= config['max_length']

    def is_content_unique(self, content):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return content_hash not in self.history["post_hashes"]

    def mark_content_used(self, content, theme, topic):
        """Сохраняет информацию о использованном контенте"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        self.history["post_hashes"].append(content_hash)
        self.history["used_themes"].append(theme)
        
        keywords = re.findall(r'\b[а-яa-z]{4,}\b', topic.lower())
        self.history["used_keywords"].extend(keywords)
        
        for key in ["post_hashes", "used_themes", "used_keywords"]:
            if len(self.history[key]) > 200:
                self.history[key] = self.history[key][-200:]
        
        self.save_history()

    def send_post(self, post_text):
        """Отправляет пост в Telegram"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": CHANNEL_ID,
                "text": post_text,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, json=payload, timeout=30)
            return response.status_code == 200
        except:
            return False

    def create_and_send_post(self, time_type):
        """Создает и отправляет пост"""
        config = self.get_time_config(time_type)
        print(f"🔄 Создание {time_type} поста ({config['min_length']}-{config['max_length']} символов)...")
        
        posts = self.get_channel_posts()
        analysis = self.analyze_channel_content(posts)
        print(f"📊 Обнаружены темы: {', '.join(analysis['themes'])}")
        
        post_text = self.generate_structured_post(time_type)
        
        if post_text:
            success = self.send_post(post_text)
            if success:
                print(f"✅ {time_type.capitalize()} пост отправлен!")
                print(f"📝 Длина: {len(post_text)} символов")
                print(f"🎯 Тема: {analysis['themes'][0] if analysis['themes'] else 'HR'}")
            else:
                print(f"❌ Ошибка отправки {time_type} поста")
        else:
            print(f"❌ Не удалось сгенерировать {time_type} пост")

def morning_post():
    bot = StructuredTelegramPostBot()
    bot.create_and_send_post("morning")

def afternoon_post():
    bot = StructuredTelegramPostBot()
    bot.create_and_send_post("afternoon")

def evening_post():
    bot = StructuredTelegramPostBot()
    bot.create_and_send_post("evening")

def main():
    schedule.every().day.at("09:00").do(morning_post)
    schedule.every().day.at("14:00").do(afternoon_post)
    schedule.every().day.at("19:00").do(evening_post)
    
    print("🤖 Умный бот запущен!")
    print("🎯 Направления: HR, PR, ремонт и строительство")
    print("📐 Формат: 7-блочная структура с разделителями")
    print("⏰ Расписание: 09:00 (300-500), 14:00 (600-900), 19:00 (500-700)")
    print("🔍 Функции: авто-анализ канала + актуальные тренды + проверка уникальности")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
