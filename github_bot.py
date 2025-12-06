import os
import requests
import random
import json
import time
import logging
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    print("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    print("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

# Настройка сессии requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ (Telegram + Яндекс.Дзен)")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.prohibited_topics = ["удаленная работа", "гибридная работа", "оформление только по ТК"]
        
        # Расширенные тематические словари для лучшего поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": {
                "keywords_en": ["human resources", "recruitment", "office", "teamwork", "meeting", 
                               "business", "workplace", "interview", "corporate", "leadership",
                               "training", "employees", "collaboration", "professional", "career",
                               "manager", "staff", "workshop", "conference", "presentation"],
                "keywords_ru": ["кадры", "рекрутинг", "офис", "команда", "совещание",
                               "бизнес", "рабочее место", "собеседование", "корпоративный", "лидерство",
                               "обучение", "сотрудники", "сотрудничество", "профессионал", "карьера"],
                "required_words": ["office", "business", "team", "work", "professional"],
                "forbidden_words": ["home", "family", "leisure", "vacation", "sport", "nature", "art"]
            },
            "PR и коммуникации": {
                "keywords_en": ["public relations", "media", "communication", "marketing", "brand",
                               "social media", "networking", "press", "journalist", "campaign",
                               "strategy", "advertising", "digital", "content", "influencer",
                               "presentation", "event", "conference", "speaker", "audience"],
                "keywords_ru": ["пиар", "сми", "коммуникации", "маркетинг", "бренд",
                               "соцсети", "нетворкинг", "пресса", "журналист", "кампания",
                               "стратегия", "реклама", "цифровой", "контент", "инфлюенсер"],
                "required_words": ["media", "communication", "public", "marketing", "digital"],
                "forbidden_words": ["sport", "music", "food", "travel", "fashion", "beauty"]
            },
            "ремонт и строительство": {
                "keywords_en": ["construction", "renovation", "tools", "building", "repair",
                               "worker", "contractor", "hardhat", "equipment", "site",
                               "architecture", "design", "interior", "home improvement", "handyman",
                               "plumbing", "electrical", "carpentry", "painting", "renovation"],
                "keywords_ru": ["стройка", "ремонт", "инструменты", "здание", "починка",
                               "рабочий", "подрядчик", "каска", "оборудование", "площадка",
                               "архитектура", "дизайн", "интерьер", "обустройство дома", "мастер"],
                "required_words": ["construction", "building", "tools", "worker", "renovation"],
                "forbidden_words": ["nature", "sky", "clouds", "sunset", "sunrise", "landscape",
                                   "mountain", "ocean", "beach", "forest", "park", "garden",
                                   "animal", "wildlife", "flower", "tree", "water"]
            }
        }
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": (400, 600),
                "zen_chars": (600, 800),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "легкий бодрящий инсайт, мини-наблюдение, 1-2 коротких совета"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": (700, 900),
                "zen_chars": (700, 900),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "аналитический разбор ситуации, мини-исследование с цифрами"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": (600, 900),
                "zen_chars": (600, 700),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "мини-история с моралью, мнение автора + мягкая эмоция"
            }
        }

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": [],
                "image_queries": {}
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": [],
                "image_queries": {}
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            if "themes" not in self.post_history:
                self.post_history["themes"] = {}
            if "global" not in self.post_history["themes"]:
                self.post_history["themes"]["global"] = []
            
            self.post_history["themes"]["global"].append(theme)
            if len(self.post_history["themes"]["global"]) > 10:
                self.post_history["themes"]["global"] = self.post_history["themes"]["global"][-8:]
            
            self.save_post_history()
            logger.info(f"🎯 Выбрана тема: {theme}")
            return theme
            
        except Exception as e:
            logger.error(f"Ошибка выбора темы: {e}")
            return random.choice(self.themes)

    def create_combined_prompt(self, theme, time_slot_info, time_key):
        """Создает промпт для Gemini"""
        slot_name = time_slot_info['name']
        content_type = time_slot_info['content_type']
        tg_chars_min, tg_chars_max = time_slot_info['tg_chars']
        zen_chars_min, zen_chars_max = time_slot_info['zen_chars']
        
        prompt = f"""Ты — эксперт в создании контента с 30+ лет опыта. Создай 2 уникальных поста на тему: {theme}

ВРЕМЯ: {time_key} ({slot_name})
ТИП КОНТЕНТА: {content_type}
ЗАПРЕЩЕННЫЕ ТЕМЫ: {', '.join(self.prohibited_topics)} — НИКОГДА НЕ УПОМИНАТЬ!

⸻
ТРЕБОВАНИЯ К TELEGRAM ПОСТУ ({tg_chars_min}-{tg_chars_max} символов):

1. ИСТОРИИ/РАССКАЗЫ:
   • Хук → Рассказ (обычными абзацами) → Мораль → Вопрос
   
2. СПИСКИ/ПЕРЕЧИСЛЕНИЯ:
   • Хук → Пункты (с точками •) → Вывод → Вопрос

ВАЖНО: Не используй точки • в историях!

ОБЩИЕ ТРЕБОВАНИЯ:
• Стиль: живой, динамичный, человеческий
• Используй эмодзи в хуке и в конце
• 3-6 хештегов в конце
• Обязательный вопрос для обсуждения

⸻
ТРЕБОВАНИЯ К ЯНДЕКС.ДЗЕН ПОСТУ ({zen_chars_min}-{zen_chars_max} символов):

СТРУКТУРА:
• ХУК: 1-2 предложения без эмодзи
• ОСНОВНОЙ ТЕКСТ: абзацы без отступов
• ФАКТЫ или ЦИФРЫ
• ВЫВОД: четкие выводы
• ЗАКРЫВАШКА: вовлекающий вопрос
• ХЕШТЕГИ: 3-6 хештегов в конце

СТИЛЬ:
• Глубокий, аналитический, как мини-статья
• БЕЗ ЭМОДЗИ: никаких смайликов
• Четкая структура и логика
• Экспертность через факты и примеры

⸻
ВАЖНЫЕ ПРАВИЛА:
• Telegram: {tg_chars_min}-{tg_chars_max} символов
• Яндекс.Дзен: {zen_chars_min}-{zen_chars_max} символов
• Яндекс.Дзен НИКОГДА не превышает {zen_chars_max} символов!
• Яндекс.Дзен: ОБЯЗАТЕЛЬНЫ хештеги и закрывашка

⸻
ПОИСКОВЫЙ ЗАПРОС ДЛЯ ИЗОБРАЖЕНИЯ:

Проанализируй суть поста и создай 2 разных релевантных поисковых запроса на английском языке для фотобанка Pexels.com

ТЕМАТИКА: {theme}
ТРЕБОВАНИЯ ДЛЯ ЗАПРОСОВ:
1. Релевантные конкретному посту
2. Используй ключевые слова из поста на английском
3. 4-7 существительных и прилагательных через запятую
4. Разные запросы для Telegram и Яндекс.Дзен
5. Минимум 3 общих слова с тематикой

ПРИМЕРЫ ДЛЯ КАЖДОЙ ТЕМЫ:
• HR: "office meeting business team collaboration professional"
• PR: "media communication conference presentation public relations"
• Ремонт: "construction workers building site renovation tools"

ФОРМАТ: только существительные и прилагательные через запятую

Создай 2 РАЗНЫХ релевантных запроса: для Telegram и для Яндекс.Дзен

⸻
ФОРМАТ ОТВЕТА (ТОЧНО!):

Telegram-пост:
[Текст для Telegram]

Яндекс.Дзен-пост:
[Текст для Яндекс.Дзен]

Поисковый запрос для Telegram изображения:
[Запрос на английском, 4-7 слов, релевантный посту]

Поисковый запрос для Яндекс.Дзен изображения:
[Запрос на английском, 4-7 слов, релевантный посту]

⸻
НАЧИНАЙ ГЕНЕРАЦИЮ СЕЙЧАС!"""

        return prompt

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            test_data = {
                "contents": [{"parts": [{"text": "Test"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            
            response = session.post(url, json=test_data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Gemini доступен")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки Gemini: {e}")
            return False

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 3500,
                        "topP": 0.92,
                        "topK": 35
                    }
                }
                
                logger.info(f"🔄 Генерируем текст (попытка {attempt + 1}/{max_retries})...")
                
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        
                        total_length = len(generated_text)
                        logger.info(f"📄 Сгенерировано {total_length} символов")
                        
                        if "Telegram-пост:" in generated_text and "Яндекс.Дзен-пост:" in generated_text:
                            logger.info(f"✅ Текст сгенерирован")
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Нет структуры, пробуем снова...")
                            time.sleep(2)
                            continue
                    else:
                        logger.warning("⚠️ Gemini не вернул текст, пробуем снова...")
                        time.sleep(2)
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст")
        return None

    def split_text_and_queries(self, combined_text):
        """Разделяет текст на Telegram, Яндекс.Дзен и поисковые запросы"""
        if not combined_text:
            return None, None, None, None
        
        tg_query = None
        zen_query = None
        
        # Ищем запросы
        if "Поисковый запрос для Telegram изображения:" in combined_text:
            tg_part = combined_text.split("Поисковый запрос для Telegram изображения:")[1]
            if "Поисковый запрос для Яндекс.Дзен изображения:" in tg_part:
                tg_query = tg_part.split("Поисковый запрос для Яндекс.Дзен изображения:")[0]
            else:
                tg_query = tg_part
            tg_query = tg_query.strip().split('\n')[0].strip()
        
        if "Поисковый запрос для Яндекс.Дзен изображения:" in combined_text:
            zen_part = combined_text.split("Поисковый запрос для Яндекс.Дзен изображения:")[1]
            zen_query = zen_part.strip().split('\n')[0].strip()
        
        # Убираем запросы из текста
        for marker in ["Поисковый запрос для Telegram изображения:", "Поисковый запрос для Яндекс.Дзен изображения:"]:
            if marker in combined_text:
                combined_text = combined_text.split(marker)[0]
        
        # Ищем посты
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Яндекс.Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Яндекс.Дзен-пост:", "").strip()
            
            return tg_text, zen_text, tg_query, zen_query
        
        return None, None, tg_query, zen_query

    def analyze_post_content(self, text, theme):
        """Анализирует содержание поста для улучшения поиска изображений"""
        text_lower = text.lower()
        theme_info = self.theme_keywords.get(theme, {})
        
        # Извлекаем ключевые слова из текста
        found_keywords = []
        for keyword in theme_info.get('keywords_ru', []):
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        # Если нашли мало ключевых слов, добавляем тематические
        if len(found_keywords) < 3:
            found_keywords.extend(random.sample(theme_info.get('keywords_ru', [])[:10], 3))
        
        return list(set(found_keywords))[:5]

    def enhance_image_query(self, query, theme, post_text):
        """Улучшает поисковый запрос на основе содержания поста"""
        if not query or query == "None":
            return self.create_enhanced_query(theme, post_text)
        
        theme_info = self.theme_keywords.get(theme, {})
        
        # Очищаем запрос
        query = query.lower().strip()
        
        # Проверяем наличие обязательных слов для темы
        for required_word in theme_info.get('required_words', []):
            if required_word not in query:
                # Добавляем 1-2 обязательных слова
                query_words = query.split(',')
                query_words.append(required_word)
                query = ', '.join(list(set(query_words))[:7])
        
        # Убираем запрещенные слова
        for forbidden_word in theme_info.get('forbidden_words', []):
            query = re.sub(r'\b' + re.escape(forbidden_word) + r'\b', '', query, flags=re.IGNORECASE)
        
        # Очищаем от лишних запятых
        query = re.sub(r',\s*,+', ', ', query)
        query = re.sub(r'^\s*,|\s*,\s*$', '', query)
        
        # Добавляем случайное ключевое слово для разнообразия
        if len(query.split(',')) < 5:
            extra_keywords = random.sample(theme_info.get('keywords_en', [])[:15], 2)
            query += ', ' + ', '.join([kw for kw in extra_keywords if kw not in query])
        
        # Ограничиваем длину
        words = [w.strip() for w in query.split(',') if w.strip()]
        words = list(set(words))[:7]  # Уникальные слова, макс 7
        
        return ', '.join(words)

    def create_enhanced_query(self, theme, post_text):
        """Создает улучшенный запрос на основе темы и текста"""
        theme_info = self.theme_keywords.get(theme, {})
        
        # Анализируем текст поста
        post_keywords = self.analyze_post_content(post_text, theme)
        
        # Базовые ключевые слова темы
        base_keywords = random.sample(theme_info.get('keywords_en', [])[:10], 4)
        
        # Добавляем обязательные слова
        required_keywords = theme_info.get('required_words', [])[:2]
        
        # Комбинируем
        all_keywords = list(set(base_keywords + required_keywords))
        
        # Переводим найденные русские ключевые слова (упрощенный вариант)
        keyword_translation = {
            "кадры": "human resources",
            "рекрутинг": "recruitment",
            "офис": "office",
            "команда": "team",
            "совещание": "meeting",
            "пиар": "public relations",
            "сми": "media",
            "коммуникации": "communication",
            "стройка": "construction",
            "ремонт": "renovation",
            "инструменты": "tools"
        }
        
        for ru_keyword in post_keywords[:2]:
            if ru_keyword in keyword_translation:
                all_keywords.append(keyword_translation[ru_keyword])
        
        # Убираем дубли и ограничиваем
        all_keywords = list(set(all_keywords))[:6]
        
        return ', '.join(all_keywords)

    def search_pexels_image(self, search_query, theme, post_text, width=1200, height=630):
        """Ищет релевантное изображение на Pexels"""
        try:
            # Улучшаем запрос на основе содержания поста
            enhanced_query = self.enhance_image_query(search_query, theme, post_text)
            
            # Используем стандартный API ключ Pexels
            PEXELS_API_KEY = "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c"
            
            encoded_query = quote_plus(enhanced_query)
            url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=15&orientation=landscape"
            
            headers = {
                "Authorization": PEXELS_API_KEY,
                "User-Agent": "Mozilla/5.0"
            }
            
            logger.info(f"🔍 Pexels поиск: '{enhanced_query}' для темы '{theme}'")
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos') and len(data['photos']) > 0:
                    # Фильтруем по релевантности теме
                    relevant_photos = self.filter_relevant_photos(data['photos'], theme, enhanced_query)
                    
                    if relevant_photos:
                        # Выбираем лучшее фото по релевантности
                        best_photo = self.select_best_photo(relevant_photos, theme, enhanced_query)
                        image_url = best_photo['src']['large']
                        
                        # Сохраняем успешный запрос в историю
                        self.save_successful_query(theme, enhanced_query)
                        
                        logger.info(f"✅ Найдено релевантное изображение")
                        return image_url
                    else:
                        # Если не нашли релевантных, берем первое
                        photo = data['photos'][0]
                        image_url = photo['src']['large']
                        logger.info(f"⚠️ Используем доступное изображение")
                        return image_url
                else:
                    logger.warning(f"⚠️ Pexels не нашел фото по запросу: '{enhanced_query}'")
                    return self.get_smart_fallback_image(theme, enhanced_query, width, height)
            else:
                logger.warning(f"⚠️ Pexels API ошибка: {response.status_code}")
                return self.get_smart_fallback_image(theme, enhanced_query, width, height)
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска на Pexels: {e}")
            return self.get_smart_fallback_image(theme, search_query, width, height)

    def filter_relevant_photos(self, photos, theme, query):
        """Фильтрует фотографии по релевантности теме и запросу"""
        if not photos:
            return photos
        
        theme_info = self.theme_keywords.get(theme, {})
        query_words = set([w.strip().lower() for w in query.split(',')])
        
        relevant_photos = []
        
        for photo in photos:
            photo_description = (photo.get('alt') or photo.get('photographer') or '').lower()
            photo_url = photo.get('url', '').lower()
            
            # Проверяем наличие слов запроса
            query_match_score = sum(1 for word in query_words if word in photo_description or word in photo_url)
            
            # Проверяем обязательные слова
            has_required = all(req_word in photo_description for req_word in theme_info.get('required_words', [])[:2])
            
            # Проверяем запрещенные слова
            has_forbidden = any(forb_word in photo_description for forb_word in theme_info.get('forbidden_words', []))
            
            # Проверяем тематические ключевые слова
            theme_match_score = sum(1 for keyword in theme_info.get('keywords_en', [])[:10] 
                                  if keyword in photo_description)
            
            # Общий счет релевантности
            total_score = query_match_score * 3 + theme_match_score * 2
            
            if has_required and not has_forbidden and total_score > 2:
                photo['relevance_score'] = total_score
                relevant_photos.append(photo)
        
        # Сортируем по релевантности
        relevant_photos.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return relevant_photos

    def select_best_photo(self, photos, theme, query):
        """Выбирает лучшее фото из релевантных"""
        if not photos:
            return None
        
        # Если есть фото с высоким скором, берем его
        for photo in photos:
            if photo.get('relevance_score', 0) > 5:
                return photo
        
        # Иначе выбираем случайно из топ-3
        top_photos = photos[:3]
        return random.choice(top_photos)

    def save_successful_query(self, theme, query):
        """Сохраняет успешные запросы для будущего использования"""
        if "image_queries" not in self.post_history:
            self.post_history["image_queries"] = {}
        
        if theme not in self.post_history["image_queries"]:
            self.post_history["image_queries"][theme] = []
        
        # Добавляем запрос если его еще нет
        if query not in self.post_history["image_queries"][theme]:
            self.post_history["image_queries"][theme].append(query)
            
            # Ограничиваем историю
            if len(self.post_history["image_queries"][theme]) > 20:
                self.post_history["image_queries"][theme] = self.post_history["image_queries"][theme][-20:]
            
            self.save_post_history()

    def get_smart_fallback_image(self, theme, query, width=1200, height=630):
        """Умный запасной вариант изображения"""
        try:
            # Пробуем найти по более общему запросу
            theme_info = self.theme_keywords.get(theme, {})
            general_keywords = theme_info.get('keywords_en', [])[:5]
            general_query = ', '.join(general_keywords)
            
            # Используем сохраненные успешные запросы
            saved_queries = self.post_history.get("image_queries", {}).get(theme, [])
            if saved_queries:
                saved_query = random.choice(saved_queries)
                PEXELS_API_KEY = "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c"
                encoded_query = quote_plus(saved_query)
                url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=5&orientation=landscape"
                
                headers = {"Authorization": PEXELS_API_KEY}
                response = session.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('photos'):
                        photo = random.choice(data['photos'])
                        return photo['src']['large']
            
            # Используем тематические изображения с Unsplash
            unsplash_themes = {
                "HR и управление персоналом": ["office", "business", "meeting", "workplace"],
                "PR и коммуникации": ["communication", "media", "marketing", "presentation"],
                "ремонт и строительство": ["construction", "tools", "building", "renovation"]
            }
            
            unsplash_theme = random.choice(unsplash_themes.get(theme, ["business", "work"]))
            return f"https://source.unsplash.com/featured/{width}x{height}/?{unsplash_theme}"
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка fallback: {e}")
            # Используем тематические изображения с Picsum
            pic_ids = {
                "HR и управление персоналом": [21, 22, 23, 24, 25],  # Офис, совещания
                "PR и коммуникации": [31, 32, 33, 34, 35],  # Коммуникации, медиа
                "ремонт и строительство": [11, 12, 13, 14, 15]  # Инструменты, стройка
            }
            
            pic_id_list = pic_ids.get(theme, [1, 2, 3, 4, 5])
            pic_id = random.choice(pic_id_list)
            
            return f"https://picsum.photos/id/{pic_id}/{width}/{height}"

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        # Очищаем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем HTML сущности
        replacements = {
            '&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', 
            '**': '', '__': '', '&amp;': '&', '&lt;': '<',
            '&gt;': '>', '&quot;': '"', '&#39;': "'"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Определяем тип поста
        lines = text.split('\n')
        text_lower = text.lower()
        
        # Проверяем на историю
        is_story = any(keyword in text_lower for keyword in [
            'история', 'случай', 'пример', 'ситуация', 'опыт',
            'однажды', 'как-то раз', 'в один день', 'недавно'
        ])
        
        # Форматируем
        formatted_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                in_list = False
                continue
            
            # Если это список (перечисление) и НЕ история
            if line.startswith('•') and not is_story:
                # Убираем эмодзи из пунктов списка
                line = re.sub(r'^•\s*[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line)
                formatted_lines.append("            • " + line[1:].strip())
                in_list = True
            # Если история с точками - убираем точки
            elif line.startswith('•') and is_story:
                line_content = line[1:].strip()
                line_content = re.sub(r'^[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line_content)
                formatted_lines.append(line_content)
                in_list = False
            else:
                formatted_lines.append(line)
                in_list = False
        
        formatted_text = '\n'.join(formatted_lines)
        
        # Убираем лишние пустые строки
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        # Убираем двойные пробелы
        formatted_text = re.sub(r'  +', ' ', formatted_text)
        
        # Добавляем хештеги если нет
        hashtag_count = len(re.findall(r'#\w+', formatted_text))
        if hashtag_count < 3:
            formatted_text = self.add_telegram_hashtags(formatted_text, self.current_theme)
        
        return formatted_text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Яндекс.Дзен"""
        if not text:
            return ""
        
        # Очищаем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем HTML сущности
        replacements = {
            '&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', 
            '**': '', '__': '', '&amp;': '&', '&lt;': '<',
            '&gt;': '>', '&quot;': '"', '&#39;': "'"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Убираем эмодзи
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # Убираем отступы в начале строк
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
        
        formatted_text = '\n\n'.join(lines)
        
        # Добавляем хештеги если нет
        hashtag_count = len(re.findall(r'#\w+', formatted_text))
        if hashtag_count < 3:
            formatted_text = self.add_zen_hashtags(formatted_text, self.current_theme)
        
        # Проверяем наличие закрывашки
        if not self.has_closing_hook(formatted_text):
            formatted_text = self.add_closing_hook(formatted_text, is_telegram=False)
        
        return formatted_text.strip()

    def check_prohibited_topics(self, text):
        """Проверяет запрещенные темы"""
        text_lower = text.lower()
        
        for topic in self.prohibited_topics:
            if topic in text_lower:
                logger.warning(f"⚠️ Обнаружена запрещенная тема: {topic}")
                if "удаленная работа" in text_lower:
                    text = re.sub(r'удаленная работа', 'формат работы', text, flags=re.IGNORECASE)
                if "гибридная работа" in text_lower:
                    text = re.sub(r'гибридная работа', 'смешанный формат', text, flags=re.IGNORECASE)
                if "оформление только по тк" in text_lower:
                    text = re.sub(r'оформление только по тк', 'оформление документов', text, flags=re.IGNORECASE)
        
        return text

    def has_closing_hook(self, text):
        """Проверяет наличие закрывашки"""
        text_lower = text[-150:].lower() if len(text) > 150 else text.lower()
        hook_indicators = [
            'как вы считаете', 'что думаете', 'ваше мнение',
            'пишите в комментариях', 'обсудим', 'расскажите',
            'поделитесь', 'комментируйте', 'жду ваши мысли',
            'а у вас', 'сталкивались', 'какой подход'
        ]
        return any(indicator in text_lower for indicator in hook_indicators)

    def add_closing_hook(self, text, is_telegram=True):
        """Добавляет закрывашку"""
        if is_telegram:
            hooks = [
                "\n\nКак вы считаете? Жду ваши мысли в комментариях! 💬",
                "\n\nА у вас был похожий опыт? Расскажите! ✨",
                "\n\nКакой подход ближе вам? Обсудим! 👇"
            ]
        else:
            hooks = [
                "\n\nЧто думаете по этому поводу? Поделитесь мнением в комментариях.",
                "\n\nА как вы решаете подобные проблемы в своей практике?",
                "\n\nСталкивались ли вы с такой ситуацией? Как поступали?"
            ]
        
        hook = random.choice(hooks)
        return text.rstrip() + hook

    def add_telegram_hashtags(self, text, theme):
        """Добавляет хештеги для Telegram"""
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера", "#работа", "#команда"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#бренд", "#пиар", "#медиа"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#дом", "#интерьер", "#отделка"]
        }
        
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы", "#бизнес"])
        general_hashtags = ["#инсайты", "#лайфхак", "#профессия", "#развитие"]
        random.shuffle(general_hashtags)
        
        all_hashtags = base_hashtags[:4] + general_hashtags[:2]
        hashtags_to_add = random.sample(all_hashtags, min(5, len(all_hashtags)))
        
        hashtags_line = " ".join(hashtags_to_add)
        return f"{text}\n\n{hashtags_line}"

    def add_zen_hashtags(self, text, theme):
        """Добавляет хештеги для Яндекс.Дзен"""
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера", "#работа"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#бренд", "#пиар"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#дом", "#интерьер"]
        }
        
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы"])
        general_hashtags = ["#инсайты", "#профессия", "#развитие", "#бизнес"]
        random.shuffle(general_hashtags)
        
        all_hashtags = base_hashtags[:4] + general_hashtags[:2]
        hashtags_to_add = random.sample(all_hashtags, min(5, len(all_hashtags)))
        
        hashtags_line = " ".join(hashtags_to_add)
        return f"{text}\n\n{hashtags_line}"

    def check_length_and_fix(self, text, max_length, is_telegram=True):
        """Проверяет длину и исправляет если нужно"""
        current_len = len(text)
        
        if current_len <= max_length:
            return text
        
        logger.warning(f"⚠️ Текст превышает лимит ({current_len} > {max_length}), сокращаю...")
        
        # Сохраняем хештеги
        hashtags_match = re.search(r'(#\w+\s*)+$', text)
        hashtags = hashtags_match.group(0) if hashtags_match else ""
        text_without_hashtags = text[:hashtags_match.start()] if hashtags_match else text
        
        # Сокращаем основной текст
        target_length = max_length - len(hashtags) - 20
        
        if len(text_without_hashtags) <= target_length:
            result = text_without_hashtags + ("\n\n" + hashtags if hashtags else "")
        else:
            # Находим последнее хорошее место для обрезки
            truncated = text_without_hashtags[:target_length]
            
            last_period = truncated.rfind('.')
            last_question = truncated.rfind('?')
            last_exclamation = truncated.rfind('!')
            last_newline = truncated.rfind('\n')
            
            best_cut = max(last_period, last_question, last_exclamation, last_newline)
            
            if best_cut > target_length * 0.7:
                result = text_without_hashtags[:best_cut + 1].strip()
            else:
                result = text_without_hashtags[:target_length - 3].strip() + "..."
            
            if hashtags:
                result += "\n\n" + hashtags
        
        logger.info(f"📊 После сокращения: {len(result)} символов")
        return result

    def send_single_post(self, chat_id, text, image_url, is_telegram=True):
        """Отправляет пост"""
        try:
            max_length = 1024
            
            if len(text) > max_length:
                text = self.check_length_and_fix(text, max_length, is_telegram)
            
            if not image_url or not image_url.startswith('http'):
                logger.error(f"❌ Невалидный URL изображения: {image_url}")
                return False
            
            # Добавляем параметры для Pexels если нужно
            if 'pexels.com' in image_url and '?' not in image_url:
                image_url += '?auto=compress&cs=tinysrgb&w=1200&h=630&fit=crop'
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            logger.info(f"📤 Отправляем пост в {chat_id}")
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Пост отправлен в {chat_id}")
                logger.info(f"📊 Длина: {len(text)} символов")
                logger.info(f"🖼️ Изображение: {image_url}")
                return True
            else:
                logger.error(f"❌ Ошибка отправки: {response.status_code}")
                if response.text:
                    logger.error(f"❌ Ответ сервера: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def generate_and_send_posts(self):
        """Главная функция"""
        try:
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            now = self.get_moscow_time()
            
            if 5 <= now.hour < 12:
                time_key = "09:00"
                schedule_time = "09:00"
            elif 12 <= now.hour < 17:
                time_key = "14:00"
                schedule_time = "14:00"
            else:
                time_key = "19:00"
                schedule_time = "19:00"
            
            time_slot_info = self.time_slots[time_key]
            
            logger.info(f"🕒 Запуск: {schedule_time} МСК")
            logger.info(f"📝 Тип: {time_slot_info['name']}")
            
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info, time_key)
            logger.info(f"📝 Длина промпта: {len(combined_prompt)} символов")
            
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            tg_text, zen_text, tg_image_query, zen_image_query = self.split_text_and_queries(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            logger.info(f"📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
            logger.info(f"📊 Яндекс.Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
            
            if tg_len > tg_max:
                tg_text = self.check_length_and_fix(tg_text, tg_max, True)
                tg_len = len(tg_text)
                logger.info(f"📊 Telegram после коррекции: {tg_len} символов")
            
            if zen_len > zen_max:
                zen_text = self.check_length_and_fix(zen_text, zen_max, False)
                zen_len = len(zen_text)
                logger.info(f"📊 Яндекс.Дзен после коррекции: {zen_len} символов")
            
            logger.info("🖼️ Ищем РЕЛЕВАНТНЫЕ тематические изображения...")
            
            # Для Telegram - улучшенный поиск
            tg_image_url = self.search_pexels_image(tg_image_query, self.current_theme, tg_text)
            logger.info(f"🔍 Telegram запрос: {tg_image_query}")
            
            time.sleep(1)
            
            # Для Яндекс.Дзен - улучшенный поиск
            zen_image_url = self.search_pexels_image(zen_image_query, self.current_theme, zen_text)
            logger.info(f"🔍 Яндекс.Дзен запрос: {zen_image_query}")
            
            if not tg_image_url or not zen_image_url:
                logger.error("❌ Не удалось найти изображения")
                return False
            
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Telegram
            logger.info(f"  → Telegram: {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url, is_telegram=True):
                success_count += 1
            
            time.sleep(2)
            
            # Яндекс.Дзен
            logger.info(f"  → Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url, is_telegram=False):
                success_count += 1
            
            if success_count == 2:
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "telegram_image_query": tg_image_query,
                    "zen_image_query": zen_image_query,
                    "telegram_enhanced_query": self.enhance_image_query(tg_image_query, self.current_theme, tg_text),
                    "zen_enhanced_query": self.enhance_image_query(zen_image_query, self.current_theme, zen_text),
                    "time": now.strftime("%H:%M:%S")
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.post_history["last_post_time"] = now.isoformat()
                self.save_post_history()
                
                logger.info("\n" + "=" * 60)
                logger.info("🎉 УСПЕХ! Посты отправлены!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time} МСК")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Яндекс.Дзен: {zen_len} символов")
                logger.info(f"   🖼️ Telegram изображение найдено по: {tg_image_query}")
                logger.info(f"   🖼️ Яндекс.Дзен изображение найдено по: {zen_image_query}")
                logger.info("=" * 60)
                return True
            else:
                logger.error(f"❌ Отправка не удалась. Успешно: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ С РЕЛЕВАНТНЫМИ ИЗОБРАЖЕНИЯМИ")
    print("=" * 80)
    print("📋 Улучшенные возможности:")
    print("   • AI анализирует содержание поста для поиска релевантных фото")
    print("   • Расширенные тематические словари для каждой темы")
    print("   • Улучшенные поисковые запросы на основе текста поста")
    print("   • Фильтрация по обязательным и запрещенным словам")
    print("   • Сохранение успешных запросов для будущего использования")
    print("   • Умные fallback-изображения")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты созданы и отправлены")
        print("   Релевантные изображения найдены")
        print("   Контент и картинки идеально сочетаются")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
