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
        
        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office meeting", "teamwork business", "workplace corporate", 
                "recruitment interview", "human resources", "business team",
                "corporate office", "workplace collaboration", "professional meeting"
            ],
            "PR и коммуникации": [
                "media communication", "public relations", "marketing strategy", 
                "digital marketing", "social media", "press conference",
                "media presentation", "communication business", "public speaking"
            ],
            "ремонт и строительство": [
                "construction worker", "renovation tools", "building site", 
                "home repair", "construction equipment", "construction site",
                "renovation project", "building construction", "tools equipment"
            ]
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
                "last_slots": []
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": []
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

Создай 2 разных поисковых запроса на английском языке для фотобанков Pexels.com и Unsplash.com

ТЕМАТИКА: {theme}

ТРЕБОВАНИЯ К ЗАПРОСАМ:
1. Только существительные и прилагательные через запятую
2. 4-7 слов максимум
3. Релевантные теме {theme}
4. НИКАКИХ КАВЫЧЕК в запросе
5. Используй общие ключевые слова для поиска
6. Запросы должны быть РАЗНЫЕ для Telegram и Яндекс.Дзен

ПРИМЕРЫ ХОРОШИХ ЗАПРОСОВ:
• HR: office meeting business team collaboration
• PR: media communication conference public relations
• Ремонт: construction workers building tools renovation

ФОРМАТ: слова через запятую без кавычек

Создай 2 РАЗНЫХ запроса: для Telegram и для Яндекс.Дзен

⸻
ФОРМАТ ОТВЕТА (ТОЧНО!):

Telegram-пост:
[Текст для Telegram]

Яндекс.Дзен-пост:
[Текст для Яндекс.Дзен]

Поисковый запрос для Telegram изображения:
[Запрос на английском, 4-7 слов через запятую, без кавычек]

