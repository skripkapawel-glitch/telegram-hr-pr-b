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
from telebot.types import Message, ReactionTypeEmoji, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import hashlib

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ЗАГРУЖАЕМ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ С ПРАВИЛЬНЫМИ ИМЕНАМИ
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL = "@da4a_hr"  # Основной канал (с эмодзи)
ZEN_CHANNEL = "@tehdzenm"   # Дзен канал (без эмодзи)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
GITHUB_TOKEN = os.environ.get("MANAGER_GITHUB_TOKEN")

# Дополнительные переменные из твоих секретов
REPO_NAME = os.environ.get("REPO_NAME", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # На всякий случай, если понадобится

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установен!")
    sys.exit(1)

if not PEXELS_API_KEY:
    logger.error("❌ PEXELS_API_KEY не установен! Обязательно получи ключ на pexels.com/api")
    sys.exit(1)

if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установлен! Укажите ваш chat_id")
    sys.exit(1)

# ТОЛЬКО ТЕ МОДЕЛИ, КОТОРЫЕ РАБОТАЮТ У ВАС
GEMINI_MODELS = [
    "gemma-3-27b-it",  # ✅ Работает у вас
]

logger.info("📤 Режим: отправка постов в личный чат администратора")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})


class PostStatus:
    """Статусы постов"""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    PUBLISHED = "published"
    REJECTED = "rejected"


