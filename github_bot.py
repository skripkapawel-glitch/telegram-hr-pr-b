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

# Используем доступные модели Gemini в порядке приоритета
GEMINI_MODELS = [
    "gemini-1.5-flash-latest",  # Наиболее стабильная и доступная
    "gemini-1.5-pro-latest",    # Вторая по доступности
    "gemini-2.5-flash-preview-04-17",  # Может быть недоступна
    "gemini-2.5-pro-exp-03-25",  # Может быть недоступна
    "gemma-3-27b-it"            # Fallback модель
]

# Текущая модель
current_model_index = 0

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
print(f"✅ BOT_TOKEN: Установен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"✅ ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
print(f"🤖 Доступные модели: {', '.join(GEMINI_MODELS)}")
print(f"📢 Основной канал (с эмодзи): {MAIN_CHANNEL}")
print(f"📢 Дзен канал (без эмодзи): {ZEN_CHANNEL}")
print(f"📋 Режим: 📤 ЛИЧНЫЙ ЧАТ → МОДЕРАЦИЯ → ПУБЛИКАЦИЯ")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневный пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)


class PostStatus:
    """Статусы постов"""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    PUBLISHED = "published"
    REJECTED = "rejected"


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
        self.pending_posts = {}
        
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
        
        # Список одобрительных слов и эмодзи
        self.approval_words = [
            'ок', 'ok', 'окей', 'океи', 'океюшки', 'да', 'yes', 'yep', 
            'давай', 'го', 'публиковать', 'публикуй', 'согласен', 
            'согласна', 'согласны', 'хорошо', 'отлично', 'прекрасно', 
            'замечательно', 'супер', 'класс', 'круто', 'огонь', 'шикарно',
            'вперед', 'вперёд', 'пошел', 'поехали', '+', '✅', '👍', '👌', 
            '🔥', '🎯', '💯', '🚀', '🙆‍♂️', '🙆‍♀️', '🙆', '👏', '👊', '🤝',
            'принято', 'подтверждаю', 'одобряю', 'ладно', 'лады', 'fire'
        ]
        
        # Список слов для отклонения поста
        self.rejection_words = [
            'нет', 'no', 'не надо', 'не нужно', 'не публикуй', 'отмена',
            'отмени', 'стоп', 'stop', 'отказ', 'не согласен', 'не согласна',
            'не согласны', 'не одобряю', 'не публиковать', 'не отправляй',
            'отклонить', 'отклоняю', 'не подходит', 'не нравится',
            '👎', '❌', '🚫', '⛔', '🙅', '🙅‍♂️', '🙅‍♀️', '🙅🏻', '🙅🏻‍♂️', '🙅🏻‍♀️'
        ]
        
        # Дополнительные эмодзи для Telegram постов
        self.additional_emojis = {
            "утренний": ["☀️", "🌄", "⏰", "💪", "🚀", "💡", "🎯", "✨", "🌟", "⚡"],
            "дневной": ["📊", "📈", "🔍", "💼", "🧠", "🤔", "💭", "🎓", "📚", "🔬"],
            "вечерний": ["🌆", "🌃", "🕯️", "🤫", "🧘", "💤", "🌟", "🌠", "🌌", "🛋️"]
        }
        
        self.current_theme = None
        self.current_format = None
        self.current_style = None
        self.current_model_index = 0  # Начинаем с первой модели
        
        # Флаг для отслеживания запуска polling
        self.polling_started = False

    def get_current_model(self):
        """Возвращает текущую модель"""
        return GEMINI_MODELS[self.current_model_index]

    def switch_to_next_model(self):
        """Переключается на следующую модель"""
        if self.current_model_index < len(GEMINI_MODELS) - 1:
            self.current_model_index += 1
            logger.info(f"🔄 Переключаемся на модель: {self.get_current_model()}")
            return True
        else:
            logger.error("❌ Все модели исчерпаны")
            return False

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

    def is_approval(self, text):
        """Проверяет, является ли текст одобрением"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Проверка по полному совпадению
        if text_lower in self.approval_words:
            return True
        
        # Проверка по частичному совпадению
        for word in self.approval_words:
            if word in text_lower:
                return True
        
        # Специальные случаи для эмодзи
        approval_emojis = ['✅', '👍', '👌', '🔥', '🎯', '💯', '🚀', '🙆‍♂️', '🙆‍♀️', '🙆', '👏', '👊', '🤝']
        for emoji in approval_emojis:
            if emoji in text:
                return True
        
        if any(word in text_lower for word in ['огонь', 'огонь!', 'огонь🔥', 'fire', 'fire!', '🔥']):
            return True
        
        return False

    def is_rejection(self, text):
        """Проверяет, является ли текст отклонением"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Проверка по полному совпадению
        if text_lower in self.rejection_words:
            return True
        
        # Проверка по частичному совпадению
        for word in self.rejection_words:
            if word in text_lower:
                return True
        
        # Специальные случаи для эмодзи
        rejection_emojis = ['👎', '❌', '🚫', '⛔', '🙅', '🙅‍♂️', '🙅‍♀️']
        for emoji in rejection_emojis:
            if emoji in text:
                return True
        
        return False

    def is_edit_request(self, text):
        """Определяет, является ли сообщение запросом на редактирование"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Ключевые слова для запроса редактирования
        edit_keywords = [
            'переделай', 'исправь', 'измени', 'правь', 'редактируй',
            'перепиши', 'переработай', 'доработай', 'пересмотри',
            'правки', 'исправления', 'редактирование',
            'замени фото', 'другое фото', 'новое фото', 'смени картинку',
            'переделать', 'исправить', 'изменить', 'редактировать',
            'нужны правки', 'сделай по-другому', 'перефразируй',
            'перегенерируй', 'сгенерируй заново', 'обнови',
            'другой текст', 'новый текст', 'измени текст',
            'перепиши текст', 'переделай пост'
        ]
        
        for keyword in edit_keywords:
            if keyword in text_lower:
                return True
        
        if ('перепиши' in text_lower or 'переделай' in text_lower) and \
           ('текст' in text_lower or 'пост' in text_lower):
            return True
        
        return False

    def process_admin_reply(self, message):
        """Обрабатывает ответы администратора"""
        try:
            # Проверяем, что сообщение от администратора
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Сообщение не от администратора: {message.chat.id}")
                return
            
            # Проверяем, что это ответ на сообщение (reply)
            if not message.reply_to_message:
                logger.debug("Сообщение не является ответом на другое сообщение")
                return
            
            # Получаем ID сообщения, на которое ответили
            original_message_id = message.reply_to_message.message_id
            
            # Проверяем, есть ли такой пост в ожидающих
            if original_message_id not in self.pending_posts:
                logger.warning(f"⚠️ Ответ на несуществующий пост: {original_message_id}")
                return
            
            post_data = self.pending_posts[original_message_id]
            reply_text = (message.text or "").strip()
            
            logger.info(f"📩 Ответ администратора на пост {original_message_id}: '{reply_text}'")
            
            # Проверяем, не истекло ли время редактирования
            if 'edit_timeout' in post_data:
                timeout = post_data['edit_timeout']
                if datetime.now() > timeout:
                    logger.info(f"⏰ Время для правок истекло для поста {original_message_id}")
                    self.bot.reply_to(message, "⏰ Время для внесения правок истекло. Пост автоматически отклонен.")
                    self.handle_rejection(original_message_id, post_data, message, reason="Время истекло")
                    return
            
            # Обработка запроса на редактирование
            if self.is_edit_request(reply_text):
                logger.info(f"✏️ Получен запрос на редактирование для поста {original_message_id}")
                logger.info(f"📝 Текст запроса: '{reply_text}'")
                self.handle_edit_request(original_message_id, post_data, reply_text, message)
                return
            
            # Обработка отклонения
            if self.is_rejection(reply_text):
                logger.info(f"❌ Получено отклонение для поста {original_message_id}")
                logger.info(f"❌ Текст отклонения: '{reply_text}'")
                self.handle_rejection(original_message_id, post_data, message, reason=reply_text)
                return
            
            # Обработка одобрения
            if self.is_approval(reply_text):
                logger.info(f"✅ Получено одобрение для поста {original_message_id}")
                logger.info(f"✅ Текст одобрения: '{reply_text}'")
                self.handle_approval(original_message_id, post_data, message)
                return
            
            # Если не распознали команду, отправляем подсказку
            logger.warning(f"❓ Не распознана команда: '{reply_text}'")
            self.bot.reply_to(
                message,
                "❓ Не понял команду. Используйте:\n"
                "• 'ок', '👍', '🔥', '✅' или подобное - для публикации\n"
                "• 'нет', '❌', '👎', 'отмена' - для отклонения\n"
                "• 'переделай', 'перепиши текст', 'правки', 'замени фото' - для редактирования\n"
                "⏰ Время на решение: 15 минут"
            )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                self.bot.reply_to(message, f"❌ Ошибка: {str(e)[:100]}")
            except:
                pass

    def handle_rejection(self, message_id, post_data, original_message, reason=""):
        """Обрабатывает отклонение поста"""
        try:
            post_type = post_data.get('type')
            theme = post_data.get('theme', '')
            slot_style = post_data.get('slot_style', {})
            
            # Обновляем статус
            post_data['status'] = PostStatus.REJECTED
            post_data['rejected_at'] = datetime.now().isoformat()
            post_data['rejection_reason'] = reason[:100] if reason else "Отклонено администратором"
            
            # Уведомляем администратора
            if "Время истекло" in reason:
                rejection_msg = "⏰ Время на модерацию истекло. Пост отклонен."
            else:
                rejection_msg = f"❌ Пост отклонен.\n📝 Причина: {reason if reason else 'Решение администратора'}"
            
            if original_message:
                self.bot.reply_to(original_message, rejection_msg)
            
            logger.info(f"❌ Пост типа '{post_type}' отклонен. Причина: {reason}")
            
            # Удаляем пост из pending_posts
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                logger.info(f"🗑️ Пост {message_id} удален из ожидания")
            
            # Обновляем историю
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            slot_time = post_data.get('slot_time', '')
            
            if slot_time:
                if "rejected_slots" not in self.post_history:
                    self.post_history["rejected_slots"] = {}
                
                if today not in self.post_history["rejected_slots"]:
                    self.post_history["rejected_slots"][today] = []
                
                self.post_history["rejected_slots"][today].append({
                    "time": slot_time,
                    "type": post_type,
                    "theme": theme,
                    "reason": reason[:100] if reason else "Отклонено",
                    "rejected_at": datetime.now().isoformat()
                })
                self.save_history()
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки отклонения: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_edit_request(self, message_id, post_data, edit_request, original_message):
        """Обрабатывает запрос на редактирование"""
        try:
            post_type = post_data.get('type')
            original_text = post_data.get('text', '')
            original_image_url = post_data.get('image_url', '')
            
            # Сохраняем оригинальные данные
            if 'original_data' not in post_data:
                post_data['original_data'] = {
                    'text': original_text,
                    'image_url': original_image_url,
                    'theme': post_data.get('theme', '')
                }
            
            # Устанавливаем статус "требует правок"
            post_data['status'] = PostStatus.NEEDS_EDIT
            
            # Устанавливаем таймаут для редактирования (15 минут)
            edit_timeout = datetime.now() + timedelta(minutes=15)
            post_data['edit_timeout'] = edit_timeout
            
            # Уведомляем администратора
            self.bot.reply_to(
                original_message,
                f"✏️ Запрос на редактирование принят.\n"
                f"⏰ Время на внесение изменений: до {edit_timeout.strftime('%H:%M:%S')}\n"
                f"🔄 Генерирую новый вариант..."
            )
            
            # Определяем, что нужно редактировать
            edit_lower = edit_request.lower()
            
            # Ключевые слова для редактирования текста
            text_edit_keywords = [
                'переделай', 'исправь', 'измени', 'правь', 'редактируй',
                'перепиши', 'переработай', 'доработай', 'пересмотри',
                'переделать', 'исправить', 'изменить', 'редактировать',
                'нужны правки', 'сделай по-другому', 'перефразируй',
                'перегенерируй', 'сгенерируй заново', 'обнови',
                'другой текст', 'новый текст', 'измени текст',
                'перепиши текст', 'переделай пост'
            ]
            
            # Ключевые слова для замены фото
            photo_edit_keywords = ['фото', 'картинк', 'изображен', 'картинку', 'изображение']
            
            # Генерация нового текста
            if any(word in edit_lower for word in text_edit_keywords):
                logger.info(f"🔄 Перегенерация текста для поста {message_id}")
                new_text = self.regenerate_post_text(
                    post_data.get('theme', ''),
                    post_data.get('slot_style', {}),
                    original_text,
                    edit_request
                )
                
                if new_text:
                    new_text = self.ensure_hashtags_at_end(new_text, post_data.get('theme', ''))
                    post_data['text'] = new_text
                    new_message_id = self.update_pending_post(message_id, post_data)
                    
                    if new_message_id:
                        self.bot.reply_to(
                            original_message,
                            f"✅ Текст переработан. Проверьте новый вариант выше.\n"
                            f"⏰ Время на правки истекает: {edit_timeout.strftime('%H:%M')}"
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "❌ Не удалось обновить пост с новым текстом."
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "❌ Не удалось перегенерировать текст. Попробуйте другой запрос."
                    )
            
            # Замена фото
            elif any(word in edit_lower for word in photo_edit_keywords):
                logger.info(f"🔄 Замена фото для поста {message_id}")
                new_image_url, new_description = self.get_new_image(
                    post_data.get('theme', ''),
                    edit_request
                )
                
                if new_image_url:
                    post_data['image_url'] = new_image_url
                    new_message_id = self.update_pending_post(message_id, post_data)
                    
                    if new_message_id:
                        self.bot.reply_to(
                            original_message,
                            f"✅ Фото заменено. Проверьте новый вариант выше.\n"
                            f"⏰ Время на правки истекает: {edit_timeout.strftime('%H:%M')}"
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "❌ Не удалось обновить пост с новой фотографией."
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "❌ Не удалось найти новое фото. Попробуйте другой запрос."
                    )
            
            # Общая перегенерация
            else:
                logger.info(f"🔄 Общая перегенерация поста {message_id}")
                new_text = self.regenerate_post_text(
                    post_data.get('theme', ''),
                    post_data.get('slot_style', {}),
                    original_text,
                    edit_request
                )
                
                if new_text:
                    new_text = self.ensure_hashtags_at_end(new_text, post_data.get('theme', ''))
                    post_data['text'] = new_text
                    new_message_id = self.update_pending_post(message_id, post_data)
                    
                    if new_message_id:
                        self.bot.reply_to(
                            original_message,
                            f"✅ Пост переработан. Проверьте новый вариант выше.\n"
                            f"⏰ Время на правки истекает: {edit_timeout.strftime('%H:%M')}"
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "❌ Не удалось обновить пост."
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "❌ Не удалось внести изменения. Попробуйте другой запрос."
                    )
            
            # Обновляем данные в словаре
            self.pending_posts[message_id] = post_data
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на редактирование: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.reply_to(original_message, f"❌ Ошибка при обработке запроса: {str(e)[:100]}")

    def handle_approval(self, message_id, post_data, original_message):
        """Обрабатывает одобрение поста"""
        try:
            post_type = post_data.get('type')
            post_text = post_data.get('text', '')
            image_url = post_data.get('image_url', '')
            channel = post_data.get('channel', '')
            
            logger.info(f"✅ Одобрение поста типа '{post_type}' для канала {channel}")
            logger.info(f"📏 Длина текста: {len(post_text)} символов")
            
            # Публикуем пост в канал
            success = self.publish_to_channel(post_text, image_url, channel)
            
            if success:
                post_data['status'] = PostStatus.PUBLISHED
                post_data['published_at'] = datetime.now().isoformat()
                
                if post_type == 'telegram':
                    self.published_telegram = True
                    logger.info("✅ Telegram пост опубликован в канал!")
                    self.bot.reply_to(original_message, "✅ Telegram пост опубликован в канал!")
                elif post_type == 'zen':
                    self.published_zen = True
                    logger.info("✅ Дзен пост опубликован в канал!")
                    self.bot.reply_to(original_message, "✅ Дзен пост опубликован в канал!")
                
                self.pending_posts[message_id] = post_data
                
            else:
                logger.error(f"❌ Ошибка публикации поста типа '{post_type}' в канал {channel}")
                self.bot.reply_to(original_message, f"❌ Ошибка публикации поста в {channel}")
        
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.reply_to(original_message, f"❌ Ошибка публикации: {str(e)[:100]}")

    def regenerate_post_text(self, theme, slot_style, original_text, edit_request):
        """Перегенерирует текст поста с учетом запроса на редактирование"""
        try:
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            
            # Создаем промпт для перегенерации с акцентом на хештеги
            prompt = f"""🔄 ПЕРЕГЕНЕРАЦИЯ ПОСТА С УЧЕТОМ ПРАВОК

