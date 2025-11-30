import os
import requests
import random
import json
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Внешние сервисы для изображений (можно настроить в .env)
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI-ГЕНЕРАЦИЯ С УМНОЙ СИСТЕМОЙ ИЗОБРАЖЕНИЙ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Ключевые слова для поиска изображений по темам
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting", "business workplace", "corporate culture", 
                "team collaboration", "professional development", "workplace diversity",
                "leadership meeting", "career growth", "employee engagement",
                "modern office", "business team", "workplace innovation"
            ],
            "PR и коммуникации": [
                "public relations", "media communication", "social media marketing",
                "brand strategy", "digital marketing", "communication technology",
                "networking event", "press conference", "media relations",
                "marketing team", "digital communication", "brand management"
            ],
            "ремонт и строительство": [
                "construction site", "building renovation", "home improvement",
                "interior design", "architecture", "construction workers",
                "renovation project", "building materials", "modern construction",
                "home renovation", "construction technology", "building design"
            ]
        }
        
        # Резервные источники изображений
        self.image_sources = [
            self.search_unsplash_image,
            self.search_pexels_image,
            self.get_fallback_image
        ]

    def load_post_history(self):
        """Загружает историю постов с расширенной информацией об изображениях"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Инициализируем структуры если их нет
                    if "used_images" not in data:
                        data["used_images"] = {}
                    if "image_search_history" not in data:
                        data["image_search_history"] = {}
                    if "full_posts" not in data:
                        data["full_posts"] = {}
                    return data
            return {
                "posts": {}, 
                "themes": {}, 
                "full_posts": {}, 
                "used_images": {},
                "image_search_history": {}
            }
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {
                "posts": {}, 
                "themes": {}, 
                "full_posts": {}, 
                "used_images": {},
                "image_search_history": {}
            }
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def search_unsplash_image(self, theme):
        """Поиск изображения через Unsplash API"""
        if not UNSPLASH_ACCESS_KEY:
            return None
            
        try:
            keywords = self.theme_keywords.get(theme, ["business", "professional"])
            keyword = random.choice(keywords)
            
            print(f"🔍 Поиск в Unsplash: {keyword}")
            
            url = f"https://api.unsplash.com/photos/random"
            params = {
                'query': keyword,
                'orientation': 'landscape',
                'client_id': UNSPLASH_ACCESS_KEY
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                image_url = data['urls']['regular']
                print(f"✅ Найдено изображение в Unsplash")
                return image_url
                
        except Exception as e:
            print(f"❌ Ошибка Unsplash: {e}")
            
        return None

    def search_pexels_image(self, theme):
        """Поиск изображения через Pexels API"""
        if not PEXELS_API_KEY:
            return None
            
        try:
            keywords = self.theme_keywords.get(theme, ["business", "professional"])
            keyword = random.choice(keywords)
            
            print(f"🔍 Поиск в Pexels: {keyword}")
            
            url = f"https://api.pexels.com/v1/search"
            headers = {
                'Authorization': PEXELS_API_KEY
            }
            params = {
                'query': keyword,
                'orientation': 'landscape',
                'per_page': 10
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data['photos']:
                    photo = random.choice(data['photos'])
                    image_url = photo['src']['large']
                    print(f"✅ Найдено изображение в Pexels")
                    return image_url
                
        except Exception as e:
            print(f"❌ Ошибка Pexels: {e}")
            
        return None

    def get_fallback_image(self, theme):
        """Резервный источник изображений через сервисы без API"""
        try:
            # Используем сервисы которые не требуют API ключей
            services = [
                self.get_lorem_picsum_image,
                self.get_placeholder_image
            ]
            
            for service in services:
                image_url = service(theme)
                if image_url:
                    return image_url
                    
        except Exception as e:
            print(f"❌ Ошибка fallback: {e}")
            
        return None

    def get_lorem_picsum_image(self, theme):
        """Получаем изображение с Lorem Picsum"""
        try:
            # Lorem Picsum предоставляет случайные изображения
            image_id = random.randint(1, 1000)
            image_url = f"https://picsum.photos/1200/630?random={image_id}"
            
            # Проверяем что изображение доступно
            response = requests.head(image_url, timeout=10)
            if response.status_code == 200:
                print(f"✅ Используем Lorem Picsum изображение")
                return image_url
                
        except Exception as e:
            print(f"❌ Ошибка Lorem Picsum: {e}")
            
        return None

    def get_placeholder_image(self, theme):
        """Создаем тематическое изображение через сервисы-заглушки"""
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Используем сервисы которые генерируют изображения по тексту
            services = [
                f"https://placehold.co/1200x630/4A90E2/FFFFFF?text={keyword.replace(' ', '+')}",
                f"https://dummyimage.com/1200x630/4A90E2/FFFFFF&text={keyword.replace(' ', '+')}"
            ]
            
            image_url = random.choice(services)
            print(f"✅ Используем placeholder: {keyword}")
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка placeholder: {e}")
            
        return None

    def get_unique_image(self, theme):
        """Находит уникальное изображение для темы"""
        print(f"🖼️ Поиск уникального изображения для: {theme}")
        
        # Получаем историю использованных изображений для темы
        theme_key = theme
        if "used_images" not in self.post_history:
            self.post_history["used_images"] = {}
        if theme_key not in self.post_history["used_images"]:
            self.post_history["used_images"][theme_key] = []
        
        used_images = self.post_history["used_images"][theme_key]
        
        # Ищем уникальное изображение через все источники
        attempts = 0
        max_attempts = len(self.image_sources) * 2
        
        while attempts < max_attempts:
            # Выбираем случайный источник
            image_source = random.choice(self.image_sources)
            image_url = image_source(theme)
            
            if image_url and image_url not in used_images:
                # Сохраняем в историю
                used_images.append(image_url)
                if len(used_images) > 20:  # Ограничиваем историю
                    used_images.pop(0)
                
                self.save_post_history()
                print(f"✅ Уникальное изображение найдено: {image_url[:80]}...")
                return image_url
            
            attempts += 1
        
        # Если не нашли уникальное, берем наименее использованное
        if used_images:
            least_used = used_images[0]  # Самое старое в истории
            print(f"🔄 Используем наименее использованное изображение")
            return least_used
        
        # Последняя попытка - любое доступное изображение
        for source in self.image_sources:
            image_url = source(theme)
            if image_url:
                print(f"⚠️ Используем любое доступное изображение")
                return image_url
        
        print("❌ Не удалось найти изображение")
        return None

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом полной истории"""
        last_themes = self.get_last_themes(channel_id, 3)
        
        available_themes = self.themes.copy()
        
        # Исключаем последние 2 темы
        for theme in last_themes[-2:]:
            if theme in available_themes:
                available_themes.remove(theme)
                print(f"🎯 Исключили недавнюю тему: {theme}")
        
        if not available_themes:
            available_themes = self.themes.copy()
            print("🔄 Все темы использовались, делаем ротацию")
        
        theme = random.choice(available_themes)
        print(f"🎯 Выбрана тема: {theme} (история: {last_themes})")
        return theme

    def get_last_themes(self, channel_id, count=5):
        channel_key = str(channel_id)
        themes = self.post_history.get("themes", {}).get(channel_key, [])
        return themes[-count:] if len(themes) >= count else themes

    def generate_with_context(self, theme, channel_id, post_type="telegram"):
        """Генерирует пост с учетом контекста истории канала"""
        
        history_analysis = self.analyze_channel_history(channel_id, theme)
        print(f"📊 Анализ истории: {history_analysis[:100]}...")
        
        if post_type == "telegram":
            prompt = self.create_telegram_prompt(theme, history_analysis)
        else:
            prompt = self.create_zen_prompt(theme, history_analysis)
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            if self.is_content_unique(generated_text, channel_id):
                return generated_text
            else:
                print("⚠️ Сгенерированный контент похож на существующий, пробуем снова...")
                return self.generate_with_context(theme, channel_id, post_type)
        else:
            return self.generate_fallback_post(theme, post_type)

    def create_telegram_prompt(self, theme, history_analysis):
        return f"""
        Напиши УНИКАЛЬНЫЙ пост для Telegram на тему "{theme}" за 2024-2025 год.

        ВАЖНО: Этот пост должен кардинально отличаться от предыдущих публикаций в канале.

        Анализ истории канала:
        {history_analysis}

        Требования к посту:
        - АБСОЛЮТНАЯ УНИКАЛЬНОСТЬ: не повторяй идеи, фразы и структуры из истории
        - Новый угол зрения на тему {theme}
        - Пиши как настоящий человек, без клише
        - Используй символ • для разделения пунктов
        - Структура:
          1. Цепляющий заголовок (новый подход)
          2. 2-3 СВЕЖИХ факта или тренда (не из истории)
          3. Раздел "Что работает сейчас:" с 3 НОВЫМИ советами
          4. Уникальный вопрос для вовлечения
        - Длина: 400-600 символов
        - Избегай любых повторений из анализа истории выше

        Создай полностью оригинальный контент!
        """

    def create_zen_prompt(self, theme, history_analysis):
        return f"""
        Напиши УНИКАЛЬНЫЙ аналитический пост для Яндекс.Дзен на тему "{theme}" за 2024-2025 год.

        ВАЖНО: Этот пост должен кардинально отличаться от предыдущих публикаций в канале.

        Анализ истории канала:
        {history_analysis}

        Требования:
        - АБСОЛЮТНАЯ УНИКАЛЬНОСТЬ: не повторяй идеи, фразы и структуры из истории
        - Профессиональная аналитика с новыми данными
        - Без корпоративного жаргона
        - Конкретные примеры и цифры (новые)
        - Без эмодзи и хештегов
        - Используй символ • для визуального разделения
        - Структура:
          1. Заголовок (новый подход)
          2. Введение с АКТУАЛЬНЫМИ данными (не из истории)
          3. Раздел "Ключевые направления:" с 3 НОВЫМИ пунктами
        - Длина: 600-900 символов

        Создай полностью оригинальный контент!
        """

    def analyze_channel_history(self, channel_id, theme):
        """Анализирует историю постов в канале"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history or channel_key not in self.post_history["full_posts"]:
            return "Нет истории постов для анализа"
        
        recent_posts = self.post_history["full_posts"][channel_key][-10:]
        
        if not recent_posts:
            return "Нет истории постов для анализа"
        
        analysis_prompt = f"""
        Проанализируй историю постов в канале и выдели основные темы, фразы и идеи, которые УЖЕ использовались.
        
        Тема для нового поста: {theme}
        
        История последних постов:
        {chr(10).join([f'{i+1}. {post[:200]}...' for i, post in enumerate(recent_posts)])}
        
        Задача: определить какие аспекты темы '{theme}' уже освещались и какие новые углы можно рассмотреть.
        Верни только список уже использованных идей и рекомендации что нового осветить.
        """
        
        try:
            analysis_result = self.generate_with_gemini(analysis_prompt)
            return analysis_result if analysis_result else "Не удалось проанализировать историю"
        except:
            return "Ошибка анализа истории"

    def is_content_unique(self, new_content, channel_id, similarity_threshold=0.8):
        """Проверяет уникальность контента"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history or channel_key not in self.post_history["full_posts"]:
            return True
        
        recent_posts = self.post_history["full_posts"][channel_key][-10:]
        
        if not recent_posts:
            return True
        
        new_content_lower = new_content.lower()
        
        for old_post in recent_posts:
            old_post_lower = old_post.lower()
            common_words = set(new_content_lower.split()) & set(old_post_lower.split())
            similarity = len(common_words) / max(len(set(new_content_lower.split())), 1)
            
            if similarity > similarity_threshold:
                print(f"⚠️ Обнаружена схожесть: {similarity:.2f}")
                return False
        
        return True

    def generate_with_gemini(self, prompt):
        try:
            print("🧠 Запрос к Gemini API...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            response = requests.post(
                url,
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 1000,
                        "temperature": 0.9,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                generated_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print("✅ Текст сгенерирован")
                return generated_text
            else:
                print(f"❌ Ошибка Gemini: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return None

    def generate_tg_post(self, theme):
        """Генерирует пост для Telegram с учетом контекста"""
        return self.generate_with_context(theme, MAIN_CHANNEL_ID, "telegram")

    def generate_zen_post(self, theme):
        """Генерирует пост для Дзена с учетом контекста"""
        return self.generate_with_context(theme, ZEN_CHANNEL_ID, "zen")

    def format_tg_post(self, text):
        """Форматирует пост для Telegram с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                if line.startswith('•'):
                    line = f"    {line}"
                elif any(keyword in line.lower() for keyword in ['что работает', 'советы:', 'рекомендации:']):
                    if formatted_lines:
                        formatted_lines.append('')
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def format_zen_post(self, text):
        """Форматирует пост для Дзена с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                if line.startswith('•'):
                    line = f"    {line}"
                elif any(keyword in line.lower() for keyword in ['ключевые направления', 'основные тренды', 'рекомендации:']):
                    if formatted_lines:
                        formatted_lines.append('')
                
                if not line.endswith(('.', '!', '?')) and len(line.split()) > 3:
                    line = line + '.'
                    
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_fallback_post(self, theme, post_type):
        """Резервные посты с вариациями"""
        fallbacks_tg = {
            "HR и управление персоналом": [
                """Современный HR: тренды 2025 года

    • 81% компаний внедряют AI в процессы найма
    • Геймификация тестов увеличивает вовлеченность на 45%

Что актуально сейчас:

    • Внедряйте системы менторства для новых сотрудников
    • Используйте данные аналитики для персонализации развития
    • Создавайте программы wellness для профилактики выгорания

Как адаптируете HR-процессы под новые реалии?

#HR #тренды2025 #управление""",
            ],
            "PR и коммуникации": [
                """PR в эпоху цифровой трансформации

    • Виртуальные ивенты собирают на 60% больше аудитории
    • Подкасты становятся ключевым каналом B2B-коммуникаций

Современные подходы:

    • Разрабатывайте интерактивный контент вместо статических пресс-релизов
    • Используйте data-driven сторителлинг в коммуникациях
    • Создавайте экосистемы партнерского контента

Какие инструменты digital-PR используете?

#PR #digital #коммуникации""",
            ],
            "ремонт и строительство": [
                """Инновации в строительстве 2025

    • 3D-печать сокращает сроки строительства на 70%
    • Умные материалы экономят до 40% энергии

Современные решения:

    • Внедряйте BIM-моделирование для точного планирования
    • Используйте дроны для мониторинга объектов
    • Применяйте экологичные материалы нового поколения

Какие технологии используете в проектах?

#ремонт #стройка #инновации""",
            ]
        }
        
        fallbacks_zen = {
            "HR и управление персоналом": [
                """Эволюция управления персоналом в 2025 году

Современные исследования показывают, что 81% организаций активно внедряют искусственный интеллект в процессы подбора персонала. Геймификация оценочных тестов демонстрирует рост вовлеченности кандидатов на 45%.

Ключевые направления развития:

    • Системы наставничества и менторства. Интеграция программ адаптации для новых сотрудников ускоряет их вхождение в должность.

    • Персонализация развития. Использование аналитики данных позволяет создавать индивидуальные траектории профессионального роста.

    • Профилактика эмоционального выгорания. Внедрение wellness-программ способствует сохранению психического здоровья сотрудников.""",
            ],
            "PR и коммуникации": [
                """Трансформация PR-стратегий в цифровую эпоху

Виртуальные мероприятия демонстрируют рост аудитории на 60%, а подкасты становятся ключевым каналом для B2B-коммуникаций. Современный PR требует интеграции цифровых технологий и аналитики данных.

Ключевые направления:

    • Интерактивный контент. Разработка динамических материалов заменяет традиционные пресс-релизы.

    • Data-driven коммуникации. Использование аналитики для создания персонализированных сообщений.

    • Партнерские экосистемы. Формирование сетей взаимовыгодного сотрудничества усиливает охват аудитории.""",
            ]
        }
        
        if post_type == "telegram":
            fallback = random.choice(fallbacks_tg.get(theme, ["Актуальные тренды 2024-2025. #тренды"]))
            hashtags = self.add_tg_hashtags(theme)
            return f"{fallback}\n\n{hashtags}"
        else:
            return random.choice(fallbacks_zen.get(theme, ["Актуальные тенденции 2024-2025 года."]))

    def add_tg_hashtags(self, theme):
        hashtags = {
            "HR и управление персоналом": "#HR #управление #команда",
            "PR и коммуникации": "#PR #коммуникации #маркетинг", 
            "ремонт и строительство": "#ремонт #стройка #дизайн"
        }
        return hashtags.get(theme, "")

    def add_theme_to_history(self, channel_id, theme):
        channel_key = str(channel_id)
        
        if "themes" not in self.post_history:
            self.post_history["themes"] = {}
        if channel_key not in self.post_history["themes"]:
            self.post_history["themes"][channel_key] = []
        
        self.post_history["themes"][channel_key].append(theme)
        if len(self.post_history["themes"][channel_key]) > 15:
            self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-10:]
        
        self.save_post_history()

    def add_full_post_to_history(self, channel_id, post_text):
        """Сохраняет полный текст поста в историю"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history:
            self.post_history["full_posts"] = {}
        if channel_key not in self.post_history["full_posts"]:
            self.post_history["full_posts"][channel_key] = []
        
        self.post_history["full_posts"][channel_key].append(post_text)
        if len(self.post_history["full_posts"][channel_key]) > 20:
            self.post_history["full_posts"][channel_key] = self.post_history["full_posts"][channel_key][-15:]
        
        self.save_post_history()

    def send_to_telegram(self, chat_id, text, image_url=None):
        print(f"📤 Отправка в {chat_id}...")
        
        # ГАРАНТИРОВАННОЕ получение изображения
        if not image_url:
            image_url = self.get_unique_image(self.current_theme)
            
        if not image_url:
            print("❌ Не удалось получить изображение, отправляем текстовый пост")
            return self.send_text_to_telegram(chat_id, text)
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                self.add_to_history(text, chat_id)
                self.add_full_post_to_history(chat_id, text)
                if self.current_theme:
                    self.add_theme_to_history(chat_id, self.current_theme)
                print(f"✅ Пост с УНИКАЛЬНЫМ изображением отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки с изображением: {response.text}")
                return self.send_text_to_telegram(chat_id, text)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return self.send_text_to_telegram(chat_id, text)
    
    def send_text_to_telegram(self, chat_id, text):
        """Отправляет текстовый пост в Telegram"""
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                self.add_to_history(text, chat_id)
                self.add_full_post_to_history(chat_id, text)
                if self.current_theme:
                    self.add_theme_to_history(chat_id, self.current_theme)
                print(f"✅ Текстовый пост отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def generate_post_hash(self, text):
        """Генерирует хеш поста для проверки уникальности"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_post_unique(self, post_text, channel_id):
        """Проверяет уникальность поста по хешу"""
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if "posts" not in self.post_history:
            self.post_history["posts"] = {}
        if channel_key not in self.post_history["posts"]:
            self.post_history["posts"][channel_key] = []
        
        recent_posts = self.post_history["posts"][channel_key][-50:]
        return post_hash not in recent_posts

    def add_to_history(self, post_text, channel_id):
        """Добавляет пост в историю"""
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if "posts" not in self.post_history:
            self.post_history["posts"] = {}
        if channel_key not in self.post_history["posts"]:
            self.post_history["posts"][channel_key] = []
        
        self.post_history["posts"][channel_key].append(post_hash)
        if len(self.post_history["posts"][channel_key]) > 100:
            self.post_history["posts"][channel_key] = self.post_history["posts"][channel_key][-50:]
        
        self.save_post_history()

    def send_dual_posts(self):
        """Основной метод отправки постов в оба канала"""
        self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
        
        print(f"🎯 Умный выбор темы: {self.current_theme}")
        
        # Глубокий анализ истории перед генерацией
        print("🔍 Анализируем историю постов для обеспечения уникальности...")
        
        # Гарантированное получение изображения
        theme_image = self.get_unique_image(self.current_theme)
        
        if not theme_image:
            print("❌ Критическая ошибка: не удалось получить изображение!")
            return False
        
        print("🧠 Генерация УНИКАЛЬНЫХ постов с учетом истории...")
        tg_post = self.generate_tg_post(self.current_theme)
        zen_post = self.generate_zen_post(self.current_theme)
        
        # Форматируем посты
        tg_post_formatted = self.format_tg_post(tg_post)
        zen_post_formatted = self.format_zen_post(zen_post)
        
        print(f"📝 ТГ-пост: {len(tg_post_formatted)} символов")
        print(f"📝 Дзен-пост: {len(zen_post_formatted)} символов")
        
        # Проверка уникальности
        if not self.is_post_unique(tg_post_formatted, MAIN_CHANNEL_ID):
            print("⚠️ Пост для ТГ не уникален, генерируем заново...")
            return self.send_dual_posts()
            
        if not self.is_post_unique(zen_post_formatted, ZEN_CHANNEL_ID):
            print("⚠️ Пост для Дзена не уникален, генерируем заново...")  
            return self.send_dual_posts()
        
        print("📤 Отправка в @da4a_hr...")
        tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post_formatted, theme_image)
        
        print("📤 Отправка в @tehdzenm...")
        zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post_formatted, theme_image)
        
        if tg_success and zen_success:
            print("✅ УНИКАЛЬНЫЕ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ!")
            return True
        else:
            print(f"⚠️ Есть ошибки: ТГ={tg_success}, Дзен={zen_success}")
            return tg_success or zen_success


def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА")
    print("🎯 Глубокий анализ истории постов")
    print("🎯 Умная система уникальных изображений")
    print("🎯 Никаких повторений контента")
    print("🖼️ Динамический поиск изображений")
    print("=" * 80)
    
    bot = SmartPostGenerator()
    success = bot.send_dual_posts()
    
    if success:
        print("\n🎉 УСПЕХ! Уникальные посты с изображениями отправлены!")
    else:
        print("\n💥 ОШИБКА ОТПРАВКИ!")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
