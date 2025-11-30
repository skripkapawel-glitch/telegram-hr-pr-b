import os
import requests
import random
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: ВРЕМЕННАЯ ОПТИМИЗАЦИЯ ПОСТОВ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временная привязка типов постов для Telegram
        self.time_slots = {
            "09:00": "short",    # Утро - короткий пост
            "14:00": "long",     # Обед - длинный пост  
            "19:00": "medium"    # Вечер - средний пост
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting", "business workplace", "corporate culture", 
                "team collaboration", "professional development", "workplace diversity"
            ],
            "PR и коммуникации": [
                "public relations", "media communication", "social media marketing",
                "brand strategy", "digital marketing", "communication technology"
            ],
            "ремонт и строительство": [
                "construction site", "building renovation", "home improvement",
                "interior design", "architecture", "construction workers"
            ]
        }
        
        self.image_sources = [
            self.search_unsplash_image,
            self.search_pexels_image,
            self.get_fallback_image
        ]

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "used_images" not in data:
                        data["used_images"] = {}
                    if "full_posts" not in data:
                        data["full_posts"] = {}
                    return data
            return {
                "posts": {}, 
                "themes": {}, 
                "full_posts": {}, 
                "used_images": {},
                "tg_types": {}
            }
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {
                "posts": {}, 
                "themes": {}, 
                "full_posts": {}, 
                "used_images": {},
                "tg_types": {}
            }
    
    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом истории"""
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
        """Возвращает последние темы для канала"""
        channel_key = str(channel_id)
        themes = self.post_history.get("themes", {}).get(channel_key, [])
        return themes[-count:] if len(themes) >= count else themes

    def get_tg_type_by_time(self):
        """Определяет тип поста для ТГ based on current time"""
        now = datetime.now().strftime("%H:%M")
        
        # Находим ближайший временной слот
        current_time = datetime.now()
        time_differences = {}
        
        for slot_time, post_type in self.time_slots.items():
            slot_datetime = datetime.strptime(slot_time, "%H:%M").replace(
                year=current_time.year, 
                month=current_time.month, 
                day=current_time.day
            )
            diff = abs((current_time - slot_datetime).total_seconds())
            time_differences[post_type] = diff
        
        # Выбираем тип поста с минимальной разницей во времени
        selected_type = min(time_differences, key=time_differences.get)
        
        print(f"🕒 Текущее время: {now}")
        print(f"📊 Выбран тип поста: {selected_type.upper()} для временного слота")
        
        return selected_type

    def create_telegram_prompt(self, theme, history_analysis, post_type, time_slot):
        """Создает промпт для Telegram с учетом типа поста и времени"""
        
        time_contexts = {
            "09:00": {
                "mood": "утренняя энергия и мотивация",
                "purpose": "быстрое погружение в тему дня",
                "reader_state": "просыпаются, проверяют уведомления"
            },
            "14:00": {
                "mood": "обеденный перерыв, время для глубокого чтения", 
                "purpose": "ценный контент для сохранения и вдумчивого изучения",
                "reader_state": "ищут полезную информацию для профессионального роста"
            },
            "19:00": {
                "mood": "вечернее подведение итогов",
                "purpose": "рефлексия и планирование на завтра", 
                "reader_state": "анализируют день, ищут inspiration для завтрашнего дня"
            }
        }
        
        type_requirements = {
            "short": {
                "words": "50-100 слов (1-2 коротких абзаца)",
                "structure": "1. Яркий заголовок\n2. 1 ключевой факт/тренд\n3. Короткий вопрос для вовлечения",
                "focus": "максимальная лаконичность, быстрый захват внимания"
            },
            "medium": {
                "words": "120-220 слов (3-4 абзаца)", 
                "structure": "1. Цепляющий заголовок\n2. 2-3 актуальных факта\n3. 2 практических совета\n4. Вопрос для обсуждения",
                "focus": "баланс лаконичности и полезности"
            },
            "long": {
                "words": "300-450 слов (5-7 абзацев)",
                "structure": "1. Глубокий заголовок\n2. 3-4 значимых тренда с данными\n3. Развернутые рекомендации\n4. Конкретный кейс/пример\n5. Призыв к сохранению/обсуждению",
                "focus": "максимальная ценность для сохранения и репостов"
            }
        }
        
        req = type_requirements[post_type]
        time_info = time_contexts.get(time_slot, time_contexts["09:00"])
        
        return f"""
        Напиши УНИКАЛЬНЫЙ пост для Telegram на тему "{theme}" за 2024-2025 год.

        ⏰ ВРЕМЯ ПУБЛИКАЦИИ: {time_slot} ({time_info['mood']})
        📊 ТИП ПОСТА: {post_type.upper()} 
        👥 СОСТОЯНИЕ АУДИТОРИИ: {time_info['reader_state']}

        ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
        - Объем: {req['words']}
        - Фокус: {req['focus']}
        - Цель: {time_info['purpose']}

        ВАЖНО: Пост должен кардинально отличаться от предыдущих публикаций.

        Анализ истории канала:
        {history_analysis}

        🎯 СТРУКТУРА ДЛЯ {time_slot}:
        {req['structure']}

        💡 КОНТЕКСТ ВРЕМЕНИ:
        - Учитывай {time_info['mood']} в подаче
        - Адаптируй контент под {time_info['reader_state']}
        - Фокусируйся на {time_info['purpose']}

        🚀 ТРЕБОВАНИЯ К КОНТЕНТУ:
        - АБСОЛЮТНАЯ УНИКАЛЬНОСТЬ относительно истории канала
        - Только практическая польза, без воды
        - Естественный язык, соответствующий времени суток
        - Используй • для пунктов в средних и длинных постах
        - В конце - вовлекающий вопрос, релевантный времени

        Длина строго в рамках указанного объема!
        Создай контент, идеально подходящий для публикации в {time_slot}!
        """

    def create_zen_prompt(self, theme, history_analysis):
        """Создает промпт для Яндекс.Дзена с увеличенным объемом"""
        return f"""
        СОЗДАЙ РАЗВЕРНУТЫЙ ПОСТ ДЛЯ ЯНДЕКС.ДЗЕНА по теме "{theme}" 2024-2025 год.

        ⚡ ТРЕБОВАНИЯ К ОБЪЕМУ:
        - ОПТИМАЛЬНЫЙ ДИАПАЗОН: 4000-7000 знаков (≈ 600-1000 слов)
        - Минимум: 3000 знаков (≈ 400-500 слов)
        - Фокус на глубину и ценность для читателя

        ВАЖНО: Пост должен быть СТРУКТУРИРОВАННЫМ и УНИКАЛЬНЫМ.

        Анализ истории канала:
        {history_analysis}

        🟡 СТРУКТУРА ДЛЯ ЯНДЕКС.ДЗЕНА:

        1. ЗАГОЛОВОК (6-9 слов, SEO + интрига)
        - Кликабельный и содержательный

        2. ИНТРО (3-4 предложения)
        - Обозначь проблему/контекст
        - Покажи ценность чтения

        3. ГЛУБОКИЙ АНАЛИЗ ПРОБЛЕМЫ (4-6 предложений)
        - Раскрой вызовы и тренды
        - Приведи статистику или исследования

        4. КЛЮЧЕВОЙ ИНСАЙТ (1-2 предложения)
        - Главная мысль поста

        5. ОСНОВНОЙ БЛОК — ПОШАГОВАЯ ПОЛЕЗНОСТЬ
        • Пункт 1 (3-5 предложений с деталями)
        • Пункт 2 (3-5 предложений с деталями)
        • Пункт 3 (3-5 предложений с деталями)
        • Дополнительные пункты при необходимости

        6. РАЗВЕРНУТЫЙ КЕЙС/ПРИМЕР (5-8 предложений)
        - Конкретная история с цифрами и результатами
        - Практическое применение рекомендаций

        7. ВЫВОДЫ И ПЕРСПЕКТИВЫ (4-6 предложений)
        - Итоги и взгляд в будущее
        - Как применять полученные знания

        8. CTA - МЯГКОЕ ВОВЛЕЧЕНИЕ
        - Вопрос для обсуждения в комментариях

        ⚡ КРИТИЧЕСКИ ВАЖНО:
        - ОБЪЕМ: 4000-7000 знаков (контролируй!)
        - Глубина раскрытия темы
        - Практическая ценность каждого абзаца
        - Структурность и читабельность
        - Без эмодзи и хештегов
        - Профессиональный, но доступный язык

        Создай РАЗВЕРНУТЫЙ пост с настоящей ценностью для читателя!
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

    def generate_with_gemini(self, prompt):
        """Генерирует текст с помощью Gemini API"""
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
                        "temperature": 0.9,
                        "maxOutputTokens": 2000,
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

    def generate_tg_post(self, theme, post_type, time_slot):
        """Генерирует пост для Telegram определенного типа с учетом времени"""
        history_analysis = self.analyze_channel_history(MAIN_CHANNEL_ID, theme)
        prompt = self.create_telegram_prompt(theme, history_analysis, post_type, time_slot)
        return self.generate_with_gemini(prompt)

    def generate_zen_post(self, theme):
        """Генерирует развернутый пост для Дзена"""
        history_analysis = self.analyze_channel_history(ZEN_CHANNEL_ID, theme)
        prompt = self.create_zen_prompt(theme, history_analysis)
        return self.generate_with_gemini(prompt)

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
        """Форматирует пост для Дзена"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Сохраняем структуру с отступами для пунктов
                if line.startswith('•'):
                    formatted_lines.append(f"    {line}")
                else:
                    formatted_lines.append(line)
        
        # Добавляем стандартное окончание
        if formatted_lines and not any('публикация' in line.lower() for line in formatted_lines[-3:]):
            formatted_lines.append('')
            formatted_lines.append('© Публикация')
        
        return '\n'.join(formatted_lines)

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
            headers = {'Authorization': PEXELS_API_KEY}
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
        """Резервный источник изображений"""
        try:
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
            image_id = random.randint(1, 1000)
            image_url = f"https://picsum.photos/1200/630?random={image_id}"
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
        
        theme_key = theme
        if "used_images" not in self.post_history:
            self.post_history["used_images"] = {}
        if theme_key not in self.post_history["used_images"]:
            self.post_history["used_images"][theme_key] = []
        
        used_images = self.post_history["used_images"][theme_key]
        
        attempts = 0
        max_attempts = len(self.image_sources) * 2
        
        while attempts < max_attempts:
            image_source = random.choice(self.image_sources)
            image_url = image_source(theme)
            
            if image_url and image_url not in used_images:
                used_images.append(image_url)
                if len(used_images) > 20:
                    used_images.pop(0)
                
                self.save_post_history()
                print(f"✅ Уникальное изображение найдено: {image_url[:80]}...")
                return image_url
            
            attempts += 1
        
        if used_images:
            least_used = used_images[0]
            print(f"🔄 Используем наименее использованное изображение")
            return least_used
        
        for source in self.image_sources:
            image_url = source(theme)
            if image_url:
                print(f"⚠️ Используем любое доступное изображение")
                return image_url
        
        print("❌ Не удалось найти изображение")
        return None

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

    def add_theme_to_history(self, channel_id, theme):
        """Добавляет тему в историю"""
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
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
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
                print(f"✅ Пост с изображением отправлен в {chat_id}")
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

    def validate_post_length(self, tg_post, zen_post):
        """Проверяет соответствие объемов требованиям"""
        tg_chars = len(tg_post)
        zen_chars = len(zen_post)
        
        print("📏 ПРОВЕРКА ОБЪЕМОВ:")
        print(f"   ТГ ({self.current_tg_type}): {tg_chars} знаков")
        
        # Проверяем Дзен
        if zen_chars < 3000:
            print("❌ Дзен: СЛИШКОМ КОРОТКО! (< 3000 знаков)")
        elif zen_chars > 10000:
            print("⚠️  Дзен: Очень длинный (> 10000 знаков)")
        else:
            print(f"✅ Дзен: Оптимальный объем ({zen_chars} знаков)")

    def send_dual_posts(self):
        """Основной метод отправки постов в оба канала"""
        self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
        current_time = datetime.now().strftime("%H:%M")
        self.current_tg_type = self.get_tg_type_by_time()
        
        # Определяем временной слот
        time_slot = min(self.time_slots.keys(), 
                       key=lambda x: abs(datetime.strptime(x, "%H:%M") - 
                                       datetime.strptime(current_time, "%H:%M")))
        
        print(f"🎯 Тема: {self.current_theme}")
        print(f"🕒 Время: {current_time} (слот: {time_slot})")
        print(f"📊 Тип ТГ-поста: {self.current_tg_type.upper()}")
        
        # Получаем изображение
        theme_image = self.get_unique_image(self.current_theme)
        
        print("🧠 Генерация постов с учетом времени...")
        tg_post = self.generate_tg_post(self.current_theme, self.current_tg_type, time_slot)
        zen_post = self.generate_zen_post(self.current_theme)
        
        if not tg_post or not zen_post:
            print("❌ Не удалось сгенерировать посты")
            return False
        
        # Форматируем посты
        tg_post_formatted = self.format_tg_post(tg_post)
        zen_post_formatted = self.format_zen_post(zen_post)
        
        print(f"📝 ТГ-пост ({self.current_tg_type} для {time_slot}): {len(tg_post_formatted)} символов")
        print(f"📝 Дзен-пост: {len(zen_post_formatted)} символов")
        
        # Проверяем объемы
        self.validate_post_length(tg_post_formatted, zen_post_formatted)
        
        # Проверяем уникальность
        if not self.is_post_unique(tg_post_formatted, MAIN_CHANNEL_ID):
            print("⚠️ Пост для ТГ не уникален, генерируем заново...")
            return self.send_dual_posts()
            
        if not self.is_post_unique(zen_post_formatted, ZEN_CHANNEL_ID):
            print("⚠️ Пост для Дзена не уникален, генерируем заново...")  
            return self.send_dual_posts()
        
        # Отправляем посты
        print("📤 Отправка в @da4a_hr...")
        tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post_formatted, theme_image)
        
        print("📤 Отправка в @tehdzenm...")
        zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post_formatted, theme_image)
        
        if tg_success and zen_success:
            print("✅ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ С УЧЕТОМ ВРЕМЕНИ!")
            return True
        else:
            print(f"⚠️ Есть ошибки: ТГ={tg_success}, Дзен={zen_success}")
            return tg_success or zen_success


def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Временная оптимизация: 9:00-короткие, 14:00-длинные, 19:00-средние")
    print("🎯 Яндекс.Дзен: 4000-7000 знаков глубины")
    print("🎯 Уникальные изображения для каждого поста")
    print("=" * 80)
    
    bot = SmartPostGenerator()
    success = bot.send_dual_posts()
    
    if success:
        print("\n🎉 УСПЕХ! Посты отправлены с учетом временных слотов!")
    else:
        print("\n💥 ОШИБКА ОТПРАВКИ!")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