class GitHubAPIManager:
    """Класс для управления GitHub API"""
    
    def __init__(self):
        self.github_token = GITHUB_TOKEN  # Используем MANAGER_GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        self.repo_owner = os.environ.get("GITHUB_REPOSITORY_OWNer", "")
        self.repo_name = REPO_NAME  # Используем REPO_NAME из секретов
        
    def get_headers(self):
        """Возвращает заголовки для запросов"""
        if not self.github_token:
            logger.warning("⚠️ GitHub токен (MANAGER_GITHUB_TOKEN) не установен")
            return {"Accept": "application/vnd.github.v3+json"}
        
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_file_content(self, file_path):
        """Получает содержимое файла из репозитория"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                return {"error": "Не указаны репозиторий или владелец"}
            
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = requests.get(url, headers=self.get_headers())
            if response.status_code == 200:
                content = response.json()
                if content.get("encoding") == "base64":
                    import base64
                    return base64.b64decode(content["content"]).decode('utf-8')
            return None
        except Exception as e:
            return None
    
    def edit_file(self, file_path, new_content, commit_message):
        """Редактирует файл в репозитории"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                return {"error": "Не указаны репозиторий или владелец"}
            
            # Сначала получаем текущий файл
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code != 200:
                return {"error": "Файл не найден"}
            
            current_file = response.json()
            sha = current_file["sha"]
            
            import base64
            encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
            
            data = {
                "message": commit_message,
                "content": encoded_content,
                "sha": sha
            }
            
            response = requests.put(url, headers=self.get_headers(), json=data)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_status(self):
        """Получает статус репозитория и workflow"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                return {"error": "Не указаны репозиторий или владелец"}
            
            status_info = {}
            
            # Получаем информацию о репозитории
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
            response = requests.get(url, headers=self.get_headers())
            if response.status_code == 200:
                repo_info = response.json()
                status_info["repo"] = {
                    "name": repo_info["name"],
                    "private": repo_info["private"],
                    "updated_at": repo_info["updated_at"],
                    "size": repo_info["size"]
                }
            
            # Получаем последние workflow runs
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/runs"
            response = requests.get(url, headers=self.get_headers())
            if response.status_code == 200:
                runs = response.json()
                status_info["workflow_runs"] = runs.get("workflow_runs", [])[:5]
            
            return status_info
        except Exception as e:
            return {"error": str(e)}


class TelegramBot:
    def __init__(self, force_generate=False):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        self.image_history_file = "image_history.json"
        self.image_history = self.load_image_history()
        
        # Инициализация бота
        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
        
        # Инициализация менеджера GitHub
        self.github_manager = GitHubAPIManager()
        
        # Словарь для хранения постов, ожидающих модерации
        self.pending_posts = {}
        
        # Флаги для отслеживания публикаций
        self.published_telegram = False
        self.published_zen = False
        
        # Трекер для отслеживания опубликованных постов
        self.published_posts_count = 0
        
        # Форматы подачи текста
        self.text_formats = [
            "разбор ошибки",
            "разбор ситуации",
            "микро-исследование",
            "аналитическое наблюдение",
            "причинно-следственные связки",
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
        
        # Хэштеги по темам (по 30+ хештегов для каждой темы)
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#команда", "#лидерство", "#мотивация", "#кадры", "#бизнес", "#управление", "#карьера", "#сотрудники", "#тимбилдинг", "#корпоративнаякультура", "#менеджмент", "#hrтренды"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#брендинг", "#соцсети", "#медиа", "#пиар", "#репутация", "#инфоповод", "#кризисныекоммуникации", "#контентмаркетинг", "#медиарилейшнз", "#стратегия", "#smm", "#prтренды"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", "#ремонтквартир", "#отделка", "#ремонтподключ", "#дизайнинтерьера", "#архитектура", "#стройматериалы", "#строительныенормы", "#умныйдом", "#евроремонт", "#квартира", "#строительныетренды"
            ]
        }
        
        # Стили по времени публикации
        self.time_styles = {
            "11:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "style": "энерго-старт: короткая польза, лёгкая динамика, мотивирующий фокус, ясные выгоды, простое объяснение",
                "allowed_formats": [
                    "структурированные советы", "демонстрация пользы", "объяснение простым языком", "мини-обобщение опыта", "сравнение подходов"
                ],
                "tg_chars": (400, 600),
                "zen_chars": (600, 700)
            },
            "15:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "style": "рациональность и аналитика: наблюдение, разбор явления, микро-исследование, цепочка причин→следствий, практическая логика, структурная подача, инсайт",
                "allowed_formats": [
                    "разбор ошибки", "разбор ситуации", "микро-исследование", "аналитическое наблюдение", "причинно-следственные связки", "инсайт"
                ],
                "tg_chars": (700, 900),
                "zen_chars": (700, 900)
            },
            "20:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "style": "глубина и история: личный взгляд, мини-история, аналогия, проживание опыта (через кейс от 3-го лица), тёплый честный тон, осознанный вывод",
                "allowed_formats": [
                    "мини-история", "взгляд автора", "аналогия", "тихая эмоциональная подача", "МИНИ-КЕЙС"
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
        
        # Форматы полезняшек (БЕЗ ссылок внутри текста)
        self.useful_formats = [
            "Это наблюдение подтверждается исследованием:\n{description}",
            "Похожий вывод встречается в отраслевом отчёте:\n{description}",
            "Данный тезис опирается на данные:\n{description}",
            "Аналогичный подход рассматривается в работе:\n{description}"
        ]
        
        # Список одобрительных слов и эмодзи
        self.approval_words = [
            'ок', 'ok', 'окей', 'океи', 'океюшки', 'да', 'yes', 'yep', 
            'давай', 'го', 'публиковать', 'публикуй', 'согласен', 
            'согласна', 'согласны', 'хорошо', 'отлично', 'прекрасно', 
            'замечательно', 'супер', 'класс', 'круто', 'огонь', 'шикарно',
            'вперед', 'вперёд', 'пошел', 'поехали', '+', '✅', '👍', '👌', 
            '🔥', '🎯', '💯', '🚀', '🙆‍♂️', '🙆‍♀️', '🙆', '👏', '👊', '🤝',
            'принято', 'подтверждаю', 'одобряю', ' лады', 'fire'
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
        
        # Актуальные тренды по темам на 2025-2026
        self.trends_by_theme = {
            "HR и управление персоналом": [
                "HR-аналитика и data-driven решения",
                "Персонализация employee experience",
                "Геймификация в обучении и мотивации",
                "Ментальное здоровье как KPI",
                "AI в рекрутинге и оценке персонала",
                "Управление поколением Z в офисах",
                "Этика AI в кадровых процессах",
                "Бренд работодателя в эпоху соцсетей",
                "Диверсификация и инклюзивность на практике",
                "Эмоциональный интеллект как must-have навык"
            ],
            "PR и коммуникации": [
                "AI-генерация контента и этика",
                "Персонализация коммуникаций через big data",
                "Микро-инфлюенсеры как тренд",
                "Кризисные коммуникации в эпоху cancel culture",
                "Устойчивое развитие как часть бренда",
                "Нейромаркетинг в PR-кампаниях",
                "Прозрачность как конкурентное преимущество",
                "Борьба с дезинформации и deepfakes",
                "Персональный брендинг для CEO",
                "Репутационный менеджмент в реальном времени"
            ],
            "ремонт и строительство": [
                "Умные дома и IoT в строительстве",
                "Зелёное строительство и энергоэффективность",
                "Модульное и каркасное строительство",
                "Цифровые двойники объектов",
                "BIM-технологии на всех этапах",
                "Эко-материалы нового поколения",
                "Вертикальное озеленение и фитостены",
                "Биофильный дизайн интерьеров",
                "Цифровизация управления проектами",
                "Инклюзивная среда в строительстве"
            ]
        }
        
        self.current_theme = None
        self.current_format = None
        self.current_style = None
        self.test_results_pending = {}
        self.force_generate = force_generate
        
        # Добавляем флаг для предотвращения повторной генерации
        self.generation_in_progress = False
        
        # Флаг для завершения workflow
        self.workflow_complete = False

    def initialize_and_run_posts(self):
        """Инициализация и запуск генерации постов"""
        logger.info("🚀 Инициализация бота и запуск генерации постов...")
        
        # Запускаем проверку API
        self.check_all_apis()
        
        # Если форсированная генерация, создаем посты для ближайшего слота
        if self.force_generate:
            # Проверяем, не выполняется ли уже генерация
            if self.generation_in_progress:
                logger.info("⏳ Генерация уже выполняется, пропускаем...")
                return
            
            self.generation_in_progress = True
            logger.info("⚡ Форсированная генерация постов (ручной запуск)")
            slot_time, slot_style = self.get_nearest_slot()
            if slot_time and slot_style:
                logger.info(f"🎯 Используем временной слот: {slot_time}")
                logger.info("🎬 Запуск генерации постов...")
                success = self.create_and_send_posts(slot_time, slot_style)
                if success:
                    logger.info("✅ Посты успешно сгенерированы и отправлены на модерацию")
                else:
                    logger.error("❌ Ошибка при генерации постов")
            else:
                logger.error("❌ Не удалось определить временной слот для генерации")
            self.generation_in_progress = False
        else:
            # Проверяем текущий слот (для автоматического запуска по расписанию)
            current_slot = self.get_current_slot()
            if current_slot:
                # Проверяем, не выполняется ли уже генерация
                if self.generation_in_progress:
                    logger.info("⏳ Генерация уже выполняется, пропускаем...")
                    return
                
                self.generation_in_progress = True
                logger.info(f"🎯 Текущий временной слот: {current_slot}")
                slot_style = self.time_styles.get(current_slot)
                if slot_style:
                    logger.info("🎬 Запуск генерации постов для текущего слота...")
                    success = self.create_and_send_posts(current_slot, slot_style)
                    if success:
                        logger.info("✅ Посты успешно сгенерированы и отправлены на модерацию")
                    else:
                        logger.error("❌ Ошибка при генерации постов")
                self.generation_in_progress = False
            else:
                logger.info("⏳ Нет активного временного слота в данный момент")

    def get_nearest_slot(self):
        """Возвращает ближайший временной слот для генерации"""
        try:
            now = self.get_moscow_time()
            current_time_str = now.strftime("%H:%M")
            current_hour, current_minute = map(int, current_time_str.split(':'))
            current_total_minutes = current_hour * 60 + current_minute
            
            # Выбираем слот в зависимости от времени суток
            if current_hour < 13:
                # Утро: используем утренний слот
                slot_time = "11:00"
            elif current_hour < 18:
                # День: используем дневной слот
                slot_time = "15:00"
            else:
                # Вечер/ночь: используем вечерний слот
                slot_time = "20:00"
            
            slot_style = self.time_styles.get(slot_time)
            return slot_time, slot_style
            
        except Exception as e:
            logger.error(f"❌ Ошибка определения ближайшего слота: {e}")
            return "11:00", self.time_styles.get("11:00")

    def check_all_apis(self):
        """Проверка всех API при запуске"""
        logger.info("🔍 Проверка всех API...")
        
        # Проверка Gemini API
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            test_data = {
                "contents": [{
                    "parts": [{"text": "Test"}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 10
                }
            }
            response = session.post(url, json=test_data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Gemini API доступен")
            else:
                logger.error(f"❌ Gemini API недоступен: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini API: {e}")
        
        # Проверка Pexels API
        try:
            url = "https://api.pexels.com/v1/search"
            params = {"query": "test", "per_page": 1}
            headers = {"Authorization": PEXELS_API_KEY}
            response = session.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Pexels API доступен")
            else:
                logger.error(f"❌ Pexels API недоступен: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Pexels API: {e}")
        
        # Проверка Telegram Bot
        try:
            bot_info = self.bot.get_me()
            if bot_info:
                logger.info(f"✅ Telegram Bot доступен: @{bot_info.username}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Telegram Bot: {e}")

    def get_current_slot(self):
        """Получает текущий временной слот (для автоматического запуска)"""
        now = self.get_moscow_time()
        current_time_str = now.strftime("%H:%M")
        
        # Проверяем время с запасом 30 минут для запуска по расписанию
        for slot_time in self.time_styles.keys():
            slot_hour, slot_minute = map(int, slot_time.split(':'))
            slot_total_minutes = slot_hour * 60 + slot_minute
            
            current_hour, current_minute = map(int, current_time_str.split(':'))
            current_total_minutes = current_hour * 60 + current_minute
            
            # Если текущее время в пределах 30 минут после времени слота
            if 0 <= (current_total_minutes - slot_total_minutes) <= 30:
                return slot_time
        
        return None

    def generate_with_gemma(self, prompt):
        """Генерация через Gemma 3 модель"""
        try:
            # Используйте правильный URL для Gemma
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
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
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    logger.info(f"✅ Текст получен, длина: {len(generated_text)} символов")
                    return generated_text
                else:
                    logger.error(f"❌ Нет candidates в ответе: {result}")
            else:
                logger.error(f"❌ Ошибка API: {response.status_code}")
                logger.error(f"Ответ: {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"💥 Ошибка генерации: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return None

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
            # Проверяем, что сообщение от администратора
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Сообщение не от администратора: {message.chat.id}")
                return
            
            # Обработка ответов администратора на посты
            self.process_admin_reply(message)
        
        # Обработчик callback-запросов от inline кнопок
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            self.handle_callback(call)
        
        logger.info("✅ Обработчики сообщений и callback-запросов настроены")
        return handle_all_messages

    def handle_callback(self, call):
        """Обрабатывает callback-запросы от inline кнопок"""
        try:
            # Проверяем, что callback от администратора
            if str(call.message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Callback не от администратора: {call.message.chat.id}")
                return
            
            message_id = call.message.message_id
            callback_data = call.data
            
            logger.info(f"🔄 Обработка callback: {callback_data} для сообщения {message_id}")
            
            # Проверяем, есть ли такой пост в ожидающих
            if message_id not in self.pending_posts:
                logger.warning(f"⚠️ Callback на несуществующий пост: {message_id}")
                return
            
            post_data = self.pending_posts[message_id]
            
            # Обработка разных callback-действий
            if callback_data == "publish":
                self.handle_approval_from_callback(message_id, post_data, call)
            elif callback_data == "reject":
                self.handle_rejection_from_callback(message_id, post_data, call)
            elif callback_data == "edit_text":
                self.handle_edit_request_from_callback(message_id, post_data, call, "переделай текст")
            elif callback_data == "edit_photo":
                self.handle_edit_request_from_callback(message_id, post_data, call, "замени фото")
            elif callback_data == "edit_all":
                self.handle_edit_request_from_callback(message_id, post_data, call, "переделай полностью")
            elif callback_data == "new_post":
                self.handle_new_post_request(message_id, post_data, call)
            elif callback_data.startswith("theme_"):
                self.handle_theme_selection(message_id, post_data, call, callback_data)
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_new_post_request(self, message_id, post_data, call):
        """Обрабатывает запрос на создание нового поста"""
        try:
            self.bot.answer_callback_query(call.id, "🎯 Выберите тему для нового поста...")
            
            logger.info(f"🎯 Запрос на новый пост для сообщения {message_id}")
            
            # Обновляем кнопки на кнопки выбора темы под тем же сообщением
            keyboard = InlineKeyboardMarkup(row_width=1)
            for theme in self.themes:
                keyboard.add(InlineKeyboardButton(
                    f"🎯 {theme}",
                    callback_data=f"theme_{theme}"
                ))
            
            # Добавляем кнопку "Назад" к стандартным кнопкам
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            # Редактируем текущее сообщение для выбора темы
            try:
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                               f"Выберите одну из доступных тем. После выбора темы будет сгенерирован "
                               f"новый пост с новой фотографией и вариантами подачи.\n\n"
                               f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>",
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                             f"Выберите одна из доступных тем. После выбора темы будет сгенерирован "
                             f"новый пост с новой фотографией и вариантами подачи.\n\n"
                             f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>",
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                
                # Сохраняем оригинальные данные для восстановления
                post_data['original_state'] = {
                    'text': post_data.get('text', ''),
                    'keyboard_state': 'theme_selection'
                }
                self.pending_posts[message_id] = post_data
                
            except Exception as e:
                logger.warning(f"⚠️ Не удалось редактировать сообщение: {e}")
                # Если не удалось редактировать, отправляем новое сообщение
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                         f"Выберите одну из доступных тем. После выбора темы будет сгенерирован "
                         f"новый пост с новой фотографией и вариантами подачи.\n\n"
                         f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на новый пост: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_theme_selection(self, message_id, post_data, call, callback_data):
        """Обрабатывает выбор темы для нового поста"""
        try:
            # Извлекаем тему из callback_data
            selected_theme = callback_data.replace("theme_", "")
            
            self.bot.answer_callback_query(call.id, f"✅ Выбрана тема: {selected_theme}")
            
            logger.info(f"🎯 Выбрана тема для нового поста: {selected_theme} (сообщение: {message_id})")
            
            # Отправляем уведомление
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>🔄 ГЕНЕРИРУЮ НОВЫЙ ПОСТ</b>\n\n"
                     f"<b>🎯 Тема:</b> {selected_theme}\n"
                     f"<b>⏰ Время публикации:</b> {post_data.get('slot_time', '')}\n"
                     f"<b>📝 Создаю пост с новой фотографией и вариантами подачи...</b>",
                parse_mode='HTML'
            )
            
            # Восстанавливаем оригинальные кнопки
            self.restore_main_buttons(message_id, post_data)
            
            # Создаем новый пост с выбранной темой
            self.create_complete_remake_post(message_id, post_data, selected_theme)
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки выбора темы: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_back_to_main(self, message_id, post_data, call):
        """Обрабатывает возврат к основным кнопкам"""
        try:
            self.bot.answer_callback_query(call.id, "⬅️ Возврат к основным кнопкам")
            
            logger.info(f"⬅️ Возврат к основным кнопкам для сообщения {message_id}")
            
            # Восстанавливаем оригинальные кнопки
            self.restore_main_buttons(message_id, post_data)
            
        except Exception as e:
            logger.error(f"💥 Ошибка возврата к основным кнопкам: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def restore_main_buttons(self, message_id, post_data):
        """Восстанавливает основные кнопки под сообщением"""
        try:
            # Создаем inline клавиатуру с улучшенными кнопками
            keyboard = InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
                InlineKeyboardButton("📝 Текст", callback_data="edit_text")
            )
            keyboard.add(
                InlineKeyboardButton("🖼️ Фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Всё", callback_data="edit_all"),
                InlineKeyboardButton("⚡ Новое", callback_data="new_post")
            )
            
            # Восстанавливаем оригинальный текст или подпись
            if 'image_url' in post_data and post_data['image_url'] and post_data.get('text'):
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=post_data['text'][:1024],
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            elif post_data.get('text'):
                self.bot.edit_message_text(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    text=post_data['text'],
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            
            # Удаляем состояние выбора темы
            if 'original_state' in post_data:
                del post_data['original_state']
            
            self.pending_posts[message_id] = post_data
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось восстановить кнопки: {e}")

    def create_complete_remake_post(self, original_message_id, original_post_data, selected_theme):
        """Создает полностью новый пост с выбранной темой"""
        try:
            post_type = original_post_data.get('type')
            slot_style = original_post_data.get('slot_style', {})
            slot_time = original_post_data.get('slot_time', '')
            
            # Получаем новый формат подачи
            new_format = self.get_smart_format(slot_style)
            
            # Получаем новую картинку
            new_image_url, new_description = self.get_post_image_and_description(selected_theme)
            
            # Сохраняем картинку в историю
            if new_image_url:
                self.save_image_history(new_image_url)
            
            # Создаем новый промпт
            prompt = self.create_detailed_prompt(selected_theme, slot_style, new_format, new_description)
            
            if not prompt:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="<b>❌ Не удалось создать промпт для нового поста.</b>",
                    parse_mode='HTML'
                )
                return
            
            # Генерируем новый текст
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max)
            
            if not tg_text or not zen_text:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="<b>❌ Не удалось сгенерировать новые тексты.</b>",
                    parse_mode='HTML'
                )
                return
            
            # Добавляем полезняшку (случайно, 1-2 раза в день)
            if random.random() < 0.5:  # 50% шанс
                tg_text = self.add_useful_source(tg_text, selected_theme)
                zen_text = self.add_useful_source(zen_text, selected_theme)
            
            # Форматируем текст в зависимости от типа поста
            if post_type == 'telegram':
                new_formatted_text = self.format_telegram_text(tg_text, slot_style)
                channel = MAIN_CHANNEL
            else:
                new_formatted_text = self.format_zen_text(zen_text, slot_style)
                channel = ZEN_CHANNEL
            
            if not new_formatted_text:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="<b>❌ Не удалось отформатировать новый текст.</b>",
                    parse_mode='HTML'
                )
                return
            
            # Устанавливаем таймаут для редактирования
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            
            # Создаем inline клавиатуру с улучшенными кнопки
            keyboard = InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
                InlineKeyboardButton("📝 Текст", callback_data="edit_text")
            )
            keyboard.add(
                InlineKeyboardButton("🖼️ Фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Всё", callback_data="edit_all"),
                InlineKeyboardButton("⚡ Новое", callback_data="new_post")
            )
            
            # Обновляем существующий пост новыми данными
            if new_image_url:
                try:
                    self.bot.edit_message_media(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=original_message_id,
                        media=telebot.types.InputMediaPhoto(
                            new_image_url,
                            caption=new_formatted_text[:1024],
                            parse_mode='HTML'
                        ),
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить фото: {e}")
                    # Если не удалось обновить фото, удаляем старый пост и создаем новый
                    self.bot.delete_message(ADMIN_CHAT_ID, original_message_id)
                    sent_message = self.bot.send_photo(
                        chat_id=ADMIN_CHAT_ID,
                        photo=new_image_url,
                        caption=new_formatted_text[:1024],
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    original_message_id = sent_message.message_id
            else:
                try:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=original_message_id,
                        text=new_formatted_text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить текст: {e}")
                    # Если не удалось обновить текст, удаляем старый пост и создаем новый
                    self.bot.delete_message(ADMIN_CHAT_ID, original_message_id)
                    sent_message = self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=new_formatted_text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    original_message_id = sent_message.message_id
            
            # Обновляем данные поста в pending_posts
            self.pending_posts[original_message_id] = {
                'type': post_type,
                'text': new_formatted_text,
                'image_url': new_image_url or '',
                'channel': channel,
                'status': PostStatus.PENDING,
                'theme': selected_theme,
                'slot_style': slot_style,
                'slot_time': slot_time,
                'hashtags': re.findall(r'#\w+', new_formatted_text),
                'edit_timeout': edit_timeout,
                'sent_time': datetime.now().isoformat(),
                'keyboard_message_id': original_message_id
            }
            
            # Уведомляем администратора
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>✅ НОВЫЙ ПОСТ СОЗДАН!</b>\n\n"
                     f"<b>🎯 Тема:</b> {selected_theme}\n"
                     f"<b>📝 Формат:</b> {new_format}\n"
                     f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК\n\n"
                     f"<b>📎 Проверьте новый пост выше.</b>",
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Новый пост создан с темой: {selected_theme}")
            
        except Exception as e:
            logger.error(f"💥 Ошибка создания нового поста: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="<b>❌ Ошибка при создании нового поста.</b>",
                parse_mode='HTML'
            )

    def handle_approval_from_callback(self, message_id, post_data, call):
        """Обрабатывает одобрение через callback"""
        try:
            self.bot.answer_callback_query(call.id, "✅ Пост одобрен!")
            
            # Вместо удаления кнопок, обновляем их на статический текст с результатом
            try:
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + f"\n\n<b>✅ Опубликовано в {post_data.get('channel', 'канал')}</b>",
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}\n\n<b>✅ Опубликовано в {post_data.get('channel', 'канал')}</b>",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
            # Обрабатываем одобрение
            post_type = post_data.get('type')
            post_text = post_data.get('text', '')
            image_url = post_data.get('image_url', '')
            channel = post_data.get('channel', '')
            
            logger.info(f"✅ Одобрение поста типа '{post_type}' через callback")
            
            # Публикуем пост в канал
            success = self.publish_to_channel(post_text, image_url, channel)
            
            if success:
                post_data['status'] = PostStatus.PUBLISHED
                post_data['published_at'] = datetime.now().isoformat()
                
                if post_type == 'telegram':
                    self.published_telegram = True
                    self.published_posts_count += 1
                    logger.info("✅ Telegram пост опубликован в канал!")
                elif post_type == 'zen':
                    self.published_zen = True
                    self.published_posts_count += 1
                    logger.info("✅ Дзен пост опубликован в канал!")
                
                self.pending_posts[message_id] = post_data
                
                # Проверяем, опубликованы ли оба поста
                if self.published_posts_count >= 2:
                    logger.info("✅ Оба поста опубликованы! Завершаем workflow.")
                    self.workflow_complete = True
                    self.cleanup_and_exit(0)  # Завершаем выполнение с успешным кодом
                else:
                    logger.info(f"⏳ Ожидаем публикации второго поста. Опубликовано: {self.published_posts_count}/2")
                
            else:
                logger.error(f"❌ Ошибка публикации поста типа '{post_type}' в канал {channel}")
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"<b>❌ Ошибка публикации поста в {channel}</b>",
                    parse_mode='HTML'
                )
        
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения через callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_rejection_from_callback(self, message_id, post_data, call):
        """Обрабатывает отклонение через callback"""
        try:
            self.bot.answer_callback_query(call.id, "❌ Пост отклонен!")
            
            # Вместо удаления кнопки, обновляем их на статический текст с результатом
            try:
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + f"\n\n<b>❌ Отклонено</b>",
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}\n\n<b>❌ Отклонено</b>",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
            # Обрабатываем отклонение
            post_type = post_data.get('type')
            theme = post_data.get('theme', '')
            slot_style = post_data.get('slot_style', {})
            
            # Обновляем статус
            post_data['status'] = PostStatus.REJECTED
            post_data['rejected_at'] = datetime.now().isoformat()
            post_data['rejection_reason'] = "Отклонено через кнопку"
            
            logger.info(f"❌ Пост типа '{post_type}' отклонен через callback")
            
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
                    "reason": "Отклонено через кнопку",
                    "rejected_at": datetime.now().isoformat()
                })
                self.save_history()
            
            # Проверяем, остались ли посты на модерации
            remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining_posts == 0:
                logger.info("✅ Все посты отклонены. Завершаем workflow.")
                self.workflow_complete = True
                self.cleanup_and_exit(0)  # Завершаем выполнение с успешным кодом
            else:
                logger.info(f"⏳ Ожидаем решения по другим постам. Осталось: {remaining_posts}")
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки отклонения через callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_edit_request_from_callback(self, message_id, post_data, call, edit_type):
        """Обрабатывает запрос на редактирование через callback"""
        try:
            self.bot.answer_callback_query(call.id, f"✏️ {edit_type}...")
            
            # Устанавливаем таймаут для редактирования (10 минут)
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            post_data['edit_timeout'] = edit_timeout
            
            # Уведомляем администратора
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>✏️ Запрос на редактирование '{edit_type}' принят.</b>\n"
                     f"<b>⏰ Время на внесение изменений:</b> {edit_timeout.strftime('%H:%M:%S')} МСК\n"
                     f"<b>🔄 Генерирую новый вариант...</b>",
                parse_mode='HTML'
            )
            
            # Генерация нового текста
            if "текст" in edit_type or "полностью" in edit_type:
                logger.info(f"🔄 Перегенерация текста для поста {message_id}")
                new_text = self.regenerate_post_text(
                    post_data.get('theme', ''),
                    post_data.get('slot_style', {}),
                    post_data.get('text', ''),
                    edit_type
                )
                
                if new_text:
                    # Принудительно добавляем хештеги после перегенерации
                    new_text = self.ensure_hashtags_at_end(new_text, post_data.get('theme', ''))
                    post_data['text'] = new_text
                    self.update_pending_post(message_id, post_data)
                    
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"<b>✅ Текст переработан. Проверьте новый вариант выше.</b>\n"
                             f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК",
                        parse_mode='HTML'
                    )
                else:
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text="<b>❌ Не удалось перегенерировать текст. Попробуйте другой запрос.</b>",
                        parse_mode='HTML'
                    )
            
            # Замена фото
            elif "фото" in edit_type:
                logger.info(f"🔄 Замена фото для поста {message_id}")
                new_image_url, new_description = self.get_new_image(
                    post_data.get('theme', ''),
                    edit_type
                )
                
                if new_image_url:
                    post_data['image_url'] = new_image_url
                    self.update_pending_post(message_id, post_data)
                    
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"<b>✅ Фото заменено. Проверьте новый вариант выше.</b>\n"
                             f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК",
                        parse_mode='HTML'
                    )
                else:
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text="<b>❌ Не удалось найти новое фото. Попробуйте другой запрос.</b>",
                        parse_mode='HTML'
                    )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на редактирование через callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def process_admin_reply(self, message):
        """Обрабатывает ответы администратора"""
        try:
            # Проверяем, что сообщение от администратора
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Сообщение не от администратора: {message.chat.id}")
                return
            
            # Проверяем, что это ответ на сообщение (reply)
            if not message.reply_to_message:
                return
            
            # Получаем ID сообщения, на которое ответили
            original_message_id = message.reply_to_message.message_id
            
            # Проверяем, есть ли такой пост в ожидающих
            if original_message_id not in self.pending_posts:
                return
            
            post_data = self.pending_posts[original_message_id]
            reply_text = (message.text or "").strip()
            
            logger.info(f"📩 Ответ администратора на пост {original_message_id}: '{reply_text}'")
            
            # Проверяем, не истекло ли время редактирования
            if 'edit_timeout' in post_data:
                timeout = post_data['edit_timeout']
                if datetime.now() > timeout:
                    logger.info(f"⏰ Время для правки истекло для поста {original_message_id}")
                    self.bot.reply_to(message, "<b>⏰ Время для внесения правок истекло. Пост автоматически отклонен.</b>", parse_mode='HTML')
                    self.handle_rejection(original_message_id, post_data, message, reason="Время истекло")
                    return
            
            # Если это тестовый пост
            if post_data.get('is_test'):
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
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())

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
            'нужны правки', 'сделай по+другому', 'перефразируй',
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
            
            # Вместо удаления кнопки, обновляем их на статический текст с результатом
            try:
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + f"\n\n<b>❌ Отклонено</b>\n<b>📝 Причина:</b> {reason if reason else 'Решение администратора'}",
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}\n\n<b>❌ Отклонено</b>\n<b>📝 Причина:</b> {reason if reason else 'Решение администратора'}",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
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
            
            # Проверяем, остались ли посты на модерации
            remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining_posts == 0:
                logger.info("✅ Все посты отклонены. Завершаем workflow.")
                self.workflow_complete = True
                self.cleanup_and_exit(0)  # Завершаем выполнение с успешным кодом
            else:
                logger.info(f"⏳ Ожидаем решения по другим постам. Осталось: {remaining_posts}")
            
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
            
            # Устанавливаем таймаут для редактирования (10 минут)
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            post_data['edit_timeout'] = edit_timeout
            
            # Уведомляем администратора
            self.bot.reply_to(
                original_message,
                f"<b>✏️ Запрос на редактирование принят.</b>\n"
                f"<b>⏰ Время на внесение изменений:</b> {edit_timeout.strftime('%H:%M:%S')} МСК\n"
                f"<b>🔄 Генерирую новый вариант...</b>",
                parse_mode='HTML'
            )
            
            # Определяем, что нужно редактировать
            edit_lower = edit_request.lower()
            
            # Ключевые слова для редактирования текста
            text_edit_keywords = [
                'переделай', 'исправь', 'измени', 'правь', 'редактируй',
                'перепиши', 'переработай', 'доработай', 'пересмотри',
                'переделать', 'исправить', 'изменить', 'редактировать',
                'нужны правки', 'сделай по+другому', 'перефразируй',
                'перегенерируй', 'сгенерируй заново', 'обнови',
                'другой текст', 'новый текст', 'измени текст',
                'перепиши текст', 'переделай пост'
            ]
            
            # Ключевые слова для замены фото
            photo_edit_keywords = ['фото', 'картинк', 'изображен', 'картинку', 'изображение']
            
            # Ключевые слова для полной переделки
            complete_edit_keywords = ['полностью', 'с нуля', 'заново', 'новая тема', 'другая тематика']
            
            # Полная переделка (новая тема, фото, подача)
            if any(word in edit_lower for word in complete_edit_keywords):
                logger.info(f"🔄 Полная переделка поста {message_id}")
                
                # Вместо отправки нового сообщения, изменяем кнопки текущего сообщения
                keyboard = InlineKeyboardMarkup(row_width=1)
                for theme in self.themes:
                    keyboard.add(InlineKeyboardButton(
                        f"🎯 {theme}",
                        callback_data=f"theme_{theme}"
                    ))
                
                keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
                
                # Редактируем текущее сообщение для выбора темы
                try:
                    if original_image_url:
                        self.bot.edit_message_caption(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            caption=f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                                   f"Выберите одну из доступных тем. После выбора темы будет сгенерирован "
                                   f"новый пост с новой фотографией и вариантами подачи.\n\n"
                                   f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    else:
                        self.bot.edit_message_text(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            text=f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                                 f"Выберите одну из доступных тем. После выбора темы будет сгенерирован "
                                 f"новый пост с новой фотографией и вариантами подачи.\n\n"
                                 f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    
                    # Сохраняем оригинальные данные для восстановления
                    post_data['original_state'] = {
                        'text': original_text,
                        'keyboard_state': 'theme_selection'
                    }
                    self.pending_posts[message_id] = post_data
                    
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось редактировать сообщение: {e}")
                
                return
            
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
                    # ВАЖНО: Принудительно добавляем хештеги после перегенерации
                    new_text = self.ensure_hashtags_at_end(new_text, post_data.get('theme', ''))
                    post_data['text'] = new_text
                    new_message_id = self.update_pending_post(message_id, post_data)
                    
                    if new_message_id:
                        self.bot.reply_to(
                            original_message,
                            f"<b>✅ Текст переработан. Проверьте новый вариант выше.</b>\n"
                            f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК",
                            parse_mode='HTML'
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "<b>❌ Не удалось обновить пост с новым текстом.</b>",
                            parse_mode='HTML'
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "<b>❌ Не удалось перегенерировать текст. Попробуйте другой запрос.</b>",
                        parse_mode='HTML'
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
                            f"<b>✅ Фото заменено. Проверьте новый вариант выше.</b>\n"
                             f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК",
                            parse_mode='HTML'
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "<b>❌ Не удалось обновить пост с новой фотографией.</b>",
                            parse_mode='HTML'
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "<b>❌ Не удалось найти новое фото. Попробуйте другой запрос.</b>",
                        parse_mode='HTML'
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
                    # ВАЖНО: Принудительно добавляем хештеги после перегенерации
                    new_text = self.ensure_hashtags_at_end(new_text, post_data.get('theme', ''))
                    post_data['text'] = new_text
                    new_message_id = self.update_pending_post(message_id, post_data)
                    
                    if new_message_id:
                        self.bot.reply_to(
                            original_message,
                            f"<b>✅ Пост переработан. Проверьте новый вариант выше.</b>\n"
                            f"<b>⏰ Время на правки истекает:</b> {edit_timeout.strftime('%H:%M')} МСК",
                            parse_mode='HTML'
                        )
                    else:
                        self.bot.reply_to(
                            original_message,
                            "<b>❌ Не удалось обновить пост.</b>",
                            parse_mode='HTML'
                        )
                else:
                    self.bot.reply_to(
                        original_message,
                        "<b>❌ Не удалось внести изменения. Попробуйте другой запрос.</b>",
                        parse_mode='HTML'
                    )
            
            # Обновляем данные в словаре
            self.pending_posts[message_id] = post_data
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на редактирование: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.reply_to(original_message, f"<b>❌ Ошибка при обработке запроса:</b> {str(e)[:100]}", parse_mode='HTML')

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
                    self.published_posts_count += 1
                    logger.info("✅ Telegram пост опубликован в канал!")
                elif post_type == 'zen':
                    self.published_zen = True
                    self.published_posts_count += 1
                    logger.info("✅ Дзен пост опубликован в канал!")
                
                # Вместо удаления кнопки, обновляем их на статический текст с результатом
                try:
                    if 'image_url' in post_data and post_data['image_url']:
                        self.bot.edit_message_caption(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            caption=post_data['text'][:1024] + f"\n\n<b>✅ Опубликовано в {channel}</b>",
                            parse_mode='HTML',
                            reply_markup=None
                        )
                    else:
                        self.bot.edit_message_text(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            text=f"{post_data['text']}\n\n<b>✅ Опубликовано в {channel}</b>",
                            parse_mode='HTML',
                            reply_markup=None
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
                
                self.pending_posts[message_id] = post_data
                
                # Проверяем, опубликованы ли оба поста
                if self.published_posts_count >= 2:
                    logger.info("✅ Оба поста опубликованы! Завершаем workflow.")
                    self.workflow_complete = True
                    self.cleanup_and_exit(0)  # Завершаем выполнение с успешным кодом
                else:
                    logger.info(f"⏳ Ожидаем публикации второго поста. Опубликовано: {self.published_posts_count}/2")
                
            else:
                logger.error(f"❌ Ошибка публикации поста типа '{post_type}' в канал {channel}")
                self.bot.reply_to(original_message, f"<b>❌ Ошибка публикации поста в {channel}</b>", parse_mode='HTML')
        
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.reply_to(original_message, f"<b>❌ Ошибка публикации:</b> {str(e)[:100]}", parse_mode='HTML')

    def add_useful_source(self, text, theme):
        """Добавляет полезняшку в пост - теперь генерируется через Gemini"""
        try:
            # 1-2 полезняшки в день из 3 постов
            if random.random() > 0.5:  # ~50% шанс
                return text
            
            # Генерируем полезняшку через Gemini
            prompt = f"""