Оригинальный текст:
{original_text}

Запрос на редактирование:
{edit_request}

Тема: {theme}

ВАЖНО:
1. Хештеги (3-5 штук) должны быть ТОЛЬКО В КОНЦЕ поста, отдельной строкой!
2. Используй эти хештеги: {hashtags_str}
3. Хештеги обязательны! Без хештегов пост не будет принят.

Правила опыта:
При упоминании профессионального опыта используй нейтральную форму:
• «по опыту практиков сферы»
• «как отмечают специалисты»
• «в профессиональной среде считается»
• «эксперты с большим стажем отмечают»

Сгенерируй улучшенный вариант поста. В конце поста ОБЯЗАТЕЛЬНО добавь хештеги:
{hashtags_str}"""

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.get_current_model()}:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": 1500,
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            response = session.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    new_text = result['candidates'][0]['content']['parts'][0]['text']
                    new_text = self.clean_generated_text(new_text)
                    new_text = self.ensure_hashtags_at_end(new_text, theme)
                    return new_text
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка перегенерации текста: {e}")
            return None

    def ensure_hashtags_at_end(self, text, theme):
        """Убеждается, что хештеги находятся в конце поста"""
        if not text:
            return text
        
        # Удаляем возможные хештеги из середины текста
        lines = text.split('\n')
        clean_lines = []
        hashtag_lines = []
        
        for line in lines:
            if '#' in line:
                # Проверяем, является ли строка только хештегами
                words = line.strip().split()
                all_hashtags = all(word.startswith('#') for word in words if word.strip())
                if all_hashtags and len(words) > 0:
                    hashtag_lines.append(line)
                    continue
            clean_lines.append(line)
        
        # Собираем текст без хештегов
        clean_text = '\n'.join(clean_lines).strip()
        
        # Получаем хештеги для темы
        hashtags_to_use = self.get_relevant_hashtags(theme, random.randint(3, 5))
        
        # Добавляем хештеги в конец
        hashtags_str = ' '.join(hashtags_to_use)
        final_text = f"{clean_text}\n\n{hashtags_str}"
        
        return final_text.strip()

    def get_new_image(self, theme, edit_request):
        """Находит новое изображение по запросу"""
        try:
            edit_lower = edit_request.lower()
            
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "building"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social"]
            }
            
            query = None
            specific_keywords = ["город", "природ", "офис", "дом", "стройк", "люди", "технологи", "архитектур", "дизайн"]
            for keyword in specific_keywords:
                if keyword in edit_lower:
                    query = keyword
                    break
            
            if not query:
                queries = theme_queries.get(theme, ["business", "work", "success"])
                query = random.choice(queries)
            
            logger.info(f"🔍 Ищем новое фото по запросу: '{query}'")
            
            # Ищем в Pexels
            url = "https://api.pexels.com/v1/search"
            params = {
                "query": query,
                "per_page": 15,
                "orientation": "landscape",
                "size": "large"
            }
            
            headers = {"Authorization": PEXELS_API_KEY}
            response = session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    used_images = self.image_history.get("used_images", [])
                    available_photos = [p for p in photos if p.get("src", {}).get("large") not in used_images]
                    
                    if not available_photos:
                        available_photos = photos
                    
                    photo = random.choice(available_photos)
                    image_url = photo.get("src", {}).get("large", "")
                    photographer = photo.get("photographer", "")
                    alt_text = photo.get("alt", "")
                    
                    if image_url:
                        description = f"{alt_text if alt_text else 'Новое фото'} от {photographer if photographer else 'фотографа'}"
                        return image_url, description
            
            # Если Pexels не сработал, пробуем Unsplash
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                description = f"Новое фото на тему '{query}'"
                return image_url, description
            
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска нового изображения: {e}")
            return None, None

    def update_pending_post(self, message_id, post_data):
        """Обновляет пост с новыми данными"""
        try:
            post_text = post_data.get('text', '')
            image_url = post_data.get('image_url', '')
            
            # Удаляем старый пост
            try:
                self.bot.delete_message(ADMIN_CHAT_ID, message_id)
                logger.info(f"🗑️ Удален старый пост с ID: {message_id}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить старый пост: {e}")
            
            # Отправляем обновленный пост
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=post_text[:1024],
                    parse_mode='HTML'
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=post_text,
                    parse_mode='HTML'
                )
            
            # Обновляем ID в словаре
            old_data = self.pending_posts.pop(message_id, {})
            old_data['message_id'] = sent_message.message_id
            
            self.pending_posts[sent_message.message_id] = old_data
            
            logger.info(f"🔄 Пост обновлен, новый ID: {sent_message.message_id}")
            
            return sent_message.message_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления поста: {e}")
            return None

    def start_polling_thread(self):
        """Запускает polling в отдельном потоке"""
        try:
            logger.info("🔄 Запускаю polling в отдельном потоке...")
            self.remove_webhook()
            self.setup_message_handler()
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
            "theme_rotation": [],
            "rejected_slots": {}
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
            if image_url and image_url not in self.image_history.get("used_images", []):
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

    def get_relevant_hashtags(self, theme, count=None):
        """Возвращает релевантные хэштеги для темы"""
        try:
            if count is None:
                count = random.randint(3, 5)
            
            hashtags = self.hashtags_by_theme.get(theme, [])
            if len(hashtags) >= count:
                return random.sample(hashtags, count)
            return hashtags[:count] if hashtags else ["#бизнес", "#советы", "#развитие"]
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения хэштеги: {e}")
            return ["#бизнес", "#советы", "#развитие"]

    def get_soft_final(self):
        """Возвращает случайный мягкий финал"""
        return random.choice(self.soft_finals)

    def enhance_telegram_with_emojis(self, text, post_type):
        """Добавляет дополнительные эмодзи в Telegram пост"""
        if not text or post_type != 'telegram':
            return text
        
        try:
            post_type_key = ""
            if "утренний" in self.current_style.get('name', '').lower():
                post_type_key = "утренний"
            elif "дневной" in self.current_style.get('name', '').lower():
                post_type_key = "дневной"
            elif "вечерний" in self.current_style.get('name', '').lower():
                post_type_key = "вечерний"
            
            if not post_type_key:
                return text
            
            additional_emojis = self.additional_emojis.get(post_type_key, [])
            
            if not additional_emojis:
                return text
            
            lines = text.split('\n')
            enhanced_lines = []
            
            for i, line in enumerate(lines):
                if i == 0:
                    enhanced_lines.append(line)
                elif i > 0 and i < len(lines) - 2:
                    line = line.strip()
                    if line and len(line) > 20:
                        if random.random() < 0.4:
                            emoji = random.choice(additional_emojis)
                            line = f"{emoji} {line}"
                    enhanced_lines.append(line)
                else:
                    enhanced_lines.append(line)
            
            return '\n'.join(enhanced_lines)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка добавления эмодзи: {e}")
            return text

    def create_master_prompt(self, theme, slot_style, text_format, image_description):
        """Создает промпт для генерации обоих постов"""
        try:
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            post_type_key = ""
            if "утренний" in slot_style.get('name', '').lower():
                post_type_key = "утренний"
            elif "дневной" in slot_style.get('name', '').lower():
                post_type_key = "дневной"
            elif "вечерний" in slot_style.get('name', '').lower():
                post_type_key = "вечерний"
            
            additional_emojis = self.additional_emojis.get(post_type_key, [])
            emojis_examples = " ".join(additional_emojis[:5]) if additional_emojis else "☀️💪🚀"
            
            # УСИЛЕННЫЙ ПРОМПТ с акцентом на хештеги
            prompt = f"""🔥 ГЕНЕРАЦИЯ ДВУХ ПОСТОВ: С ЭМОДЗИ И БЕЗ ЭМОДЗИ

