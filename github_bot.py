# github_bot.py - Telegram бот для автоматической публикации постов
import os
import requests
import random
import json
import time
import logging
import re
import sys
import argparse
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
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

if not PEXELS_API_KEY:
    logger.error("❌ PEXELS_API_KEY не установлен! Обязательно получи ключ на pexels.com/api")
    sys.exit(1)

# Система согласования отключена - прямая публикация в каналы
logger.info("📤 Режим: прямая публикация в каналы")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: АВТОПИЛОТ С ПРЯМОЙ ПУБЛИКАЦИЕЙ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
print(f"📋 Режим: 📤 ПРЯМАЯ ПУБЛИКАЦИЯ В КАНАЛЫ")
if ADMIN_CHAT_ID:
    print(f"👨‍💼 Уведомления для: {ADMIN_CHAT_ID}")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        self.image_history_file = "image_history.json"
        self.image_history = self.load_image_history()
        
        # 19 форматов подачи текста
        self.text_formats = [
            "разбор ситуации",
            "микро-исследование",
            "аналитическое наблюдение",
            "разбор ошибки",
            "мини-история",
            "взгляд автора",
            "объяснение простым языком",
            "сторителлинг",
            "структурированные советы",
            "аналогия",
            "демонстрация пользы",
            "анализ поведения аудитории",
            "причинно-следственные связи",
            "цепочка «факт → пример → вывод»",
            "список шагов",
            "инсайт",
            "тихая эмоциональная подача",
            "сравнение подходов",
            "мини-обобщение опыта"
        ]
        
        # Объемы по временным слотам
        self.schedule = {
            "09:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "tg_chars": (400, 600),
                "zen_chars": (600, 700)
            },
            "14:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "tg_chars": (700, 900),
                "zen_chars": (700, 900)
            },
            "19:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "tg_chars": (600, 900),
                "zen_chars": (700, 800)
            }
        }
        
        self.current_theme = None
        self.current_format = None

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {
                "sent_slots": {},
                "last_post": None,
                "formats_used": [],
                "themes_used": []
            }

    def load_image_history(self):
        """Загружает историю использованных картинок"""
        try:
            if os.path.exists(self.image_history_file):
                with open(self.image_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {
                "used_images": [],
                "last_update": None
            }

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def save_image_history(self, image_url):
        """Сохраняет историю использованных картинок"""
        try:
            if image_url not in self.image_history["used_images"]:
                self.image_history["used_images"].append(image_url)
                self.image_history["last_update"] = datetime.utcnow().isoformat()
                
                with open(self.image_history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.image_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
            return slot_time in sent_slots
        except:
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if "sent_slots" not in self.post_history:
                self.post_history["sent_slots"] = {}
            
            if today not in self.post_history["sent_slots"]:
                self.post_history["sent_slots"][today] = []
            
            if slot_time not in self.post_history["sent_slots"][today]:
                self.post_history["sent_slots"][today].append(slot_time)
            
            if self.current_theme:
                if "themes_used" not in self.post_history:
                    self.post_history["themes_used"] = []
                self.post_history["themes_used"].append({
                    "date": today,
                    "time": slot_time,
                    "theme": self.current_theme
                })
            
            if self.current_format:
                if "formats_used" not in self.post_history:
                    self.post_history["formats_used"] = []
                self.post_history["formats_used"].append({
                    "date": today,
                    "time": slot_time,
                    "format": self.current_format
                })
            
            self.save_history()
            logger.info(f"✅ Слот {slot_time} помечен как отправленный")
        except:
            pass

    def get_smart_theme(self):
        """Выбирает тему умным способом"""
        try:
            recent_themes = []
            if "themes_used" in self.post_history and self.post_history["themes_used"]:
                recent_entries = self.post_history["themes_used"][-5:] if len(self.post_history["themes_used"]) >= 5 else self.post_history["themes_used"]
                recent_themes = [item.get("theme", "") for item in recent_entries if item.get("theme")]
            
            recent_unique = list(dict.fromkeys(recent_themes))
            available_themes = [theme for theme in self.themes if theme not in recent_unique[-2:]]
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            self.current_theme = theme
            logger.info(f"🎯 Выбрана тема: {theme}")
            return theme
        except:
            self.current_theme = random.choice(self.themes)
            logger.info(f"🎯 Выбрана тема (случайно): {self.current_theme}")
            return self.current_theme

    def get_smart_format(self):
        """Выбирает формат подачи умным способом"""
        try:
            recent_formats = []
            if "formats_used" in self.post_history and self.post_history["formats_used"]:
                recent_entries = self.post_history["formats_used"][-5:] if len(self.post_history["formats_used"]) >= 5 else self.post_history["formats_used"]
                recent_formats = [item.get("format", "") for item in recent_entries if item.get("format")]
            
            recent_unique = list(dict.fromkeys(recent_formats))
            available_formats = [fmt for fmt in self.text_formats if fmt not in recent_unique[-3:]]
            
            if not available_formats:
                available_formats = self.text_formats.copy()
            
            text_format = random.choice(available_formats)
            self.current_format = text_format
            logger.info(f"📝 Выбран формат: {text_format}")
            return text_format
        except:
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def create_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Gemini с полным промтом пользователя"""
        
        # Определяем стиль по времени
        time_styles = {
            "09:00": "мотивация, фокус и энерго-старт",
            "14:00": "аналитика, рациональность, польза",
            "19:00": "истории, личные выводы, рефлексия"
        }
        
        slot_time = list(self.schedule.keys())[list(self.schedule.values()).index(slot_info)] if slot_info in self.schedule.values() else "19:00"
        time_style = time_styles.get(slot_time, "истории, личные выводы, рефлексия")
        
        tg_min, tg_max = slot_info['tg_chars']
        zen_min, zen_max = slot_info['zen_chars']
        
        prompt = f"""🎭 РОЛЬ NEURO AI (несколько профессий)

Ты — синтез из лучших специалистов с 30+ годами опыта:

Промтмейкер
Копирайтер-редактор
SMM-стратег
Контент-мейкер
Продюсер и медиадиректор
Аналитик трендов
Сторителлер и упаковщик смыслов

🎯 ЗАДАЧА

Сгенерировать два текста строго по структуре и строго по лимиту символов:
Telegram-пост и Дзен-пост.

ВНИМАНИЕ! СТРОГОЕ ТРЕБОВАНИЕ К ЛИМИТАМ СИМВОЛОВ:
• Telegram: ТОЧНО {tg_min}-{tg_max} символов (не меньше {tg_min} и не больше {tg_max}!)
• Дзен: ТОЧНО {zen_min}-{zen_max} символов (не меньше {zen_min} и не больше {zen_max}!)

Перед отправкой обязательно проверь длину текстов функцией len() в Python.
Если текст не соответствует лимитам — перепиши его!

AI обязательно:

строго соблюдает структуру
строго соблюдает лимиты символов
учитывает формат подачи по времени публикации (09 / 14 / 19)
подбирает релевантную картинку
не использует воду
не добавляет вводных фраз

⏰ СТИЛИ ПО ВРЕМЕНИ
09:00 — мотивация, фокус и энерго-старт

Подходящие подачи:
• советы
• объяснение сложного простым
• демонстрация пользы
• сравнение подходов
• тихая эмоциональная подача
• цепочка «факт → пример → вывод»

14:00 — аналитика, рациональность, польза

Подходящие подачи:
• аналитическое наблюдение
• микро-исследование
• разбор ошибки
• разбор явления
• анализ поведения аудитории
• причинно-следственные связи
• список шагов
• сильный инсайт

19:00 — истории, личные выводы, рефлексия

Подходящие подачи:
• мини-история
• взгляд автора
• сторителлинг
• аналогия
• проживание опыта
• раскрытие глубокой темы

⏰ ЛИМИТЫ СИМВОЛОВ (СТРОГО)
Telegram (@da4a_hr)

• 09:00 — 400–600
• 14:00 — 700–900
• 19:00 — 600–900

Дзен (@tehdzenm)

• 09:00 — 600–700
• 14:00 — 700–900
• 19:00 — 700–800

📌 РАСШИРЕННЫЕ ФОРМАТЫ ПОДАЧИ

AI выбирает подходящий:

• разбор ситуации
• микро-исследование
• аналитическое наблюдение
• разбор ошибки
• мини-история
• взгляд автора
• объяснение простым языком
• сторителлинг
• структурированные советы
• аналогия
• демонстрация пользы
• анализ поведения аудитории
• причинно-следственные связи
• цепочка «факт → пример → вывод»
• список шагов
• инсайт
• тихая эмоциональная подача
• сравнение подходов
• мини-обобщение опыта

🌿 МЯГКИЙ ВОВЛЕКАЮЩИЙ ФИНАЛ (ОБЯЗАТЕЛЕН)

В конце каждого поста:
• вопрос
• приглашение поделиться
• лёгкий CTA
Типа:
«А как вы считаете?»
«А у вас было так?»
«Что думаете?»

🧱 СТРУКТУРА ТЕЛЕГРАМА

(эмодзи обязательны)

Крючок

1–3 смысловых абзаца

Мини-вывод

Мягкий финал

Хэштеги

[Картинка: …]

🧱 СТРУКТУРА ДЗЕНА

(эмодзи запрещены)

Заголовок

2–4 раскрывающих абзаца

Мини-вывод

Мягкий финал

Хэштеги

[Картинка: …]

══════════════════════════════════════════════════════════════════════════════════

ТЕКУЩИЕ ПАРАМЕТРЫ:

🎯 ТЕМА: {theme}
⏰ ВРЕМЯ ПУБЛИКАЦИИ: {slot_time} ({time_style})
📝 ВЫБРАННЫЙ ФОРМАТ ПОДАЧИ: {text_format}
👥 КАНАЛЫ: Telegram @da4a_hr, Дзен @tehdzenm

ТОЧНЫЕ ОБЪЁМЫ СИМВОЛОВ (СТРОГО СОБЛЮДАТЬ!):
• Telegram: ТОЧНО {tg_min}-{tg_max} символов (сейчас время {slot_time})
• Дзен: ТОЧНО {zen_min}-{zen_max} символов (сейчас время {slot_time})

ПРОВЕРЬ ДЛИНУ ТЕКСТОВ ПЕРЕД ОТПРАВКОЙ!

ВЫХОДНОЙ ФОРМАТ:

TG:
[Телеграм текст ПОЛНОСТЬЮ готовый к публикации со структурой как выше]
---
DZEN:
[Дзен текст ПОЛНОСТЬЮ готовый к публикации со структурой как выше]

ВАЖНО: 
1. Генерируй ДВА ПОЛНОСТЬЮ РАЗНЫХ текста для разных платформ!
2. Соблюдай лимиты символов: TG {tg_min}-{tg_max}, Дзен {zen_min}-{zen_max}
3. Учти время публикации: {slot_time} - {time_style}
4. Используй выбранный формат подачи: {text_format}
5. Добавь мягкий вовлекающий финал в конце каждого поста"""

        logger.info(f"📝 Создан промпт для Gemini")
        logger.info(f"📊 Параметры: Тема={theme}, Время={slot_time}, Формат={text_format}")
        logger.info(f"📏 Лимиты: TG={tg_min}-{tg_max}, Дзен={zen_min}-{zen_max}")
        return prompt

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API"""
        try:
            # Используем доступные модели
            available_models = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro",
                "gemini-1.5-flash-002",
                "gemini-1.5-pro-002"
            ]
            
            for model_name in available_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                    
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.4,
                            "topP": 0.8,
                            "topK": 40,
                            "maxOutputTokens": 2000
                        }
                    }
                    
                    logger.info(f"🤖 Пробуем модель: {model_name}")
                    response = session.post(url, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                            logger.info(f"✅ Текст сгенерирован моделью {model_name}")
                            logger.info(f"📊 Длина текста: {len(generated_text)} символов")
                            return generated_text
                    else:
                        error_msg = response.text[:200] if response.text else "Нет ответа"
                        logger.warning(f"⚠️ Модель {model_name} недоступна: {response.status_code} - {error_msg}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка с моделью {model_name}: {str(e)[:100]}")
                    continue
            
            logger.error("❌ Все модели недоступны")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации текста: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def split_generated_text(self, combined_text):
        """Разделяет сгенерированный текст на Telegram и Дзен части"""
        if not combined_text:
            return None, None
        
        # Ищем разделитель
        if "---" not in combined_text:
            logger.error("❌ В сгенерированном тексте нет разделителя ---")
            return None, None
        
        parts = combined_text.split("---", 1)
        if len(parts) != 2:
            logger.error("❌ Неправильный формат сгенерированного текста")
            return None, None
        
        tg_text = parts[0].replace("TG:", "").replace("Telegram:", "").strip()
        zen_part = parts[1]
        
        # Ищем начало Дзен текста
        if "DZEN:" in zen_part:
            zen_text = zen_part.split("DZEN:", 1)[1].strip()
        elif "Дзен:" in zen_part:
            zen_text = zen_part.split("Дзен:", 1)[1].strip()
        else:
            zen_text = zen_part.strip()
        
        return tg_text, zen_text

    def validate_and_fix_structure(self, text, is_telegram=True):
        """Валидирует и исправляет структуру текста"""
        if not text:
            return text
        
        # 1. Удаляем все вступительные фразы
        text = re.sub(r'^(Вот|Держи|Пожалуйста|Смотри|Вот тебе|Я создал|Я подготовил|Как тебе).+?\n', '', text, flags=re.IGNORECASE)
        
        # 2. Заменяем все тире в списках на •
        lines = text.split('\n')
        fixed_lines = []
        for line in lines:
            # Заменяем "- " на "• " в начале строки
            line = re.sub(r'^- ', '• ', line)
            # Заменяем "— " на "• " в начале строки
            line = re.sub(r'^— ', '• ', line)
            # Заменяем "* " на "• " в начале строки
            line = re.sub(r'^\* ', '• ', line)
            fixed_lines.append(line)
        text = '\n'.join(fixed_lines)
        
        # 3. Удаляем ### заголовки
        text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)
        
        # 4. Для Telegram: добавляем эмодзи если их нет
        if is_telegram:
            # Проверяем наличие эмодзи в первых 5 строках
            first_lines = text.split('\n')[:5]
            has_emoji = any(re.search("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF"
                u"\U0001F680-\U0001F6FF"
                u"\U0001F1E0-\U0001F1FF"
                u"\U00002700-\U000027BF"
                "]+", line) for line in first_lines)
            
            if not has_emoji:
                # Добавляем эмодзи к заголовку или первой строке
                lines = text.split('\n')
                if lines:
                    lines[0] = f"🔥 {lines[0]}"
                    text = '\n'.join(lines)
        
        # 5. Для Дзен: удаляем все эмодзи
        if not is_telegram:
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF"
                u"\U0001F680-\U0001F6FF"
                u"\U0001F1E0-\U0001F1FF"
                u"\U00002700-\U0001F251" 
                "]+", flags=re.UNICODE)
            text = emoji_pattern.sub('', text)
        
        return text.strip()

    def strict_length_validation(self, text, min_chars, max_chars, text_type):
        """Строгая валидация длины"""
        if not text:
            return False, 0
        
        text_length = len(text)
        
        if text_length < min_chars:
            logger.error(f"❌ {text_type} текст слишком короткий: {text_length} < {min_chars}")
            return False, text_length
        
        if text_length > max_chars:
            logger.error(f"❌ {text_type} текст слишком длинный: {text_length} > {max_chars}")
            return False, text_length
        
        logger.info(f"✅ {text_type}: {text_length} символов (требуется {min_chars}-{max_chars})")
        return True, text_length

    def smart_truncate(self, text, max_chars, preserve_structure=True):
        """Умное обрезание текста с сохранением структуры"""
        if len(text) <= max_chars:
            return text
        
        # Обрезаем по последнему законченному предложению
        truncated = text[:max_chars]
        last_dot = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclamation = truncated.rfind('!')
        
        last_punctuation = max(last_dot, last_question, last_exclamation)
        
        if last_punctuation > max_chars * 0.7:  # Если есть пунктуация в последней трети
            return truncated[:last_punctuation + 1]
        
        return truncated + "..."

    def get_post_image(self, theme):
        """Находит подходящую картинку через Pexels API"""
        try:
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "building"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social"]
            }
            
            queries = theme_queries.get(theme, ["business", "work", "success"])
            query = random.choice(queries)
            
            # Используем Pexels API
            logger.info(f"🔍 Ищем картинку в Pexels по запросу: '{query}'")
            
            url = "https://api.pexels.com/v1/search"
            params = {
                "query": query,
                "per_page": 10,
                "orientation": "landscape",
                "size": "large"
            }
            
            headers = {
                "Authorization": PEXELS_API_KEY
            }
            
            response = session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    logger.info(f"📸 Найдено {len(photos)} фото в Pexels")
                    # Берем случайное фото
                    photo = random.choice(photos)
                    image_url = photo.get("src", {}).get("large", "")
                    
                    if image_url:
                        logger.info(f"🖼️ Используем картинку из Pexels: {image_url[:80]}...")
                        return image_url
                else:
                    logger.warning("⚠️ Pexels не вернул фотографий по запросу")
            else:
                logger.error(f"❌ Pexels API ошибка: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске картинки в Pexels: {e}")
        
        # Если Pexels не сработал, используем Unsplash
        logger.info("🔄 Pexels не сработал, пробуем Unsplash...")
        try:
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                logger.info(f"🖼️ Используем картинку из Unsplash: {image_url[:80]}...")
                return image_url
        except Exception as unsplash_error:
            logger.error(f"❌ Unsplash тоже не сработал: {unsplash_error}")
        
        # Дефолтная картинка если всё сломалось
        default_image = "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"
        logger.info(f"🖼️ Используем дефолтную картинку")
        return default_image

    def format_telegram_text(self, text, slot_info):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        # 1. Очистка
        text = self.validate_and_fix_structure(text, is_telegram=True)
        
        # 2. Удаляем все следы предыдущих форматов
        text = re.sub(r'^TG:\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^Telegram:\s*', '', text, flags=re.MULTILINE)
        
        # 3. Удаляем квадратные скобки
        if text.startswith('['):
            text = text[1:].strip()
        if text.endswith(']'):
            text = text[:-1].strip()
        
        # 4. Добавляем эмодзи слота
        lines = text.split('\n')
        if lines:
            lines[0] = f"{slot_info['emoji']} {lines[0]}"
            text = '\n'.join(lines)
        
        # 5. Строгая проверка длины
        tg_min, tg_max = slot_info['tg_chars']
        is_valid, length = self.strict_length_validation(text, tg_min, tg_max, "Telegram")
        
        if not is_valid:
            if length > tg_max:
                text = self.smart_truncate(text, tg_max)
                logger.warning(f"⚠️ Telegram текст обрезан до {len(text)} символов")
            elif length < tg_min:
                # Добавляем мягкий вовлекающий финал
                addition = f"\n\n{slot_info['emoji']} А как вы считаете? Поделитесь в комментариях!"
                text += addition
                if len(text) > tg_max:
                    text = text[:tg_max-3] + "..."
                logger.warning(f"⚠️ Telegram текст дополнен до {len(text)} символов")
        
        # 6. Финальная проверка
        text_length = len(text)
        if text_length < tg_min or text_length > tg_max:
            logger.error(f"❌ Критично: Telegram текст не соответствует требованиям: {text_length}")
            if text_length > tg_max:
                text = text[:tg_max-3] + "..."
        
        # 7. Проверяем наличие мягкого финала
        if "?" not in text[-50:] and "!" not in text[-50:]:
            text += f"\n\nЧто думаете по этому поводу?"
        
        # 8. Добавляем хэштеги если есть место
        max_length = 1024  # Telegram limit for captions
        if text_length < max_length - 50 and self.current_theme:
            try:
                # Исправление ошибки: используем self.current_theme вместо theme
                theme_for_hashtag = self.current_theme.lower().replace(' ', '_').replace('и', '')
                hashtags = f"\n\n#{theme_for_hashtag} #бизнес"
                if text_length + len(hashtags) < max_length:
                    text += hashtags
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при добавлении хэштегов: {e}")
                # Добавляем простые хэштеги
                if text_length + 20 < max_length:
                    text += "\n\n#бизнес #советы"
        
        return text.strip()

    def format_zen_text(self, text, slot_info):
        """Форматирует текст для Дзен"""
        if not text:
            return ""
        
        # 1. Очистка
        text = self.validate_and_fix_structure(text, is_telegram=False)
        
        # 2. Удаляем все следы предыдущих форматов
        text = re.sub(r'^DZEN:\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^Дзен:\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^TG:\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^Telegram:\s*', '', text, flags=re.MULTILINE)
        
        # 3. Удаляем квадратные скобки
        if text.startswith('['):
            text = text[1:].strip()
        if text.endswith(']'):
            text = text[:-1].strip()
        
        # 4. Удаляем эмодзи
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U000027BF"
            u"\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        # 5. Удаляем хэштеги (они будут добавлены отдельно если нужно)
        text = re.sub(r'#\w+', '', text)
        
        # 6. Строгая проверка длины
        zen_min, zen_max = slot_info['zen_chars']
        is_valid, length = self.strict_length_validation(text, zen_min, zen_max, "Дзен")
        
        if not is_valid:
            if length > zen_max:
                text = self.smart_truncate(text, zen_max)
                logger.warning(f"⚠️ Дзен текст обрезан до {len(text)} символов")
            elif length < zen_min:
                # Добавляем вопрос если слишком короткий
                addition = f"\n\nА у вас было так? Поделитесь своим опытом в комментариях."
                text += addition
                if len(text) > zen_max:
                    text = text[:zen_max-3] + "..."
                logger.warning(f"⚠️ Дзен текст дополнен до {len(text)} символов")
        
        # 7. Финальная проверка
        text_length = len(text)
        if text_length < zen_min or text_length > zen_max:
            logger.error(f"❌ Критично: Дзен текст не соответствует требованиям: {text_length}")
            if text_length > zen_max:
                text = text[:zen_max-3] + "..."
        
        # 8. Проверяем наличие мягкого финала
        if "?" not in text[-50:] and "!" not in text[-50:]:
            text += f"\n\nЧто вы думаете по этой теме?"
        
        return text.strip()

    def publish_directly(self, slot_time, tg_text, zen_text, image_url, theme):
        """Публикует посты напрямую в каналы"""
        logger.info("📤 Публикую посты напрямую в каналы...")
        
        success_count = 0
        
        logger.info(f"📨 Отправляем в ОСНОВНОЙ КАНАЛ: {MAIN_CHANNEL_ID}")
        if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {MAIN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {MAIN_CHANNEL_ID}")
        
        time.sleep(2)
        
        logger.info(f"📨 Отправляем в ДЗЕН КАНАЛ: {ZEN_CHANNEL_ID}")
        if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {ZEN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {ZEN_CHANNEL_ID}")
        
        if ADMIN_CHAT_ID and success_count > 0:
            self.send_admin_notification(slot_time, theme, success_count)
        
        return success_count

    def send_admin_notification(self, slot_time, theme, success_count):
        """Отправляет уведомление администратору о публикации"""
        try:
            notification = (
                f"✅ <b>Посты опубликованы автоматически</b>\n\n"
                f"🎯 <b>Тема:</b> {theme}\n"
                f"🕒 <b>Время слота:</b> {slot_time} МСК\n"
                f"📊 <b>Успешно опубликовано:</b> {success_count}/2 каналов\n\n"
                f"📢 Каналы:\n"
                f"• {MAIN_CHANNEL_ID}\n"
                f"• {ZEN_CHANNEL_ID}"
            )
            
            params = {
                'chat_id': ADMIN_CHAT_ID,
                'text': notification,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"📨 Уведомление отправлено администратору")
                return True
            else:
                logger.warning(f"⚠️ Не удалось отправить уведомление администратору")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram канал"""
        try:
            logger.info(f"📤 Отправляем пост в {chat_id}")
            
            if not text or len(text.strip()) < 50:
                logger.error(f"❌ Текст слишком короткий")
                return False
            
            # Логируем структуру поста
            logger.info(f"📋 Структура поста для {chat_id}:")
            lines = text.split('\n')
            for i, line in enumerate(lines[:8]):
                if line.strip():
                    logger.info(f"   L{i+1}: {line[:80]}{'...' if len(line) > 80 else ''}")
            if len(lines) > 8:
                logger.info(f"   ... и еще {len(lines)-8} строк")
            logger.info(f"📏 Длина: {len(text)} символов")
            
            # Пробуем отправить с картинкой
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text[:1024],
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"✅ Успешно отправлено с картинкой в {chat_id}")
                    return True
            
            logger.warning(f"⚠️ Не удалось с картинкой, пробуем текстом...")
            
            text_params = {
                'chat_id': chat_id,
                'text': text[:4096],
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response2 = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=text_params,
                timeout=30
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                if result2.get('ok'):
                    logger.info(f"✅ Успешно отправлено как текст в {chat_id}")
                    return True
            
            logger.error(f"❌ Оба метода не сработали для {chat_id}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке в {chat_id}: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_info, is_test=False, force_send=False):
        """Генерирует и отправляет посты для указанного слота"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_info['name']}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            prompt = self.create_prompt(theme, slot_info, text_format)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            logger.info(f"📝 Сгенерированный текст: {len(combined_text)} символов")
            
            tg_text_raw, zen_text_raw = self.split_generated_text(combined_text)
            
            if not tg_text_raw:
                logger.error("❌ Не удалось извлечь Telegram текст")
                return False
            
            if not zen_text_raw:
                logger.error("❌ Не удалось извлечь Дзен текст")
                return False
            
            tg_text = self.format_telegram_text(tg_text_raw, slot_info)
            zen_text = self.format_zen_text(zen_text_raw, slot_info)
            
            # Проверяем структуру
            lines = tg_text.split('\n')
            if lines:
                first_line = lines[0]
                if "?" not in first_line and "!" not in first_line and ":" not in first_line:
                    logger.warning("⚠️ Хук не достаточно цепляющий, добавляем интригу")
                    enhanced_hook = f"💡 {first_line}"
                    if "?" not in enhanced_hook and "!" not in enhanced_hook:
                        enhanced_hook += "?"
                    tg_text = enhanced_hook + "\n" + "\n".join(lines[1:])
            
            # Проверяем списки
            if "•" not in tg_text and "•" not in zen_text:
                logger.warning("⚠️ Нет списков, добавляем структуру")
            
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            logger.info(f"📊 Длина текстов после форматирования:")
            logger.info(f"   TG: {tg_length} символов (требуется {tg_min}-{tg_max})")
            logger.info(f"   DZEN: {zen_length} символов (требуется {zen_min}-{zen_max})")
            
            # Финальная валидация
            if tg_length < tg_min or tg_length > tg_max:
                logger.error(f"❌ Telegram текст не прошел валидацию по длине: {tg_length} (требуется {tg_min}-{tg_max})")
                # Попробуем исправить
                if tg_length > tg_max:
                    tg_text = self.smart_truncate(tg_text, tg_max)
                    logger.info(f"📝 Telegram текст обрезан до {len(tg_text)} символов")
            
            if zen_length < zen_min or zen_length > zen_max:
                logger.error(f"❌ Дзен текст не прошел валидацию по длине: {zen_length} (требуется {zen_min}-{zen_max})")
                # Попробуем исправить
                if zen_length > zen_max:
                    zen_text = self.smart_truncate(zen_text, zen_max)
                    logger.info(f"📝 Дзен текст обрезан до {len(zen_text)} символов")
            
            # Повторная проверка после исправлений
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            if tg_length < tg_min or tg_length > tg_max:
                logger.error(f"❌ Telegram текст все еще не соответствует лимитам: {tg_length}")
                return False
            
            if zen_length < zen_min or zen_length > zen_max:
                logger.error(f"❌ Дзен текст все еще не соответствует лимитам: {zen_length}")
                return False
            
            logger.info("🖼️ Подбираем картинку...")
            image_url = self.get_post_image(theme)
            
            if not is_test:
                logger.info("📤 ПУБЛИКУЮ ПОСТЫ НАПРЯМУЮ В КАНАЛЫ")
                success_count = self.publish_directly(slot_time, tg_text, zen_text, image_url, theme)
            else:
                logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ - публикация пропущена")
                success_count = 1
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                logger.info(f"📝 Информация сохранена в историю")
            
            if success_count >= 1:
                logger.info(f"\n🎉 УСПЕХ! Отправлено постов: {success_count}/2")
                logger.info(f"   🕒 Время: {slot_time} МСК")
                logger.info(f"   🎯 Тема: {theme}")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Длина TG: {tg_length} символов")
                logger.info(f"   📏 Длина DZEN: {zen_length} символов")
                
                # Проверяем наличие хука
                lines_for_hook = tg_text.split('\n')
                first_line_for_hook = lines_for_hook[0] if lines_for_hook else ""
                has_hook = '?' in first_line_for_hook or '!' in first_line_for_hook or ':' in first_line_for_hook
                structure_status = '✅ Хук есть' if has_hook else '⚠️ Хук слабый'
                logger.info(f"   📐 Структура: {structure_status}")
                
                # Проверяем наличие мягкого финала
                has_soft_final = '?' in tg_text[-100:] or '?' in zen_text[-100:]
                final_status = '✅ Есть' if has_soft_final else '⚠️ Нет'
                logger.info(f"   🤝 Мягкий финал: {final_status}")
                
                has_lists = '•' in tg_text or '•' in zen_text
                lists_status = '✅ Есть' if has_lists else '⚠️ Нет'
                logger.info(f"   📋 Списки: {lists_status}")
                return True
            else:
                logger.error(f"❌ Не удалось отправить ни одного поста")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        print(f"\n🔄 Запуск в режиме once. Время МСК: {current_time}")
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Найден слот для отправки: {slot_time} - {slot_info['name']}")
        print(f"📏 Лимиты: Telegram {slot_info['tg_chars'][0]}-{slot_info['tg_chars'][1]} символов")
        print(f"📏 Лимиты: Дзен {slot_info['zen_chars'][0]}-{slot_info['zen_chars'][1]} символов")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            print(f"✅ Посты опубликованы в каналы в {slot_time} МСК")
        else:
            print(f"❌ Ошибка публикации постов")
        
        return success

    def run_test_mode(self):
        """Тестовый режим"""
        print("\n" + "=" * 80)
        print("🧪 ТЕСТОВЫЙ РЕЖИМ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Текущее время МСК: {now.strftime('%H:%M:%S')}")
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📝 Выбран слот: {slot_time} - {slot_info['name']}")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=True)
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ТЕСТ ПРОЙДЕН!")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН")
        print("=" * 80)
        
        return success


def main():
    """Главная функция запуска"""
    
    parser = argparse.ArgumentParser(description='Телеграм бот для автоматической публикации постов')
    parser.add_argument('--test', '-t', action='store_true', help='Тестовый режим')
    parser.add_argument('--once', '-o', action='store_true', help='Однократный запуск (для GitHub Actions)')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕЛЕГРАМ БОТА")
    print("=" * 80)
    
    bot = TelegramBot()
    
    if args.once:
        print("📝 РЕЖИМ: Однократный запуск (GitHub Actions)")
        bot.run_once_mode()
    elif args.test:
        print("📝 РЕЖИМ: Тестирование")
        bot.run_test_mode()
    else:
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("python github_bot.py --once   # Для GitHub Actions")
        print("python github_bot.py --test   # Тестирование")
        print("\nДЛЯ GITHUB ACTIONS: python github_bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