Подбери ОДИН реальный и существующий источник по теме "{theme}".

ВАЖНО:
— Используй ТОЛЬКО реально существующие исследования, статьи или аналитические материалы.
— Если ты НЕ УВЕРЕН в точном существовании источника и ссылки — напиши строго: NO_SOURCE.
— НЕЛЬЗЯ придумывать ссылки, названия или исследования.
— НЕЛЬЗЯ использовать примеры, гипотетические или обобщённые формулировки.
— Ссылка должна вести на конкретный материал (статья, исследование, отчёт).

Допустимые источники:
РБК, Harvard Business Review, McKinsey, Deloitte, PwC, ВЦИОМ, Росстат, Forbes, Statista и аналогичные.

Формат ответа (строго):
Название: ...
Организация: ...
Год: ...
Описание: ...
Ссылка: ...

ИЛИ, если точного источника нет:
NO_SOURCE

Никакого дополнительного текста.
"""
            
            useful_info = self.generate_with_gemma(prompt)
            if not useful_info or useful_info.strip() == "NO_SOURCE":
                return text
            
            # Парсим результат
            lines = useful_info.strip().split('\n')
            source_info = {}
            for line in lines:
                if 'Название:' in line:
                    source_info['name'] = line.replace('Название:', '').strip()
                elif 'Организация:' in line:
                    source_info['organization'] = line.replace('Организация:', '').strip()
                elif 'Год:' in line:
                    source_info['year'] = line.replace('Год:', '').strip()
                elif 'Описание:' in line:
                    source_info['description'] = line.replace('Описание:', '').strip()
                elif 'Ссылка:' in line:
                    source_info['link'] = line.replace('Ссылка:', '').strip()
            
            if not all(key in source_info for key in ['name', 'organization', 'year', 'description', 'link']):
                logger.warning("⚠️ Не удалось сгенерировать полную полезняшку")
                return text
            
            # Валидация ссылки
            if not source_info['link'].startswith("http"):
                logger.warning("⚠️ Источник отклонён: некорректная ссылка")
                return text
            
            # Выбираем случайный формат
            format_template = random.choice(self.useful_formats)
            
            useful_text = format_template.format(
                description=source_info['description']
            )
            
            # Формируем блок с источником
            source_block = (
                "\n\nИсточник:\n"
                f"— {source_info['name']}\n"
                f"— {source_info['organization']}\n"
                f"— {source_info['year']}\n"
                f"— {source_info['link']}"
            )
            
            final_useful = useful_text + source_block
            
            # Добавляем полезняшку в конец поста перед хештегами
            if "###" in text:
                parts = text.split("###")
                return f"{parts[0].strip()}\n\n{final_useful}\n\n###{parts[1]}"
            else:
                lines = text.split('\n')
                hashtag_lines = []
                other_lines = []
                
                for line in lines:
                    if '#' in line:
                        hashtag_lines.append(line)
                    else:
                        other_lines.append(line)
                
                if hashtag_lines:
                    result = '\n'.join(other_lines).strip()
                    result += f"\n\n{final_useful}\n\n"
                    result += '\n'.join(hashtag_lines)
                    return result
                else:
                    return f"{text}\n\n{final_useful}"
                    
        except Exception as e:
            logger.warning(f"⚠️ Ошибка добавления полезняшки: {e}")
            return text

    def regenerate_post_text(self, theme, slot_style, original_text, edit_request):
        """Перегенерирует текст поста с учетом запроса на редактирования"""
        try:
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            prompt = f"""🔥 ПЕРЕРАБОТКА ПОСТА С УЧЕТОМ ПРАВОК