🎯 ТВОЯ РОЛЬ
Ты — топ-специалист с 30+ лет опыта в HR, PR и строительстве.
Ты пишешь живо, глубоко, уверенно и структурно.

🎯 ЗАДАЧА
Сгенерировать ДВА текста по одной теме, но с разной подачей:
1. Telegram пост С ЭМОДЗИ - для основного канала
2. Дзен пост БЕЗ ЭМОДЗИ - для канала Дзен

Тема поста: {theme}

🚨🚨🚨 КРИТИЧЕСКИ ВАЖНО: ХЕШТЕГИ ОБЯЗАТЕЛЬНЫ 🚨🚨🚨
В КОНЦЕ КАЖДОГО ПОСТА ДОЛЖНА БЫТЬ ОТДЕЛЬНАЯ СТРОКА С ХЕШТЕГАМИ!
ИСПОЛЬЗУЙ ЭТИ ХЕШТЕГИ: {hashtags_str}
ХЕШТЕГИ ДОЛЖНЫ БЫТЬ ПОСЛЕ МЯГКОГО ФИНАЛА "{soft_final}"

🔒 СТРОГИЕ ПРАВИЛА
1. Telegram пост ДОЛЖЕН содержать эмодзи
2. Telegram пост должен начинаться с эмодзи {slot_style['emoji']}
3. Telegram пост может содержать дополнительные эмодзи: {emojis_examples}
4. Дзен пост НЕ ДОЛЖЕН содержать эмодзи вообще - удали все эмодзи из Дзен поста
5. Оба текста разные по структуре, но об одном смысле
6. ХЕШТЕГИ (3-5 штук) ДОЛЖНЫ БЫТЬ ТОЛЬКО В КОНЦЕ ПОСТА, ОТДЕЛЬНОЙ СТРОКОЙ! 
7. Формат хештегов: {hashtags_str}
8. Если не будет хештегов - задание провалено!

