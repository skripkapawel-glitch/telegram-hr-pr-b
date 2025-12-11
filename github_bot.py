# github_bot.py - Telegram бот для автоматической публикации постов
import os
import requests
import random
import json
import time
import logging
import re
import sys
import argparse
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import telebot
from telebot.types import Message
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL = "@da4a_hr"  # Основной канал (с эмодзи)
ZEN_CHANNEL = "@tehdzenm"   # Дзен канал (без эмодзи)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

if not PEXELS_API_KEY:
    logger.error("❌ PEXELS_API_KEY не установлен! Обязательно получи ключ на pexels.com/api")
    sys.exit(1)

if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установлен! Укажите ваш chat_id")
    sys.exit(1)

# Актуальные модели Gemini (март 2025)
GEMINI_MODEL = "gemini-2.5-pro-exp-03-25"
FALLBACK_MODEL = "gemma-3-27b-it"

logger.info("📤 Режим: отправка постов в личный чат администратора")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: ОТПРАВКА В ЛИЧНЫЙ ЧАТ → МОДЕРАЦИЯ → ПУБЛИКАЦИЯ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"✅ ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
print(f"🤖 Основная модель: {GEMINI_MODEL}")
print(f"🤖 Запасная модель: {FALLBACK_MODEL}")
print(f"📢 Основной канал (с эмодзи): {MAIN_CHANNEL}")
print(f"📢 Дзен канал (без эмодзи): {ZEN_CHANNEL}")
print(f"📋 Режим: 📤 ЛИЧНЫЙ ЧАТ → МОДЕРАЦИЯ → ПУБЛИКАЦИЯ")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        self.image_history_file = "image_history.json"
        self.image_history = self.load_image_history()
        
        # Инициализация бота
        self.bot = telebot.TeleBot(BOT_TOKEN)
        
        # Словарь для хранения постов, ожидающих модерации
        # Структура: {message_id: {'type': 'telegram'/'zen', 'text': '...', 'image_url': '...'}}
        self.sent_messages = {}
        
        # Флаги для отслеживания публикаций
        self.published_telegram = False
        self.published_zen = False
        
        # Форматы подачи текста
        self.text_formats = [
            "разбор ошибки",
            "разбор ситуации",
            "микро-исследование",
            "аналитическое наблюдение",
            "причинно-следственные связи",
            "инсайт",
            "структурированные советы",
            "демонстрация пользы",
            "объяснение простым языком",
            "мини-история",
            "взгляд автора",
            "аналогия",
            "мини-обобщение опыта",
            "тихая эмоциональная подача",
            "сравнение подходов"
        ]
        
        # Хэштеги по темам
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#кадры", 
                "#команда", "#лидерство", "#мотивация", "#развитиеперсонала",
                "#бизнес", "#управление", "#работа", "#карьера"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#продвижение", 
                "#брендинг", "#соцсети", "#медиа", "#пиар", 
                "#общение", "#публичность", "#репутация", "#инфоповод"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", 
                "#ремонтквартир", "#строитель", "#отделка", "#ремонтдома",
                "#стройматериалы", "#проект", "#ремонтподключ", "#евроремонт"
            ]
        }
        
        # Стили по времени публикации
        self.time_styles = {
            "09:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "style": "энерго-старт: короткая польза, лёгкая динамика, мотивирующий фокус, ясные выгоды, простое объяснение, «факт → мысль → вывод»",
                "allowed_formats": [
                    "демонстрация пользы", "объяснение простым языком", 
                    "структурированные советы", "сравнение подходов", 
                    "мини-обобщение опыта"
                ],
                "tg_chars": (400, 600),
                "zen_chars": (600, 700)
            },
            "14:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "style": "рациональность и аналитика: наблюдение, разбор явления, микро-исследование, цепочка причин → следствий, практическая логика, структурная подача, инсайт",
                "allowed_formats": [
                    "микро-исследование", "аналитическое наблюдение", 
                    "разбор ошибки", "разбор ситуации", 
                    "причинно-следственные связи", "инсайт"
                ],
                "tg_chars": (700, 900),
                "zen_chars": (700, 900)
            },
            "19:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "style": "глубина и история: личный взгляд, мини-история, аналогия, проживание опыта, тёплый честный тон, осознанный вывод",
                "allowed_formats": [
                    "мини-история", "взгляд автора", "аналогия",
                    "тихая эмоциональная подача", "проживание опыта"
                ],
                "tg_chars": (600, 900),
                "zen_chars": (700, 800)
            }
        }
        
        # Мягкие финалы
        self.soft_finals = [
            "А как вы считаете?",
            "Было ли у вас так?",
            "Что думаете?",
            "Согласны с этим?",
            "Какой у вас опыт?",
            "Как бы вы поступили?",
            "Есть что добавить?"
        ]
        
        # Словарь для одобрительных слов
        self.approval_words = ['ок', 'ok', 'да', '👍', '🔥', 'класс', 'хорошо', 'отлично', 'публиковать', 'го', 'согласен', '+', 'вперед']
        
        self.current_theme = None
        self.current_format = None
        self.current_style = None
        self.current_model = GEMINI_MODEL
        
        # Флаг для отслеживания запуска polling
        self.polling_started = False

    def remove_webhook(self):
        """Удаляет вебхук перед запуском polling"""
        try:
            logger.info("🧹 Удаляю вебхук...")
            self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Вебхук удален, pending updates очищены")
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления вебхука: {e}")
            return False

    def setup_message_handler(self):
        """Настраивает обработчик сообщений"""
        @self.bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            self.process_admin_reply(message)
        
        logger.info("✅ Обработчик сообщений настроен")
        return handle_all_messages

    def process_admin_reply(self, message):
        """Обрабатывает ответы администратора"""
        try:
            logger.info(f"📨 Получено сообщение от: {message.chat.id}")
            logger.info(f"📝 Текст: {message.text}")
            logger.info(f"🔍 Ответ на сообщение ID: {message.reply_to_message.message_id if message.reply_to_message else 'None'}")
            
            # Проверяем, что сообщение от администратора
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.info(f"❌ Сообщение не от админа: {message.chat.id} != {ADMIN_CHAT_ID}")
                return
            
            logger.info("✅ Сообщение от администратора!")
            
            # Проверяем, что это ответ на сообщение (reply)
            if not message.reply_to_message:
                logger.info("❌ Сообщение не является reply (ответом)")
                return
            
            # Получаем ID сообщения, на которое ответили
            original_message_id = message.reply_to_message.message_id
            logger.info(f"📌 Ответ на сообщение с ID: {original_message_id}")
            
            # Проверяем, есть ли такой пост в ожидающих
            if original_message_id not in self.sent_messages:
                logger.info(f"❌ Сообщение ID {original_message_id} не найдено в sent_messages")
                logger.info(f"📊 Доступные ID: {list(self.sent_messages.keys())}")
                return
            
            logger.info(f"✅ Найден пост для публикации!")
            
            # Проверяем текст ответа
            reply_text = (message.text or "").lower().strip()
            logger.info(f"📝 Текст ответа: '{reply_text}'")
            
            # Проверяем, является ли ответ одобрением
            is_approval = False
            for word in self.approval_words:
                if word in reply_text:
                    is_approval = True
                    break
            
            logger.info(f"✅ Является ли одобрением: {is_approval}")
            
            if not is_approval:
                logger.info("❌ Ответ не является одобрением")
                return
            
            # Получаем данные поста
            post_data = self.sent_messages[original_message_id]
            post_type = post_data.get('type')  # 'telegram' или 'zen'
            post_text = post_data.get('text')
            image_url = post_data.get('image_url')
            channel = post_data.get('channel')
            
            logger.info(f"🚀 Публикую пост типа '{post_type}' в канал {channel}")
            
            # Публикуем пост в канал
            success = self.publish_to_channel(post_text, image_url, channel)
            
            if success:
                # Обновляем флаги публикации
                if post_type == 'telegram':
                    self.published_telegram = True
                    logger.info("✅ Telegram пост опубликован!")
                    # Отправляем подтверждение администратору
                    self.bot.reply_to(message, "✅ Telegram пост опубликован в канал!")
                elif post_type == 'zen':
                    self.published_zen = True
                    logger.info("✅ Дзен пост опубликован!")
                    # Отправляем подтверждение администратору
                    self.bot.reply_to(message, "✅ Дзен пост опубликован в канал!")
                
                # Удаляем пост из ожидающих
                del self.sent_messages[original_message_id]
                logger.info(f"🗑️ Удален из ожидания: {original_message_id}")
            else:
                logger.error(f"❌ Ошибка публикации поста типа '{post_type}'")
                self.bot.reply_to(message, f"❌ Ошибка публикации поста")
        
        except Exception as e:
            logger.error(f"💥 Ошибка обработки ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                self.bot.reply_to(message, f"❌ Ошибка: {str(e)[:100]}")
            except:
                pass

    def start_polling_thread(self):
        """Запускает polling в отдельном потоке"""
        try:
            logger.info("🔄 Запускаю polling в отдельном потоке...")
            
            # Удаляем вебхук перед запуском polling
            self.remove_webhook()
            
            # Настраиваем обработчик
            self.setup_message_handler()
            
            # Запускаем polling
            self.bot.polling(none_stop=True, interval=1, timeout=30)
            self.polling_started = True
            logger.info("✅ Polling запущен и готов принимать сообщения")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            self.polling_started = False

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки истории: {e}")
        return {
            "sent_slots": {},
            "last_post": None,
            "formats_used": [],
            "themes_used": [],
            "theme_rotation": []
        }

    def load_image_history(self):
        """Загружает историю использованных картинок"""
        try:
            if os.path.exists(self.image_history_file):
                with open(self.image_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки истории картинок: {e}")
        return {
            "used_images": [],
            "last_update": None
        }

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения истории: {e}")

    def save_image_history(self, image_url):
        """Сохраняет историю использованных картинок"""
        try:
            if image_url not in self.image_history.get("used_images", []):
                self.image_history.setdefault("used_images", []).append(image_url)
                self.image_history["last_update"] = datetime.utcnow().isoformat()
                
                with open(self.image_history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.image_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения истории картинок: {e}")

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            if self.post_history and "sent_slots" in self.post_history:
                sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
                return slot_time in sent_slots
            return False
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки отправленного слота: {e}")
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if not self.post_history:
                self.post_history = {}
            
            if "sent_slots" not in self.post_history:
                self.post_history["sent_slots"] = {}
            
            if today not in self.post_history["sent_slots"]:
                self.post_history["sent_slots"][today] = []
            
            if slot_time not in self.post_history["sent_slots"][today]:
                self.post_history["sent_slots"][today].append(slot_time)
            
            if self.current_theme:
                if "themes_used" not in self.post_history:
                    self.post_history["themes_used"] = []
                self.post_history["themes_used"].append({
                    "date": today,
                    "time": slot_time,
                    "theme": self.current_theme
                })
                
                # Обновляем ротацию тем
                if "theme_rotation" not in self.post_history:
                    self.post_history["theme_rotation"] = []
                self.post_history["theme_rotation"].append(self.current_theme)
                if len(self.post_history["theme_rotation"]) > 10:
                    self.post_history["theme_rotation"] = self.post_history["theme_rotation"][-10:]
            
            if self.current_format:
                if "formats_used" not in self.post_history:
                    self.post_history["formats_used"] = []
                self.post_history["formats_used"].append({
                    "date": today,
                    "time": slot_time,
                    "format": self.current_format
                })
            
            self.save_history()
            logger.info(f"✅ Слот {slot_time} помечен как отправленный")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с умной ротацией"""
        try:
            if not self.post_history:
                self.post_history = {"theme_rotation": []}
            
            if "theme_rotation" not in self.post_history:
                self.post_history["theme_rotation"] = []
            
            theme_rotation = self.post_history.get("theme_rotation", [])
            
            if not theme_rotation:
                theme = random.choice(self.themes)
                self.current_theme = theme
                logger.info(f"🎯 Выбрана тема (первая): {theme}")
                return theme
            
            last_theme = theme_rotation[-1] if theme_rotation else None
            available_themes = [t for t in self.themes if t != last_theme]
            
            if not available_themes:
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_rotation):
                    for theme in self.themes:
                        if theme == used_theme:
                            theme_counts[theme] += 1
                theme = min(theme_counts, key=theme_counts.get)
            else:
                theme = random.choice(available_themes)
            
            self.current_theme = theme
            logger.info(f"🎯 Выбрана тема: {theme} (последняя была: {last_theme})")
            return theme
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выборе темы: {e}")
            self.current_theme = random.choice(self.themes)
            logger.info(f"🎯 Выбрана тема (случайно): {self.current_theme}")
            return self.current_theme

    def get_smart_format(self, slot_style):
        """Выбирает формат подачи с учетом стиля времени"""
        try:
            allowed_formats = slot_style.get("allowed_formats", self.text_formats)
            
            if not self.post_history or "formats_used" not in self.post_history:
                self.current_format = random.choice(allowed_formats)
                logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
                return self.current_format
            
            recent_formats = []
            if self.post_history.get("formats_used"):
                recent_entries = self.post_history["formats_used"][-5:] if len(self.post_history["formats_used"]) >= 5 else self.post_history["formats_used"]
                recent_formats = [item.get("format", "") for item in recent_entries if item.get("format")]
            
            recent_unique = list(dict.fromkeys(recent_formats))
            available_formats = [fmt for fmt in allowed_formats if fmt not in recent_unique[-3:]]
            
            if not available_formats:
                available_formats = allowed_formats.copy()
            
            text_format = random.choice(available_formats)
            self.current_format = text_format
            logger.info(f"📝 Выбран формат: {text_format}")
            return text_format
        except Exception as e:
            logger.error(f"❌ Ошибка при выборе формата: {e}")
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def get_relevant_hashtags(self, theme, count=3):
        """Возвращает релевантные хэштеги для темы"""
        try:
            hashtags = self.hashtags_by_theme.get(theme, [])
            if len(hashtags) >= count:
                return random.sample(hashtags, count)
            return hashtags[:count] if hashtags else ["#бизнес", "#советы", "#развитие"]
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения хэштегов: {e}")
            return ["#бизнес", "#советы", "#развитие"]

    def get_soft_final(self):
        """Возвращает случайный мягкий финал"""
        return random.choice(self.soft_finals)

    def create_master_prompt(self, theme, slot_style, text_format, image_description):
        """Создает промпт для генерации обоих постов"""
        try:
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            hashtags = self.get_relevant_hashtags(theme, 3)
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            prompt = f"""🔥 ГЕНЕРАЦИЯ ДВУХ ПОСТОВ: С ЭМОДЗИ И БЕЗ ЭМОДЗИ

🎯 ТВОЯ РОЛЬ
Ты — топ-специалист с 30+ лет опыта в HR, PR и строительстве.
Ты пишешь живо, глубоко, уверенно и структурно.

🎯 ЗАДАЧА
Сгенерировать ДВА текста по одной теме, но с разной подачей:
1. Telegram пост С ЭМОДЗИ - для основного канала
2. Дзен пост БЕЗ ЭМОДЗИ - для канала Дзен

Тема поста: {theme}

🔒 СТРОГИЕ ПРАВИЛА
1. Telegram пост ДОЛЖЕН содержать эмодзи
2. Дзен пост НЕ ДОЛЖЕН содержать эмодзи вообще
3. Оба текста разные по структуре, но об одном смысле

🕒 УЧЁТ ВРЕМЕНИ ПУБЛИКАЦИИ
{slot_style['name']} — {slot_style['style']}

✂ ЛИМИТЫ СИМВОЛОВ (СТРОГО)
Telegram (с эмодзи): {tg_min}–{tg_max} символов
Дзен (без эмодзи): {zen_min}–{zen_max} символов

🧱 СТРУКТУРА TELEGRAM ПОСТА (С ЭМОДЗИ)
• Начинается с эмодзи {slot_style['emoji']}
• 1–3 абзаца с глубиной
• Мини-вывод
• Мягкий финал: {soft_final}
• Хэштеги: {hashtags_str}
• Картинка: {image_description}

🧱 СТРУКТУРА ДЗЕН ПОСТА (БЕЗ ЭМОДЗИ)
• Заголовок БЕЗ эмодзи
• 2–4 раскрывающих абзаца  
• Мини-вывод
• Мягкий финал: {soft_final}
• Хэштеги: {hashtags_str}
• Картинка: {image_description}

💡 ФОРМАТ ПОДАЧИ
{text_format}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
НАЧИНАЙ ГЕНЕРАЦИЮ С TELEGRAM ПОСТА (С ЭМОДЗИ):

TELEGRAM ПОСТ (с эмодзи, {tg_min}-{tg_max} символов):"""

            return prompt
        except Exception as e:
            logger.error(f"❌ Ошибка создания промпта: {e}")
            return ""

    def clean_generated_text(self, text):
        """Очищает сгенерированный текст от артефактов"""
        if not text:
            return text
        
        try:
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # Пропускаем строки со счетчиком символов
                if any(keyword in line.lower() for keyword in ['длина:', 'символов', 'символы:', 'количество символов', 'символа', 'текст содержит']):
                    continue
                
                # Удаляем ** с начала и конца строки
                stripped_line = line.strip()
                if stripped_line.startswith('**') and stripped_line.endswith('**'):
                    cleaned_line = stripped_line[2:-2].strip()
                    cleaned_lines.append(cleaned_line)
                else:
                    cleaned_lines.append(line)
            
            cleaned_text = '\n'.join(cleaned_lines)
            
            # Удаляем возможные артефакты
            cleaned_text = re.sub(r'━+$', '', cleaned_text, flags=re.MULTILINE)
            cleaned_text = re.sub(r'=+$', '', cleaned_text, flags=re.MULTILINE)
            
            # Удаляем возможные фразы в конце
            unwanted_endings = [
                'текст готов', 'пост готов', 'готово', 'создано', 
                'вот пост:', 'вот текст:', 'результат:', 'пост:',
                'пример поста:', 'структура поста:', 'дополнительный контент'
            ]
            
            for ending in unwanted_endings:
                if cleaned_text.lower().endswith(ending.lower()):
                    cleaned_text = cleaned_text[:-len(ending)].strip()
            
            return cleaned_text.strip()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очистки текста: {e}")
            return text.strip()

    def _force_cut_text(self, text, target_max):
        """Режет текст до нужной длины"""
        if len(text) <= target_max:
            return text
        
        logger.info(f"⚔️ Сокращение: {len(text)} → {target_max}")
        
        # Пробуем найти естественное место для обрезки
        cut_point = text[:target_max].rfind('.')
        if cut_point > target_max * 0.8:  # Если нашли точку в последних 20%
            text = text[:cut_point + 1].strip()
        else:
            # Ищем перенос строки
            cut_point = text[:target_max].rfind('\n')
            if cut_point > target_max * 0.8:
                text = text[:cut_point].strip()
            else:
                # Ищем пробел
                cut_point = text[:target_max].rfind(' ')
                if cut_point > target_max * 0.8:
                    text = text[:cut_point].strip()
                else:
                    # Жесткая обрезка
                    text = text[:target_max - 3].strip() + "..."
        
        logger.info(f"⚔️ После сокращения: {len(text)} символов")
        return text

    def parse_generated_texts(self, text, tg_min, tg_max, zen_min, zen_max):
        """Парсит сгенерированные тексты"""
        try:
            # Разделяем на Telegram и Дзен посты
            parts = text.split('ДЗЕН ПОСТ')
            if len(parts) < 2:
                parts = text.split('ДЗЕН ПОСТ:')
            
            if len(parts) < 2:
                # Пробуем найти разделитель по заглавным буквам
                lines = text.split('\n')
                tg_lines = []
                zen_lines = []
                found_separator = False
                
                for line in lines:
                    if not found_separator:
                        tg_lines.append(line)
                        if line.strip().upper() == 'ДЗЕН ПОСТ' or 'ДЗЕН' in line.upper():
                            found_separator = True
                            tg_lines.pop()  # Удаляем разделитель
                    else:
                        zen_lines.append(line)
                
                tg_text_raw = '\n'.join(tg_lines)
                zen_text_raw = '\n'.join(zen_lines)
            else:
                tg_text_raw = parts[0].replace('TELEGRAM ПОСТ:', '').replace('TELEGRAM ПОСТ', '').strip()
                zen_text_raw = parts[1].replace('ДЗЕН ПОСТ:', '').strip()
            
            # Очищаем тексты
            tg_text = self.clean_generated_text(tg_text_raw)
            zen_text = self.clean_generated_text(zen_text_raw)
            
            # Удаляем возможные маркеры
            if 'Telegram' in tg_text[:100]:
                tg_text = tg_text.replace('Telegram', '').replace('пост', '').strip()
            if 'Дзен' in zen_text[:100]:
                zen_text = zen_text.replace('Дзен', '').replace('пост', '').strip()
            
            # Удаляем любые повторяющиеся фразы
            for phrase in ["Дополнительный контент для соответствия длине.", 
                          "Дополнительный контент.", 
                          "Текст для соответствия длине."]:
                while phrase in tg_text:
                    tg_text = tg_text.replace(phrase, '').strip()
                while phrase in zen_text:
                    zen_text = zen_text.replace(phrase, '').strip()
            
            # Удаляем лишние переносы строк
            tg_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', tg_text)
            zen_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', zen_text)
            
            # Проверяем длину
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            logger.info(f"📊 Парсинг: Telegram {tg_length} символов, Дзен {zen_length} символов")
            
            # Если текст слишком короткий - возвращаем None для перегенерации
            if tg_length < tg_min * 0.8 or zen_length < zen_min * 0.8:
                logger.warning(f"⚠️ Текст слишком короткий для перегенерации")
                return None, None
            
            # Корректируем длину если необходимо
            if tg_length > tg_max:
                logger.warning(f"⚠️ Telegram текст слишком длинный: {tg_length} > {tg_max}")
                tg_text = self._force_cut_text(tg_text, tg_max)
            
            if zen_length > zen_max:
                logger.warning(f"⚠️ Дзен текст слишком длинный: {zen_length} > {zen_max}")
                zen_text = self._force_cut_text(zen_text, zen_max)
            
            return tg_text, zen_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга текстов: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None

    def generate_with_retry(self, prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=3):
        """Генерация постов с повторными попытками"""
        current_model = self.current_model
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🤖 Попытка {attempt+1}/{max_attempts}: генерация обоих постов (модель: {current_model})")
                
                # Актуальный URL для Gemini API
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 3000,
                    }
                }
                
                headers = {
                    'Content-Type': 'application/json'
                }
                
                response = session.post(url, json=data, headers=headers, timeout=60)
                
                if response.status_code != 200:
                    logger.error(f"❌ Gemini API ошибка: {response.status_code}")
                    logger.error(f"Ответ: {response.text[:200]}")
                    
                    if response.status_code == 404:
                        logger.error(f"⚠️ Модель {current_model} не найдена, пробуем {FALLBACK_MODEL}")
                        current_model = FALLBACK_MODEL
                        continue
                    
                    if attempt < max_attempts - 1:
                        time.sleep(3)
                        continue
                
                result = response.json()
                
                if 'candidates' not in result or not result['candidates']:
                    logger.error(f"❌ Нет candidates в ответе: {result}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                        continue
                
                candidate = result['candidates'][0]
                if 'content' not in candidate or 'parts' not in candidate['content']:
                    logger.error(f"❌ Неверная структура ответа: {candidate}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                        continue
                
                generated_text = candidate['content']['parts'][0]['text']
                logger.info(f"✅ Текст получен, длина: {len(generated_text)} символов")
                
                # Парсим оба текста
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    # Проверяем финальную длину
                    tg_final_len = len(tg_text)
                    zen_final_len = len(zen_text)
                    
                    # Основной критерий - тексты не должны быть пустыми
                    if tg_final_len >= 100 and zen_final_len >= 100:
                        logger.info(f"✅ Посты сгенерированы: TG={tg_final_len}, Дзен={zen_final_len}")
                        
                        # Если длины в пределах диапазона - отлично
                        if tg_min <= tg_final_len <= tg_max and zen_min <= zen_final_len <= zen_max:
                            logger.info(f"✅ Идеально: TG в диапазоне {tg_min}-{tg_max}, Дзен в диапазоне {zen_min}-{zen_max}")
                            return tg_text, zen_text
                        else:
                            # Если близко к диапазону, но не идеально - все равно возвращаем
                            if tg_final_len >= tg_min * 0.9 and zen_final_len >= zen_min * 0.9:
                                logger.warning(f"⚠️ Длины близки к диапазону: TG={tg_final_len}, Дзен={zen_final_len}")
                                return tg_text, zen_text
                            else:
                                # Слишком короткие - пробуем еще раз
                                logger.warning(f"⚠️ Тексты слишком короткие, пробуем снова")
                                if attempt < max_attempts - 1:
                                    time.sleep(2)
                                    continue
                    else:
                        logger.warning(f"⚠️ Тексты слишком короткие: TG={tg_final_len}, Дзен={zen_final_len}")
                        if attempt < max_attempts - 1:
                            time.sleep(2)
                            continue
                
                # Если не получили тексты или они плохие
                if attempt < max_attempts - 1:
                    wait_time = 2 * (attempt + 1)
                    logger.info(f"⏸️ Жду {wait_time} секунд перед следующей попыткой...")
                    time.sleep(wait_time)
                    
            except requests.exceptions.Timeout:
                logger.error(f"⏱️ Таймаут при попытке {attempt+1}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
            except requests.exceptions.ConnectionError:
                logger.error(f"🌐 Ошибка соединения при попытке {attempt+1}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
            except Exception as e:
                logger.error(f"💥 Ошибка в generate_with_retry: {e}")
                import traceback
                logger.error(traceback.format_exc())
                if attempt < max_attempts - 1:
                    time.sleep(3)
        
        # АВАРИЙНЫЙ РЕЖИМ - создаем качественные посты вручную
        logger.warning("🆘 Все попытки провалились, создаем качественные посты вручную")
        
        theme = self.current_theme or "HR и управление персоналом"
        hashtags = self.get_relevant_hashtags(theme, 3)
        hashtags_str = ' '.join(hashtags)
        soft_final = self.get_soft_final()
        
        emoji = self.current_style['emoji'] if self.current_style else "🌙"
        
        # Качественный Telegram пост (С ЭМОДЗИ)
        if theme == "HR и управление персоналом":
            tg_emergency = f"{emoji} Ключевая ошибка HR, которую допускают 9 из 10 компаний\n\nНанимая сотрудников, мы часто фокусируемся на навыках и опыте, забывая о культурном соответствии.\n\nНовый сотрудник с блестящим резюме, но чуждыми ценностями — бомба замедленного действия.\n\nПроводите ценностные интервью наравне с профессиональными. Это сэкономит время и ресурсы на адаптацию.\n\nИ помните: навыкам можно научить, а ценности изменить почти невозможно.\n\n{soft_final}\n\n{hashtags_str}"
        elif theme == "PR и коммуникации":
            tg_emergency = f"{emoji} Почему молчание в кризис убивает репутацию\n\nКогда случается кризис, первая реакция — затаиться и переждать.\n\nНо в эпоху соцсетей молчание воспринимается как признание вины.\n\nБыстрая, честная реакция — уже 50% успеха в управлении кризисом.\n\nГоворите первыми, говорите правду, говорите регулярно.\n\n{soft_final}\n\n{hashtags_str}"
        else:
            tg_emergency = f"{emoji} Самый дорогой этап ремонта, который часто экономят\n\nНе геометрия стен, не толщина штукатурки. Самое важное — подготовка поверхностей.\n\nЭкономия на грунтовке и выравнивании приводит к трещинам через 3 месяца.\n\nИнвестируйте в подготовку — это окупится долговечностью.\n\nКачественная основа — залог безупречной отделки на годы.\n\n{soft_final}\n\n{hashtags_str}"
        
        # Качественный Дзен пост (БЕЗ ЭМОДЗИ)
        if theme == "HR и управление персоналом":
            zen_emergency = f"Как избежать главной ошибки в подборе персонала\n\nСовременный HR сталкивается с парадоксом: идеальные по навыкам кандидаты оказываются неподходящими по ценностям. Это приводит к текучке и конфликтам.\n\nРешение — введение ценностных интервью. Задавайте вопросы о принятии решений в сложных ситуациях, о понимании миссии компании, о личных приоритетах.\n\nКультурное соответствие важнее идеального резюме. Сотрудник, разделяющий ценности, будет развиваться вместе с компанией, проявлять инициативу и оставаться лояльным.\n\nИсследования показывают: правильный культурный fit повышает удержание персонала на 40%.\n\n{soft_final}\n\n{hashtags_str}"
        elif theme == "PR и коммуникации":
            zen_emergency = f"Стратегия коммуникации в кризисных ситуациях\n\nКризис — проверка на прочность для любой коммуникационной стратегии. Молчание в первые часы создает вакуум, который заполняют слухи и домыслы.\n\nКлючевое правило: говорить быстро, четко и регулярно. Даже если нет полной информации, сообщите, что ситуация под контролем и вы работаете над решением.\n\nЧестность и открытость спасают репутацию там, где скрытность ее разрушает. Прозрачность вызывает доверие даже в самых сложных ситуациях.\n\nПомните: кризис — это не только угроза, но и возможность показать ответственность компании.\n\n{soft_final}\n\n{hashtags_str}"
        else:
            zen_emergency = f"Экономия на подготовке поверхностей: ложная выгода\n\nВ стремлении удешевить ремонт заказчики часто соглашаются на экономию подготовительных работ. Это фундаментальная ошибка.\n\nГрунтовка, выравнивание, обработка трещин — этапы, которые определяют срок службы отделки. На правильно подготовленной поверхности материалы держатся в разы дольше.\n\nЭкономия 10% на подготовке приводит к дополнительным 50% затрат на переделку через год. Инвестиции в подготовку окупаются отсутствием ремонтов в ближайшие годы.\n\nПрофессионалы знают: ремонт начинается не с отделки, а с подготовки.\n\n{soft_final}\n\n{hashtags_str}"
        
        # Удаляем эмодзи из Дзен поста
        zen_emergency = re.sub(r'[^\w\s#@.,!?;:"\'()\-—–«»]', '', zen_emergency)
        
        # Подгоняем длину если нужно
        if len(tg_emergency) > tg_max:
            tg_emergency = self._force_cut_text(tg_emergency, tg_max)
        if len(zen_emergency) > zen_max:
            zen_emergency = self._force_cut_text(zen_emergency, zen_max)
        
        # Если все еще слишком короткие, добавляем дополнительный содержательный текст
        while len(tg_emergency) < tg_min * 0.9:
            tg_emergency += f"\n\nПрактический опыт показывает: внимание к деталям определяет конечный результат."
        
        while len(zen_emergency) < zen_min * 0.9:
            zen_emergency += f"\n\nРеальные кейсы подтверждают эффективность этого подхода в долгосрочной перспективе."
        
        logger.info(f"🆘 Используем качественные посты: TG={len(tg_emergency)} симв, Дзен={len(zen_emergency)} симв")
        return tg_emergency, zen_emergency

    def get_post_image_and_description(self, theme):
        """Находит подходящую картинку и генерирует описание"""
        try:
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "building"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social"]
            }
            
            queries = theme_queries.get(theme, ["business", "work", "success"])
            query = random.choice(queries)
            
            logger.info(f"🔍 Ищем картинку в Pexels по запросу: '{query}'")
            
            url = "https://api.pexels.com/v1/search"
            params = {
                "query": query,
                "per_page": 10,
                "orientation": "landscape",
                "size": "large"
            }
            
            headers = {
                "Authorization": PEXELS_API_KEY
            }
            
            response = session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    logger.info(f"📸 Найдено {len(photos)} фото в Pexels")
                    photo = random.choice(photos)
                    image_url = photo.get("src", {}).get("large", "")
                    photographer = photo.get("photographer", "")
                    alt_text = photo.get("alt", "")
                    
                    if image_url:
                        description = f"{alt_text if alt_text else 'Профессиональная фотография'} от {photographer if photographer else 'фотографа'}. Высокое качество, релевантно теме."
                        logger.info(f"🖼️ Используем картинку из Pexels с описанием: {description[:80]}...")
                        return image_url, description
                else:
                    logger.warning("⚠️ Pexels не вернул фотографий по запросу")
            else:
                logger.error(f"❌ Pexels API ошибка: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске картинки в Pexels: {e}")
        
        logger.info("🔄 Pexels не сработал, пробуем Unsplash...")
        try:
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                description = f"Профессиональная фотография на тему '{query}'. Высокое качество, релевантно содержанию."
                logger.info(f"🖼️ Используем картинку из Unsplash: {description[:80]}...")
                return image_url, description
        except Exception as unsplash_error:
            logger.error(f"❌ Unsplash тоже не сработал: {unsplash_error}")
        
        default_image = "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"
        description = "Профессиональная фотография бизнес-тематики. Высокое качество, релевантно деловому контенту."
        logger.info(f"🖼️ Используем дефолтную картинку: {description}")
        return default_image, description

    def format_telegram_text(self, text, slot_style):
        """Форматирует Telegram текст (с эмодзи)"""
        if not text:
            return None
        
        text = text.strip()
        text = self.clean_generated_text(text)
        
        # Удаляем все упоминания "Дополнительный контент"
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        # Добавляем стартовый эмодзи слота если его нет
        if not text.startswith(slot_style['emoji']):
            lines = text.split('\n')
            if lines and lines[0].strip():
                lines[0] = f"{slot_style['emoji']} {lines[0]}"
                text = '\n'.join(lines)
        
        tg_min, tg_max = slot_style['tg_chars']
        text_length = len(text)
        
        logger.info(f"📏 Telegram текст (с эмодзи): {text_length} символов ({tg_min}-{tg_max})")
        
        # Для аварийных постов разрешаем быть короче
        if text_length < tg_min:
            logger.warning(f"⚠️ Telegram текст коротковат: {text_length} < {tg_min}")
            # Не возвращаем None, аварийный режим уже обработал это
        
        if text_length > tg_max:
            logger.warning(f"⚠️ Telegram текст длинноват: {text_length} > {tg_max}")
            text = self._force_cut_text(text, tg_max)
            text_length = len(text)
        
        return text

    def format_zen_text(self, text, slot_style):
        """Форматирует Дзен текст (без эмодзи)"""
        if not text:
            return None
        
        text = text.strip()
        text = self.clean_generated_text(text)
        
        # Удаляем все упоминания "Дополнительный контент"
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        # Удаляем ВСЕ эмодзи из Дзен текста
        text = re.sub(r'[^\w\s#@.,!?;:"\'()\-—–«»]', '', text)
        
        zen_min, zen_max = slot_style['zen_chars']
        text_length = len(text)
        
        logger.info(f"📏 Дзен текст (без эмодзи): {text_length} символов ({zen_min}-{zen_max})")
        
        # Для аварийных постов разрешаем быть короче
        if text_length < zen_min:
            logger.warning(f"⚠️ Дзен текст коротковат: {text_length} < {zen_min}")
        
        if text_length > zen_max:
            logger.warning(f"⚠️ Дзен текст длинноват: {text_length} > {zen_max}")
            text = self._force_cut_text(text, zen_max)
            text_length = len(text)
        
        return text

    def send_to_admin_for_moderation(self, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет посты администратору на модерацию"""
        logger.info("📤 Отправляю посты администратору на модерацию...")
        
        success_count = 0
        
        # Telegram пост (с эмодзи)
        logger.info(f"📨 Отправляем Telegram пост (с эмодзи) администратору")
        tg_message = f"📱 <b>TELEGRAM ПОСТ (с эмодзи)</b>\n\n"
        tg_message += f"🎯 <b>Для канала:</b> {MAIN_CHANNEL}\n"
        tg_message += f"🕒 <b>Время:</b> {slot_time} МСК\n"
        tg_message += f"📚 <b>Тема:</b> {theme}\n"
        tg_message += f"📏 <b>Символов:</b> {len(tg_text)}\n\n"
        tg_message += tg_text
        
        try:
            # Отправляем пост с картинкой
            sent_message = self.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=image_url,
                caption=tg_message[:1024],  # Telegram ограничивает подписи к фото
                parse_mode='HTML'
            )
            
            # Сохраняем информацию о посте для обработки ответов
            self.sent_messages[sent_message.message_id] = {
                'type': 'telegram',
                'text': tg_text,
                'image_url': image_url,
                'channel': MAIN_CHANNEL,
                'sent_time': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Telegram пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram поста: {e}")
        
        time.sleep(2)
        
        # Дзен пост (без эмодзи)
        logger.info(f"📨 Отправляем Дзен пост (без эмодзи) администратору")
        zen_message = f"📝 <b>ДЗЕН ПОСТ (без эмодзи)</b>\n\n"
        zen_message += f"🎯 <b>Для канала:</b> {ZEN_CHANNEL}\n"
        zen_message += f"🕒 <b>Время:</b> {slot_time} МСК\n"
        zen_message += f"📚 <b>Тема:</b> {theme}\n"
        zen_message += f"📏 <b>Символов:</b> {len(zen_text)}\n\n"
        zen_message += zen_text
        
        try:
            # Отправляем пост с картинкой
            sent_message = self.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=image_url,
                caption=zen_message[:1024],
                parse_mode='HTML'
            )
            
            # Сохраняем информацию о посте для обработки ответов
            self.sent_messages[sent_message.message_id] = {
                'type': 'zen',
                'text': zen_text,
                'image_url': image_url,
                'channel': ZEN_CHANNEL,
                'sent_time': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Дзен пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Дзен поста: {e}")
        
        if success_count == 2:
            instruction = f"✅ <b>Оба поста отправлены на модерацию</b>\n\n"
            instruction += f"<b>Telegram пост (с эмодзи)</b> → будет в {MAIN_CHANNEL}\n"
            instruction += f"<b>Дзен пост (без эмодзи)</b> → будет в {ZEN_CHANNEL}\n\n"
            instruction += f"<b>Чтобы опубликовать пост:</b>\n"
            instruction += f"• Ответьте на пост любым одобрением:\n"
            instruction += f"  ок / ok / да / 👍 / 🔥 / класс / хорошо / вперед\n\n"
            instruction += f"<i>Бот автоматически опубликует пост в соответствующий канал.</i>"
            
            try:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=instruction,
                    parse_mode='HTML'
                )
                logger.info(f"📨 Инструкция отправлена администратору")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки инструкции: {e}")
        
        return success_count

    def publish_to_channel(self, text, image_url, channel):
        """Публикует пост в канал"""
        try:
            logger.info(f"📤 Публикую пост в канал {channel}")
            
            # Пробуем отправить с картинкой
            try:
                if image_url and image_url.startswith('http'):
                    self.bot.send_photo(
                        chat_id=channel,
                        photo=image_url,
                        caption=text,
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Пост опубликован в {channel} (с картинкой)")
                    return True
            except Exception as photo_error:
                logger.warning(f"⚠️ Не удалось отправить с картинкой: {photo_error}")
            
            # Если не получилось с картинкой, отправляем текстовый пост
            self.bot.send_message(
                chat_id=channel,
                text=text,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            
            logger.info(f"✅ Пост опубликован в {channel} (текстовый)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в канал {channel}: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_style, is_test=False, force_send=False):
        """Генерирует и отправляет посты"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_style['name']}")
            logger.info(f"🎨 Стиль: {slot_style['style']}")
            logger.info(f"📏 Лимиты: Telegram {slot_style['tg_chars'][0]}-{slot_style['tg_chars'][1]}, Дзен {slot_style['zen_chars'][0]}-{slot_style['zen_chars'][1]}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format(slot_style)
            self.current_style = slot_style
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            logger.info("🖼️ Подбираем картинку...")
            image_url, image_description = self.get_post_image_and_description(theme)
            
            logger.info("\n📝 СОЗДАНИЕ МАСТЕР-ПРОМПТА")
            master_prompt = self.create_master_prompt(theme, slot_style, text_format, image_description)
            
            logger.info("\n🤖 ГЕНЕРАЦИЯ ОБОИХ ПОСТОВ ЧЕРЕЗ GEMINI API")
            tg_text, zen_text = self.generate_with_retry(master_prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=3)
            
            if not tg_text or not zen_text:
                logger.error("❌ Критическая ошибка: не удалось получить тексты постов")
                return False
            
            tg_formatted = self.format_telegram_text(tg_text, slot_style)
            zen_formatted = self.format_zen_text(zen_text, slot_style)
            
            if not tg_formatted or not zen_formatted:
                logger.error("❌ Один из текстов не прошел проверку формата")
                return False
            
            tg_length = len(tg_formatted)
            zen_length = len(zen_formatted)
            
            logger.info(f"\n🔴 ФИНАЛЬНАЯ ПРОВЕРКА:")
            logger.info(f"   Telegram (с эмодзи): {tg_length} символов ({tg_min}-{tg_max})")
            logger.info(f"   Дзен (без эмодзи): {zen_length} символов ({zen_min}-{zen_max})")
            
            # Разрешаем отклонения для аварийных постов
            if tg_length < 300 or zen_length < 400:
                logger.error("❌ Тексты слишком короткие")
                return False
            
            if not is_test:
                logger.info("📤 ОТПРАВЛЯЮ ПОСТЫ АДМИНИСТРАТОРУ НА МОДЕРАЦИЮ")
                success_count = self.send_to_admin_for_moderation(slot_time, tg_formatted, zen_formatted, image_url, theme)
            else:
                logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ - публикация пропущена")
                success_count = 1
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                logger.info(f"📝 Информация сохранена в историю")
            
            if success_count >= 1:
                logger.info(f"\n🎉 УСПЕХ! Отправлено постов на модерацию: {success_count}/2")
                logger.info(f"   🕒 Время: {slot_time} МСК")
                logger.info(f"   🎨 Стиль: {slot_style['style']}")
                logger.info(f"   🎯 Тема: {theme} (ротация активна)")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Telegram (с эмодзи): {tg_length} символов → {MAIN_CHANNEL}")
                logger.info(f"   📏 Дзен (без эмодзи): {zen_length} символов → {ZEN_CHANNEL}")
                logger.info(f"   🤖 Модель: {self.current_model}")
                logger.info(f"   🖼️ Картинка: {image_description[:80]}...")
                return True
            else:
                logger.error(f"❌ Не удалось отправить ни одного поста на модерацию")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка в create_and_send_posts: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        print(f"\n🔄 Запуск в режиме once. Время МСК: {current_time}")
        
        # Запускаем polling в отдельном потоке
        polling_thread = threading.Thread(target=self.start_polling_thread)
        polling_thread.daemon = True
        polling_thread.start()
        
        # Ждем пока polling запустится
        time.sleep(3)
        
        print("✅ Обработчик ответов администратора запущен")
        print("🤖 Бот готов принимать ваши ответы 'ок' на посты")
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_style = self.time_styles[slot_time]
        print(f"📅 Найден слот для отправки: {slot_time} - {slot_style['name']}")
        print(f"🎨 Стиль времени: {slot_style['style']}")
        print(f"📏 Лимиты: Telegram {slot_style['tg_chars'][0]}-{slot_style['tg_chars'][1]} символов (с эмодзи)")
        print(f"📏 Лимиты: Дзен {slot_style['zen_chars'][0]}-{slot_style['zen_chars'][1]} символов (без эмодзи)")
        print(f"🤖 Используемая модель: {self.current_model}")
        print(f"🎯 Система ротации тем: одинаковые темы не будут идти подряд")
        print(f"🔄 Умный выбор формата в зависимости от времени суток")
        print(f"📨 Режим: отправка в личный чат → модерация → публикация в 2 канала")
        print(f"📢 Каналы: {MAIN_CHANNEL} (с эмодзи) и {ZEN_CHANNEL} (без эмодзи)")
        
        success = self.create_and_send_posts(slot_time, slot_style, is_test=False)
        
        if success:
            print(f"\n✅ Посты отправлены администратору на модерацию в {slot_time} МСК")
            print(f"👨‍💼 Проверьте ваш личный чат с ботом")
            print(f"📱 Telegram пост (с эмодзи) → будет в {MAIN_CHANNEL}")
            print(f"📝 Дзен пост (без эмодзи) → будет в {ZEN_CHANNEL}")
            print(f"🤖 Ответьте 'ок' на каждый пост для публикации")
            print(f"\n⏰ Бот ожидает ваши ответы в течение 15 минут...")
            
            # Ждем 15 минут (900 секунд) для ответа администратора
            wait_time = 900  # 15 минут в секундах
            check_interval = 10  # Проверяем каждые 10 секунд
            
            for i in range(wait_time // check_interval):
                # Проверяем, опубликованы ли уже оба поста
                if self.published_telegram and self.published_zen:
                    print("✅ Оба поста опубликованы!")
                    break
                
                # Показываем прогресс
                if i % 6 == 0:  # Каждую минуту
                    minutes_left = (wait_time - (i * check_interval)) // 60
                    print(f"⏳ Ожидание... осталось {minutes_left} минут")
                
                time.sleep(check_interval)
            
            # Итоговый отчет
            print("\n📊 ИТОГ МОДЕРАЦИИ:")
            if self.published_telegram:
                print(f"   ✅ Telegram пост опубликован в {MAIN_CHANNEL}")
            else:
                print(f"   ❌ Telegram пост НЕ опубликован (не получено одобрение)")
            
            if self.published_zen:
                print(f"   ✅ Дзен пост опубликован в {ZEN_CHANNEL}")
            else:
                print(f"   ❌ Дзен пост НЕ опубликован (не получено одобрение)")
            
        else:
            print(f"❌ Ошибка отправки постов на модерацию")
        
        return success

    def run_test_mode(self):
        """Тестовый режим"""
        print("\n" + "=" * 80)
        print("🧪 ТЕСТОВЫЙ РЕЖИМ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Текущее время МСК: {now.strftime('%H:%M:%S')}")
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_style = self.time_styles[slot_time]
        print(f"📝 Выбран слот: {slot_time} - {slot_style['name']}")
        
        success = self.create_and_send_posts(slot_time, slot_style, is_test=True)
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ТЕСТ ПРОЙДЕН! Текст соответствует лимитам.")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН (текст не соответствует лимитам)")
        print("=" * 80)
        
        return success


def main():
    """Главная функция запуска"""
    
    parser = argparse.ArgumentParser(description='Телеграм бот для автоматической публикации постов')
    parser.add_argument('--test', '-t', action='store_true', help='Тестовый режим')
    parser.add_argument('--once', '-o', action='store_true', help='Однократный запуск (для GitHub Actions)')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕЛЕГРАМ БОТА")
    print("=" * 80)
    
    bot = TelegramBot()
    
    if args.once:
        print("📝 РЕЖИМ: Однократный запуск (GitHub Actions)")
        bot.run_once_mode()
    elif args.test:
        print("📝 РЕЖИМ: Тестирование")
        bot.run_test_mode()
    else:
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("python github_bot.py --once   # Для GitHub Actions")
        print("python github_bot.py --test   # Тестирование")
        print(f"🤖 Используемая модель: {GEMINI_MODEL}")
        print("\nДЛЯ GITHUB ACTIONS: python github_bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
