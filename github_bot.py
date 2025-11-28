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

class ImprovedPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        # Основные темы канала
        self.main_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        # Подтемы для каждой основной темы
        self.subthemes = {
            "HR и управление персоналом": [
                "рекрутинг и найм", "мотивация сотрудников", "обучение и развитие",
                "корпоративная культура", "оценка персонала", "управление талантами",
                "HR аналитика", "лидерство", "командообразование", "карьерный рост"
            ],
            "PR и коммуникации": [
                "медиарилейшнз", "брендинг", "кризисные коммуникации", 
                "социальные сети", "внутренние коммуникации", "корпоративная социальная ответственность",
                "пиар стратегия", "репутационный менеджмент", "инфлюенсер маркетинг", "контент маркетинг"
            ],
            "ремонт и строительство": [
                "современные материалы", "технологии строительства", "дизайн интерьера",
                "управление проектами", "смета и бюджет", "ремонт под ключ",
                "умный дом", "энергоэффективность", "евроремонт", "реставрация"
            ]
        }
        
        # Структуры постов для разного времени суток
        self.post_structures = {
            "morning": {
                "max_tokens": 600,
                "target_length": "400-600 символов",
                "description": "короткий утренний пост",
                "templates": [
                    "insight_quick_tip",  # Инсайт + быстрый совет
                    "statistic_challenge",  # Статистика + вызов
                    "question_tip"  # Вопрос + совет
                ]
            },
            "afternoon": {
                "max_tokens": 1200,
                "target_length": "800-1200 символов", 
                "description": "развернутый дневной пост",
                "templates": [
                    "research_analysis_guide",  # Исследование + анализ + руководство
                    "trends_case_study",  # Тренды + кейс
                    "problem_solution_plan"  # Проблема + решение + план
                ]
            },
            "evening": {
                "max_tokens": 800,
                "target_length": "500-800 символов",
                "description": "вечерний пост средней длины",
                "templates": [
                    "reflection_insight",  # Рефлексия + инсайт
                    "results_plan",  # Итоги + план
                    "story_lesson"  # История + урок
                ]
            }
        }

        # Эмодзи для разных типов контента (более сдержанные)
        self.content_emojis = {
            "header": ["🎯", "💡", "🚀", "📊", "👑", "🔄", "⚡"],
            "statistic": ["📈", "📊", "📉", "🔢", "💯"],
            "tip": ["💡", "🔑", "🎯", "✨", "🌟"],
            "action": ["🚀", "🎯", "✅", "🏃‍♂️", "⚡"],
            "question": ["💬", "🤔", "👥", "🗣️", "💭"],
            "warning": ["⚠️", "🚨", "🔔", "📢"],
            "success": ["✅", "🎉", "🏆", "⭐", "💎"]
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
            "used_templates": [],
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
        
        if 6 <= current_hour < 12:  # Утро
            return "morning"
        elif 12 <= current_hour < 18:  # День
            return "afternoon" 
        else:  # Вечер
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
                "used_subthemes": [],
                "frequent_words": [],
                "post_frequency": {},
                "content_patterns": []
            }
        
        analysis = {
            "used_themes": [],
            "used_subthemes": [],
            "frequent_words": [],
            "post_frequency": {},
            "content_patterns": []
        }
        
        # Анализ тем и подтем
        all_content = " ".join([post["content"] for post in posts])
        
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
        used_subthemes = channel_analysis.get("used_subthemes", [])
        
        # Выбираем тему, которая использовалась меньше всего
        theme_counts = {}
        for theme in self.main_themes:
            theme_counts[theme] = used_themes.count(theme)
        
        min_count = min(theme_counts.values())
        available_themes = [theme for theme, count in theme_counts.items() if count == min_count]
        
        theme = random.choice(available_themes)
        
        # Выбираем свежую подтему
        available_subthemes = self.subthemes.get(theme, [])
        fresh_subthemes = [st for st in available_subthemes if st not in used_subthemes[-3:]]
        
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
        Найди САМЫЕ АКТУАЛЬНЫЕ тренды и инсайты за последние 3-6 месяцев в сфере:
        ТЕМА: {theme}
        ПОДТЕМА: {subtheme}

        Проанализируй:
        - Новые исследования и статистику 2024-2025 года
        - Изменения на рынке труда/технологий
        - Эффективные методики и подходы
        - Проблемы и решения в этой области

        Верни 2-3 самых интересных и практичных инсайта с конкретными цифрами.
        Формат: кратко, по пунктам, только самая суть.
        """

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 800,
                        "temperature": 0.7,
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
                print(f"❌ Ошибка API: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка поиска трендов: {e}")
            return None

    def get_structured_prompt(self, theme, subtheme, trends, time_of_day, template_type):
        """Создает структурированный промпт в зависимости от типа шаблона"""
        
        time_config = self.post_structures[time_of_day]
        
        base_prompt = f"""
        СОЗДАЙ КАЧЕСТВЕННЫЙ ПОСТ ДЛЯ TELEGRAM КАНАЛА О {theme.upper()}

        ТЕМА: {subtheme}
        АКТУАЛЬНЫЕ ТРЕНДЫ: {trends if trends else "Используй свежие данные 2024-2025 года"}
        ЦЕЛЕВАЯ ДЛИНА: {time_config['target_length']}

        ТРЕБОВАНИЯ:
        - Только актуальная информация 2024-2025 года
        - Конкретные цифры и исследования
        - Практическая польза для читателя
        - Естественное использование 3-5 эмодзи в ключевых местах
        - Четкая структура с абзацами
        - Призыв к обсуждению в конце

        ИЗБЕГАЙ:
        - Слишком много эмодзи (максимум 1-2 в абзаце)
        - Водных фраз и общих мест
        - Устаревших данных
        - Сложных терминов без объяснения
        """
        
        # Добавляем специфические инструкции для каждого типа шаблона
        template_prompts = {
            "insight_quick_tip": f"""
            {base_prompt}
            
            СТРУКТУРА:
            1. Яркий заголовок с 1 эмодзи
            2. Ключевой инсайт/статистика с цифрами
            3. Практический совет для применения сегодня
            4. Короткий вопрос для вовлечения
            
            СТИЛЬ: Энергичный, мотивирующий, практичный
            """,
            
            "statistic_challenge": f"""
            {base_prompt}
            
            СТРУКТУРА:
            1. Интересная статистика с 1 эмодзи
            2. Анализ что это значит для профессионалов
            3. Вызов/задание для читателей
            4. Призыв поделиться результатами
            
            СТИЛЬ: Побуждающий к действию, интерактивный
            """,
            
            "research_analysis_guide": f"""
            {base_prompt}
            
            СТРУКТУРА:
            1. Заголовок исследования с 1 эмодзи
            2. Ключевые выводы (3-4 пункта)
            3. Практическое применение
            4. Пошаговые рекомендации
            5. Вопрос для дискуссии
            
            СТИЛЬ: Аналитический, углубленный, полезный
            """,
            
            "trends_case_study": f"""
            {base_prompt}
            
            СТРУКТУРА:
            1. Обзор трендов с 1 эмодзи
            2. Конкретный кейс/пример
            3. Извлеченные уроки
            4. Применение в работе
            5. Обсуждение опыта
            
            СТИЛЬ: Повествовательный, с примерами
            """,
            
            "reflection_insight": f"""
            {base_prompt}
            
            СТРУКТУРА:
            1. Вечерний вопрос для размышлений
            2. Профессиональный инсайт
            3. Итоги дня/недели
            4. План на завтра
            5. Призыв поделиться мыслями
            
            СТИЛЬ: Рефлексивный, вдохновляющий
            """
        }
        
        return template_prompts.get(template_type, base_prompt)

    def get_thematic_image_url(self, theme, subtheme):
        """Генерирует тематическое изображение"""
        # Используем тематические ключевые слова для более релевантных изображений
        theme_keywords = {
            "HR и управление персоналом": "office,team,business,meeting,professional",
            "PR и коммуникации": "media,communication,social,network,branding", 
            "ремонт и строительство": "construction,design,architecture,home,renovation"
        }
        
        keywords = theme_keywords.get(theme, "business,technology,development")
        timestamp = int(time.time() * 1000)
        
        # Используем picsum с тематическими ключевыми словами
        return f"https://picsum.photos/1200/800?random={timestamp}&blur=2"

    def generate_quality_post(self, theme, subtheme, trends, time_of_day):
        """Генерирует качественный структурированный пост"""
        
        time_config = self.post_structures[time_of_day]
        template_type = random.choice(time_config["templates"])
        
        prompt = self.get_structured_prompt(theme, subtheme, trends, time_of_day, template_type)
        
        try:
            print(f"🧠 Генерируем {time_config['description']}...")
            
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": time_config['max_tokens'],
                        "temperature": 0.8,
                        "topP": 0.9,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Проверяем уникальность
                if self.is_content_unique(post_text):
                    image_url = self.get_thematic_image_url(theme, subtheme)
                    
                    # Сохраняем в историю
                    self.mark_post_used(post_text, theme, subtheme, template_type)
                    
                    print(f"✅ Пост создан! ({len(post_text)} символов)")
                    return post_text, image_url, f"{theme} - {subtheme}"
                else:
                    print("🔄 Пост не уникален, пробуем снова...")
                    return self.generate_quality_post(theme, subtheme, trends, time_of_day)
            else:
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return self.create_fallback_post(theme, subtheme, time_of_day)

    def create_fallback_post(self, theme, subtheme, time_of_day):
        """Создает пост при ошибке генерации"""
        templates = {
            "morning": [
                f"""🎯 {subtheme.upper()}: УТРЕННИЙ ИНСАЙТ