Поисковый запрос для Яндекс.Дзен изображения:
[Запрос на английском, 4-7 слов через запятую, без кавычек]

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

    def clean_image_query(self, query):
        """Очищает поисковый запрос от кавычек и лишних символов"""
        if not query:
            return None
        
        # Убираем кавычки
        query = query.replace('"', '').replace("'", "")
        
        # Убираем лишние пробелы
        query = ' '.join(query.split())
        
        # Если запрос слишком длинный, берем первые 4-6 слов
        words = query.split()
        if len(words) > 6:
            query = ' '.join(words[:6])
        
        return query

    def get_random_pexels_key(self):
        """Возвращает случайный Pexels API ключ"""
        pexels_keys = [
            "563492ad6f9170000100000134567890abcdef1234567890abcdef",  # Демо-ключ 1
            "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c",  # Демо-ключ 2
            "563492ad6f91700001000001987654321fedcba0987654321fedcba",  # Демо-ключ 3
        ]
        return random.choice(pexels_keys)

    def search_pexels_image(self, search_query, theme):
        """Ищет изображение на Pexels"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                if not search_query:
                    search_query = random.choice(self.theme_keywords.get(theme, ["business"]))
                
                # Очищаем запрос
                search_query = self.clean_image_query(search_query)
                
                # Берем первое слово для упрощенного поиска
                words = search_query.split()
                if words:
                    simple_query = words[0]
                else:
                    simple_query = "business"
                
                # Пробуем разные ключи Pexels
                pexels_key = self.get_random_pexels_key()
                encoded_query = quote_plus(simple_query)
                url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=20&orientation=landscape"
                
                headers = {
                    "Authorization": pexels_key,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                logger.info(f"🔍 Pexels поиск (попытка {attempt + 1}): '{simple_query}'")
                
                response = session.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('photos') and len(data['photos']) > 0:
                        # Пробуем каждую фотографию пока не найдем валидную
                        for photo in data['photos']:
                            image_url = photo.get('src', {}).get('original', '')
                            if self.is_valid_image_url(image_url):
                                logger.info(f"✅ Найдено изображение на Pexels")
                                return image_url
                
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка Pexels (попытка {attempt + 1}): {e}")
                time.sleep(1)
        
        return None

    def search_unsplash_image(self, search_query, theme, max_attempts=10):
        """Ищет изображение на Unsplash с множественными попытками"""
        for attempt in range(max_attempts):
            try:
                if not search_query:
                    search_query = random.choice(self.theme_keywords.get(theme, ["business"]))
                
                # Очищаем запрос
                search_query = self.clean_image_query(search_query)
                
                # Берем разные слова для каждой попытки
                words = search_query.split()
                if words:
                    query_word = words[attempt % len(words)] if attempt < len(words) else words[0]
                else:
                    query_word = "business"
                
                # Разные размеры и стили для разнообразия
                sizes = ["1200x630", "1200x800", "1024x768", "800x600", "1600x900"]
                size = random.choice(sizes)
                
                # Разные стили Unsplash
                styles = ["", "featured/", "random/", "daily/"]
                style = random.choice(styles)
                
                # Уникальный параметр чтобы избежать кэширования
                timestamp = int(time.time()) + attempt
                
                unsplash_url = f"https://source.unsplash.com/{style}{size}/?{query_word}&sig={timestamp}"
                
                logger.info(f"🔍 Unsplash поиск (попытка {attempt + 1}): '{query_word}'")
                
                # Получаем изображение с редиректом
                response = session.get(unsplash_url, timeout=10, allow_redirects=True)
                
                if response.status_code == 200 and response.url:
                    image_url = response.url
                    
                    # Проверяем, что это действительно изображение
                    if self.is_valid_image_url(image_url):
                        logger.info(f"✅ Найдено изображение на Unsplash")
                        return image_url
                
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка Unsplash (попытка {attempt + 1}): {e}")
                time.sleep(1)
        
        return None

    def search_pixabay_image(self, search_query, theme, max_attempts=3):
        """Ищет изображение на Pixabay"""
        for attempt in range(max_attempts):
            try:
                if not search_query:
                    search_query = random.choice(self.theme_keywords.get(theme, ["business"]))
                
                # Очищаем запрос
                search_query = self.clean_image_query(search_query)
                
                # Берем первое слово
                words = search_query.split()
                if words:
                    simple_query = words[0]
                else:
                    simple_query = "business"
                
                # Pixabay API ключ (публичный демо-ключ)
                PIXABAY_API_KEY = "38020412-af8d8b3f2c15b5a7d9c2a8f7d"
                
                encoded_query = quote_plus(simple_query)
                url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={encoded_query}&image_type=photo&orientation=horizontal&per_page=30"
                
                logger.info(f"🔍 Pixabay поиск (попытка {attempt + 1}): '{simple_query}'")
                
                response = session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('hits') and len(data['hits']) > 0:
                        # Пробуем каждое изображение пока не найдем валидное
                        for hit in data['hits']:
                            image_url = hit.get('largeImageURL', '')
                            if self.is_valid_image_url(image_url):
                                logger.info(f"✅ Найдено изображение на Pixabay")
                                return image_url
                
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка Pixabay (попытка {attempt + 1}): {e}")
                time.sleep(1)
        
        return None

    def is_valid_image_url(self, url):
        """Проверяет, является ли URL валидным изображением"""
        if not url:
            return False
        
        # Проверяем что это не документ
        invalid_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx']
        if any(ext in url.lower() for ext in invalid_extensions):
            return False
        
        # Проверяем что это изображение
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff']
        if any(ext in url.lower() for ext in valid_extensions):
            return True
        
        # Проверяем по заголовкам HTTP если нет расширения
        try:
            response = session.head(url, timeout=5, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()
            return any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/webp', 'image/gif'])
        except:
            return False

    def find_image_anywhere(self, search_query, theme):
        """Ищет изображение ВЕЗДЕ пока не найдет"""
        logger.info(f"🔍 Начинаем поиск изображения для темы: {theme}")
        logger.info(f"🔍 Поисковый запрос: {search_query}")
        
        # Пробуем разные источники в случайном порядке
        sources = [
            ("Pexels", self.search_pexels_image),
            ("Unsplash", self.search_unsplash_image),
            ("Pixabay", self.search_pixabay_image)
        ]
        
        random.shuffle(sources)  # Меняем порядок источников
        
        for source_name, source_func in sources:
            logger.info(f"🔄 Пробуем {source_name}...")
            
            # Даем больше попыток для каждого источника
            if source_name == "Unsplash":
                image_url = source_func(search_query, theme, max_attempts=15)
            else:
                image_url = source_func(search_query, theme)
            
            if image_url and self.is_valid_image_url(image_url):
                logger.info(f"✅ Найдено валидное изображение на {source_name}")
                return image_url
        
        # Если не нашли по конкретному запросу, пробуем тематические запросы
        logger.warning("⚠️ Не нашли по запросу, пробуем тематические запросы...")
        theme_queries = self.theme_keywords.get(theme, ["business"])
        
        for query in theme_queries:
            logger.info(f"🔄 Пробуем тематический запрос: {query}")
            
            for source_name, source_func in sources:
                if source_name == "Unsplash":
                    image_url = source_func(query, theme, max_attempts=10)
                else:
                    image_url = source_func(query, theme)
                
                if image_url and self.is_valid_image_url(image_url):
                    logger.info(f"✅ Найдено изображение по тематическому запросу на {source_name}")
                    return image_url
        
        # Если все еще не нашли, используем базовые запросы
        logger.warning("⚠️ Не нашли по тематическим запросам, пробуем базовые...")
        basic_queries = ["business", "work", "office", "team", "meeting", "construction", "tools"]
        
        for query in basic_queries:
            logger.info(f"🔄 Пробуем базовый запрос: {query}")
            
            for source_name, source_func in sources:
                if source_name == "Unsplash":
                    image_url = source_func(query, theme, max_attempts=8)
                else:
                    image_url = source_func(query, theme)
                
                if image_url and self.is_valid_image_url(image_url):
                    logger.info(f"✅ Найдено изображение по базовому запросу на {source_name}")
                    return image_url
        
        # Если ВООБЩЕ ничего не нашли, пробуем генерацию через Unsplash
        logger.warning("⚠️ Все источники не сработали, пробуем последний шанс...")
        return self.get_last_chance_image(theme)

    def get_last_chance_image(self, theme):
        """Последний шанс - генерируем изображение через Unsplash"""
        try:
            # Базовые слова для каждой темы
            theme_words = {
                "HR и управление персоналом": ["office", "business", "team", "work"],
                "PR и коммуникации": ["communication", "media", "marketing", "conference"],
                "ремонт и строительство": ["construction", "tools", "building", "renovation"]
            }
            
            words = theme_words.get(theme, ["business", "work"])
            
            # Пробуем каждое слово много раз
            for word in words:
                for i in range(20):  # 20 попыток на каждое слово
                    try:
                        timestamp = int(time.time()) + i
                        size = random.choice(["1200x630", "1200x800", "1024x768"])
                        
                        unsplash_url = f"https://source.unsplash.com/featured/{size}/?{word}&sig={timestamp}"
                        
                        response = session.get(unsplash_url, timeout=10, allow_redirects=True)
                        
                        if response.status_code == 200 and response.url:
                            image_url = response.url
                            if self.is_valid_image_url(image_url):
                                logger.info(f"✅ Последний шанс сработал: {word}")
                                return image_url
                        
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка последнего шанса: {e}")
                        time.sleep(0.5)
            
            # Если даже это не сработало, пробуем абсолютно случайное
            logger.warning("⚠️ Даже последний шанс не сработал, пробуем случайное...")
            timestamp = int(time.time())
            return f"https://source.unsplash.com/random/1200x630/?sig={timestamp}"
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка последнего шанса: {e}")
            # Абсолютно последний вариант
            return "https://source.unsplash.com/random/1200x630/"

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

    def send_telegram_photo_with_retry(self, chat_id, text, image_url, max_attempts=10):
        """Отправляет фото в Telegram с множественными попытками"""
        for attempt in range(max_attempts):
            try:
                max_length = 1024
                
                if len(text) > max_length:
                    text = self.check_length_and_fix(text, max_length, True)
                
                # Проверяем URL изображения
                if not image_url or not image_url.startswith('http'):
                    logger.error(f"❌ Невалидный URL изображения: {image_url}")
                    return False
                
                # Проверяем что это действительно изображение
                if not self.is_valid_image_url(image_url):
                    logger.error(f"❌ Это не изображение: {image_url}")
                    return False
                
                # Очищаем URL от лишних параметров
                clean_url = image_url.split('?')[0] if '?' in image_url else image_url
                
                params = {
                    'chat_id': chat_id,
                    'photo': clean_url,
                    'caption': text,
                    'parse_mode': 'HTML',
                    'disable_notification': False
                }
                
                logger.info(f"📤 Отправляем фото в {chat_id} (попытка {attempt + 1}/{max_attempts})")
                logger.info(f"🖼️ Изображение: {clean_url[:80]}...")
                
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Фото отправлено в {chat_id}")
                    return True
                else:
                    logger.error(f"❌ Ошибка отправки фото: {response.status_code}")
                    if response.text:
                        logger.error(f"❌ Ответ сервера: {response.text[:100]}")
                    
                    # Если ошибка связана с изображением, пробуем другое
                    if "failed to get HTTP URL content" in response.text or "wrong type" in response.text:
                        logger.warning("🔄 Пробуем другое изображение...")
                        # Ищем новое изображение
                        new_image_url = self.find_image_anywhere("", self.current_theme)
                        if new_image_url and new_image_url != image_url:
                            image_url = new_image_url
                            time.sleep(2)
                            continue
                    
                    time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки фото (попытка {attempt + 1}): {e}")
                time.sleep(2)
        
        logger.error(f"❌ Не удалось отправить фото в {chat_id} после {max_attempts} попыток")
        return False

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def generate_and_send_posts(self):
        """Главная функция - ВСЕ посты ТОЛЬКО с изображениями, AI сам ищет"""
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
            
            logger.info("🖼️ AI ищет изображения САМ в интернете...")
            
            # AI сам ищет изображения - ищет пока не найдет
            logger.info("🔍 Ищем изображение для Telegram...")
            tg_image_url = self.find_image_anywhere(tg_image_query, self.current_theme)
            
            time.sleep(2)
            
            logger.info("🔍 Ищем изображение для Яндекс.Дзен...")
            zen_image_url = self.find_image_anywhere(zen_image_query, self.current_theme)
            
            logger.info("📤 Отправляем посты ТОЛЬКО с изображениями...")
            success_count = 0
            
            # Telegram - отправляем ТОЛЬКО с фото
            logger.info(f"  → Telegram: {MAIN_CHANNEL_ID}")
            if self.send_telegram_photo_with_retry(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            else:
                logger.error("❌ Не удалось отправить Telegram пост с изображением")
                return False
            
            time.sleep(2)
            
            # Яндекс.Дзен - отправляем ТОЛЬКО с фото
            logger.info(f"  → Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            if self.send_telegram_photo_with_retry(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            else:
                logger.error("❌ Не удалось отправить Яндекс.Дзен пост с изображением")
                return False
            
            if success_count == 2:
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "telegram_image_query": tg_image_query,
                    "zen_image_query": zen_image_query,
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
                logger.info(f"🎉 ВСЕ посты отправлены С ИЗОБРАЖЕНИЯМИ!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time} МСК")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Яндекс.Дзен: {zen_len} символов")
                logger.info(f"   🔍 Telegram запрос: {tg_image_query}")
                logger.info(f"   🔍 Яндекс.Дзен запрос: {zen_image_query}")
                logger.info("=" * 60)
                return True
            else:
                logger.error(f"❌ НЕ ВСЕ посты отправлены с изображениями: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ С ИЗОБРАЖЕНИЯМИ")
    print("=" * 80)
    print("📋 СТРОГИЕ ТРЕБОВАНИЯ:")
    print("   • ВСЕ посты ТОЛЬКО с изображениями")
    print("   • AI САМ ищет изображения в интернете")
    print("   • Ищет ВЕЗДЕ пока не найдет")
    print("   • НИКАКИХ заранее заготовленных изображений")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ ВЫПОЛНИЛ РАБОТУ!")
        print("   AI САМ нашел изображения в интернете")
        print("   ВСЕ посты отправлены С ИЗОБРАЖЕНИЯМИ")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ БОТ НЕ СМОГ ОТПРАВИТЬ ПОСТЫ С ИЗОБРАЖЕНИЯМИ!")
        print("   Проверьте логи для деталей")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
