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

# Настройка сессии requests
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=10, pool_maxsize=10)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Список моделей
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

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
        self.fallback_text = "Извините, произошла ошибка при генерации контента."
        
        # Временные слоты - ПРАВИЛЬНЫЕ объемы (Дзен БОЛЬШЕ чем ТГ)
        self.time_slots = {
            "09:00": {
                "type": "short", 
                "name": "Утренний пост", 
                "emoji": "🌅",
                "tg_words": "100-130 слов",     # Telegram - КОРОТКИЙ
                "zen_words": "300-400 слов",    # Дзен - ДЛИННЫЙ
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },
            "14:00": {
                "type": "long", 
                "name": "Обеденный пост", 
                "emoji": "🌞",
                "tg_words": "120-150 слов",     # Telegram - СРЕДНИЙ
                "zen_words": "400-500 слов",    # Дзен - ОЧЕНЬ ДЛИННЫЙ
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },  
            "19:00": {
                "type": "medium", 
                "name": "Вечерний пост", 
                "emoji": "🌙",
                "tg_words": "110-140 слов",     # Telegram - КОРОТКИЙ
                "zen_words": "350-450 слов",    # Дзен - ДЛИННЫЙ
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            }
        }

        # Улучшенные ключевые слова для изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "business office team meeting", 
                "human resources recruitment", 
                "corporate teamwork success",
                "workplace collaboration professionals"
            ],
            "PR и коммуникации": [
                "public relations media conference",
                "social media marketing digital",
                "communication networking event",
                "press branding advertising"
            ],
            "ремонт и строительство": [
                "construction building renovation",
                "tools architecture design",
                "home interior repair",
                "workers contractor project"
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
        """Выбирает тему"""
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

    def create_telegram_prompt(self, theme, time_slot_info):
        """Промпт для Telegram - КОРОТКИЙ"""
        tg_words = time_slot_info['tg_words']
        
        prompt = f"""Напиши КОРОТКИЙ пост для Telegram на тему: "{theme}"

Требования:
- Объем: {tg_words} (КОРОТКО!)
- Год: 2025-2026
- Используй отступы и символ • для списков
- Добавь вопрос для обсуждения
- Добавь 3-5 хештегов
- НИКАКИХ *, #, ** в тексте

Пример формата:
[Короткий вопрос или факт]

[Основная мысль]

  • Пункт 1 с отступом
  • Пункт 2 с отступом

[Вопрос для обсуждения]

#Хештег1 #Хештег2

Тема: {theme}"""

        return prompt

    def create_zen_prompt(self, theme, time_slot_info):
        """Промпт для Дзена - ДЛИННЫЙ"""
        zen_words = time_slot_info['zen_words']
        
        prompt = f"""Напиши РАЗВЕРНУТЫЙ пост для Яндекс.Дзен на тему: "{theme}"

Требования:
- Объем: {zen_words} (ПОЛНОЦЕННАЯ статья!)
- Год: 2025-2026
- Используй отступы и символ • для списков
- Добавь факты, статистику, данные
- Сделай пост полезным и информативным
- НИКАКИХ *, #, ** в тексте

Пример структуры:
[Введение с важностью темы]

[Основной анализ]

  • Направление 1: детали
  • Направление 2: детали

[Практические рекомендации]

[Заключение]

Тема: {theme}"""

        return prompt

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерирует текст"""
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

    def get_image_for_theme(self, theme):
        """Получает реальное изображение для темы"""
        logger.info(f"Поиск изображения для: {theme}")
        
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keywords = random.choice(keywords_list)
            
            # Используем Unsplash - самый надежный
            encoded_keywords = quote_plus(keywords)
            url = f"https://source.unsplash.com/featured/1200x630/?{encoded_keywords}"
            
            logger.info(f"Пробуем URL: {url}")
            
            # Проверяем доступность
            response = session.head(url, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                final_url = response.url
                logger.info(f"✅ Изображение найдено: {final_url[:80]}...")
                return final_url
            
            # Fallback
            logger.warning("Unsplash не ответил, используем fallback")
            return f"https://source.unsplash.com/featured/1200x630/?{encoded_keywords}"
            
        except Exception as e:
            logger.error(f"Ошибка поиска изображения: {e}")
            return "https://source.unsplash.com/featured/1200x630/?business"

    def download_image(self, url):
        """Скачивает изображение"""
        try:
            logger.info(f"Скачивание изображения: {url[:80]}...")
            response = session.get(url, timeout=15)
            
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
            logger.error(f"Ошибка скачивания: {e}")
        
        return None

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram С ФОТО"""
        logger.info(f"Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            logger.error("Отсутствует BOT_TOKEN")
            return False
        
        # Обрезаем текст
        max_length = 1024
        if len(text) > max_length:
            logger.warning(f"Текст длинный ({len(text)}), обрезаем...")
            text = text[:max_length-3] + "..."
        
        try:
            # ВСЕГДА отправляем с фото
            logger.info(f"Отправка с изображением: {image_url[:80]}...")
            
            # Конвертируем отступы для HTML
            html_text = text.replace('\n', '<br>').replace('  ', '&emsp;&emsp;')
            
            # Сначала пробуем по URL
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
                logger.warning(f"Ошибка по URL ({response.status_code}), пробуем скачать...")
                
                # Скачиваем и отправляем
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
                        logger.info(f"✅ Пост с фото (скачанным) отправлен")
                        return True
            
            # Fallback: текстовый пост
            logger.info("Пробуем текстовый пост...")
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': html_text,
                    'parse_mode': 'HTML'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текстовый пост отправлен")
                return True
            else:
                logger.error(f"❌ Ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            logger.info("Проверка времени последнего поста...")
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                if hours_since_last < 4:
                    logger.info(f"⏭️ Пропускаем - прошло всего {hours_since_last:.1f} часов")
                    return True
            
            if not self.find_working_model():
                logger.error("❌ Нет рабочей модели Gemini")
                return False
            
            # Выбираем тему
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            # Определяем время
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            # Выбираем слот
            slots = list(self.time_slots.keys())
            time_objects = [datetime.strptime(slot, "%H:%M").replace(year=now.year, month=now.month, day=now.day) 
                          for slot in slots]
            
            closest_slot = min(time_objects, key=lambda x: abs((now - x).total_seconds()))
            slot_name = closest_slot.strftime("%H:%M")
            time_slot_info = self.time_slots.get(slot_name, self.time_slots["14:00"])
            
            logger.info(f"🕒 Время: {current_time_str}, Слот: {slot_name}")
            logger.info(f"📏 Telegram: {time_slot_info['tg_words']}")
            logger.info(f"📏 Яндекс.Дзен: {time_slot_info['zen_words']}")
            
            # Генерируем посты
            logger.info("🧠 Генерация Telegram поста...")
            tg_prompt = self.create_telegram_prompt(self.current_theme, time_slot_info)
            tg_text = self.generate_with_gemini(tg_prompt)
            
            logger.info("🧠 Генерация Дзен поста...")
            zen_prompt = self.create_zen_prompt(self.current_theme, time_slot_info)
            zen_text = self.generate_with_gemini(zen_prompt)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            # Форматируем Дзен пост
            zen_post = f"{self.current_theme}\n\n{zen_text}\n\nГлавная Видео Статьи Новости Подписки"
            
            logger.info(f"📊 Статистика:")
            logger.info(f"  Telegram: {len(tg_text)} символов")
            logger.info(f"  Яндекс.Дзен: {len(zen_post)} символов")
            
            # Получаем изображения (РАЗНЫЕ для каждого канала)
            logger.info("🖼️ Поиск изображений...")
            
            tg_image = self.get_image_for_theme(self.current_theme)
            time.sleep(2)
            zen_image = self.get_image_for_theme(self.current_theme)
            
            logger.info(f"📸 Telegram фото: {tg_image[:80]}...")
            logger.info(f"📸 Яндекс.Дзен фото: {zen_image[:80]}...")
            
            # Отправляем посты С ФОТО
            logger.info("📤 Отправка Telegram...")
            tg_success = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, tg_image)
            
            time.sleep(3)
            
            logger.info("📤 Отправка Яндекс.Дзен...")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_post, zen_image)
            
            if tg_success or zen_success:
                if tg_success and zen_success:
                    logger.info("✅ ОБА поста отправлены с фото!")
                elif tg_success:
                    logger.info("✅ Только Telegram отправлен")
                else:
                    logger.info("✅ Только Яндекс.Дзен отправлен")
                
                # Обновляем время
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                return True
            else:
                logger.error("❌ Не удалось отправить посты")
                return False
                
        except Exception as e:
            logger.error(f"💥 Ошибка: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Telegram: КОРОТКО (100-150 слов)")
    print("🎯 Яндекс.Дзен: ДЛИННО (300-500 слов)")
    print("🎯 ОБЯЗАТЕЛЬНО фото в каждом посте!")
    print("🎯 Отступы и буллеты •")
    print("🎯 Год 2025-2026")
    print("=" * 80)
    
    if not BOT_TOKEN or not GEMINI_API_KEY:
        print("❌ ОШИБКА: Проверьте переменные окружения!")
        return
    
    bot = AIPostGenerator()
    
    try:
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n✅ УСПЕХ! Посты с фото отправлены!")
        else:
            print("\n⚠️  Не удалось отправить посты")
            
    except Exception as e:
        print(f"\n💥 ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