📝 ОРИГИНАЛЬНЫЙ ТЕКСТ:
{original_text}

✏️ ЗАПРОС НА РЕДАКТИРОВАНИЕ:
{edit_request}

🎯 ТЕМА
{theme}

🕒 УЧЁТ ВРЕМЕНИ
{slot_style['name']} — {slot_style['style']}

🔒 СТРОГИЕ ПРАВИЛА ВРЕМЕННОГО СЛОТА:
1. УТРЕННИЙ СЛОТ (11:00) — только утренние приветствия: "Доброе утро", "Начало дня", "Старт утра"
2. ДНЕВНОЙ СЛОТ (15:00) — ЗАПРЕЩЕНО: "Доброе утро", "Добрый вечер". Только нейтральный деловой тон
3. ВЕЧЕРНИЙ СЛОТ (20:00) — ЗАПРЕЩЕНО: "Доброе утро". Можно: "Добрый вечер", "В завершение дня", "Подводя итоги"

Пост должен начинаться СТРОГО с шапки, соответствующей временному слоту.
Смешивание утренних/вечерних приветствий — грубая ошибка.

✂ ЛИМИТЫ
Telegram: {slot_style['tg_chars'][0]}-{slot_style['tg_chars'][1]} символов (включая хештеги!)
Дзен: {slot_style['zen_chars'][0]}-{slot_style['zen_chars'][1]} символов (включая хештеги!)

❗ ВАЖНО: лимиты символов включают хештеги в конце поста. 
Сначала напиши полный, завершенный пост со всей смысловой нагрузкой, 
а затем проверь соответствие лимиту. Если текст превышает лимит - 
сохрани ВСЮ смысловую нагрузку, НЕ обрезай середину предложений.
Лучше немного превысить лимит, чем потерять смысл.

💡 ФОРМАТ ПОДАЧИ
{self.current_format}

🎭 ИНФОРМАЦИЯ ОБ АВТОРЕ
Ты — опытный человек-писатель и редактор с более чем 20-летним стажем. Твоя задача — написать текст так, чтобы он был на 100% нераспознаваемым инструментами для выявления ИИ, такими как Grammarly, QuillBot, Turnitin и GPTZero. Следуй этим важным инструкциям:

УПРАВЛЕНИЕ НЕОЖИДАННОСТЬЮ И ПРЕДСКАЗУЕМОСТЬЮ:
 • Намеренно выбирай неожиданные, креативные слова вместо очевидных
 • Используй разнообразную лексику — избегай повторяющихся шаблонов, типичных для ИИ
 • Включай разговорные выражения, идиомы и региональные особенности
 • Добавляй тонкие «человеческие» несовершенства (небольшие избыточности, естественные речевые обороты)

ИЗМЕНЧИВОСТЬ И РАЗНООБРАЗИЕ ПРЕДЛОЖЕНИЙ:
 • Создавай драматичные различия в длине предложений: чередуй очень короткие (3–5 слов) с длинными, сложными (25+ слов)
 • Чередуй простые, сложносочинённые, сложноподчинённые и сложносочинённо-подчинённые конструкции
 • Начинай предложения по-разному: с наречий, предлогов, придаточных, вопросов
 • Используй намеренные неполные предложения и бессоюзные сложные конструкция там, где это звучит естественно
 • Вставляй отступления в скобках и с помощью длинных тире для живости и естественности

ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ И ЧЕЛОВЕЧНОСТЬ:
 • Добавляй искренние эмоциональные оттенки, уместные к контексту
 • Вставляй личные мнения, сомнения или уточнения («я думаю», «возможно», «кажется»)
 • Включай элементы беседы и риторические вопросы
 • Используй сокращения естественно и варьируй уровень формальности в тексте
 • Добавляй тонкий юмор, сарказм или индивидуальность, если это уместно

