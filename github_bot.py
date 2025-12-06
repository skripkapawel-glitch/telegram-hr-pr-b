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
        self.last_image_query = None
        self.last_gemini_image_query = None
        
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

ТИПЫ ПОСТОВ И ФОРМАТИРОВАНИЕ:

1. ИСТОРИИ/РАССКАЗЫ (со словами: "коллега", "история", "случай", "знакомый", "делился"):
   • Формат: пункты БЕЗ отступов, НЕ добавляй эмодзи к каждому пункту!
   • Структура: Хук → Пункты рассказа → Мораль/вывод → Вопрос
   • Пример ПРАВИЛЬНО:
     🔥 Коллега делился историей о ремонте...
     
     • Решил сэкономить и нанял "мастера на все руки"...
     • Обещал сделать все быстро и недорого...
     • В итоге: плитка кривая, сантехника течет...
     
     Мораль: скупой платит дважды...
     А у вас были подобные истории? 👇

2. СПИСКИ/ПЕРЕЧИСЛЕНИЯ (советы, шаги, причины, выводы):
   • Формат: пункты С отступами
   • Пример:
     💡 3 ключевых ошибки в управлении:
     
            • Не давать обратную связь вовремя
            • Игнорировать инициативу сотрудников
     
     Что добавите к этому списку? 💭

ОБЩИЕ ТРЕБОВАНИЯ ДЛЯ TELEGRAM:
• Стиль: живой, динамичный, человеческий
• Используй эмодзи в хуке и в конце, НЕ в каждом пункте истории!
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

ПРИМЕР:
Знаете, какая самая частая причина увольнений? Не низкая зарплата и не плохие условия.

Отсутствие признания — вот что действительно демотивирует сотрудников. Исследования показывают, что 79% сотрудников увольняются из-за недостатка признания их заслуг.

Руководитель, который не говорит "спасибо" и "молодец", теряет команду быстрее, чем думает. Регулярная обратная связь повышает лояльность на 35%.

Как вы решаете вопрос признания в своей команде? Какие практики используете?

#HR #управление #персонал #мотивация #команда

⸻
ВАЖНЫЕ ПРАВИЛА:
• Telegram: {tg_chars_min}-{tg_chars_max} символов
• Яндекс.Дзен: {zen_chars_min}-{zen_chars_max} символов
• Яндекс.Дзен НИКОГДА не превышает {zen_chars_max} символов!
• Яндекс.Дзен: ОБЯЗАТЕЛЬНЫ хештеги и закрывашка

⸻
ПОИСКОВЫЙ ЗАПРОС ДЛЯ ИЗОБРАЖЕНИЯ:

После написания текста ты анализируешь пост и формируешь точный поисковый запрос для изображения.
Твоя главная задача — выделить тематику поста как ключевой ориентир.

Определи:

1. главный смысл и тему поста,
2. ключевые объекты и детали,
3. эмоции и атмосферу,
4. контекст и сюжет, который задаёт тематика,

и на основе этого создай один чёткий, максимально точный запрос для картинки, отражающий именно тематику поста, без лишних слов и воды.

⸻
ФОРМАТ ОТВЕТА (СОБЛЮДАЙ ТОЧНО):

Telegram-пост:
[Текст для Telegram с правильным форматированием по типу поста]

Яндекс.Дзен-пост:
[Текст для Яндекс.Дзен без эмодзи, с закрывашкой и хештегами]

