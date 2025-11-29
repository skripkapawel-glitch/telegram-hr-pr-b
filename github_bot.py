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

class ProfessionalPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        self.main_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.time_configs = {
            "morning": {"target_chars": 800, "description": "энергичный, мотивирующий, практичный"},
            "afternoon": {"target_chars": 1200, "description": "аналитический, экспертный, информативный"}, 
            "evening": {"target_chars": 1000, "description": "рефлексивный, вдохновляющий, дружеский"}
        }
        
        self.hashtags = {
            "HR и управление персоналом": [
                "#HR", "#рекрутинг", "#управлениеперсоналом", "#мотивация", "#команда",
                "#кадры", "#HRаналитика", "#развитиеперсонала", "#брендработодателя", 
                "#корпоративнаякультура", "#лидерство", "#управление", "#бизнес",
                "#карьера", "#работа", "#2025", "#тренды2025"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#пиар", "#бренд", "#репутация", 
                "#медиа", "#соцсети", "#маркетинг", "#контент", "#SMM",
                "#кризисныекоммуникации", "#брендинг", "#инфлюенсеры",
                "#digital", "#продвижение", "#2025", "#новоевPR"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", "#квартира",
                "#дом", "#евроремонт", "#стройка", "#материалы", "#технологии",
                "#умныйдом", "#энергоэффективность", "#перепланировка",
                "#недвижимость", "#жилье", "#2025", "#трендыремонта"
            ]
        }

    def load_post_history(self):
        """Загружает историю и сразу обновляет файл"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {
                    "post_hashes": [],
                    "daily_posts": {},
                    "channel_analysis": {},
                    "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
                }
            
            # Очищаем старые данные (больше 7 дней)
            self.clean_old_history(history)
            return history
            
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")
            return {
                "post_hashes": [],
                "daily_posts": {},
                "channel_analysis": {},
                "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
            }

    def clean_old_history(self, history):
        """Очищает историю старше 7 дней"""
        today = datetime.datetime.now()
        dates_to_remove = []
        
        for date_str in history.get("daily_posts", {}):
            try:
                post_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                if (today - post_date).days > 7:
                    dates_to_remove.append(date_str)
            except:
                continue
        
        for date_str in dates_to_remove:
            del history["daily_posts"][date_str]

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения: {e}")

    def get_time_of_day(self):
        current_hour = datetime.datetime.now().hour
        if 6 <= current_hour < 12:
            return "morning"
        elif 12 <= current_hour < 18:
            return "afternoon"
        else:
            return "evening"

    def get_channel_posts(self, limit=50):
        """Получает посты из Telegram канала"""
        print("📊 Анализируем посты в канале...")
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatHistory"
            payload = {
                "chat_id": CHANNEL_ID,
                "limit": limit
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
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
                        posts.append({
                            "content": content,
                            "date": message.get("date", ""),
                            "message_id": message.get("message_id")
                        })
            
            print(f"✅ Получено {len(posts)} постов из канала")
            return posts
            
        except Exception as e:
            print(f"❌ Ошибка получения постов: {e}")
            return []

    def analyze_channel_content(self, posts):
        """Анализирует контент канала"""
        if not posts:
            return {
                "used_themes": [],
                "frequent_words": [],
                "post_frequency": {}
            }
        
        analysis = {
            "used_themes": [],
            "frequent_words": [],
            "post_frequency": {}
        }
        
        all_content = " ".join([post["content"] for post in posts])
        
        # Анализ тем
        for theme in self.main_themes:
            theme_keywords = self.get_theme_keywords(theme)
            for keyword in theme_keywords:
                if keyword in all_content.lower():
                    if theme not in analysis["used_themes"]:
                        analysis["used_themes"].append(theme)
                    break
        
        # Анализ частых слов
        words = re.findall(r'\b[а-яa-z]{4,}\b', all_content.lower())
        stop_words = {
            'этот', 'это', 'также', 'очень', 'можно', 'будет', 'есть', 
            'который', 'только', 'после', 'когда', 'потому', 'может'
        }
        word_freq = Counter([word for word in words if word not in stop_words])
        analysis["frequent_words"] = [word for word, count in word_freq.most_common(15)]
        
        return analysis

    def get_theme_keywords(self, theme):
        """Ключевые слова для определения темы"""
        keywords = {
            "HR и управление персоналом": [
                "hr", "персонал", "сотрудник", "команда", "рекрутинг", "найм",
                "мотивация", "обучение", "развитие", "кадр", "hrbp", "kpi"
            ],
            "PR и коммуникации": [
                "pr", "коммуникация", "бренд", "репутац", "медиа", "пиар",
                "публичный", "сми", "информация", "комьюнити"
            ],
            "ремонт и строительство": [
                "ремонт", "строитель", "квартир", "дом", "дизайн", "интерьер",
                "отделк", "материал", "проект", "ремонт", "строит", "объект"
            ]
        }
        return keywords.get(theme, [])

    def select_optimal_theme(self, channel_analysis):
        """Выбирает оптимальную тему на основе анализа канала"""
        used_themes = channel_analysis.get("used_themes", [])
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Сразу обновляем историю перед выбором темы
        self.history = self.load_post_history()
        
        # Учитываем посты за сегодня
        today_posts = self.history.get("daily_posts", {}).get(today, [])
        
        print(f"📅 Сегодня уже были темы: {today_posts}")
        
        # Доступные темы (которые еще не использовались сегодня)
        available_themes = [theme for theme in self.main_themes if theme not in today_posts]
        
        if available_themes:
            # Выбираем из доступных тем ту, что реже всего использовалась в истории
            theme_counts = {}
            for theme in available_themes:
                theme_counts[theme] = used_themes.count(theme)
            
            min_count = min(theme_counts.values()) if theme_counts else 0
            best_themes = [theme for theme, count in theme_counts.items() if count == min_count]
            selected_theme = random.choice(best_themes) if best_themes else random.choice(available_themes)
        else:
            # Если все темы уже использовались сегодня, выбираем случайную
            selected_theme = random.choice(self.main_themes)
        
        print(f"🎯 Выбрана тема: {selected_theme}")
        return selected_theme

    def generate_thematic_image(self, theme):
        theme_keywords = {
            "HR и управление персоналом": "business,team,office,professional,meeting",
            "PR и коммуникации": "media,communication,social,network,marketing",
            "ремонт и строительство": "construction,design,architecture,home,renovation"
        }
        
        keywords = theme_keywords.get(theme, "business,development")
        timestamp = int(time.time() * 1000)
        
        return f"https://picsum.photos/1200/800?random={timestamp}&blur=1"

    def add_hashtags(self, post_text, theme):
        """Добавляет релевантные хештеги к посту"""
        theme_hashtags = self.hashtags.get(theme, [])
        
        # Выбираем 5-7 самых релевантных хештегов
        selected_hashtags = random.sample(theme_hashtags, min(7, len(theme_hashtags)))
        
        hashtags_string = " ".join(selected_hashtags)
        
        # Добавляем хештеги в конец поста
        return f"{post_text}\n\n{hashtags_string}"

    def generate_professional_post(self, theme, time_of_day):
        tone = self.time_configs[time_of_day]["description"]
        
        prompt = f"""
        Ты профессиональный маркетолог, копирайтер и PR-специалист. Создай УНИКАЛЬНЫЙ пост для Telegram канала.

        ТЕМА: {theme}
        ТОН: {tone}
        ВРЕМЯ СУТОК: {time_of_day}

        СТРУКТУРА ПОСТА:
        
        🎯 HOOK - цепляющий заголовок (1-2 строки, максимум вовлечения)
        
        📝 Контекст - краткое введение в проблему (2-3 строки)
        
        💡 Главная мысль - ключевой инсайт (1 предложение)
        
        ✅ Практическая польза - конкретные действия:
        • Пункт 1
        • Пункт 2  
        • Пункт 3
        • Пункт 4
        
        🎪 Мини-кейс - реальный пример (1-2 строки)
        
        🔚 Итог - сильный вывод
        
        💬 CTA - легкий призыв к обсуждению

        КРИТИЧЕСКИ ВАЖНО:
        - Пост должен быть АБСОЛЮТНО УНИКАЛЬНЫМ
        - НЕ повторять предыдущие посты
        - Использовать РАЗНЫЕ углы и примеры
        - Только свежие данные 2024-2025
        - Конкретные цифры и исследования
        - Естественные эмодзи для визуального акцента
        - Практическая ценность для читателя
        - Живой, человеческий язык без шаблонов
        - НЕ добавляй хештеги в текст поста
        """

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 1500,
                        "temperature": 0.95,  # Повышаем температуру для большей уникальности
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Добавляем хештеги к сгенерированному посту
                post_with_hashtags = self.add_hashtags(post_text, theme)
                return post_with_hashtags
            else:
                return None
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return None

    def is_content_unique(self, content):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Сразу обновляем историю перед проверкой
        self.history = self.load_post_history()
        
        is_unique = content_hash not in self.history["post_hashes"]
        
        if not is_unique:
            print("⚠️ Обнаружен повторяющийся контент")
        
        return is_unique

    def mark_post_sent(self, content, theme):
        """Сохраняет пост в историю СРАЗУ ЖЕ"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Сначала загружаем актуальную историю
        self.history = self.load_post_history()
        
        # Добавляем данные
        self.history["post_hashes"].append(content_hash)
        
        if today not in self.history["daily_posts"]:
            self.history["daily_posts"][today] = []
        
        self.history["daily_posts"][today].append(theme)
        
        # Ограничиваем размер истории
        if len(self.history["post_hashes"]) > 200:
            self.history["post_hashes"] = self.history["post_hashes"][-200:]
        
        # СРАЗУ сохраняем
        self.save_post_history()
        
        print(f"💾 Пост сохранен в историю: {theme}")

    def send_to_telegram(self, message, image_url=None):
        try:
            if image_url:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": message,
                    "parse_mode": "HTML"
                }
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            print("✅ Пост отправлен в Telegram!")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False

    def run(self):
        try:
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            time_config = self.time_configs[time_of_day]
            
            print(f"\n{'='*50}")
            print(f"🚀 ПРОФЕССИОНАЛЬНЫЙ ГЕНЕРАТОР ПОСТОВ")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"⏰ Время: {time_of_day} ({time_config['description']})")
            print(f"🆔 Сессия: {self.session_id}")
            print(f"{'='*50}")
            
            # Анализ канала
            posts = self.get_channel_posts()
            channel_analysis = self.analyze_channel_content(posts)
            
            # Выбор темы на основе анализа
            theme = self.select_optimal_theme(channel_analysis)
            
            # Генерация поста
            post_text = self.generate_professional_post(theme, time_of_day)
            
            # Проверка уникальности и повторная генерация при необходимости
            max_attempts = 3
            attempt = 0
            
            while attempt < max_attempts:
                if post_text and self.is_content_unique(post_text):
                    break
                else:
                    print(f"🔄 Попытка {attempt + 1}: генерируем уникальный пост...")
                    post_text = self.generate_professional_post(theme, time_of_day)
                    attempt += 1
            
            if not post_text:
                print("❌ Не удалось сгенерировать уникальный пост")
                return
            
            image_url = self.generate_thematic_image(theme)
            
            print(f"📊 Результат:")
            print(f"   Тема: {theme}")
            print(f"   Длина: {len(post_text)} символов")
            print(f"   Время: {time_of_day}")
            
            # Отправка
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                # СРАЗУ сохраняем в историю
                self.mark_post_sent(post_text, theme)
                print(f"✅ Готово! Уникальный пост создан и отправлен.")
            else:
                print("❌ Ошибка при отправке")
            
            print(f"{'='*50}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    bot = ProfessionalPostGenerator()
    bot.run()

if __name__ == "__main__":
    main()