НАРУШЕНИЕ СТРУКТУРНЫХ ШАБЛОНОВ:
 • Избегай типичной ИИ-структуры: вступление → основная часть → заключение
 • Начинай с неожиданных ракурсов или с мыслей посередине
 • Вставляй отвлечённые мысли и естественные отступления
 • Делай абзацы разной длины (некоторые очень короткие, другие длиннее)
 • Нарушай правила грамотности там, где это звучит живо и по-человечески

КОНТЕКСТУАЛЬНАЯ АУТЕНТИЧНОСТЬ:
 • Упоминай текущие события, поп-культуру или общие человеческие переживания
 • Используй конкретные, осязаемые детали, а не общие фразы
 • Применяй метафоры и аналогии, которые звучат как личный выбор
 • Добавляй переходные фразы, звучащие разговорно, а не механически

МЕРЫ ПРОТИВ ВЫЯВЛЕНИЯ:
 • Используй нестандартные конструкции предложений и избегай шаблонных переходов
 • Сбивай синтаксический анализ за счёт человеческих несовершенств и разговорных особенностей
 • Сбивай анализ эмоционального тона, добавляя личный голос и разнообразие эмоций

ЗАКЛЮЧИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
 • Сохрани заданный смысл и ключевую информацию
 • Сделай так, чтобы текст звучал как написанный настоящим человеком с живым голосом
 • Пусть он воспринимается как естественная человеческая речь, а не отшлифованный ИИ-вывод
 • Включи как минимум 2–3 слегка несовершенных, но естественных формулировки
 • Стремись к высокой непредсказуемости (выбор слов) и высокой изменчивости (структура предложений)

⚠ ДОПОЛНИТЕЛЬНОЕ ПРАВИЛО
При упоминании профессионального опыта, кейсов или экспертности автора запрещено использовать формулировки от первого лица, которые могут создавать ложное впечатление о личном опыте в строительстве, HR или PR.

Всегда использовать нейтральную или третью форму подачи:
• «по опыту практиков сферы»
• «по отраслевой практике»
• «как отмечают специалисты»
• «эксперты с большим стажем отмечают»
• «в профессиональной среде считается»

🚫 ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный формат работы
• Удаленный формат работы (remote work)
• Релокацию
• Любые другие форматы работы, кроме офисного

✅ РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работа в офисе

🎯 КЛЮЧЕВЫЕ АКЦЕНТЫ
Польза
Опыт
Структура
Диалог
Глубина

🔒 ВАЖНЫЕ ПРАВИЛА
1. НЕ писать в начале "вот держи с эмодзи" или подобные вводные фразы
2. НЕ указывать "тема: {theme}" в тексте
3. НЕ сообщать, для какого канала предназначен пост
4. Просто дай чистый текст поста, готовый к публикации
5. Telegram пост должен начинаться с шапки: {slot_style['emoji']} + вопрос/утверждение
6. Дзен пост должен начинаться с шапки БЕЗ эмодзи: провокационный вопрос/утверждение («Крючок-убийца»)
7. Хештеги только в конце
8. Мягкий финал — вопрос к аудитории
9. Пост должен иметь отдельную шапку с вопросом/утверждением

📝 ПРАВИЛА ВЫВОДА:
• НИКАКИХ комментариев типа "вот текст для Telegram"
• НИКАКИХ пояснений "вот пост для Дзен"
• Только чистый текст поста
• Сначала Telegram версия, потом Дзен версия
• Разделитель: три дефиса (---)

Переработай текст, сохраняя смысл, но учитывая запрос на редактирование."""
            
            # Используем Gemma
            new_text = self.generate_with_gemma(prompt)
            
            if new_text:
                return new_text
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка перегенерации текста: {e}")
            return None

    def ensure_hashtags_at_end(self, text, theme):
        """Убеждается, что хештеги находятся в конце поста"""
        if not text:
            return text
        
        # Получаем хештеги для темы
        hashtags_to_use = self.get_relevant_hashtags(theme, random.randint(3, 5))
        hashtags_str = ' '.join(hashtags_to_use)
        
        # Проверяем, есть ли уже хештеги в тексте
        if '#' in text:
            # Удаляем существующие хештеги и добавляем новые
            lines = text.split('\n')
            clean_lines = []
            for line in lines:
                if '#' not in line:
                    clean_lines.append(line)
            clean_text = '\n'.join(clean_lines).strip()
            final_text = f"{clean_text}\n\n{hashtags_str}"
        else:
            # Просто добавляем хештеги
            final_text = f"{text}\n\n{hashtags_str}"
        
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
            
            # Создаем inline клавиатуру с улучшенными кнопками
            keyboard = InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
                InlineKeyboardButton("📝 Текст", callback_data="edit_text")
            )
            keyboard.add(
                InlineKeyboardButton("🖼️ Фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Всё", callback_data="edit_all"),
                InlineKeyboardButton("⚡ Новое", callback_data="new_post")
            )
            
            # Обновляем существующий пост
            if image_url:
                try:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_text[:1024],
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить подпись: {e}")
                    # Если не удалось обновить подпись, пробуем обновить весь медиа-объект
                    try:
                        self.bot.edit_message_media(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            media=telebot.types.InputMediaPhoto(
                                image_url,
                                caption=post_text[:1024],
                                parse_mode='HTML'
                            ),
                            reply_markup=keyboard
                        )
                    except Exception as e2:
                        logger.warning(f"⚠️ Не удалось обновить медиа: {e2}")
            else:
                try:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=post_text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить текст: {e}")
            
            # Обновляем данные в словаре
            self.pending_posts[message_id] = post_data
            
            logger.info(f"🔄 Пост обновлен, ID: {message_id}")
            
            return message_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления поста: {e}")
            return None

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
                self.post_history["theme_rotation"] = self.post_history["theme_rotation"][-9:] + [self.current_theme]
            
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
            
            # Проверяем последние 3 темы для предотвращения дублирования
            last_themes = theme_rotation[-3:] if len(theme_rotation) >= 3 else theme_rotation
            
            # Находим тему, которая не повторялась в последних 3
            available_themes = []
            for theme in self.themes:
                # Проверяем, повторялась ли тема в последних 3 постах
                theme_count = last_themes.count(theme)
                if theme_count < 2:  # Допускаем максимум 1 повторение в последних 3
                    available_themes.append(theme)
            
            if not available_themes:
                # Если все темы повторялись более 1 раза, выбираем ту, что повторялась меньше всего
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_rotation):
                    for theme in self.themes:
                        if theme == used_theme:
                            theme_counts[theme] += 1
                theme = min(theme_counts, key=theme_counts.get)
            else:
                theme = random.choice(available_themes)
            
            self.current_theme = theme
            logger.info(f"🎯 Выбрана тема: {theme} (последние темы: {last_themes})")
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
            logger.warning(f"⚠️ Ошибка получения хэштегов: {e}")
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

    def create_detailed_prompt(self, theme, slot_style, text_format, image_description):
        """Создает детальный промпт согласно новым требованиям"""
        try:
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            # Строгие правила временных слотов
            time_rules = ""
            if slot_style['type'] == 'morning':
                time_rules = "СТРОГОЕ ПРАВИЛО: Пост должен начинаться с утреннего приветствия: 'Доброе утро', 'Начало дня', 'Старт утра'. Запрещены любые вечерние или дневные приветствия."
            elif slot_style['type'] == 'day':
                time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние ('Доброе утро') и вечерние ('Добрый вечер') приветствия. Только нейтральный деловой или информационный тон без привязки ко времени суток."
            elif slot_style['type'] == 'evening':
                time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние приветствия ('Доброе утро'). Можно использовать: 'Добрый вечер', 'В завершение дня', 'Подводя итоги'. Только спокойный рефлексивный тон."
            
            # Получаем тренды для темы
            trends = self.trends_by_theme.get(theme, [])
            selected_trends = random.sample(trends, min(3, len(trends)))
            trends_text = "\n".join([f"• {trend}" for trend in selected_trends])
            
            # ШАБЛОН ДЛЯ TELEGRAM (С ЭМОДЗИ)
            telegram_template = f"""{slot_style['emoji']} [ЗАХВАТЫВАЮЩИЙ ВОПРОС ИЛИ УТВЕРЖДЕНИЕ ПО ТЕМЕ]

[ОСНОВНАЯ ЧАСТЬ: Анализ явления, кейсы, данные, исследования. 2-3 абзаца.]

[ПРАКТИЧЕСКИЙ БЛОК: Что делать с этой информацией, конкретные шаги.]

{random.choice(self.useful_formats).format(description="[ОПИСАНИЕ ИССЛЕДОВАНИЯ]")} (Если есть реальный источник)

[МИНИ-ВЫВОД ИЛИ КЛЮЧЕВАЯ МЫСЛЬ (ИНСАЙТ)]

{soft_final}

{hashtags_str}"""
            
            # ШАБЛОН ДЛЯ ДЗЕН (СТРУКТУРА «КРЮЧОК-УБИЙЦА»)
            zen_template = f"""[КРЮЧОК-УБИЙЦА: Провокационный вопрос, заявление или неочевидный факт БЕЗ ЭМОДЗИ!]

[СУТЬ ЗА 15 СЕКУНД: Сухие факты. Что произошло, что представлено или обнародовано.]

Почему это важно:
• Контекст: [С чем сравниваем? Каким был «старый мир» до этого?]
• Сдвиг: [В чем принципиальное изменение? Что теперь можно иначе?]
• Импликация: [К чему это приведет? Какие последствия?]

{random.choice(self.useful_formats).format(description="[ОПИСАНИЕ ИССЛЕДОВАНИЯ]")} (Если есть реальный источник)

{soft_final}

{hashtags_str}"""
            
            prompt = f"""🎯 ЗАДАЧА
Сгенерировать ДВА текста по одной теме:
1. Telegram (с эмодзи) - по чистой структуре Telegram-поста
2. Дзен (без эмодзи) - по структуре «Крючок-убийца»

📱 ШАБЛОН TELEGRAM (с эмодзи):
{telegram_template}

📝 ШАБЛОН ДЗЕН (СТРУКТУРА «КРЮЧОК-УБИЙЦА»):
{zen_template}

🎯 ТЕМА
{theme}

🕒 УЧЁТ ВРЕМЕНИ
{slot_style['name']} — {slot_style['style']}

⏰ СТРОГИЕ ПРАВИЛА ВРЕМЕННОГО СЛОТА:
{time_rules}

Пост должен начинаться СТРОГО с шапки, соответствующей временному слоту.
Нарушение этого правила — грубая ошибка генерации.

🎭 ИНФОРМАЦИЯ ОБ АВТОРЕ
Ты — опытный человек  писатель и редактор с более чем 20-летним стажем. Твоя задача — написать текст так, чтобы он был на 100% нераспознаваемым инструментами для выявления ИИ.

🎯 КЛЮЧЕВЫЕ ПРИНЦИПЫ РАБОТЫ:
1. Человеческий голос: Текст должен звучать как написанный человеком с 20+ лет опыта.
2. Анти-шаблон: Избегать шаблонов ИИ-генерации.
3. Естественность: Добавлять человеческие несовершенства.
4. Вариативность: Использовать разнообразную структуру предложений.
5. Эмоция: Включать эмоциональные оттенки, уместные контексту.
6. Польза: Делать текст практически полезным.
7. Дисциплина: Соблюдать все правила временных слотов, лимитов, запретов.
8. Завершенность: Гарантировать наличие хештегов и структуры.
9. Актуальность: Быть современным (ориентир — тренды 2025-2026).