⚠ ПРАВИЛО ОПЫТА
При упоминании профессионального опыта используй нейтральную форму:
• «по опыту практиков сферы»
• «как отмечают специалисты»
• «в профессиональной среде считается»
• «эксперты с большим стажем отмечают»

🕒 ВРЕМЯ ПУБЛИКАЦИИ
{slot_style['name']} — {slot_style['style']}

✂ ЛИМИТЫ СИМВОЛОВ
Telegram (с эмодзи): {tg_min}–{tg_max} символов
Дзен (без эмодзи): {zen_min}–{zen_max} символов

🧱 СТРУКТУРА TELEGRAM ПОСТА
• Начинается с эмодзи {slot_style['emoji']}
• 1–3 абзаца с глубиной
• Используй дополнительные эмодзи умеренно
• Мини-вывод
• Мягкий финал: {soft_final}
• Хэштеги (ТОЛЬКО В КОНЦЕ): {hashtags_str}

🧱 СТРУКТУРА ДЗЕН ПОСТА
• Заголовок БЕЗ эмодзи
• 2–4 раскрывающих абзаца  
• Мини-вывод
• Мягкий финал: {soft_final}
• Хэштеги (ТОЛЬКО В КОНЦЕ): {hashtags_str}
• НИКАКИХ ЭМОДЗИ В ДЗЕН ПОСТЕ!

