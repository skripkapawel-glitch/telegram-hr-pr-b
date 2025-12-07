import os
import requests
import random
import json
import time
import logging
import re
import sys
from datetime import datetime, timedelta
import urllib3
from urllib.parse import quote

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
})

print("=" * 80)
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ (Telegram + Яндекс.Дзен)")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"🖼️ Источник изображений: Unsplash (прямые ссылки на изображения)")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("=" * 80)

# Список доступных моделей Gemini с приоритетами
AVAILABLE_MODELS = [
    "gemini-2.0-flash",                # Базовая стабильная
    "gemma-3-27b-it",                  # Для коротких текстов
]

# Убираем модели, которые не работают с generateContent
# gemini-2.5-flash-preview-04-17 и gemini-2.5-pro-exp-03-25 дают 404 ошибку

class ModelRotator:
    def __init__(self):
        self.models = AVAILABLE_MODELS.copy()
        self.current_index = 0
        self.model_stats = {model: {"calls": 0, "errors": 0, "last_used": 0} for model in self.models}
        
    def get_next_model(self, retry_count=0):
        """Возвращает следующую модель для использования с учетом ошибок"""
        # Если это повторная попытка, берем следующую модель
        if retry_count > 0:
            self.current_index = (self.current_index + 1) % len(self.models)
        
        current_model = self.models[self.current_index]
        
        # Проверяем, не было ли много ошибок у этой модели
        if self.model_stats[current_model]["errors"] >= 3:
            logger.warning(f"⚠️ Модель {current_model} имеет {self.model_stats[current_model]['errors']} ошибок, пропускаем")
            self.current_index = (self.current_index + 1) % len(self.models)
            return self.get_next_model(retry_count)
        
        # Обновляем статистику
        self.model_stats[current_model]["calls"] += 1
        self.model_stats[current_model]["last_used"] = time.time()
        
        return current_model
    
    def report_error(self, model_name):
        """Сообщает об ошибке для модели"""
        if model_name in self.model_stats:
            self.model_stats[model_name]["errors"] += 1
            
    def report_success(self, model_name):
        """Сбрасывает счетчик ошибок при успехе"""
        if model_name in self.model_stats:
            self.model_stats[model_name]["errors"] = max(0, self.model_stats[model_name]["errors"] - 1)

