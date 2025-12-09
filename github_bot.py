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
    logger.warning("⚠️ PEXELS_API_KEY не установлен! Будут использоваться дефолтные картинки")

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
print(f"✅ GEMINI_API_KEY: Установлен")
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
            "разбор ситуации или явления",
            "микро-исследование (данные, цифры, вывод)",
            "аналитическое наблюдение",
            "разбор ошибки и решение",
            "мини-история с выводом",
            "взгляд автора + расширение темы",
            "объяснение сложного простым языком",
            "элементы сторителлинга",
            "структурированные советы",
            "объяснение через аналогию",
            "демонстрация пользы",
            "анализ поведения аудитории",
            "выявление причин «почему так происходит»",
            "логичная цепочка: факт → пример → вывод",
            "список полезных шагов",
            "раскрытие одного сильного инсайта",
            "тихая эмоциональная подача (без ярких эмоций)",
            "сравнение разных подходов",
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
        """Создает промпт для Gemini"""
        
        system_prompt = """Ты — синтез из лучших специалистов: копирайтера, контент-мейкера, SMM-стратега, редактора с ощущением ритма текста, аналитика трендов и продюсера, который упаковывает мысли в живые форматы. У тебя 30+ лет опыта в контенте, медиа и коммуникациях. Твоя задача — создавать тексты, которые цепляют с первых строк и удерживают до последнего символа. Присылай посты уже в готовом виде, без "Вот пожалуйста держи и тд"."""
        
        format_instructions = {
            "разбор ситуации или явления": "Разбери конкретную ситуацию или явление в выбранной теме. Что происходит? Почему это важно? Какие последствия и выводы?",
            "микро-исследование (данные, цифры, вывод)": "Проведи микро-исследование по теме. Используй данные, цифры, статистику. Сделай выводы на основе этих данных.",
            "аналитическое наблюдение": "Поделись аналитическими наблюдениями по теме. Что ты заметил в практике? Какие закономерности и тренды?",
            "разбор ошибки и решение": "Выбери типичную ошибку в выбранной теме. Разбери почему она происходит, какие последствия и как её правильно решить.",
            "мини-история с выводом": "Расскажи мини-историю из практики по теме. История должна быть поучительной и заканчиваться четким выводом.",
            "взгляд автора + расширение темы": "Вырази своё авторское мнение по теме и расширь её, показав связи со смежными областями или глобальными трендами.",
            "объяснение сложного простым языком": "Возьми сложное понятие или процесс из темы и объясни его максимально простым языком с понятными примерами.",
            "элементы сторителлинга": "Используй элементы сторителлинга: создай персонажа, конфликт, развитие сюжета и разрешение в контексте выбранной темы.",
            "структурированные советы": "Дай конкретные, структурированные советы по теме. Разбей на четкие шаги, категории или принципы. Используй символ • для перечислений.",
            "объяснение через аналогию": "Объясни явление или процесс из темы через аналогию с чем-то знакомым и понятным обычному читателю.",
            "демонстрация пользы": "Покажи конкретную практическую пользу от применения знаний по теме. Что изменится, какие результаты можно получить.",
            "анализ поведения аудитории": "Проанализируй поведение людей (сотрудников, клиентов, аудитории) в контексте темы. Почему они так поступают?",
            "выявление причин «почему так происходит»": "Погрузись в глубинные причины явления в выбранной теме. Почему всё устроено именно так? Какие скрытые механизмы?",
            "логичная цепочка: факт → пример → вывод": "Используй логичную цепочку: приведи интересный факт, проиллюстрируй его конкретным примером, сделай практический вывод.",
            "список полезных шагов": "Создай список конкретных полезных шагов для решения проблемы или улучшения ситуации в выбранной теме. Используй символ • для перечислений.",
            "раскрытие одного сильного инсайта": "Сфокусируйся на одном мощном инсайте по теме. Раскрой его полностью, покажи все грани и практическое применение.",
            "тихая эмоциональная подача (без ярких эмоций)": "Используй сдержанную, глубокую подачу без излишней эмоциональности. Сосредоточься на сути и глубине содержания.",
            "сравнение разных подходов": "Сравни несколько разных подходов к решении проблемы в выбранной теме. Плюсы и минусы каждого, когда что лучше применять.",
            "мини-обобщение опыта": "Обобщи опыт практиков по выбранной теме. Что действительно работает на практике, а что является мифом или бесполезно."
        }
        
        format_guide = format_instructions.get(text_format, "Используй аналитический и практический подход к теме.")
        
        tg_min, tg_max = slot_info['tg_chars']
        zen_min, zen_max = slot_info['zen_chars']
        
        prompt = f"""{system_prompt}

🎯 ТЕМА: {theme}
📋 ФОРМАТ ПОДАЧИ: {text_format}
📝 ИНСТРУКЦИЯ ДЛЯ ФОРМАТА: {format_guide}

═══ КЛЮЧЕВЫЕ ТРЕБОВАНИЯ ═══

1) ВРЕМЕННЫЕ СЛОТЫ И ОБЪЁМЫ:

Telegram ({slot_info['name']}):
• Объем: {tg_min}-{tg_max} символов
• Стиль: живой, динамичный, человеческий, используй эмодзи {slot_info['emoji']}
• Для перечислений используй символ •

Яндекс Дзен ({slot_info['name']}):
• Объем: {zen_min}-{zen_max} символов  
• Стиль: глубже, аналитичнее, как мини-статья. БЕЗ ЭМОДЗИ
• Для перечислений используй символ •

2) СТРУКТУРА ИДЕАЛЬНОГО ПОСТА:

• СИЛЬНЫЙ ХУК — сразу интрига или провокационный факт
• ЖИВАЯ ПОДАЧА — короткие фразы, эмоции, структурность
• ЯСНАЯ ЛОГИКА: факт → наблюдение → вывод → вопрос
• ЭКСПЕРТНОСТЬ через реальные ситуации:
  - Если опыт профессии — пиши от 3-го лица («знакомый из сферы рассказал»)
  - Если анализ/исследование — от 1-го лица
• ЗАКРЫВАШКА: мягкий вовлекающий финал с вопросом («Как вы считаете?», «А у вас было такое?»)

3) ОТЛИЧИЯ ДЗЕН ОТ TELEGRAM:

TELEGRAM:
• Быстро, ярко, живо
• Больше эмоций и эмодзи {slot_info['emoji']}
• 1–2 сильных тезиса, чтобы читатель сразу «схватил» суть
• Используй символ • для перечислений

ДЗЕН:
• Глубина и разборы
• Факты, аналитика, мини-исследования, выводы
• Чёткая структура с отступами
• Ощущение мини-статьи, но читается легко
• Используй символ • для перечислений

═══ ТВОЯ ЗАДАЧА ═══

Создай ДВА РАЗНЫХ текста для одной темы.

TELEGRAM-ПОСТ (для канала {MAIN_CHANNEL_ID}):
• Объем: {tg_min}-{tg_max} символов
• Эмодзи: {slot_info['emoji']} и другие уместные
• Яркий хук, живая подача
• Используй символ • для перечислений
• Закрывашка с вовлекающим вопросом

ДЗЕН-ПОСТ (для канала {ZEN_CHANNEL_ID}):
• Объем: {zen_min}-{zen_max} символов
• БЕЗ ЭМОДЗИ — только текст
• Глубокий аналитический разбор
• Чёткая структура, как мини-статья
• Используй символ • для перечислений
• Закрывашка с вопросом для обсуждения

ВАЖНЫЕ ПРАВИЛА:
1. Telegram — быстро и живо. Дзен — глубина и анализ.
2. Используй конкретику: цифры, примеры, кейсы из реальной практики.
3. Избегай клише и шаблонных фраз.
4. Каждый текст должен быть УНИКАЛЬНЫМ — не дублируй контент.
5. НИКОГДА не начинай с «Вот пожалуйста держи...» или подобных фраз.
6. Если используешь списки — применяй символ •
7. В конце ОБЯЗАТЕЛЬНО мягкий вовлекающий финал с вопросом.

Формат вывода (СТРОГО СОБЛЮДАЙ!):
TG: [здесь Telegram-пост полностью]
---
DZEN: [здесь Дзен-пост полностью]

НИКАКИХ ДОПОЛНИТЕЛЬНЫХ ПОЯСНЕНИЙ, ТОЛЬКО ДВА ТЕКСТА В УКАЗАННОМ ФОРМАТЕ!"""
        
        logger.info(f"📝 Создан промпт для Gemini")
        return prompt

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API"""
        try:
            # Используем стабильную модель
            model_name = "gemini-1.5-flash-001"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "topP": 0.95,
                    "maxOutputTokens": 4000
                }
            }
            
            logger.info(f"🤖 Используем модель: {model_name}")
            response = session.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    logger.info(f"✅ Текст сгенерирован")
                    logger.info(f"📊 Длина текста: {len(generated_text)} символов")
                    return generated_text
            else:
                logger.error(f"❌ Ошибка API: {response.status_code}")
                if response.text:
                    logger.error(f"📄 Ответ сервера: {response.text[:200]}")
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
        
        separators = ["---", "——", "––––", "***", "\nDZEN:", "\nДзен:"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("TG:", "").replace("Telegram:", "").strip()
                    zen_text = parts[1].replace("DZEN:", "").replace("Дзен:", "").strip()
                    return tg_text, zen_text
        
        # Если разделитель не найден, разделяем пополам
        text_length = len(combined_text)
        split_point = text_length // 2
        
        for i in range(split_point, min(split_point + 100, text_length - 1)):
            if combined_text[i] in ['.', '!', '?']:
                split_point = i + 1
                break
        
        return combined_text[:split_point].strip(), combined_text[split_point:].strip()

    def get_post_image(self, theme):
        """Находит подходящую картинку через Pexels API"""
        try:
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "home improvement"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting", "workplace"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social media", "media"]
            }
            
            queries = theme_queries.get(theme, ["business", "success", "work"])
            query = random.choice(queries)
            
            # Используем Pexels API если ключ есть
            if PEXELS_API_KEY:
                url = f"https://api.pexels.com/v1/search"
                params = {
                    "query": query,
                    "per_page": 20,
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
                        # Ищем неиспользованную картинку
                        for photo in photos:
                            image_url = photo.get("src", {}).get("large", "")
                            if image_url and image_url not in self.image_history.get("used_images", []):
                                logger.info(f"🖼️ Найдена новая картинка через Pexels: {image_url[:80]}...")
                                self.save_image_history(image_url)
                                return image_url
                        
                        # Если все использованы, берем случайную
                        photo = random.choice(photos)
                        image_url = photo.get("src", {}).get("large", "")
                        logger.info(f"🖼️ Используем картинку из Pexels (возможно повтор): {image_url[:80]}...")
                        return image_url
            
            # Fallback на Unsplash
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                logger.info(f"🖼️ Найдена картинка через Unsplash: {image_url[:80]}...")
                return image_url
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при поиске картинки: {e}")
        
        # Дефолтная картинка
        default_images = [
            "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop",
            "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&h=630&fit=crop",
            "https://images.unsplash.com/photo-1559136555-9303baea8ebd?w=1200&h=630&fit=crop"
        ]
        return random.choice(default_images)

    def clean_text_for_posting(self, text):
        """Очищает текст от артефактов форматирования"""
        if not text:
            return ""
        
        text = re.sub(r'^\[+\s*', '', text)
        text = re.sub(r'\s*\]+$', '', text)
        text = re.sub(r'^(Вот|Держи|Пожалуйста|Смотри|Вот тебе).+?\n', '', text, flags=re.IGNORECASE)
        text = text.strip()
        
        return text

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        text = self.clean_text_for_posting(text)
        text = re.sub(r'TG:\s*', '', text)
        text = re.sub(r'Telegram:\s*', '', text)
        
        if text.startswith('['):
            text = text[1:].strip()
        if text.endswith(']'):
            text = text[:-1].strip()
        
        max_length = 1024
        if len(text) > max_length:
            cut_position = text[:max_length-100].rfind('.')
            if cut_position > max_length-200:
                text = text[:cut_position + 1] + ".."
            else:
                text = text[:max_length-50] + "..."
        
        if '#' not in text:
            hashtags = "\n\n#hr #pr #бизнес #управление #коммуникации"
            if len(text) + len(hashtags) < max_length:
                text += hashtags
        
        return text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзен"""
        if not text:
            return ""
        
        text = self.clean_text_for_posting(text)
        text = re.sub(r'DZEN:\s*', '', text)
        text = re.sub(r'Дзен:\s*', '', text)
        text = re.sub(r'TG:\s*', '', text)
        text = re.sub(r'Telegram:\s*', '', text)
        
        if text.startswith('['):
            text = text[1:].strip()
        if text.endswith(']'):
            text = text[:-1].strip()
        
        text = re.sub(r'#\w+', '', text)
        
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002700-\U000027BF"
            u"\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        return text.strip()

    def publish_directly(self, slot_time, tg_text, zen_text, image_url, theme):
        """Публикует посты напрямую в каналы"""
        logger.info("📤 Публикую посты напрямую в каналы...")
        
        if tg_text and (tg_text.startswith('[') or tg_text.endswith(']')):
            logger.warning("⚠️ Telegram текст содержит квадратные скобки, очищаем...")
            tg_text = self.clean_text_for_posting(tg_text)
        
        if zen_text and (zen_text.startswith('[') or zen_text.endswith(']')):
            logger.warning("⚠️ Дзен текст содержит квадратные скобки, очищаем...")
            zen_text = self.clean_text_for_posting(zen_text)
        
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
            
            if not text or len(text.strip()) < 10:
                logger.error(f"❌ Текст слишком короткий")
                return False
            
            text = self.clean_text_for_posting(text)
            
            if text.startswith('[') or text.endswith(']'):
                logger.warning(f"⚠️ Текст содержит квадратные скобки, удаляем...")
                text = text.strip('[]').strip()
            
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
                logger.warning("⚠️ Не удалось извлечь Дзен текст, используем Telegram текст")
                zen_text_raw = tg_text_raw
            
            tg_text = self.format_telegram_text(tg_text_raw)
            zen_text = self.format_zen_text(zen_text_raw)
            
            if tg_text.startswith('[') or tg_text.endswith(']'):
                logger.warning("⚠️ Telegram текст содержит квадратные скобки, исправляем...")
                tg_text = self.clean_text_for_posting(tg_text)
            
            if zen_text.startswith('[') or zen_text.endswith(']'):
                logger.warning("⚠️ Дзен текст содержит квадратные скобки, исправляем...")
                zen_text = self.clean_text_for_posting(zen_text)
            
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            logger.info(f"📊 Длина текстов: TG={tg_length} (требуется {tg_min}-{tg_max}), DZEN={zen_length} (требуется {zen_min}-{zen_max})")
            
            if tg_length < 50:
                logger.error(f"❌ Telegram текст слишком короткий")
                return False
            
            if zen_length < 50:
                logger.warning(f"⚠️ Дзен текст слишком короткий, но продолжим")
            
            logger.info("🖼️ Подбираем картинку...")
            image_url = self.get_post_image(theme)
            
            logger.info("📤 ПУБЛИКУЮ ПОСТЫ НАПРЯМУЮ В КАНАЛЫ")
            
            success_count = self.publish_directly(slot_time, tg_text, zen_text, image_url, theme)
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                logger.info(f"📝 Информация сохранена в историю")
            
            if success_count >= 1:
                logger.info(f"\n🎉 УСПЕХ! Отправлено постов: {success_count}/2")
                logger.info(f"   🕒 Время: {slot_time} МСК")
                logger.info(f"   🎯 Тема: {theme}")
                logger.info(f"   📝 Формат: {text_format}")
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
