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
            return f"""Напиши уникальный пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — энергичный утренний старт
Год: 2025-2026

Структура:
1. Начни с сильного хука (первое предложение должно цеплять внимание)
2. Основная часть:
   • 2-4 коротких и ёмких тезиса по теме
   • Используй буллеты (•) для структуры
   • Добавь 1-2 смайлика в текст
   • Минимальный объем воды, только суть
3. Финал:
   • Задай провокационный вопрос для комментариев
   • Добавь 5-7 релевантных хештегов на русском языке в конце

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст с переносами строк
• Хештеги только в конце, раздели их пробелами
• Не нумеруй пункты, используй буллеты

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши аналитический пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — глубокая аналитика + живой язык
Год: 2025-2026

Структура:
1. Мощный хук (интригующее начало)
2. Анализ темы:
   • Раскрой тему глубже
   • Добавь конкретный пример или мини-кейс
   • Сделай выводы
   • Используй буллеты (•) для структурирования
3. Завершение:
   • Задай открытый вопрос для дискуссии
   • Добавь 5-7 релевантных хештегов на русском языке в конце

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст с абзацами
• Хештеги только в конце
• Можно использовать смайлики для эмоциональной окраски

Тема: {theme}"""

        else:  # evening
            return f"""Напиши вечерний пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — расслабленный, но цепляющий
Год: 2025-2026

Структура:
1. Эмоциональный хук (бить в эмоции читателя)
2. Основные мысли:
   • 2-3 глубокие мысли по теме
   • Короткое личное наблюдение или инсайт
   • Вызови эмоцию у читателя
   • Используй буллеты (•)
3. Финальная часть:
   • Вопрос для вечернего обсуждения
   • Добавь 5-7 релевантных хештегов на русском языке в конце

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст
• Хештеги только в конце
• Добавь 1-2 уместных смайлика

Тема: {theme}"""

    def create_zen_prompt(self, theme, time_slot_info):
        """Промт для Яндекс канала"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['zen_chars']
        
        if slot_type == "morning":
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — легкий, информативный
Год: 2025-2026

Структура:
1. Мощный хук для привлечения внимания
2. Основное содержание:
   • Подай тему доступно и легко
   • Добавь микросюжет или конкретный пример
   • Сделай текст интересным для чтения
3. Финал:
   • Завершающий вопрос читателю
   • В самом конце добавь строку: "Главная Видео Статьи Новости Подписки"

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст с абзацами
• Не добавляй хештеги
• Сделай текст хорошо структурированным

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши развернутый аналитический пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — глубокий анализ + экспертное мнение
Год: 2025-2026

Структура:
1. Сильный хук, обозначающий важность темы
2. Детальный разбор:
   • Проанализируй тему с разных сторон
   • Вставь мини-кейс или статистику
   • Представь экспертную точку зрения
   • Сделай содержательные выводы
3. Завершение:
   • Призыв к обсуждению или размышлению
   • В самом конце добавь строку: "Главная Видео Статьи Новости Подписки"

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст с четкими абзацами
• Не добавляй хештеги
• Сделай текст максимально информативным

Тема: {theme}"""

        else:  # evening
            return f"""Напиши вечерний пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — легкий вечерний, философский
Год: 2025-2026

Структура:
1. Хук, который цепляет эмоционально
2. Основная мысль:
   • Короткая, но глубокая мысль по теме
   • Личный взгляд или наблюдение
   • Вывод, который заставляет задуматься
3. Финальная часть:
   • Вопрос для вечерних размышлений
   • В самом конце добавь строку: "Главная Видео Статьи Новости Подписки"

Форматирование:
• Не используй HTML или markdown
• Используй обычный текст
• Не добавляй хештеги
• Сделай текст атмосферным и уютным

Тема: {theme}"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY не установлен")
            return False
        
        try:
            # Простая проверка доступности API
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            test_data = {
                "contents": [{"parts": [{"text": "test"}]}]
            }
            
            response = session.post(test_url, json=test_data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Gemini API доступен")
                return True
            else:
                logger.error(f"❌ Gemini API недоступен: {response.status_code}")
                logger.error(f"Ответ: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini"""
        try:
            # Исправленный URL для Gemini API
            # Попробуем разные модели
            models_to_try = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro"
            ]
            
            generated_text = None
            
            for model in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.9 if "morning" in prompt.lower() else 0.8,
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
                    
                    logger.info(f"🧠 Генерация через {model}...")
                    response = session.post(url, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            generated_text = result['candidates'][0]['content']['parts'][0]['text']
                            logger.info(f"✅ Текст сгенерирован ({model})")
                            return generated_text.strip()
                    else:
                        logger.warning(f"⚠️ Модель {model} недоступна: {response.status_code}")
                        logger.warning(f"Ответ: {response.text[:200]}")
                        
                except Exception as model_error:
                    logger.warning(f"⚠️ Ошибка с моделью {model}: {model_error}")
                    continue
            
            # Если все модели не работают
            if not generated_text:
                logger.error("❌ Все модели Gemini недоступны")
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
            
            # Пробуем Unsplash API для более релевантных фото
            unsplash_urls = [
                f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_keyword}&sig={timestamp}",
                f"https://source.unsplash.com/{width}x{height}/?{encoded_keyword},business&sig={timestamp}",
                f"https://source.unsplash.com/random/{width}x{height}/?{encoded_keyword}&sig={timestamp}"
            ]
            
            logger.info(f"🖼️ Поиск картинки для темы '{theme}': {keyword}")
            
            for url in unsplash_urls:
                try:
                    # Получаем финальный URL после редиректа
                    response = session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        final_url = response.url
                        # Проверяем, что это действительно изображение
                        if any(ext in final_url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            logger.info(f"✅ Найдена релевантная картинка")
                            return final_url
                except Exception as e:
                    continue
            
            # Fallback на Pexels или Pixabay
            logger.info("🔄 Пробуем альтернативные источники...")
            
            # Pexels
            pexels_keywords = encoded_keyword.replace('+', ',')
            pexels_url = f"https://images.pexels.com/photos/{random.randint(1, 999999)}/pexels-photo-{random.randint(1, 999999)}.jpeg?auto=compress&cs=tinysrgb&w={width}&h={height}&fit=crop"
            
            # Пробуем Pexels
            try:
                response = session.head(pexels_url, timeout=3, allow_redirects=True)
                if response.status_code == 200:
                    return response.url
            except:
                pass
            
            # Последний fallback - Lorem Picsum
            fallback_url = f"https://picsum.photos/{width}/{height}?random={timestamp}"
            logger.info("🔄 Используем fallback картинку")
            return fallback_url
            
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
        
        # Убеждаемся, что хештеги разделены пробелами
        text = re.sub(r'(#\w+)(#)', r'\1 \2', text)
        
        # Обрезаем если слишком длинный
        if len(text) > 4096:
            text = text[:4000] + "..."
        
        return text.strip()

    def ensure_zen_signature(self, text):
        """Убеждается, что в тексте Zen есть подпись"""
        signature = "Главная Видео Статьи Новости Подписки"
        
        if signature not in text:
            # Удаляем все хештеги из Zen текста
            text = re.sub(r'#\w+\s*', '', text)
            text = re.sub(r'\s+#\w+', '', text)
            
            # Добавляем подпись
            text = f"{text}\n\n{signature}"
        
        return text

    def test_bot_access(self):
        """Проверяет доступ бота"""
        logger.info("🔍 Проверка доступа...")
        
        # Проверяем бота
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"🤖 Бот: @{bot_info.get('result', {}).get('username', 'N/A')}")
            else:
                logger.error(f"❌ Бот не доступен")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False
        
        return True

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
                
                # Метод 1: sendPhoto с caption
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
                
                # Метод 2: без caption
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
            
            time.sleep(2)
            
            # Zen канал
            logger.info(f"📤 Отправка в {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url)
            
            if zen_success:
                success_count += 1
                logger.info("✅ Zen: УСПЕХ")
            else:
                logger.error("❌ Zen: НЕУДАЧА")
            
            # Результат
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count == 2:
                    logger.info("🎉 УСПЕХ! Посты отправлены в ОБА канала!")
                else:
                    logger.info(f"⚠️  Отправлено в {success_count} из 2 каналов")
                return True
            else:
                logger.error("❌ НЕУДАЧА!")
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
            print("🏷️  Хештеги добавлены автоматически")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("🔧 Что проверить:")
            print("1. Бот должен быть админом в каналах")
            print("2. У бота должно быть право отправки сообщений")
            print("3. Проверьте BOT_TOKEN и GEMINI_API_KEY")
            print("4. Каналы должны быть публичными")
            print("5. Gemini API должен быть доступен")
            print("\n🔄 Попробуйте запустить снова")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен")
    except Exception as e:
        print(f"\n💥 ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