class UnsplashImageFinder:
    """Класс для работы с Unsplash - ФИКСИРОВАННАЯ ВЕРСИЯ"""
    
    # Гарантированные изображения Unsplash (прямые ссылки на JPG)
    GUARANTEED_IMAGES = {
        "HR и управление персоналом": [
            "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=630&fit=crop",  # Бизнес встреча
            "https://images.unsplash.com/photo-1551836026-d5c2c5af78e4?w=1200&h=630&fit=crop",  # Команда
            "https://images.unsplash.com/photo-1573164713988-8665fc963095?w=1200&h=630&fit=crop",  # Офис
            "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=1200&h=630&fit=crop",  # Планирование
            "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=1200&h=630&fit=crop",  # Рукопожатие
        ],
        "PR и коммуникации": [
            "https://images.unsplash.com/photo-1559136555-9303baea8ebd?w=1200&h=630&fit=crop",  # Коммуникация
            "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&h=630&fit=crop",  # Маркетинг
            "https://images.unsplash.com/photo-1551836036-2c6d0c2c1c9d?w=1200&h=630&fit=crop",  # Соцсети
            "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=630&fit=crop",  # Презентация
        ],
        "ремонт и строительство": [
            "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=1200&h=630&fit=crop",  # Стройка
            "https://images.unsplash.com/photo-1503387769-00a112127ca0?w=1200&h=630&fit=crop",  # Инструменты
            "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1200&h=630&fit=crop",  # Ремонт
            "https://images.unsplash.com/photo-1504309092620-4d0ec726efa4?w=1200&h=630&fit=crop",  # Строители
        ]
    }
    
    # Простые ключевые слова без пробелов
    SIMPLE_KEYWORDS = {
        "HR и управление персоналом": ["office", "team", "business", "meeting", "work"],
        "PR и коммуникации": ["communication", "media", "marketing", "social", "network"],
        "ремонт и строительство": ["construction", "tools", "building", "repair", "renovation"]
    }
    
    @staticmethod
    def get_direct_unsplash_url(keywords=None, theme=None):
        """
        Получает прямую ссылку на изображение Unsplash
        НЕ используем source.unsplash.com - он возвращает HTML
        """
        try:
            # Используем простые гарантированные изображения
            if theme and theme in UnsplashImageFinder.GUARANTEED_IMAGES:
                images = UnsplashImageFinder.GUARANTEED_IMAGES[theme]
                selected = random.choice(images)
                # Добавляем timestamp для уникальности
                timestamp = int(time.time())
                return f"{selected}&_t={timestamp}"
            
            # Fallback на конкретное изображение
            fallback = "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=630&fit=crop"
            timestamp = int(time.time())
            return f"{fallback}&_t={timestamp}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения: {e}")
            # Абсолютный fallback
            return "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=630&fit=crop"
    
    @staticmethod
    def clean_query_for_telegram(query):
        """Очищает запрос для Telegram (убирает пробелы, оставляет только слова через запятую)"""
        if not query:
            return None
        
        # Убираем все кроме букв и запятых
        query = re.sub(r'[^a-zA-Z, ]', '', query)
        
        # Заменяем пробелы на запятые
        query = query.replace(' ', ',')
        
        # Убираем лишние запятые
        query = re.sub(r',+', ',', query)
        query = query.strip(',')
        
        # Берем только первые 3 слова
        words = query.split(',')
        words = [w.strip() for w in words if w.strip()]
        
        if len(words) > 3:
            words = words[:3]
        
        return ','.join(words) if words else None

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.prohibited_topics = ["удаленная работа", "гибридная работа", "оформление только по ТК"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.model_rotator = ModelRotator()
        self.image_finder = UnsplashImageFinder()
        
        # Настройки для разных временных слотов
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
        
        # Настройки для разных моделей
        self.model_configs = {
            "gemini-2.0-flash": {
                "max_tokens": 3500,
                "temperature": 0.85,
                "description": "Базовая стабильная модель"
            },
            "gemma-3-27b-it": {
                "max_tokens": 2000,
                "temperature": 0.8,
                "description": "Легкая модель для коротких текстов"
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
                "model_usage": {}
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": [],
                "model_usage": {}
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с учетом истории"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            # Убираем последние 2 темы, чтобы не повторяться
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
ФОРМАТ ОТВЕТА (ТОЧНО!):

Telegram-пост:
[Текст для Telegram]

Яндекс.Дзен-пост:
[Текст для Яндекс.Дзен]

⸻
НАЧИНАЙ ГЕНЕРАЦИЮ СЕЙЧАС!"""

        return prompt

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API через разные модели"""
        test_models = ["gemini-2.0-flash", "gemma-3-27b-it"]
        
        for model in test_models:
            try:
                logger.info(f"🔍 Тестируем доступ к Gemini API (модель: {model})...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                
                test_data = {
                    "contents": [{"parts": [{"text": "Тест. Ответь одним словом: OK"}]}],
                    "generationConfig": {"maxOutputTokens": 5}
                }
                
                response = session.post(url, json=test_data, timeout=15)
                
                if response.status_code == 200:
                    logger.info(f"✅ Модель {model} доступна!")
                    return True
                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate limit для {model}, пробуем следующую модель...")
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"⚠️ Модель {model} недоступна: {response.status_code}")
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки модели {model}: {str(e)}")
                time.sleep(2)
                continue
        
        logger.error("❌ Ни одна модель Gemini не доступна")
        return False

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            logger.info("🔍 Тестируем доступ к Telegram API...")
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Telegram доступен! Бот: @{result['result']['username']}")
                return True
            else:
                logger.error(f"❌ Telegram ошибка: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=5):
        """Генерирует текст через Gemini с ротацией моделей"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Выбираем модель
                current_model = self.model_rotator.get_next_model(retry_count)
                config = self.model_configs.get(current_model, {
                    "max_tokens": 3500,
                    "temperature": 0.85
                })
                
                logger.info(f"🔄 Генерируем текст (попытка {retry_count + 1}/{max_retries}, модель: {current_model})...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": config["temperature"],
                        "maxOutputTokens": config["max_tokens"],
                        "topP": 0.92,
                        "topK": 35
                    }
                }
                
                # Добавляем небольшую задержку между запросами
                time.sleep(random.uniform(1, 2))
                
                response = session.post(url, json=data, timeout=90)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        self.model_rotator.report_success(current_model)
                        
                        # Сохраняем статистику использования моделей
                        if "model_usage" not in self.post_history:
                            self.post_history["model_usage"] = {}
                        
                        if current_model not in self.post_history["model_usage"]:
                            self.post_history["model_usage"][current_model] = 0
                        
                        self.post_history["model_usage"][current_model] += 1
                        self.save_post_history()
                        
                        total_length = len(generated_text)
                        logger.info(f"📄 Сгенерировано {total_length} символов моделью {current_model}")
                        
                        if "Telegram-пост:" in generated_text and "Яндекс.Дзен-пост:" in generated_text:
                            logger.info(f"✅ Текст сгенерирован успешно")
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Нет структуры в ответе от {current_model}, пробуем снова...")
                            self.model_rotator.report_error(current_model)
                            retry_count += 1
                            continue
                    else:
                        logger.warning(f"⚠️ {current_model} не вернул текст, пробуем другую модель...")
                        self.model_rotator.report_error(current_model)
                        retry_count += 1
                        continue
                        
                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate limit для {current_model}, пробуем следующую модель...")
                    self.model_rotator.report_error(current_model)
                    retry_count += 1
                    time.sleep(2)
                    continue
                    
                else:
                    logger.error(f"❌ Ошибка {response.status_code} для {current_model}: {response.text[:200]}")
                    self.model_rotator.report_error(current_model)
                    retry_count += 1
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Ошибка генерации моделью {current_model}: {str(e)[:100]}")
                self.model_rotator.report_error(current_model)
                retry_count += 1
                time.sleep(2)
                continue
        
        logger.error("❌ Не удалось сгенерировать текст после всех попыток со всеми моделями")
        return None

    def split_text_and_queries(self, combined_text):
        """Разделяет текст на Telegram и Яндекс.Дзен"""
        if not combined_text:
            return None, None, None, None
        
        # Ищем посты
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Яндекс.Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Яндекс.Дзен-пост:", "").strip()
            
            return tg_text, zen_text, None, None
        
        return None, None, None, None

    def get_image_for_post(self, theme, post_type="telegram"):
        """Получает гарантированное изображение для поста"""
        try:
            # Используем наш класс с гарантированными изображениями
            image_url = self.image_finder.get_direct_unsplash_url(theme=theme)
            
            logger.info(f"🖼️ Получаем изображение для {post_type.upper()} (тема: {theme})")
            logger.info(f"   🔗 URL: {image_url[:80]}...")
            
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения: {e}")
            # Абсолютный fallback
            return "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=630&fit=crop"

    def is_valid_image_url(self, url):
        """Проверяет валидность URL изображения"""
        if not url:
            return False
        
        # Проверяем, что это прямой URL на изображение Unsplash
        if 'images.unsplash.com/photo-' in url and ('?w=' in url or '&w=' in url):
            return True
        
        # Проверяем расширение
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        if any(url.lower().endswith(ext) for ext in image_extensions):
            return True
        
        return False

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
        text_lower = text.lower()
        
        # Проверяем на историю
        is_story = any(keyword in text_lower for keyword in [
            'история', 'случай', 'пример', 'ситуация', 'опыт',
            'однажды', 'как-то раз', 'в один день', 'недавно'
        ])
        
        # Форматируем
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Если это список (перечисление) и НЕ история
            if line.startswith('•') and not is_story:
                # Убираем эмодзи из пунктов списка
                line = re.sub(r'^•\s*[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line)
                formatted_lines.append("            • " + line[1:].strip())
            # Если история с точками - убираем точки
            elif line.startswith('•') and is_story:
                line_content = line[1:].strip()
                line_content = re.sub(r'^[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line_content)
                formatted_lines.append(line_content)
            else:
                formatted_lines.append(line)
        
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
            # Находим последнее хорошее место для обрезка
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

    def send_telegram_photo_with_retry(self, chat_id, text, image_url, max_attempts=3):
        """Отправляет фото в Telegram с повторными попытками"""
        for attempt in range(max_attempts):
            try:
                max_length = 1024
                
                if len(text) > max_length:
                    text = self.check_length_and_fix(text, max_length, True)
                
                # Проверяем URL изображения
                if not image_url or not image_url.startswith('http'):
                    logger.error(f"❌ Невалидный URL изображения: {image_url}")
                    return False
                
                # Убеждаемся, что это прямой URL на изображение
                clean_url = image_url
                
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
                    
                    # Если ошибка с изображением, пробуем другое
                    if "wrong type of the web page content" in response.text:
                        logger.warning("⚠️ Telegram не принимает URL, пробуем другое изображение...")
                        new_image_url = self.get_image_for_post(self.current_theme)
                        image_url = new_image_url
                    
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки фото (попытка {attempt + 1}): {e}")
                time.sleep(1)
        
        logger.error(f"❌ Не удалось отправить фото в {chat_id} после {max_attempts} попыток")
        return False

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def generate_and_send_posts(self):
        """Главная функция - генерация и отправка постов"""
        try:
            logger.info("🔍 Проверяем доступ к сервисам...")
            
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            # Проверяем Gemini через ротацию моделей
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен.")
                logger.error("  1. Проверьте API ключ в переменной окружения GEMINI_API_KEY")
                logger.error("  2. Убедитесь что ключ активирован на https://makersuite.google.com/app/apikey")
                logger.error("  3. Возможно, превышена квота - подождите некоторое время")
                return False
            
            now = self.get_moscow_time()
            
            # Определяем временной слот
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
            
            # Генерация промпта
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info, time_key)
            logger.info(f"📝 Длина промпта: {len(combined_prompt)} символов")
            
            # Генерация текста через Gemini с ротацией моделей
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            # Разделение текстов
            tg_text, zen_text, tg_image_query, zen_image_query = self.split_text_and_queries(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Форматирование текстов
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            logger.info(f"📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
            logger.info(f"📊 Яндекс.Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
            
            # Проверка длины
            if tg_len > tg_max:
                tg_text = self.check_length_and_fix(tg_text, tg_max, True)
                tg_len = len(tg_text)
                logger.info(f"📊 Telegram после коррекции: {tg_len} символов")
            
            if zen_len > zen_max:
                zen_text = self.check_length_and_fix(zen_text, zen_max, False)
                zen_len = len(zen_text)
                logger.info(f"📊 Яндекс.Дзен после коррекции: {zen_len} символов")
            
            # Получение изображений (гарантированные)
            logger.info("🖼️ Получаем гарантированные изображения из Unsplash...")
            
            logger.info("🔍 Изображение для Telegram...")
            tg_image_url = self.get_image_for_post(self.current_theme, "telegram")
            
            time.sleep(1)  # Небольшая пауза между запросами
            
            logger.info("🔍 Изображение для Яндекс.Дзен...")
            zen_image_url = self.get_image_for_post(self.current_theme, "zen")
            
            # Отправка постов
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Telegram
            logger.info(f"  → Telegram: {MAIN_CHANNEL_ID}")
            if self.send_telegram_photo_with_retry(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            else:
                logger.error("❌ Не удалось отправить Telegram пост")
                return False
            
            time.sleep(2)  # Пауза между отправками
            
            # Яндекс.Дзен
            logger.info(f"  → Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            if self.send_telegram_photo_with_retry(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            else:
                logger.error("❌ Не удалось отправить Яндекс.Дзен пост")
                return False
            
            if success_count == 2:
                # Сохраняем историю
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "telegram_image_url": tg_image_url[:100] if tg_image_url else None,
                    "zen_image_url": zen_image_url[:100] if zen_image_url else None,
                    "time": now.strftime("%H:%M:%S"),
                    "model_used": list(self.post_history.get("model_usage", {}).keys())[-1] if self.post_history.get("model_usage") else None
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.post_history["last_post_time"] = now.isoformat()
                self.save_post_history()
                
                logger.info("\n" + "=" * 60)
                logger.info(f"🎉 ВСЕ посты отправлены!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time} МСК")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Яндекс.Дзен: {zen_len} символов")
                logger.info(f"   🖼️ Изображения: Гарантированные Unsplash")
                logger.info("=" * 60)
                return True
            else:
                logger.error(f"❌ Не все посты отправлены: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ (исправленная версия)")
    print("=" * 80)
    print("📋 ОСОБЕННОСТИ:")
    print("   • Только рабочие модели Gemini: gemini-2.0-flash и gemma-3-27b-it")
    print("   • Гарантированные изображения Unsplash (прямые ссылки)")
    print("   • НЕТ проблем с 'wrong type of the web page content'")
    print("   • Автоматическое восстановление при ошибках")
    print("=" * 80)
    
    # Быстрая проверка доступа перед запуском
    print("\n🔍 Проверка доступа к сервисам...")
    
    bot = AIPostGenerator()
    
    # Тестируем доступ
    print("  1. Проверяем Telegram...")
    if bot.test_bot_access():
        print("     ✅ Telegram доступен")
    else:
        print("     ❌ Telegram недоступен")
        print("     Проверьте BOT_TOKEN и подключение к интернету")
        sys.exit(1)
    
    print("  2. Проверяем Gemini AI...")
    if bot.test_gemini_access():
        print("     ✅ Gemini доступен")
    else:
        print("     ❌ Gemini недоступен")
        print("     Проблемы с Gemini API:")
        print("     - Проверьте GEMINI_API_KEY в настройках GitHub Secrets")
        print("     - Возможно превышена квота - подождите 1 час")
        sys.exit(1)
    
    print("  3. Проверяем источник изображений...")
    print("     ✅ Гарантированные изображения Unsplash готовы")
    
    print("\n✅ Все сервисы доступны, запускаем бота...")
    
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ ВЫПОЛНИЛ РАБОТУ!")
        print("   Все посты отправлены")
        print("   Использованы рабочие модели Gemini")
        print("   Изображения: гарантированные Unsplash")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА!")
        print("   Проверьте логи выше")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
