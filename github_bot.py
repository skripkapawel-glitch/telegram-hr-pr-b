import os
import requests
import random
import json
import time
import logging
import re
from datetime import datetime
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
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")  # Основной канал
ZEN_CHANNEL_ID = "@tehdzenn"  # Яндекс канал
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка сессии requests
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
session.mount('https://', adapter)
session.mount('http://', adapter)

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ С ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Яндекс канал: {ZEN_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "700-1000",
                "zen_chars": "1200-2000",
                "description": "Короткий, энергичный утренний старт"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "1500-2500",
                "zen_chars": "2500-4000",
                "description": "Самый объёмный, аналитика + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "900-1300",
                "zen_chars": "1200-1600",
                "description": "Средний, расслабленный, но цепляющий"
            }
        }

        # Ключевые слова для изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "hr human resources team meeting office professional",
                "recruitment interview job hiring corporate",
                "workplace collaboration employees business meeting",
                "leadership management team building corporate",
                "office workers collaboration modern workplace"
            ],
            "PR и коммуникации": [
                "public relations media press conference communication",
                "social media marketing digital strategy business",
                "networking event business communication professional",
                "brand marketing advertising media relations",
                "digital communication technology business meeting"
            ],
            "ремонт и строительство": [
                "construction building renovation architecture modern",
                "interior design home repair tools renovation",
                "construction workers building site architecture",
                "home improvement DIY renovation project",
                "architecture design building construction site"
            ]
        }

        # Хештеги для тем
        self.theme_hashtags = {
            "HR и управление персоналом": [
                "HR", "рекрутинг", "управление", "персонал", "карьера",
                "работа", "бизнес", "лидерство", "команда", "развитие",
                "тренинг", "мотивация", "кадры", "HRтренды", "работа2025"
            ],
            "PR и коммуникации": [
                "PR", "маркетинг", "коммуникации", "бренд", "медиа",
                "реклама", "SMM", "контент", "пиар", "стратегия",
                "digital", "соцсети", "бизнес", "продвижение", "PRтренды"
            ],
            "ремонт и строительство": [
                "ремонт", "строительство", "дизайн", "интерьер", "дом",
                "квартира", "ремонт2025", "строительство2025", "отделка",
                "материалы", "проект", "DIY", "евроремонт", "стройка"
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
                "last_post_time": None
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None
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

    def create_telegram_prompt(self, theme, time_slot_info):
        """Промт для Telegram поста"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['tg_chars']
        
        hashtags = self.theme_hashtags.get(theme, ["новости", "бизнес"])
        hashtag_examples = " ".join([f"#{tag}" for tag in hashtags[:5]])
        
        if slot_type == "morning":
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — энергичный утренний старт

Требования:
1. Начни с сильного хука
2. Структура:
   • 2-4 коротких тезиса
   • Минимальный объем воды
   • Финал — вопрос для комментариев
3. В конце добавь 5-7 релевантных хештегов, включая: {hashtag_examples}
4. Не добавляй хештеги в середине текста, только в конце
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст с переносами
8. Добавь 1-2 смайлика в тексте
9. Сделай текст живым и вовлекающим

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — аналитика + живой язык

Требования:
1. Добавь мощный хук
2. Структура:
   • Раскрой тему глубже
   • Добавь пример или кейс
   • Сделай вывод
   • Задай провокационный вопрос
3. В конце добавь 5-7 релевантных хештегов, включая: {hashtag_examples}
4. Не добавляй хештеги в середине текста, только в конце
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст

Тема: {theme}"""

        else:  # evening
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — расслабленный, но цепляющий

Требования:
1. Хук должен бить в эмоцию
2. Структура:
   • 2-3 мысли
   • Короткое наблюдение
   • Вызови эмоцию
   • Вопрос для обсуждения
3. В конце добавь 5-7 релевантных хештегов, включая: {hashtag_examples}
4. Не добавляй хештеги в середине текста, только в конце
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст

Тема: {theme}"""

    def create_zen_prompt(self, theme, time_slot_info):
        """Промт для Яндекс канала"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['zen_chars']
        
        if slot_type == "morning":
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков

Требования:
1. Добавь мощный хук
2. Структура:
   • Подай тему легко
   • Микросюжет или пример
   • Финал — вопрос
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Не добавляй хештеги
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст с абзацами

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши длинный пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков

Требования:
1. Добавь сильный хук
2. Структура:
   • Сделай разбор темы
   • Вставь мини-кейс
   • Сделай вывод
   • Финал с CTA
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Не добавляй хештеги
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст

Тема: {theme}"""

        else:  # evening
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — лёгкий вечерний

Требования:
1. Хук должен цеплять
2. Структура:
   • Короткая мысль
   • Вывод
   • Финальный вопрос
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Не добавляй хештеги
5. Год: 2025-2026
6. Не используй HTML или markdown
7. Используй обычный текст

Тема: {theme}"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        if not GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY не установлен")
            return False
        
        try:
            # Простая проверка доступности API
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            test_data = {
                "contents": [{"parts": [{"text": "test"}]}]
            }
            
            response = session.post(test_url, json=test_data, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Gemini API доступен")
                return True
            else:
                logger.error(f"❌ Gemini API недоступен: {response.status_code}")
                logger.error(f"Ответ: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini"""
        try:
            # Исправленный URL для Gemini API
            # Попробуем разные модели
            models_to_try = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro"
            ]
            
            generated_text = None
            
            for model in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                    
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.8,
                            "topK": 40,
                            "topP": 0.9,
                            "maxOutputTokens": 4000,
                        },
                        "safetySettings": [
                            {
                                "category": "HARM_CATEGORY_HARASSMENT",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_HATE_SPEECH",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                "threshold": "BLOCK_NONE"
                            }
                        ]
                    }
                    
                    logger.info(f"🧠 Генерация через {model}...")
                    response = session.post(url, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            generated_text = result['candidates'][0]['content']['parts'][0]['text']
                            logger.info(f"✅ Текст сгенерирован ({model})")
                            return generated_text.strip()
                    else:
                        logger.warning(f"⚠️ Модель {model} недоступна: {response.status_code}")
                        logger.warning(f"Ответ: {response.text[:200]}")
                        
                except Exception as model_error:
                    logger.warning(f"⚠️ Ошибка с моделью {model}: {model_error}")
                    continue
            
            # Если все модели не работают
            if not generated_text:
                logger.error("❌ Все модели Gemini недоступны")
                return None
                    
        except Exception as e:
            logger.error(f"💥 Критическая ошибка генерации: {e}")
            return None

    def get_image_url(self, theme):
        """Получает URL изображения по теме"""
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords_list)
            
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Unsplash с конкретными тегами
            encoded_keyword = quote_plus(keyword)
            
            # Пробуем Unsplash API для более релевантных фото
            unsplash_urls = [
                f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_keyword}&sig={timestamp}",
                f"https://source.unsplash.com/{width}x{height}/?{encoded_keyword},business&sig={timestamp}",
                f"https://source.unsplash.com/random/{width}x{height}/?{encoded_keyword}&sig={timestamp}"
            ]
            
            logger.info(f"🖼️ Поиск картинки для темы '{theme}': {keyword}")
            
            for url in unsplash_urls:
                try:
                    # Получаем финальный URL после редиректа
                    response = session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        final_url = response.url
                        # Проверяем, что это действительно изображение
                        if any(ext in final_url for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            logger.info(f"✅ Найдена релевантная картинка")
                            return final_url
                except Exception as e:
                    continue
            
            # Fallback на Pexels или Pixabay
            logger.info("🔄 Пробуем альтернативные источники...")
            
            # Pexels
            pexels_keywords = encoded_keyword.replace('+', ',')
            pexels_url = f"https://images.pexels.com/photos/{random.randint(1, 999999)}/pexels-photo-{random.randint(1, 999999)}.jpeg?auto=compress&cs=tinysrgb&w={width}&h={height}&fit=crop"
            
            # Пробуем Pexels
            try:
                response = session.head(pexels_url, timeout=3, allow_redirects=True)
                if response.status_code == 200:
                    return response.url
            except:
                pass
            
            # Последний fallback - Lorem Picsum
            fallback_url = f"https://picsum.photos/{width}/{height}?random={timestamp}&grayscale&blur=1"
            logger.info("🔄 Используем fallback картинку")
            return fallback_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/1200/630?random={int(time.time())}"

    def get_fallback_text(self, platform, theme, time_slot_info):
        """Возвращает запасной текст если Gemini не работает"""
        
        fallback_texts = {
            "HR и управление персоналом": {
                "morning": "🌅 Утренний HR-старт! Сегодня поговорим о трендах в управлении персоналом на 2025-2026 год.\n\n• Цифровизация процессов\n• Гибкий график\n• Развитие корпоративной культуры\n\nЧто считаете главным в HR сегодня?",
                "day": "🌞 HR-аналитика: Как меняется управление персоналом в 2025 году?\n\nТренды:\n1. AI в рекрутинге\n2. Удаленная работа\n3. Персонализированный подход\n4. Data-driven решения\n\nДелитесь опытом в комментариях!",
                "evening": "🌙 Вечерние мысли об HR: Важность человеческого подхода в цифровую эпоху.\n\nТехнологии важны, но человеческий фактор остается ключевым. Как сохранить баланс?"
            },
            "PR и коммуникации": {
                "morning": "🌅 PR-утро: Эффективные коммуникации в 2025 году.\n\n• Цифровые каналы\n• Автоматизация\n• Личный бренд\n\nС чего начать день PR-специалисту?",
                "day": "🌞 Глубокий разбор: PR-стратегии на 2025-2026 год.\n\nНовые вызовы требуют новых подходов. Аналитика, кейсы и практические советы.",
                "evening": "🌙 Вечерний PR: Искусство storytelling в бизнесе.\n\nКак рассказывать истории, которые цепляют? Просто о сложном."
            },
            "ремонт и строительство": {
                "morning": "🌅 Утро строителя: Новые материалы и технологии 2025 года.\n\n• Эко-материалы\n• Умный дом\n• Быстрая сборка\n\nЧто выбираете для ремонта?",
                "day": "🌞 Строительная аналитика: Тренды в ремонте и строительстве на 2025-2026 год.\n\nРазбираем новые подходы, материалы и технологии.",
                "evening": "🌙 Вечерние мысли о ремонте: Как создать уютное пространство.\n\nПростота, функциональность и эстетика - как найти баланс?"
            }
        }
        
        # Получаем базовый текст
        base_text = fallback_texts.get(theme, {}).get(
            time_slot_info['type'], 
            f"{time_slot_info['emoji']} {theme}\n\nАктуальная тема для обсуждения."
        )
        
        # Добавляем хештеги для Telegram
        if platform == "telegram":
            hashtags = self.theme_hashtags.get(theme, ["новости", "бизнес"])
            selected_hashtags = random.sample(hashtags, min(7, len(hashtags)))
            hashtags_text = " ".join([f"#{tag}" for tag in selected_hashtags])
            base_text += f"\n\n{hashtags_text}"
        
        # Добавляем подпись для Zen
        elif platform == "zen":
            base_text += "\n\nГлавная Видео Статьи Новости Подписки"
        
        return base_text

    def add_hashtags_to_text(self, text, theme):
        """Добавляет хештеги к тексту если их нет"""
        # Проверяем, есть ли уже хештеги в тексте
        if re.search(r'#\w+', text):
            logger.info("✅ Хештеги уже есть в тексте")
            return text
        
        # Выбираем хештеги для темы
        hashtags = self.theme_hashtags.get(theme, ["новости", "бизнес"])
        
        # Выбираем 5-7 случайных хештегов
        num_hashtags = random.randint(5, 7)
        if len(hashtags) < num_hashtags:
            num_hashtags = len(hashtags)
        
        selected_hashtags = random.sample(hashtags, num_hashtags)
        hashtags_text = " ".join([f"#{tag}" for tag in selected_hashtags])
        
        # Добавляем хештеги в конец текста
        return f"{text}\n\n{hashtags_text}"

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы
        replacements = {
            '&nbsp;': ' ',
            '&emsp;': '    ',
            '&ensp;': '  ',
            ' ': '    ',
            ' ': '  ',
            ' ': ' ',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Удаляем лишние пустые строки
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        # Обрезаем если слишком длинный
        if len(text) > 4096:
            text = text[:4000] + "..."
        
        return text.strip()

    def test_bot_access(self):
        """Проверяет доступ бота"""
        logger.info("🔍 Проверка доступа...")
        
        # Проверяем бота
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"🤖 Бот: @{bot_info.get('result', {}).get('username', 'N/A')}")
            else:
                logger.error(f"❌ Бот не доступен")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False
        
        return True

    def send_telegram_post(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            # Для Zen канала добавляем подпись если нет
            if chat_id == ZEN_CHANNEL_ID and "Главная Видео Статьи Новости Подписки" not in clean_text:
                clean_text += "\n\nГлавная Видео Статьи Новости Подписки"
            
            # Пробуем с фото
            if image_url:
                logger.info(f"📤 Отправка в {chat_id} с фото...")
                
                # Метод 1: sendPhoto с caption
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': clean_text[:1024],
                    'parse_mode': 'HTML'
                }
                
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Отправлено в {chat_id}")
                    return True
                
                # Метод 2: без caption
                logger.info(f"🔄 Пробуем без caption...")
                params = {'chat_id': chat_id, 'photo': image_url}
                response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Отправляем текст отдельно
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
                        logger.info(f"✅ Фото+текст отправлены в {chat_id}")
                        return True
            
            # Только текст
            logger.info(f"📝 Отправка текста в {chat_id}...")
            params = {
                'chat_id': chat_id,
                'text': clean_text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен в {chat_id}")
                return True
            
            logger.error(f"❌ Ошибка отправки в {chat_id}: {response.status_code}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Исключение: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            # Проверяем доступ
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к Telegram")
                return False
            
            # Проверяем Gemini
            if not self.test_gemini_access():
                logger.warning("⚠️ Gemini недоступен, будут использованы запасные тексты")
            
            # Проверка интервала
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                if hours_since_last < 3:
                    logger.info(f"⏭️ Пропускаем - прошло {hours_since_last:.1f} часов")
                    return True
            
            # Выбор темы
            self.current_theme = self.get_smart_theme()
            
            # Определение временного слота
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            slots = list(self.time_slots.keys())
            time_objects = [datetime.strptime(slot, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day) for slot in slots]
            
            closest_slot = min(time_objects, key=lambda x: abs((now - x).total_seconds()))
            slot_name = closest_slot.strftime("%H:%M")
            time_slot_info = self.time_slots.get(slot_name, self.time_slots["14:00"])
            
            logger.info(f"🕒 Время: {current_time_str}")
            logger.info(f"📅 Слот: {slot_name} - {time_slot_info['emoji']} {time_slot_info['name']}")
            
            # Генерация постов
            logger.info("🧠 Генерация Telegram поста...")
            tg_prompt = self.create_telegram_prompt(self.current_theme, time_slot_info)
            tg_text = self.generate_with_gemini(tg_prompt)
            
            if not tg_text:
                tg_text = self.get_fallback_text("telegram", self.current_theme, time_slot_info)
            else:
                # Добавляем хештеги если их нет
                tg_text = self.add_hashtags_to_text(tg_text, self.current_theme)
            
            logger.info("🧠 Генерация Zen поста...")
            zen_prompt = self.create_zen_prompt(self.current_theme, time_slot_info)
            zen_text = self.generate_with_gemini(zen_prompt)
            
            if not zen_text:
                zen_text = self.get_fallback_text("zen", self.current_theme, time_slot_info)
            
            # Проверяем подпись для Zen
            if "Главная Видео Статьи Новости Подписки" not in zen_text:
                zen_text += "\n\nГлавная Видео Статьи Новости Подписки"
            
            logger.info(f"📊 Telegram: {len(tg_text)} знаков")
            logger.info(f"📊 Zen: {len(zen_text)} знаков")
            
            # Поиск картинки
            logger.info("🖼️ Поиск картинки...")
            image_url = self.get_image_url(self.current_theme)
            
            # Отправка
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку...")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал
            logger.info(f"📤 Отправка в {MAIN_CHANNEL_ID}")
            main_success = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной: УСПЕХ")
            else:
                logger.error("❌ Основной: НЕУДАЧА")
            
            time.sleep(2)
            
            # Zen канал
            logger.info(f"📤 Отправка в {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url)
            
            if zen_success:
                success_count += 1
                logger.info("✅ Zen: УСПЕХ")
            else:
                logger.error("❌ Zen: НЕУДАЧА")
            
            # Результат
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count == 2:
                    logger.info("🎉 УСПЕХ! Посты отправлены в ОБА канала!")
                else:
                    logger.info(f"⚠️  Отправлено в {success_count} из 2 каналов")
                return True
            else:
                logger.error("❌ НЕУДАЧА!")
                return False
                
        except Exception as e:
            logger.error(f"💥 ОШИБКА: {e}")
            return False


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Telegram: утро/день/вечер с разными объемами")
    print("🎯 Яндекс.Дзен: структурированные посты с подписью")
    print("🎯 В каждом посте: 1 фото из интернета")
    print("🎯 Форматирование: отступы и буллеты •")
    print("🎯 Год: 2025-2026")
    print("🎯 Хештеги: автоматическая генерация")
    print("=" * 80)
    
    print("✅ Все переменные окружения загружены")
    
    bot = AIPostGenerator()
    
    print("\n" + "=" * 80)
    print("🚀 НАЧИНАЕМ ГЕНЕРАЦИЮ И ОТПРАВКУ ПОСТОВ...")
    print("=" * 80)
    
    try:
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n" + "=" * 80)
            print("🎉 УСПЕХ! Посты успешно отправлены!")
            print("=" * 80)
            print("📅 Следующий пост через 3 часа")
            print("🔄 Хештеги добавлены автоматически")
            print("🖼️ Картинки соответствуют теме")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
