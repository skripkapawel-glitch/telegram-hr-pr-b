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
                "tg_words": "700-1000",
                "zen_words": "1200-2000",
                "description": "Энергичный старт дня"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_words": "1500-2500",
                "zen_words": "2500-4000",
                "description": "Глубокий анализ + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_words": "900-1300",
                "zen_words": "1200-1600",
                "description": "Рефлексивный, атмосферный"
            }
        }

        # Более специфичные ключевые слова для ТЕМАТИЧЕСКИХ изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting business professionals collaboration",
                "human resources recruitment interview hiring process",
                "workplace diversity inclusion corporate culture",
                "leadership management team building training",
                "employee engagement motivation career development",
                "remote work digital workplace future of work",
                "corporate training skill development HR technology"
            ],
            "PR и коммуникации": [
                "public relations media communication press conference",
                "social media marketing digital strategy content creation",
                "brand reputation crisis management corporate communication",
                "influencer marketing media relations digital PR",
                "content marketing storytelling brand awareness",
                "communication strategy networking business relations",
                "digital transformation communication technology"
            ],
            "ремонт и строительство": [
                "construction site building renovation architecture",
                "interior design home renovation modern living space",
                "construction workers tools equipment building project",
                "home improvement DIY renovation before after",
                "architecture design sustainable building materials",
                "construction technology innovation smart home",
                "building restoration historic renovation project"
            ]
        }

        # Список работающих моделей Gemini
        self.gemini_models = [
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.0-pro-latest",
            "gemini-pro"
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

    def create_telegram_prompt(self, theme, time_slot_info):
        """Промт для Telegram поста по НОВОЙ структуре"""
        slot_type = time_slot_info['type']
        words_range = time_slot_info['tg_words']
        
        return f"""Создай пост для Telegram канала на тему: "{theme}"

СТРУКТУРА (обязательно соблюдать):

1. ХУК (1-2 строки):
   Текст текст текст. Хук хук хук — сразу цепляет.

2. ОСНОВНАЯ ЧАСТЬ (2-4 тезиса с отступом):
  • Тест тест тест — первый тезис с отступом.
  • Тест тест тест — второй тезис с отступом.
  • Тест тест тест — третий тезис с отступом.

3. МИНИ-ИНСАЙТ/ПРИМЕР:
   Текст текст текст. Короткое наблюдение или вывод.

4. ВОПРОС ДЛЯ ВОВЛЕЧЕНИЯ:
   Как вы думаете? Напишите в комментах.

ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
• Объем: {words_range} слов
• Год: 2025-2026
• Используй отступы и буллеты "•"
• Хештеги: добавь 5-7 релевантных хештегов в конце
• Стиль: живой, разговорный, энергичный
• Не используй HTML/Markdown, только чистый текст

ВАЖНО:
• Строго следуй структуре выше
• Используй отступы (пробелы) перед буллетами
• Каждый буллет с новой строки
• Сохраняй естественный, человеческий тон

Тема: {theme}"""

    def create_zen_prompt(self, theme, time_slot_info):
        """Промт для Яндекс.Дзен по НОВОЙ структуре"""
        slot_type = time_slot_info['type']
        words_range = time_slot_info['zen_words']
        
        return f"""Создай пост в стиле Яндекс.Дзен на тему: "{theme}"

СТРУКТУРА (обязательно соблюдать):

1. ХУК (сильный, цепляющий):
   Текст текст текст. Хук хук хук. Аудитория сразу должна захотеть читать дальше.

2. РАЗБОР / СОДЕРЖАНИЕ (короткий абзац):
   Текст текст текст.

3. ОСНОВНАЯ ЧАСТЬ (2-4 пункта с отступом):
  • Тест тест тест — важный пункт, оформленный структурно.
  • Тест тест тест — второй пункт с отступом.
  • Тест тест тест — третий пункт.

4. ИСТОРИЯ / МИНИ-КЕЙС:
   Текст текст текст. Небольшой сюжет для удержания внимания.

5. ВЫВОД:
   Текст текст текст. Чёткий итог.

6. ВОПРОС:
   Что думаете? Был ли у вас похожий опыт?

ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
• Объем: {words_range} слов
• Год: 2025-2026
• Используй отступы и буллеты "•"
• Чёткие абзацы между разделами
• В конце добавь: "Главная Видео Статьи Новости Подписки"
• Не используй хештеги
• Стиль: информативный, экспертный, но доступный
• Не используй HTML/Markdown, только чистый текст

ВАЖНО:
• Строго следуй структуре выше
• Используй отступы (пробелы) перед буллетами
• Каждый раздел с новой строки
• Сохраняй профессиональный, но человечный тон

Тема: {theme}"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY не установлен")
            return False
        
        try:
            logger.info("🔍 Проверка доступности Gemini API...")
            
            # Пробуем последнюю версию моделей
            test_models = [
                "gemini-1.5-flash-latest",
                "gemini-1.5-pro-latest",
                "gemini-1.0-pro-latest"
            ]
            
            for model in test_models:
                try:
                    test_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    test_data = {
                        "contents": [{
                            "parts": [{"text": "test"}]
                        }]
                    }
                    
                    response = session.post(test_url, json=test_data, timeout=15)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Gemini API доступен (модель: {model})")
                        return True
                    elif response.status_code == 400:
                        error_data = response.json()
                        logger.debug(f"⚠️ Модель {model}: {error_data.get('error', {}).get('message', 'Неизвестная ошибка')}")
                        continue
                    elif response.status_code == 404:
                        logger.debug(f"⚠️ Модель {model} не найдена, пробуем следующую...")
                        continue
                    else:
                        logger.debug(f"⚠️ Модель {model}: статус {response.status_code}")
                        continue
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"⚠️ Таймаут при проверке модели {model}")
                    continue
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка с моделью {model}: {str(e)[:50]}")
                    continue
            
            # Если ничего не сработало, пробуем базовый endpoint
            try:
                test_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
                test_data = {
                    "contents": [{
                        "parts": [{"text": "test"}]
                    }]
                }
                
                response = session.post(test_url, json=test_data, timeout=15)
                if response.status_code == 200:
                    logger.info("✅ Gemini API доступен (базовая модель)")
                    return True
            except:
                pass
            
            logger.error("❌ Все модели Gemini недоступны")
            logger.error("ℹ️ Проверьте:")
            logger.error("1. Правильность API ключа")
            logger.error("2. Доступ к интернету")
            logger.error("3. Активность API в Google Cloud Console")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini с повторами"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🧠 Попытка генерации {attempt + 1}/{max_retries}...")
                
                # Пробуем разные модели в порядке приоритета
                models_to_try = [
                    "gemini-1.5-flash-latest",
                    "gemini-1.5-pro-latest", 
                    "gemini-1.0-pro-latest",
                    "gemini-pro"
                ]
                
                for model in models_to_try:
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                        
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
                                },
                                {
                                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                    "threshold": "BLOCK_NONE"
                                },
                                {
                                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                    "threshold": "BLOCK_NONE"
                                }
                            ]
                        }
                        
                        logger.debug(f"🔄 Пробуем модель {model}...")
                        response = session.post(url, json=data, timeout=30)
                        
                        if response.status_code == 200:
                            result = response.json()
                            if 'candidates' in result and result['candidates']:
                                generated_text = result['candidates'][0]['content']['parts'][0]['text']
                                logger.info(f"✅ Текст сгенерирован ({model})")
                                return generated_text.strip()
                        else:
                            error_data = response.json() if response.content else {}
                            logger.debug(f"⚠️ Ошибка {response.status_code} для {model}: {error_data.get('error', {}).get('message', '')[:100]}")
                            
                    except requests.exceptions.Timeout:
                        logger.warning(f"⚠️ Таймаут для модели {model}")
                        continue
                    except Exception as model_error:
                        logger.debug(f"⚠️ Ошибка с моделью {model}: {str(model_error)[:50]}")
                        continue
                
                # Если все модели не сработали в этой попытке
                if attempt < max_retries - 1:
                    wait_time = 2 * (attempt + 1)  # Экспоненциальная задержка
                    logger.warning(f"🔄 Все модели не ответили, ждем {wait_time} сек...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"💥 Критическая ошибка генерации (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                continue
        
        logger.error("❌ Не удалось сгенерировать текст через Gemini после всех попыток")
        return None

    def extract_keywords_from_text(self, text, theme):
        """Извлекает ключевые слова из текста для поиска релевантной картинки"""
        # Сначала используем тематические ключевые слова
        theme_keywords = self.theme_keywords.get(theme, [""])[0].split()
        
        # Добавляем общие слова по теме
        common_words = {
            "HR и управление персоналом": ["office", "business", "team", "work", "professional"],
            "PR и коммуникации": ["media", "communication", "marketing", "digital", "brand"],
            "ремонт и строительство": ["construction", "building", "design", "home", "renovation"]
        }
        
        # Получаем слова из текста (первые 100 символов для релевантности)
        text_preview = text[:200].lower()
        
        # Ищем существительные и важные слова
        important_words = []
        for word in text_preview.split():
            if len(word) > 4 and word.isalpha():
                important_words.append(word)
        
        # Комбинируем ключевые слова
        all_keywords = theme_keywords[:3] + common_words.get(theme, [])[:3] + important_words[:4]
        
        # Удаляем дубликаты и оставляем уникальные
        unique_keywords = []
        for word in all_keywords:
            if word and word not in unique_keywords:
                unique_keywords.append(word)
        
        # Берем до 5 ключевых слов
        selected_keywords = unique_keywords[:5]
        
        logger.info(f"🔑 Ключевые слова для картинки: {selected_keywords}")
        return " ".join(selected_keywords)

    def get_relevant_image_url(self, text, theme):
        """Получает РЕЛЕВАНТНУЮ картинку под текст поста"""
        try:
            # Извлекаем ключевые слова из текста
            keywords = self.extract_keywords_from_text(text, theme)
            
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Кодируем ключевые слова
            encoded_keywords = quote_plus(keywords)
            
            # Пробуем Unsplash с конкретными ключевыми словами
            unsplash_urls = [
                f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_keywords}&sig={timestamp}&fit=crop&face",
                f"https://source.unsplash.com/{width}x{height}/?{encoded_keywords},professional,modern&sig={timestamp}",
                f"https://source.unsplash.com/random/{width}x{height}/?{encoded_keywords}&sig={timestamp}"
            ]
            
            logger.info(f"🖼️ Поиск РЕЛЕВАНТНОЙ картинки: {keywords}")
            
            for url in unsplash_urls:
                try:
                    response = session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        final_url = response.url
                        # Проверяем, что это изображение
                        if any(ext in final_url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            logger.info(f"✅ Найдена релевантная картинка для темы '{theme}'")
                            return final_url
                except Exception as e:
                    continue
            
            # Если не нашли релевантную, используем тематическую
            logger.info("🔄 Используем тематическую картинку")
            theme_keywords_list = self.theme_keywords.get(theme, ["business professional"])
            theme_keyword = random.choice(theme_keywords_list)
            encoded_theme = quote_plus(theme_keyword)
            
            fallback_url = f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_theme}&sig={timestamp}"
            
            try:
                response = session.head(fallback_url, timeout=3, allow_redirects=True)
                if response.status_code == 200:
                    return response.url
            except:
                pass
            
            # Последний fallback
            return f"https://picsum.photos/{width}/{height}?random={timestamp}&grayscale"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/1200/630?random={int(time.time())}"

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
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
            '*': '•',  # Заменяем звездочки на буллеты
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Удаляем лишние пустые строки
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        # Обрезаем если слишком длинный
        if len(text) > 4096:
            text = text[:4000] + "..."
        
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
                
                # Сначала пробуем отправить фото с текстом
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': clean_text[:1024],
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
                logger.error("ℹ️ Проверьте API ключ и доступ к интернету")
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
            
            logger.info("📱 Генерация Telegram поста...")
            tg_prompt = self.create_telegram_prompt(self.current_theme, time_slot_info)
            tg_text = self.generate_with_gemini(tg_prompt)
            
            if not tg_text:
                logger.error("❌ Не удалось сгенерировать Telegram пост")
                return False
            
            logger.info("🌐 Генерация поста для второго канала (стиль Дзен)...")
            zen_prompt = self.create_zen_prompt(self.current_theme, time_slot_info)
            zen_text = self.generate_with_gemini(zen_prompt)
            
            if not zen_text:
                logger.error("❌ Не удалось сгенерировать пост для второго канала")
                return False
            
            # Обрабатываем тексты
            tg_text = self.clean_telegram_text(tg_text)
            zen_text = self.ensure_zen_signature(self.clean_telegram_text(zen_text))
            
            # Подсчет слов
            tg_words = len(tg_text.split())
            zen_words = len(zen_text.split())
            
            logger.info(f"📊 Telegram пост: {tg_words} слов ({len(tg_text)} знаков)")
            logger.info(f"📊 Второй канал (стиль Дзен): {zen_words} слов ({len(zen_text)} знаков)")
            
            # Поиск РЕЛЕВАНТНЫХ картинок под текст
            logger.info("\n" + "=" * 50)
            logger.info("🖼️ ПОИСК КАРТИНОК")
            logger.info("=" * 50)
            
            logger.info("🔍 Поиск РЕЛЕВАНТНЫХ картинок под текст...")
            
            # Для основного канала
            tg_image_url = self.get_relevant_image_url(tg_text, self.current_theme)
            
            # Для второго канала
            zen_image_url = self.get_relevant_image_url(zen_text, self.current_theme)
            
            logger.info(f"📸 Основной канал: картинка подобрана под тему '{self.current_theme}'")
            logger.info(f"📸 Второй канал: картинка подобрана под тему '{self.current_theme}'")
            
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
                logger.info(f"   📝 Текст: {tg_words} слов")
                logger.info(f"   🖼️  Картинка: релевантная теме")
            else:
                logger.error("❌ Основной канал: НЕУДАЧА")
            
            time.sleep(3)  # Пауза между отправками
            
            # Второй канал (Telegram для Дзен)
            logger.info(f"\n📤 Отправка во второй канал: {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, zen_image_url)
            
            if zen_success:
                success_count += 1
                logger.info("✅ Второй канал: УСПЕХ")
                logger.info(f"   📝 Текст: {zen_words} слов (стиль Дзен)")
                logger.info(f"   🖼️  Картинка: релевантная теме")
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
                    logger.info(f"   🤖 Тексты: сгенерированы AI")
                    logger.info(f"   🖼️  Картинки: релевантные теме")
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
        
        print("\n🔧 РЕШЕНИЯ:")
        print("1. Установите переменные окружения:")
        print("   export BOT_TOKEN='ваш_токен_бота'")
        print("   export GEMINI_API_KEY='ваш_gemini_ключ'")
        print("   export CHANNEL_ID='@ваш_канал'")
        print("\n2. Или создайте файл .env с этими переменными")
        print("\n3. Для Gemini API ключа:")
        print("   - Получите ключ: https://makersuite.google.com/app/apikey")
        print("   - Убедитесь, что API активирован в Google Cloud Console")
        return False
    
    return True


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Канал 1: Telegram (оригинальный стиль)")
    print("🎯 Канал 2: Telegram (стиль Яндекс.Дзен)")
    print("🎯 Объем: утро/день/вечер с разными объемами")
    print("🎯 Картинки: РЕЛЕВАНТНЫЕ тексту поста")
    print("🎯 Форматирование: отступы и буллеты •")
    print("🎯 Год: 2025-2026")
    print("🎯 Хештеги: автоматически генерируются AI")
    print("=" * 80)
    
    # Проверка окружения
    if not verify_environment():
        return
    
    print("\n✅ Все переменные окружения загружены")
    print("🤖 Создание экземпляра бота...")
    
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
            print("🤖 Все тексты сгенерированы AI")
            print("🖼️ Картинки РЕЛЕВАНТНЫЕ тексту поста")
            print("🏗️  Структура: Хук → Тезисы → Инсайт → Вопрос")
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
