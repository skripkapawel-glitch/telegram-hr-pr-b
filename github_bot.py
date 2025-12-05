import os
import requests
import random
import json
import time
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus
import io

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
ZEN_CHANNEL_ID = "@tehdzemm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Проверка обязательных переменных
if not BOT_TOKEN:
    logger.error("❌ Отсутствует BOT_TOKEN")
    exit(1)
if not GEMINI_API_KEY:
    logger.error("❌ Отсутствует GEMINI_API_KEY")
    exit(1)

# Настройка сессии requests с ретраями
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

# Настройка retry стратегии
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

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

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.working_model = None
        
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

        # Ключевые слова для изображений (упрощенные)
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting",
                "human resources",
                "workplace collaboration",
                "business professionals"
            ],
            "PR и коммуникации": [
                "public relations",
                "social media",
                "communication",
                "marketing"
            ],
            "ремонт и строительство": [
                "construction",
                "renovation",
                "tools",
                "architecture"
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

    def find_working_model(self):
        """Ищет рабочую модель Gemini"""
        try:
            models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
            
            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                test_data = {
                    "contents": [{"parts": [{"text": "Test"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                }
                
                try:
                    response = session.post(url, json=test_data, timeout=15)
                    if response.status_code == 200:
                        self.working_model = model
                        logger.info(f"✅ Выбрана модель: {model}")
                        return True
                except Exception as e:
                    logger.warning(f"Модель {model} недоступна: {e}")
                    continue
            
            logger.error("❌ Не найдено рабочей модели")
            return False
        except Exception as e:
            logger.error(f"Ошибка поиска модели: {e}")
            return False

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
        """Промт для Telegram"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['tg_chars']
        
        if slot_type == "morning":
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — энергичный утренний старт

Требования:
1. Начни с сильного хука в первых 1-2 строках, чтобы сразу зацепить
2. Структура:
   • Перечисли 2-4 коротких тезиса
   • Минимальный объем воды
   • Финал — простой вопрос, провоцирующий комментарии
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML или markdown разметку
6. Используй обычный текст с переносами строк
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Пример структуры:
Мощный хук

Основная мысль

• Пункт 1
• Пункт 2

Вопрос для обсуждения

#хештег1 #хештег2

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — аналитика + живой язык

Требования:
1. Добавь мощный хук, который создаёт интригу
2. Структура:
   • Раскрой тему глубже, чем в утреннем посте
   • Добавь mini-story или кейс
   • Сделай вывод
   • Задай провокационный вопрос, вызывающий дискуссию
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычный текст
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука
8. Сделай разбивку на абзацы для легкой читабельности

Тема: {theme}"""

        else:  # evening
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — расслабленный, но цепляющий

Требования:
1. Хук должен бить в эмоцию
2. Структура:
   • Перечисли 2-3 мысли
   • Добавь короткое наблюдение или личный инсайт
   • Вызови эмоцию
   • В конце — простой CTA: "Как вы думаете?"
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычный текст
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Тема: {theme}"""

    def create_zen_prompt(self, theme, time_slot_info):
        """Промт для Яндекс.Дзен"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['zen_chars']
        
        if slot_type == "morning":
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков

Требования:
1. Добавь мощный хук, который удерживает первые 5 секунд
2. Структура:
   • Подай тему легко, без перегруза
   • В тексте — микросюжет или пример
   • Финал — вопрос для комментариев
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычный текст с абзацами
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши длинный пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков

Требования:
1. Добавь сильный хук, интригу или сюжет
2. Структура:
   • Сделай разбор темы
   • Вставь мини-кейс / историю / данные
   • Сделай полезный вывод
   • Финал с CTA для обсуждения
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычный текст
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Тема: {theme}"""

        else:  # evening
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — лёгкий вечерний

Требования:
1. Хук должен цеплять эмоцией или неожиданным фактом
2. Структура:
   • Короткая мысль, инсайт
   • Вывод
   • Финальный вопрос
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычный текст
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Тема: {theme}"""

    def generate_with_gemini(self, prompt):
        """Генерирует текст"""
        if not self.working_model:
            logger.error("Рабочая модель не выбрана")
            return None
            
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.working_model}:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "topK": 40,
                    "topP": 0.9,
                    "maxOutputTokens": 4000,
                }
            }
            
            logger.info(f"Генерация текста с моделью {self.working_model}...")
            response = session.post(url, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    if generated_text and generated_text.strip():
                        logger.info("✅ Текст успешно сгенерирован")
                        return generated_text.strip()
                    else:
                        logger.warning("Сгенерирован пустой текст")
                else:
                    logger.warning("Нет кандидатов в ответе")
            else:
                logger.error(f"Ошибка API: {response.status_code} - {response.text}")
            
            return None
                
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return None

    def get_image_url(self, theme):
        """Получает URL изображения - УПРОЩЕННАЯ ВЕРСИЯ"""
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords_list)
            
            # Unsplash с простыми параметрами
            width, height = 1200, 630
            
            # Варианты источников (только Unsplash)
            urls = [
                f"https://source.unsplash.com/{width}x{height}/?{quote_plus(keyword)}",
                f"https://source.unsplash.com/featured/{width}x{height}/?{quote_plus(keyword)}",
                f"https://source.unsplash.com/random/{width}x{height}/?{quote_plus(keyword.split()[0])}",
            ]
            
            # Добавляем timestamp для уникальности
            timestamp = int(time.time())
            
            for url in urls:
                try:
                    url_with_timestamp = f"{url}&t={timestamp}"
                    logger.info(f"🔍 Пробуем: {url_with_timestamp[:80]}...")
                    
                    # Быстрая проверка HEAD запросом
                    response = session.head(url_with_timestamp, timeout=5, allow_redirects=True)
                    
                    if response.status_code == 200:
                        final_url = response.url
                        logger.info(f"✅ Изображение найдено: {final_url}")
                        return final_url
                    
                except Exception as e:
                    logger.debug(f"Источник недоступен: {e}")
                    continue
            
            # Fallback - самый простой вариант
            fallback = f"https://source.unsplash.com/{width}x{height}/?{quote_plus(theme.split()[0])}&t={timestamp}"
            logger.warning(f"🔄 Используем fallback: {fallback}")
            return fallback
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения: {e}")
            return f"https://source.unsplash.com/1200x630/?business&t={int(time.time())}"

    def clean_text(self, text, max_length=1024):
        """Очищает текст от разметки и форматирует"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы
        replacements = {
            '&nbsp;': ' ',
            '&emsp;': '    ',
            '&ensp;': '  ',
            ' ': '    ',  # em space
            ' ': '  ',   # en space
            ' ': ' ',    # non-breaking space
            '•': '•',    # сохраняем буллет
            '—': '-',
            '–': '-',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Удаляем строки с "Тема:", "Заголовок:"
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.lower().startswith(('тема:', 'заголовок:', 'топик:', '##')):
                clean_lines.append(line)
        
        text = '\n'.join(clean_lines)
        
        # Обрезаем если нужно
        if len(text) > max_length:
            # Ищем место для обрезки в конце абзаца
            cut_pos = text[:max_length-100].rfind('\n\n')
            if cut_pos > max_length - 300:
                text = text[:cut_pos] + "\n\n..."
            else:
                text = text[:max_length-50] + "..."
        
        return text.strip()

    def send_telegram_photo(self, chat_id, photo_url, caption=""):
        """Отправляет фото в Telegram - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Сначала пытаемся отправить по URL
            params = {
                'chat_id': chat_id,
                'photo': photo_url,
            }
            
            if caption:
                # Важно: не передаем parse_mode вообще если caption пустой или None
                params['caption'] = caption[:1024]  # Ограничение Telegram
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,  # Используем params вместо json!
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в {chat_id}")
                return True
            
            error_data = response.json() if response.content else {}
            logger.warning(f"Ошибка отправки фото по URL: {response.status_code} - {error_data}")
            
            # Пробуем скачать и отправить
            time.sleep(1)
            try:
                logger.info("🔄 Пробуем скачать изображение...")
                
                img_response = session.get(photo_url, timeout=10)
                if img_response.status_code == 200 and len(img_response.content) > 10240:
                    
                    files = {'photo': ('image.jpg', img_response.content, 'image/jpeg')}
                    data = {'chat_id': chat_id}
                    
                    if caption:
                        data['caption'] = caption[:1024]
                    
                    response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data=data,
                        files=files,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Фото (скачанное) отправлено в {chat_id}")
                        return True
                    else:
                        logger.warning(f"Ошибка отправки скачанного фото: {response.status_code}")
                else:
                    logger.warning(f"Не удалось скачать изображение: {img_response.status_code}, размер: {len(img_response.content) if img_response.content else 0}")
                    
            except Exception as e:
                logger.warning(f"Ошибка скачивания фото: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            return False

    def send_telegram_message(self, chat_id, text):
        """Отправляет текстовое сообщение в Telegram"""
        try:
            # Очищаем текст
            clean_text = self.clean_text(text, max_length=4096)
            
            if not clean_text:
                logger.error("Текст пустой после очистки")
                return False
            
            # Отправляем как обычный текст (без parse_mode)
            params = {
                'chat_id': chat_id,
                'text': clean_text,
                'disable_web_page_preview': True
                # Не указываем parse_mode вообще!
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен в {chat_id}")
                return True
            
            error_data = response.json() if response.content else {}
            logger.error(f"❌ Ошибка отправки текста: {response.status_code} - {error_data}")
            
            # Если текст слишком длинный, пробуем разбить
            if response.status_code == 400 and "message is too long" in str(error_data):
                logger.info("✂️ Текст слишком длинный, пробуем разбить...")
                
                # Разбиваем по абзацам
                paragraphs = clean_text.split('\n\n')
                current_part = ""
                parts = []
                
                for para in paragraphs:
                    if len(current_part) + len(para) + 2 < 4000:
                        current_part += para + "\n\n"
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = para + "\n\n"
                
                if current_part:
                    parts.append(current_part.strip())
                
                # Отправляем части
                success = True
                for i, part in enumerate(parts):
                    if i > 0:
                        time.sleep(1)
                    
                    part_response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        params={
                            'chat_id': chat_id,
                            'text': part,
                            'disable_web_page_preview': True
                        },
                        timeout=30
                    )
                    
                    if part_response.status_code != 200:
                        success = False
                        break
                
                if success:
                    logger.info(f"✅ Текст отправлен частями в {chat_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return False

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Основная функция отправки в Telegram"""
        # Очищаем текст для caption
        caption_text = self.clean_text(text, max_length=1024)
        
        if chat_id == ZEN_CHANNEL_ID and self.current_theme:
            # Для Дзена добавляем тему в начало
            if not any(theme in caption_text[:100] for theme in self.themes):
                caption_text = f"{self.current_theme}\n\n{caption_text}"
        
        # Пробуем отправить с фото
        if image_url:
            logger.info(f"🖼️ Пробуем отправить с фото в {chat_id}")
            photo_success = self.send_telegram_photo(chat_id, image_url, caption_text)
            
            if photo_success:
                return True
            else:
                logger.info("📝 Фото не отправилось, пробуем текстовый пост")
        
        # Fallback: текстовый пост
        text_for_message = text
        if chat_id == ZEN_CHANNEL_ID and self.current_theme:
            if not any(theme in text_for_message[:100] for theme in self.themes):
                text_for_message = f"{self.current_theme}\n\n{text_for_message}"
        
        return self.send_telegram_message(chat_id, text_for_message)

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            logger.info("⏰ Проверка времени последнего поста...")
            
            # Проверка интервала между постами (минимум 3 часа)
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                if hours_since_last < 3:
                    logger.info(f"⏭️ Пропускаем - прошло всего {hours_since_last:.1f} часов")
                    return True
            
            # Поиск рабочей модели
            if not self.find_working_model():
                logger.error("❌ Не удалось найти рабочую модель Gemini")
                return False
            
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
            
            logger.info(f"🕒 Текущее время: {current_time_str}")
            logger.info(f"📅 Выбран слот: {slot_name} - {time_slot_info['emoji']} {time_slot_info['name']}")
            logger.info(f"📏 Telegram: {time_slot_info['tg_chars']} знаков")
            logger.info(f"📏 Яндекс.Дзен: {time_slot_info['zen_chars']} знаков")
            
            # Генерация Telegram поста
            logger.info("🧠 Генерация Telegram поста...")
            tg_prompt = self.create_telegram_prompt(self.current_theme, time_slot_info)
            tg_text = self.generate_with_gemini(tg_prompt)
            
            if not tg_text:
                logger.error("❌ Не удалось сгенерировать Telegram пост")
                tg_text = f"{self.current_theme}\n\nАктуальные новости и тренды! Обсудим в комментариях?\n\n#{self.current_theme.lower().replace(' ', '_')} #новости"
            
            # Генерация Дзен поста
            logger.info("🧠 Генерация Яндекс.Дзен поста...")
            zen_prompt = self.create_zen_prompt(self.current_theme, time_slot_info)
            zen_text = self.generate_with_gemini(zen_prompt)
            
            if not zen_text:
                logger.error("❌ Не удалось сгенерировать Дзен пост")
                zen_text = f"{self.current_theme}\n\nПодробный анализ и экспертные мнения по теме.\n\nГлавная Видео Статьи Новости Подписки"
            
            # Проверяем наличие подписи в Дзен посте
            if "Главная Видео Статьи Новости Подписки" not in zen_text:
                zen_text += "\n\nГлавная Видео Статьи Новости Подписки"
            
            logger.info(f"📊 Статистика генерации:")
            logger.info(f"  Telegram: {len(tg_text)} знаков")
            logger.info(f"  Яндекс.Дзен: {len(zen_text)} знаков")
            
            # Получение изображений (разные для каждого канала)
            logger.info("🖼️ Поиск изображений...")
            
            tg_image = self.get_image_url(self.current_theme)
            time.sleep(2)
            zen_image = self.get_image_url(self.current_theme)
            
            logger.info(f"📸 Telegram фото: {tg_image[:80]}...")
            logger.info(f"📸 Яндекс.Дзен фото: {zen_image[:80]}...")
            
            # Отправка постов
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку постов...")
            logger.info("=" * 50)
            
            # Telegram
            logger.info(f"📤 Отправка в Telegram канал: {MAIN_CHANNEL_ID}")
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_text, tg_image)
            
            time.sleep(3)
            
            # Яндекс.Дзен
            logger.info(f"📤 Отправка в Яндекс.Дзен канал: {ZEN_CHANNEL_ID}")
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_text, zen_image)
            
            # Обработка результатов
            if tg_success or zen_success:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if tg_success and zen_success:
                    logger.info("✅ УСПЕХ! ОБА поста отправлены!")
                elif tg_success:
                    logger.info("✅ УСПЕХ! Только Telegram пост отправлен")
                else:
                    logger.info("✅ УСПЕХ! Только Яндекс.Дзен пост отправлен")
                return True
            else:
                logger.error("❌ НЕУДАЧА! Не удалось отправить ни один пост")
                return False
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
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
    print("=" * 80)
    
    print("✅ Все переменные окружения загружены")
    
    # Создание бота
    bot = AIPostGenerator()
    
    print("\n" + "=" * 80)
    print("🚀 НАЧИНАЕМ ГЕНЕРАЦИЮ И ОТПРАВКУ ПОСТОВ...")
    print("=" * 80)
    
    try:
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n" + "=" * 80)
            print("🎉 УСПЕХ! Посты успешно сгенерированы и отправлены!")
            print("=" * 80)
            print("📅 Следующий пост можно будет отправить через 3 часа")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("ℹ️  Возможные причины:")
            print("  • Проблемы с интернет-соединением")
            print("  • Ошибки API Gemini")
            print("  • Проблемы с Telegram API")
            print("  • Отсутствие изображений")
            print("\n🔄 Попробуйте запустить снова через несколько минут")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("\n🔧 Рекомендации:")
        print("1. Проверьте переменные окружения")
        print("2. Убедитесь в наличии интернета")
        print("3. Проверьте лимиты Gemini API")
        print("4. Убедитесь, что бот добавлен в каналы")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
