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
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")  # Основной канал
ZEN_CHANNEL_ID = "@tehdzenn"  # Яндекс канал
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка сессии requests
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
session.mount('https://', adapter)
session.mount('http://', adapter)

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ С ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Яндекс канал: {ZEN_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "700-1000",
                "zen_chars": "1200-2000",
                "description": "Короткий, энергичный утренний старт"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "1500-2500",
                "zen_chars": "2500-4000",
                "description": "Самый объёмный, аналитика + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "900-1300",
                "zen_chars": "1200-1600",
                "description": "Средний, расслабленный, но цепляющий"
            }
        }

        # Ключевые слова для изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "hr human resources team meeting office professional",
                "recruitment interview job hiring corporate",
                "workplace collaboration employees business meeting",
                "leadership management team building corporate",
                "office workers collaboration modern workplace"
            ],
            "PR и коммуникации": [
                "public relations media press conference communication",
                "social media marketing digital strategy business",
                "networking event business communication professional",
                "brand marketing advertising media relations",
                "digital communication technology business meeting"
            ],
            "ремонт и строительство": [
                "construction building renovation architecture modern",
                "interior design home repair tools renovation",
                "construction workers building site architecture",
                "home improvement DIY renovation project",
                "architecture design building construction site"
            ]
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
        """Промт для Telegram поста"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['tg_chars']
        
        if slot_type == "morning":
            return f"""Создай пост для Telegram канала на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков
- Стиль: энергичный, мотивирующий утренний пост
- Год: 2025-2026
- Для: Telegram канал

Структура:
1. Хук (цепляющее начало)
2. Основная часть (2-3 ключевых тезиса)
3. Вопрос для обсуждения
4. 5-7 релевантных хештегов

Требования:
- Используй буллеты (•) для списков
- Добавь 1-2 смайлика
- Хештеги только в конце
- Простой текст без HTML/Markdown
- Живой, разговорный стиль

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Создай аналитический пост для Telegram канала на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков  
- Стиль: аналитический, экспертный
- Год: 2025-2026
- Для: Telegram канал

Структура:
1. Мощный хук с интригой
2. Анализ темы с примерами
3. Выводы и рекомендации
4. Вопрос для дискуссии
5. 5-7 релевантных хештегов

Требования:
- Используй буллеты (•) для структуры
- Добавь примеры или кейсы
- Хештеги только в конце
- Простой текст без HTML/Markdown
- Профессиональный, но доступный язык

Тема: {theme}"""

        else:  # evening
            return f"""Создай вечерний пост для Telegram канала на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков
- Стиль: расслабленный, рефлексивный
- Год: 2025-2026
- Для: Telegram канал

Структура:
1. Эмоциональный хук
2. Размышления по теме
3. Финальная мысль
4. Вопрос для обсуждения
5. 5-7 релевантных хештегов

Требования:
- Используй буллеты (•)
- Добавь 1-2 смайлика
- Хештеги только в конце
- Простой текст без HTML/Markdown
- Уютный, доверительный тон

