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
        
        # Эмодзи для Telegram
        self.tg_emojis = ["📊", "💡", "🎯", "🔥", "✨", "⚡", "🚀", "💎", "🏆", "👑", "💼", "📈", "🤔", "💬", "👥", "🎪", "📌", "🔍", "📝", "🎨"]
        
        # Хэштеги по темам
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#кадры", 
                "#команда", "#лидерство", "#мотивация", "#развитиеперсонала",
                "#бизнес", "#управление", "#работа", "#карьера"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#продвижение", 
                "#брендинг", "#соцсети", "#медиа", "#пиар", 
                "#общение", "#публичность", "#репутация", "#инфоповод"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", 
                "#ремонтквартир", "#строитель", "#отделка", "#ремонтдома",
                "#стройматериалы", "#проект", "#ремонтподключ", "#евроремонт"
            ]
        }
        
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
        
        # Закрывающие фразы для Дзен
        self.zen_closings = [
            "━\nЧто думаете по этому поводу? 👇",
            "━\nЖду ваших комментариев! 👇",
            "━\nА как у вас с этим? 👇",
            "━\nПоделитесь своим опытом в комментариях! 👇",
            "━\nВаше мнение важно — напишите в комментариях! 👇",
            "━\nБуду рад обсудить в комментариях! 👇",
            "━\nЖду ваших историй и мнений ниже! 👇"
        ]
        
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
            if not self.post_history:
                self.post_history = {"theme_rotation": []}
            
            if "theme_rotation" not in self.post_history:
                self.post_history["theme_rotation"] = []
            
            theme_rotation = self.post_history.get("theme_rotation", [])
            
            if not theme_rotation:
                theme = random.choice(self.themes)
                self.current_theme = theme
                logger.info(f"🎯 Выбрана тема (первая): {theme}")
                return theme
            
            last_theme = theme_rotation[-1] if theme_rotation else None
            available_themes = [t for t in self.themes if t != last_theme]
            
            if not available_themes:
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_rotation):
                    for theme in self.themes:
                        if theme == used_theme:
                            theme_counts[theme] += 1
                theme = min(theme_counts, key=theme_counts.get)
            else:
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

    def get_relevant_hashtags(self, theme, count=3):
        """Возвращает релевантные хэштеги для темы"""
        hashtags = self.hashtags_by_theme.get(theme, [])
        if len(hashtags) >= count:
            return random.sample(hashtags, count)
        return hashtags[:count] if hashtags else ["#бизнес", "#советы", "#развитие"]

    def create_telegram_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Telegram поста с ЖЕСТКИМИ ограничениями"""
        tg_min, tg_max = slot_info['tg_chars']
        slot_time = None
        for time_key, info in self.schedule.items():
            if info == slot_info:
                slot_time = time_key
                break
        
        # Выбираем случайные эмодзи для Telegram
        selected_emojis = random.sample(self.tg_emojis, 3)
        emoji_line = ' '.join(selected_emojis)
        
        # Получаем релевантные хэштеги для темы
        hashtags = self.get_relevant_hashtags(theme, 3)
        hashtags_str = ' '.join(hashtags)
        
        # Рассчитываем примерное количество слов
        avg_word_length = 6
        words_min = int(tg_min / avg_word_length)
        words_max = int(tg_max / avg_word_length)
        
        prompt = f"""СОЗДАЙ TELEGRAM ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
ЖЕСТКОЕ ОГРАНИЧЕНИЕ ДЛИНЫ: от {tg_min} до {tg_max} символов ВКЛЮЧИТЕЛЬНО
ПРИМЕРНО: {words_min}-{words_max} слов

🔴 КРИТИЧЕСКИ ВАЖНО: Длина поста ДОЛЖНА БЫТЬ РОВНО от {tg_min} до {tg_max} символов. 
Если текст длиннее {tg_max} символов — УДАЛИ лишнее.
Если текст короче {tg_min} символов — ДОБАВЬ деталей.
ПЕРЕД отправкой ПОДСЧИТАЙ символы!