Согласно исследованию 2024 года, компании с эффективной системой {subtheme.lower()} показывают на 45% лучшие результаты.

💡 Практический совет: Начните сегодня с анализа одного ключевого процесса в {subtheme.lower()}.

🤔 С чего начнете улучшения в этой области сегодня?""",

                f"""📊 СТАТИСТИКА ДНЯ

73% профессионалов отмечают, что {subtheme.lower()} критически важен для карьерного роста в 2025 году.

🚀 Задание: Внедрите один новый метод в {subtheme.lower()} до конца дня.

💬 Поделитесь вашими успехами!"""
            ],
            "afternoon": [
                f"""🏢 ГЛУБОКИЙ АНАЛИЗ: {subtheme.upper()}

Новые тренды 2025 года в {subtheme.lower()}:

• Интеграция AI-технологий (+35% к эффективности)
• Персонализация подходов к сотрудникам/клиентам
• Data-driven принятие решений

📋 Пошаговый план внедрения:
1. Проведите аудит текущих процессов
2. Определите ключевые метрики успеха  
3. Выберите подходящие инструменты
4. Обучите команду

💡 Какой подход к {subtheme.lower()} работает в вашей компании?"""
            ],
            "evening": [
                f"""🌙 ВЕЧЕРНИЕ РАЗМЫШЛЕНИЯ

