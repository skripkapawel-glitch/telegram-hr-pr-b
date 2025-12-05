import os
import requests
import random
import json
import time
import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlencode

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

# Настройка сессии requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
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
        
        # Временные слоты с объемами
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

        # Ключевые слова для изображений (исправлено!)
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting business",
                "human resources recruitment",
                "workplace collaboration",
                "leadership management"
            ],
            "PR и коммуникации": [
                "public relations media",
                "social media marketing",
                "communication networking",
                "branding advertising"
            ],
            "ремонт и строительство": [
                "construction building",
                "tools architecture",
                "home renovation",
                "contractor workers"
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
                "used_images": {},
                "last_post_time": None,
                "last_model": None
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
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
   • С отступом и символом • перечисли 2-4 коротких тезиса
   • Минимальный объем воды
   • Финал — простой вопрос, провоцирующий комментарии
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML теги или markdown
6. Используй обычные пробелы и символ •
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Пример структуры:
[Мощный хук]

[Основная мысль]

• Пункт 1 с отступом
• Пункт 2 с отступом

[Вопрос для обсуждения]

#хештег1 #хештег2

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши пост для Telegram на тему: {theme}

Объем: {chars_range} знаков
Стиль — аналитика + живой язык

Требования:
1. Добавь мощный хук, который создаёт интригу
2. Структура:
   • Отступ и символ • для каждого пункта
   • Раскрой тему глубже, чем в утреннем посте
   • Добавь mini-story или кейс
   • Сделай вывод
   • Задай провокационный вопрос, вызывающий дискуссию
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычные пробелы и символ •
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
   • Через пробел и символ • перечисли 2-3 мысли
   • Добавь короткое наблюдение или личный инсайт
   • Вызови эмоцию
   • В конце — простой CTA: "Как вы думаете?"
3. Добавь 3-5 релевантных хештегов в конце
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычные пробелы и символ •
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
   • Оформи ключевые тезисы с пробелом и символом •
   • Подай тему легко, без перегруза
   • В тексте — микросюжет или пример
   • Финал — вопрос для комментариев
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычные пробелы и символ •
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука
8. Формат Дзен — структурированный, абзацы короткие

Тема: {theme}"""

        elif slot_type == "day":
            return f"""Напиши длинный пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков

Требования:
1. Добавь сильный хук, интригу или сюжет
2. Структура:
   • Сделай разбор темы
   • Оформи пункты с пробелом и символом •
   • Вставь мини-кейс / историю / данные
   • Сделай полезный вывод
   • Финал с CTA для обсуждения
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычные пробелы и символ •
7. Не указывай "Тема:" или "Заголовок:", просто начни с хука

Тема: {theme}"""

        else:  # evening
            return f"""Напиши пост для Яндекс.Дзен на тему: {theme}

Объем: {chars_range} знаков
Стиль — лёгкий вечерний

Требования:
1. Хук должен цеплять эмоцией или неожиданным фактом
2. Структура:
   • 2-4 пункта через пробел и символ •
   • Короткая мысль, инсайт
   • Вывод
   • Финальный вопрос
3. В конце добавь подпись: "Главная Видео Статьи Новости Подписки"
4. Год: 2025-2026
5. Не используй HTML или markdown
6. Используй обычные пробелы и символ •
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

    def get_image_for_theme(self, theme):
        """Получает изображение для темы"""
        logger.info(f"🔍 Поиск изображения для темы: {theme}")
        
        try:
            keywords_list = self.theme_keywords.get(theme, ["business"])
            keywords = random.choice(keywords_list)
            
            # ИСПРАВЛЕНО: правильное кодирование для Unsplash
            # Unsplash принимает запятые как разделители, не нужно сложного кодирования
            keywords_clean = keywords.replace(' ', ',')
            
            # Формируем URL правильно
            unsplash_url = f"https://source.unsplash.com/1200x630/?{keywords_clean}"
            
            # Добавляем случайный параметр чтобы избежать кэширования
            timestamp = int(time.time())
            unsplash_url = f"{unsplash_url}&t={timestamp}"
            
            logger.info(f"🖼️ Запрос изображения: {unsplash_url}")
            
            try:
                # Пробуем получить изображение с таймаутом
                response = session.get(unsplash_url, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    # Проверяем что это действительно изображение
                    if 'image' in response.headers.get('content-type', ''):
                        final_url = response.url
                        logger.info(f"✅ Изображение найдено: {final_url[:80]}...")
                        return final_url
                    else:
                        logger.warning("Ответ не является изображением")
                else:
                    logger.warning(f"Не удалось получить изображение, статус: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Ошибка при получении изображения: {e}")
            
            # Fallback на общую картинку
            fallback_url = f"https://source.unsplash.com/1200x630/?{theme.split()[0]}&t={timestamp}"
            logger.info(f"🔄 Используем fallback изображение: {fallback_url}")
            return fallback_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска изображения: {e}")
            # Самый простой fallback
            return "https://source.unsplash.com/1200x630/?business"

    def clean_text_for_telegram(self, text, is_caption=False):
        """Очищает текст для Telegram"""
        # Удаляем HTML/XML теги
        import re
        
        # Удаляем возможные теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы на обычные
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&emsp;', '    ')
        text = text.replace(' ', '    ')  # em space
        text = text.replace(' ', '  ')   # en space
        
        # Удаляем возможные указания темы
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            if not line.strip().startswith(('Тема:', 'Заголовок:', 'Тематика:', '#')):
                clean_lines.append(line.strip())
        
        text = '\n'.join(clean_lines)
        
        # Обрезаем если слишком длинный
        max_len = 1024 if is_caption else 4096
        if len(text) > max_len:
            # Ищем хорошее место для обрезки
            cutoff = text[:max_len-100].rfind('\n')
            if cutoff > max_len - 300:  # Если нашли разумное место
                text = text[:cutoff] + "\n\n..."
            else:
                text = text[:max_len-50] + "..."
        
        return text.strip()

    def send_telegram_post(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        logger.info(f"📤 Отправка в {chat_id}...")
        
        try:
            # Очищаем текст
            clean_text = self.clean_text_for_telegram(text, is_caption=(image_url is not None))
            
            # Добавляем тему для Дзена если нужно
            if chat_id == ZEN_CHANNEL_ID and self.current_theme:
                if not any(theme in clean_text[:100] for theme in self.themes):
                    clean_text = f"{self.current_theme}\n\n{clean_text}"
            
            # Вариант 1: Отправка с фото (если есть)
            if image_url:
                logger.info(f"🖼️ Пробуем отправить с фото: {image_url[:80]}...")
                
                # Попытка 1: Отправка напрямую по URL
                try:
                    payload = {
                        'chat_id': chat_id,
                        'photo': image_url,
                        'caption': clean_text,
                        'parse_mode': None  # Важно: без HTML!
                    }
                    
                    response = session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Фото отправлено в {chat_id}")
                        return True
                    else:
                        error_data = response.json() if response.content else {}
                        logger.warning(f"Ошибка отправки фото (URL): {response.status_code} - {error_data.get('description', 'Bad Request')}")
                        
                except Exception as e:
                    logger.warning(f"Ошибка при отправке фото по URL: {e}")
                
                # Попытка 2: Скачать и отправить как файл
                time.sleep(1)
                try:
                    logger.info("🔄 Пробуем скачать и отправить файл...")
                    
                    # Скачиваем изображение
                    img_response = session.get(image_url, timeout=15)
                    if img_response.status_code == 200:
                        # Проверяем размер файла
                        if len(img_response.content) < 10240:  # Меньше 10KB
                            logger.warning("Изображение слишком маленькое")
                            raise Exception("Small image")
                        
                        # Сохраняем временно
                        with open('temp_image.jpg', 'wb') as f:
                            f.write(img_response.content)
                        
                        # Отправляем как файл
                        with open('temp_image.jpg', 'rb') as photo_file:
                            files = {'photo': photo_file}
                            data = {
                                'chat_id': chat_id,
                                'caption': clean_text
                            }
                            
                            response = session.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                                data=data,
                                files=files,
                                timeout=30
                            )
                        
                        # Удаляем временный файл
                        try:
                            os.remove('temp_image.jpg')
                        except:
                            pass
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Фото (скачанное) отправлено в {chat_id}")
                            return True
                        else:
                            error_data = response.json() if response.content else {}
                            logger.warning(f"Ошибка отправки скачанного фото: {response.status_code}")
                    else:
                        logger.warning(f"Не удалось скачать изображение: {img_response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"Ошибка скачивания/отправки файла: {e}")
            
            # Fallback: текстовый пост
            logger.info("📝 Переход к текстовому посту...")
            
            # Важно: для текстовых постов можно использовать HTML, но аккуратно
            # Сначала пробуем без HTML
            payload_plain = {
                'chat_id': chat_id,
                'text': clean_text,
                'parse_mode': None,
                'disable_web_page_preview': True
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload_plain,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текстовый пост отправлен в {chat_id}")
                return True
            else:
                error_data = response.json() if response.content else {}
                logger.warning(f"Ошибка отправки текста: {response.status_code} - {error_data.get('description', '')}")
                
                # Последняя попытка: разбить на части если слишком длинный
                if len(clean_text) > 4096:
                    logger.info("✂️ Текст слишком длинный, пробуем разбить...")
                    parts = [clean_text[i:i+4000] for i in range(0, len(clean_text), 4000)]
                    
                    success = True
                    for i, part in enumerate(parts):
                        if i > 0:  # Задержка между частями
                            time.sleep(1)
                        
                        part_payload = {
                            'chat_id': chat_id,
                            'text': part,
                            'parse_mode': None,
                            'disable_web_page_preview': True
                        }
                        
                        part_response = session.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json=part_payload,
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
            logger.error(f"❌ Критическая ошибка отправки: {e}")
            return False

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
            
            # Находим ближайший слот
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
            
            # Получение изображений
            logger.info("🖼️ Поиск изображений...")
            
            tg_image = self.get_image_for_theme(self.current_theme)
            time.sleep(2)  # Задержка между запросами
            zen_image = self.get_image_for_theme(self.current_theme)
            
            logger.info(f"📸 Telegram фото: {tg_image[:80]}...")
            logger.info(f"📸 Яндекс.Дзен фото: {zen_image[:80]}...")
            
            # Отправка постов
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку постов...")
            logger.info("=" * 50)
            
            # Telegram
            logger.info(f"📤 Отправка в Telegram канал: {MAIN_CHANNEL_ID}")
            tg_success = self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, tg_image)
            
            time.sleep(3)  # Задержка между отправками
            
            # Яндекс.Дзен
            logger.info(f"📤 Отправка в Яндекс.Дзен канал: {ZEN_CHANNEL_ID}")
            zen_success = self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, zen_image)
            
            # Обработка результатов
            if tg_success or zen_success:
                # Обновляем время последнего поста
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