СТРУКТУРА (жёстко соблюдай):
1. {slot_info['emoji']} Цепляющая первая фраза с эмодзи
2. 1-2 коротких абзаца (по 2-3 предложения каждый) 
3. Один четкий вывод
4. Один конкретный вопрос к читателям
5. {emoji_line} (эмодзи для акцента)
6. Хэштеги: {hashtags_str}

КОЛИЧЕСТВО СИМВОЛОВ ПО ЭЛЕМЕНТАМ:
• Заголовок: 30-50 символов
• Абзац 1: 100-150 символов  
• Абзац 2: 100-150 символов
• Вывод: 50-80 символов
• Вопрос: 40-70 символов
• Хэштеги: 20-40 символов

ПРИМЕР структуры ({tg_min}-{tg_max} символов, УЖЕ ПОДСЧИТАНО):
{slot_info['emoji']} Заголовок/первая фраза 💡

Первый абзац из 2-3 предложений 📊

Второй абзац из 2-3 предложений с эмодзи 🚀

Вывод одним предложением ✅

Вопрос к читателям? 🤔

{emoji_line}
{hashtags_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОЗДАЙ ТЕКСТ, КОТОРЫЙ БУДЕТ РОВНО {tg_min}-{tg_max} СИМВОЛОВ.
ПОДСЧИТАЙ СИМВОЛЫ ПЕРЕД ОТВЕТОМ!

ТВОЙ ПОСТ (только текст):"""

        return prompt

    def create_zen_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Дзен поста с ЖЕСТКИМИ ограничениями"""
        zen_min, zen_max = slot_info['zen_chars']
        
        # Выбираем случайную закрывающую фразу
        closing = random.choice(self.zen_closings)
        
        # Получаем релевантные хэштеги для темы (для Дзена можно больше)
        hashtags = self.get_relevant_hashtags(theme, 4)
        hashtags_str = ' '.join(hashtags)
        
        # Рассчитываем примерное количество слов
        avg_word_length = 6
        words_min = int(zen_min / avg_word_length)
        words_max = int(zen_max / avg_word_length)
        
        prompt = f"""СОЗДАЙ ДЗЕН ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
ЖЕСТКОЕ ОГРАНИЧЕНИЕ ДЛИНЫ: от {zen_min} до {zen_max} символов ВКЛЮЧИТЕЛЬНО
ПРИМЕРНО: {words_min}-{words_max} слов

🔴 КРИТИЧЕСКИ ВАЖНО: Длина поста ДОЛЖНА БЫТЬ РОВНО от {zen_min} до {zen_max} символов. 
Если текст длиннее {zen_max} символов — УДАЛИ лишнее.
Если текст короче {zen_min} символов — ДОБАВЬ деталей.
ПЕРЕД отправкой ПОДСЧИТАЙ символы!

СТРУКТУРА (жёстко соблюдай):
1. Заголовок (без эмодзи, 1 строка)
2. 2-3 информативных абзаца (по 3-4 предложения)
3. Один четкий вывод
4. Вопрос для обсуждения
5. {closing}
6. Релевантные хэштеги: {hashtags_str}

КОЛИЧЕСТВО СИМВОЛОВ ПО ЭЛЕМЕНТАМ:
• Заголовок: 30-60 символов
• Абзац 1: 150-200 символов
• Абзац 2: 150-200 символов  
• Абзац 3: 150-200 символов
• Вывод: 60-100 символов
• Вопрос: 50-80 символов
• Хэштеги: 30-60 символов

ВАЖНО ДЛЯ ДЗЕН: 
• НЕ используй эмодзи в основном тексте
• Используй релевантные хэштеги по теме "{theme}"
• Текст должен быть информативным, но лаконичным

ПРИМЕР структуры ({zen_min}-{zen_max} символов, УЖЕ ПОДСЧИТАНО):
Заголовок статьи

Первый абзац из 3-4 предложений. Раскрывает основную мысль.

Второй абзац из 3-4 предложений. Дает примеры или объяснения.

Третий абзац из 3-4 предложений. Подводит к выводу.

Вывод статьи одним-двумя предложениями.

Вопрос для обсуждения с читателями.

{closing}
{hashtags_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОЗДАЙ ТЕКСТ, КОТОРЫЙ БУДЕТ РОВНО {zen_min}-{zen_max} СИМВОЛОВ.
ПОДСЧИТАЙ СИМВОЛЫ ПЕРЕД ОТВЕТОМ!

ТВОЙ ПОСТ (только текст, без эмодзи в основном тексте):"""

        return prompt

    def _smart_adjust_text(self, text, target_min, target_max, text_type, max_attempts=2):
        """
        Умная корректировка текста с ЖЕСТКИМИ ограничениями
        """
        current_len = len(text)
        
        if target_min <= current_len <= target_max:
            return text
        
        logger.info(f"🔄 Корректируем {text_type}: {current_len} → {target_min}-{target_max}")
        
        for attempt in range(max_attempts):
            try:
                if current_len > target_max:
                    # Жесткое сокращение
                    excess_percent = ((current_len - target_max) / target_max) * 100
                    
                    if excess_percent > 50:
                        instruction = f"Сократи этот текст ДО {target_max} символов. Удали ВСЕ лишнее: повторы, вводные слова, избыточные описания. Оставь только суть."
                    elif excess_percent > 20:
                        instruction = f"Сократи текст до {target_max} символов. Упрости формулировки, объедини предложения, удали второстепенное."
                    else:
                        instruction = f"Сократи текст до {target_max} символов. Сделай минимальные правки."
                else:
                    # Добавление контента
                    missing_percent = ((target_min - current_len) / target_min) * 100
                    
                    if missing_percent > 50:
                        instruction = f"Дополни текст до {target_min} символов. Добавь конкретные примеры, кейсы, практические советы по теме."
                    elif missing_percent > 20:
                        instruction = f"Дополни текст до {target_min} символов. Раскрой ключевые моменты подробнее, добавь детали."
                    else:
                        instruction = f"Дополни текст до {target_min} символов. Добавь уточняющие фразы."
                
                adjust_prompt = f"""Скорректируй длину текста:

ТЕКСТ:
{text}

ИНСТРУКЦИЯ: {instruction}

ТЕКУЩАЯ ДЛИНА: {current_len} символов
ЦЕЛЕВАЯ ДЛИНА: РОВНО {target_min}-{target_max} символов

🔴 ВАЖНО: Результат ДОЛЖЕН быть от {target_min} до {target_max} символов.
ПОДСЧИТАЙ символы в своем ответе!

Отредактированный текст (только текст, без пояснений):"""
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
                
                # Точный расчет токенов
                max_tokens = min(int(target_max * 1.2), 2000)
                
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
                        
                        logger.info(f"📊 Попытка {attempt+1}: {new_len} символов")
                        
                        if target_min <= new_len <= target_max:
                            logger.info(f"✅ {text_type} успешно откорректирован")
                            return adjusted_text
                        else:
                            # Пробуем еще раз с более жесткими инструкциями
                            text = adjusted_text
                            current_len = new_len
                else:
                    logger.warning(f"⚠️ Ошибка API при корректировке: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при корректировке (попытка {attempt+1}): {str(e)[:100]}")
        
        logger.warning(f"⚠️ Не удалось откорректировать {text_type} за {max_attempts} попыток")
        
        # Если не удалось откорректировать, пробуем жестко обрезать/дополнить
        if current_len > target_max:
            logger.warning(f"⚠️ Принудительно обрезаем {text_type} до {target_max} символов")
            return text[:target_max].rsplit(' ', 1)[0] + "..."  # Обрезаем до последнего целого слова
        elif current_len < target_min:
            logger.warning(f"⚠️ {text_type} слишком короткий, возвращаем как есть")
            return text
        
        return text

    def generate_single_post(self, prompt, target_chars_min, target_chars_max, post_type):
        """Генерирует ОДИН пост с ЖЕСТКИМИ проверками"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            # Жесткое ограничение токенов
            max_tokens = min(int(target_chars_max * 1.3), 2500)
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.6,
                    "topK": 40,
                    "maxOutputTokens": max_tokens,
                }
            }
            
            logger.info(f"🤖 Генерация {post_type} ({target_chars_min}-{target_chars_max} символов)")
            response = session.post(url, json=data, timeout=40)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    length = len(generated_text)
                    
                    logger.info(f"📊 {post_type}: {length} символов (нужно {target_chars_min}-{target_chars_max})")
                    
                    # ЖЕСТКАЯ проверка
                    if not (target_chars_min <= length <= target_chars_max):
                        logger.warning(f"⚠️ {post_type} не соответствует длине, корректируем...")
                        generated_text = self._smart_adjust_text(
                            generated_text, 
                            target_chars_min, 
                            target_chars_max,
                            post_type,
                            max_attempts=2
                        )
                    
                    # Финальная проверка
                    final_length = len(generated_text)
                    if not (target_chars_min <= final_length <= target_chars_max):
                        logger.error(f"❌ {post_type} после корректировки: {final_length} символов (вне лимитов)")
                        return None
                    
                    logger.info(f"✅ {post_type} готов: {final_length} символов")
                    return generated_text
                else:
                    logger.error(f"❌ Нет кандидатов в ответе API для {post_type}")
                    return None
            
            logger.error(f"❌ Ошибка API при генерации {post_type}: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при генерации {post_type}: {e}")
            return None

    def strict_length_validation(self, text, min_chars, max_chars, text_type):
        """ЖЕСТКАЯ валидация длины"""
        if not text:
            logger.error(f"❌ {text_type} текст пустой")
            return False, 0
        
        text_length = len(text)
        
        # НУЛЕВОЙ допуск
        if text_length < min_chars:
            logger.error(f"❌ {text_type} текст слишком короткий: {text_length} < {min_chars}")
            return False, text_length
        
        if text_length > max_chars:
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
        
        default_image = "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"
        logger.info(f"🖼️ Используем дефолтную картинку")
        return default_image

    def enhance_telegram_emojis(self, text):
        """Добавляет больше эмодзи в Telegram текст"""
        if not text:
            return text
        
        # Упрощенный словарь для ключевых слов
        emoji_map = {
            r'\bуспех\b': '✅',
            r'\bпроблем\b': '⚠️',
            r'\bважн\b': '❗',
            r'\bсовет\b': '💡',
            r'\bпример\b': '📌',
            r'\bрезультат\b': '📊',
            r'\bрост\b': '📈',
            r'\bиде\b': '💎',
            r'\bрешен\b': '🔧',
            r'\bвопрос\b': '❓',
            r'\bответ\b': '💬',
            r'\bкоманда\b': '👥',
            r'\bопыт\b': '🎓',
            r'\bзнан\b': '🧠',
            r'\bвремя\b': '⏰',
            r'\bденьги\b': '💰',
            r'\bцель\b': '🎯',
            r'\bстратег\b': '♟️',
            r'\bплан\b': '🗺️',
            r'\bначал\b': '🚀',
            r'\bзаверш\b': '🏁',
            r'\bвывод\b': '📝',
            r'\bанализ\b': '🔍',
            r'\bданн\b': '📊',
            r'\bтренд\b': '📉',
            r'\bбудущ\b': '🔮',
            r'\bинновац\b': '⚡',
            r'\bтехнолог\b': '🤖',
            r'\bэффектив\b': '⚡',
            r'\bкачеств\b': '⭐',
            r'\bконтроль\b': '🎛️',
            r'\bуправлен\b': '🎮',
            r'\bлидер\b': '👑',
            r'\bсотрудник\b': '👨‍💼',
            r'\bклиент\b': '🤝',
            r'\bрынок\b': '🌐',
            r'\bконкурен\b': '⚔️',
            r'\bпреимуществ\b': '🏆',
            r'\bриск\b': '🎲',
            r'\bбезопасн\b': '🛡️',
            r'\bсложн\b': '🎪',
            r'\bпрост\b': '✨',
            r'\bясн\b': '🔆',
            r'\bпонятн\b': '💡',
            r'\bсистем\b': '🔧',
            r'\bпроцесс\b': '🔄',
            r'\bэтап\b': '📍',
            r'\bуровен\b': '📶',
            r'\bструктур\b': '🏢',
            r'\bинструмент\b': '🛠️',
            r'\bметод\b': '🔬',
            r'\bподход\b': '🎯',
            r'\bстиль\b': '🎨',
            r'\bсмысл\b': '💎',
            r'\bценност\b': '💎',
            r'\bпринцип\b': '⚖️',
            r'\bправил\b': '📜',
            r'\bожидан\b': '👀',
            r'\bпрактик\b': '🔧',
            r'\bтеори\b': '📚',
            r'\bобучен\b': '🎓',
            r'\bразвит\b': '🌱',
            r'\bпрогресс\b': '📈',
            r'\bулучшен\b': '✨',
            r'\bоптимизац\b': '⚡',
            r'\bизменен\b': '🔄',
            r'\bдостижен\b': '🏆',
            r'\bпобеда\b': '🏆',
            r'\bнаград\b': '🏅',
            r'\bрепутац\b': '👑',
            r'\bимидж\b': '🎭',
            r'\bбренд\b': '🏷️',
            r'\bуникальн\b': '💎',
            r'\bособенн\b': '🌟',
            r'\bдетал\b': '🔍',
            r'\bглубин\b': '🌊',
            r'\bсуть\b': '💎',
            r'\bоснов\b': '🏗️',
            r'\bглавн\b': '👑',
            r'\bключев\b': '🔑',
            r'\bрешающ\b': '⚡',
            r'\bкритичн\b': '🚨',
            r'\bприоритет\b': '1️⃣',
            r'\bлогик\b': '🧩',
            r'\bэмоц\b': '💖',
            r'\bкоммуникац\b': '💬',
            r'\bобщен\b': '🗣️',
            r'\bдиалог\b': '💬',
            r'\bобсужден\b': '🗣️',
            r'\bсоглашен\b': '🤝',
            r'\bкомпромисс\b': '⚖️',
            r'\bгармони\b': '🎵',
            r'\bбаланс\b': '⚖️',
            r'\bстабильн\b': '⚓',
            r'\bнадежн\b': '🔒',
            r'\bдовер\b': '🤝',
            r'\bответствен\b': '📝',
            r'\bмотивац\b': '🔥',
            r'\bвдохновен\b': '✨',
            r'\bэнерг\b': '⚡',
            r'\bактивн\b': '🏃',
            r'\bинициатив\b': '💡',
            r'\bкреатив\b': '🎨',
            r'\bтворчеств\b': '🎭',
            r'\bцель\b': '🎯',
            r'\bамбиц\b': '👑',
            r'\bстремлен\b': '🚀',
            r'\bтруд\b': '🛠️',
            r'\bработ\b': '👨‍💼',
            r'\bзадач\b': '📋',
            r'\bпроект\b': '📂',
            r'\bфункц\b': '⚙️',
            r'\bрол\b': '🎭',
            r'\bпрофесс\b': '🎓',
            r'\bнавык\b': '🔧',
            r'\bумени\b': '🎯',
            r'\bкомпетенц\b': '🏆',
            r'\bэксперт\b': '👨‍🔬',
            r'\bспециалист\b': '👨‍💻',
            r'\bтренер\b': '🏋️',
            r'\bментор\b': '🧑‍🏫',
            r'\bкоуч\b': '🎯',
            r'\bконсультант\b': '💼',
            r'\bподдержк\b': '🤗',
            r'\bнаблюден\b': '👁️',
            r'\bмониторинг\b': '📊',
            r'\bконтрол\b': '🎛️',
            r'\bпроверк\b': '🔍',
            r'\bоценк\b': '⭐',
            r'\bтестирован\b': '🧪',
            r'\bразрешен\b': '✅',
            r'\bодобрен\b': '👍',
            r'\bограничен\b': '🚫',
            r'\bзапрет\b': '⛔',
            r'\bинструкц\b': '📋',
            r'\bруководств\b': '🗺️',
            r'\bалгоритм\b': '🔢',
            r'\bплан\b': '🗺️',
            r'\bпуть\b': '🛤️',
            r'\bнаправлен\b': '🧭',
            r'\bдвижен\b': '🏃',
        }
        
        lines = text.split('\n')
        enhanced_lines = []
        
        for line in lines:
            enhanced_line = line
            if line.strip() and not line.strip().startswith('#') and len(line.strip()) > 10:
                # Добавляем эмодзи в конец строки (кроме хэштегов)
                for pattern, emoji in emoji_map.items():
                    if re.search(pattern, line.lower()):
                        # Проверяем, нет ли уже эмодзи в конце
                        if not line.strip().endswith(emoji):
                            enhanced_line = f"{line.strip()} {emoji}"
                        break
            enhanced_lines.append(enhanced_line)
        
        return '\n'.join(enhanced_lines)

    def ensure_relevant_hashtags(self, text, theme, platform="zen"):
        """Добавляет релевантные хэштеги если их нет в тексте"""
        if not text:
            return text
        
        # Проверяем есть ли уже хэштеги
        hashtag_pattern = r'#\w+'
        existing_hashtags = re.findall(hashtag_pattern, text)
        
        # Если хэштегов нет или их мало
        if len(existing_hashtags) < 2:
            # Получаем релевантные хэштеги для темы
            if platform == "zen":
                relevant_hashtags = self.get_relevant_hashtags(theme, 4)
            else:
                relevant_hashtags = self.get_relevant_hashtags(theme, 3)
            
            # Добавляем только те хэштеги, которых еще нет в тексте
            new_hashtags = [ht for ht in relevant_hashtags if ht not in existing_hashtags]
            
            if new_hashtags:
                # Добавляем хэштеги в конец текста
                hashtags_str = ' '.join(new_hashtags[:3])
                if not text.strip().endswith('\n'):
                    text += '\n\n'
                text += hashtags_str
        
        return text

    def format_telegram_text(self, text, slot_info):
        """Форматирует текст для Telegram с улучшенными эмодзи"""
        if not text:
            return None
        
        text = text.strip()
        
        # Добавляем стартовый эмодзи слота если его нет
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U0001F251" 
            "]+", flags=re.UNICODE)
        
        if not text.startswith(slot_info['emoji']):
            lines = text.split('\n')
            if lines and lines[0].strip():
                lines[0] = f"{slot_info['emoji']} {lines[0]}"
                text = '\n'.join(lines)
        
        # Улучшаем эмодзи в тексте
        text = self.enhance_telegram_emojis(text)
        
        # Проверяем и добавляем релевантные хэштеги
        if self.current_theme:
            text = self.ensure_relevant_hashtags(text, self.current_theme, "telegram")
        
        # ЖЕСТКАЯ проверка длины
        tg_min, tg_max = slot_info['tg_chars']
        is_valid, length = self.strict_length_validation(text, tg_min, tg_max, "Telegram")
        
        if not is_valid:
            return None
        
        return text.strip()

    def format_zen_text(self, text, slot_info):
        """Форматирует текст для Дзен с закрывающей фразой и релевантными хэштегами"""
        if not text:
            return None
        
        text = text.strip()
        
        # Удаляем все эмодзи из основного текста
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U0001F251" 
            "]+", flags=re.UNICODE)
        
        # Разделяем на строки и обрабатываем
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            # Пропускаем строки с хэштегами (там могут быть эмодзи в закрывающей фразе)
            if line.strip().startswith('#'):
                cleaned_lines.append(line)
            else:
                # Удаляем эмодзи только из не-хэштег строк
                cleaned_line = emoji_pattern.sub('', line)
                cleaned_lines.append(cleaned_line.strip())
        
        text = '\n'.join(cleaned_lines)
        
        # Добавляем закрывающую фразу если ее нет
        has_closing = any(closing in text for closing in self.zen_closings)
        if not has_closing:
            closing = random.choice(self.zen_closings)
            text = f"{text}\n\n{closing}"
        
        # Проверяем и добавляем релевантные хэштеги для Дзен
        if self.current_theme:
            text = self.ensure_relevant_hashtags(text, self.current_theme, "zen")
        
        # ЖЕСТКАЯ проверка длины
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
        """Отправляет уведомление администратору"""
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
        """Генерирует и отправляет посты для указанного слота с ЖЕСТКИМИ ограничениями"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_info['name']}")
            logger.info(f"🔴 ЖЕСТКИЕ ОГРАНИЧЕНИЯ: Telegram {slot_info['tg_chars'][0]}-{slot_info['tg_chars'][1]}, Дзен {slot_info['zen_chars'][0]}-{slot_info['zen_chars'][1]}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
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
            
            tg_text = self.format_telegram_text(tg_text_raw, slot_info)
            if not tg_text:
                logger.error("❌ Telegram текст не прошел финальную проверку")
                return False
            
            tg_length = len(tg_text)
            logger.info(f"✅ Telegram готов: {tg_length} символов ({tg_min}-{tg_max} {'✓' if tg_min <= tg_length <= tg_max else '✗'})")
            
            # ШАГ 2: Генерация Дзен поста
            logger.info("\n📰 ГЕНЕРАЦИЯ ДЗЕН ПОСТА")
            zen_prompt = self.create_zen_prompt(theme, slot_info, text_format)
            zen_text_raw = self.generate_single_post(zen_prompt, zen_min, zen_max, "Дзен пост")
            
            if not zen_text_raw:
                logger.error("❌ Не удалось сгенерировать Дзен пост")
                return False
            
            zen_text = self.format_zen_text(zen_text_raw, slot_info)
            if not zen_text:
                logger.error("❌ Дзен текст не прошел финальную проверку")
                return False
            
            zen_length = len(zen_text)
            logger.info(f"✅ Дзен готов: {zen_length} символов ({zen_min}-{zen_max} {'✓' if zen_min <= zen_length <= zen_max else '✗'})")
            
            # ФИНАЛЬНАЯ ЖЕСТКАЯ ПРОВЕРКА
            logger.info(f"\n🔴 ФИНАЛЬНАЯ ЖЕСТКАЯ ПРОВЕРКА:")
            tg_ok = tg_min <= tg_length <= tg_max
            zen_ok = zen_min <= zen_length <= zen_max
            
            logger.info(f"   Telegram: {tg_length} символов ({tg_min}-{tg_max}) {'✅' if tg_ok else '❌'}")
            logger.info(f"   Дзен: {zen_length} символов ({zen_min}-{zen_max}) {'✅' if zen_ok else '❌'}")
            
            if not tg_ok:
                logger.error(f"❌ КРИТИЧНО: Telegram вне лимитов: {tg_length}")
                return False
            
            if not zen_ok:
                logger.error(f"❌ КРИТИЧНО: Дзен вне лимитов: {zen_length}")
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
                logger.info(f"   📏 Telegram: {tg_length} символов ({tg_min}-{tg_max} ✅)")
                logger.info(f"   📏 Дзен: {zen_length} символов ({zen_min}-{zen_max} ✅)")
                # Выводим использованные хэштеги
                tg_hashtags = re.findall(r'#\w+', tg_text)
                zen_hashtags = re.findall(r'#\w+', zen_text)
                if tg_hashtags:
                    logger.info(f"   🔖 Telegram хэштеги: {' '.join(tg_hashtags[:3])}")
                if zen_hashtags:
                    logger.info(f"   🔖 Дзен хэштеги: {' '.join(zen_hashtags[:4])}")
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
        print(f"🔖 Релевантные хэштеги для каждой темы")
        print(f"🔴 ЖЕСТКИЕ ОГРАНИЧЕНИЯ ДЛИНЫ: модель будет перегенерировать текст до соответствия")
        
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
