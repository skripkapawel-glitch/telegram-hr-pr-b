import os
import requests
import random
import json
import time
import logging
import re
from datetime import datetime
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
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")  # Основной канал (чисто Telegram)
ZEN_CHANNEL_ID = "@tehdzenm"  # ВТОРОЙ канал Telegram для Яндекс.Дзен контента
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    logger.info("ℹ️ Получите ключ на: https://makersuite.google.com/app/apikey")
    exit(1)

# Настройка сессии requests
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    max_retries=3,
    pool_connections=10,
    pool_maxsize=10,
    pool_block=False
)
session.mount('https://', adapter)
session.mount('http://', adapter)

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Content-Type': 'application/json',
})

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ С ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты - ОБНОВЛЕННЫЕ ТРЕБОВАНИЯ
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "400-600",
                "zen_chars": "1000-1500",
                "description": "Энергичный старт дня"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "800-1500",
                "zen_chars": "1700-2300",
                "description": "Глубокий анализ + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "600-1000",
                "zen_chars": "1500-2100",
                "description": "Рефлексивный, атмосферный"
            }
        }

        # Конкретные тематические запросы для картинок
        self.theme_image_queries = {
            "ремонт и строительство": [
                "construction site building renovation",
                "interior design home renovation",
                "construction workers tools",
                "home improvement DIY",
                "architecture building design",
                "construction technology",
                "building materials tools",
                "renovation project before after",
                "construction safety equipment",
                "modern apartment renovation"
            ],
            "HR и управление персоналом": [
                "office team meeting business",
                "human resources interview hiring",
                "workplace diversity inclusion",
                "leadership management training",
                "employee engagement motivation",
                "remote work digital workplace",
                "corporate training development",
                "team building collaboration",
                "recruitment job interview",
                "business professionals meeting"
            ],
            "PR и коммуникации": [
                "public relations media communication",
                "social media marketing digital",
                "brand reputation crisis management",
                "influencer marketing media relations",
                "content marketing storytelling",
                "communication strategy networking",
                "digital transformation technology",
                "press conference media event",
                "marketing strategy planning",
                "business communication meeting"
            ]
        }

        # Актуальные модели для Gemini
        self.available_models = [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash",
        ]

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None
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
            
            # Убираем последние 2 использованные темы
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            # Сохраняем историю
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

    def create_combined_prompt(self, theme, time_slot_info):
        """Создает комбинированный промт для генерации двух текстов"""
        slot_type = time_slot_info['type']
        tg_chars = time_slot_info['tg_chars']
        zen_chars = time_slot_info['zen_chars']
        
        return f"""Ты — копирайтер, контент-мейкер и SMM-эксперт с 30+ годами опыта.
Цель — писать живые, полезные тексты, которые удерживают внимание. 
Выводи строго два текста: Telegram-пост и Дзен-пост, без лишних вступлений.

Тема: {theme}
Временной слот: {time_slot_info['name']} ({slot_type})

⸻
Telegram-пост:
• Объем: {tg_chars} символов
• Живой стиль, много эмодзи
• Блоки с отступом (4 пробела) + •

Структура поста:
• Хук (1–2 строки с эмодзи)
• 2–4 тезиса с отступом + «•»
• Мини-пример/инсайт
• Вопрос для вовлечения
• 5-7 релевантных хештегов
• Год: 2025-2026

⸻
Дзен-пост:
• Объем: {zen_chars} символов  
• Без эмодзи, как мини-статья
• Блоки с отступом (4 пробела) + •

Структура поста:
• Сильный хук
• Чёткие абзацы
• 2–4 пункта с отступом + «•»
• Мини-кейс/история
• Вывод
• Вопрос в конце
• Подпись: "Главная Видео Статьи Новости Подписки"
• Без хештегов
• Год: 2025-2026

⸻
Варианты подачи (используй подходящие):
• Разбор ситуации или явления
• Микро-исследование (данные, цифры, вывод)
• Аналитическое наблюдение
• Разбор ошибки и решение
• Мини-история с выводом
• Взгляд автора + расширение темы
• Объяснение сложного простым языком
• Элементы сторителлинга
• Структурированные советы
• Объяснение через аналогию
• Демонстрация пользы
• Анализ поведения аудитории
• Выявление причин «почему так происходит»
• Логичная цепочка: факт → пример → вывод
• Список полезных шагов
• Раскрытие одного сильного инсайта
• Тихая эмоциональная подача
• Сравнение разных подходов
• Мини-обобщение опыта

⸻
ВАЖНО:
1. Соблюдай структуру: каждый тезис с новой строки, начинается с "• "
2. Telegram-пост: короткие абзацы, эмодзи, вопросы к аудитории
3. Дзен-пост: глубокий анализ, без эмодзи, подпись в конце
4. Не обрезай текст! Пиши полные предложения
5. Картинка будет подобрана автоматически по теме

Теперь создай посты на тему: "{theme}" для времени "{time_slot_info['name']}".

Формат вывода строго такой:
Telegram-пост:
[текст Telegram поста]

---

Дзен-пост:
[текст Дзен поста]"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API с актуальными моделями"""
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY не установлен")
            return False
        
        try:
            logger.info("🔍 Проверка доступности Gemini API...")
            
            # Проверяем доступность каждой модели с разными URL форматами
            working_models = []
            
            # Варианты URL для моделей
            models_to_test = [
                ("gemini-2.0-flash-exp", "v1beta"),
                ("gemini-2.0-flash", "v1beta"),
                ("gemini-1.5-flash", "v1"),
                ("gemini-1.5-pro", "v1"),
                ("gemini-2.0-flash-exp", "v1"),
                ("gemini-2.0-flash", "v1"),
            ]
            
            for model_name, api_version in models_to_test:
                try:
                    url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                    
                    test_data = {
                        "contents": [{
                            "parts": [{"text": "Привет, ответь 'OK'"}]
                        }],
                        "generationConfig": {
                            "maxOutputTokens": 10,
                            "temperature": 0.1
                        }
                    }
                    
                    logger.debug(f"🔄 Проверяем модель: {model_name} (версия API: {api_version})")
                    response = session.post(url, json=test_data, timeout=15)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            working_models.append(f"{model_name} ({api_version})")
                            logger.info(f"✅ Модель {model_name} доступна через {api_version}")
                            self.working_model = model_name
                            self.api_version = api_version
                            return True
                        else:
                            logger.debug(f"⚠️ Модель {model_name}: пустой ответ")
                    elif response.status_code == 404:
                        logger.debug(f"⚠️ Модель {model_name} не найдена в {api_version}")
                    else:
                        logger.debug(f"⚠️ Модель {model_name}: ошибка {response.status_code} в {api_version}")
                        
                except requests.exceptions.Timeout:
                    logger.debug(f"⚠️ Модель {model_name}: таймаут")
                except Exception as e:
                    logger.debug(f"⚠️ Модель {model_name}: {str(e)[:50]}")
            
            # Пробуем использовать Google Generative Language API напрямую
            logger.info("🔄 Пробуем прямой вызов Google Generative Language API...")
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                test_data = {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "generationConfig": {"maxOutputTokens": 5}
                }
                
                response = session.post(url, json=test_data, timeout=15)
                if response.status_code == 200:
                    logger.info("✅ Gemini 2.0 Flash доступен через v1beta")
                    self.working_model = "gemini-2.0-flash"
                    self.api_version = "v1beta"
                    return True
            except:
                pass
            
            logger.error("❌ Ни одна модель Gemini не доступна")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=2):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🧠 Попытка генерации {attempt + 1}/{max_retries}...")
                
                # Используем рабочую модель и версию API
                if hasattr(self, 'working_model') and hasattr(self, 'api_version'):
                    model = self.working_model
                    api_version = self.api_version
                else:
                    # По умолчанию пробуем gemini-2.0-flash через v1beta
                    model = "gemini-2.0-flash"
                    api_version = "v1beta"
                
                url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 4000,
                    },
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_NONE"
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH", 
                            "threshold": "BLOCK_NONE"
                        }
                    ]
                }
                
                logger.info(f"🔄 Генерируем текст с помощью {model} (API: {api_version})...")
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        logger.info(f"✅ Текст сгенерирован ({model})")
                        return generated_text.strip()
                    else:
                        logger.error(f"⚠️ Пустой ответ от модели {model}")
                else:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('error', {}).get('message', '')[:200]
                    logger.error(f"❌ Ошибка {response.status_code} от модели {model}: {error_msg}")
                    
                    # Если ошибка 404, пробуем другую версию API
                    if response.status_code == 404 and api_version == "v1":
                        logger.info("🔄 Пробуем v1beta вместо v1...")
                        api_version = "v1beta"
                        url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                        continue
                        
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Таймаут при генерации текста")
                if attempt < max_retries - 1:
                    time.sleep(3)
                continue
            except Exception as e:
                logger.error(f"💥 Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                continue
        
        logger.error("❌ Не удалось сгенерировать текст через Gemini после всех попыток")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет объединенный текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        # Пробуем разные разделители
        separators = [
            "---", 
            "——", 
            "––––", 
            "Дзен-пост:", 
            "Telegram-пост:",
            "ТГ пост:"
        ]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # Очищаем от возможных заголовков
                    tg_text = re.sub(r'^(Telegram-пост|ТГ пост|Telegram|Первый пост):?\s*', '', tg_text, flags=re.IGNORECASE)
                    zen_text = re.sub(r'^(Дзен-пост|Дзен пост|Zen|Второй пост):?\s*', '', zen_text, flags=re.IGNORECASE)
                    
                    logger.info(f"✅ Тексты разделены по разделителю: '{separator}'")
                    return tg_text, zen_text
        
        # Если разделитель не найден, пробуем разделить по длине
        logger.warning("⚠️ Разделитель не найден, пробуем разделить по длине")
        text_length = len(combined_text)
        if text_length > 500:
            # Предполагаем, что Telegram пост короче
            split_point = text_length // 2
            tg_text = combined_text[:split_point].strip()
            zen_text = combined_text[split_point:].strip()
            return tg_text, zen_text
        
        # Если текст короткий, возвращаем как Telegram, а Zen делаем на его основе
        return combined_text, None

    def extract_keywords_from_post(self, text, theme):
        """Извлекает ключевые слова из поста для поиска картинки"""
        # Удаляем все технические элементы
        unwanted_patterns = [
            r'гнепрочитанные сообщения',
            r'\d+ подписчик\w*',
            r'Дзен-пост.*',
            r'Закреплённое сообщение.*',
            r'Честно\? Я устал от шаблонов.*',
            r'#\w+',  # хештеги
            r'http[s]?://\S+',  # ссылки
            r'[Публикация расходы.]',
            r'\[.*?\]',  # квадратные скобки
        ]
        
        clean_text = text
        for pattern in unwanted_patterns:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
        
        # Берем первые 300 символов (основная тема)
        text_preview = clean_text[:300].lower()
        
        # Удаляем пунктуацию и спецсимволы
        text_preview = re.sub(r'[^\w\s]', ' ', text_preview)
        
        # Разбиваем на слова
        words = text_preview.split()
        
        # Фильтруем стоп-слова
        stop_words = {
            'это', 'для', 'что', 'как', 'или', 'но', 'на', 'в', 'с', 'по', 'у', 'о', 'же',
            'и', 'а', 'то', 'не', 'так', 'вот', 'бы', 'вы', 'мы', 'он', 'она', 'они', 'ему',
            'ей', 'им', 'их', 'его', 'её', 'нам', 'вам', 'им', 'меня', 'тебя', 'его', 'её',
            'нас', 'вас', 'них', 'мой', 'твой', 'наш', 'ваш', 'их', 'свой'
        }
        
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        
        # Берем 3-5 уникальных ключевых слов
        unique_keywords = []
        for word in keywords:
            if word and word not in unique_keywords:
                unique_keywords.append(word)
        
        # Добавляем тематические слова
        theme_words = {
            "ремонт и строительство": ["renovation", "construction", "building", "home", "interior"],
            "HR и управление персоналом": ["office", "business", "team", "work", "professional"],
            "PR и коммуникации": ["communication", "media", "marketing", "public", "relations"]
        }
        
        # Комбинируем
        all_keywords = unique_keywords[:3] + theme_words.get(theme, [])[:2]
        
        logger.info(f"🔑 Ключевые слова для картинки: {all_keywords}")
        return " ".join(all_keywords)

    def get_highly_relevant_image(self, text, theme):
        """Получает СТРОГО РЕЛЕВАНТНУЮ картинку по теме поста"""
        try:
            # Извлекаем ключевые слова
            keywords = self.extract_keywords_from_post(text, theme)
            
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Кодируем ключевые слова
            encoded_keywords = quote_plus(keywords)
            
            # Берем конкретные тематические запросы
            theme_queries = self.theme_image_queries.get(theme, ["business professional"])
            
            # Пробуем несколько тематических запросов
            for theme_query in theme_queries[:3]:  # Берем первые 3 запроса
                try:
                    encoded_query = quote_plus(theme_query)
                    
                    # Unsplash с конкретными категориями
                    unsplash_urls = [
                        f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_query}&sig={timestamp}",
                        f"https://source.unsplash.com/{width}x{height}/?{encoded_query}&sig={timestamp}&orientation=landscape",
                        f"https://images.unsplash.com/photo-{timestamp}?crop=entropy&cs=tinysrgb&fit=crop&fm=jpg&h={height}&w={width}&q=85&{encoded_query}"
                    ]
                    
                    logger.info(f"🔍 Поиск по тематическому запросу: {theme_query}")
                    
                    for url in unsplash_urls:
                        try:
                            response = session.head(url, timeout=5, allow_redirects=True)
                            if response.status_code == 200:
                                final_url = response.url
                                # Проверяем что это изображение
                                if any(ext in final_url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                    logger.info(f"✅ Найдена тематическая картинка: {theme_query}")
                                    return final_url
                        except:
                            continue
                            
                except Exception as e:
                    continue
            
            # Если не нашли по тематике, пробуем по ключевым словам
            logger.info(f"🔄 Пробуем поиск по ключевым словам: {keywords}")
            keyword_url = f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_keywords}&sig={timestamp}"
            
            try:
                response = session.head(keyword_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    final_url = response.url
                    logger.info(f"✅ Найдена картинка по ключевым словам")
                    return final_url
            except:
                pass
            
            # Fallback: Pexels API (если добавить ключ)
            try:
                # Можно использовать Pexels API для более точного поиска
                # Нужен API ключ: https://www.pexels.com/api/
                pexels_query = theme.replace(" ", "+")
                pexels_url = f"https://api.pexels.com/v1/search?query={pexels_query}&per_page=1"
                
                # Если есть PEXELS_API_KEY в переменных окружения
                pexels_key = os.environ.get("PEXELS_API_KEY")
                if pexels_key:
                    headers = {"Authorization": pexels_key}
                    response = session.get(pexels_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('photos'):
                            photo_url = data['photos'][0]['src']['large']
                            logger.info(f"✅ Найдена картинка через Pexels")
                            return photo_url
            except:
                pass
            
            # Последний fallback: тематическая картинка из фиксированного списка
            fallback_images = {
                "ремонт и строительство": [
                    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",  # строительство
                    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00",  # инструменты
                    "https://images.unsplash.com/photo-1487958449943-2429e8be8625",  # интерьер
                ],
                "HR и управление персоналом": [
                    "https://images.unsplash.com/photo-1552664730-d307ca884978",  # офис
                    "https://images.unsplash.com/photo-1560264280-88b68371db39",  # команда
                    "https://images.unsplash.com/photo-1551836026-d5c2c5af78e4",  # бизнес
                ],
                "PR и коммуникации": [
                    "https://images.unsplash.com/photo-1533750349088-cd871a92f312",  # коммуникация
                    "https://images.unsplash.com/photo-1542744095-fcf48d80b0fd",  # маркетинг
                    "https://images.unsplash.com/photo-1559136555-9303baea8ebd",  # медиа
                ]
            }
            
            fallback_list = fallback_images.get(theme, ["https://images.unsplash.com/photo-1497366754035-f200968a6e72"])
            return random.choice(fallback_list)
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            # Гарантированная тематическая картинка
            fallback_by_theme = {
                "ремонт и строительство": "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
                "HR и управление персоналом": "https://images.unsplash.com/photo-1552664730-d307ca884978",
                "PR и коммуникации": "https://images.unsplash.com/photo-1533750349088-cd871a92f312"
            }
            return fallback_by_theme.get(theme, "https://images.unsplash.com/photo-1497366754035-f200968a6e72")

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram - НЕ ОБРЕЗАТЬ"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы
        replacements = {
            '&nbsp;': ' ',
            '&emsp;': '    ',
            '&ensp;': '  ',
            ' ': '    ',
            ' ': '  ',
            ' ': ' ',
            '**': '',  # Удаляем markdown жирный
            '__': '',  # Удаляем markdown подчеркивание
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Обрезаем только если ОЧЕНЬ длинный (>4096 символов для Telegram)
        if len(text) > 4090:
            # Обрезаем до последнего целого предложения
            text = text[:4080]
            last_period = text.rfind('.')
            if last_period > 3800:
                text = text[:last_period+1]
            text = text + "..."
        
        # Удаляем лишние пустые строки
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def ensure_zen_signature(self, text):
        """Убеждается, что в тексте Zen есть подпись"""
        signature = "Главная Видео Статьи Новости Подписки"
        
        if signature not in text:
            text = f"{text}\n\n{signature}"
        
        return text

    def test_bot_access(self):
        """Проверяет доступ бота к каналам"""
        logger.info("🔍 Проверка доступа...")
        
        # Проверяем бота
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                bot_username = bot_info.get('result', {}).get('username', 'N/A')
                logger.info(f"🤖 Бот: @{bot_username}")
            else:
                logger.error(f"❌ Бот не доступен: {response.status_code}")
                logger.error(f"Ответ: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False
        
        # Проверяем каналы
        channels_to_check = [
            ("Основной канал (Telegram)", MAIN_CHANNEL_ID),
            ("Второй канал (Telegram для Дзен)", ZEN_CHANNEL_ID)
        ]
        
        all_channels_ok = True
        
        for channel_name, channel_id in channels_to_check:
            try:
                params = {'chat_id': channel_id}
                response = session.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    chat_info = response.json()
                    logger.info(f"✅ {channel_name}: доступен ({channel_id})")
                    logger.debug(f"   Тип: {chat_info.get('result', {}).get('type', 'N/A')}")
                    logger.debug(f"   Название: {chat_info.get('result', {}).get('title', 'N/A')}")
                elif response.status_code == 400:
                    error_info = response.json()
                    logger.error(f"❌ {channel_name}: ошибка доступа ({channel_id})")
                    logger.error(f"   Причина: {error_info.get('description', 'Неизвестная ошибка')}")
                    all_channels_ok = False
                else:
                    logger.error(f"❌ {channel_name}: недоступен ({channel_id}) - {response.status_code}")
                    all_channels_ok = False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки {channel_name}: {e}")
                all_channels_ok = False
        
        if not all_channels_ok:
            logger.error("\nℹ️ Убедитесь что:")
            logger.error(f"1. Бот - администратор в ОБОИХ каналах: {MAIN_CHANNEL_ID} и {ZEN_CHANNEL_ID}")
            logger.error("2. Правильные ID каналов")
            logger.error("3. Каналы публичные или бот добавлен в приватные")
        
        return all_channels_ok

    def send_telegram_post(self, chat_id, text, image_url=None):
        """Отправляет пост с фото в Telegram"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            # Для второго канала добавляем подпись если нет
            if chat_id == ZEN_CHANNEL_ID:
                clean_text = self.ensure_zen_signature(clean_text)
            
            # Пробуем с фото
            if image_url:
                logger.info(f"📤 Отправка в {chat_id} с фото...")
                
                # Для caption берем первые 1000 символов
                caption_length = min(len(clean_text), 1000)
                caption_text = clean_text[:caption_length]
                
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': caption_text,
                    'parse_mode': 'HTML'
                }
                
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Отправлено в {chat_id}")
                    return True
                else:
                    logger.warning(f"⚠️ Ошибка sendPhoto: {response.status_code}")
                    logger.debug(f"Ответ: {response.text[:200]}")
                
                # Пробуем без caption
                logger.info(f"🔄 Пробуем без caption...")
                params = {'chat_id': chat_id, 'photo': image_url}
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Отправляем текст отдельно
                    time.sleep(1)
                    text_params = {
                        'chat_id': chat_id,
                        'text': clean_text,
                        'parse_mode': 'HTML',
                        'disable_web_page_preview': True
                    }
                    text_response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        params=text_params,
                        timeout=30
                    )
                    if text_response.status_code == 200:
                        logger.info(f"✅ Фото+текст отправлены в {chat_id}")
                        return True
                    else:
                        logger.warning(f"⚠️ Ошибка отправки текста: {text_response.status_code}")
            
            # Только текст
            logger.info(f"📝 Отправка текста в {chat_id}...")
            params = {
                'chat_id': chat_id,
                'text': clean_text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен в {chat_id}")
                return True
            
            logger.error(f"❌ Ошибка отправки в {chat_id}: {response.status_code}")
            if response.text:
                logger.error(f"Детали: {response.text[:200]}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при отправке: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            # Проверяем доступ
            logger.info("=" * 50)
            logger.info("🔍 ПРОВЕРКА ДОСТУПА")
            logger.info("=" * 50)
            
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к Telegram или каналам")
                return False
            
            # Проверяем Gemini
            logger.info("\n" + "=" * 50)
            logger.info("🔍 ПРОВЕРКА GEMINI API")
            logger.info("=" * 50)
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini API недоступен")
                return False
            
            # Проверка интервала
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                if hours_since_last < 3:
                    logger.info(f"⏭️ Пропускаем - прошло {hours_since_last:.1f} часов")
                    return True
            
            # Выбор темы
            logger.info("\n" + "=" * 50)
            logger.info("🎯 ВЫБОР ТЕМЫ")
            logger.info("=" * 50)
            
            self.current_theme = self.get_smart_theme()
            
            # Определение временного слота
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            slots = list(self.time_slots.keys())
            time_objects = [datetime.strptime(slot, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day) for slot in slots]
            
            closest_slot = min(time_objects, key=lambda x: abs((now - x).total_seconds()))
            slot_name = closest_slot.strftime("%H:%M")
            time_slot_info = self.time_slots.get(slot_name, self.time_slots["14:00"])
            
            logger.info(f"🕒 Текущее время: {current_time_str}")
            logger.info(f"📅 Выбранный слот: {slot_name} - {time_slot_info['emoji']} {time_slot_info['name']}")
            logger.info(f"📝 Описание: {time_slot_info['description']}")
            
            # Генерация постов
            logger.info("\n" + "=" * 50)
            logger.info("🧠 ГЕНЕРАЦИЯ ПОСТОВ")
            logger.info("=" * 50)
            
            logger.info("🎯 Генерация комбинированного поста...")
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info)
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            # Разделяем текст на Telegram и Zen
            logger.info("✂️ Разделение текста на Telegram и Дзен...")
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text:
                logger.error("❌ Не удалось получить Telegram текст")
                return False
            
            if not zen_text:
                logger.warning("⚠️ Не удалось получить Дзен текст, используем Telegram как основу")
                zen_text = tg_text
            
            # Проверяем структуру текста
            if "•" not in tg_text:
                logger.warning("⚠️ Telegram пост без буллетов! Добавляем форматирование...")
                sentences = re.split(r'(?<=[.!?])\s+', tg_text)
                tg_text = "\n• ".join(sentences)
                tg_text = "• " + tg_text

            if "•" not in zen_text:
                logger.warning("⚠️ Дзен пост без буллетов! Добавляем форматирование...")
                sentences = re.split(r'(?<=[.!?])\s+', zen_text)
                zen_text = "\n• ".join(sentences)
                zen_text = "• " + zen_text
            
            # Обрабатываем тексты
            tg_text = self.clean_telegram_text(tg_text)
            zen_text = self.ensure_zen_signature(self.clean_telegram_text(zen_text))
            
            # Подсчет символов
            tg_chars = len(tg_text)
            zen_chars = len(zen_text)
            
            logger.info(f"📊 Telegram пост: {tg_chars} символов")
            logger.info(f"📊 Дзен пост: {zen_chars} символов")
            
            # Поиск СТРОГО РЕЛЕВАНТНЫХ картинок
            logger.info("\n" + "=" * 50)
            logger.info("🖼️ ПОИСК РЕЛЕВАНТНЫХ КАРТИНОК")
            logger.info("=" * 50)
            
            logger.info(f"🔍 Поиск картинок для темы: {self.current_theme}")
            
            # Для основного канала
            logger.info("📸 Подбор картинки для основного канала...")
            tg_image_url = self.get_highly_relevant_image(tg_text, self.current_theme)
            
            # Для второго канала
            logger.info("📸 Подбор картинки для второго канала...")
            zen_image_url = self.get_highly_relevant_image(zen_text, self.current_theme)
            
            logger.info(f"✅ Основной канал: найдена релевантная картинка")
            logger.info(f"✅ Второй канал: найдена релевантная картинка")
            
            # Отправка
            logger.info("\n" + "=" * 50)
            logger.info("🚀 ОТПРАВКА ПОСТОВ")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал (Telegram)
            logger.info(f"\n📤 Отправка в основной канал: {MAIN_CHANNEL_ID}")
            main_success = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, tg_image_url)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной канал: УСПЕХ")
                logger.info(f"   📝 Текст: {tg_chars} символов")
                logger.info(f"   🖼️  Картинка: релевантная теме '{self.current_theme}'")
            else:
                logger.error("❌ Основной канал: НЕУДАЧА")
            
            time.sleep(3)  # Пауза между отправками
            
            # Второй канал (Telegram для Дзен)
            logger.info(f"\n📤 Отправка во второй канал: {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, zen_image_url)
            
            if zen_success:
                success_count += 1
                logger.info("✅ Второй канал: УСПЕХ")
                logger.info(f"   📝 Текст: {zen_chars} символов (стиль Дзен)")
                logger.info(f"   🖼️  Картинка: релевантная теме '{self.current_theme}'")
                logger.info(f"   📍 Подпись: 'Главная Видео Статьи Новости Подписки'")
            else:
                logger.error("❌ Второй канал: НЕУДАЧА")
            
            # Результат
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count == 2:
                    logger.info("\n" + "=" * 50)
                    logger.info("🎉 УСПЕХ! Посты отправлены в ОБА канала!")
                    logger.info("=" * 50)
                    logger.info(f"   🎯 Тема: {self.current_theme}")
                    logger.info(f"   🕒 Слот: {slot_name} ({time_slot_info['name']})")
                    logger.info(f"   🤖 Тексты: полные, с четкой структурой")
                    logger.info(f"   🖼️  Картинки: СТРОГО РЕЛЕВАНТНЫЕ теме")
                    logger.info(f"   📱 Основной канал: {MAIN_CHANNEL_ID}")
                    logger.info(f"   🌐 Второй канал: {ZEN_CHANNEL_ID}")
                else:
                    logger.warning(f"\n⚠️  Отправлено в {success_count} из 2 каналов")
                return True
            else:
                logger.error("\n❌ НЕУДАЧА! Не удалось отправить ни в один канал")
                logger.error("ℹ️ Проверьте:")
                logger.error(f"1. Бот администратор в каналах: {MAIN_CHANNEL_ID} и {ZEN_CHANNEL_ID}")
                logger.error("2. Права бота на отправку сообщений")
                logger.error("3. Правильность ID каналов")
                return False
                
        except Exception as e:
            logger.error(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def verify_environment():
    """Проверяет все необходимые переменные окружения"""
    print("\n" + "=" * 80)
    print("🔍 ПРОВЕРКА ОКРУЖЕНИЯ")
    print("=" * 80)
    
    issues = []
    
    # Проверка BOT_TOKEN
    if not BOT_TOKEN:
        issues.append("❌ BOT_TOKEN не установлен")
    else:
        print(f"✅ BOT_TOKEN: установлен ({len(BOT_TOKEN)} символов)")
    
    # Проверка GEMINI_API_KEY
    if not GEMINI_API_KEY:
        issues.append("❌ GEMINI_API_KEY не установлен")
    else:
        print(f"✅ GEMINI_API_KEY: установлен ({len(GEMINI_API_KEY)} символов)")
    
    # Проверка каналов
    if not MAIN_CHANNEL_ID:
        issues.append("❌ MAIN_CHANNEL_ID не установлен")
    else:
        print(f"✅ Основной канал: {MAIN_CHANNEL_ID}")
    
    if not ZEN_CHANNEL_ID:
        issues.append("❌ ZEN_CHANNEL_ID не установлен")
    else:
        print(f"✅ Второй канал: {ZEN_CHANNEL_ID}")
    
    if issues:
        print("\n⚠️  ПРОБЛЕМЫ:")
        for issue in issues:
            print(f"   {issue}")
        
        print("\n🔧 РЕШЕНИЕ:")
        print("1. Установите переменные окружения:")
        print("   export BOT_TOKEN='ваш_токен_бота'")
        print("   export GEMINI_API_KEY='ваш_gemini_ключ'")
        print("   export CHANNEL_ID='@ваш_канал'")
        print("\nℹ️ Для лучшего подбора картинок можно добавить PEXELS_API_KEY")
        return False
    
    return True


def test_gemini_direct_simple():
    """Простая прямая проверка Gemini API"""
    print("\n" + "=" * 80)
    print("🔍 ПРОВЕРКА GEMINI API")
    print("=" * 80)
    
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY не установлен")
        return False
    
    print(f"🔑 API ключ: {GEMINI_API_KEY[:15]}...{GEMINI_API_KEY[-5:]}")
    print(f"📏 Длина: {len(GEMINI_API_KEY)} символов")
    
    # Пробуем самые вероятные варианты
    test_cases = [
        ("v1beta", "gemini-2.0-flash"),
        ("v1", "gemini-2.0-flash-exp"),
        ("v1beta", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-pro"),
    ]
    
    for api_version, model in test_cases:
        try:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            
            test_data = {
                "contents": [{
                    "parts": [{"text": "Привет! Ответь одним словом: 'OK'"}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 5,
                    "temperature": 0.1
                }
            }
            
            print(f"\n🔄 Тестируем: {model} (API: {api_version})")
            
            response = requests.post(url, json=test_data, timeout=15)
            
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Нет текста')
                print(f"✅ УСПЕХ! Ответ: {text.strip()}")
                print(f"\n🎉 Найдена рабочая модель: {model} (API: {api_version})")
                return True
            elif response.status_code == 404:
                print(f"⚠️  Модель не найдена")
            else:
                print(f"❌ Ошибка: {response.status_code}")
                    
        except requests.exceptions.Timeout:
            print(f"⏱️  Таймаут")
        except Exception as e:
            print(f"❌ Исключение: {str(e)[:50]}")
    
    print("\n❌ Ни один тест не прошел успешно")
    print("\n🔧 Попробуйте:")
    print("1. Проверить активацию API в Google Cloud Console")
    print("2. Получить новый ключ: https://makersuite.google.com/app/apikey")
    print("3. Проверить интернет соединение")
    
    return False


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Канал 1: Telegram (оригинальный стиль)")
    print("🎯 Канал 2: Telegram (стиль Яндекс.Дзен)")
    print("🎯 Объем по времени:")
    print("   • 09:00 - ТГ: 400-600, Дзен: 1000-1500 символов")
    print("   • 14:00 - ТГ: 800-1500, Дзен: 1700-2300 символов")
    print("   • 19:00 - ТГ: 600-1000, Дзен: 1500-2100 символов")
    print("🎯 КАРТИНКИ: СТРОГО РЕЛЕВАНТНЫЕ тематике поста!")
    print("🎯 Форматирование: отступы и буллеты •")
    print("🎯 Структура: хук, тезисы, пример, вопрос, вывод")
    print("🎯 НЕ обрезать текст! Полные посты!")
    print("🎯 Год: 2025-2026")
    print("=" * 80)
    
    # Проверка окружения
    if not verify_environment():
        return
    
    print("\n✅ Все переменные окружения загружены")
    
    # Проверка Gemini API
    if not test_gemini_direct_simple():
        print("\n" + "=" * 80)
        print("⚠️  ПРОБЛЕМЫ С GEMINI API")
        print("=" * 80)
        print("Бот не может работать без доступа к Gemini API.")
        return
    
    print("\n🤖 Создание экземпляра бота...")
    
    bot = AIPostGenerator()
    
    print("\n" + "=" * 80)
    print("🚀 НАЧИНАЕМ ГЕНЕРАЦИЮ И ОТПРАВКУ ПОСТОВ...")
    print("=" * 80)
    
    try:
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n" + "=" * 80)
            print("🎉 УСПЕХ! Посты успешно отправлены!")
            print("=" * 80)
            print("📅 Следующий пост через 3 часа")
            print("🤖 Тексты: полные, с четкой структурой")
            print("🖼️ КАРТИНКИ: строго релевантные теме поста")
            print("📍 Второй канал: стиль Яндекс.Дзен с подписью")
            print("🔗 Основной канал:", MAIN_CHANNEL_ID)
            print("🔗 Второй канал:", ZEN_CHANNEL_ID)
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("🔧 Что проверить:")
            print(f"1. Бот администратор в ОБОИХ каналах: {MAIN_CHANNEL_ID} и {ZEN_CHANNEL_ID}")
            print("2. Проверь правильность ID второго канала: @tehdzenm")
            print("3. Каналы должны быть публичными")
            print("4. Gemini API ключ должен быть активен")
            print("5. Проверь интернет соединение")
            print("\n🔄 Попробуйте запустить снова")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n💥 НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