Поисковый запрос для изображения:
[Один чёткий запрос на русском языке]

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
                        "maxOutputTokens": 3000,
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

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Яндекс.Дзен посты"""
        if not combined_text:
            return None, None, None
        
        # Ищем поисковый запрос
        image_query = None
        query_markers = ["Поисковый запрос для изображения:"]
        
        for marker in query_markers:
            if marker in combined_text:
                query_part = combined_text.split(marker)[-1]
                image_query = query_part.strip().split('\n')[0].strip()
                image_query = image_query.strip('"\'')
                break
        
        # Убираем поисковый запрос
        for marker in query_markers:
            combined_text = combined_text.split(marker)[0]
        
        # Ищем разделители
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Яндекс.Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Telegram
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Яндекс.Дзен
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Яндекс.Дзен-пост:", "").strip()
            
            return tg_text, zen_text, image_query
        
        # Fallback на старые названия
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Telegram
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Яндекс.Дзен
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Дзен-пост:", "").strip()
            
            return tg_text, zen_text, image_query
        
        return None, None, image_query

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
        
        # Анализируем тип поста
        lines = text.split('\n')
        
        # Определяем тип поста
        is_story_post = any(keyword in text.lower() for keyword in [
            'коллега', 'история', 'случай', 'знакомый', 'делился',
            'поделился', 'рассказал', 'рассказывал', 'слышал', 'видел',
            'мораль', 'итог', 'вывод', 'запомнился', 'случилось'
        ])
        
        has_bullet_points = any(line.strip().startswith('•') for line in lines)
        
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # ИСТОРИИ: пункты БЕЗ отступов
            if is_story_post and line.startswith('•'):
                # Убираем эмодзи если они в начале пункта
                line = re.sub(r'^•\s*[🎯⏰🤔💡🔥🙈⭐📌👉❗⚠️🛁🛠️🤦‍♂️]+\s*', '• ', line)
                formatted_lines.append(line)
            
            # СПИСКИ/ПЕРЕЧИСЛЕНИЯ: с отступами
            elif has_bullet_points and line.startswith('•') and not is_story_post:
                formatted_lines.append("            • " + line[1:].strip())
            
            # Обычный текст
            else:
                formatted_lines.append(line)
        
        formatted_text = '\n'.join(formatted_lines)
        
        # Убираем лишние пустые строки
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
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

    def generate_image_search_query(self, text, theme):
        """Генерирует точный поисковый запрос для изображения по тематике"""
        try:
            # Используем запрос от Gemini если есть
            if self.last_gemini_image_query:
                return self.last_gemini_image_query
            
            if self.last_image_query:
                return self.last_image_query
            
            # Точные запросы по тематике
            theme_queries = {
                "HR и управление персоналом": [
                    "офис сотрудники совещание команда работа",
                    "бизнес менеджер переговоры карьера",
                    "управление персоналом HR интервью отбор",
                    "рабочий процесс команда проект офис",
                    "деловой бизнес карьера развитие"
                ],
                "PR и коммуникации": [
                    "коммуникация переговоры медиа пиар",
                    "презентация бренд маркетинг связи",
                    "публичные выступления PR медиа",
                    "социальные сети медиа коммуникация",
                    "пресс конференция журналисты пиар"
                ],
                "ремонт и строительство": [
                    "ремонт квартиры инструменты строительство",
                    "отделка ремонт дом дизайн интерьер",
                    "строительство рабочие инструменты работа",
                    "ремонт ванной сантехника плитка",
                    "ремонт кухни мебель отделка"
                ]
            }
            
            queries = theme_queries.get(theme, ["бизнес работа профессия"])
            
            # Анализируем текст для более точного запроса
            text_lower = text.lower()
            
            if theme == "ремонт и строительство":
                if "ванн" in text_lower or "сантех" in text_lower or "плитк" in text_lower:
                    queries = ["ремонт ванной сантехника плитка", "ванная комната ремонт плитка", "ремонт ванной комнаты"]
                elif "кухн" in text_lower:
                    queries = ["ремонт кухни мебель техника", "кухня ремонт дизайн интерьер", "ремонт кухонного помещения"]
                elif "квартир" in text_lower or "жиль" in text_lower:
                    queries = ["ремонт квартиры отделка дизайн", "квартира ремонт интерьер", "ремонт жилого помещения"]
                elif "дом" in text_lower or "строительств" in text_lower:
                    queries = ["строительство дома инструменты работа", "дом строительство рабочие", "строительные работы дом"]
                elif "инструмент" in text_lower:
                    queries = ["строительные инструменты работа", "инструменты для ремонта", "рабочие инструменты"]
            
            elif theme == "HR и управление персоналом":
                if "собеседован" in text_lower or "интервью" in text_lower or "отбор" in text_lower:
                    queries = ["собеседование работа карьера HR", "интервью работа HR отбор", "процесс собеседования"]
                elif "команд" in text_lower or "коллектив" in text_lower:
                    queries = ["команда офис сотрудники работа", "командная работа офис проект", "рабочий коллектив"]
                elif "офис" in text_lower or "рабочее мест" in text_lower:
                    queries = ["офис работа сотрудники бизнес", "офисный интерьер работа команда", "современный офис"]
                elif "управлен" in text_lower or "руковод" in text_lower:
                    queries = ["управление бизнес менеджмент", "руководство команда бизнес", "бизнес управление"]
            
            elif theme == "PR и коммуникации":
                if "презентац" in text_lower or "выступлен" in text_lower:
                    queries = ["презентация бизнес медиа переговоры", "публичное выступление презентация", "бизнес презентация"]
                elif "медиа" in text_lower or "соцсет" in text_lower or "сми" in text_lower:
                    queries = ["медиа социальные сети коммуникация", "социальные медиа маркетинг", "медиа коммуникации"]
                elif "бренд" in text_lower or "маркетинг" in text_lower:
                    queries = ["брендинг маркетинг бизнес", "бренд управление маркетинг", "развитие бренда"]
                elif "переговор" in text_lower or "коммуникац" in text_lower:
                    queries = ["переговоры бизнес коммуникация", "деловые переговоры", "бизнес коммуникации"]
            
            image_query = random.choice(queries)
            logger.info(f"🔍 Используем тематический запрос: {image_query}")
            return image_query
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации запроса: {e}")
            return "бизнес работа профессия"

    def get_fresh_image(self, text, theme, width=1200, height=630):
        """Находит свежую картинку"""
        try:
            search_query = self.generate_image_search_query(text, theme)
            logger.info(f"🔍 Ищем картинку по запросу: '{search_query}'")
            
            # Пробуем Pexels API
            pexels_api_key = "563492ad6f91700001000001d15a5e2d6a9d4b5c8c0e6f5b8c1a9b7c"
            encoded_query = quote_plus(search_query)
            url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=5"  # Увеличил до 5 фото
            
            headers = {
                "Authorization": pexels_api_key,
                "User-Agent": "Mozilla/5.0"
            }
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos') and len(data['photos']) > 0:
                    photo = random.choice(data['photos'])
                    image_url = photo['src']['large']
                    logger.info(f"✅ Найдено изображение по тематике: '{search_query}'")
                    return image_url
                else:
                    logger.warning(f"⚠️ Pexels не нашел фото по запросу: '{search_query}'")
            else:
                logger.warning(f"⚠️ Pexels API ошибка: {response.status_code}")
            
            # Fallback на тематический Picsum
            logger.info(f"⚠️ Используем тематический Picsum")
            
            # Выбираем тематическое изображение
            pic_ids = {
                "HR и управление персоналом": [10, 20, 30, 40, 50],  # Офисные фото
                "PR и коммуникации": [60, 70, 80, 90, 100],  # Коммуникации
                "ремонт и строительство": [110, 120, 130, 140, 150]  # Стройка
            }
            
            pic_id_list = pic_ids.get(theme, [1, 2, 3, 4, 5])
            pic_id = random.choice(pic_id_list)
            
            return f"https://picsum.photos/id/{pic_id}/{width}/{height}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/{width}/{height}"

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
            tg_text, zen_text, image_query = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Сохранение запроса от Gemini
            if image_query:
                self.last_image_query = image_query
                self.last_gemini_image_query = image_query
                logger.info(f"🔍 Запрос от Gemini для картинки: {image_query}")
            
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
            
            # Поиск картинок
            logger.info("🖼️ Ищем картинки...")
            tg_image_url = self.get_fresh_image(tg_text, self.current_theme)
            time.sleep(1)
            zen_image_url = self.get_fresh_image(zen_text, self.current_theme)
            
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
                logger.info(f"   🕒 Время: {schedule_time} МСК")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Яндекс.Дзен: {zen_len} символов")
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

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ ДЛЯ TELEGRAM И ЯНДЕКС.ДЗЕН")
    print("=" * 80)
    print("📋 Особенности:")
    print("   • Telegram: истории без отступов, чистый рассказ")
    print("   • Яндекс.Дзен: аналитический стиль без эмодзи")
    print("   • Тематические фото (ремонт, офис, коммуникации)")
    print("   • Умное форматирование по типу поста")
    print("   • Обязательные хештеги и закрывашки")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты созданы и отправлены")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
