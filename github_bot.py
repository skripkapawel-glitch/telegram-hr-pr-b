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
                "themes_used": [],
                "theme_rotation": []  # Для отслеживания ротации тем
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
        except:
            pass

    def get_smart_theme(self):
        """Выбирает тему с умной ротацией - НЕ повторяем темы подряд"""
        try:
            # Получаем историю тем
            theme_history = self.post_history.get("theme_rotation", [])
            
            # Если история пустая, берем случайную тему
            if not theme_history:
                theme = random.choice(self.themes)
                self.current_theme = theme
                logger.info(f"🎯 Выбрана тема (первая): {theme}")
                return theme
            
            # Получаем последнюю использованную тему
            last_theme = theme_history[-1] if theme_history else None
            
            # Создаем список доступных тем (исключаем последнюю использованную)
            available_themes = [t for t in self.themes if t != last_theme]
            
            # Если все темы использовались, берем ту, которая давно не использовалась
            if not available_themes:
                # Ищем тему, которая дольше всего не использовалась
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_history):
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
        """Создает промпт для Gemini с МАКСИМАЛЬНО СТРОГИМИ требованиями"""
        
        # Определяем стиль по времени
        time_styles = {
            "09:00": "мотивация, фокус и энерго-старт",
            "14:00": "аналитика, рациональность, польза",
            "19:00": "истории, личные выводы, рефлексия"
        }
        
        # Находим ключ слота времени
        slot_time = None
        for time_key, info in self.schedule.items():
            if info == slot_info:
                slot_time = time_key
                break
        
        if not slot_time:
            slot_time = "19:00"
            
        time_style = time_styles.get(slot_time, "истории, личные выводы, рефлексия")
        
        tg_min, tg_max = slot_info['tg_chars']
        zen_min, zen_max = slot_info['zen_chars']
        
        # Рассчитываем идеальные длины
        tg_ideal = (tg_min + tg_max) // 2
        zen_ideal = (zen_min + zen_max) // 2
        
        prompt = f"""# ============== СТРОГОЕ ТЕХНИЧЕСКОЕ ЗАДАНИЕ ==============

# 🔴 КРИТИЧЕСКИ ВАЖНЫЕ ТРЕБОВАНИЯ К ЛИМИТАМ СИМВОЛОВ 🔴

Ты ДОЛЖЕН создать ДВА текста с ТОЧНЫМ количеством символов:

1. Telegram пост: ДОЛЖЕН быть ОТ {tg_min} ДО {tg_max} символов
   • МИНИМУМ: {tg_min} символов
   • МАКСИМУМ: {tg_max} символов  
   • ИДЕАЛЬНО: около {tg_ideal} символов
   • ПРОВЕРКА: len(text) >= {tg_min} and len(text) <= {tg_max}

2. Дзен пост: ДОЛЖЕН быть ОТ {zen_min} ДО {zen_max} символов
   • МИНИМУМ: {zen_min} символов
   • МАКСИМУМ: {zen_max} символов
   • ИДЕАЛЬНО: около {zen_ideal} символов
   • ПРОВЕРКА: len(text) >= {zen_min} and len(text) <= {zen_max}

# ❗️ ЕСЛИ ТЫ НЕ СОБЛЮДЕШЬ ЭТИ ЛИМИТЫ - ТЕКСТ БУДЕТ УДАЛЕН ❗️
# ❗️ НИКАКИХ ИСКЛЮЧЕНИЙ, НИКАКИХ ПРИБЛИЗИТЕЛЬНЫХ ЗНАЧЕНИЙ ❗️

🎭 РОЛЬ NEURO AI
Ты — синтез из лучших специалистов с 30+ годами опыта:
• Промтмейкер • Копирайтер-редактор • SMM-стратег 
• Контент-мейкер • Продюсер и медиадиректор • Аналитик трендов
• Сторителлер и упаковщик смыслов

🎯 ТЕКУЩАЯ ЗАДАЧА
Тема: {theme}
Время публикации: {slot_time} МСК ({time_style})
Формат подачи: {text_format}

📌 КЛЮЧЕВЫЕ ТРЕБОВАНИЯ:
1. Telegram: {tg_min}-{tg_max} символов (len() = от {tg_min} до {tg_max})
2. Дзен: {zen_min}-{zen_max} символов (len() = от {zen_min} до {zen_max})
3. ДВА РАЗНЫХ текста для разных платформ
4. Соблюдать структуру для каждой платформы
5. Добавить мягкий вовлекающий финал

⏰ СТИЛЬ ПО ВРЕМЕНИ ({slot_time}):
{time_style}

📋 ФОРМАТ ПОДАЧИ: {text_format}

🧱 СТРУКТУРА TELEGRAM (@da4a_hr):
• Эмодзи обязательны
• Крючок (цепляющая первая строка)
• 1–3 смысловых абзаца  
• Мини-вывод
• Мягкий финал с вопросом
• Хэштеги в конце
• [Картинка: …]

🧱 СТРУКТУРА ДЗЕН (@tehdzenm):
• Эмодзи ЗАПРЕЩЕНЫ
• Заголовок
• 2–4 раскрывающих абзаца
• Мини-вывод
• Мягкий финал с вопросом
• Хэштеги в конце
• [Картинка: …]

🌿 МЯГКИЙ ФИНАЛ (ОБЯЗАТЕЛЕН):
• Вопрос для вовлечения
• Приглашение поделиться
• Примеры: "Что думаете?", "А как у вас?", "Поделитесь опытом"

# ============== АЛГОРИТМ ПРОВЕРКИ ==============

ПОСЛЕ СОЗДАНИЯ КАЖДОГО ТЕКСТА ТЫ ДОЛЖЕН:

1. Взять текст и посчитать символы: len(text)
2. Для Telegram: проверить что {tg_min} <= len(text) <= {tg_max}
3. Для Дзен: проверить что {zen_min} <= len(text) <= {zen_max}
4. Если не соответствует - ПЕРЕПИСАТЬ текст
5. Убедиться, что тексты РАЗНЫЕ для разных платформ

# ============== ПРИМЕР РАСЧЕТА ==============

Если Telegram должен быть 400-600 символов:
• ХОРОШО: 450, 500, 550 символов
• ПЛОХО: 399 символов (мало), 601 символ (много), 650 символов (много)

Если Дзен должен быть 600-700 символов:
• ХОРОШО: 620, 650, 680 символов  
• ПЛОХО: 599 символов (мало), 701 символ (много), 750 символов (много)

# ============== ФОРМАТ ВЫВОДА ==============

Строго соблюдай этот формат:

TG:
[Текст для Telegram, ТОЧНО {tg_min}-{tg_max} символов, с эмодзи]
---
DZEN:
[Текст для Дзен, ТОЧНО {zen_min}-{zen_max} символов, без эмодзи]

# ============== ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ ==============

ЕСЛИ ТЫ НЕ МОЖЕШЬ СОЗДАТЬ ТЕКСТЫ С ТАКИМИ ЛИМИТАМИ:
1. Сначала создай черновик
2. Посчитай символы: len(текст)
3. Если мало - добавь деталей, примеров, пояснений
4. Если много - сократи, удали воду, оставь суть
5. Проверь снова
6. Повторяй пока не получится {tg_min}-{tg_max} для TG и {zen_min}-{zen_max} для Дзен

НИКАКИХ ОПРАВДАНИЙ. ТЫ МОЖЕШЬ ЭТО СДЕЛАТЬ.
"""

        logger.info(f"📝 Создан УЛЬТРАСТРОГИЙ промпт для Gemini")
        logger.info(f"📊 Параметры: Тема={theme}, Время={slot_time}, Формат={text_format}")
        logger.info(f"📏 АБСОЛЮТНЫЕ лимиты: TG={tg_min}-{tg_max}, Дзен={zen_min}-{zen_max}")
        logger.info(f"🎯 Целевые длины: TG~{tg_ideal}, Дзен~{zen_ideal}")
        return prompt

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API с актуальными моделями"""
        try:
            # Актуальные модели Gemini
            available_models = [
                "gemini-2.5-flash-preview-04-17",
                "gemini-2.5-pro-exp-03-25",
                "gemma-3-27b-it"
            ]
            
            for model_name in available_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                    
                    # Сверхстрогие настройки для точности
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.1,  # ОЧЕНЬ низкая температура для максимальной точности
                            "topP": 0.5,
                            "topK": 10,
                            "maxOutputTokens": 4000,
                            "responseMimeType": "text/plain"
                        },
                        "safetySettings": [
                            {
                                "category": "HARM_CATEGORY_HARASSMENT",
                                "threshold": "BLOCK_NONE"
                            }
                        ]
                    }
                    
                    logger.info(f"🤖 Пробуем модель: {model_name}")
                    response = session.post(url, json=data, timeout=90)  # Увеличил таймаут
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                            logger.info(f"✅ Текст сгенерирован моделью {model_name}")
                            logger.info(f"📊 Длина ответа: {len(generated_text)} символов")
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
        
        # Убираем возможные лишние символы в начале
        combined_text = combined_text.strip()
        
        # Ищем разделитель
        if "---" not in combined_text:
            logger.error("❌ В сгенерированном тексте нет разделителя ---")
            return None, None
        
        parts = combined_text.split("---", 1)
        if len(parts) != 2:
            logger.error("❌ Неправильный формат сгенерированного текста")
            return None, None
        
        tg_text = parts[0].strip()
        zen_part = parts[1].strip()
        
        # Убираем префиксы
        tg_text = re.sub(r'^(TG|Telegram):\s*', '', tg_text, flags=re.IGNORECASE | re.MULTILINE)
        tg_text = tg_text.strip()
        
        # Ищем начало Дзен текста
        if "DZEN:" in zen_part:
            zen_text = zen_part.split("DZEN:", 1)[1].strip()
        elif "Дзен:" in zen_part:
            zen_text = zen_part.split("Дзен:", 1)[1].strip()
        else:
            zen_text = zen_part.strip()
        
        # Убираем префиксы из Дзен текста
        zen_text = re.sub(r'^(DZEN|Дзен):\s*', '', zen_text, flags=re.IGNORECASE | re.MULTILINE)
        zen_text = zen_text.strip()
        
        logger.info(f"📊 Telegram текст: {len(tg_text)} символов")
        logger.info(f"📊 Дзен текст: {len(zen_text)} символов")
        
        return tg_text, zen_text

    def strict_length_validation(self, text, min_chars, max_chars, text_type):
        """Строгая валидация длины БЕЗ ИСПРАВЛЕНИЙ"""
        if not text:
            logger.error(f"❌ {text_type} текст пустой")
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

    def validate_and_fix_structure(self, text, is_telegram=True):
        """Валидирует структуру текста (только проверка, без исправлений)"""
        if not text:
            return text
        
        # Удаляем вступительные фразы
        text = re.sub(r'^(Вот|Держи|Пожалуйста|Смотри|Вот тебе|Я создал|Я подготовил|Как тебе|Привет|Здравствуйте|Хорошо|Так|Итак|Отлично).+?\n', '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Удаляем квадратные скобки
        text = re.sub(r'\[|\]', '', text)
        
        # Удаляем лишние пробелы
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()

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
        """Форматирует текст для Telegram (только минимальная очистка)"""
        if not text:
            return None
        
        # 1. Минимальная очистка
        text = self.validate_and_fix_structure(text, is_telegram=True)
        
        # 2. Удаляем следы форматов
        text = re.sub(r'^TG:\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^Telegram:\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        # 3. Добавляем эмодзи слота только если его нет
        if not text.startswith(slot_info['emoji']) and text.strip():
            lines = text.split('\n')
            if lines and lines[0].strip():
                lines[0] = f"{slot_info['emoji']} {lines[0]}"
                text = '\n'.join(lines)
        
        # 4. СТРОГАЯ проверка длины БЕЗ ИСПРАВЛЕНИЙ
        tg_min, tg_max = slot_info['tg_chars']
        is_valid, length = self.strict_length_validation(text, tg_min, tg_max, "Telegram")
        
        if not is_valid:
            logger.error(f"❌ Telegram текст отбракован: {length} символов (требуется {tg_min}-{tg_max})")
            return None
        
        return text.strip()

    def format_zen_text(self, text, slot_info):
        """Форматирует текст для Дзен (только минимальная очистка)"""
        if not text:
            return None
        
        # 1. Минимальная очистка
        text = self.validate_and_fix_structure(text, is_telegram=False)
        
        # 2. Удаляем следы форматов
        text = re.sub(r'^DZEN:\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^Дзен:\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        # 3. Удаляем эмодзи (если вдруг есть)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U0001F251" 
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        # 4. СТРОГАЯ проверка длины БЕЗ ИСПРАВЛЕНИЙ
        zen_min, zen_max = slot_info['zen_chars']
        is_valid, length = self.strict_length_validation(text, zen_min, zen_max, "Дзен")
        
        if not is_valid:
            logger.error(f"❌ Дзен текст отбракован: {length} символов (требуется {zen_min}-{zen_max})")
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
            
            # МИНИМАЛЬНАЯ обработка текста, НЕ исправляем длину!
            tg_text = self.format_telegram_text(tg_text_raw, slot_info)
            zen_text = self.format_zen_text(zen_text_raw, slot_info)
            
            # Если тексты не прошли валидацию по длине - ОТБРАКОВЫВАЕМ!
            if tg_text is None:
                logger.error("❌ Telegram текст отбракован - не соответствует лимитам символов")
                return False
            
            if zen_text is None:
                logger.error("❌ Дзен текст отбракован - не соответствует лимитам символов")
                return False
            
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            logger.info(f"📊 Длина текстов:")
            logger.info(f"   TG: {tg_length} символов (требуется {tg_min}-{tg_max})")
            logger.info(f"   DZEN: {zen_length} символов (требуется {zen_min}-{zen_max})")
            
            # Финальная проверка (на всякий случай)
            if tg_length < tg_min or tg_length > tg_max:
                logger.error(f"❌ КРИТИЧНО: Telegram текст не соответствует лимитам: {tg_length}")
                return False
            
            if zen_length < zen_min or zen_length > zen_max:
                logger.error(f"❌ КРИТИЧНО: Дзен текст не соответствует лимитам: {zen_length}")
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
                logger.info(f"   📏 Длина TG: {tg_length} символов (в пределах {tg_min}-{tg_max} ✓)")
                logger.info(f"   📏 Длина DZEN: {zen_length} символов (в пределах {zen_min}-{zen_max} ✓)")
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
        print(f"📏 АБСОЛЮТНЫЕ лимиты: Telegram {slot_info['tg_chars'][0]}-{slot_info['tg_chars'][1]} символов")
        print(f"📏 АБСОЛЮТНЫЕ лимиты: Дзен {slot_info['zen_chars'][0]}-{slot_info['zen_chars'][1]} символов")
        print(f"🎯 Система ротации тем: одинаковые темы не будут идти подряд")
        print(f"⚠️  Текст будет ОТБРАКОВАН, если не соответствует лимитам!")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            print(f"✅ Посты опубликованы в каналы в {slot_time} МСК")
        else:
            print(f"❌ Ошибка публикации постов (текст не соответствует лимитам)")
        
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