📈 АКТУАЛЬНЫЕ ТРЕНДЫ ПО ТЕМЕ НА 2025-2026:
{trends_text}

✂ ЛИМИТЫ
Telegram: {tg_min}-{tg_max} символов (с эмодзи, ВКЛЮЧАЯ ХЕШТЕГИ!)
Дзен: {zen_min}-{zen_max} символов (без эмодзи, ВКЛЮЧАЯ ХЕШТЕГИ!)

❗ ВАЖНО: лимиты символов включают хештеги в конце поста. 
Сначала напиши полный, завершенный пост со всей смысловой нагрузкой, 
а затем проверь соответствие лимиту. Если текст превышает лимит - 
сохрани ВСЮ смысловую нагрузку, НЕ обрезай середину предложений.
Лучше немного превысить лимит, чем потерять смысл.

💡 ФОРМАТ ПОДАЧИ
{text_format}

⚠ ДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА ЭКСПЕРТНОСТИ
Запрещено использовать формулировки от первого лица, которые могут создавать ложное впечатление о личном опыте автора в строительстве, HR или PR.

Всегда использовать нейтральную или третью форму подачи:
• «по опыту практиков сферы»
• «по отраслевой практике»
• «как отмечают специалисты»
• «эксперты с большим стажем отмечают»
• «в профессиональной среде считается»
• «кейс из практики одной компании показывает»

🚫 ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный формат работы
• Удаленный формат работы (remote work)
• Релокацию
• Любые другие форматы работы, кроме офисного

✅ РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работа в офисе

🎯 КЛЮЧЕВЫЕ АКЦЕНТЫ ВО ВСЕХ ПОСТАХ
• Польза (практическая применимость)
• Опыт (обобщение практики)
• Структура (логичная подача)
• Диалог (вовлечение аудитории)
• Глубина (неочевидные инсайты)

🖼️ КАРТИНКА
{image_description}