💡 ФОРМАТ ПОДАЧИ
{text_format}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ФОРМАТ ОТВЕТА:

TELEGRAM ПОСТ (с эмодзи):
{slot_style['emoji']} [Текст с эмодзи]
[Заканчивается "{soft_final}"]
{hashtags_str}

ДЗЕН ПОСТ (без эмодзи):
[Текст БЕЗ эмодзи]
[Заканчивается "{soft_final}"]
{hashtags_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
НАЧИНАЙ ГЕНЕРАЦИЮ:"""

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
                if any(keyword in line.lower() for keyword in ['длина:', 'символов', 'символы:', 'количество символов', 'символа', 'текст содержит']):
                    continue
                
                stripped_line = line.strip()
                if stripped_line.startswith('**') and stripped_line.endswith('**'):
                    cleaned_line = stripped_line[2:-2].strip()
                    cleaned_lines.append(cleaned_line)
                else:
                    cleaned_lines.append(line)
            
            cleaned_text = '\n'.join(cleaned_lines)
            cleaned_text = re.sub(r'━+$', '', cleaned_text, flags=re.MULTILINE)
            cleaned_text = re.sub(r'=+$', '', cleaned_text, flags=re.MULTILINE)
            
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
        
        cut_point = text[:target_max].rfind('.')
        if cut_point > target_max * 0.8:
            text = text[:cut_point + 1].strip()
        else:
            cut_point = text[:target_max].rfind('\n')
            if cut_point > target_max * 0.8:
                text = text[:cut_point].strip()
            else:
                cut_point = text[:target_max].rfind(' ')
                if cut_point > target_max * 0.8:
                    text = text[:cut_point].strip()
                else:
                    text = text[:target_max - 3].strip() + "..."
        
        logger.info(f"⚔️ После сокращения: {len(text)} символов")
        return text

    def parse_generated_texts(self, text, tg_min, tg_max, zen_min, zen_max):
        """Парсит сгенерированные тексты"""
        try:
            # Ищем разделители
            parts = text.split('ДЗЕН ПОСТ')
            if len(parts) < 2:
                parts = text.split('ДЗЕН ПОСТ:')
            
            if len(parts) < 2:
                parts = text.split('ДЗЕН')
            
            if len(parts) < 2:
                lines = text.split('\n')
                tg_lines = []
                zen_lines = []
                found_separator = False
                
                for line in lines:
                    if not found_separator:
                        tg_lines.append(line)
                        if line.strip().upper() in ['ДЗЕН ПОСТ', 'ДЗЕН', 'ZEN', 'ZEN POST']:
                            found_separator = True
                            tg_lines.pop()
                    else:
                        zen_lines.append(line)
                
                tg_text_raw = '\n'.join(tg_lines)
                zen_text_raw = '\n'.join(zen_lines)
            else:
                tg_text_raw = parts[0]
                zen_text_raw = parts[1]
                
                for marker in ['TELEGRAM ПОСТ:', 'TELEGRAM ПОСТ', 'Telegram пост:', 'TELEGRAM:', 'Telegram:']:
                    tg_text_raw = tg_text_raw.replace(marker, '').strip()
                
                for marker in ['ДЗЕН ПОСТ:', 'Дзен пост:', 'ZEN POST:', 'ZEN:']:
                    zen_text_raw = zen_text_raw.replace(marker, '').strip()
            
            tg_text = self.clean_generated_text(tg_text_raw)
            zen_text = self.clean_generated_text(zen_text_raw)
            
            # Удаляем лишние префиксы
            for phrase in ["Telegram пост", "Telegram", "Пост для Telegram", "Для Telegram"]:
                if tg_text.startswith(phrase):
                    tg_text = tg_text[len(phrase):].strip()
            
            for phrase in ["Дзен пост", "Дзен", "Пост для Дзен", "Для Дзен"]:
                if zen_text.startswith(phrase):
                    zen_text = zen_text[len(phrase):].strip()
            
            # Удаляем фразы про длину
            for phrase in ["Дополнительный контент для соответствия длине.", 
                          "Дополнительный контент.", 
                          "Текст для соответствия длине.",
                          "Контент для соответствия лимиту символов."]:
                while phrase in tg_text:
                    tg_text = tg_text.replace(phrase, '').strip()
                while phrase in zen_text:
                    zen_text = zen_text.replace(phrase, '').strip()
            
            # Очищаем от множественных пустых строк
            tg_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', tg_text)
            zen_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', zen_text)
            
            # Проверяем наличие хештегов
            tg_hashtags = re.findall(r'#\w+', tg_text)
            zen_hashtags = re.findall(r'#\w+', zen_text)
            
            # Если хештегов нет, добавляем их принудительно
            if not tg_hashtags:
                logger.warning("⚠️ В Telegram посте нет хештегов! Добавляю принудительно...")
                hashtags = self.get_relevant_hashtags(self.current_theme or "HR и управление персоналом", 3)
                tg_text = f"{tg_text}\n\n{' '.join(hashtags)}"
            
            if not zen_hashtags:
                logger.warning("⚠️ В Дзен посте нет хештеги! Добавляю принудительно...")
                hashtags = self.get_relevant_hashtags(self.current_theme or "HR и управление персоналом", 3)
                zen_text = f"{zen_text}\n\n{' '.join(hashtags)}"
            
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            logger.info(f"📊 Парсинг: Telegram {tg_length} символов, Дзен {zen_length} символов")
            
            # Проверяем наличие хештегов после добавления
            tg_hashtags = re.findall(r'#\w+', tg_text)
            zen_hashtags = re.findall(r'#\w+', zen_text)
            
            if not tg_hashtags:
                logger.warning("⚠️ В Telegram посте все еще нет хештегов после добавления!")
            if not zen_hashtags:
                logger.warning("⚠️ В Дзен посте все еще нет хештеги после добавления!")
            
            if tg_length < tg_min * 0.8 or zen_length < zen_min * 0.8:
                logger.warning(f"⚠️ Текст слишком короткий для перегенерации")
                return None, None
            
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
        for attempt in range(max_attempts):
            current_model = self.get_current_model()
            
            try:
                logger.info(f"🤖 Попытка {attempt+1}/{max_attempts}: генерация обоих постов (модель: {current_model})")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 4000,
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
                        logger.error(f"⚠️ Модель {current_model} не найдена")
                        if self.switch_to_next_model():
                            logger.info(f"🔄 Пробуем следующую модель: {self.get_current_model()}")
                            continue
                        else:
                            logger.error("❌ Все модели исчерпаны")
                            return None, None
                    
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
                
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    tg_final_len = len(tg_text)
                    zen_final_len = len(zen_text)
                    
                    tg_hashtags = re.findall(r'#\w+', tg_text)
                    zen_hashtags = re.findall(r'#\w+', zen_text)
                    
                    if (not tg_hashtags or not zen_hashtags) and attempt < max_attempts - 1:
                        logger.warning(f"⚠️ Отсутствуют хештеги: TG={len(tg_hashtags)}, Дзен={len(zen_hashtags)}")
                        logger.info("🔄 Пробуем снова - хештеги обязательны для обоих постов")
                        time.sleep(2)
                        continue
                    
                    if tg_final_len >= 100 and zen_final_len >= 100:
                        logger.info(f"✅ Посты сгенерированы: TG={tg_final_len}, Дзен={zen_final_len}")
                        logger.info(f"✅ Хештеги: TG={len(tg_hashtags)} шт., Дзен={len(zen_hashtags)} шт.")
                        
                        if tg_min <= tg_final_len <= tg_max and zen_min <= zen_final_len <= zen_max:
                            logger.info(f"✅ Идеально: TG в диапазоне {tg_min}-{tg_max}, Дзен в диапазоне {zen_min}-{zen_max}")
                            return tg_text, zen_text
                        else:
                            if tg_final_len >= tg_min * 0.9 and zen_final_len >= zen_min * 0.9:
                                logger.warning(f"⚠️ Длины близки к диапазону: TG={tg_final_len}, Дзен={zen_final_len}")
                                return tg_text, zen_text
                            else:
                                logger.warning(f"⚠️ Тексты слишком короткие, пробуем снова")
                                if attempt < max_attempts - 1:
                                    time.sleep(2)
                                    continue
                    else:
                        logger.warning(f"⚠️ Тексты слишком короткие: TG={tg_final_len}, Дзен={zen_final_len}")
                        if attempt < max_attempts - 1:
                            time.sleep(2)
                            continue
                
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
        
        logger.error("❌ Все попытки провалились, не удалось сгенерировать посты с хештегами")
        return None, None

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
        
        logger.warning("⚠️ Не удалось найти картинку, будет сгенерирован текстовый пост")
        return None, "Нет картинки - текстовый пост"

    def format_telegram_text(self, text, slot_style):
        """Форматирует Telegram текст (с эмодзи)"""
        if not text:
            return None
        
        text = text.strip()
        text = self.clean_generated_text(text)
        
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        text = self.ensure_hashtags_at_end(text, self.current_theme or "HR и управление персоналом")
        
        hashtags = re.findall(r'#\w+', text)
        if not hashtags:
            logger.warning("⚠️ В Telegram посте после форматирования нет хештегов!")
            text = self.ensure_hashtags_at_end(text, self.current_theme or "HR и управление персоналом")
        
        if not text.startswith(slot_style['emoji']):
            lines = text.split('\n')
            if lines and lines[0].strip():
                lines[0] = f"{slot_style['emoji']} {lines[0]}"
                text = '\n'.join(lines)
        
        text = self.enhance_telegram_with_emojis(text, 'telegram')
        
        tg_min, tg_max = slot_style['tg_chars']
        text_length = len(text)
        
        logger.info(f"📏 Telegram текст (с эмодзи): {text_length} символов ({tg_min}-{tg_max})")
        
        if text_length < tg_min:
            logger.warning(f"⚠️ Telegram текст коротковат: {text_length} < {tg_min}")
        
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
        
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        text = self.ensure_hashtags_at_end(text, self.current_theme or "HR и управление персоналом")
        
        hashtags = re.findall(r'#\w+', text)
        if not hashtags:
            logger.warning("⚠️ В Дзен посте после форматирования нет хештеги!")
            text = self.ensure_hashtags_at_end(text, self.current_theme or "HR и управление персоналом")
        
        text = re.sub(r'[^\w\s#@.,!?;:"\'()\-—–«»]', '', text)
        
        zen_min, zen_max = slot_style['zen_chars']
        text_length = len(text)
        
        logger.info(f"📏 Дзен текст (без эмодзи): {text_length} символов ({zen_min}-{zen_max})")
        
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
        post_ids = []
        
        edit_timeout = datetime.now() + timedelta(minutes=15)
        
        logger.info(f"📨 Отправляем Telegram пост (с эмодзи) администратору")
        
        try:
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=tg_text[:1024],
                    parse_mode='HTML'
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=tg_text,
                    parse_mode='HTML'
                )
            
            post_ids.append(('telegram', sent_message.message_id))
            
            self.pending_posts[sent_message.message_id] = {
                'type': 'telegram',
                'text': tg_text,
                'image_url': image_url or '',
                'channel': MAIN_CHANNEL,
                'status': PostStatus.PENDING,
                'theme': theme,
                'slot_style': self.current_style,
                'slot_time': slot_time,
                'hashtags': re.findall(r'#\w+', tg_text),
                'edit_timeout': edit_timeout,
                'sent_time': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Telegram пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram поста: {e}")
        
        time.sleep(1)
        
        logger.info(f"📨 Отправляем Дзен пост (без эмодзи) администратору")
        
        try:
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=zen_text[:1024],
                    parse_mode='HTML'
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=zen_text,
                    parse_mode='HTML'
                )
            
            post_ids.append(('zen', sent_message.message_id))
            
            self.pending_posts[sent_message.message_id] = {
                'type': 'zen',
                'text': zen_text,
                'image_url': image_url or '',
                'channel': ZEN_CHANNEL,
                'status': PostStatus.PENDING,
                'theme': theme,
                'slot_style': self.current_style,
                'slot_time': slot_time,
                'hashtags': re.findall(r'#\w+', zen_text),
                'edit_timeout': edit_timeout,
                'sent_time': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Дзен пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Дзен поста: {e}")
        
        time.sleep(1)
        self.send_moderation_instructions(post_ids, slot_time, theme, tg_text, zen_text, edit_timeout)
        
        return success_count

    def send_moderation_instructions(self, post_ids, slot_time, theme, tg_text, zen_text, edit_timeout):
        """Отправляет инструкции по модерации"""
        if not post_ids:
            return
        
        timeout_str = edit_timeout.strftime("%H:%M")
        
        # Вычисляем количество хештегов заранее
        tg_hashtags_count = len(re.findall(r'#\w+', tg_text))
        zen_hashtags_count = len(re.findall(r'#\w+', zen_text))
        
        instruction = "✅ <b>ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
        
        instruction += f"📱 <b>1. Telegram пост (с эмодзи)</b>\n"
        instruction += f"   🎯 Канал: {MAIN_CHANNEL}\n"
        instruction += f"   🕒 Время: {slot_time} МСК\n"
        instruction += f"   📚 Тема: {theme}\n"
        instruction += f"   📏 Символов: {len(tg_text)}\n"
        instruction += f"   #️⃣ Хештеги: {tg_hashtags_count} шт.\n"
        instruction += f"   📌 Ответьте «ок» или «🔥» на <b>первый пост</b> выше (с эмодзи 🌅)\n\n"
        
        instruction += f"📝 <b>2. Дзен пост (без эмодзи)</b>\n"
        instruction += f"   🎯 Канал: {ZEN_CHANNEL}\n"
        instruction += f"   🕒 Время: {slot_time} МСК\n"
        instruction += f"   📚 Тема: {theme}\n"
        instruction += f"   📏 Символов: {len(zen_text)}\n"
        instruction += f"   #️⃣ Хештеги: {zen_hashtags_count} шт.\n"
        instruction += f"   📌 Ответьте «ок» или «🔥» на <b>второй пост</b> выше (без эмодзи)\n\n"
        
        instruction += f"🔧 <b>Как опубликовать:</b>\n"
        instruction += f"• Проверьте посты выше\n"
        instruction += f"• Ответьте «ок», «👍», «🔥», «✅» на КАЖДЫЙ пост\n"
        instruction += f"• Бот автоматически опубликует их\n\n"
        
        instruction += f"✏️ <b>Как внести правки:</b>\n"
        instruction += f"• Ответьте «переделай», «перепиши текст», «правки», «замени фото»\n"
        instruction += f"• AI переработает текст или найдет новую картинку\n\n"
        
        instruction += f"❌ <b>Как отменить:</b>\n"
        instruction += f"• Ответьте «нет», «❌», «👎», «отмена»\n"
        instruction += f"• Пост будет отклонен\n\n"
        
        instruction += f"⏰ <b>Время на решение:</b> до {timeout_str} (15 минут)\n"
        instruction += f"📢 После истечения времени посты будут автоматически <b>отклонены</b>"
        
        try:
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=instruction,
                parse_mode='HTML'
            )
            logger.info(f"📨 Инструкция отправлена администратору")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки инструкции: {e}")

    def publish_to_channel(self, text, image_url, channel):
        """Публикует пост в канал"""
        try:
            logger.info(f"📤 Публикую пост в канал {channel}")
            
            if image_url and image_url.startswith('http'):
                try:
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
            
            tg_hashtags = re.findall(r'#\w+', tg_formatted)
            zen_hashtags = re.findall(r'#\w+', zen_formatted)
            
            if not tg_hashtags:
                logger.error("❌ В Telegram посте отсутствуют хештеги")
                return False
            
            if not zen_hashtags:
                logger.error("❌ В Дзен посте отсутствуют хештеги")
                return False
            
            logger.info(f"\n🔴 ФИНАЛЬНАЯ ПРОВЕРКА:")
            logger.info(f"   Telegram (с эмодзи): {tg_length} символов ({tg_min}-{tg_max})")
            logger.info(f"   Дзен (без эмодзи): {zen_length} символов ({zen_min}-{zen_max})")
            logger.info(f"   Хештеги Telegram: {len(tg_hashtags)} шт.")
            logger.info(f"   Хештеги Дзен: {len(zen_hashtags)} шт.")
            
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
                logger.info(f"   🎯 Тема: {theme}")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Telegram (с эмодзи): {tg_length} символов → {MAIN_CHANNEL}")
                logger.info(f"   📏 Дзен (без эмодзи): {zen_length} символов → {ZEN_CHANNEL}")
                logger.info(f"   #️⃣ Хештеги TG: {len(tg_hashtags)} шт.")
                logger.info(f"   #️⃣ Хештеги Дзен: {len(zen_hashtags)} шт.")
                logger.info(f"   🤖 Модель: {self.get_current_model()}")
                logger.info(f"   🖼️ Картинка: {'Есть' if image_url else 'Нет'}")
                logger.info(f"   ⏰ Время на решение: 15 минут")
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
        
        polling_thread = threading.Thread(target=self.start_polling_thread)
        polling_thread.daemon = True
        polling_thread.start()
        
        time.sleep(3)
        
        print("✅ Обработчик ответов администратора запущен")
        print("🤖 Бот готов принимать ваши ответы на посты")
        
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
        print(f"🤖 Доступные модели: {', '.join(GEMINI_MODELS)}")
        print(f"🎯 Текущая модель: {self.get_current_model()}")
        print(f"🎯 Система ротации тем: одинаковые темы не будут идти подряд")
        print(f"🔄 Умный выбор формата в зависимости от времени суток")
        print(f"📨 Режим: отправка в личный чат → модерация → публикация в 2 канала")
        print(f"📢 Каналы: {MAIN_CHANNEL} (с эмодзи) и {ZEN_CHANNEL} (без эмодзи)")
        print(f"⏰ Режим модерации: 15 минут на решение")
        print(f"✅ Варианты подтверждения: 'ок', '👍', '✅', '👌', '🔥', '🙆‍♂️' и другие")
        print(f"❌ Варианты отклонения: 'нет', '❌', '👎', 'отмена', 'не надо'")
        print(f"✏️ Варианты правки: 'переделай', 'перепиши текст', 'правки', 'замени фото'")
        print(f"🚫 После 15 минут посты автоматически отклоняются")
        
        success = self.create_and_send_posts(slot_time, slot_style, is_test=False)
        
        if success:
            print(f"\n✅ Посты отправлены администратору на модерацию в {slot_time} МСК")
            print(f"👨‍💼 Проверьте ваш личный чат с ботом")
            print(f"📱 Telegram пост (с эмодзи) → будет в {MAIN_CHANNEL}")
            print(f"📝 Дзен пост (без эмодзи) → будет в {ZEN_CHANNEL}")
            print(f"✅ Ответьте 'ок', '🔥', '👍' на каждый пост для публикации")
            print(f"❌ Ответьте 'нет', '❌', '👎' для отклонения")
            print(f"✏️ Или 'переделай', 'перепиши текст' для редактирования")
            print(f"\n⏰ Бот ожидает ваше решение в течение 15 минут...")
            print(f"🚫 После 15 минут посты будут автоматически отклонены")
            
            wait_time = 900
            check_interval = 10
            
            for i in range(wait_time // check_interval):
                current_time = datetime.now()
                posts_to_remove = []
                
                for msg_id, post_data in list(self.pending_posts.items()):
                    if post_data.get('status') == PostStatus.PENDING:
                        if 'edit_timeout' in post_data and current_time > post_data['edit_timeout']:
                            print(f"⏰ Время истекло для поста {msg_id}, отклоняю...")
                            self.handle_rejection(msg_id, post_data, None, reason="Время истекло")
                            posts_to_remove.append(msg_id)
                
                for msg_id in posts_to_remove:
                    if msg_id in self.pending_posts:
                        del self.pending_posts[msg_id]
                
                if i % 6 == 0:
                    minutes_left = (wait_time - (i * check_interval)) // 60
                    print(f"⏳ Ожидание... осталось {minutes_left} минут")
                
                time.sleep(check_interval)
            
            print("\n📊 ИТОГ МОДЕРАЦИИ:")
            if self.published_telegram:
                print(f"   ✅ Telegram пост опубликован в {MAIN_CHANNEL}")
            else:
                print(f"   ❌ Telegram пост НЕ опубликован (отклонен или время истекло)")
            
            if self.published_zen:
                print(f"   ✅ Дзен пост опубликован в {ZEN_CHANNEL}")
            else:
                print(f"   ❌ Дзен пост НЕ опубликован (отклонен или время истекло)")
            
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
        print(f"🤖 Доступные модели: {', '.join(GEMINI_MODELS)}")
        print("\nДЛЯ GITHUB ACTIONS: python github_bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