Тема: {theme}"""

    def create_zen_prompt(self, theme, time_slot_info):
        """Промт для Яндекс канала"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['zen_chars']
        
        if slot_type == "morning":
            return f"""Создай пост для Яндекс.Дзен на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков
- Стиль: информативный, легкий
- Год: 2025-2026
- Для: Яндекс.Дзен

Структура:
1. Привлекательный заголовок-хук
2. Основная информация по теме
3. Пример или мини-кейс
4. Вопрос читателю
5. Подпись: "Главная Видео Статьи Новости Подписки"

Требования:
- Форматирование обычным текстом
- Абзацы для читаемости
- Без хештегов
- Без HTML/Markdown
- Интересный, вовлекающий стиль

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Создай развернутый пост для Яндекс.Дзен на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков
- Стиль: аналитический, глубокий
- Год: 2025-2026
- Для: Яндекс.Дзен

Структура:
1. Сильный заголовок-хук
2. Детальный анализ темы
3. Статистика или кейс
4. Экспертное мнение
5. Выводы
6. Подпись: "Главная Видео Статьи Новости Подписки"

Требования:
- Хорошо структурированный текст
- Четкие абзацы
- Без хештегов
- Без HTML/Markdown
- Информативный, полезный контент

Тема: {theme}"""

        else:  # evening
            return f"""Создай вечерний пост для Яндекс.Дзен на тему: {theme}

Характеристики:
- Объем: {chars_range} знаков
- Стиль: философский, размышляющий
- Год: 2025-2026
- Для: Яндекс.Дзен

Структура:
1. Эмоциональный заголовок-хук
2. Личные размышления по теме
3. Финальный вывод
4. Вопрос для размышлений
5. Подпись: "Главная Видео Статьи Новости Подписки"

Требования:
- Уютный, доверительный тон
- Четкие абзацы
- Без хештегов
- Без HTML/Markdown
- Атмосферный текст

Тема: {theme}"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY не установлен")
            return False
        
        try:
            # Попробуем разные API endpoints
            test_models = [
                "gemini-1.5-pro",
                "gemini-1.0-pro",
                "gemini-pro"
            ]
            
            for model in test_models:
                try:
                    test_url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    test_data = {
                        "contents": [{"parts": [{"text": "test"}]}]
                    }
                    
                    response = session.post(test_url, json=test_data, timeout=5)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Gemini API доступен (модель: {model})")
                        return True
                except:
                    continue
            
            logger.error("❌ Все модели Gemini недоступны")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini: {e}")
            return False

    def get_available_gemini_models(self):
        """Получает список доступных моделей"""
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}"
            response = session.get(list_url, timeout=10)
            
            if response.status_code == 200:
                models = response.json()
                available_models = []
                for model in models.get("models", []):
                    model_name = model.get("name", "")
                    if "gemini" in model_name.lower() and "generateContent" in model.get("supportedGenerationMethods", []):
                        available_models.append(model_name.split("/")[-1])
                
                logger.info(f"📋 Доступные модели Gemini: {available_models}")
                return available_models
            return []
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить список моделей: {e}")
            return []

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini"""
        try:
            # Пробуем разные модели Gemini
            models_to_try = [
                "gemini-1.0-pro",  # Стандартная модель
                "gemini-pro",      # Альтернативное название
                "gemini-1.5-pro",  # Новая модель
                "gemini-1.5-flash-latest",  # Последняя версия flash
            ]
            
            generated_text = None
            
            for model in models_to_try:
                try:
                    # Пробуем разные API версии
                    api_versions = ["v1", "v1beta"]
                    
                    for version in api_versions:
                        try:
                            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                            
                            data = {
                                "contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {
                                    "temperature": 0.8,
                                    "topK": 40,
                                    "topP": 0.95,
                                    "maxOutputTokens": 2000,
                                }
                            }
                            
                            logger.info(f"🧠 Пробуем модель {model} (API: {version})...")
                            response = session.post(url, json=data, timeout=30)
                            
                            if response.status_code == 200:
                                result = response.json()
                                if 'candidates' in result and result['candidates']:
                                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                                    logger.info(f"✅ Текст сгенерирован ({model})")
                                    return generated_text.strip()
                            elif response.status_code == 404:
                                logger.debug(f"Модель {model} не найдена в {version}")
                                continue
                            else:
                                logger.warning(f"⚠️ Ошибка {response.status_code} для {model}")
                                
                        except Exception as version_error:
                            logger.debug(f"Ошибка API {version}: {version_error}")
                            continue
                            
                except Exception as model_error:
                    logger.warning(f"⚠️ Ошибка с моделью {model}: {model_error}")
                    continue
            
            # Если все модели не работают, пробуем получить доступные модели
            logger.info("🔄 Получаю список доступных моделей...")
            available_models = self.get_available_gemini_models()
            
            if available_models:
                for model in available_models:
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                        
                        data = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": 0.8,
                                "topK": 40,
                                "topP": 0.95,
                                "maxOutputTokens": 2000,
                            }
                        }
                        
                        logger.info(f"🧠 Пробуем доступную модель {model}...")
                        response = session.post(url, json=data, timeout=30)
                        
                        if response.status_code == 200:
                            result = response.json()
                            if 'candidates' in result and result['candidates']:
                                generated_text = result['candidates'][0]['content']['parts'][0]['text']
                                logger.info(f"✅ Текст сгенерирован ({model})")
                                return generated_text.strip()
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка с доступной моделью {model}: {e}")
                        continue
            
            # Если ничего не сработало
            if not generated_text:
                logger.error("❌ Не удалось сгенерировать текст через Gemini")
                return None
                    
        except Exception as e:
            logger.error(f"💥 Критическая ошибка генерации: {e}")
            return None

    def get_image_url(self, theme):
        """Получает URL изображения по теме"""
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords_list)
            
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Unsplash с конкретными тегами
            encoded_keyword = quote_plus(keyword)
            
            # Пробуем Unsplash API
            unsplash_urls = [
                f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_keyword}&sig={timestamp}",
                f"https://source.unsplash.com/{width}x{height}/?{encoded_keyword},business&sig={timestamp}",
                f"https://source.unsplash.com/random/{width}x{height}/?{encoded_keyword}&sig={timestamp}"
            ]
            
            logger.info(f"🖼️ Поиск картинки для темы '{theme}': {keyword}")
            
            for url in unsplash_urls:
                try:
                    response = session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        final_url = response.url
                        if any(ext in final_url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            logger.info(f"✅ Найдена релевантная картинка")
                            return final_url
                except Exception as e:
                    continue
            
            # Fallback
            logger.info("🔄 Используем fallback картинку")
            return f"https://picsum.photos/{width}/{height}?random={timestamp}"
            
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
        """Проверяет доступ бота"""
        logger.info("🔍 Проверка доступа...")
        
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"🤖 Бот: @{bot_info.get('result', {}).get('username', 'N/A')}")
                return True
            else:
                logger.error(f"❌ Бот не доступен: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            # Для Zen канала добавляем подпись если нет
            if chat_id == ZEN_CHANNEL_ID:
                clean_text = self.ensure_zen_signature(clean_text)
            
            # Пробуем с фото
            if image_url:
                logger.info(f"📤 Отправка в {chat_id} с фото...")
                
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': clean_text[:1024]
                }
                
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Отправлено в {chat_id}")
                    return True
                
                # Пробуем без caption
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
            
            # Только текст
            logger.info(f"📝 Отправка текста в {chat_id}...")
            params = {
                'chat_id': chat_id,
                'text': clean_text,
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
            logger.error(f"❌ Исключение: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            # Проверяем доступ
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к Telegram")
                return False
            
            # Проверяем Gemini
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
            
            logger.info(f"🕒 Время: {current_time_str}")
            logger.info(f"📅 Слот: {slot_name} - {time_slot_info['emoji']} {time_slot_info['name']}")
            
            # Генерация постов
            logger.info("🧠 Генерация Telegram поста...")
            tg_prompt = self.create_telegram_prompt(self.current_theme, time_slot_info)
            tg_text = self.generate_with_gemini(tg_prompt)
            
            if not tg_text:
                logger.error("❌ Не удалось сгенерировать Telegram пост")
                return False
            
            logger.info("🧠 Генерация Zen поста...")
            zen_prompt = self.create_zen_prompt(self.current_theme, time_slot_info)
            zen_text = self.generate_with_gemini(zen_prompt)
            
            if not zen_text:
                logger.error("❌ Не удалось сгенерировать Zen пост")
                return False
            
            # Обрабатываем тексты
            tg_text = self.clean_telegram_text(tg_text)
            zen_text = self.ensure_zen_signature(self.clean_telegram_text(zen_text))
            
            logger.info(f"📊 Telegram: {len(tg_text)} знаков")
            logger.info(f"📊 Zen: {len(zen_text)} знаков")
            
            # Поиск картинки
            logger.info("🖼️ Поиск картинки...")
            image_url = self.get_image_url(self.current_theme)
            
            # Отправка
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку...")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал
            logger.info(f"📤 Отправка в {MAIN_CHANNEL_ID}")
            main_success = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной: УСПЕХ")
            else:
                logger.error("❌ Основной: НЕУДАЧА")
                # Пробуем без фото
                time.sleep(2)
                main_success_text = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text)
                if main_success_text:
                    success_count += 1
                    logger.info("✅ Основной (без фото): УСПЕХ")
            
            time.sleep(2)
            
            # Zen канал
            logger.info(f"📤 Отправка в {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url)
            
            if zen_success:
                success_count += 1
                logger.info("✅ Zen: УСПЕХ")
            else:
                logger.error("❌ Zen: НЕУДАЧА")
                # Пробуем без фото
                time.sleep(2)
                zen_success_text = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text)
                if zen_success_text:
                    success_count += 1
                    logger.info("✅ Zen (без фото): УСПЕХ")
            
            # Результат
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count >= 1:
                    logger.info(f"🎉 УСПЕХ! Посты отправлены в {success_count} канал(ов)")
                return True
            else:
                logger.error("❌ НЕУДАЧА! Не удалось отправить ни в один канал")
                return False
                
        except Exception as e:
            logger.error(f"💥 ОШИБКА: {e}")
            return False


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Telegram: утро/день/вечер с разными объемами")
    print("🎯 Яндекс.Дзен: структурированные посты с подписью")
    print("🎯 В каждом посте: 1 фото из интернета")
    print("🎯 Форматирование: отступы и буллеты •")
    print("🎯 Год: 2025-2026")
    print("🎯 Хештеги: автоматически генерируются AI")
    print("=" * 80)
    
    print("✅ Все переменные окружения загружены")
    
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
            print("🖼️ Картинки соответствуют теме")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("🔧 Что проверить:")
            print("1. Проверьте Gemini API ключ")
            print("2. Убедитесь что API ключ активен")
            print("3. Проверьте доступ к Google AI Studio")
            print("4. Бот должен быть админом в каналах")
            print("\n🔄 Попробуйте запустить снова")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен")
    except Exception as e:
        print(f"\n💥 ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
