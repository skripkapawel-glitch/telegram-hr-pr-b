import os
import requests
import random
import json
import time
import logging
import re
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
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")  # Основной канал (Telegram стиль)
ZEN_CHANNEL_ID = "@tehdzenm"  # Второй канал (Telegram для Дзен стиля)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    logger.info("ℹ️ Получите ключ на: https://makersuite.google.com/app/apikey")
    exit(1)

# Настройка сессии requests
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    max_retries=3,
    pool_connections=10,
    pool_maxsize=10,
    pool_block=False
)
session.mount('https://', adapter)
session.mount('http', adapter)

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 УМНЫЙ БОТ: ГЕНЕРАЦИЯ ПОСТОВ С РЕЛЕВАНТНЫМИ ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("\n⏰ РАСПИСАНИЕ ОТПРАВКИ:")
print("   • 09:00 - Утренний пост")
print("   • 14:00 - Дневной пост")
print("   • 19:00 - Вечерний пост")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты - ТОЧНОЕ РАСПИСАНИЕ
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "400-600",
                "zen_chars": "1000-1500",
                "description": "Энергичный старт дня"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "800-1500",
                "zen_chars": "1700-2300",
                "description": "Глубокий анализ + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "600-1000",
                "zen_chars": "1500-2100",
                "description": "Рефлексивный, атмосферный"
            }
        }

        # Конкретные тематические запросы для картинок
        self.theme_image_queries = {
            "ремонт и строительство": [
                "construction renovation building site",
                "interior design home renovation",
                "construction workers tools equipment",
                "home improvement DIY project",
                "architecture building design modern",
                "construction technology innovation",
                "building materials texture detail",
                "renovation before after transformation",
                "construction safety equipment gear",
                "modern apartment renovation design"
            ],
            "HR и управление персоналом": [
                "office team meeting business",
                "human resources interview hiring process",
                "workplace diversity inclusion culture",
                "leadership management team building",
                "employee engagement motivation success",
                "remote work digital workplace future",
                "corporate training development skills",
                "team collaboration workplace office",
                "recruitment job interview process",
                "business professionals meeting discussion"
            ],
            "PR и коммуникации": [
                "public relations media communication",
                "social media marketing digital strategy",
                "brand reputation crisis management",
                "influencer marketing media relations",
                "content marketing storytelling brand",
                "communication strategy networking business",
                "digital transformation technology innovation",
                "press conference media event journalism",
                "marketing strategy planning business",
                "business communication presentation meeting"
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
            
            # Сохраняем историю
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

    def create_combined_prompt(self, theme, time_slot_info):
        """Создает промт для генерации двух текстов"""
        slot_type = time_slot_info['type']
        tg_chars = time_slot_info['tg_chars']
        zen_chars = time_slot_info['zen_chars']
        
        return f"""Ты — копирайтер, контент-мейкер и SMM-эксперт с 30+ годами опыта.
Цель — писать живые, полезные тексты, которые удерживают внимание. 
Выводи строго два текста: Telegram-пост и Дзен-пост, без лишних вступлений.

Тема: {theme}
Временной слот: {time_slot_info['name']} ({slot_type})

⸻
Telegram-пост:
• Объем: {tg_chars} символов
• Живой стиль, много эмодзи
• Блоки с отступом (4 пробела) + •

Структура поста:
• Хук (1–2 строки с эмодзи)
• 2–4 тезиса с отступом + «•»
• Мини-пример/инсайт
• Вопрос для вовлечения
• 5-7 релевантных хештегов
• Год: 2025-2026

⸻
Дзен-пост:
• Объем: {zen_chars} символов  
• Без эмодзи, как мини-статья
• Блоки с отступом (4 пробела) + •

Структура поста:
• Сильный хук
• Чёткие абзацы
• 2–4 пункта с отступом + «•»
• Мини-кейс/история
• Вывод
• Вопрос в конце
• Подпись: "Главная Видео Статьи Новости Подписки"
• Без хештегов
• Год: 2025-2026

⸻
Варианты подачи (используй подходящие):
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
ВАЖНО:
1. Соблюдай структуру: каждый тезис с новой строки, начинается с "• "
2. Telegram-пост: короткие абзацы, эмодзи, вопросы к аудитории
3. Дзен-пост: глубокий анализ, без эмодзи, подпись в конце
4. Не обрезай текст! Пиши полные предложения
5. Картинка будет подобрана автоматически по теме

Теперь создай посты на тему: "{theme}" для времени "{time_slot_info['name']}".

Формат вывода строго такой:
Telegram-пост:
[текст Telegram поста]

---

Дзен-пост:
[текст Дзен поста]"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        if not GEMINI_API_KEY:
            return False
        
        try:
            # Пробуем разные модели
            models = [
                ("gemini-2.0-flash", "v1beta"),
                ("gemini-1.5-flash", "v1"),
                ("gemini-1.5-pro", "v1"),
            ]
            
            for model, version in models:
                try:
                    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    
                    test_data = {
                        "contents": [{"parts": [{"text": "Hello"}]}],
                        "generationConfig": {"maxOutputTokens": 5}
                    }
                    
                    response = session.post(url, json=test_data, timeout=15)
                    if response.status_code == 200:
                        logger.info(f"✅ Gemini доступен ({model})")
                        self.working_model = model
                        self.api_version = version
                        return True
                except:
                    continue
            
            return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=2):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                if not hasattr(self, 'working_model'):
                    self.working_model = "gemini-2.0-flash"
                    self.api_version = "v1beta"
                
                url = f"https://generativelanguage.googleapis.com/{self.api_version}/models/{self.working_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "maxOutputTokens": 4000,
                    }
                }
                
                logger.info(f"🔄 Генерируем текст с помощью {self.working_model}...")
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        logger.info("✅ Текст сгенерирован")
                        return generated_text.strip()
                        
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        # Ищем разделитель
        separators = ["---", "——", "––––"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # Очищаем заголовки
                    tg_text = re.sub(r'^(Telegram-пост|ТГ пост):?\s*', '', tg_text, flags=re.IGNORECASE)
                    zen_text = re.sub(r'^(Дзен-пост|Дзен пост):?\s*', '', zen_text, flags=re.IGNORECASE)
                    
                    return tg_text, zen_text
        
        # Если разделитель не найден
        text_length = len(combined_text)
        if text_length > 500:
            split_point = text_length // 2
            return combined_text[:split_point].strip(), combined_text[split_point:].strip()
        
        return combined_text, combined_text

    def analyze_post_for_image(self, text, theme):
        """Анализирует пост для подбора картинки"""
        try:
            # Очищаем текст
            clean_text = re.sub(r'#\w+|http\S+|\[.*?\]', '', text)[:300].lower()
            
            # Определяем конкретную тему
            specific_topics = {
                "ремонт и строительство": {
                    "ванная": ["ванн", "сануз", "плитк", "душ", "умывальник"],
                    "кухня": ["кухн", "гарнитур", "техник", "мойк", "плит"],
                    "инструменты": ["инструмент", "дрель", "перфоратор", "отвертк", "молоток"],
                    "потолок": ["потолок", "натяжн", "гипсокартон", "подвесн"],
                    "материалы": ["материал", "краск", "обои", "шпаклевк", "грунтовк"]
                },
                "HR и управление персоналом": {
                    "собеседование": ["собеседован", "интервью", "найм", "резюме", "кандидат"],
                    "команда": ["команд", "тимбилдинг", "совмест", "коллектив", "взаимодейств"],
                    "обучение": ["обучен", "тренинг", "развитие", "курс", "навык"],
                    "оценка": ["оценк", "kpi", "эффективн", "результат", "показатель"],
                    "мотивация": ["мотивац", "стимулирован", "вознагражден", "лояльност"]
                },
                "PR и коммуникации": {
                    "соцсети": ["соцсет", "instagram", "facebook", "vk", "twitter", "tiktok"],
                    "кризис": ["кризис", "проблем", "скандал", "репутац", "имидж"],
                    "бренд": ["бренд", "имидж", "узнаваемост", "позиционирован"],
                    "контент": ["контент", "стать", "видео", "подкаст", "инфографик"],
                    "коммуникация": ["коммуникац", "общен", "диалог", "взаимодейств"]
                }
            }
            
            # Находим конкретную тему
            specific_topic = None
            for topic, keywords in specific_topics.get(theme, {}).items():
                for keyword in keywords:
                    if keyword in clean_text:
                        specific_topic = topic
                        break
                if specific_topic:
                    break
            
            if not specific_topic:
                specific_topic = "общее"
            
            # Извлекаем ключевые слова
            words = re.findall(r'\b\w{4,}\b', clean_text)
            stop_words = {'этот', 'это', 'очень', 'много', 'можно', 'нужно', 'будет', 'всего', 'который'}
            keywords = [word for word in words if word not in stop_words][:5]
            
            return {
                'specific_topic': specific_topic,
                'keywords': " ".join(keywords),
                'theme': theme
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа поста: {e}")
            return {'specific_topic': 'общее', 'keywords': theme, 'theme': theme}

    def get_post_image(self, text, theme):
        """Находит релевантную картинку для поста"""
        try:
            # Анализируем пост
            analysis = self.analyze_post_for_image(text, theme)
            specific_topic = analysis['specific_topic']
            keywords = analysis['keywords']
            
            # Создаем запрос
            if specific_topic != "общее":
                # Ищем по конкретной теме
                query_map = {
                    "ванная": "bathroom renovation design",
                    "кухня": "kitchen renovation modern", 
                    "инструменты": "construction tools equipment",
                    "потолок": "ceiling design interior",
                    "материалы": "building materials texture",
                    "собеседование": "job interview business",
                    "команда": "team meeting collaboration",
                    "обучение": "corporate training workshop",
                    "оценка": "performance review business",
                    "мотивация": "employee motivation success",
                    "соцсети": "social media digital marketing",
                    "кризис": "crisis management business",
                    "бренд": "brand identity marketing",
                    "контент": "content creation digital",
                    "коммуникация": "business communication meeting"
                }
                
                base_query = query_map.get(specific_topic, theme)
            else:
                base_query = theme
            
            # Добавляем ключевые слова
            if keywords:
                query = f"{base_query} {keywords}"
            else:
                query = base_query
            
            # Кодируем запрос
            encoded_query = quote_plus(query)
            timestamp = int(time.time())
            
            # Пробуем Unsplash
            width, height = 1200, 630
            
            unsplash_urls = [
                f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_query}&sig={timestamp}",
                f"https://images.unsplash.com/photo-{timestamp}?fit=crop&w={width}&h={height}&q=80&{encoded_query}",
            ]
            
            for url in unsplash_urls:
                try:
                    response = session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        image_url = response.url
                        logger.info(f"✅ Найдена картинка: {query}")
                        return image_url
                except:
                    continue
            
            # Fallback: гарантированные картинки
            fallback_images = {
                "ремонт и строительство": [
                    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
                    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00",
                    "https://images.unsplash.com/photo-1487958449943-2429e8be8625",
                ],
                "HR и управление персоналом": [
                    "https://images.unsplash.com/photo-1552664730-d307ca884978",
                    "https://images.unsplash.com/photo-1560264280-88b68371db39",
                    "https://images.unsplash.com/photo-1551836026-d5c2c5af78e4",
                ],
                "PR и коммуникации": [
                    "https://images.unsplash.com/photo-1533750349088-cd871a92f312",
                    "https://images.unsplash.com/photo-1542744095-fcf48d80b0fd",
                    "https://images.unsplash.com/photo-1559136555-9303baea8ebd",
                ]
            }
            
            images = fallback_images.get(theme, ["https://images.unsplash.com/photo-1497366754035-f200968a6e72"])
            selected = random.choice(images)
            logger.info(f"🔄 Используем fallback картинку для {theme}")
            return f"{selected}?w={width}&h={height}&fit=crop"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Обрезаем если слишком длинный
        if len(text) > 4090:
            text = text[:4080]
            last_period = text.rfind('.')
            if last_period > 3800:
                text = text[:last_period+1]
            text = text + "..."
        
        # Удаляем лишние пустые строки
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен поста"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def check_schedule_time(self):
        """Проверяет, настало ли время для отправки по расписанию"""
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        # Точное время слотов (допуск ±2 минуты)
        schedule_times = ["09:00", "14:00", "19:00"]
        
        for schedule_time in schedule_times:
            schedule_dt = datetime.strptime(schedule_time, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            
            # Разница в минутах
            time_diff = abs((now - schedule_dt).total_seconds() / 60)
            
            # Если время совпадает (с допуском ±2 минуты)
            if time_diff <= 2:
                # Проверяем, не отправляли ли уже в этот слот сегодня
                last_slots = self.post_history.get("last_slots", [])
                today = now.strftime("%Y-%m-%d")
                
                for slot in last_slots:
                    if slot.get("date") == today and slot.get("slot") == schedule_time:
                        logger.info(f"⏭️ Пост в {schedule_time} уже отправлен сегодня")
                        return None
                
                logger.info(f"✅ Время для отправки по расписанию: {schedule_time}")
                return schedule_time
        
        logger.info(f"⏭️ Не время для отправки (текущее: {current_time_str})")
        return None

    def test_bot_access(self):
        """Проверяет доступ бота к каналам"""
        try:
            # Проверяем бота
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code != 200:
                logger.error("❌ Бот не доступен")
                return False
            
            # Проверяем каналы
            channels = [
                ("Основной канал", MAIN_CHANNEL_ID),
                ("Второй канал", ZEN_CHANNEL_ID)
            ]
            
            for name, chat_id in channels:
                params = {'chat_id': chat_id}
                response = session.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
                    params=params,
                    timeout=10
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ {name} недоступен: {chat_id}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост с фото в Telegram"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            # Для второго канала добавляем подпись
            if chat_id == ZEN_CHANNEL_ID:
                clean_text = self.ensure_zen_signature(clean_text)
            
            # Создаем короткий caption
            caption = clean_text[:150] + "..." if len(clean_text) > 150 else clean_text
            
            # Отправляем фото с caption
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': caption[:1024],
                'parse_mode': 'HTML'
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в {chat_id}")
                
                # Отправляем полный текст отдельно
                time.sleep(1)
                
                text_params = {
                    'chat_id': chat_id,
                    'text': clean_text,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
                
                text_response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    params=text_params,
                    timeout=30
                )
                
                if text_response.status_code == 200:
                    logger.info(f"✅ Текст отправлен в {chat_id}")
                    return True
            
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self):
        """Главная функция: генерирует и отправляет посты ПО РАСПИСАНИЮ"""
        try:
            # Проверяем доступ
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            # Проверяем время по расписанию
            schedule_time = self.check_schedule_time()
            if not schedule_time:
                logger.info("⏭️ Не время для отправки по расписанию")
                return False
            
            time_slot_info = self.time_slots.get(schedule_time, self.time_slots["14:00"])
            
            logger.info("=" * 50)
            logger.info(f"🕒 ЗАПУСК ПО РАСПИСАНИЮ: {schedule_time}")
            logger.info(f"📝 Слот: {time_slot_info['name']}")
            logger.info("=" * 50)
            
            # Выбор темы
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            # Генерация постов
            logger.info("🧠 Генерируем посты...")
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info)
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            # Разделяем текст
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Проверяем структуру
            if "•" not in tg_text:
                sentences = re.split(r'(?<=[.!?])\s+', tg_text)
                tg_text = "\n• ".join(sentences)
                tg_text = "• " + tg_text
            
            if "•" not in zen_text:
                sentences = re.split(r'(?<=[.!?])\s+', zen_text)
                zen_text = "\n• ".join(sentences)
                zen_text = "• " + zen_text
            
            # Обработка текстов
            tg_text = self.clean_telegram_text(tg_text)
            zen_text = self.ensure_zen_signature(self.clean_telegram_text(zen_text))
            
            # Подбор картинок
            logger.info("🖼️ Подбираем релевантные картинки...")
            tg_image_url = self.get_post_image(tg_text, self.current_theme)
            zen_image_url = self.get_post_image(zen_text, self.current_theme)
            
            # Отправка
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Основной канал
            logger.info(f"  → Основной канал: {MAIN_CHANNEL_ID}")
            if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            
            time.sleep(3)
            
            # Второй канал
            logger.info(f"  → Второй канал: {ZEN_CHANNEL_ID}")
            if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            
            # Сохраняем историю
            if success_count > 0:
                now = datetime.now()
                self.post_history["last_post_time"] = now.isoformat()
                
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "time": now.strftime("%H:%M:%S")
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.save_post_history()
                
                logger.info("\n" + "=" * 50)
                logger.info("🎉 УСПЕХ! Посты отправлены по расписанию!")
                logger.info("=" * 50)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📱 Канал 1: {MAIN_CHANNEL_ID}")
                logger.info(f"   📱 Канал 2: {ZEN_CHANNEL_ID}")
                logger.info(f"   🖼️  Картинки: релевантные теме")
                
                # Показываем следующее время отправки
                next_times = ["09:00", "14:00", "19:00"]
                current_idx = next_times.index(schedule_time)
                next_idx = (current_idx + 1) % len(next_times)
                next_time = next_times[next_idx]
                
                logger.info(f"   ⏰ Следующий пост: {next_time}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_scheduled(self):
        """Запуск по расписанию (для cron)"""
        print("\n" + "=" * 80)
        print("⏰ ЗАПУСК ПО РАСПИСАНИЮ")
        print("=" * 80)
        
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        print(f"Текущее время: {current_time}")
        
        success = self.generate_and_send_posts()
        
        if not success:
            print("❌ Не удалось отправить посты")
        else:
            print("✅ Задание выполнено")
        
        print("=" * 80)
        return success


def main():
    """Главная функция"""
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК БОТА ДЛЯ ОТПРАВКИ ПОСТОВ ПО РАСПИСАНИЮ")
    print("=" * 80)
    print("📅 Расписание:")
    print("   • 09:00 - Утренний пост")
    print("   • 14:00 - Дневной пост")
    print("   • 19:00 - Вечерний пост")
    print(f"\n📢 Каналы:")
    print(f"   • {MAIN_CHANNEL_ID} (Telegram стиль)")
    print(f"   • {ZEN_CHANNEL_ID} (Дзен стиль)")
    print("\n🎯 Тексты:")
    print("   • AI генерация через Gemini")
    print("   • Релевантные картинки по теме")
    print("   • Полные посты без обрезки")
    print("=" * 80)
    
    # Создаем экземпляр бота
    bot = AIPostGenerator()
    
    # Запускаем один раз (предполагается запуск через cron в 09:00, 14:00, 19:00)
    success = bot.run_scheduled()
    
    if success:
        print("\n✅ Бот успешно выполнил задание")
    else:
        print("\n❌ Бот завершился с ошибкой")
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
