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

# Загружаем настройки
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Файл для хранения хешей постов
HISTORY_FILE = "post_history.json"

class EmojiPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        # Основные темы канала
        self.main_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        # Подтемы для каждой основной темы (без удаленки)
        self.subthemes = {
            "HR и управление персоналом": [
                "рекрутинг и найм 👔", "мотивация сотрудников 💪", "обучение и развитие 🎓",
                "корпоративная культура 🏢", "оценка персонала 📊", "управление талантами 🌟",
                "HR аналитика 📈", "лидерство 👑", "командообразование 🤝", "карьерный рост 🚀",
                "онбординг 🎯", "тимбилдинг 🎪", "бенефиты 🎁", "KPI и цели 🎯"
            ],
            "PR и коммуникации": [
                "медиарилейшнз 📰", "брендинг 🎨", "кризисные коммуникации 🚨", 
                "социальные сети 📱", "внутренние коммуникации 🗣️", "корпоративная социальная ответственность 🌍",
                "пиар стратегия 🎯", "репутационный менеджмент 🛡️", "инфлюенсер маркетинг 🌟", "контент маркетинг ✍️",
                "ивенты и мероприятия 🎪", "комьюнити менеджмент 👥", "бренд-медиа 📺", "PR кампании 🎬"
            ],
            "ремонт и строительство": [
                "современные материалы 🏗️", "технологии строительства 🔨", "дизайн интерьера 🎨",
                "управление проектами 📋", "смета и бюджет 💰", "ремонт под ключ 🔑",
                "умный дом 🤖", "энергоэффективность 💡", "евроремонт 🏠", "реставрация 🏛️",
                "отделочные работы 🎨", "архитектура 📐", "ландшафтный дизайн 🌿", "строительные нормы 📏"
            ]
        }
        
        # Эмодзи для форматов и акцентов
        self.formats = [
            "🎯 {content}", "🔥 {content}", "💡 {content}", "🚀 {content}",
            "🌟 {content}", "📈 {content}", "👥 {content}", "💼 {content}",
            "🏗️ {content}", "📢 {content}", "🤝 {content}", "💎 {content}",
            "✨ {content}", "🎨 {content}", "📊 {content}", "👑 {content}",
            "🛠️ {content}", "🎪 {content}", "🔄 {content}", "⚡ {content}"
        ]

        # Эмодзи для разных секций постов
        self.emoji_sections = {
            "header": ["🎯", "🔥", "💡", "🚀", "🌟", "📢", "💎", "✨", "⚡", "🎪"],
            "fact": ["📊", "📈", "📉", "🔢", "💯", "🎯", "🔍", "📋", "📝", "🎓"],
            "tip": ["💡", "🔑", "🎁", "💎", "✨", "🌟", "⚡", "🔮", "🧠", "💭"],
            "action": ["🚀", "🎯", "👣", "🔄", "⚡", "🔨", "🏃‍♂️", "🎪", "🏆", "✅"],
            "discussion": ["💬", "👥", "🤝", "🗣️", "👂", "💭", "🤔", "💡", "🎤", "📢"]
        }

        # Настройки длины по времени суток
        self.time_settings = {
            "morning": {  # 9:00
                "max_tokens": 400,
                "target_length": "300-500 символов",
                "description": "короткий утренний пост"
            },
            "afternoon": {  # 14:00
                "max_tokens": 1000,
                "target_length": "500-1200 символов", 
                "description": "развернутый дневной пост"
            },
            "evening": {  # 19:00
                "max_tokens": 700,
                "target_length": "400-800 символов",
                "description": "вечерний пост средней длины"
            }
        }

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")
            
        return {
            "post_hashes": [],
            "used_themes": [],
            "used_subthemes": [],
            "used_formats": [],
            "channel_analysis": {},
            "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
        }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения: {e}")

    def get_time_of_day(self):
        """Определяет время суток и настройки"""
        current_hour = datetime.datetime.now().hour
        
        if current_hour == 6:  # 9:00 МСК
            return "morning"
        elif current_hour == 11:  # 14:00 МСК
            return "afternoon" 
        elif current_hour == 16:  # 19:00 МСК
            return "evening"
        else:
            return "afternoon"  # по умолчанию

    def get_channel_posts(self, limit=100):
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
                    
                    if content and len(content.strip()) > 50:
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
                "used_subthemes": [],
                "frequent_words": [],
                "post_frequency": {},
                "recent_patterns": []
            }
        
        analysis = {
            "used_themes": [],
            "used_subthemes": [],
            "frequent_words": [],
            "post_frequency": {},
            "recent_patterns": []
            }
        
        # Анализ тем и подтем
        all_content = " ".join([post["content"] for post in posts])
        
        # Определяем использованные темы
        for theme in self.main_themes:
            theme_keywords = self.get_theme_keywords(theme)
            for keyword in theme_keywords:
                if keyword in all_content.lower():
                    if theme not in analysis["used_themes"]:
                        analysis["used_themes"].append(theme)
                    break
        
        # Анализ подтем
        for theme, subthemes in self.subthemes.items():
            for subtheme in subthemes:
                subtheme_keywords = self.get_subtheme_keywords(subtheme)
                for keyword in subtheme_keywords:
                    if keyword in all_content.lower():
                        if subtheme not in analysis["used_subthemes"]:
                            analysis["used_subthemes"].append(subtheme)
                        break
        
        # Анализ частых слов
        words = re.findall(r'\b[а-яa-z]{4,}\b', all_content.lower())
        stop_words = {
            'этот', 'это', 'также', 'очень', 'можно', 'будет', 'есть', 
            'который', 'только', 'после', 'когда', 'потому', 'может'
        }
        word_freq = Counter([word for word in words if word not in stop_words])
        analysis["frequent_words"] = [word for word, count in word_freq.most_common(20)]
        
        # Анализ частоты постов по темам (последние 30 постов)
        recent_posts = posts[:30]
        theme_frequency = {}
        for post in recent_posts:
            content = post["content"].lower()
            for theme in self.main_themes:
                theme_keywords = self.get_theme_keywords(theme)
                if any(keyword in content for keyword in theme_keywords):
                    theme_frequency[theme] = theme_frequency.get(theme, 0) + 1
        
        analysis["post_frequency"] = theme_frequency
        
        print(f"📈 Анализ канала:")
        print(f"   Использованные темы: {analysis['used_themes']}")
        print(f"   Частота тем: {theme_frequency}")
        
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

    def get_subtheme_keywords(self, subtheme):
        """Ключевые слова для определения подтемы"""
        words = re.findall(r'\b\w+\b', subtheme.lower())
        return words

    def select_optimal_theme(self, channel_analysis):
        """Выбирает оптимальную тему на основе анализа канала"""
        theme_frequency = channel_analysis.get("post_frequency", {})
        used_themes = channel_analysis.get("used_themes", [])
        
        if not theme_frequency:
            theme = random.choice(self.main_themes)
            subtheme = random.choice(self.subthemes[theme])
            return theme, subtheme
        
        # Находим наименее использованную тему
        available_themes = []
        for theme in self.main_themes:
            frequency = theme_frequency.get(theme, 0)
            if frequency < 2:
                available_themes.append(theme)
        
        if not available_themes:
            least_used_theme = min(theme_frequency.items(), key=lambda x: x[1])[0]
            theme = least_used_theme
        else:
            theme = random.choice(available_themes)
        
        # Выбираем подтему
        available_subthemes = self.subthemes.get(theme, [])
        used_subthemes = channel_analysis.get("used_subthemes", [])
        
        fresh_subthemes = [st for st in available_subthemes if st not in used_subthemes[-5:]]
        
        if fresh_subthemes:
            subtheme = random.choice(fresh_subthemes)
        else:
            subtheme = random.choice(available_subthemes)
        
        print(f"🎯 Выбрана тема: {theme} -> {subtheme}")
        return theme, subtheme

    def search_market_trends(self, theme, subtheme):
        """Ищет актуальные тренды на рынке"""
        print(f"🌐 Ищем тренды для: {subtheme}...")
        
        prompt = f"""
        Найди САМЫЕ АКТУАЛЬНЫЕ тренды, новости и инсайты за последние 2-3 месяца в сфере:
        ОСНОВНАЯ ТЕМА: {theme}
        ПОДТЕМА: {subtheme}

        Проанализируй:
        - Новые исследования и статистику 2024-2025 года
        - Изменения на рынке
        - Технологические инновации
        - Тренды в смежных отраслях

        Верни 3-5 самых интересных и виральных инсайтов с конкретными цифрами и фактами.
        Формат: кратко, по пунктам, только самая суть.
        """

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 1200,
                        "temperature": 0.8,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                trends = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print("✅ Актуальные тренды найдены!")
                return trends
            else:
                return None
                
        except Exception as e:
            print(f"❌ Ошибка поиска трендов: {e}")
            return None

    def get_random_emoji(self, category):
        """Возвращает случайный эмодзи из категории"""
        return random.choice(self.emoji_sections.get(category, ["💡"]))

    def get_unique_format(self, channel_analysis):
        """Выбирает уникальный формат"""
        used_formats = self.history.get("used_formats", [])
        available = [f for f in self.formats if f not in used_formats[-3:]]
        return random.choice(available) if available else random.choice(self.formats)

    def get_unique_image(self):
        """Генерирует уникальную картинку"""
        timestamp = int(time.time() * 1000) + random.randint(1, 1000)
        return f"https://picsum.photos/1200/800?random={timestamp}"

    def is_content_unique(self, content):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return content_hash not in self.history["post_hashes"]

    def generate_emoji_rich_post(self, theme, subtheme, trends, channel_analysis, time_of_day, attempt=1):
        """Генерирует пост с максимальным количеством эмодзи"""
        
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        if self.history.get("last_reset_date") != current_date:
            self.history["used_formats"] = []
            self.history["used_themes"] = []
            self.history["used_subthemes"] = []
            self.history["last_reset_date"] = current_date
            self.save_post_history()
            print("🔄 История очищена (новый день)")

        post_format = self.get_unique_format(channel_analysis)
        avoid_words = channel_analysis.get("frequent_words", [])[:10]
        
        time_config = self.time_settings[time_of_day]
        
        prompt = f"""
        СОЗДАЙ ЯРКИЙ ВИРАЛЬНЫЙ ПОСТ ДЛЯ TELEGRAM С МАКСИМАЛЬНЫМ КОЛИЧЕСТВОМ ЭМОДЗИ! 🚀

        ВРЕМЯ СУТОК: {time_of_day} ({time_config['description']})
        ЦЕЛЕВАЯ ДЛИНА: {time_config['target_length']}

        КОНТЕКСТ:
        🎯 Основная тема: {theme}
        💡 Конкретная подтема: {subtheme}
        📊 Актуальные тренды: {trends if trends else "Используй самые свежие данные 2024-2025"}

        ТРЕБОВАНИЯ К ЭМОДЗИ:
        🔥 МНОГО эмодзи в каждом абзаце
        ✨ Эмодзи в заголовке, фактах, советах, призывах к действию
        🎨 Используй разнообразные эмодзи для визуальной привлекательности
        💎 Эмодзи должны подчеркивать смысл, а не мешать чтению

        СТРУКТУРА С ЭМОДЗИ:
        {self.get_random_emoji('header')} ЦЕПЛЯЮЩИЙ ЗАГОЛОВОК (минимум 2-3 эмодзи)
        {self.get_random_emoji('fact')} ИНТЕРЕСНЫЙ ФАКТ/ИССЛЕДОВАНИЕ (с цифрами + эмодзи)
        {self.get_random_emoji('tip')} ПРАКТИЧЕСКИЙ СОВЕТ/ЛАЙФХАК (с эмодзи)
        {self.get_random_emoji('action')} ПРИЗЫВ К ДЕЙСТВИЮ (эмодзи для мотивации)
        {self.get_random_emoji('discussion')} ВОПРОС ДЛЯ ОБСУЖДЕНИЯ (эмодзи для вовлечения)

        ТЕМАТИЧЕСКИЕ ЭМОДЗИ ДЛЯ {subtheme}:
        {self.get_theme_emojis(theme)}

        ОСОБЕННОСТИ ДЛЯ {time_of_day.upper()}:
        {self.get_time_specific_instructions(time_of_day)}

        ТРЕБОВАНИЯ:
        🚀 ТОЛЬКО свежие данные 2024-2025 года
        💎 Конкретные цифры и исследования
        ✨ Максимум эмодзи в каждом элементе
        🎯 Естественный поток с эмодзи
        📏 Длина: {time_config['target_length']}

        ЦЕЛЬ: Создать яркий, запоминающийся пост, который хочется сохранить и обсудить! 🎉
        """

        try:
            print(f"🧠 Генерируем {time_config['description']}: {subtheme}...")
            
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": time_config['max_tokens'],
                        "temperature": 0.95,
                        "topP": 0.9,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                if self.is_content_unique(post_text):
                    formatted_text = post_format.format(content=post_text)
                    image_url = self.get_unique_image()
                    
                    self.mark_post_used(post_text, theme, subtheme, post_format)
                    
                    print(f"✅ {time_config['description']} создан! ({len(post_text)} символов)")
                    return formatted_text, image_url, f"{theme} - {subtheme}"
                else:
                    print(f"🔄 Пост не уникален, пробуем снова... ({attempt}/2)")
                    if attempt < 2:
                        return self.generate_emoji_rich_post(theme, subtheme, trends, channel_analysis, time_of_day, attempt + 1)
                    else:
                        new_subtheme = random.choice([st for st in self.subthemes[theme] if st != subtheme])
                        return self.generate_emoji_rich_post(theme, new_subtheme, trends, channel_analysis, time_of_day, 1)
            else:
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return self.create_emoji_fallback(theme, subtheme, time_of_day)

    def get_time_specific_instructions(self, time_of_day):
        """Возвращает инструкции в зависимости от времени суток"""
        instructions = {
            "morning": "🌅 УТРЕННИЙ ПОСТ: короткий, энергичный, мотивирующий! Отличное начало дня с быстрыми инсайтами и практическими советами. Идеально для утреннего кофе! ☕️",
            "afternoon": "🌞 ДНЕВНОЙ ПОСТ: развернутый, информативный, с глубоким анализом! Время для серьезных тем, исследований и детальных кейсов. Отлично для обеденного перерыва! 🍽️", 
            "evening": "🌙 ВЕЧЕРНИЙ ПОСТ: средней длины, рефлексивный, вдохновляющий! Подведение итогов дня, размышления и планы на завтра. Идеально для вечернего отдыха! 🌃"
        }
        return instructions.get(time_of_day, "✨ Создай интересный и полезный пост!")

    def get_theme_emojis(self, theme):
        """Возвращает тематические эмодзи для промпта"""
        theme_emojis = {
            "HR и управление персоналом": "👔 💼 🎯 📊 👥 🌟 🎓 💪 🤝 🏢 📈 🔑 🎁 🎪",
            "PR и коммуникации": "📢 🎨 📰 📱 🗣️ 🌍 🛡️ 🌟 ✍️ 🎪 👥 📺 🎬 🔄",
            "ремонт и строительство": "🏗️ 🔨 🎨 🏠 📋 💰 🔑 🤖 💡 🏛️ 🌿 📐 📏 🛠️"
        }
        return theme_emojis.get(theme, "✨ 💎 🚀 🌟")

    def create_emoji_fallback(self, theme, subtheme, time_of_day):
        """Создает пост с эмодзи при ошибке"""
        time_config = self.time_settings[time_of_day]
        
        # Разные шаблоны в зависимости от времени суток
        morning_templates = [
            f"""🌅🚀 {subtheme.upper()}: УТРЕННИЙ ИНСАЙТ 💡☕️

📊 Статистика: 73% успешных проектов начинаются с правильного {subtheme.split(' ')[0]}! 📈✨

💡 Утренний совет: Начните день с анализа {subtheme.split(' ')[0]}! 🎯🌟

🚀 Действие: Примените один лайфхак по {subtheme.split(' ')[0]} сегодня! 💪✅

💬 Что планируете в {subtheme.split(' ')[0]}? 👥🗣️""",

            f"""☀️🎯 {subtheme.upper()}: ЗАРЯДКА ДЛЯ МОЗГА 🧠💫

📈 Факт: Эффективный {subtheme.split(' ')[0]} повышает продуктивность на 45%! 📊🚀

💎 Утренний лайфхак: Используйте технику Pomodoro для {subtheme.split(' ')[0]}! ⏰🍅

🌟 Задача: Оптимизируйте один процесс {subtheme.split(' ')[0]} до обеда! 🔄✅

🤔 Ваши утренние ритуалы в {subtheme.split(' ')[0]}? 👥💭"""
        ]
        
        afternoon_templates = [
            f"""🌞📊 {subtheme.upper()}: ГЛУБОКИЙ АНАЛИЗ 2025 🎯🔍

📈 Исследование Harvard: компании с продуманной стратегией {subtheme.split(' ')[0]} показывают рост на 67%! 💎📊

💡 Детальный разбор: Ключевые элементы успешного {subtheme.split(' ')[0]} в 2025 году:
• AI-интеграция 🤖✨  
• Персонализация подходов 🎯👤
• Data-driven решения 📊🔢
• Agile методологии 🔄🏃‍♂️

🚀 Пошаговый план: Внедрение современных технологий в {subtheme.split(' ')[0]}:
1. Аудит текущих процессов 📋🔍
2. Выбор подходящих инструментов 🛠️💡
3. Обучение команды 🎓👥
4. Тестирование и оптимизация 🧪📈

💬 Обсудим кейсы? Какие подходы к {subtheme.split(' ')[0]} работают у вас? 👥🗣️""",

            f"""🏢🎨 {subtheme.upper()}: ПОЛНОЕ РУКОВОДСТВО 💼📚

📊 Анализ рынка: специалисты в {subtheme.split(' ')[0]} получают на 35% больше предложений! 💰🌟

💡 Глубокое погружение: Тренды {subtheme.split(' ')[0]} в 2025 году:
🎯 Digital трансформация процессов
🚀 Автоматизация рутинных задач  
💎 Фокус на soft skills
📱 Mobile-first подходы
🌍 Глобализация best practices

🔧 Практические инструменты для {subtheme.split(' ')[0]}:
• CRM системы 📊
• AI-ассистенты 🤖
• Analytics платформы 📈
• Collaboration tools 👥

🌟 Рекомендация: Разработайте дорожную карту {subtheme.split(' ')[0]} на 2025 год! 🗺️✅

💬 Поделитесь опытом! Какие инструменты используете в {subtheme.split(' ')[0]}? 👥💭"""
        ]
        
        evening_templates = [
            f"""🌙💫 {subtheme.upper()}: ВЕЧЕРНИЕ РАЗМЫШЛЕНИЯ 🎯🤔

📊 Итоги дня: 68% professionals отмечают важность {subtheme.split(' ')[0]} для карьеры! 📈✨

💡 Вечерний инсайт: Рефлексия - ключ к улучшению {subtheme.split(' ')[0]}! 🧠🌟

🚀 Завтрашний план: Внедрите один новый метод в {subtheme.split(' ')[0]}! 📅✅

💬 Как прошел ваш день в {subtheme.split(' ')[0]}? 👥🗣️""",

            f"""🌟🌃 {subtheme.upper()}: ИТОГИ И ПЕРСПЕКТИВЫ 📊🚀

📈 Статистика: ежедневное улучшение {subtheme.split(' ')[0]} дает +25% к годовым результатам! 💎✨

💡 Вечерняя практика: Проанализируйте сегодняшние успехи в {subtheme.split(' ')[0]}! 📝🔍

🎯 План на завтра: Сфокусируйтесь на одном аспекте {subtheme.split(' ')[0]}! 🎯✅

🤔 Какие инсайты получили сегодня в {subtheme.split(' ')[0]}? 👥💭"""
        ]
        
        templates = {
            "morning": morning_templates,
            "afternoon": afternoon_templates, 
            "evening": evening_templates
        }
        
        post_text = random.choice(templates.get(time_of_day, afternoon_templates))
        post_format = self.get_unique_format({"used_formats": []})
        image_url = self.get_unique_image()
        
        self.mark_post_used(post_text, theme, subtheme, post_format)
        
        return post_text, image_url, f"{theme} - {subtheme}"

    def mark_post_used(self, content, theme, subtheme, post_format):
        """Сохраняет пост в историю"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        self.history["post_hashes"].append(content_hash)
        self.history["used_themes"].append(theme)
        self.history["used_subthemes"].append(subtheme)
        self.history["used_formats"].append(post_format)
        
        for key in ["post_hashes", "used_themes", "used_subthemes", "used_formats"]:
            if len(self.history[key]) > 200:
                self.history[key] = self.history[key][-200:]
        
        self.save_post_history()

    def send_to_telegram(self, message, image_url=None):
        """Отправляет пост в Telegram"""
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
        """Основная функция"""
        try:
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            time_config = self.time_settings[time_of_day]
            
            print(f"\n{'='*60}")
            print(f"🚀 ЭМОДЗИ-ГЕНЕРАТОР ПОСТОВ")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"⏰ Время: {time_of_day} ({time_config['description']})")
            print(f"📏 Целевая длина: {time_config['target_length']}")
            print(f"{'='*60}")
            
            # Анализ канала
            posts = self.get_channel_posts()
            channel_analysis = self.analyze_channel_content(posts)
            
            # Выбор темы
            theme, subtheme = self.select_optimal_theme(channel_analysis)
            
            # Поиск трендов
            trends = self.search_market_trends(theme, subtheme)
            
            # Генерация поста
            post_text, image_url, final_topic = self.generate_emoji_rich_post(
                theme, subtheme, trends, channel_analysis, time_of_day
            )
            
            print(f"📊 Результат:")
            print(f"   Тема: {final_topic}")
            print(f"   Длина: {len(post_text)} символов")
            print(f"   Эмодзи: {post_text.count('️')} шт.")
            print(f"   Время: {time_of_day}")
            
            # Отправка
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                print(f"✅ Готово! {time_config['description']} создан и отправлен.")
            else:
                print("❌ Ошибка при отправке")
            
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    generator = EmojiPostGenerator()
    generator.run()

if __name__ == "__main__":
    main()
