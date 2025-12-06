import os
import requests
import random
import json
import time
import logging
import re
import sys
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ СТРУКТУРИРОВАННЫХ ПОСТОВ")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.prohibited_topics = ["удаленная работа", "гибридная работа", "оформление только по ТК"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.last_image_query = None
        
        # Временные слоты с обновлёнными объёмами
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": (400, 600),      # Telegram: 400-600
                "zen_chars": (600, 800),     # Дзен: 600-800
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "легкий бодрящий инсайт, мини-наблюдение, 1-2 коротких совета, лайтовый тренд/новость, микро-исследование с одним фактом, напоминание или чек-лист на день, быстрый кейс без тяжелой аналитики, ошибка + короткий вывод, пост-вопрос на разминку, позитивный настрой (мотивация без пафоса)"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": (700, 900),      # Telegram: 700-900
                "zen_chars": (700, 900),     # Дзен: 700-900
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "аналитический разбор ситуации, мини-исследование с цифрами, разбор ошибок + решение, сравнение подходов 'так/так лучше', экспертный кейс с деталями, логическая цепочка: факт → пример → вывод, список шагов (причины или выводы), объяснение сложного простым языком, тренд + почему он важен, разбор поведения аудитории / механизм процессов"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": (600, 900),      # Telegram: 600-900
                "zen_chars": (600, 700),     # Дзен: 600-700
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "мини-история с моралью, мнение автора + мягкая эмоция, реальная ситуация 'как было → что поняли', наблюдение за людьми или индустрией, тихая эмоциональная подача, инсайт дня, кейс через 'знакомый рассказал', легкая рефлексия (вывод дня), провокационный вопрос для обсуждения, пост, вызывающий отклик и комментарии"
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
                "last_slots": []
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": []
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с исключением запрещенных тем"""
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
        """Создает промпт для постов с новой структурой"""
        slot_name = time_slot_info['name']
        slot_type = time_slot_info['type']
        content_type = time_slot_info['content_type']
        tg_chars_min, tg_chars_max = time_slot_info['tg_chars']
        zen_chars_min, zen_chars_max = time_slot_info['zen_chars']
        
        prompt = f"""Ты — эксперт в создании контента с 30+ лет опыта. Твоя задача — создавать тексты, которые цепляют с первых строк.

⸻
ТЕМА: {theme}
ВРЕМЕННОЙ СЛОТ: {time_key} ({slot_name})
ТИП КОНТЕНТА: {content_type}
ЗАПРЕЩЕННЫЕ ТЕМЫ: {', '.join(self.prohibited_topics)} — НИКОГДА НЕ УПОМИНАТЬ!

⸻
ТРЕБОВАНИЯ К ОБЪЁМУ:

Telegram:
• 09:00 — 400–600 символов
• 14:00 — 700–900 символов
• 19:00 — 600–900 символов
Стиль: живой, динамичный, человеческий, много эмодзи.

Яндекс Дзен:
• 09:00 — 600–800 символов
• 14:00 — 700–900 символов
• 19:00 — 600–700 символов
Стиль: глубже, аналитичнее, как мини-статья. Без эмодзи.

⸻
СТРУКТУРА ИДЕАЛЬНОГО ПОСТА:

1. СИЛЬНЫЙ ХУК — интрига или провокационный факт с первых слов
2. ЖИВАЯ ПОДАЧА — короткие фразы, эмоции, лёгкая динамика
3. ЯСНАЯ ЛОГИКА: факт → мини-кейс → вывод → вопрос
4. ЭКСПЕРТНОСТЬ через реальные ситуации
   • Если опыт — через 3-е лицо («знакомый из сферы рассказал»)
   • Если аналитика — от 1 лица

⸻
РАЗЛИЧИЯ МЕЖДУ ПЛАТФОРМАМИ:

