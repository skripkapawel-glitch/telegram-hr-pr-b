import os
import requests
import random
import json
import time
import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка сессии requests для повторных попыток
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Список доступных моделей для тестирования
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# Сервисы с реальными изображениями
REAL_IMAGE_SERVICES = [
    {
        "name": "Unsplash",
        "url": "https://source.unsplash.com/featured/1200x630/?",
        "quality": "high"
    },
    {
        "name": "Pexels",
        "url": "https://images.pexels.com/photos/",
        "quality": "high"
    },
    {
        "name": "Pixabay",
        "url": "https://pixabay.com/get/",
        "quality": "high"
    }
]

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Канал: {MAIN_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.working_model = None
        self.fallback_text = "Извините, произошла ошибка при генерации контента."
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "short", 
                "name": "Утренний пост", 
                "emoji": "🌅",
                "tg_words": "130-160 слов",
                "zen_words": "300-400 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },
            "14:00": {
                "type": "long", 
                "name": "Обеденный пост", 
                "emoji": "🌞",
                "tg_words": "150-180 слов",
                "zen_words": "400-500 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },  
            "19:00": {
                "type": "medium", 
                "name": "Вечерний пост", 
                "emoji": "🌙",
                "tg_words": "140-170 слов",
                "zen_words": "350-450 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            }
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office,business,teamwork,meeting,workplace",
                "human resources,recruitment,interview,career",
                "corporate,management,leadership,employees",
                "work,success,collaboration,communication"
            ],
            "PR и коммуникации": [
                "public relations,media,communication,marketing",
                "social media,branding,networking,advertising",
                "press,conference,event,strategy",
                "digital marketing,content,influencer"
            ],
            "ремонт и строительство": [
                "construction,building,renovation,repair",
                "tools,workers,architecture,design",
                "interior,home,project,contractor",
                "diy,handyman,construction site"
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
                "full_posts": {}, 
                "used_images": {}, 
                "last_post_time": None,
                "last_model": None
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {}, 
                "themes": {}, 
                "full_posts": {}, 
                "used_images": {}, 
                "last_post_time": None,
                "last_model": None
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def test_gemini_model(self, model_name):
        """Тестирует модель Gemini"""
        logger.info(f"Тестируем модель: {model_name}")
        
        if self.post_history.get("last_model") == model_name:
            logger.info(f"Модель {model_name} работала в прошлый раз")
            return model_name
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        test_data = {
            "contents": [{
                "parts": [{"text": "Ответь одним словом: 'OK'"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10,
            }
        }
        
        try:
            response = session.post(url, json=test_data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    logger.info(f"Модель {model_name} работает!")
                    self.post_history["last_model"] = model_name
                    self.save_post_history()
                    return model_name
                else:
                    logger.warning(f"Модель {model_name}: неверный формат ответа")
                    return None
            elif response.status_code == 429:
                logger.warning(f"Модель {model_name}: лимит запросов (429)")
                return None
            elif response.status_code == 404:
                logger.warning(f"Модель {model_name}: не найдена (404)")
                return None
            else:
                logger.warning(f"Модель {model_name}: ошибка {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Модель {model_name}: ошибка подключения - {e}")
            return None

    def find_working_model(self):
        """Ищет рабочую модель Gemini"""
        logger.info("Ищем рабочую модель Gemini...")
        
        last_model = self.post_history.get("last_model")
        if last_model and last_model in GEMINI_MODELS:
            logger.info(f"Пробуем последнюю рабочую модель: {last_model}")
            working_model = self.test_gemini_model(last_model)
            if working_model:
                self.working_model = working_model
                logger.info(f"Выбрана модель: {self.working_model}")
                return True
        
        for model in GEMINI_MODELS:
            if model == last_model:
                continue
            working_model = self.test_gemini_model(model)
            if working_model:
                self.working_model = working_model
                logger.info(f"Выбрана модель: {self.working_model}")
                return True
        
        logger.error("Не найдено ни одной рабочей модели!")
        return False

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом истории и времени"""
        try:
            channel_key = str(channel_id)
            themes_history = self.post_history.get("themes", {}).get(channel_key, [])
            
            current_hour = datetime.now().hour
            available_themes = self.themes.copy()
            
            if 6 <= current_hour < 12:
                preferred_themes = ["HR и управление персоналом", "ремонт и строительство"]
            elif 12 <= current_hour < 18:
                preferred_themes = ["PR и коммуникации", "HR и управление персоналом"]
            else:
                preferred_themes = ["ремонт и строительство", "PR и коммуникации"]
            
            available_themes.sort(key=lambda x: preferred_themes.index(x) if x in preferred_themes else len(preferred_themes))
            
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes[:2]) if len(available_themes) > 1 else available_themes[0]
            
            if "themes" not in self.post_history:
                self.post_history["themes"] = {}
            if channel_key not in self.post_history["themes"]:
                self.post_history["themes"][channel_key] = []
            
            self.post_history["themes"][channel_key].append(theme)
            if len(self.post_history["themes"][channel_key]) > 10:
                self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-8:]
            
            self.save_post_history()
            return theme
            
        except Exception as e:
            logger.error(f"Ошибка выбора темы: {e}")
            return random.choice(self.themes)

    def get_tg_type_by_time(self):
        """Определяет тип поста по времени"""
        try:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            closest_slot = None
            min_diff = float('inf')
            
            for slot_time in self.time_slots.keys():
                slot_datetime = datetime.strptime(slot_time, "%H:%M").replace(
                    year=now.year, 
                    month=now.month, 
                    day=now.day
                )
                diff = abs((now - slot_datetime).total_seconds())
                
                if diff < min_diff:
                    min_diff = diff
                    closest_slot = slot_time
            
            if closest_slot is None:
                closest_slot = "19:00"
            
            post_type_info = self.time_slots.get(closest_slot, self.time_slots["19:00"])
            
            logger.info(f"Текущее время: {current_time_str}")
            logger.info(f"Ближайший слот: {closest_slot} - {post_type_info['name']}")
            
            return post_type_info['type'], closest_slot, post_type_info['emoji'], post_type_info
            
        except Exception as e:
            logger.error(f"Ошибка определения типа поста: {e}")
            return "medium", "19:00", "📝", self.time_slots["19:00"]

    def check_last_post_time(self):
        """Проверяет, когда был последний пост"""
        try:
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                logger.info(f"Последний пост был: {last_time.strftime('%Y-%m-%d %H:%M')}")
                logger.info(f"Прошло часов: {hours_since_last:.1f}")
                
                if hours_since_last < 4:
                    logger.info("Пост был недавно, пропускаем отправку")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки времени: {e}")
            return True

    def update_last_post_time(self):
        """Обновляет время последнего поста"""
        try:
            self.post_history["last_post_time"] = datetime.now().isoformat()
            self.save_post_history()
        except Exception as e:
            logger.error(f"Ошибка обновления времени: {e}")

    def format_with_tabs_and_bullets(self, text):
        """Форматирует текст с табами и буллетами •"""
        if not text or not text.strip():
            return self.fallback_text
        
        # Убираем все символы форматирования
        text = text.replace('*', '').replace('#', '').replace('**', '')
        text = text.replace('дней назад', '').replace('день назад', '')
        
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Определяем, нужно ли добавлять отступ и буллет
            # Если строка похожа на элемент списка
            if line.startswith(('•', '-', '—', '▪', '○', '›', '»', '‣')):
                # Убираем старый маркер и добавляем правильный с табом
                clean_line = line.lstrip('•-—▪○›»‣ ')
                formatted_line = f"  • {clean_line}"  # Два таба + буллет
                formatted_lines.append(formatted_line)
            elif any(line.lower().startswith(x) for x in ['пункт', 'во-первых', 'во-вторых', 'в-третьих', 'пример', 'совет', 'кейс', 'тренд']):
                # Для ключевых элементов тоже добавляем отступ
                formatted_line = f"  • {line}"  # Два таба + буллет
                formatted_lines.append(formatted_line)
            elif line.lower().startswith(('ключевой', 'главный', 'важный', 'основной')):
                # Заголовки разделов
                formatted_lines.append(f"\n{line}")
            else:
                # Обычный текст
                formatted_lines.append(line)
        
        # Добавляем пустую строку перед списками для лучшей читаемости
        result = '\n'.join(formatted_lines)
        
        # Заменяем множественные пустые строки на одинарные
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result

    def create_telegram_prompt(self, theme, time_slot_info):
        """Создает промпт для Telegram"""
        tg_words = time_slot_info['tg_words']
        
        prompt = f"""Напиши пост для Telegram-канала на тему: "{theme}"

ВАЖНО для форматирования:
• Используй отступы (табуляцию) для элементов списка
• Используй символ • (точка в середине строки) для маркированных списков
• Добавь визуальное разделение с помощью отступов

Формат поста:
1. Интересный вопрос или провокация
2. Краткий анализ ситуации
3. Ключевые тренды (с отступами и буллетами •)
4. Конкретные примеры/кейсы (с отступами)
5. Практические советы (с отступами)
6. Вопрос для обсуждения
7. 3-5 релевантных хештегов

Требования:
- Объем: {tg_words}
- Говори о 2025-2026 годах
- Используй отступы для визуального разделения
- Для списков используй: [TAB][TAB]• [текст]
- НЕ используй *, #, ** в тексте
- НЕ пиши "дней назад"

Пример правильного форматирования:
  • Ключевой тренд: AI в рекрутинге
  • Пример: Компания X внедрила AI-скрининг
  • Совет: Начните с пилотного проекта

Тема: {theme} (тренды 2025-2026)"""

        return prompt

    def create_zen_prompt(self, theme, time_slot_info):
        """Создает промпт для Яндекс.Дзен"""
        zen_words = time_slot_info['zen_words']
        
        prompt = f"""Напиши пост для Яндекс.Дзен на тему: "{theme}"

ВАЖНО для форматирования:
• Используй отступы (табуляцию) для лучшей читаемости
• Используй символ • для маркированных списков
• Структурируй текст с визуальными разделениями

Требования:
- Объем: {zen_words}
- Говори о 2025-2026 годах
- Профессионально, но доступно
- Используй факты, статистику, данные
- Для списков используй отступы: [TAB][TAB]• [текст]
- Не используй *, #, **
- НЕ пиши "дней назад"
- Сделай пост полезным и информативным

Пример структуры:
[Основной текст]

Ключевые направления:

  • Направление 1: описание
  • Направление 2: описание
  • Направление 3: описание

[Продолжение текста]

Тема: {theme} (прогнозы на 2025-2026 год)"""

        return prompt

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерирует текст с повторными попытками"""
        if not self.working_model:
            logger.error("Не выбрана рабочая модель Gemini")
            return None
            
        for attempt in range(max_attempts):
            try:
                logger.info(f"Попытка {attempt + 1}/{max_attempts} (модель: {self.working_model})...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.working_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topK": 40,
                        "topP": 0.9,
                        "maxOutputTokens": 1024,
                    }
                }
                
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        if generated_text and generated_text.strip():
                            logger.info("Текст успешно сгенерирован!")
                            return generated_text.strip()
                
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                if attempt < max_attempts - 1:
                    time.sleep((attempt + 1) * 3)
        
        logger.error("Не удалось сгенерировать контент")
        return None

    def generate_tg_post(self, theme, time_slot_info):
        """Генерирует пост для Telegram"""
        try:
            prompt = self.create_telegram_prompt(theme, time_slot_info)
            raw_text = self.generate_with_gemini(prompt)
            if raw_text:
                formatted_text = self.format_with_tabs_and_bullets(raw_text)
                return formatted_text
            return self.fallback_text
        except Exception as e:
            logger.error(f"Ошибка генерации ТГ поста: {e}")
            return self.fallback_text

    def generate_zen_post(self, theme, time_slot_info):
        """Генерирует пост для Дзена"""
        try:
            prompt = self.create_zen_prompt(theme, time_slot_info)
            raw_text = self.generate_with_gemini(prompt)
            if raw_text:
                formatted_text = self.format_with_tabs_and_bullets(raw_text)
                return f"{theme}\n\n{formatted_text}\n\nГлавная Видео Статьи Новости Подписки"
            return self.fallback_text
        except Exception as e:
            logger.error(f"Ошибка генерации Дзен поста: {e}")
            return self.fallback_text

    def get_real_image_url(self, theme):
        """Получает URL реального изображения"""
        logger.info(f"Поиск реального изображения для: {theme}")
        
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keywords = random.choice(keywords_list).split(',')
            primary_keyword = keywords[0].strip()
            
            services = random.sample(REAL_IMAGE_SERVICES, len(REAL_IMAGE_SERVICES))
            
            for service in services:
                try:
                    if service["name"] == "Unsplash":
                        encoded_keywords = quote_plus(primary_keyword)
                        url = f"{service['url']}{encoded_keywords}&sig={random.randint(1, 10000)}"
                        
                    elif service["name"] == "Pexels":
                        pexels_id = random.randint(1, 1000000)
                        url = f"{service['url']}{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w=1200&h=630&fit=crop"
                        
                    elif service["name"] == "Pixabay":
                        url = f"https://pixabay.com/get/g{random.randint(1000000000, 9999999999)}.jpg"
                    
                    logger.info(f"Пробуем сервис: {service['name']}")
                    response = session.head(url, timeout=5, allow_redirects=True)
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'image' in content_type:
                            logger.info(f"✅ Найдено изображение: {service['name']}")
                            return url
                        
                except Exception as e:
                    logger.debug(f"Сервис {service['name']} не доступен: {e}")
                    continue
            
            logger.warning("Все сервисы недоступны, используем Unsplash fallback")
            fallback_url = f"https://source.unsplash.com/featured/1200x630/?{quote_plus(primary_keyword)}"
            return fallback_url
            
        except Exception as e:
            logger.error(f"Ошибка поиска изображения: {e}")
            return "https://source.unsplash.com/featured/1200x630/?business"

    def download_image(self, url):
        """Скачивает изображение для отправки"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Скачивание изображения (попытка {attempt + 1})...")
                response = session.get(url, timeout=15, stream=True)
                
                if response.status_code == 200:
                    content = response.content
                    if len(content) > 10240:
                        logger.info(f"Изображение скачано: {len(content)} байт")
                        return content
                    else:
                        logger.warning("Изображение слишком маленькое")
                else:
                    logger.warning(f"Ошибка HTTP: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Ошибка скачивания: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        logger.error("Не удалось скачать изображение")
        return None

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram С ФОТО"""
        logger.info(f"Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            logger.error("Отсутствует BOT_TOKEN")
            return False
        
        # Обрезаем текст если слишком длинный
        max_length = 1024
        
        if len(text) > max_length:
            logger.warning(f"Текст длинный ({len(text)}), обрезаем до {max_length}...")
            cutoff = text[:max_length-100].rfind('\n')
            if cutoff > max_length * 0.6:
                text = text[:cutoff]
            else:
                text = text[:max_length-3] + "..."
        
        try:
            # ВСЕГДА ОТПРАВЛЯЕМ С ФОТО!
            if not image_url:
                image_url = self.get_real_image_url(self.current_theme)
            
            logger.info(f"Отправка поста с изображением: {image_url[:80]}...")
            
            # Для Telegram используем HTML разметку для сохранения отступов
            html_text = text.replace('\n', '<br>').replace('  ', '&emsp;&emsp;')
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': html_text,
                    'parse_mode': 'HTML'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Пост с фото отправлен в {chat_id}")
                return True
            else:
                logger.warning(f"Ошибка отправки фото по URL ({response.status_code}): {response.text[:200]}")
                
                # Пробуем скачать и отправить
                image_data = self.download_image(image_url)
                if image_data:
                    files = {'photo': ('image.jpg', image_data, 'image/jpeg')}
                    data = {
                        'chat_id': chat_id,
                        'caption': html_text,
                        'parse_mode': 'HTML'
                    }
                    
                    response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data=data,
                        files=files,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Пост с фото (скачанным) отправлен в {chat_id}")
                        return True
            
            # Если не удалось с фото, отправляем текстовый пост
            logger.info("Пробуем отправить текстовый пост...")
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'HTML'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текстовый пост отправлен в {chat_id}")
                return True
            else:
                logger.error(f"❌ Ошибка отправки текста ({response.status_code}): {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            return False

    def send_dual_posts(self):
        """Основной метод отправки постов С ФОТО"""
        try:
            if not self.check_last_post_time():
                logger.info("⏭️ Пропускаем отправку - недавно уже был пост")
                return True
                
            if not self.find_working_model():
                logger.error("❌ Не удалось найти рабочую модель Gemini")
                return False
            
            # Выбираем тему
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            tg_type, time_slot, time_emoji, time_slot_info = self.get_tg_type_by_time()
            
            logger.info(f"🎯 Тема: {self.current_theme}")
            logger.info(f"📅 Год: 2025-2026")
            
            # Генерируем посты
            logger.info("🧠 Генерация Telegram поста...")
            tg_post = self.generate_tg_post(self.current_theme, time_slot_info)
            
            logger.info("🧠 Генерация Дзен поста...")
            zen_post = self.generate_zen_post(self.current_theme, time_slot_info)
            
            logger.info(f"📈 Статистика постов:")
            logger.info(f"  📱 ТГ-пост: {len(tg_post)} символов")
            logger.info(f"  📄 Дзен-пост: {len(zen_post)} символов")
            
            # Получаем РЕАЛЬНЫЕ ИЗОБРАЖЕНИЯ
            logger.info("🖼️ Поиск реальных изображений...")
            tg_image_url = self.get_real_image_url(self.current_theme)
            time.sleep(2)
            zen_image_url = self.get_real_image_url(self.current_theme)
            
            logger.info(f"📸 Изображения получены:")
            logger.info(f"  ТГ: {tg_image_url[:80]}...")
            logger.info(f"  Дзен: {zen_image_url[:80]}...")
            
            # Отправляем посты С ИЗОБРАЖЕНИЯМИ
            logger.info("📤 Отправляем посты с изображениями...")
            
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, tg_image_url)
            time.sleep(3)
            
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, zen_image_url)
            
            if tg_success or zen_success:
                if tg_success and zen_success:
                    logger.info("✅ ОБА поста успешно отправлены с реальными изображениями!")
                elif tg_success:
                    logger.info("✅ Только Telegram пост отправлен")
                else:
                    logger.info("✅ Только Дзен пост отправлен")
                
                self.update_last_post_time()
                return True
            else:
                logger.error("❌ Не удалось отправить ни один пост")
                return False
                
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Автоматический подбор рабочей модели Gemini")
    print("🎯 Умный подбор тем по времени суток")
    print("🎯 Контроль частоты постов")
    print("🎯 ОБЯЗАТЕЛЬНО ФОТО в каждом посте!")
    print("🎯 Отступы и буллеты • для визуального разделения")
    print("🎯 Год: 2025-2026")
    print("🎯 Без шаблонов - AI сам пишет")
    print("=" * 80)
    
    if not BOT_TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден!")
        return
    
    if not GEMINI_API_KEY:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: GEMINI_API_KEY не найден!")
        return
    
    try:
        bot = AIPostGenerator()
        success = bot.send_dual_posts()
        
        if success:
            print("\n✅ УСПЕХ! AI посты с реальными фото и отступами отправлены!")
        else:
            print("\n⚠️  ПРЕДУПРЕЖДЕНИЕ: Не все посты удалось отправить")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
