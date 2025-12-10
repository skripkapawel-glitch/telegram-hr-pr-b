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
print(f"✅ BOT_TOKEN: Установен")
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
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки истории: {e}")
        return {
            "sent_slots": {},
            "last_post": None,
            "formats_used": [],
            "themes_used": [],
            "theme_rotation": []
        }

    def load_image_history(self):
        """Загружает историю использованных картинок"""
        try:
            if os.path.exists(self.image_history_file):
                with open(self.image_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {
            "used_images": [],
            "last_update": None
        }

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_image_history(self, image_url):
        """Сохраняет историю использованных картинок"""
        try:
            if image_url not in self.image_history.get("used_images", []):
                self.image_history.setdefault("used_images", []).append(image_url)
                self.image_history["last_update"] = datetime.utcnow().isoformat()
                
                with open(self.image_history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.image_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            if self.post_history and "sent_slots" in self.post_history:
                sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
                return slot_time in sent_slots
            return False
        except Exception:
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if not self.post_history:
                self.post_history = {}
            
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
                
                # Обновляем ротацию тем
                if "theme_rotation" not in self.post_history:
                    self.post_history["theme_rotation"] = []
                self.post_history["theme_rotation"].append(self.current_theme)
                # Ограничиваем историю последними 10 темами
                if len(self.post_history["theme_rotation"]) > 10:
                    self.post_history["theme_rotation"] = self.post_history["theme_rotation"][-10:]
            
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
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с умной ротацией - НЕ повторяем темы подряд"""
        try:
            # Проверяем что post_history не None
            if not self.post_history:
                self.post_history = {
                    "theme_rotation": []
                }
            
            # Инициализируем theme_rotation если его нет
            if "theme_rotation" not in self.post_history:
                self.post_history["theme_rotation"] = []
            
            theme_rotation = self.post_history.get("theme_rotation", [])
            
            # Если история пустая, берем случайную тему
            if not theme_rotation:
                theme = random.choice(self.themes)
                self.current_theme = theme
                logger.info(f"🎯 Выбрана тема (первая): {theme}")
                return theme
            
            # Получаем последнюю использованную тему
            last_theme = theme_rotation[-1] if theme_rotation else None
            
            # Создаем список доступных тем (исключаем последнюю использованную)
            available_themes = [t for t in self.themes if t != last_theme]
            
            # Если все темы использовались, берем ту, которая давно не использовалась
            if not available_themes:
                # Ищем тему, которая дольше всего не использовалась
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_rotation):
                    for theme in self.themes:
                        if theme == used_theme:
                            theme_counts[theme] += 1
                
                # Берем тему с наименьшим счетчиком (реже всего использовалась)
                theme = min(theme_counts, key=theme_counts.get)
            else:
                # Берем случайную из доступных
                theme = random.choice(available_themes)
            
            self.current_theme = theme
            logger.info(f"🎯 Выбрана тема: {theme} (последняя была: {last_theme})")
            return theme
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выборе темы: {e}")
            self.current_theme = random.choice(self.themes)
            logger.info(f"🎯 Выбрана тема (случайно): {self.current_theme}")
            return self.current_theme

    def get_smart_format(self):
        """Выбирает формат подачи умным способом"""
        try:
            if not self.post_history or "formats_used" not in self.post_history:
                self.current_format = random.choice(self.text_formats)
                logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
                return self.current_format
            
            recent_formats = []
            if self.post_history.get("formats_used"):
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
        except Exception:
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def create_telegram_prompt(self, theme, slot_info, text_format):
        """Создает ОТДЕЛЬНЫЙ промпт только для Telegram поста"""
        tg_min, tg_max = slot_info['tg_chars']
        slot_time = None
        for time_key, info in self.schedule.items():
            if info == slot_info:
                slot_time = time_key
                break
        
        # УЧИЩАЕМ ПРОМПТ: делаем его максимально простым и понятным
        prompt = f"""СОЗДАЙ TELEGRAM ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
СИМВОЛОВ: от {tg_min} до {tg_max}

🔴 ВАЖНО: Длина поста ДОЛЖНА быть от {tg_min} до {tg_max} символов включительно.

СТРУКТУРА:
1. {slot_info['emoji']} Цепляющая первая фраза
2. 1-2 коротких абзаца (по 2-3 предложения каждый)
3. Один вывод
4. Вопрос к читателям
5. 2-3 хэштега

ПРИМЕР структуры ({tg_min}-{tg_max} символов):
{slot_info['emoji']} Заголовок/первая фраза

Первый абзац из 2-3 предложений.

Второй абзац из 2-3 предложений.

Вывод одним предложением.

Вопрос к читателям?

#хэштег1 #хэштег2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ТВОЙ ПОСТ (только текст):"""

        return prompt

    def create_zen_prompt(self, theme, slot_info, text_format):
        """Создает ОТДЕЛЬНЫЙ промпт только для Дзен поста"""
        zen_min, zen_max = slot_info['zen_chars']
        
        # УПРОЩАЕМ ПРОМПТ для Дзен
        prompt = f"""СОЗДАЙ ДЗЕН ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
СИМВОЛОВ: от {zen_min} до {zen_max}

🔴 ВАЖНО: Длина поста ДОЛЖНА быть от {zen_min} до {zen_max} символов включительно.

СТРУКТУРА:
1. Заголовок (без эмодзи, 1 строка)
2. 2-3 информативных абзаца (по 3-4 предложения)
3. Один вывод
4. Вопрос для обсуждения
5. 2-3 хэштега

ПРИМЕР структуры ({zen_min}-{zen_max} символов):
Заголовок статьи

Первый абзац из 3-4 предложений. Раскрывает основную мысль.

Второй абзац из 3-4 предложений. Дает примеры или объяснения.

Третий абзац из 3-4 предложений. Подводит к выводу.

Вывод статьи одним-двумя предложениями.

Вопрос для обсуждения с читателями.

#хэштег1 #хэштег2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ТВОЙ ПОСТ (только текст, без эмодзи):"""

        return prompt

    def _smart_adjust_text(self, text, target_min, target_max, text_type):
        """
        УМНАЯ корректировка текста: просим модель саму оптимизировать длину
        без потери смысла
        """
        current_len = len(text)
        
        if target_min <= current_len <= target_max:
            return text  # Уже подходит
        
        logger.info(f"🔄 Корректируем {text_type}: {current_len} → {target_min}-{target_max}")
        
        if current_len > target_max:
            instruction = f"Сократи этот текст до {target_max} символов. Удали повторы, упрости формулировки, но сохрани смысл."
            multiplier = 0.7
        else:
            instruction = f"Дополни этот текст до {target_min} символов. Добавь конкретных примеров, деталей, но не меняй основную мысль."
            multiplier = 1.3
        
        adjust_prompt = f"""Скорректируй длину текста:

ТЕКСТ:
{text}

ИНСТРУКЦИЯ: {instruction}

ТЕКУЩАЯ ДЛИНА: {current_len} символов
ЦЕЛЕВАЯ ДЛИНА: {target_min}-{target_max} символов

Отредактированный текст (только текст, без пояснений):"""
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            max_tokens = int(len(text) * multiplier)
            data = {
                "contents": [{"parts": [{"text": adjust_prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.5,
                    "topK": 30,
                    "maxOutputTokens": max_tokens,
                }
            }
            
            response = session.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    adjusted_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    new_len = len(adjusted_text)
                    
                    logger.info(f"📊 После корректировки: {new_len} символов")
                    
                    if target_min <= new_len <= target_max:
                        logger.info(f"✅ {text_type} успешно откорректирован")
                        return adjusted_text
                    else:
                        logger.warning(f"⚠️ Корректировка не удалась: {new_len} символов")
                        return text  # Возвращаем оригинальный текст
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при корректировке: {str(e)[:100]}")
        
        return text  # Если что-то пошло не так, возвращаем оригинал

    def generate_single_post(self, prompt, target_chars_min, target_chars_max, post_type):
        """Генерирует ОДИН пост с последующей умной корректировкой"""
        try:
            # Используем gemma-3-27b-it
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            # Рассчитываем разумный лимит токенов
            max_tokens = int(target_chars_max / 3 * 1.5)  # Запас 50%
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.6,
                    "topK": 40,
                    "maxOutputTokens": max_tokens,
                }
            }
            
            logger.info(f"🤖 Генерация {post_type}")
            response = session.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    length = len(generated_text)
                    
                    logger.info(f"📊 {post_type}: {length} символов (нужно {target_chars_min}-{target_chars_max})")
                    
                    # Если длина не соответствует - корректируем
                    if not (target_chars_min <= length <= target_chars_max):
                        generated_text = self._smart_adjust_text(
                            generated_text, 
                            target_chars_min, 
                            target_chars_max,
                            post_type
                        )
                    
                    return generated_text
            
            logger.error(f"❌ Ошибка при генерации {post_type}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при генерации {post_type}: {e}")
            return None

    def strict_length_validation(self, text, min_chars, max_chars, text_type):
        """СТРОГАЯ валидация длины с разумным допуском"""
        if not text:
            logger.error(f"❌ {text_type} текст пустой")
            return False, 0
        
        text_length = len(text)
        
        # Добавляем небольшой допуск (±10 символов) из-за проблем модели
        tolerance = 10
        adjusted_min = max(1, min_chars - tolerance)
        adjusted_max = max_chars + tolerance
        
        if text_length < adjusted_min:
            logger.error(f"❌ {text_type} текст слишком короткий: {text_length} < {min_chars}")
            return False, text_length
        
        if text_length > adjusted_max:
            logger.error(f"❌ {text_type} текст слишком длинный: {text_length} > {max_chars}")
            return False, text_length
        
        logger.info(f"✅ {text_type}: {text_length} символов (требуется {min_chars}-{max_chars})")
        return True, text_length

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
            return None
        
        text = text.strip()
        
        # Добавляем эмодзи слота если его нет
        if not text.startswith(slot_info['emoji']):
            # Проверяем, есть ли уже какой-то эмодзи
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF"
                u"\U0001F680-\U0001F6FF"
                u"\U0001F1E0-\U0001F1FF"
                u"\U00002700-\U0001F251" 
                "]+", flags=re.UNICODE)
            
            if not emoji_pattern.match(text[:2]):
                lines = text.split('\n')
                if lines and lines[0].strip():
                    lines[0] = f"{slot_info['emoji']} {lines[0]}"
                    text = '\n'.join(lines)
        
        # Проверяем длину
        tg_min, tg_max = slot_info['tg_chars']
        is_valid, length = self.strict_length_validation(text, tg_min, tg_max, "Telegram")
        
        if not is_valid:
            return None
        
        return text.strip()

    def format_zen_text(self, text, slot_info):
        """Форматирует текст для Дзен"""
        if not text:
            return None
        
        text = text.strip()
        
        # Удаляем эмодзи если есть
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U0001F251" 
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        # Проверяем длину
        zen_min, zen_max = slot_info['zen_chars']
        is_valid, length = self.strict_length_validation(text, zen_min, zen_max, "Дзен")
        
        if not is_valid:
            return None
        
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
            
            # Получаем тему с умной ротацией
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            logger.info(f"📏 Лимиты: Telegram {tg_min}-{tg_max}, Дзен {zen_min}-{zen_max}")
            
            # ШАГ 1: Генерация Telegram поста
            logger.info("\n📱 ГЕНЕРАЦИЯ TELEGRAM ПОСТА")
            tg_prompt = self.create_telegram_prompt(theme, slot_info, text_format)
            tg_text_raw = self.generate_single_post(tg_prompt, tg_min, tg_max, "Telegram пост")
            
            if not tg_text_raw:
                logger.error("❌ Не удалось сгенерировать Telegram пост")
                return False
            
            # Форматируем и проверяем Telegram
            tg_text = self.format_telegram_text(tg_text_raw, slot_info)
            if not tg_text:
                logger.error("❌ Telegram текст не прошел финальную проверку")
                return False
            
            logger.info(f"✅ Telegram готов: {len(tg_text)} символов")
            
            # ШАГ 2: Генерация Дзен поста
            logger.info("\n📰 ГЕНЕРАЦИЯ ДЗЕН ПОСТА")
            zen_prompt = self.create_zen_prompt(theme, slot_info, text_format)
            zen_text_raw = self.generate_single_post(zen_prompt, zen_min, zen_max, "Дзен пост")
            
            if not zen_text_raw:
                logger.error("❌ Не удалось сгенерировать Дзен пост")
                return False
            
            # Форматируем и проверяем Дзен
            zen_text = self.format_zen_text(zen_text_raw, slot_info)
            if not zen_text:
                logger.error("❌ Дзен текст не прошел финальную проверку")
                return False
            
            logger.info(f"✅ Дзен готов: {len(zen_text)} символов")
            
            # ФИНАЛЬНАЯ ПРОВЕРКА
            logger.info(f"\n📊 ФИНАЛЬНАЯ ПРОВЕРКА:")
            logger.info(f"   Telegram: {len(tg_text)} символов ({tg_min}-{tg_max} ✓)")
            logger.info(f"   Дзен: {len(zen_text)} символов ({zen_min}-{zen_max} ✓)")
            
            # Абсолютная гарантия
            if not (tg_min <= len(tg_text) <= tg_max):
                logger.error(f"❌ КРИТИЧНО: Telegram вне лимитов: {len(tg_text)}")
                return False
            
            if not (zen_min <= len(zen_text) <= zen_max):
                logger.error(f"❌ КРИТИЧНО: Дзен вне лимитов: {len(zen_text)}")
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
                logger.info(f"   🎯 Тема: {theme} (ротация активна)")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Telegram: {len(tg_text)} символов ({tg_min}-{tg_max} ✓)")
                logger.info(f"   📏 Дзен: {len(zen_text)} символов ({zen_min}-{zen_max} ✓)")
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
        print(f"🎯 Система ротации тем: одинаковые темы не будут идти подряд")
        print(f"🔄 Пошаговая генерация с умной корректировкой")
        
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
            print("✅ ТЕСТ ПРОЙДЕН! Текст соответствует лимитам.")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН (текст не соответствует лимитам)")
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