Telegram:
• Быстро, ярко, живо
• Больше эмоций и эмодзи
• Короткие абзацы с отступом и точкой •
• 1–2 сильных тезиса
• 3-6 хештегов # (по тематике)

Дзен:
• Глубина и разборы
• Факты, аналитика, мини-исследования, выводы
• Чёткая структура с отступами
• Без эмодзи
• Ощущение мини-статьи

⸻
ЗАКРЫВАШКА (ОБЯЗАТЕЛЬНО):
• Вопрос для обсуждения
• Мини-итог + приглашение поделиться мнением
• «Как вы считаете…?», «А у вас было такое?»
• Лёгкий CTA без давления

⸻
ВАРИАНТЫ ПОДАЧИ ТЕКСТА:
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
КОНКРЕТНЫЕ ТРЕБОВАНИЯ:

Telegram ({tg_chars_min}-{tg_chars_max} символов):
• Начинай сразу с хука
• Используй эмодзи для эмоций
• Короткие абзацы
• Структура: ХУК → Тезис → Пример → Вывод → Вопрос → Хештеги
• ТОЧНО {tg_chars_min}-{tg_chars_max} символов!

Яндекс Дзен ({zen_chars_min}-{zen_chars_max} символов):
• Начинай сразу с хука
• БЕЗ эмодзи
• Глубокая аналитика с фактами
• Чёткая структура с отступами
• Структура: ХУК → Проблема → Анализ → Решение → Вопрос
• ТОЧНО {zen_chars_min}-{zen_chars_max} символов!

⸻
ВАЖНО:
• Соблюдай точный объём символов!
• Дзен НИКОГДА не должен превышать {zen_chars_max} символов
• Telegram НИКОГДА не должен превышать {tg_chars_max} символов
• Если текст длиннее — сокращай, убирай воду
• Один сильный тезис лучше трёх слабых

⸻
ПОИСКОВЫЙ ЗАПРОС ДЛЯ ИЗОБРАЖЕНИЯ:
После написания текста проанализируй и создай один чёткий запрос для картинки

⸻
ФОРМАТ ОТВЕТА (СОБЛЮДАЙ ТОЧНО!):

Telegram-пост:
[текст для Telegram с эмодзи, отступами и 3-6 хештегами]
(ТОЧНО {tg_chars_min}-{tg_chars_max} символов!)

Дзен-пост:
[текст для Дзен без эмодзи, с четкой структурой]
(ТОЧНО {zen_chars_min}-{zen_chars_max} символов!)

Поисковый запрос для изображения:
[один четкий запрос на русском языке]