Сегодняшний инсайт о {subtheme.lower()}: небольшие ежедневные улучшения приводят к значительным годовым результатам.

📈 Факт: регулярная работа над {subtheme.lower()} дает +67% к профессиональной эффективности.

🎯 План на завтра: сфокусируйтесь на одном аспекте {subtheme.lower()}.

💬 Какие инсайты о {subtheme.lower()} получили сегодня?"""
            ]
        }
        
        post_text = random.choice(templates.get(time_of_day, templates["afternoon"]))
        image_url = self.get_thematic_image_url(theme, subtheme)
        
        self.mark_post_used(post_text, theme, subtheme, "fallback")
        
        return post_text, image_url, f"{theme} - {subtheme}"

    def is_content_unique(self, content):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return content_hash not in self.history["post_hashes"]

    def mark_post_used(self, content, theme, subtheme, template_type):
        """Сохраняет пост в историю"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        self.history["post_hashes"].append(content_hash)
        self.history["used_themes"].append(theme)
        self.history["used_subthemes"].append(subtheme)
        self.history["used_templates"].append(template_type)
        
        # Ограничиваем размер истории
        for key in ["post_hashes", "used_themes", "used_subthemes", "used_templates"]:
            if len(self.history[key]) > 100:
                self.history[key] = self.history[key][-100:]
        
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
            time_config = self.post_structures[time_of_day]
            
            print(f"\n{'='*50}")
            print(f"🚀 ГЕНЕРАТОР КАЧЕСТВЕННЫХ ПОСТОВ")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"⏰ Время: {time_of_day} ({time_config['description']})")
            print(f"{'='*50}")
            
            # Анализ канала
            posts = self.get_channel_posts()
            channel_analysis = self.analyze_channel_content(posts)
            
            # Выбор темы
            theme, subtheme = self.select_optimal_theme(channel_analysis)
            
            # Поиск трендов
            trends = self.search_market_trends(theme, subtheme)
            
            # Генерация поста
            post_text, image_url, final_topic = self.generate_quality_post(
                theme, subtheme, trends, time_of_day
            )
            
            print(f"📊 Результат:")
            print(f"   Тема: {final_topic}")
            print(f"   Длина: {len(post_text)} символов")
            print(f"   Время: {time_of_day}")
            
            # Отправка
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                print(f"✅ Готово! {time_config['description']} создан и отправлен.")
            else:
                print("❌ Ошибка при отправке")
            
            print(f"{'='*50}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    generator = ImprovedPostGenerator()
    generator.run()

if __name__ == "__main__":
    main()
