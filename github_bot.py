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

# Улучшенный список сервисов с реальными изображениями
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
    },
    {
        "name": "Lorem Picsum",
        "url": "https://picsum.photos/1200/630?random=",
        "quality": "medium"
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
        self.fallback_text = "Извините, произошла ошибка при генерации контента. Попробуем снова в следующий раз."
        
        # Временные слоты с объемами (Яндекс.Дзен - полный объем)
        self.time_slots = {
            "09:00": {
                "type": "short", 
                "name": "Утренний пост", 
                "emoji": "🌅",
                "tg_words": "130-160 слов",
                "zen_words": "600-800 слов",  # Полный объем
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },
            "14:00": {
                "type": "long", 
                "name": "Обеденный пост", 
                "emoji": "🌞",
                "tg_words": "150-180 слов",
                "zen_words": "800-1000 слов",  # Полный объем
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },  
            "19:00": {
                "type": "medium", 
                "name": "Вечерний пост", 
                "emoji": "🌙",
                "tg_words": "140-170 слов",
                "zen_words": "700-900 слов",  # Полный объем
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            }
        }

        # Ключевые слова для поиска реальных изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office,team,meeting,business,workplace,professional",
                "hr,human resources,recruitment,interview,career",
                "corporate,management,leadership,employees,staff",
                "work,success,teamwork,collaboration,communication"
            ],
            "PR и коммуникации": [
                "public relations,media,communication,social media",
                "marketing,branding,advertising,networking",
                "press,conference,event,digital marketing",
                "influencer,content,strategy,campaign"
            ],
            "ремонт и строительство": [
                "construction,building,renovation,repair,home",
                "tools,workers,architecture,design,house",
                "interior,remodeling,contractor,project",
                "diy,handyman,construction site,blueprint"
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

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram: убирает символы * и # в начале"""
        if not text or not text.strip():
            return self.fallback_text
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Убираем # в начале строки
            if line.strip().startswith('#'):
                line = line.replace('#', '', 1).strip()
            
            # Убираем * из текста
            line = line.replace('*', '')
            
            # Форматирование списков
            if line.strip().startswith(('•', '-', '⁃', '▪')):
                clean_line = line.lstrip('•-⁃▪ ')
                formatted_line = f" • {clean_line}"
                cleaned_lines.append(formatted_line)
            elif '•' in line and line.find('•') < 10:
                parts = line.split('•', 1)
                if len(parts) > 1:
                    formatted_line = f" • {parts[1].strip()}"
                    cleaned_lines.append(formatted_line)
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        return result if result.strip() else self.fallback_text

    def clean_zen_text(self, text, theme):
        """Форматирует текст для Яндекс.Дзен в правильном формате"""
        if not text or not text.strip():
            return self.fallback_text
        
        # Убираем все символы *, #, **
        text = text.replace('*', '').replace('#', '')
        
        # Заменяем маркеры списков на • (точки в середине строки)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Убираем **
            line = line.replace('**', '')
            
            # Заменяем - на • в начале строки для списков
            if line.strip().startswith('-'):
                # Убираем - и добавляем • с пробелом
                clean_line = line.lstrip('- ')
                formatted_line = f"• {clean_line}"
                cleaned_lines.append(formatted_line)
            elif line.strip().startswith('—'):
                # Убираем — и добавляем • с пробелом
                clean_line = line.lstrip('— ')
                formatted_line = f"• {clean_line}"
                cleaned_lines.append(formatted_line)
            elif line.strip().startswith('•'):
                # Уже правильный формат, оставляем как есть
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Получаем текущую дату для формата "X дней назад"
        days_ago = random.randint(1, 7)
        
        # Форматируем заголовок и подзаголовок БЕЗ #
        formatted_text = f"{theme}\n\n"
        formatted_text += f"{days_ago} дней назад\n\n"
        formatted_text += f"{theme}\n\n"
        
        # Разделяем на абзацы
        paragraphs = [p.strip() for p in cleaned_text.split('\n\n') if p.strip()]
        
        # Собираем основной текст до "Ключевые направления"
        main_content = ""
        
        # Находим где начинается "Ключевые направления"
        key_directions_index = -1
        for i, para in enumerate(paragraphs):
            if "Ключевые направления:" in para or "ключевые направления:" in para.lower():
                key_directions_index = i
                break
        
        if key_directions_index == -1:
            # Если не нашли, ищем блок с пунктами • в начале
            for i, para in enumerate(paragraphs):
                if para.strip().startswith('•') or ('\n•' in para):
                    key_directions_index = i
                    break
        
        if key_directions_index > 0:
            # Берем параграфы до "Ключевые направления"
            for i in range(key_directions_index):
                main_content += f"{paragraphs[i]}\n\n"
        else:
            # Берем первые 2-3 абзаца
            for i, para in enumerate(paragraphs):
                if i < 3:  # Ограничиваем 3 абзацами для начала
                    main_content += f"{para}\n\n"
        
        formatted_text += main_content
        
        # Добавляем разделитель (просто пустая строка, а не ---)
        formatted_text += "\n"
        
        # Добавляем нижнее меню БЕЗ **
        formatted_text += "Главная Видео Статьи Новости Подписки"
        
        return formatted_text

    def create_telegram_prompt(self, theme, time_slot_info):
        """Создает промпт для Telegram"""
        time_emoji = time_slot_info['emoji']
        tg_words = time_slot_info['tg_words']
        
        prompt = f"""Создай пост для Telegram на тему "{theme}" для 2024-2025 года.

Объем: {tg_words} (500–900 символов)
Используй эмодзи в разделах.
НЕ используй символы * в тексте.

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
        """Создает промпт для Яндекс.Дзен в правильном формате"""
        zen_words = time_slot_info['zen_words']
        
        prompt = f"""Создай полноценный пост для Яндекс.Дзен на тему "{theme}" для 2024-2025 года.

Объем: {zen_words} (3000-5000 символов)
Формат начала: как в примере ниже.

ВАЖНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:
1. НЕ используй символ # в начале
2. НЕ используй символы * и ** вообще в тексте
3. Для списков используй символ • (точка в середине строки), НЕ используй -
4. Разделитель - просто пустая строка, НЕ используй ---

ПРИМЕР ПРАВИЛЬНОГО ФОРМАТА:
Трансформация PR-коммуникаций

6 дней назад

Трансформация PR-коммуникаций

45% используют искусственный интеллект, аудитория доверяет микроинфлюенсерам.

Ключевые направления:

• Простота и ясность. Говорите на языке аудитории.
• Прозрачность и аутентичность. Демонстрация закулисы создает доверие.
• Формирование сообщества. Ответы на комментарии создают активное сообщество.


Главная Видео Статьи Новости Подписки

ТЕПЕРЬ СОЗДАЙ ПОЛНЫЙ ПОСТ:

Тема: "{theme}"

СТРУКТУРА НАЧАЛА (ПЕРВЫЕ 10-15 СТРОК):
1. Название темы (БЕЗ символа #)
2. Пустая строка
3. "X дней назад" (случайное число 1-7)
4. Пустая строка
5. Название темы еще раз
6. Пустая строка
7. 1-2 абзаца с ключевой статистикой, фактами, инсайтами
8. Пустая строка
9. "Ключевые направления:" (именно так)
10. Пустая строка
11. 3-5 пунктов с маркером • (точка в середине строки)
12. Пустая строка (разделитель)
13. "Главная Видео Статьи Новости Подписки" (БЕЗ символов **)
14. Пустая строка
15. ПУНКТ 15 И ДАЛЕЕ - ЭТО ПОЛНАЯ СТАТЬЯ!

ДАЛЕЕ НАПИШИ ПОЛНОЦЕННУЮ СТАТЬЮ:
- Подробное раскрытие темы
- Примеры, кейсы, данные исследований
- Анализ трендов
- Практические рекомендации
- Прогнозы на будущее
- Заключение

ТРЕБОВАНИЯ:
- Общий объем: {zen_words} (полноценная статья)
- НИКАКИХ символов *, #, ** в тексте
- Для списков используй только • (не -, не —)
- Разделитель - просто пустая строка
- Нижнее меню БЕЗ **
- Используй реальную статистику, исследования, данные
- Глубокий анализ, полезная информация
- Профессиональный, но доступный язык"""

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
                        "maxOutputTokens": 4096,
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
                return self.clean_telegram_text(raw_text)
            return self.fallback_text
        except Exception as e:
            logger.error(f"Ошибка генерации ТГ поста: {e}")
            return self.fallback_text

    def generate_zen_post(self, theme, time_slot_info):
        """Генерирует пост для Дзена в правильном формате"""
        try:
            prompt = self.create_zen_prompt(theme, time_slot_info)
            raw_text = self.generate_with_gemini(prompt)
            if raw_text:
                # Форматируем текст в стиле Яндекс.Дзен
                return self.clean_zen_text(raw_text, theme)
            return self.fallback_text
        except Exception as e:
            logger.error(f"Ошибка генерации Дзен поста: {e}")
            return self.fallback_text

    def get_real_image_url(self, theme):
        """Получает URL реального изображения с различных сервисов"""
        logger.info(f"Поиск реального изображения для: {theme}")
        
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keywords = random.choice(keywords_list).split(',')
            primary_keyword = keywords[0].strip()
            
            # Пробуем разные сервисы в случайном порядке
            services = random.sample(REAL_IMAGE_SERVICES, len(REAL_IMAGE_SERVICES))
            
            for service in services:
                try:
                    if service["name"] == "Unsplash":
                        # Unsplash - качественные фото
                        encoded_keywords = quote_plus(primary_keyword)
                        url = f"{service['url']}{encoded_keywords}&sig={random.randint(1, 10000)}"
                        
                    elif service["name"] == "Pexels":
                        # Pexels - случайное фото по ключевому слову
                        pexels_id = random.randint(1, 1000000)
                        url = f"{service['url']}{pexels_id}/pexels-photo-{pexels_id}.jpeg?auto=compress&cs=tinysrgb&w=1200&h=630&fit=crop"
                        
                    elif service["name"] == "Pixabay":
                        # Pixabay - через их API (упрощенно)
                        url = f"https://pixabay.com/get/g{random.randint(1000000000, 9999999999)}.jpg"
                        
                    else:  # Lorem Picsum
                        # Lorem Picsum - случайные фото
                        url = f"{service['url']}{random.randint(1, 1000)}"
                    
                    # Быстрая проверка доступности
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
            
            # Если все сервисы недоступны, используем Unsplash как fallback
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
                    if len(content) > 10240:  # Минимум 10KB для реального изображения
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
        """Отправляет пост в Telegram"""
        logger.info(f"Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            logger.error("Отсутствует BOT_TOKEN")
            return False
        
        # Обрезаем текст если слишком длинный для фото
        max_length = 1024
        
        if len(text) > max_length:
            logger.warning(f"Текст длинный ({len(text)}), обрезаем до {max_length}...")
            cutoff = text[:max_length-100].rfind('.')
            if cutoff > max_length * 0.6:
                text = text[:cutoff+1]
            else:
                text = text[:max_length-3] + "..."
        
        try:
            # Всегда пытаемся отправить с изображением
            if image_url:
                logger.info("Отправка поста с изображением...")
                
                # Скачиваем изображение
                image_data = self.download_image(image_url)
                
                if image_data:
                    # Отправляем фото с подписью
                    files = {'photo': ('image.jpg', image_data, 'image/jpeg')}
                    data = {
                        'chat_id': chat_id,
                        'caption': text,
                        'parse_mode': ''  # Отключаем форматирование
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
                            'caption': text,
                            'parse_mode': ''
                        },
                        timeout=30
                    )
                
                if response.status_code == 200:
                    logger.info(f"✅ Пост с фото отправлен в {chat_id}")
                    return True
                else:
                    logger.warning(f"Ошибка отправки фото ({response.status_code}): {response.text[:200]}")
            
            # Если не удалось с фото, отправляем текстовый пост
            logger.info("Пробуем отправить текстовый пост...")
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': ''  # Отключаем форматирование
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
        """Основной метод отправки постов"""
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
            logger.info(f"📊 Тип поста: {tg_type.upper()}")
            
            # Генерируем посты
            logger.info("🧠 Генерация Telegram поста...")
            tg_post = self.generate_tg_post(self.current_theme, time_slot_info)
            
            logger.info("🧠 Генерация Дзен поста...")
            zen_post = self.generate_zen_post(self.current_theme, time_slot_info)
            
            logger.info(f"📈 Статистика постов:")
            logger.info(f"  📱 ТГ-пост: {len(tg_post)} символов")
            logger.info(f"  📄 Дзен-пост: {len(zen_post)} символов")
            
            # Получаем реальные изображения
            logger.info("🖼️ Поиск реальных изображений...")
            tg_image_url = self.get_real_image_url(self.current_theme)
            time.sleep(2)  # Пауза между запросами
            zen_image_url = self.get_real_image_url(self.current_theme)
            
            logger.info(f"📸 Изображения получены:")
            logger.info(f"  ТГ: {tg_image_url[:80]}...")
            logger.info(f"  Дзен: {zen_image_url[:80]}...")
            
            # Отправляем посты
            logger.info("📤 Отправляем посты...")
            
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, tg_image_url)
            time.sleep(3)  # Пауза между отправками
            
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
            logger.error(f"💥 Критическая ошибка в основном процессе: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Автоматический подбор рабочей модели Gemini")
    print("🎯 Умный подбор тем по времени суток")
    print("🎯 Контроль частоты постов")
    print("🎯 РЕАЛЬНЫЕ фото из интернета в каждом посте")
    print("🎯 Яндекс.Дзен: правильный формат (без #, *, **, -)")
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
            print("\n✅ УСПЕХ! AI посты с реальными фото отправлены или пропущены по расписанию!")
        else:
            print("\n⚠️  ПРЕДУПРЕЖДЕНИЕ: Не все посты удалось отправить")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