⸻
НАЧИНАЙ ГЕНЕРАЦИЮ. Создай по-настоящему цепляющие тексты в рамках указанных объёмов!"""

        return prompt

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            test_data = {
                "contents": [{"parts": [{"text": "Test"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            
            response = session.post(url, json=test_data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Gemini доступен")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=5):
        """Генерирует текст через Gemini с увеличенным количеством токенов"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                # Увеличиваем токены для полноценных постов
                max_tokens = 3000 if "14:00" in prompt or "19:00" in prompt else 2500
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.85,  # Слегка уменьшил для большей структурированности
                        "maxOutputTokens": max_tokens,
                        "topP": 0.92,
                        "topK": 35
                    }
                }
                
                logger.info(f"🔄 Генерируем текст (попытка {attempt + 1}/{max_retries})...")
                logger.info(f"📊 Максимальные токены: {max_tokens}")
                
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        
                        total_length = len(generated_text)
                        logger.info(f"📄 Сгенерировано {total_length} символов")
                        
                        # Проверяем структуру
                        if "Telegram-пост:" in generated_text and "Дзен-пост:" in generated_text:
                            logger.info(f"✅ Текст сгенерирован успешно")
                            
                            # Проверяем длину
                            if total_length > 3500:  # Если слишком длинно
                                logger.warning("⚠️ Текст слишком длинный, пробуем короче...")
                                if attempt < max_retries - 1:
                                    time.sleep(2)
                                    continue
                            
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Структура текста неполная, пробуем снова...")
                            time.sleep(2)
                            continue
                    else:
                        logger.warning("⚠️ Gemini не вернул кандидатов, пробуем снова...")
                        time.sleep(2)
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст после всех попыток")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Zen посты с проверкой длины"""
        if not combined_text:
            return None, None, None
        
        # Ищем поисковый запрос
        image_query = None
        query_markers = ["Поисковый запрос для изображения:", "Search query for image:", "Image search query:"]
        
        for marker in query_markers:
            if marker in combined_text:
                query_part = combined_text.split(marker)[-1]
                image_query = query_part.strip().split('\n')[0].strip()
                image_query = image_query.strip('"\'')
                break
        
        # Убираем поисковый запрос из текста
        for marker in query_markers:
            combined_text = combined_text.split(marker)[0]
        
        # Ищем разделители
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Telegram
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Дзен
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Дзен-пост:", "").strip()
            
            # Убираем скобки с требованиями по символам
            tg_text = re.sub(r'\(ТОЧНО.*?символов!\)', '', tg_text).strip()
            zen_text = re.sub(r'\(ТОЧНО.*?символов!\)', '', zen_text).strip()
            
            # Форматируем
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            return tg_text, zen_text, image_query
        
        # Fallback
        separators = ["---", "——", "––––", "⸻"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = self.format_telegram_text(parts[0].strip())
                    zen_text = self.format_zen_text(parts[1].strip())
                    return tg_text, zen_text, image_query
        
        # Дефолт
        text_length = len(combined_text)
        if text_length > 300:
            split_point = text_length // 2
            tg_text = self.format_telegram_text(combined_text[:split_point].strip())
            zen_text = self.format_zen_text(combined_text[split_point:].strip())
            return tg_text, zen_text, image_query
        
        tg_text = self.format_telegram_text(combined_text)
        return tg_text, tg_text, image_query

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram с проверкой длины"""
        if not text:
            return ""
        
        # Очищаем
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Убираем лишние разделители
        text = re.sub(r'[-_=]{3,}', '', text)
        
        # Форматируем абзацы с отступами
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Добавляем эмодзи в первую строку если нет
            if i == 0 and not any(emoji in line for emoji in ['🔥', '💡', '👉', '✨', '🎯', '❗', '⚠️']):
                emoji = random.choice(['🔥 ', '💡 ', '👉 ', '✨ ', '🎯 '])
                line = emoji + line
            
            # Форматируем пункты
            if line.startswith(('•', '-', '*', '—')):
                formatted_line = "        • " + line[1:].strip()
                formatted_lines.append(formatted_line)
            else:
                formatted_lines.append(line)
        
        # Добавляем хештеги если нет
        formatted_text = '\n\n'.join(formatted_lines)
        hashtag_count = len(re.findall(r'#\w+', formatted_text))
        if hashtag_count < 3:
            formatted_text = self.add_telegram_hashtags(formatted_text, self.current_theme)
        
        # Проверяем закрывашку
        if not self.has_closing_hook(formatted_text):
            formatted_text = self.add_closing_hook(formatted_text, is_telegram=True)
        
        # Сокращаем если превышает лимит
        current_len = len(formatted_text)
        time_key = self.get_current_time_key()
        if time_key in self.time_slots:
            tg_max = self.time_slots[time_key]['tg_chars'][1]
            if current_len > tg_max:
                logger.warning(f"⚠️ Telegram пост превышает лимит ({current_len} > {tg_max}), сокращаю...")
                formatted_text = self.smart_truncate(formatted_text, tg_max)
        
        return formatted_text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзена с жёсткой проверкой длины"""
        if not text:
            return ""
        
        # Очищаем
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Убираем эмодзи
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # Форматируем с отступами
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Первая строка - хук
            if i == 0 and len(line) < 10:
                hook_starters = ["Важный момент:", "Интересный факт:", "Знаете ли вы:", "Сегодня разбираем:"]
                line = random.choice(hook_starters) + " " + line
            
            # Форматируем структуру
            if line.startswith(('•', '-', '*', '—')):
                formatted_line = "        " + line
                formatted_lines.append(formatted_line)
            else:
                formatted_lines.append(line)
        
        # Добавляем подпись
        formatted_text = '\n\n'.join(formatted_lines)
        formatted_text = self.ensure_zen_signature(formatted_text)
        
        # Проверяем закрывашку
        if not self.has_closing_hook(formatted_text):
            formatted_text = self.add_closing_hook(formatted_text, is_telegram=False)
        
        # ЖЁСТКО проверяем длину Дзен поста
        current_len = len(formatted_text)
        time_key = self.get_current_time_key()
        if time_key in self.time_slots:
            zen_max = self.time_slots[time_key]['zen_chars'][1]
            
            if current_len > zen_max:
                logger.warning(f"❌ Дзен пост превышает лимит ({current_len} > {zen_max})")
                logger.info(f"⚠️ Сокращаю Дзен пост до {zen_max} символов...")
                
                # Более агрессивное сокращение для Дзена
                formatted_text = self.smart_truncate_aggressive(formatted_text, zen_max)
                
                # Проверяем еще раз
                new_len = len(formatted_text)
                if new_len > zen_max:
                    logger.error(f"❌ Не удалось сократить Дзен пост ({new_len} > {zen_max})")
                    # Последний резерв - обрезаем до лимита
                    formatted_text = formatted_text[:zen_max - 3] + "..."
        
        return formatted_text.strip()

    def smart_truncate_aggressive(self, text, max_length):
        """Агрессивное сокращение текста для Дзена"""
        if len(text) <= max_length:
            return text
        
        logger.warning(f"⚡ Агрессивное сокращение Дзена: {len(text)} -> {max_length}")
        
        # Сначала убираем лишние пробелы и пустые строки
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        if len(text) <= max_length:
            return text
        
        # Убираем менее важные части
        # 1. Находим основные части по структуре
        parts = text.split('\n\n')
        
        if len(parts) > 3:
            # Оставляем первые 3 части (хук + основное содержание)
            text = '\n\n'.join(parts[:3])
            
            # Добавляем закрывашку если есть
            if len(parts) > 3 and any(word in parts[-1].lower() for word in ['считаете', 'думаете', 'мнение', 'обсудим']):
                text += '\n\n' + parts[-1]
        
        if len(text) <= max_length:
            return text
        
        # 2. Укорачиваем предложения
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) > 4:
            text = '. '.join(sentences[:4]) + '.'
        
        if len(text) <= max_length:
            return text
        
        # 3. Жёсткое сокращение
        text = text[:max_length - 3]
        
        # Находим последнее хорошее место для обрезки
        last_period = text.rfind('.')
        last_question = text.rfind('?')
        last_exclamation = text.rfind('!')
        last_newline = text.rfind('\n')
        
        best_cut = max(last_period, last_question, last_exclamation, last_newline)
        
        if best_cut > max_length * 0.6:
            return text[:best_cut + 1]
        else:
            return text[:max_length - 3] + "..."

    def get_current_time_key(self):
        """Возвращает текущий временной ключ"""
        utc_hour = datetime.utcnow().hour
        
        if utc_hour == 6:  # 09:00 МСК
            return "09:00"
        elif utc_hour == 11:  # 14:00 МСК
            return "14:00"
        elif utc_hour == 16:  # 19:00 МСК
            return "19:00"
        else:
            now = self.get_moscow_time()
            current_hour = now.hour
            
            if 5 <= current_hour < 12:
                return "09:00"
            elif 12 <= current_hour < 17:
                return "14:00"
            else:
                return "19:00"

    def has_closing_hook(self, text):
        """Проверяет наличие закрывашки"""
        text_lower = text[-100:].lower() if len(text) > 100 else text.lower()
        hook_indicators = [
            'как вы считаете', 'что думаете', 'ваше мнение',
            'пишите в комментариях', 'обсудим', 'расскажите',
            'поделитесь', 'комментируйте', 'жду ваши мысли',
            'а у вас', 'сталкивались', 'какой подход',
            'что важнее', 'ваши мысли', 'поделитесь опытом'
        ]
        return any(indicator in text_lower for indicator in hook_indicators)

    def add_closing_hook(self, text, is_telegram=True):
        """Добавляет закрывашку"""
        if is_telegram:
            hooks = [
                "\n\nКак вы считаете? Жду ваши мысли в комментариях! 💬",
                "\n\nА у вас был похожий опыт? Расскажите! ✨",
                "\n\nКакой подход ближе вам? Обсудим! 👇",
                "\n\nСталкивались с таким в практике? 🔥",
                "\n\nЧто думаете по этому поводу? 💭"
            ]
        else:
            hooks = [
                "\n\nЧто думаете по этому поводу? Поделитесь мнением в комментариях.",
                "\n\nА как вы решаете подобные проблемы в своей практике?",
                "\n\nСталкивались ли вы с такой ситуацией? Как поступали?",
                "\n\nКакой подход кажется вам более эффективным?",
                "\n\nА в вашем опыте было нечто подобное? Расскажите!"
            ]
        
        hook = random.choice(hooks)
        return text.rstrip() + hook

    def generate_image_search_query(self, text, theme):
        """Генерирует поисковый запрос для изображения"""
        try:
            if hasattr(self, 'last_image_query') and self.last_image_query:
                logger.info(f"✅ Используем сгенерированный запрос: {self.last_image_query}")
                return self.last_image_query
            
            theme_keywords = {
                "HR и управление персоналом": ["офис", "команда", "встреча", "бизнес", "управление", "персонал", "карьера"],
                "PR и коммуникации": ["коммуникация", "медиа", "аудитория", "брендинг", "маркетинг", "пресс-релиз", "пиар"],
                "ремонт и строительство": ["ремонт", "строительство", "инструменты", "дизайн", "дом", "интерьер", "отделка"]
            }
            
            keywords = theme_keywords.get(theme, ["бизнес", "профессия", "развитие", "работа"])
            
            text_lower = text.lower()
            found_keywords = []
            
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
            
            if found_keywords:
                main_keyword = random.choice(found_keywords[:3])
            else:
                main_keyword = random.choice(keywords)
            
            contexts = ["деловой", "профессиональный", "современный", "рабочий", "эффективный"]
            context = random.choice(contexts)
            
            image_query = f"{context} {main_keyword}"
            logger.info(f"✅ Сгенерирован поисковый запрос: {image_query}")
            return image_query
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации поискового запроса: {e}")
            return "бизнес профессия"

    def get_fresh_image(self, text, theme, width=1200, height=630):
        """Находит свежую картинку"""
        try:
            search_query = self.generate_image_search_query(text, theme)
            
            # Пробуем Pexels
            pexels_api_key = "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c"
            encoded_query = quote_plus(search_query)
            url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=3"
            
            headers = {
                "Authorization": pexels_api_key,
                "User-Agent": "Mozilla/5.0"
            }
            
            response = session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos') and len(data['photos']) > 0:
                    photo = random.choice(data['photos'])
                    image_url = photo['src']['large']
                    logger.info(f"✅ Найдено изображение: '{search_query}'")
                    return image_url
            
            # Fallback на Picsum
            logger.info(f"⚠️ Pexels не нашел, используем Picsum")
            unique_id = hash(f"{theme}{time.time()}") % 1000
            return f"https://picsum.photos/{width}/{height}?random={unique_id}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/{width}/{height}"

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

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def smart_truncate(self, text, max_length):
        """Сокращает текст"""
        if len(text) <= max_length:
            return text
        
        # Сохраняем важные части
        hashtags_match = re.search(r'(#\w+\s*)+$', text)
        hashtags = hashtags_match.group(0) if hashtags_match else ""
        
        # Убираем хештеги для сокращения
        text_without_hashtags = text[:hashtags_match.start()] if hashtags_match else text
        
        # Сокращаем основной текст
        if len(text_without_hashtags) <= max_length - len(hashtags):
            return text_without_hashtags + hashtags
        
        truncated = text_without_hashtags[:max_length - len(hashtags) - 100]  # Оставляем запас
        
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        last_newline = truncated.rfind('\n')
        
        best_cut = max(last_sentence_end, last_newline)
        
        if best_cut > (max_length - len(hashtags)) * 0.7:
            result = text_without_hashtags[:best_cut + 1].strip() + "\n\n" + hashtags.strip()
        else:
            result = text_without_hashtags[:max_length - len(hashtags) - 3].strip() + "...\n\n" + hashtags.strip()
        
        return result

    def add_telegram_hashtags(self, text, theme):
        """Добавляет хештеги для Telegram"""
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера", "#работа", "#трудоустройство"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#бренд", "#пиар", "#медиа"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#дом", "#интерьер", "#отделка"]
        }
        
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы", "#бизнес"])
        general_hashtags = ["#инсайты", "#лайфхак", "#профессия", "#развитие", "#успех", "#полезное"]
        random.shuffle(general_hashtags)
        
        all_hashtags = base_hashtags[:4] + general_hashtags[:2]
        hashtags_to_add = random.sample(all_hashtags, min(6, len(all_hashtags)))
        
        existing_hashtags = re.findall(r'#\w+', text)
        if len(existing_hashtags) < 3:
            hashtags_line = " ".join(hashtags_to_add)
            return f"{text}\n\n{hashtags_line}"
        
        return text

    def send_single_post(self, chat_id, text, image_url, is_telegram=True):
        """Отправляет пост"""
        try:
            # Проверяем длину перед отправкой
            current_len = len(text)
            
            if is_telegram and current_len > 1024:
                logger.warning(f"⚠️ Telegram пост длиннее 1024 символов ({current_len}), сокращаю...")
                text = self.smart_truncate(text, 1024)
            elif not is_telegram and current_len > 1024:
                logger.warning(f"⚠️ Дзен пост длиннее 1024 символов ({current_len}), сокращаю...")
                text = self.smart_truncate(text, 1024)
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Пост отправлен в {chat_id}")
                logger.info(f"📊 Длина: {len(text)} символов")
                return True
            else:
                logger.error(f"❌ Ошибка отправки: {response.status_code}")
                if response.text:
                    logger.error(f"❌ Ответ сервера: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self):
        """Главная функция"""
        try:
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            # Определяем временной слот
            utc_hour = datetime.utcnow().hour
            
            if utc_hour == 6:  # 09:00 МСК
                time_key = "09:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "09:00"
            elif utc_hour == 11:  # 14:00 МСК
                time_key = "14:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "14:00"
            elif utc_hour == 16:  # 19:00 МСК
                time_key = "19:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "19:00"
            else:
                now = self.get_moscow_time()
                current_hour = now.hour
                
                if 5 <= current_hour < 12:
                    time_key = "09:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной УТРЕННИЙ ({now.strftime('%H:%M')} МСК)"
                elif 12 <= current_hour < 17:
                    time_key = "14:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной ДНЕВНОЙ ({now.strftime('%H:%M')} МСК)"
                else:
                    time_key = "19:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной ВЕЧЕРНИЙ ({now.strftime('%H:%M')} МСК)"
            
            logger.info(f"🕒 Запуск: {schedule_time}")
            logger.info(f"📝 Тип: {time_slot_info['name']}")
            
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info, time_key)
            logger.info(f"📝 Длина промпта: {len(combined_prompt)} символов")
            
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            tg_text, zen_text, image_query = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            if image_query:
                self.last_image_query = image_query
                logger.info(f"🔍 Поисковый запрос: {image_query}")
            
            # Проверяем длину
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            logger.info(f"📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
            logger.info(f"📊 Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
            
            # Строгая проверка Дзена
            if zen_len > zen_max:
                logger.error(f"❌ Дзен превышает максимальный лимит! {zen_len} > {zen_max}")
                logger.warning("⚠️ Принудительно сокращаю Дзен пост...")
                zen_text = self.smart_truncate_aggressive(zen_text, zen_max)
                zen_len = len(zen_text)
                logger.info(f"📊 Дзен после сокращения: {zen_len} символов")
            
            # Проверяем хуки
            if not self.has_hook_at_start(tg_text):
                logger.warning("⚠️ В Telegram посте нет хука в начале, добавляем...")
                tg_text = "🔥 " + tg_text
            
            if not self.has_hook_at_start(zen_text):
                logger.warning("⚠️ В Дзен посте нет хука в начале, добавляем...")
                hook_starters = ["Важный момент:", "Интересный факт:", "Знаете ли вы:"]
                zen_text = random.choice(hook_starters) + " " + zen_text
            
            # Картинки
            logger.info("🖼️ Ищем картинки...")
            combined_post_text = f"{tg_text[:200]} {zen_text[:200]}"
            tg_image_url = self.get_fresh_image(combined_post_text, self.current_theme)
            time.sleep(1)
            zen_image_url = self.get_fresh_image(combined_post_text, self.current_theme)
            
            # Отправка
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Telegram
            logger.info(f"  → Telegram: {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url, is_telegram=True):
                success_count += 1
            
            time.sleep(2)
            
            # Дзен
            logger.info(f"  → Дзен: {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url, is_telegram=False):
                success_count += 1
            
            if success_count == 2:
                now = datetime.now()
                
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "time_key": time_key,
                    "theme": self.current_theme,
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "image_query": image_query,
                    "time": now.strftime("%H:%M:%S")
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.post_history["last_post_time"] = now.isoformat()
                self.save_post_history()
                
                logger.info("\n" + "=" * 60)
                logger.info("🎉 УСПЕХ! Посты отправлены!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
                logger.info(f"   📊 Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
                if image_query:
                    logger.info(f"   🔍 Запрос: {image_query}")
                logger.info("=" * 60)
                return True
            else:
                logger.error(f"❌ Отправка не удалась. Успешно: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def has_hook_at_start(self, text):
        """Проверяет, есть ли хук в начале текста"""
        first_50 = text[:50].lower()
        hook_indicators = ['🔥', '💡', '👉', '✨', '🎯', 'важный момент:', 'интересный факт:', 'знаете ли вы:', 'сегодня']
        return any(indicator.lower() in first_50 for indicator in hook_indicators)

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: СТРОГО СТРУКТУРИРОВАННЫЕ ПОСТЫ")
    print("=" * 80)
    print("📋 Обновлённые объёмы постов:")
    print("   TELEGRAM:")
    print("   • 09:00 — 400–600 символов")
    print("   • 14:00 — 700–900 символов")
    print("   • 19:00 — 600–900 символов")
    print("\n   ДЗЕН:")
    print("   • 09:00 — 600–800 символов")
    print("   • 14:00 — 700–900 символов")
    print("   • 19:00 — 600–700 символов")
    print("=" * 80)
    print("⚡ УЛУЧШЕНИЯ:")
    print("   • Увеличенные токены для Gemini")
    print("   • Жёсткая проверка длины Дзен постов")
    print("   • Агрессивное сокращение при превышении лимита")
    print("   • Чёткое соблюдение символьных лимитов")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты строго в рамках лимитов отправлены")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
