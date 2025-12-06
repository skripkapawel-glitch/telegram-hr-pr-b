#!/usr/bin/env python3
"""
Telegram HR Bot - Генератор контента для SMM
Автоматическая генерация и отправка постов в Telegram и Zen
"""

import os
import sys
import json
import time
import random
import logging
import argparse
import requests
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ========== ПРОВЕРКА КРИТИЧЕСКИХ ПЕРЕМЕННЫХ ==========
def validate_environment():
    """Проверка необходимых переменных окружения"""
    errors = []
    
    if not BOT_TOKEN:
        errors.append("❌ BOT_TOKEN не установлен!")
    
    if not GEMINI_API_KEY:
        errors.append("❌ GEMINI_API_KEY не установлен!")
    
    if not MAIN_CHANNEL_ID:
        errors.append("❌ CHANNEL_ID не установлен!")
    
    if errors:
        for error in errors:
            logger.error(error)
            print(error)
        return False
    
    logger.info("✅ Все переменные окружения загружены")
    return True

# ========== НАСТРОЙКА СЕССИИ ==========
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Content-Type': 'application/json'
})

# ========== КЛАСС ГЕНЕРАТОРА ПОСТОВ ==========
class AIPostGenerator:
    def __init__(self, manual_mode=True):
        """Инициализация генератора постов"""
        self.manual_mode = manual_mode
        self.themes = [
            "HR и управление персоналом", 
            "PR и коммуникации", 
            "ремонт и строительство"
        ]
        
        # Файл истории
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Настройки временных слотов
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "400-600",
                "zen_chars": "1000-1500",
                "utc_hour": 6  # 09:00 MSK = 06:00 UTC
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "800-1500",
                "zen_chars": "1700-2300",
                "utc_hour": 11  # 14:00 MSK = 11:00 UTC
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "600-1000",
                "zen_chars": "1500-2100",
                "utc_hour": 16  # 19:00 MSK = 16:00 UTC
            }
        }
        
        self.manual_slots = {
            "morning": self.time_slots["09:00"],
            "day": self.time_slots["14:00"],
            "evening": self.time_slots["19:00"]
        }
        
        logger.info("🤖 Генератор постов инициализирован")

    def load_post_history(self):
        """Загружает историю постов из файла"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📖 Загружена история: {len(data.get('posts', {}))} постов")
                    return data
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": [],
                "statistics": {
                    "total_posts": 0,
                    "successful_posts": 0,
                    "failed_posts": 0
                }
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": [],
                "statistics": {
                    "total_posts": 0,
                    "successful_posts": 0,
                    "failed_posts": 0
                }
            }

    def save_post_history(self):
        """Сохраняет историю постов в файл"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
            logger.debug("💾 История сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с учетом истории"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            # Убираем темы, которые использовались в последних 2 постах
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            # Если все темы использовались, сбрасываем
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            # Обновляем историю тем
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
        """Создает промпт для генерации контента"""
        slot_type = time_slot_info['type']
        slot_name = time_slot_info['name']
        tg_chars = time_slot_info['tg_chars']
        zen_chars = time_slot_info['zen_chars']
        
        return f"""Ты — профессиональный копирайтер и SMM-специалист с 20+ летним опытом.

Тема: {theme}
Время публикации: {slot_name}

Создай ДВА разных поста:

1. ДЛЯ TELEGRAM ({tg_chars} символов):
   • Живой, энергичный стиль с эмодзи
   • Цепляющий заголовок
   • Полезный контент с практическими советами
   • Призыв к обсуждению
   • 5-7 релевантных хештегов
   
2. ДЛЯ ДЗЕН ({zen_chars} символов):
   • Более формальный, аналитический стиль (без эмодзи)
   • Глубокий разбор темы
   • Примеры из практики
   • Выводы и рекомендации
   • Призыв к комментариям
   • В конце добавь: "Главная Видео Статьи Новости Подписки"

ВАЖНО: Не используй разметку, только чистый текст!
Раздели посты строкой: ---

Пример формата:
Telegram-пост:
[текст для Telegram]

---

Дзен-пост:
[текст для Дзен]"""

    def test_gemini_access(self):
        """Проверяет доступность Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            test_data = {
                "contents": [{"parts": [{"text": "Hello"}]}],
                "generationConfig": {
                    "maxOutputTokens": 10,
                    "temperature": 0.1
                }
            }
            
            response = session.post(url, json=test_data, timeout=15)
            
            if response.status_code == 200:
                logger.info("✅ Gemini API доступен")
                return True
            else:
                logger.error(f"❌ Gemini API недоступен: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini API"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 4000,
                    }
                }
                
                logger.info(f"🔄 Генерация текста (попытка {attempt + 1}/{max_retries})...")
                
                response = session.post(url, json=data, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    logger.info(f"✅ Текст сгенерирован ({len(generated_text)} символов)")
                    return generated_text.strip()
                else:
                    logger.error("❌ Gemini вернул пустой ответ")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Таймаут при генерации (попытка {attempt + 1})")
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.info(f"⏳ Ждем {wait_time} секунд перед повторной попыткой...")
                time.sleep(wait_time)
        
        logger.error("❌ Не удалось сгенерировать текст после всех попыток")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет сгенерированный текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        # Ищем разделитель
        separators = ["---", "——", "––––", "\n\n"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    # Очищаем тексты от меток
                    tg_text = parts[0].replace("Telegram-пост:", "").strip()
                    tg_text = tg_text.replace("Для Telegram:", "").strip()
                    
                    zen_text = parts[1].replace("Дзен-пост:", "").strip()
                    zen_text = zen_text.replace("Для Дзен:", "").strip()
                    
                    return tg_text, zen_text
        
        # Если разделитель не найден, делим пополам
        logger.warning("⚠️ Разделитель не найден, делю текст пополам")
        text_length = len(combined_text)
        split_point = text_length // 2
        
        # Ищем точку для красивого разделения
        for i in range(split_point, min(split_point + 200, text_length)):
            if combined_text[i] in ['.', '!', '?', '\n']:
                split_point = i + 1
                break
        
        return combined_text[:split_point].strip(), combined_text[split_point:].strip()

    def get_post_image(self, theme):
        """Получает URL изображения для поста"""
        try:
            theme_queries = {
                "ремонт и строительство": "construction renovation home improvement",
                "HR и управление персоналом": "office team business workplace",
                "PR и коммуникации": "communication marketing social media"
            }
            
            query = theme_queries.get(theme, theme)
            encoded_query = quote_plus(query)
            
            # Параметры изображения
            width, height = 1200, 630
            
            # Пробуем Unsplash
            unsplash_url = f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                logger.info(f"🖼️ Найдено изображение: {image_url[:80]}...")
                return image_url
            
            # Fallback изображения
            fallback_images = {
                "ремонт и строительство": [
                    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
                    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00",
                ],
                "HR и управление персоналом": [
                    "https://images.unsplash.com/photo-1552664730-d307ca884978",
                    "https://images.unsplash.com/photo-1560264280-88b68371db39",
                ],
                "PR и коммуникации": [
                    "https://images.unsplash.com/photo-1533750349088-cd871a92f312",
                    "https://images.unsplash.com/photo-1542744095-fcf48d80b0fd",
                ]
            }
            
            images = fallback_images.get(theme, [
                "https://images.unsplash.com/photo-1497366754035-f200968a6e72"
            ])
            
            selected = random.choice(images)
            image_url = f"{selected}?w={width}&h={height}&fit=crop&q=85"
            logger.info(f"🖼️ Использую fallback изображение")
            
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения: {e}")
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop&q=85"

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        # Убираем возможные HTML теги
        import re
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем специальные символы
        replacements = {
            '&nbsp;': ' ',
            '&emsp;': '    ',
            ' ': ' ',
            '**': '*',
            '__': '_'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Добавляем отступы для пунктов
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Для пунктов добавляем эмодзи и отступ
            if line.startswith('•') or line.startswith('-') or (i > 0 and len(line) < 100):
                formatted_lines.append("   " + line)
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines).strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзен"""
        if not text:
            return ""
        
        # Убираем эмодзи и хештеги
        import re
        
        # Удаляем эмодзи
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # эмоции
            u"\U0001F300-\U0001F5FF"  # символы
            u"\U0001F680-\U0001F6FF"  # транспорт
            u"\U0001F1E0-\U0001F1FF"  # флаги
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # Удаляем хештеги
        text = re.sub(r'#\w+', '', text)
        
        # Добавляем подпись
        signature = "\n\nГлавная Видео Статьи Новости Подписки"
        if signature not in text:
            text += signature
        
        return text.strip()

    def test_bot_access(self):
        """Проверяет доступность Telegram бота"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
            response = session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_name = data["result"]["first_name"]
                    logger.info(f"✅ Бот доступен: @{bot_name}")
                    return True
                else:
                    logger.error(f"❌ Бот не доступен: {data.get('description')}")
            else:
                logger.error(f"❌ Ошибка API Telegram: {response.status_code}")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram"""
        try:
            # Подготавливаем текст
            if len(text) > 1024:
                text = text[:1000] + "..."
            
            # Параметры запроса
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            logger.info(f"📤 Отправляю в {chat_id}...")
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Успешно отправлено в {chat_id}")
                return True
            else:
                error_data = response.json()
                logger.error(f"❌ Ошибка отправки: {error_data.get('description', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            return False

    def generate_and_send_posts(self, slot_type=None):
        """Основная функция генерации и отправки постов"""
        try:
            logger.info("=" * 60)
            logger.info("🚀 НАЧАЛО ГЕНЕРАЦИИ ПОСТОВ")
            logger.info("=" * 60)
            
            # Проверка доступности сервисов
            if not self.test_bot_access():
                return False
            
            if not self.test_gemini_access():
                return False
            
            # Определяем временной слот
            if self.manual_mode and slot_type and slot_type in self.manual_slots:
                time_slot_info = self.manual_slots[slot_type]
                schedule_time = f"Ручной ({slot_type})"
            else:
                # Автоматический выбор слота
                utc_now = datetime.utcnow()
                utc_hour = utc_now.hour
                
                if 5 <= utc_hour < 9:  # 08:00-12:00 MSK
                    time_slot_info = self.time_slots["09:00"]
                    schedule_time = "09:00 МСК"
                elif 9 <= utc_hour < 14:  # 12:00-17:00 MSK
                    time_slot_info = self.time_slots["14:00"]
                    schedule_time = "14:00 МСК"
                else:  # 17:00-23:00 MSK
                    time_slot_info = self.time_slots["19:00"]
                    schedule_time = "19:00 МСК"
            
            logger.info(f"🕒 Временной слот: {schedule_time}")
            logger.info(f"📝 Тип поста: {time_slot_info['name']}")
            
            # Выбираем тему
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            # Генерируем промпт
            prompt = self.create_combined_prompt(self.current_theme, time_slot_info)
            
            # Генерируем текст
            combined_text = self.generate_with_gemini(prompt)
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            # Разделяем на Telegram и Zen
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            logger.info(f"📊 Длина текстов: TG={len(tg_text)}, Zen={len(zen_text)} символов")
            
            # Форматируем тексты
            tg_text = self.format_telegram_text(tg_text)
            zen_text = self.format_zen_text(zen_text)
            
            # Получаем изображения
            logger.info("🖼️ Получаю изображения...")
            image_url = self.get_post_image(self.current_theme)
            
            # Отправляем посты
            logger.info("📤 Начинаю отправку...")
            
            success_count = 0
            
            # Отправляем в основной канал
            logger.info(f"1. Основной канал: {MAIN_CHANNEL_ID}")
            if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url):
                success_count += 1
                time.sleep(2)  # Пауза между отправками
            
            # Отправляем в Zen канал
            logger.info(f"2. Zen канал: {ZEN_CHANNEL_ID}")
            if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url):
                success_count += 1
            
            # Обновляем статистику
            if success_count == 2:
                now = datetime.now()
                
                slot_info = {
                    "timestamp": now.isoformat(),
                    "schedule": schedule_time,
                    "theme": self.current_theme,
                    "channels": [MAIN_CHANNEL_ID, ZEN_CHANNEL_ID],
                    "success": True
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 20:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-20:]
                
                self.post_history["last_post_time"] = now.isoformat()
                
                # Обновляем статистику
                stats = self.post_history.get("statistics", {})
                stats["total_posts"] = stats.get("total_posts", 0) + 1
                stats["successful_posts"] = stats.get("successful_posts", 0) + 1
                self.post_history["statistics"] = stats
                
                self.save_post_history()
                
                logger.info("=" * 60)
                logger.info("🎉 ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ!")
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Статистика: {stats['successful_posts']}/{stats['total_posts']} успешно")
                logger.info("=" * 60)
                
                return True
            else:
                logger.error(f"❌ Успешно отправлено только {success_count}/2 постов")
                
                # Обновляем статистику ошибок
                stats = self.post_history.get("statistics", {})
                stats["total_posts"] = stats.get("total_posts", 0) + 1
                stats["failed_posts"] = stats.get("failed_posts", 0) + 1
                self.post_history["statistics"] = stats
                self.save_post_history()
                
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def send_scheduled_post():
    """Функция для отправки по расписанию"""
    logger.info("⏰ АВТОМАТИЧЕСКАЯ ОТПРАВКА ПО РАСПИСАНИЮ")
    
    bot = AIPostGenerator(manual_mode=False)
    success = bot.generate_and_send_posts()
    
    if success:
        logger.info("✅ Пост отправлен по расписанию")
    else:
        logger.error("❌ Ошибка при отправке по расписанию")

