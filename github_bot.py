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

# Список доступных моделей для тестирования (обновленный)
GEMINI_MODELS = [
    "gemini-2.0-flash",  # Первым тестируем работающую модель
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# Резервные URL для изображений
IMAGE_SERVICES = [
    "https://picsum.photos/1200/630",  # Service 1: Lorem Picsum
    "https://source.unsplash.com/1200x630/",  # Service 2: Unsplash Source
    "https://dummyimage.com/1200x630/",  # Service 3: DummyImage
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
        self.fallback_text = "Извините, произошла ошибка при генерации контента. Попробуем снова в следующий раз."
        
        # Временные слоты с объемами
        self.time_slots = {
            "09:00": {
                "type": "short", 
                "name": "Утренний пост", 
                "emoji": "🌅",
                "tg_words": "130-160 слов",
                "zen_words": "600-800 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },
            "14:00": {
                "type": "long", 
                "name": "Обеденный пост", 
                "emoji": "🌞",
                "tg_words": "150-180 слов",
                "zen_words": "800-1000 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },  
            "19:00": {
                "type": "medium", 
                "name": "Вечерний пост", 
                "emoji": "🌙",
                "tg_words": "140-170 слов",
                "zen_words": "700-900 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            }
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office", "teamwork", "business", "meeting", "workplace",
                "hr", "management", "corporate", "recruitment", "career"
            ],
            "PR и коммуникации": [
                "communication", "media", "social", "marketing", "public",
                "relations", "branding", "networking", "content", "strategy"
            ],
            "ремонт и строительство": [
                "construction", "renovation", "building", "repair", "tools",
                "architecture", "design", "home", "project", "workers"
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
        """Тестирует конкретную модель Gemini"""
        logger.info(f"Тестируем модель: {model_name}")
        
        # Проверяем, была ли модель успешной в прошлый раз
        if self.post_history.get("last_model") == model_name:
            logger.info(f"Модель {model_name} работала в прошлый раз, используем её")
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
        
        # Сначала пробуем модель из истории
        last_model = self.post_history.get("last_model")
        if last_model and last_model in GEMINI_MODELS:
            logger.info(f"Пробуем последнюю рабочую модель: {last_model}")
            working_model = self.test_gemini_model(last_model)
            if working_model:
                self.working_model = working_model
                logger.info(f"Выбрана модель: {self.working_model}")
                return True
        
        # Если не сработало, тестируем все модели
        for model in GEMINI_MODELS:
            if model == last_model:
                continue  # Уже тестировали
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
            
            # Сортируем по предпочтениям
            available_themes.sort(key=lambda x: preferred_themes.index(x) if x in preferred_themes else len(preferred_themes))
            
            # Избегаем повторения последних 2 тем
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes[:2]) if len(available_themes) > 1 else available_themes[0]
            
            # Обновляем историю
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
        """Определяет тип поста для ТГ based on current time"""
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
            logger.info(f"Тип поста: {post_type_info['type'].upper()}")
            logger.info(f"Объем ТГ: {post_type_info['tg_words']}")
            logger.info(f"Объем Дзен: {post_type_info['zen_words']}")
            
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

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram с правильными отступами"""
        try:
            if not text or not text.strip():
                return self.fallback_text
            
            lines = text.split('\n')
            formatted_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    formatted_lines.append('')
                    continue
                
                # Если строка начинается с маркера списка
                if line.startswith('•') or line.startswith('-') or line.startswith('⁃') or line.startswith('▪'):
                    clean_line = line.lstrip('•-⁃▪ ')
                    formatted_line = f" • {clean_line}"
                    formatted_lines.append(formatted_line)
                elif '•' in line and line.find('•') < 10:
                    parts = line.split('•', 1)
                    if len(parts) > 1:
                        formatted_line = f" • {parts[1].strip()}"
                        formatted_lines.append(formatted_line)
                    else:
                        formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
            
            result = '\n'.join(formatted_lines)
            return result if result.strip() else self.fallback_text
            
        except Exception as e:
            logger.error(f"Ошибка форматирования текста: {e}")
            return self.fallback_text

    def create_telegram_prompt(self, theme, time_slot_info):
        """Создает промпт для Telegram"""
        time_emoji = time_slot_info['emoji']
        tg_words = time_slot_info['tg_words']
        
        prompt = f"""Создай пост для Telegram на тему "{theme}" для 2024-2025 года.

Объем: {tg_words} (500–900 символов)
Используй эмодзи в разделах.

СТРУКТУРА:
{time_emoji} [Хук: 1-2 строки]
Цепляем вниманием, эмоцией или фактом.

📌 [Короткое объяснение: 2-3 строки]
Что важно / какой инсайт.

🎯 [Основной блок: 4-6 строк]
 • ключевая мысль
 • пример или кейс
 • практический совет

💡 [Вывод + CTA: 1-2 строки]
Вопрос для обсуждения.

🏷️ [3-5 хештегов]

Язык: русский, живой, вовлекающий.
Используй эмодзи, но умеренно.
Форматирование: каждый раздел с новой строки, между разделами пустая строка."""

        return prompt

    def create_zen_prompt(self, theme, time_slot_info):
        """Создает промпт для Яндекс.Дзена"""
        zen_words = time_slot_info['zen_words']
        
        prompt = f"""Напиши развернутый пост для Яндекс.Дзен на тему "{theme}" для 2024-2025 года.

Объем: {zen_words} (3000-5000 символов)
Без эмодзи и хештегов.

СТРУКТУРА:
1. Хук (1 абзац)
Сильное начало, факт или вопрос.

2. Введение (1-2 абзаца)
О чем статья, почему важно.

3. Основная часть (3-4 раздела)
Каждый раздел с подзаголовком.
Примеры, кейсы, данные.

4. Практическая часть (1 раздел)
Что делать, конкретные шаги.

5. Заключение (1 абзац)
Итог, выводы.

Требования:
- Русский язык, профессиональный но доступный
- Конкретные примеры и данные
- Абзацы по 3-5 строк
- Глубокий анализ с пользой для читателя"""

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
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.9,
                        "maxOutputTokens": 2048,
                    }
                }
                
                response = session.post(url, json=data, timeout=45)
                
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
                return self.format_telegram_text(raw_text)
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
                return self.format_telegram_text(raw_text)
            return self.fallback_text
        except Exception as e:
            logger.error(f"Ошибка генерации Дзен поста: {e}")
            return self.fallback_text

    def get_image_url(self, theme):
        """Получает изображение для темы (улучшенная версия)"""
        logger.info(f"Получаем изображение для: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Пробуем разные сервисы по очереди
            for service_index, service_url in enumerate(IMAGE_SERVICES):
                try:
                    if service_index == 0:  # Picsum
                        image_url = f"{service_url}?random={random.randint(1, 1000)}"
                    elif service_index == 1:  # Unsplash
                        encoded_keyword = quote_plus(keyword)
                        image_url = f"{service_url}?{encoded_keyword}&sig={random.randint(1, 1000)}"
                    else:  # DummyImage
                        colors = ["4A90E2", "2E8B57", "FF6B35", "6A5ACD", "20B2AA", "8B4513", "2F4F4F"]
                        color = random.choice(colors)
                        encoded_keyword = quote_plus(keyword)
                        image_url = f"{service_url}{color}/fff&text={encoded_keyword}"
                    
                    # Быстрая проверка доступности
                    test_response = session.head(image_url, timeout=5)
                    if test_response.status_code == 200:
                        logger.info(f"Изображение найдено: {service_url[:30]}...")
                        return image_url
                        
                except Exception as e:
                    logger.debug(f"Сервис {service_index} не доступен: {e}")
                    continue
            
            # Если все сервисы недоступны, возвращаем простую ссылку
            logger.warning("Все сервисы изображений недоступны, используем заглушку")
            return "https://picsum.photos/1200/630"
            
        except Exception as e:
            logger.error(f"Ошибка получения изображения: {e}")
            return "https://picsum.photos/1200/630"

    def download_image(self, url):
        """Скачивает изображение для отправки с резервными вариантами"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                response = session.get(url, timeout=15)
                if response.status_code == 200 and len(response.content) > 1024:  # Минимум 1KB
                    return response.content
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} скачивания изображения: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        logger.error("Не удалось скачать изображение")
        return None

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram (исправленная версия)"""
        logger.info(f"Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            logger.error("Отсутствует BOT_TOKEN")
            return False
        
        # Обрезаем текст если слишком длинный для фото
        max_length = 1024
        
        if len(text) > max_length:
            logger.warning(f"Текст длинный ({len(text)}), обрезаем до {max_length}...")
            # Ищем место для обрезки
            cutoff = text[:max_length-100].rfind('.')
            if cutoff > max_length * 0.6:
                text = text[:cutoff+1]
            else:
                text = text[:max_length-3] + "..."
        
        try:
            # Пытаемся отправить с изображением
            if image_url:
                logger.info("Пробуем отправить с изображением...")
                
                # Скачиваем изображение
                image_data = self.download_image(image_url)
                
                if image_data:
                    # Отправляем фото с подписью
                    files = {'photo': ('image.jpg', image_data, 'image/jpeg')}
                    data = {
                        'chat_id': chat_id,
                        'caption': text,
                        # parse_mode должен быть строкой или не указываться вообще
                    }
                    
                    response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data=data,
                        files=files,
                        timeout=30
                    )
                else:
                    # Если не скачали, пробуем отправить по URL
                    logger.info("Пробуем отправить изображение по URL...")
                    response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        json={
                            'chat_id': chat_id,
                            'photo': image_url,
                            'caption': text
                            # Не указываем parse_mode
                        },
                        timeout=30
                    )
                
                if response.status_code == 200:
                    logger.info(f"Пост с фото отправлен в {chat_id}")
                    return True
                else:
                    logger.warning(f"Ошибка отправки фото ({response.status_code}): {response.text[:200]}")
            
            # Если не удалось с фото, пробуем без него
            logger.info("Пробуем отправить текстовый пост...")
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    # Не указываем parse_mode
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Текстовый пост отправлен в {chat_id}")
                return True
            else:
                logger.error(f"Ошибка отправки текста ({response.status_code}): {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            return False

    def send_dual_posts(self):
        """Основной метод отправки постов"""
        try:
            if not self.check_last_post_time():
                logger.info("Пропускаем отправку - недавно уже был пост")
                return True
                
            if not self.find_working_model():
                logger.error("Не удалось найти рабочую модель Gemini")
                return False
            
            # Выбираем тему
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            tg_type, time_slot, time_emoji, time_slot_info = self.get_tg_type_by_time()
            
            logger.info(f"Тема: {self.current_theme}")
            logger.info(f"Тип поста: {tg_type.upper()}")
            
            # Генерируем посты
            logger.info("Генерация Telegram поста...")
            tg_post = self.generate_tg_post(self.current_theme, time_slot_info)
            
            logger.info("Генерация Дзен поста...")
            zen_post = self.generate_zen_post(self.current_theme, time_slot_info)
            
            logger.info(f"Статистика постов:")
            logger.info(f"  ТГ-пост: {len(tg_post)} символов")
            logger.info(f"  Дзен-пост: {len(zen_post)} символов")
            
            # Получаем изображения (разные для каждого поста)
            logger.info("Получаем изображения...")
            tg_image_url = self.get_image_url(self.current_theme)
            time.sleep(1)  # Пауза между запросами
            zen_image_url = self.get_image_url(self.current_theme)
            
            # Отправляем посты
            logger.info("Отправляем посты...")
            
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, tg_image_url)
            time.sleep(2)  # Пауза между отправками
            
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, zen_image_url)
            
            if tg_success or zen_success:
                if tg_success and zen_success:
                    logger.info("ОБА поста успешно отправлены!")
                elif tg_success:
                    logger.info("Только Telegram пост отправлен")
                else:
                    logger.info("Только Дзен пост отправлен")
                
                self.update_last_post_time()
                return True
            else:
                logger.error("Не удалось отправить ни один пост")
                return False
                
        except Exception as e:
            logger.error(f"Критическая ошибка в основном процессе: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Автоматический подбор рабочей модели Gemini")
    print("🎯 Умный подбор тем по времени суток")
    print("🎯 Контроль частоты постов")
    print("🎯 1 фото в каждом посте")
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
            print("\n✅ УСПЕХ! AI посты отправлены или пропущены по расписанию!")
        else:
            print("\n⚠️  ПРЕДУПРЕЖДЕНИЕ: Не все посты удалось отправить")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
