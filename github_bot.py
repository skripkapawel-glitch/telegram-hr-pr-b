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
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ КОРОТКИХ ПОСТОВ (до 900 символов)")
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
        
        # Временные слоты с УМЕНЬШЕННОЙ длиной (макс 900 символов)
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": (400, 600),      # Telegram: 400-600
                "zen_chars": (600, 700),     # Дзен: 600-700
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "легкий бодрящий инсайт, мини-наблюдение, 1-2 коротких совета, лайтовый тренд/новость, микро-исследование с одним фактом, напоминание или чек-лист на день, быстрый кейс без тяжелой аналитики, ошибка + короткий вывод, пост-вопрос на разминку, позитивный настрой (мотивация без пафоса)"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": (700, 900),      # Telegram: 700-900 (уменьшено)
                "zen_chars": (700, 850),     # Дзен: 700-850 (уменьшено)
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "аналитический разбор ситуации, мини-исследование с цифрами, разбор ошибок + решение, сравнение подходов 'так/так лучше', экспертный кейс с деталями, логическая цепочка: факт → пример → вывод, список шагов (причины или выводы), объяснение сложного простым языком, тренд + почему он важен, разбор поведения аудитории / механизм процессов"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": (600, 900),      # Telegram: 600-900 (уменьшено)
                "zen_chars": (800, 900),     # Дзен: 800-900 (уменьшено)
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
        """Создает промпт для коротких постов (макс 900 символов)"""
        slot_name = time_slot_info['name']
        slot_type = time_slot_info['type']
        content_type = time_slot_info['content_type']
        tg_chars_min, tg_chars_max = time_slot_info['tg_chars']
        zen_chars_min, zen_chars_max = time_slot_info['zen_chars']
        
        prompt = f"""Ты — синтез из лучших специалистов: копирайтера, контент-мейкера, SMM-стратега, редактора с ощущением ритма текста, аналитика трендов и продюсера, который упаковывает мысли в живые форматы. У тебя 30+ лет опыта в контенте, медиа и коммуникациях. Твоя задача — создавать КОРОТКИЕ, но емкие тексты, которые цепляют с первых строк.

ВРЕМЕННОЙ СЛОТ: {time_key} ({slot_name})

ТЕМА: {theme}

ТИП КОНТЕНТА ДЛЯ ЭТОГО СЛОТА: {content_type}

ЗАПРЕЩЕННЫЕ ТЕМЫ (НИКОГДА НЕ УПОМИНАТЬ): {', '.join(self.prohibited_topics)}

---

ВАЖНО: Все посты должны быть КОРОТКИМИ! Максимум 900 символов.

ТРЕБОВАНИЯ К ПОСТАМ:

1. КОРОТКИЙ ФОРМАТ:
• Telegram: {tg_chars_min}-{tg_chars_max} символов
• Дзен: {zen_chars_min}-{zen_chars_max} символов
• Будь лаконичным! Один сильный тезис лучше трех слабых.
• Убирай воду, оставляй только суть.

2. TELEGRAM ПОСТ ({tg_chars_min}-{tg_chars_max} символов):
• Стиль: {time_slot_info['tg_style']}
• Быстро, ярко, живо, больше эмоций и эмодзи
• Короткие абзацы, 1-2 предложения максимум
• 1 сильный тезис + пример + вывод
• 3-4 хештега # в конце
• Форматирование: используй • для пунктов
• КОНЦОВКА: четкий вопрос + хештеги

3. ДЗЕН ПОСТ ({zen_chars_min}-{zen_chars_max} символов):
• Стиль: {time_slot_info['zen_style']}
• Лаконичный анализ, факты, выводы
• Без эмодзи
• Структура: проблема → пример → решение → вопрос
• КОНЦОВКА: ясный вывод + вопрос для обсуждения

4. ОБЯЗАТЕЛЬНАЯ СТРУКТУРА (для обоих):
• Хук (1-2 предложения)
• Кейс/пример (2-3 предложения)
• Вывод (1-2 предложения)
• Вопрос для обсуждения (1 предложение)

5. ЧЕГО ИЗБЕГАТЬ:
• Длинных вступлений
• Многочисленных примеров (один сильный достаточно)
• Повторов
• Воды и общих фраз

---

После написания текста проанализируй пост и сформируй точный поисковый запрос для изображения.
Определи ключевые смыслы, объекты, эмоции, атмосферу и главное сообщение текста.
На основе этого создай один чёткий, конкретный запрос для поиска картинки, без лишних слов.

---

ФОРМАТ ОТВЕТА (СОБЛЮДАЙ ТОЧНО):

Telegram-пост:
[здесь КОРОТКИЙ текст для Telegram с эмодзи и 3-4 хештегами в конце]

Дзен-пост:
[здесь КОРОТКИЙ текст для Дзен без эмодзи, с четкой концовкой]

Поисковый запрос для изображения:
[один четкий запрос на русском языке]

---

ПОМНИ: КОРОТКО ≠ ПОВЕРХНОСТНО. Будь лаконичным, но глубоким.
УБЕРИ ВСЮ ВОДУ. ОСТАВЬ ТОЛЬКО СУТЬ.

НАЧИНАЙ ГЕНЕРАЦИЮ СЕЙЧАС."""

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
        """Генерирует КОРОТКИЙ текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.9,
                        "maxOutputTokens": 4000,  # Меньше токенов для коротких постов
                        "topP": 0.95,
                        "topK": 40
                    }
                }
                
                logger.info(f"🔄 Генерируем КОРОТКИЙ текст (попытка {attempt + 1}/{max_retries})...")
                logger.info(f"📊 Максимальные токены: {data['generationConfig']['maxOutputTokens']}")
                
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
                            if total_length > 3000:  # Если слишком длинно
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
        """Разделяет текст на Telegram и Zen посты"""
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
            
            # Очищаем
            tg_text = self.clean_and_shorten_text(tg_text, is_telegram=True)
            zen_text = self.clean_and_shorten_text(zen_text, is_telegram=False)
            
            return tg_text, zen_text, image_query
        
        # Fallback
        separators = ["---", "——", "––––"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = self.clean_and_shorten_text(parts[0].strip(), is_telegram=True)
                    zen_text = self.clean_and_shorten_text(parts[1].strip(), is_telegram=False)
                    return tg_text, zen_text, image_query
        
        # Дефолт
        text_length = len(combined_text)
        if text_length > 300:
            split_point = text_length // 2
            tg_text = self.clean_and_shorten_text(combined_text[:split_point].strip(), is_telegram=True)
            zen_text = self.clean_and_shorten_text(combined_text[split_point:].strip(), is_telegram=False)
            return tg_text, zen_text, image_query
        
        tg_text = self.clean_and_shorten_text(combined_text, is_telegram=True)
        return tg_text, tg_text, image_query

    def clean_and_shorten_text(self, text, is_telegram=True):
        """Очищает и сокращает текст"""
        if not text:
            return ""
        
        # Убираем лишнее
        text = re.sub(r'-{3,}', '', text)
        text = re.sub(r'_{3,}', '', text)
        text = re.sub(r'={3,}', '', text)
        
        # Убираем обрывки
        endings_to_remove = [
            r'\s*\.\.\.\s*$',
            r'\s*---\s*$',
            r'\s*–\s*$',
            r'\s*-\s*$',
        ]
        
        for pattern in endings_to_remove:
            text = re.sub(pattern, '', text)
        
        # Сокращаем если слишком длинно
        text = self.shorten_if_needed(text, is_telegram)
        
        # Улучшаем концовку
        text = self.improve_ending(text, is_telegram)
        
        return text.strip()

    def shorten_if_needed(self, text, is_telegram=True):
        """Сокращает текст если он слишком длинный"""
        current_length = len(text)
        
        # Определяем максимальную длину
        if is_telegram:
            max_length = 900  # Максимум для Telegram
        else:
            max_length = 900  # Максимум для Дзен
        
        if current_length <= max_length:
            return text
        
        # Сокращаем
        logger.warning(f"⚠️ Текст слишком длинный ({current_length} > {max_length}), сокращаю...")
        
        # Ищем естественное место для обрезки
        shortened = text[:max_length]
        
        # Ищем последнее хорошее место для обрезки
        cut_points = [
            shortened.rfind('.'), 
            shortened.rfind('!'), 
            shortened.rfind('?'),
            shortened.rfind('\n\n'),
            shortened.rfind('\n')
        ]
        
        best_cut = max(cut_points)
        
        if best_cut > max_length * 0.6:  # Если нашли хорошее место
            return text[:best_cut + 1]
        else:
            return text[:max_length - 3] + "..."

    def improve_ending(self, text, is_telegram=True):
        """Улучшает концовку короткого поста"""
        lines = text.split('\n')
        
        # Находим последнюю содержательную строку
        last_content_line = None
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and len(line) > 5:
                last_content_line = i
                break
        
        if last_content_line is not None:
            last_line = lines[last_content_line].strip()
            
            # Проверяем концовку
            has_good_ending = any(marker in last_line.lower() for marker in [
                'как вы считаете', 'что думаете', 'ваше мнение', 
                'пишите в комментариях', 'обсудим', 'расскажите',
                'поделитесь', 'комментируйте', 'жду ваши мысли',
                'а у вас', 'сталкивались', 'какой подход', 'что важнее'
            ])
            
            if not has_good_ending:
                if is_telegram:
                    endings = [
                        "\n\nА что думаете вы? 💬",
                        "\n\nКак вы считаете? 👇",
                        "\n\nА у вас так было? ✨",
                        "\n\nСталкивались? 🔥",
                        "\n\nКакой подход ближе? 💭"
                    ]
                else:
                    endings = [
                        "\n\nЧто думаете по этому поводу?",
                        "\n\nА как вы решаете подобные проблемы?",
                        "\n\nСталкивались ли вы с такой ситуацией?",
                        "\n\nКакой подход кажется вам более эффективным?",
                        "\n\nА в вашей практике было нечто подобное?"
                    ]
                
                ending = random.choice(endings)
                lines.append("")
                lines.append(ending)
        
        return '\n'.join(lines)

    def generate_image_search_query(self, text, theme):
        """Генерирует поисковый запрос для изображения"""
        try:
            if hasattr(self, 'last_image_query') and self.last_image_query:
                logger.info(f"✅ Используем сгенерированный запрос: {self.last_image_query}")
                return self.last_image_query
            
            theme_keywords = {
                "HR и управление персоналом": ["офис", "команда", "встреча", "бизнес", "управление"],
                "PR и коммуникации": ["коммуникация", "медиа", "аудитория", "брендинг", "маркетинг"],
                "ремонт и строительство": ["ремонт", "строительство", "инструменты", "дизайн", "дом"]
            }
            
            keywords = theme_keywords.get(theme, ["бизнес", "профессия", "развитие"])
            
            text_lower = text.lower()
            found_keywords = []
            
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
            
            if found_keywords:
                main_keyword = random.choice(found_keywords[:2])
            else:
                main_keyword = random.choice(keywords)
            
            contexts = ["деловой", "рабочий", "современный", "профессиональный"]
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

    def format_text_with_indent(self, text, is_telegram=True):
        """Форматирует текст для поста"""
        if not text:
            return ""
        
        # Очищаем
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Убираем дефисы
        text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
        
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Пропускаем ---
            if line.startswith('---') or line == '---':
                continue
            
            # Telegram: добавляем эмодзи
            if is_telegram and not any(line.startswith(char) for char in ['•', '#', '📌', '🎯', '💡']):
                if random.random() > 0.7 and len(formatted_lines) < 2:
                    emoji_prefix = random.choice(['🎯 ', '💡 ', '👉 ', '✨ ', '🔥 '])
                    line = emoji_prefix + line
            
            # Форматируем пункты
            if line.startswith('•'):
                formatted_line = "            " + line
                formatted_lines.append(formatted_line)
            elif line.startswith(('- ', '* ', '— ')):
                formatted_line = "            • " + line[2:].strip()
                formatted_lines.append(formatted_line)
            else:
                if formatted_lines and formatted_lines[-1].startswith('            •'):
                    formatted_lines.append("               " + line)
                else:
                    formatted_lines.append(line)
        
        formatted_text = '\n'.join(formatted_lines)
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
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

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def ensure_closing_hook(self, text, is_telegram=True):
        """Добавляет закрывашку"""
        if not text:
            return text
        
        # Убираем обрывки
        text = re.sub(r'\s*\.\.\.\s*$', '', text)
        text = re.sub(r'\s*---\s*$', '', text)
        
        # Проверяем концовку
        patterns = [
            r'как вы считаете[^?.!]*[?.!]',
            r'а у вас было такое[^?.!]*[?.!]',
            r'что думаете[^?.!]*[?.!]',
            r'ваше мнение[^?.!]*[?.!]',
            r'пишите в комментариях[^?.!]*[?.!]',
            r'обсудим[^?.!]*[?.!]',
            r'расскажите[^?.!]*[?.!]',
            r'поделитесь[^?.!]*[?.!]',
        ]
        
        has_good_ending = False
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                has_good_ending = True
                break
        
        if has_good_ending:
            return text
        
        # Добавляем концовку
        if is_telegram:
            endings = [
                "\n\nА что думаете вы? Пишите в комментариях! 💬",
                "\n\nКак вы считаете? Обсудим! 👇",
                "\n\nА у вас был похожий опыт? Расскажите! ✨",
                "\n\nСталкивались с таким? 🔥",
                "\n\nКакой подход ближе вам? 💭"
            ]
        else:
            endings = [
                "\n\nЧто думаете по этому поводу?",
                "\n\nА как вы решаете подобные проблемы?",
                "\n\nСталкивались ли вы с такой ситуацией?",
                "\n\nКакой подход кажется вам более эффективным?",
                "\n\nА в вашей практике было нечто подобное?"
            ]
        
        ending = random.choice(endings)
        
        if not is_telegram and "Главная Видео Статьи Новости Подписки" in text:
            parts = text.split("Главная Видео Статьи Новости Подписки")
            main_text = parts[0].strip()
            signature = "Главная Видео Статьи Новости Подписки"
            return f"{main_text}{ending}\n\n{signature}"
        else:
            return text.rstrip() + ending

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

    def smart_truncate_text(self, text, max_length=1024):
        """Сокращает текст"""
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length]
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        last_newline = truncated.rfind('\n')
        last_bullet = truncated.rfind('\n            •')
        
        best_cut = max(last_sentence_end, last_newline, last_bullet)
        
        if best_cut > max_length * 0.7:
            return text[:best_cut + 1]
        else:
            return text[:max_length - 3] + "..."

    def add_telegram_hashtags(self, text, theme):
        """Добавляет хештеги для Telegram"""
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#бренд"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#дом"]
        }
        
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы"])
        general_hashtags = ["#инсайты", "#лайфхак", "#профессия", "#развитие"]
        random.shuffle(general_hashtags)
        
        all_hashtags = base_hashtags[:2] + general_hashtags[:2]
        hashtags_to_add = random.sample(all_hashtags, min(3, len(all_hashtags)))
        
        existing_hashtags = re.findall(r'#\w+', text)
        if len(existing_hashtags) < 2:
            hashtags_line = " ".join(hashtags_to_add)
            return f"{text}\n\n{hashtags_line}"
        
        return text

    def send_single_post(self, chat_id, text, image_url, is_telegram=True):
        """Отправляет пост"""
        try:
            # Форматируем
            formatted_text = self.format_text_with_indent(text, is_telegram)
            formatted_text = re.sub(r'\n-{3,}\n', '\n\n', formatted_text)
            
            # Добавляем концовку
            formatted_text = self.ensure_closing_hook(formatted_text, is_telegram)
            
            if is_telegram:
                # Хештеги
                formatted_text = self.add_telegram_hashtags(formatted_text, self.current_theme)
            else:
                # Подпись Дзен
                formatted_text = self.ensure_zen_signature(formatted_text)
            
            # Сокращаем если нужно
            formatted_text = self.smart_truncate_text(formatted_text, 1024)
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': formatted_text,
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
                logger.info(f"📊 Длина: {len(formatted_text)} символов")
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
            
            logger.info(f"📊 Telegram: {tg_len} символов (требуется: {tg_min}-{tg_max})")
            logger.info(f"📊 Дзен: {zen_len} символов (требуется: {zen_min}-{zen_max})")
            
            if tg_len > tg_max:
                logger.warning(f"⚠️ Telegram пост слишком длинный")
                tg_text = self.shorten_if_needed(tg_text, is_telegram=True)
                tg_len = len(tg_text)
                logger.info(f"📊 Сокращен до: {tg_len} символов")
            
            if zen_len > zen_max:
                logger.warning(f"⚠️ Дзен пост слишком длинный")
                zen_text = self.shorten_if_needed(zen_text, is_telegram=False)
                zen_len = len(zen_text)
                logger.info(f"📊 Сокращен до: {zen_len} символов")
            
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
                logger.info("🎉 УСПЕХ! Короткие посты отправлены!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов (макс: {tg_max})")
                logger.info(f"   📊 Дзен: {zen_len} символов (макс: {zen_max})")
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
    print("🤖 GITHUB BOT: КОРОТКИЕ ПОСТЫ (до 900 символов)")
    print("=" * 80)
    print("📋 Все посты сокращены до максимум 900 символов:")
    print("   • Telegram 09:00: 400-600")
    print("   • Telegram 14:00: 700-900")
    print("   • Telegram 19:00: 600-900")
    print("   • Дзен 09:00: 600-700")
    print("   • Дзен 14:00: 700-850")
    print("   • Дзен 19:00: 800-900")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Короткие посты отправлены")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
