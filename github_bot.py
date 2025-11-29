import os
import requests
import datetime
import hashlib
import json
import random
import time
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "post_history.json"

class ProfessionalPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        
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
        Ты профессиональный маркетолог, копирайтер и PR-специалист. Создай качественный пост для Telegram канала.

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

        ТРЕБОВАНИЯ:
        - Только уникальный, свежий контент 2024-2025
        - Конкретные цифры, исследования, факты
        - Естественные эмодзи для визуального акцента
        - Практическая ценность для читателя
        - Читабельный формат с абзацами
        - Живой, человеческий язык без шаблонов
        - Актуальные тренды и инсайты
        - Длина: оптимальная для чтения
        - НЕ добавляй хештеги в текст поста
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
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Добавляем хештеги к сгенерированному посту
                post_with_hashtags = self.add_hashtags(post_text, theme)
                return post_with_hashtags
            else:
                return None
                
        except Exception:
            return None

    def create_quality_fallback(self, theme, time_of_day):
        fallbacks = {
            "HR и управление персоналом": {
                "morning": """🚀 Утренний HR-заряд: Мотивация 2025

73% сотрудников теряют интерес к работе без регулярного фидбека. 

Ключевой инсайт: персональное внимание стоит дороже денег.

✅ Что работает сегодня:
• Еженедельные 15-минутные 1:1 встречи
• Система мгновенного признания достижений  
• Персональные карты развития
• Геймификация рабочих процессов

Кейс: внедрили систему микро-бонусов - вовлеченность выросла на 40%.

Инвестиции в отношения с командой окупаются лояльностью.

Как мотивируете свою команду?""",

                "afternoon": """📊 Глубокий анализ: Рекрутинг в эпоху AI

Новые данные 2025: 60% компаний используют AI для первичного отбора.

Главное: технологии не заменят человеческое чутье.

✅ Эффективный рекрутинг сегодня:
• AI-сортировка резюме + личная оценка
• Видео-интервью с анализом эмоций
• Тестовые рабочие дни вместо собеседований
• Реферальные программы с повышенным бонусом

Кейс: сократили время найма с 45 до 14 дней.

Баланс технологий и человеческого подхода - ключ к успеху.

Какие методы рекрутинга работают у вас?""",

                "evening": """🌙 Вечерние размышления: Лидерство 2025

82% сотрудников ценят эмпатию руководителя выше профессиональных навыков.

Суть: современный лидер - это вдохновитель, а не контролер.

✅ Практика эмпатичного лидерства:
• Регулярные "чашки кофе" с командой
• Открытость к ошибкам и обучению
• Прозрачность в принятии решений
• Поддержка work-life баланса

История: руководитель, который сам прошел все отделы, построил самую сплоченную команду.

Истинная сила лидера - в умении слушать и слышать.

Какие качества цените в руководителях?"""
            }
        }
        
        fallback_text = fallbacks[theme][time_of_day]
        return self.add_hashtags(fallback_text, theme)

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
            return response.status_code == 200
            
        except Exception:
            return False

    def run(self):
        try:
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            
            theme = self.select_todays_theme()
            
            post_text = self.generate_professional_post(theme, time_of_day)
            
            if not post_text or not self.is_content_unique(post_text):
                post_text = self.create_quality_fallback(theme, time_of_day)
            
            image_url = self.generate_thematic_image(theme)
            
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                self.mark_post_sent(post_text, theme)
                print(f"✅ Пост отправлен! Тема: {theme}, Время: {time_of_day}, Символов: {len(post_text)}")
            else:
                print("❌ Ошибка отправки")
            
        except Exception as e:
            print(f"💥 Ошибка: {e}")

def main():
    bot = ProfessionalPostGenerator()
    bot.run()

if __name__ == "__main__":
    main()