def main():
    """Главная функция запуска бота"""
    print("\n" + "=" * 80)
    print("🤖 TELEGRAM HR BOT - ГЕНЕРАТОР КОНТЕНТА")
    print("=" * 80)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Рабочая директория: {os.getcwd()}")
    print("=" * 80)
    
    # Проверяем переменные окружения
    if not validate_environment():
        sys.exit(1)
    
    print(f"🔑 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"🔑 GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌'}")
    print(f"📢 Каналы: {MAIN_CHANNEL_ID}, {ZEN_CHANNEL_ID}")
    print("=" * 80)
    
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(
        description='Telegram бот для генерации постов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python bot.py --once           # Одноразовый запуск (для GitHub Actions)
  python bot.py --auto           # Запуск планировщика
  python bot.py --slot morning   # Ручная отправка утреннего поста
  python bot.py --slot day       # Ручная отправка дневного поста
  python bot.py --slot evening   # Ручная отправка вечернего поста
        """
    )
    
    parser.add_argument('--auto', '-a', action='store_true',
                       help='Автоматический режим с планировщиком')
    parser.add_argument('--slot', '-s', choices=['morning', 'day', 'evening'],
                       help='Тип поста для ручной отправки')
    parser.add_argument('--once', action='store_true',
                       help='Одноразовый запуск (для workflow)')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Только проверка окружения')
    
    args = parser.parse_args()
    
    # Режим тестирования
    if args.test:
        print("🔍 ТЕСТИРОВАНИЕ ОКРУЖЕНИЯ...")
        
        bot = AIPostGenerator()
        
        print("1. Проверка Telegram бота...")
        if bot.test_bot_access():
            print("   ✅ Telegram бот доступен")
        else:
            print("   ❌ Telegram бот недоступен")
        
        print("2. Проверка Gemini API...")
        if bot.test_gemini_access():
            print("   ✅ Gemini API доступен")
        else:
            print("   ❌ Gemini API недоступен")
        
        print("3. Проверка истории...")
        print(f"   📊 Загружено {len(bot.post_history.get('posts', {}))} постов")
        
        print("\n✅ Тестирование завершено")
        sys.exit(0)
    
    # Режим одноразового запуска (для GitHub Actions)
    elif args.once:
        print("🚀 ЗАПУСК ИЗ GITHUB ACTIONS WORKFLOW...")
        
        bot = AIPostGenerator(manual_mode=True)
        
        # Определяем слот по времени UTC
        utc_hour = datetime.utcnow().hour
        print(f"🕒 Текущее время UTC: {utc_hour}:00")
        
        if utc_hour < 9:  # До 12:00 МСК
            slot = 'morning'
        elif utc_hour < 14:  # До 17:00 МСК
            slot = 'day'
        else:  # После 17:00 МСК
            slot = 'evening'
        
        print(f"🎯 Выбран слот: {slot}")
        
        success = bot.generate_and_send_posts(slot)
        
        if success:
            print("\n✅ РАБОТА ВЫПОЛНЕНА УСПЕШНО!")
            sys.exit(0)
        else:
            print("\n❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ!")
            sys.exit(1)
    
    # Режим ручной отправки конкретного слота
    elif args.slot:
        print(f"👨‍💻 РУЧНАЯ ОТПРАВКА: {args.slot}")
        
        bot = AIPostGenerator(manual_mode=True)
        success = bot.generate_and_send_posts(args.slot)
        
        if success:
            print("\n✅ Пост отправлен успешно!")
        else:
            print("\n❌ Ошибка при отправке")
    
    # Режим автоматического планировщика
    elif args.auto:
        print("🤖 ЗАПУСК ПЛАНИРОВЩИКА...")
        print("Расписание отправки (МСК):")
        print("  • 09:00 - Утренний пост")
        print("  • 14:00 - Дневной пост")
        print("  • 19:00 - Вечерний пост")
        print("=" * 80)
        
        # Создаем планировщик
        scheduler = BlockingScheduler(timezone=pytz.timezone('Europe/Moscow'))
        
        # Добавляем задачи по расписанию
        scheduler.add_job(
            send_scheduled_post,
            CronTrigger(hour=6, minute=0),  # 09:00 МСК (06:00 UTC)
            id='morning_post',
            name='Утренний пост',
            replace_existing=True
        )
        
        scheduler.add_job(
            send_scheduled_post,
            CronTrigger(hour=11, minute=0),  # 14:00 МСК (11:00 UTC)
            id='day_post',
            name='Дневной пост',
            replace_existing=True
        )
        
        scheduler.add_job(
            send_scheduled_post,
            CronTrigger(hour=16, minute=0),  # 19:00 МСК (16:00 UTC)
            id='evening_post',
            name='Вечерний пост',
            replace_existing=True
        )
        
        print("✅ Планировщик запущен и настроен")
        print("📅 Следующие запуски:")
        
        for job in scheduler.get_jobs():
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S МСК')
            print(f"  • {job.name}: {next_run}")
        
        print("\n⏳ Ожидание расписания...")
        print("Для остановки нажмите Ctrl+C")
        print("=" * 80)
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\n👋 Планировщик остановлен")
            scheduler.shutdown()
    
    else:
        # Режим по умолчанию - справка
        parser.print_help()
        print("\n" + "=" * 80)
        print("💡 Для GitHub Actions используйте: python bot.py --once")
        print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