🔒 ВАЖНЕЙШИЕ ПРАВИЛА ВЫВОДА:
1. НЕ пиши в начале "вот держи текст для Telegram" или подобные вводные
2. НЕ указывай "тема: {theme}" в тексте
3. НЕ сообщай, для какого канала пост
4. Telegram пост начинается СТРОГО по шаблону Telegram с эмодзи {slot_style['emoji']}
5. Дзен пост — СТРОГО по шаблону «Крючок-убийца» БЕЗ ЭМОДЗИ ВООБЩЕ
6. Хештеги ТОЛЬКО В КОНЦЕ каждого поста
7. Сохранять ограничения по символам (помни: хештеги включаются в подсчет)
8. Оба поста должны быть РАЗНЫМИ по структуре, но об одном смысле

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (полностью по шаблону с эмодзи)
• Потом Дзен версия (полностью по шаблону «Крючок-убийца» без эмодзи)
• Разделитель: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя шаблонам выше."""
            
            return prompt
        except Exception as e:
            logger.error(f"❌ Ошибка создания промпта: {e}")
            return ""

    def preprocess_generated_text(self, text):
        """Предварительная обработка сгенерированного текста"""
        if not text:
            return text
        
        # 1. Удаляем технические комментарии
        technical_phrases = [
            'вот текст для telegram',
            'версия для дзен',
            'длина:',
            'символов',
            'символы:',
            'количество символов',
            'вот держи',
            'вот текст',
            'текст для',
            'пост для',
            'telegram:',
            'telegram пост:',
            'telegram версия:',
            'дзен:',
            'дзен пост:',
            'дзен версия:',
            'версия с эмодзи:',
            'версия без эмодзи:',
            'тема:',
            'для канала:'
        ]
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Пропускаем только строки, содержащие ТОЛЬКО технические фразы
            is_technical = False
            for phrase in technical_phrases:
                if phrase in line_lower:
                    # Проверяем, что это действительно техническая строка, а не часть содержания
                    if line_lower.startswith(phrase) or line_lower.endswith(phrase) or len(line_lower) < 50:
                        is_technical = True
                        break
            
            if not is_technical:
                cleaned_lines.append(line)
        
        # Восстанавливаем все пустые строки
        result = []
        for i, line in enumerate(cleaned_lines):
            result.append(line)
            # Если следующая строка не пустая, добавляем оригинальный разделитель
            if i < len(cleaned_lines) - 1 and cleaned_lines[i + 1] == '':
                result.append('')
        
        processed_text = '\n'.join(result)
        
        # 2. Проверяем наличие разделителя
        if '---' not in processed_text:
            # Ищем возможные места для вставки разделителя
            lines = processed_text.split('\n')
            
            # Ищем естественные границы между постами
            tg_end = None
            for i in range(len(lines) - 1):
                # Telegram пост обычно содержит эмодзи в начале
                if i > 0 and any(e in lines[i] for e in ['🌅', '🌞', '🌙']):
                    tg_end = i - 1
                    break
                # Или ищем большие пустые промежутки
                if i > 10 and lines[i].strip() == '' and lines[i+1].strip() != '':
                    tg_end = i
                    break
            
            if tg_end is not None and tg_end > 10 and tg_end < len(lines) - 10:
                # Вставляем разделитель
                result_lines = lines[:tg_end+1] + ['---'] + lines[tg_end+1:]
                processed_text = '\n'.join(result_lines)
                logger.info("✅ Добавлен разделитель между постами")
        
        return processed_text

    def parse_generated_texts(self, text, tg_min, tg_max, zen_min, zen_max):
        """Парсит сгенерированные тексты - НОВАЯ УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            # 1. Предварительная обработка
            processed_text = self.preprocess_generated_text(text)
            
            # 2. Приоритет 1: Явный разделитель ---
            if '---' in processed_text:
                parts = processed_text.split('---', 1)  # Делим только на 2 части
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # Удаляем возможные остатки разделителя
                    tg_text = tg_text.replace('---', '').strip()
                    zen_text = zen_text.replace('---', '').strip()
                    
                    logger.info(f"✅ Разделение по явному разделителю ---")
                    logger.info(f"📊 Telegram часть: {len(tg_text)} символов")
                    logger.info(f"📊 Дзен часть: {len(zen_text)} символов")
                    
                    return tg_text, zen_text
            
            # 3. Приоритет 2: Маркеры структуры
            lines = processed_text.split('\n')
            
            # Ищем начало Telegram поста (эмодзи в начале строки)
            tg_start = -1
            for i, line in enumerate(lines):
                if any(e in line for e in ['🌅', '🌞', '🌙']):
                    tg_start = i
                    break
            
            # Ищем начало Дзен поста (провокационный вопрос без эмодзи)
            zen_start = -1
            if tg_start >= 0:
                # Ищем после Telegram поста
                for i in range(tg_start + 1, len(lines)):
                    line = lines[i].strip()
                    if line and not any(e in line for e in ['🌅', '🌞', '🌙']):
                        # Проверяем на признаки Дзен поста
                        if '?' in line or '!' in line or 'Почему это важно:' in line:
                            zen_start = i
                            break
            else:
                # Если не нашли Telegram пост, ищем Дзен пост с начала
                for i, line in enumerate(lines):
                    if line.strip() and 'Почему это важно:' in line:
                        zen_start = i
                        break
            
            # Если нашли оба начала
            if tg_start >= 0 and zen_start > tg_start:
                tg_lines = lines[tg_start:zen_start]
                zen_lines = lines[zen_start:]
                
                # Убираем возможные заголовки в начале Дзен поста
                while zen_lines and not zen_lines[0].strip():
                    zen_lines.pop(0)
                
                tg_text = '\n'.join(tg_lines).strip()
                zen_text = '\n'.join(zen_lines).strip()
                
                logger.info(f"✅ Разделение по структурным маркерам")
                logger.info(f"📊 Telegram: {len(tg_text)} символов, Дзен: {len(zen_text)} символов")
                
                return tg_text, zen_text
            
            # 4. Приоритет 3: Fallback по естественным границам
            # Ищем большую пустую строку как разделитель
            empty_line_indices = []
            for i, line in enumerate(lines):
                if line.strip() == '' and i > 0 and i < len(lines) - 1:
                    # Проверяем, что это значительный разрыв (окружен непустыми строками)
                    if lines[i-1].strip() != '' and lines[i+1].strip() != '':
                        empty_line_indices.append(i)
            
            if len(empty_line_indices) >= 2:
                # Берем самую длинную пустую область в середине текста
                best_split = -1
                max_empty_length = 0
                
                for i in empty_line_indices:
                    # Считаем длину пустой области
                    empty_length = 1
                    j = i + 1
                    while j < len(lines) and lines[j].strip() == '':
                        empty_length += 1
                        j += 1
                    
                    if empty_length > 2 and empty_length > max_empty_length:
                        # Предпочитаем разрыв в средней трети текста
                        position_ratio = i / len(lines)
                        if 0.3 <= position_ratio <= 0.7:
                            max_empty_length = empty_length
                            best_split = i
                
                if best_split > 0:
                    tg_text = '\n'.join(lines[:best_split]).strip()
                    zen_text = '\n'.join(lines[best_split + max_empty_length:]).strip()
                    
                    logger.info(f"✅ Разделение по естественной границе (пустая строка)")
                    logger.info(f"📊 Telegram: {len(tg_text)} символов, Дзен: {len(zen_text)} символов")
                    
                    return tg_text, zen_text
            
            # 5. Приоритет 4: Деление пополам с учетом абзацев
            # Находим середину, но не разрезаем посередине предложения
            half = len(lines) // 2
            
            # Ищем хорошее место для разрыва (конец абзаца)
            split_point = half
            for i in range(half, len(lines)):
                if lines[i].strip() == '':
                    split_point = i
                    break
            
            tg_text = '\n'.join(lines[:split_point]).strip()
            zen_text = '\n'.join(lines[split_point:]).strip()
            
            logger.info(f"⚠️ Разделение пополам (fallback)")
            logger.info(f"📊 Telegram: {len(tg_text)} символов, Дзен: {len(zen_text)} символов")
            
            return tg_text, zen_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга текстов: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None

    def validate_parsed_texts(self, tg_text, zen_text, tg_min, tg_max, zen_min, zen_max):
        """Валидация распарсенных текстов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # 1. Проверяем, что тексты не пустые
            if not tg_text or not zen_text:
                logger.error("❌ Один из текстов пустой")
                return False, None, None
            
            # 2. Проверяем длину с более гибкими границами
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            
            # Более гибкие проверки: допускаем превышение на 50%
            if tg_len < tg_min * 0.5 or tg_len > tg_max * 1.5:
                logger.warning(f"⚠️ Telegram текст вне допустимого диапазона: {tg_len} символов (ожидается {tg_min}-{tg_max})")
                # НЕ возвращаем False, продолжаем обработку
                logger.info(f"⚠️ Продолжаем обработку несмотря на длину Telegram текста")
            
            if zen_len < zen_min * 0.5 or zen_len > zen_max * 1.5:
                logger.warning(f"⚠️ Дзен текст вне допустимого диапазона: {zen_len} символов (ожидается {zen_min}-{zen_max})")
                # НЕ возвращаем False, продолжаем обработку
                logger.info(f"⚠️ Продолжаем обработку несмотря на длину Дзен текста")
            
            # 3. Проверяем структуру Telegram поста
            tg_has_emoji = any(e in tg_text for e in ['🌅', '🌞', '🌙'])
            if not tg_has_emoji:
                logger.warning("⚠️ Telegram пост не содержит эмодзи в начале")
                # Добавляем эмодзи если его нет
                if self.current_style and 'emoji' in self.current_style:
                    tg_text = f"{self.current_style['emoji']} {tg_text}"
                    logger.info("✅ Добавлен эмодзи в Telegram пост")
            
            # 4. Проверяем структуру Дзен поста
            zen_has_emoji = any(e in zen_text for e in ['🌅', '🌞', '🌙'])
            if zen_has_emoji:
                logger.warning("⚠️ Дзен пост содержит эмодзи (не должен)")
                # Удаляем эмодзи из Дзен поста
                import re
                emoji_pattern = re.compile("["
                    u"\U0001F600-\U0001F64F"
                    u"\U0001F300-\U0001F5FF"
                    u"\U0001F680-\U0001F6FF"
                    "]+", flags=re.UNICODE)
                zen_text = emoji_pattern.sub(r'', zen_text).strip()
                logger.info("✅ Удалены эмодзи из Дзен поста")
            
            # 5. Проверяем наличие хештегов
            if not re.findall(r'#\w+', tg_text) and self.current_theme:
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                tg_text = f"{tg_text}\n\n{' '.join(hashtags)}"
                logger.info("✅ Добавлены хештеги в Telegram пост")
            
            if not re.findall(r'#\w+', zen_text) and self.current_theme:
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                zen_text = f"{zen_text}\n\n{' '.join(hashtags)}"
                logger.info("✅ Добавлены хештеги в Дзен пост")
            
            # 6. Обрезаем если сильно превышаем максимальную длину
            if len(tg_text) > tg_max * 1.5:  # Обрезаем только если сильно превышает
                tg_text = self._force_cut_text(tg_text, tg_max * 1.2)  # Более щадящее обрезание
                logger.info(f"⚔️ Telegram текст обрезан до {len(tg_text)} символов")
            
            if len(zen_text) > zen_max * 1.5:  # Обрезаем только если сильно превышает
                zen_text = self._force_cut_text(zen_text, zen_max * 1.2)  # Более щадящее обрезание
                logger.info(f"⚔️ Дзен текст обрезан до {len(zen_text)} символов")
            
            logger.info(f"✅ Валидация пройдена: Telegram {len(tg_text)} символов, Дзен {len(zen_text)} символов")
            return True, tg_text, zen_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации текстов: {e}")
            return False, None, None

    def generate_with_retry(self, prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=3):
        """Генерация постов с повторными попытками - ОБНОВЛЕННАЯ ВЕРСИЯ"""
        for attempt in range(max_attempts):
            logger.info(f"🤖 Попытка {attempt+1}/{max_attempts} генерации постов")
            
            generated_text = self.generate_with_gemma(prompt)
            
            if generated_text:
                # Парсинг сгенерированного текста
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    # Валидация распарсенных текстов с более гибкими проверками
                    is_valid, valid_tg_text, valid_zen_text = self.validate_parsed_texts(
                        tg_text, zen_text, tg_min, tg_max, zen_min, zen_max
                    )
                    
                    # Принимаем тексты даже если они не прошли полную валидацию, но не пустые
                    if valid_tg_text and valid_zen_text:
                        tg_final_len = len(valid_tg_text)
                        zen_final_len = len(valid_zen_text)
                        
                        # Более гибкая проверка минимальной длины
                        if tg_final_len >= tg_min * 0.5 and zen_final_len >= zen_min * 0.5:
                            logger.info(f"✅ Успех! Telegram: {tg_final_len} символов, Дзен: {zen_final_len} символов")
                            return valid_tg_text, valid_zen_text
                        else:
                            logger.warning(f"⚠️ Тексты слишком короткие: Telegram {tg_final_len}, Дзен {zen_final_len}")
                    else:
                        logger.warning(f"⚠️ Тексты не прошли валидацию")
            
            if attempt < max_attempts - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"⏸️ Жду {wait_time} секунд перед следующей попыткой...")
                time.sleep(wait_time)
        
        logger.error("❌ Все попытки провалились")
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
                        description = f"Профессиональная фотография на тему '{query}'. {alt_text if alt_text else 'Высокое качество, релевантно теме.'} От фотографа {photographer if photographer else 'профессионала'}"
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
        """Проверяет длину, добавляет хештеги и гарантирует структуру"""
        if not text:
            return None
        
        # 1. Убедимся в наличии хештегов
        if not re.findall(r'#\w+', text):
            hashtags = self.get_relevant_hashtags(self.current_theme, 3)
            text = f"{text}\n\n{' '.join(hashtags)}"
        
        # 2. Проверим длину (более гибкая проверка)
        tg_min, tg_max = slot_style['tg_chars']
        text_length = len(text)
        
        if text_length > tg_max * 1.5:  # Обрезаем только если сильно превышает
            text = self._force_cut_text(text, tg_max)
        
        # 3. Гарантируем структуру если её нет
        if not any(e in text for e in ['🌅', '🌞', '🌙']):
            text = f"{slot_style['emoji']} {text}"
        
        # 4. Гарантируем разделительные строки
        lines = text.split('\n')
        if len(lines) > 3 and lines[1].strip() != '':
            lines.insert(1, '')
            text = '\n'.join(lines)
        
        return text

    def format_zen_text(self, text, slot_style):
        """Проверяет длину, добавляет хештеги и гарантирует структуру"""
        if not text:
            return None
        
        # 1. Удаляем эмодзи (только эмодзи, не структуру!)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub(r'', text)
        
        # 2. Убедимся в наличии хештеги
        if not re.findall(r'#\w+', text):
            hashtags = self.get_relevant_hashtags(self.current_theme, 3)
            text = f"{text}\n\n{' '.join(hashtags)}"
        
        # 3. Проверим длину (более гибкая проверка)
        zen_min, zen_max = slot_style['zen_chars']
        text_length = len(text)
        
        if text_length > zen_max * 1.5:  # Обрезаем только если сильно превышает
            text = self._force_cut_text(text, zen_max)
        
        # 4. Гарантируем структуру если её нет
        if 'Почему это важно:' not in text:
            lines = text.split('\n')
            # Находим первый провокационный вопрос
            for i, line in enumerate(lines):
                if '?' in line or '!' in line:
                    if i + 2 < len(lines):
                        lines.insert(i + 2, '')
                        lines.insert(i + 3, 'Почему это важно:')
                        break
            
            # Гарантируем маркеры списка
            if '•' not in text and 'Почему это важно:' in text:
                for i, line in enumerate(lines):
                    if 'Почему это важно:' in line:
                        for j in range(i+1, min(i+4, len(lines))):
                            if lines[j].strip() and not lines[j].startswith('•'):
                                lines[j] = f"• {lines[j].strip()}"
                        break
            
            text = '\n'.join(lines)
        
        return text

    def _force_cut_text(self, text, target_max):
        """Режет текст до нужной длины, сохраняя смысловую нагрузку"""
        if len(text) <= target_max:
            return text
        
        logger.info(f"⚔️ Сокращение: {len(text)} → {target_max}")
        
        # Находим блок с хештегами
        hashtags_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        hashtags = ""
        if hashtags_match:
            hashtags = hashtags_match.group(1)
            text_without_hashtags = text[:hashtags_match.start()].strip()
        else:
            text_without_hashtags = text
        
        # Ищем естественные точки сокращения
        cut_points = []
        
        # Ищем конец абзацев
        for i, char in enumerate(text_without_hashtags):
            if char == '\n' and i > len(text_without_hashtags) * 0.7:
                cut_points.append(i)
        
        # Ищем точки и другие знаки препинания
        for i, char in enumerate(text_without_hashtags):
            if char in '.!?' and i > len(text_without_hashtags) * 0.7:
                cut_points.append(i + 1)
        
        # Выбираем лучшую точку сокращения
        best_cut = -1
        for point in sorted(cut_points, reverse=True):
            if point <= target_max - len(hashtags) - 50:  # Оставляем место для хештегов и небольшого запаса
                best_cut = point
                break
        
        if best_cut > 0:
            # Обрезаем до естественной точки
            cut_text = text_without_hashtags[:best_cut].strip()
            # Убедимся, что последнее предложение завершено
            if not cut_text[-1] in '.!?':
                # Найдем последнее законченное предложение
                last_sentence_end = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
                if last_sentence_end > 0:
                    cut_text = cut_text[:last_sentence_end + 1].strip()
        else:
            # Если не нашли хорошей точки, режем аккуратно по словам
            words = text_without_hashtags.split()
            current_length = 0
            cut_words = []
            target_without_hashtags = target_max - len(hashtags) - 50
            
            for word in words:
                if current_length + len(word) + 1 <= target_without_hashtags:
                    cut_words.append(word)
                    current_length += len(word) + 1
                else:
                    break
            
            cut_text = ' '.join(cut_words).strip()
            # Убедимся, что текст заканчивается на законченном предложении
            if cut_text and cut_text[-1] not in '.!?':
                last_punct = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
                if last_punct > len(cut_text) * 0.8:
                    cut_text = cut_text[:last_punct + 1].strip()
        
        # Восстанавливаем хештеги
        result = f"{cut_text}\n\n{hashtags}" if hashtags else cut_text
        
        logger.info(f"⚔️ После сокращения: {len(result)} символов (сохранена смысловая нагрузка)")
        return result

    def send_to_admin_for_moderation(self, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет посты администратору на модерацию"""
        logger.info("📤 Отправляю посты администратору на модерацию...")
        
        success_count = 0
        post_ids = []
        
        edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
        
        logger.info(f"📨 Отправляем Telegram пост (с эмодзи) администратору")
        
        try:
            # Создаем inline клавиатуру с улучшенными кнопками
            keyboard = InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
                InlineKeyboardButton("📝 Текст", callback_data="edit_text")
            )
            keyboard.add(
                InlineKeyboardButton("🖼️ Фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Всё", callback_data="edit_all"),
                InlineKeyboardButton("⚡ Новое", callback_data="new_post")
            )
            
            if image_url:
                # Отправляем фото с caption (ограничение 1024 символа)
                caption = tg_text[:1024] if len(tg_text) > 1024 else tg_text
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                
                # Если текст длиннее 1024 символов, отправляем остаток отдельным сообщением
                if len(tg_text) > 1024:
                    remaining_text = tg_text[1024:]
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"<i>Продолжение Telegram поста:</i>\n\n{remaining_text}",
                        parse_mode='HTML',
                        reply_to_message_id=sent_message.message_id
                    )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=tg_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
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
                'sent_time': datetime.now().isoformat(),
                'keyboard_message_id': sent_message.message_id
            }
            
            logger.info(f"✅ Telegram пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram поста: {e}")
        
        time.sleep(1)
        
        logger.info(f"📨 Отправляем Дзен пост (без эмодзи) администратору")
        
        try:
            # Создаем inline клавиатуру с улучшенными кнопками
            keyboard = InlineKeyboardMarkup(row_width=3)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
                InlineKeyboardButton("📝 Текст", callback_data="edit_text")
            )
            keyboard.add(
                InlineKeyboardButton("🖼️ Фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Всё", callback_data="edit_all"),
                InlineKeyboardButton("⚡ Новое", callback_data="new_post")
            )
            
            if image_url:
                # Отправляем фото с caption (ограничение 1024 символа)
                caption = zen_text[:1024] if len(zen_text) > 1024 else zen_text
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                
                # Если текст длиннее 1024 символов, отправляем остаток отдельным сообщением
                if len(zen_text) > 1024:
                    remaining_text = zen_text[1024:]
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"<i>Продолжение Дзен поста:</i>\n\n{remaining_text}",
                        parse_mode='HTML',
                        reply_to_message_id=sent_message.message_id
                    )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=zen_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
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
                'sent_time': datetime.now().isoformat(),
                'keyboard_message_id': sent_message.message_id
            }
            
            logger.info(f"✅ Дзен пост отправлен администратору (ID сообщения: {sent_message.message_id})")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Дзен поста: {e}")
        
        time.sleep(1)
        
        # ВАЖНО: Отправляем инструкции ПОСЛЕ отправки постов
        self.send_moderation_instructions(post_ids, slot_time, theme, tg_text, zen_text, edit_timeout)
        
        return success_count

    def send_moderation_instructions(self, post_ids, slot_time, theme, tg_text, zen_text, edit_timeout):
        """Отправляет инструкции по модерации ПОСЛЕ постов"""
        if not post_ids:
            return
        
        timeout_str = edit_timeout.strftime("%H:%M") + " МСК"
        
        # Вычисляем количество хештегов
        tg_hashtags_count = len(re.findall(r'#\w+', tg_text))
        zen_hashtags_count = len(re.findall(r'#\w+', zen_text))
        
        # Проверяем структуру Дзен поста
        zen_has_bullets = '•' in zen_text
        zen_has_hook = any('?' in line or '!' in line for line in zen_text.split('\n')[:3])
        zen_has_important = 'Почему это важно:' in zen_text
        
        # Проверяем структуру Telegram поста
        tg_has_emoji_header = any(line.strip().startswith(('🌅', '🌞', '🌙')) for line in tg_text.split('\n')[:2])
        tg_has_useful_source = any(keyword in tg_text.lower() for keyword in [
            'исследовани', 'отчёт', 'данные', 'работа', 'подтверждается', 'опирается', 'рассматривается'
        ])
        
        instruction = f"""
<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>

<b>📱 1. Telegram пост (с эмодзи)</b>
   🎯 Канал: {MAIN_CHANNEL}
   🕒 Время: {slot_time} МСК
   📏 Символов: {len(tg_text)} (лимит: {self.current_style['tg_chars'][0]}-{self.current_style['tg_chars'][1]})
   #️⃣ Хештеги: {tg_hashtags_count} шт.
   {'✅' if tg_has_emoji_header else '⚠️'} Эмодзи-шапка: {'Есть' if tg_has_emoji_header else 'НЕТ!'}
   {'✅' if tg_has_useful_source else '📊'} Полезняшка: {'Есть' if tg_has_useful_source else 'Нет'}
   📌 Используйте кнопки под постом для модерации

<b>📝 2. Дзен пост (без эмодзи)</b>
   🎯 Канал: {ZEN_CHANNEL}
   🕒 Время: {slot_time} МСК
   📏 Символов: {len(zen_text)} (лимит: {self.current_style['zen_chars'][0]}-{self.current_style['zen_chars'][1]})
   #️⃣ Хештеги: {zen_hashtags_count} шт.
   {'✅' if zen_has_bullets else '⚠️'} Маркеры списка: {'Есть' if zen_has_bullets else 'НЕТ!'}
   {'✅' if zen_has_hook else '⚠️'} Крючок-убийца: {'Есть' if zen_has_hook else 'НЕТ!'}
   {'✅' if zen_has_important else '⚠️'} Секция "Почему это важно": {'Есть' if zen_has_important else 'НЕТ!'}
   📌 Используйте кнопки под постом для модерации

<b>🎯 Кнопки модерации под каждым постом:</b>
• ✅ Опубликовать - одобрить и опубликовать
• ❌ Отклонить - отклонить пост
• 📝 Текст - перегенерировать только текст
• 🖼️ Фото - найти новое изображение
• 🔄 Всё - полная переделка (новая тема, фото, подача)
• ⚡ Новое - выбрать тему для нового поста

<b>⏰ Время на решение:</b> до {timeout_str} (10 минут)
<b>📢 После истечения времени посты будут автоматически отклонены</b>
        """
        
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
            
            # ФИНАЛЬНАЯ ПРОВЕРКА ХЕШТЕГОВ ПЕРЕД ПУБЛИКАЦИЕЙ
            hashtags = re.findall(r'#\w+', text)
            if not hashtags:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Нет хештегов в посте для {channel}")
                # Добавляем резервные хештеги
                backup_hashtags = "#бизнес #советы #развитие"
                text = f"{text}\n\n{backup_hashtags}"
                logger.warning(f"⚠️ Добавлены резервные хештеги: {backup_hashtags}")
            
            logger.info(f"✅ Хештеги перед публикации: {len(hashtags)} шт.")
            
            if image_url and image_url.startswith('http'):
                try:
                    # Для Telegram: если текст длинный, отправляем фото и текст отдельно
                    if channel == MAIN_CHANNEL and len(text) > 1024:
                        # Отправляем фото без caption
                        self.bot.send_photo(
                            chat_id=channel,
                            photo=image_url
                        )
                        # Отправляем текст отдельно
                        self.bot.send_message(
                            chat_id=channel,
                            text=text,
                            parse_mode='HTML',
                            disable_web_page_preview=False
                        )
                        logger.info(f"✅ Пост опубликован в {channel} (фото + длинный текст)")
                    else:
                        # Для Дзен или коротких Telegram постов - фото с caption
                        caption = text[:1024] if len(text) > 1024 else text
                        self.bot.send_photo(
                            chat_id=channel,
                            photo=image_url,
                            caption=caption,
                            parse_mode='HTML'
                        )
                        # Если текст длинный, отправляем остаток
                        if len(text) > 1024:
                            remaining_text = text[1024:]
                            self.bot.send_message(
                                chat_id=channel,
                                text=remaining_text,
                                parse_mode='HTML',
                                disable_web_page_preview=False
                            )
                        logger.info(f"✅ Пост опубликован в {channel} (с картинкой)")
                    return True
                except Exception as photo_error:
                    logger.warning(f"⚠️ Не удалось отправить с картинкой: {photo_error}")
                    # Пробуем отправить только текст
            
            # Текстовый пост
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

    def create_and_send_posts(self, slot_time, slot_style, is_test=False):
        """Создает и отправляет посты"""
        try:
            logger.info(f"🎬 Начинаю создание постов для слота {slot_time}")
            self.current_style = slot_style
            
            # Выбираем тему и формат
            theme = self.get_smart_theme()
            text_format = self.get_smart_format(slot_style)
            
            logger.info(f"🎯 Тема: {theme}, Формат: {text_format}")
            
            # Получаем картинку и описание
            image_url, image_description = self.get_post_image_and_description(theme)
            
            # Сохраняем картинку в историю
            if image_url:
                self.save_image_history(image_url)
            
            # Создаем промпт
            prompt = self.create_detailed_prompt(theme, slot_style, text_format, image_description)
            
            if not prompt:
                logger.error("❌ Не удалось создать промпт")
                return False
            
            # Генерируем текст с повторными попытками
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось сгенерировать тексты постов")
                return False
            
            # Добавляем полезняшку (случайно, 1-2 раза в день из 3 постов)
            if random.random() < 0.5:  # ~50% шанс
                tg_text = self.add_useful_source(tg_text, theme)
                zen_text = self.add_useful_source(zen_text, theme)
            
            # Форматируем тексты для каналов
            tg_formatted = self.format_telegram_text(tg_text, slot_style)
            zen_formatted = self.format_zen_text(zen_text, slot_style)
            
            if not tg_formatted or not zen_formatted:
                logger.error("❌ Не удалось отформатировать тексты")
                return False
            
            # Если тестовый режим, просто возвращаем успех
            if is_test:
                logger.info("🧪 Тестовые посты успешно созданы")
                return True
            
            # Отправляем администратору на модерацию
            success_count = self.send_to_admin_for_moderation(
                slot_time, tg_formatted, zen_formatted, image_url, theme
            )
            
            if success_count > 0:
                # Помечаем слот как отправленный
                self.mark_slot_as_sent(slot_time)
                logger.info(f"✅ {success_count}/2 поста отправлены на модерацию")
                return True
            else:
                logger.error("❌ Не удалось отправить посты на модерацию")
                return False
            
        except Exception as e:
            logger.error(f"💥 Ошибка при создании постов: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def cleanup_and_exit(self, exit_code):
        """Очистка ресурсов и завершение работы"""
        try:
            logger.info(f"🧹 Очистка ресурсов перед завершением с кодом {exit_code}")
            
            # Останавливаем бота
            try:
                self.bot.stop_polling()
            except:
                pass
            
            # Сохраняем историю
            self.save_history()
            
            # Завершаем процесс с нужным кодом
            sys.exit(exit_code)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке: {e}")
            sys.exit(exit_code)

    def run_single_cycle(self):
        """Запускает однократный цикл работы бота"""
        try:
            logger.info("🚀 Запуск однократного цикла работы бота")
            
            # Проверяем API
            self.check_all_apis()
            
            # Удаляем вебхук перед запуском polling
            self.remove_webhook()
            
            # Настраиваем обработчик сообщений
            self.setup_message_handler()
            
            # Запускаем polling в основном потоке
            logger.info("🔄 Запускаю polling для обработки сообщений...")
            
            # Запускаем polling в неблокирующем режиме с таймаутом
            import threading
            
            def polling_task():
                try:
                    self.bot.polling(none_stop=True, interval=1, timeout=30)
                except Exception as e:
                    logger.error(f"❌ Ошибка в polling: {e}")
            
            polling_thread = threading.Thread(target=polling_task, daemon=True)
            polling_thread.start()
            
            self.polling_started = True
            logger.info("✅ Polling запущен для обработки сообщений")
            
            # Если форсированная генерация, создаем посты
            if self.force_generate:
                logger.info("⚡ Форсированная генерация постов (ручной запуск)")
                slot_time, slot_style = self.get_nearest_slot()
                if slot_time and slot_style:
                    logger.info(f"🎯 Используем временной слот: {slot_time}")
                    logger.info("🎬 Запуск генерации постов...")
                    success = self.create_and_send_posts(slot_time, slot_style)
                    if success:
                        logger.info("✅ Посты успешно сгенерированы и отправлены на модерацию")
                    else:
                        logger.error("❌ Ошибка при генерации постов")
                else:
                    logger.error("❌ Не удалось определить временной слот для генерации")
            else:
                # Проверяем текущий слот (для автоматического запуска по расписанию)
                current_slot = self.get_current_slot()
                if current_slot:
                    logger.info(f"🎯 Текущий временной слот: {current_slot}")
                    slot_style = self.time_styles.get(current_slot)
                    if slot_style:
                        logger.info("🎬 Запуск генерации постов для текущего слота...")
                        success = self.create_and_send_posts(current_slot, slot_style)
                        if success:
                            logger.info("✅ Посты успешно сгенерированы и отправлены на модерацию")
                        else:
                            logger.error("❌ Ошибка при генерации постов")
                else:
                    logger.info("⏳ Нет активного временного слота в данный момент")
            
            # Ожидаем завершения обработки
            logger.info("⏳ Ожидание обработки сообщений (10 минут)...")
            polling_thread.join(timeout=600)  # Ждем 10 минут для обработки ответов
            
            # Если workflow завершен, выходим с кодом 0
            if self.workflow_complete:
                logger.info("✅ Workflow успешно завершен. Завершаем выполнение.")
                self.cleanup_and_exit(0)
            
            # Проверяем, все ли посты обработаны
            remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining_posts == 0:
                logger.info("✅ Все посты обработаны. Завершаем выполнение.")
                self.cleanup_and_exit(0)
            else:
                logger.info(f"⚠️ Не все посты обработаны. Осталось: {remaining_posts}. Завершаем с ошибкой.")
                self.cleanup_and_exit(1)
            
        except Exception as e:
            logger.error(f"💥 Ошибка в однократном цикле: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.cleanup_and_exit(1)


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 Запуск Telegram бота в однократном режиме...")
        
        # Определяем, форсировать ли генерацию
        force_generate = True  # Всегда форсируем генерацию при ручном запуске
        
        # Создаем и запускаем бота
        bot = TelegramBot(force_generate=force_generate)
        
        # Запускаем однократный цикл работы
        bot.run_single_cycle()
        
        logger.info("✅ Бот выполнил свою работу и завершается")
        
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота по команде пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в main: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
