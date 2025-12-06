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
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ (фиксированная структура)")
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
                "content_type": "легкий бодрящий инсайт, мини-наблюдение, 1-2 коротких совета, лайтовый тренд/новость, микро-исследование с одним фактом, напоминание или чек-лист на день, быстрый кейс без тяжелой аналитики, ошибка + короткий вывод, пост-вопрос на разминку, позитивный настрой"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": (700, 900),
                "zen_chars": (700, 900),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "аналитический разбор ситуации, мини-исследование с цифрами, разбор ошибок + решение, сравнение подходов 'так/так лучше', экспертный кейс с деталями, логическая цепочка: факт → пример → вывод, список шагов, объяснение сложного простым языком, тренд + почему он важен, разбор поведения аудитории"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": (600, 900),
                "zen_chars": (600, 700),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "мини-история с моралью, мнение автора + мягкая эмоция, реальная ситуация 'как было → что поняли', наблюдение за людьми или индустрией, тихая эмоциональная подача, инсайт дня, кейс через 'знакомый рассказал', легкая рефлексия, провокационный вопрос для обсуждения"
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
        """Создает промпт с ФИКСИРОВАННОЙ структурой"""
        slot_name = time_slot_info['name']
        content_type = time_slot_info['content_type']
        tg_chars_min, tg_chars_max = time_slot_info['tg_chars']
        zen_chars_min, zen_chars_max = time_slot_info['zen_chars']
        
        prompt = f"""Ты — эксперт в создании контента. Создай 2 поста на тему: {theme}

ТИП КОНТЕНТА: {content_type}
ЗАПРЕЩЕННЫЕ ТЕМЫ: {', '.join(self.prohibited_topics)} — НЕ УПОМИНАТЬ!

⸻
СТРУКТУРА TELEGRAM ПОСТА ({tg_chars_min}-{tg_chars_max} символов):

1. ХУК: 1-2 предложения с эмодзи в начале
2. ПУНКТЫ с отступом (начинаются с •):
   • Первый пункт с примером или кейсом
   • Второй пункт с анализом
   • Третий пункт с выводом
   • Четвертый пункт с вопросом для размышления
3. ВОПРОС для обсуждения
4. ХЕШТЕГИ: 3-6 штук

Пример Telegram поста:
Знаете, что самое дорогое в компании? 🤯 Нет, не кофемашина! Это время ваших сотрудников.⏰

• Знакомый HR-директор поделился: "Внедряли новую систему оценки..."

• Оказалось, отчётность ради отчётности...

• Вывод дня: Каждая HR-процедура должна приносить пользу!

• Задайте себе вопрос: что мои сотрудники скажут...

Поделитесь, какие HR-процессы требуют оптимизации? 👇

#HR #управление #советы

⸻
СТРУКТУРА ДЗЕН ПОСТА ({zen_chars_min}-{zen_chars_max} символов):

1. ХУК: 1-2 предложения без эмодзи
2. ОСНОВНОЙ ТЕКСТ: абзацы без отступов
3. ФАКТЫ или ЦИФРЫ (если есть)
4. ВЫВОД
5. ВОПРОС для обсуждения
6. ПОДПИСЬ "Главная Видео Статьи Новости Подписки"

Пример Дзен поста:
Знаете, какая самая частая причина увольнений? Не низкая зарплата! А отсутствие признания.

Да-да, банальное "спасибо" от руководителя может удержать сотрудника лучше премии.

Мой знакомый HR-директор внедрил систему обратной связи. Увольняемость упала на 35%.

Казалось бы, малость. Но для человека важно чувствовать, что его вклад ценят.

Как вы считаете, достаточно ли внимания уделяется признанию в вашей компании?

Главная Видео Статьи Новости Подписки

⸻
ВАЖНО:
• Telegram: {tg_chars_min}-{tg_chars_max} символов
• Дзен: {zen_chars_min}-{zen_chars_max} символов
• Дзен НИКОГДА не превышает {zen_chars_max} символов!
• Дзен БЕЗ эмодзи!

⸻
ПОИСКОВЫЙ ЗАПРОС для картинки:
После постов создай один запрос

⸻
ФОРМАТ ОТВЕТА (ТОЧНО ТАК!):

Telegram-пост:
[Сюда текст для Telegram с отступами для пунктов]

Дзен-пост:
[Сюда текст для Дзен без отступов в начале абзацев]

Поисковый запрос для изображения:
[Один запрос]

⸻
НАЧИНАЙ!"""

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

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "maxOutputTokens": 2500,
                        "topP": 0.9,
                        "topK": 30
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
                        
                        if "Telegram-пост:" in generated_text and "Дзен-пост:" in generated_text:
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
        """Разделяет текст на Telegram и Zen посты"""
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
        zen_start = combined_text.find("Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Telegram
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Дзен
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Дзен-пост:", "").strip()
            
            return tg_text, zen_text, image_query
        
        return None, None, image_query

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram СОХРАНЯЯ отступы для пунктов"""
        if not text:
            return ""
        
        # Очищаем
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Сохраняем отступы для пунктов, убираем для обычного текста
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.rstrip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Сохраняем отступы для пунктов (начинаются с •)
            if line.strip().startswith('•'):
                # Добавляем отступ 12 пробелов перед пунктом
                formatted_lines.append("            " + line.strip())
            else:
                # Обычный текст без отступа
                formatted_lines.append(line.strip())
        
        formatted_text = '\n'.join(formatted_lines)
        
        # Убираем лишние пустые строки, но сохраняем разделение
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        # Добавляем хештеги если нет
        if not re.search(r'#\w+', formatted_text):
            formatted_text = self.add_telegram_hashtags(formatted_text, self.current_theme)
        
        return formatted_text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзен БЕЗ отступов"""
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
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # Убираем ВСЕ отступы в начале строк
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
        
        # Добавляем подпись
        formatted_text = '\n\n'.join(lines)
        formatted_text = self.ensure_zen_signature(formatted_text)
        
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

    def add_telegram_hashtags(self, text, theme):
        """Добавляет хештеги для Telegram"""
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера", "#работа"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#бренд", "#пиар"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#дом", "#интерьер"]
        }
        
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы"])
        hashtags_to_add = random.sample(base_hashtags, min(5, len(base_hashtags)))
        
        hashtags_line = " ".join(hashtags_to_add)
        return f"{text}\n\n{hashtags_line}"

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
            unique_id = hash(f"{theme}{time.time()}") % 1000
            return f"https://picsum.photos/{width}/{height}?random={unique_id}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/{width}/{height}"

    def generate_image_search_query(self, text, theme):
        """Генерирует поисковый запрос для изображения"""
        try:
            if self.last_image_query:
                return self.last_image_query
            
            theme_keywords = {
                "HR и управление персоналом": ["офис", "команда", "бизнес", "управление"],
                "PR и коммуникации": ["коммуникация", "медиа", "маркетинг", "бренд"],
                "ремонт и строительство": ["ремонт", "строительство", "инструменты", "дом"]
            }
            
            keywords = theme_keywords.get(theme, ["бизнес", "профессия"])
            main_keyword = random.choice(keywords)
            
            image_query = f"{main_keyword} работа профессия"
            return image_query
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации запроса: {e}")
            return "бизнес профессия"

    def check_length_and_fix(self, text, max_length, is_telegram=True):
        """Проверяет длину и исправляет если нужно"""
        current_len = len(text)
        
        if current_len <= max_length:
            return text
        
        logger.warning(f"⚠️ Текст превышает лимит ({current_len} > {max_length}), сокращаю...")
        
        # Сохраняем хештеги для Telegram
        if is_telegram:
            hashtags_match = re.search(r'(#\w+\s*)+$', text)
            hashtags = hashtags_match.group(0) if hashtags_match else ""
            text_without_hashtags = text[:hashtags_match.start()] if hashtags_match else text
        else:
            hashtags = ""
            text_without_hashtags = text
        
        # Сокращаем основной текст
        target_length = max_length - len(hashtags) - 20  # Запас
        
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
            elif utc_hour == 11:  # 14:00 МСК
                time_key = "14:00"
            elif utc_hour == 16:  # 19:00 МСК
                time_key = "19:00"
            else:
                now = self.get_moscow_time()
                current_hour = now.hour
                
                if 5 <= current_hour < 12:
                    time_key = "09:00"
                elif 12 <= current_hour < 17:
                    time_key = "14:00"
                else:
                    time_key = "19:00"
            
            time_slot_info = self.time_slots[time_key]
            schedule_time = time_key
            
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
            
            # Форматируем
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            # Проверяем длину
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            logger.info(f"📊 Telegram: {tg_len} символов (диапазон: {tg_min}-{tg_max})")
            logger.info(f"📊 Дзен: {zen_len} символов (диапазон: {zen_min}-{zen_max})")
            
            # Проверяем и корректируем длину
            if tg_len > tg_max:
                tg_text = self.check_length_and_fix(tg_text, tg_max, True)
                tg_len = len(tg_text)
                logger.info(f"📊 Telegram после коррекции: {tg_len} символов")
            
            if zen_len > zen_max:
                zen_text = self.check_length_and_fix(zen_text, zen_max, False)
                zen_len = len(zen_text)
                logger.info(f"📊 Дзен после коррекции: {zen_len} символов")
            
            # Картинки
            logger.info("🖼️ Ищем картинки...")
            tg_image_url = self.get_fresh_image(tg_text, self.current_theme)
            time.sleep(1)
            zen_image_url = self.get_fresh_image(zen_text, self.current_theme)
            
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
                logger.info("\n" + "=" * 60)
                logger.info("🎉 УСПЕХ! Посты отправлены!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Дзен: {zen_len} символов")
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

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def get_moscow_time(self):
        """Возвращает время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB BOT: ФИКСИРОВАННАЯ СТРУКТУРА ПОСТОВ")
    print("=" * 80)
    print("📋 Структура постов:")
    print("   TELEGRAM:")
    print("   • Хук с эмодзи")
    print("   • Пункты с отступами (•)")
    print("   • Хештеги")
    print("\n   ДЗЕН:")
    print("   • Хук без эмодзи")
    print("   • Абзацы без отступов")
    print("   • Подпись 'Главная Видео...'")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты с правильной структурой отправлены")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
