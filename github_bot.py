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
PEXELS_API_KEY = "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c"  # Публичный ключ Pexels

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
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ (Telegram + Яндекс.Дзен)")
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
        
        # Временные слоты
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
        
        # Тематические ключевые слова для поиска (без жесткой привязки к конкретным URL)
        self.theme_keywords = {
            "ремонт и строительство": [
                "construction workers", "renovation work", "building site", 
                "repair tools", "construction equipment", "home renovation",
                "construction team", "hardhat workers", "construction materials"
            ],
            "HR и управление персоналом": [
                "office meeting", "team collaboration", "business discussion",
                "workplace environment", "job interview", "corporate training",
                "business conference", "professional development"
            ],
            "PR и коммуникации": [
                "public relations", "media conference", "press release",
                "social media marketing", "brand communication", "public speaking",
                "marketing strategy", "digital communication"
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
            
            # Сохраняем в историю
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
        """Создает промпт для Gemini с генерацией поискового запроса"""
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

ФОРМАТИРОВАНИЕ ПО ТИПУ ПОСТА:

1. ИСТОРИИ/РАССКАЗЫ (когда есть повествование, развитие событий):
   • Структура: Хук → Рассказ (обычными абзацами) → Мораль → Вопрос
   • Пример ПРАВИЛЬНО:
     🔥 История, как однажды PR пошел не по плану...
     
     Одна крупная компания решила запустить "вирусную" акцию в поддержку экологии. Разослали блогерам наборы для посадки деревьев и попросили поделиться в соцсетях.
     
     Но блогеры раскопали информацию о том, что компания активно загрязняет реки своими отходами! Поднялся огромный скандал, репутация пострадала сильнее, чем если бы акции не было вообще.
     
     Мораль: PR без реальных действий – это как косметика на грязное лицо.
     
     А вы какие провальные PR-кампании помните? 👇

2. СПИСКИ/ПЕРЕЧИСЛЕНИЯ (когда есть отдельные пункты, советы, шаги):
   • Структура: Хук → Пункты (с точками •) → Вывод → Вопрос
   • Пример:
     💡 3 ключевых ошибки в управлении:
     
            • Не давать обратную связь вовремя
            • Игнорировать инициативу сотрудников
            • Не делегировать задачи
     
     Что добавите к этому списку? 💭

ВАЖНО: Не используй точки • в историях! Истории пиши обычными абзацами.

ОБЩИЕ ТРЕБОВАНИЯ ДЛЯ TELEGRAM:
• Стиль: живой, динамичный, человеческий
• Используй эмодзи в хуке и в конце
• 3-6 хештегов в конце
• Обязательный вопрос для обсуждения

⸻
ТРЕБОВАНИЯ К ЯНДЕКС.ДЗЕН ПОСТУ ({zen_chars_min}-{zen_chars_max} символов):

СТРУКТУРА:
• ХУК: 1-2 предложения без эмодзи
• ОСНОВНОЙ ТЕКСТ: абзацы без отступов
• ФАКТЫ или ЦИФРЫ (если уместно)
• ВЫВОД: четкие выводы из анализа
• ЗАКРЫВАШКА: обязательный вовлекающий вопрос
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
ПОИСКОВЫЙ ЗАПРОС ДЛЯ ИЗОБРАЖЕНИЯ:

Анализируй контекст поста и создай точный поисковый запрос на английском языке для поиска фотографии на Pexels.com

ЗАПРЕЩЕННЫЕ ДЛЯ ИЗОБРАЖЕНИЙ ТЕМЫ (особенно для "ремонт и строительство"):
• природа, небо, облака, закаты, рассветы
• пейзажи, горы, океаны, пляжи
• животные, цветы, растения

ДЛЯ КАЖДОЙ ТЕМЫ ИСПОЛЬЗУЙ:
• "ремонт и строительство": construction, renovation, building, workers, tools, equipment, hardhat
• "HR и управление персоналом": office, meeting, business, team, collaboration, workplace
• "PR и коммуникации": communication, media, conference, presentation, marketing, public relations

Создай 2 РАЗНЫХ запроса: один для Telegram поста, другой для Яндекс.Дзен поста.

⸻
ФОРМАТ ОТВЕТА (СОБЛЮДАЙ ТОЧНО):

Telegram-пост:
[Текст для Telegram с правильным форматированием]

Яндекс.Дзен-пост:
[Текст для Яндекс.Дзен без эмодзи, с закрывашкой и хештегами]

Поисковый запрос для Telegram изображения:
[Точный запрос на английском, максимум 5-7 слов]

Поисковый запрос для Яндекс.Дзен изображения:
[Точный запрос на английском, максимум 5-7 слов]

⸻
НАЧИНАЙ ГЕНЕРАЦИЮ СЕЙЧАС!"""

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

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 3500,
                        "topP": 0.92,
                        "topK": 35
                    }
                }
                
                logger.info(f"🔄 Генерируем текст (попытка {attempt + 1}/{max_retries})...")
                
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        
                        total_length = len(generated_text)
                        logger.info(f"📄 Сгенерировано {total_length} символов")
                        
                        if "Telegram-пост:" in generated_text and "Яндекс.Дзен-пост:" in generated_text:
                            logger.info(f"✅ Текст сгенерирован")
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Нет структуры, пробуем снова...")
                            time.sleep(2)
                            continue
                    else:
                        logger.warning("⚠️ Gemini не вернул текст, пробуем снова...")
                        time.sleep(2)
                            continue
                        
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст")
        return None

    def split_text_and_queries(self, combined_text):
        """Разделяет текст на Telegram, Яндекс.Дзен и поисковые запросы"""
        if not combined_text:
            return None, None, None, None
        
        # Ищем поисковые запросы
        tg_query = None
        zen_query = None
        
        # Ищем запрос для Telegram
        tg_query_marker = "Поисковый запрос для Telegram изображения:"
        zen_query_marker = "Поисковый запрос для Яндекс.Дзен изображения:"
        
        if tg_query_marker in combined_text:
            tg_part = combined_text.split(tg_query_marker)[1]
            tg_query = tg_part.split('\n')[0].strip()
            tg_query = tg_query.strip('"\'')
        
        if zen_query_marker in combined_text:
            zen_part = combined_text.split(zen_query_marker)[1]
            zen_query = zen_part.split('\n')[0].strip()
            zen_query = zen_query.strip('"\'')
        
        # Убираем поисковые запросы из текста
        for marker in [tg_query_marker, zen_query_marker]:
            combined_text = combined_text.split(marker)[0] if marker in combined_text else combined_text
        
        # Ищем разделители постов
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Яндекс.Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Telegram
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Яндекс.Дзен
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Яндекс.Дзен-пост:", "").strip()
            
            return tg_text, zen_text, tg_query, zen_query
        
        return None, None, tg_query, zen_query

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        # Очищаем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем HTML сущности
        replacements = {
            '&nbsp;': ' ', 
            '&emsp;': '    ', 
            ' ': ' ', 
            '**': '', 
            '__': '',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Определяем тип поста
        lines = text.split('\n')
        text_lower = text.lower()
        
        # Проверяем, есть ли в тексте явное перечисление
        has_enumeration_keywords = any(keyword in text_lower for keyword in [
            'первое', 'второе', 'третье', '1)', '2)', '3)', 'во-первых', 'во-вторых',
            'шаг 1', 'шаг 2', 'шаг 3', 'совет 1', 'совет 2', 'совет 3',
            'ошибка 1', 'ошибка 2', 'ошибка 3', 'причина 1', 'причина 2', 'причина 3'
        ])
        
        # Проверяем, является ли это списком советов/ошибок/шагов
        is_list_post = any(keyword in text_lower for keyword in [
            'советы', 'ошибки', 'шаги', 'правила', 'принципы', 'рекомендации',
            'ключевые моменты', 'основные пункты', 'главное'
        ])
        
        # Проверяем, является ли это историей
        is_story_post = any(keyword in text_lower for keyword in [
            'история', 'случай', 'пример', 'ситуация', 'опыт',
            'однажды', 'как-то раз', 'в один день', 'недавно',
            'коллега', 'знакомый', 'клиент', 'руководитель'
        ])
        
        # Считаем количество пунктов с точками
        bullet_points = sum(1 for line in lines if line.strip().startswith('•'))
        total_lines = len([line for line in lines if line.strip()])
        bullet_ratio = bullet_points / total_lines if total_lines > 0 else 0
        
        # Определяем окончательный тип
        is_enumeration = (has_enumeration_keywords or is_list_post or bullet_ratio > 0.3) and not is_story_post
        
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Если это СПИСОК (перечисление) → делаем отступы
            if is_enumeration and line.startswith('•'):
                line = re.sub(r'^•\s*[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line)
                formatted_lines.append("            • " + line[1:].strip())
            
            # Если это ИСТОРИЯ с точками → убираем точки
            elif is_story_post and line.startswith('•'):
                line_content = line[1:].strip()
                line_content = re.sub(r'^[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '', line_content)
                formatted_lines.append(line_content)
            
            # Если обычный пункт
            elif line.startswith('•') and not is_story_post and not is_enumeration:
                formatted_lines.append(line)
            
            # Обычный текст
            else:
                formatted_lines.append(line)
        
        formatted_text = '\n'.join(formatted_lines)
        
        # Убираем лишние пустые строки
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        # Убираем возможные двойные пробелы
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
            '&nbsp;': ' ', 
            '&emsp;': '    ', 
            ' ': ' ', 
            '**': '', 
            '__': '',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'"
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
        
        # Убираем все отступы в начале строк
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
        
        # Проверяем наличие закрывашки (вопроса)
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
            'а у вас', 'сталкивались', 'какой подход',
            'что важнее', 'ваши мысли', 'поделитесь опытом',
            'как вы решаете', 'ваш опыт', 'что скажете'
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

    def search_pexels_image(self, search_query, theme):
        """Ищет изображение на Pexels по запросу"""
        try:
            if not search_query:
                # Используем тематические ключевые слова
                keywords = self.theme_keywords.get(theme, ["business", "work"])
                search_query = random.choice(keywords)
            
            # Фильтруем запрос для ремонта - убираем природу
            if theme == "ремонт и строительство":
                search_query = self.filter_construction_query(search_query)
            
            encoded_query = quote_plus(search_query)
            url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=10&orientation=landscape"
            
            headers = {
                "Authorization": PEXELS_API_KEY,
                "User-Agent": "Mozilla/5.0"
            }
            
            logger.info(f"🔍 Pexels поиск: '{search_query}' для темы '{theme}'")
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos') and len(data['photos']) > 0:
                    # Фильтруем фотографии по тематике
                    filtered_photos = self.filter_photos_by_theme(data['photos'], theme)
                    
                    if filtered_photos:
                        photo = random.choice(filtered_photos)
                        image_url = photo['src']['large']
                        logger.info(f"✅ Найдено подходящее изображение: {photo.get('alt', 'No description')[:50]}")
                        return image_url
                    else:
                        # Если не нашли подходящих, берем любую
                        photo = random.choice(data['photos'])
                        image_url = photo['src']['large']
                        logger.info(f"⚠️ Используем любое доступное изображение")
                        return image_url
                else:
                    logger.warning(f"⚠️ Pexels не нашел фото по запросу: '{search_query}'")
            else:
                logger.warning(f"⚠️ Pexels API ошибка: {response.status_code}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска на Pexels: {e}")
            return None

    def filter_construction_query(self, query):
        """Фильтрует поисковый запрос для ремонта/строительства"""
        # Убираем слова связанные с природой
        nature_words = ["nature", "sky", "cloud", "sunset", "sunrise", "landscape", 
                       "mountain", "ocean", "beach", "tree", "forest", "field"]
        
        query_lower = query.lower()
        words = query_lower.split()
        
        # Убираем слова природы
        filtered_words = [word for word in words if word not in nature_words]
        
        # Добавляем обязательные слова для строительства
        construction_words = ["construction", "building", "renovation", "workers", 
                            "tools", "equipment", "hardhat", "site"]
        
        # Если нет строительных слов, добавляем
        has_construction = any(word in filtered_words for word in construction_words)
        if not has_construction and filtered_words:
            filtered_words.append(random.choice(construction_words))
        
        if not filtered_words:
            filtered_words = ["construction workers"]
        
        return ' '.join(filtered_words)

    def filter_photos_by_theme(self, photos, theme):
        """Фильтрует фотографии по тематике"""
        filtered = []
        
        for photo in photos:
            # Проверяем описание
            description = (photo.get('alt') or photo.get('description') or '').lower()
            
            # Для ремонта - строго отсеиваем природу
            if theme == "ремонт и строительство":
                # Ключевые слова которые ДОЛЖНЫ быть
                required_words = ["construction", "building", "renovation", "worker", 
                                "tool", "equipment", "hardhat", "site", "repair"]
                
                # Слова которые НЕ ДОЛЖНЫ быть
                forbidden_words = ["nature", "sky", "cloud", "sunset", "sunrise", 
                                 "landscape", "mountain", "ocean", "beach", "tree", 
                                 "forest", "field", "park", "garden"]
                
                has_required = any(word in description for word in required_words)
                has_forbidden = any(word in description for word in forbidden_words)
                
                if has_required and not has_forbidden:
                    filtered.append(photo)
            
            # Для HR - офисная тематика
            elif theme == "HR и управление персоналом":
                hr_words = ["office", "meeting", "business", "team", "work", 
                           "workplace", "conference", "collaboration", "professional"]
                
                if any(word in description for word in hr_words):
                    filtered.append(photo)
            
            # Для PR - медиа и коммуникации
            elif theme == "PR и коммуникации":
                pr_words = ["media", "communication", "conference", "presentation", 
                           "marketing", "public", "relations", "digital", "social"]
                
                if any(word in description for word in pr_words):
                    filtered.append(photo)
        
        return filtered if filtered else photos  # Если не отфильтровали, возвращаем все

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
            # Находим последнее хорошее место для обрезки
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

    def send_single_post(self, chat_id, text, image_url, is_telegram=True):
        """Отправляет пост"""
        try:
            # Проверяем длину перед отправкой
            max_length = 1024  # Лимит Telegram
            
            if len(text) > max_length:
                text = self.check_length_and_fix(text, max_length, is_telegram)
            
            # Проверяем URL изображения
            if not image_url or not image_url.startswith('http'):
                logger.error(f"❌ Невалидный URL изображения: {image_url}")
                return False
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            logger.info(f"📤 Отправляем пост в {chat_id}")
            
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

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def generate_and_send_posts(self):
        """Главная функция"""
        try:
            # Проверка доступа
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            # Определяем временной слот
            utc_hour = datetime.utcnow().hour
            now = self.get_moscow_time()
            
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
            
            # Выбор темы
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            # Генерация контента
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info, time_key)
            logger.info(f"📝 Длина промпта: {len(combined_prompt)} символов")
            
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            # Разделение текста
            tg_text, zen_text, tg_image_query, zen_image_query = self.split_text_and_queries(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Форматирование
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            # Проверка длины
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            logger.info(f"📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
            logger.info(f"📊 Яндекс.Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
            
            # Корректировка длины
            if tg_len > tg_max:
                tg_text = self.check_length_and_fix(tg_text, tg_max, True)
                tg_len = len(tg_text)
                logger.info(f"📊 Telegram после коррекции: {tg_len} символов")
            
            if zen_len > zen_max:
                zen_text = self.check_length_and_fix(zen_text, zen_max, False)
                zen_len = len(zen_text)
                logger.info(f"📊 Яндекс.Дзен после коррекции: {zen_len} символов")
            
            # Поиск изображений
            logger.info("🖼️ Ищем тематические изображения...")
            
            # Для Telegram
            tg_image_url = self.search_pexels_image(tg_image_query, self.current_theme)
            if not tg_image_url:
                logger.warning("⚠️ Не удалось найти изображение для Telegram, используем общий запрос")
                tg_image_url = self.search_pexels_image(None, self.current_theme)
            
            time.sleep(1)
            
            # Для Яндекс.Дзен
            zen_image_url = self.search_pexels_image(zen_image_query, self.current_theme)
            if not zen_image_url:
                logger.warning("⚠️ Не удалось найти изображение для Яндекс.Дзен, используем общий запрос")
                zen_image_url = self.search_pexels_image(None, self.current_theme)
            
            # Если все еще нет изображений
            if not tg_image_url or not zen_image_url:
                logger.error("❌ Не удалось найти изображения")
                return False
            
            # Отправка постов
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Telegram
            logger.info(f"  → Telegram: {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url, is_telegram=True):
                success_count += 1
            
            time.sleep(2)
            
            # Яндекс.Дзен
            logger.info(f"  → Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url, is_telegram=False):
                success_count += 1
            
            # Сохранение в историю
            if success_count == 2:
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "telegram_image_query": tg_image_query,
                    "zen_image_query": zen_image_query,
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
                logger.info(f"   🕒 Время: {schedule_time} МСК")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Яндекс.Дзен: {zen_len} символов")
                if tg_image_query:
                    logger.info(f"   🔍 Telegram запрос: {tg_image_query}")
                if zen_image_query:
                    logger.info(f"   🔍 Яндекс.Дзен запрос: {zen_image_query}")
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

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ ДЛЯ TELEGRAM И ЯНДЕКС.ДЗЕН")
    print("=" * 80)
    print("📋 Особенности:")
    print("   • AI генерирует посты И поисковые запросы для изображений")
    print("   • Умная фильтрация фото: для ремонта - НИКАКОГО НЕБА!")
    print("   • Pexels API для поиска свежих тематических фото")
    print("   • Разные изображения для Telegram и Яндекс.Дзен")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты созданы и отправлены")
        print("   Фото найдены AI через Pexels")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
