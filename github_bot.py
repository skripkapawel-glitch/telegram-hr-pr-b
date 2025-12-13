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
from telebot.types import Message, ReactionTypeEmoji, InlineKeyboardMarkup, InlineKeyboardButton
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
        self.repo_owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
        self.repo_name = REPO_NAME  # Используем REPO_NAME из секретов
        
    def get_headers(self):
        """Возвращает заголовки для запросов"""
        if not self.github_token:
            logger.warning("⚠️ GitHub токен (MANAGER_GITHUB_TOKEN) не установлен")
            return {"Accept": "application/vnd.github.v3+json"}
        
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_file_content(self, file_path):
        """Получает содержимое файла из репозитория"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установлен"}
            
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
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установлен"}
            
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
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установлен"}
            
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
    
    def run_tests(self, test_type="quick"):
        """Запускает тесты"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установлен"}
            
            workflow_id = "test.yml" if test_type == "quick" else "full_tests.yml"
            return self.manage_workflow("dispatch", workflow_id)
        except Exception as e:
            return {"error": str(e)}


class TelegramBot:
    def __init__(self):
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
        
        # Хэштеги по темам (по 30+ хештегов для каждой темы)
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#кадры", "#команда", "#лидерство", "#мотивация", 
                "#развитиеперсонала", "#бизнес", "#управление", "#работа", "#карьера", "#сотрудники", "#трудоустройство", 
                "#персонал", "#управлениекомандой", "#hrменеджмент", "#кадроваяполитика", "#обучениеперсонала", 
                "#оценкаперсонала", "#кадровыйучет", "#трудовоеправо", "#корпоративнаякультура", "#тимбилдинг", 
                "#адаптацияперсонала", "#kpi", "#управлениепроектами", "#бизнеспроцессы", "#стратегия", "#менеджмент",
                "#hrаналитика", "#управлениеталантами", "#hrбренд", "#hrтехнологии", "#digitalhr", "#hrтренды"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#продвижение", "#брендинг", "#соцсети", "#медиа", "#пиар", 
                "#общение", "#публичность", "#репутация", "#инфоповод", "#сми", "#прессрелиз", "#медиапланирование", 
                "#кризисныекоммуникации", "#брендменеджмент", "#контентмаркетинг", "#социальныемедиа", "#инфлюенсеры", 
                "#медиарилейшнз", "#корпоративныекоммуникации", "#внутренниекоммуникации", "#внешниекоммуникации", 
                "#стратегиякоммуникаций", "#prкампания", "#имидж", "#репутационныйменеджмент", "#интернетмаркетинг", 
                "#таргетированнаяреклама", "#seo", "#smm", "#контекстнаяреклама", "#вебинары", "#презентации", "#копирайтинг"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", "#ремонтквартир", "#строитель", "#отделка", 
                "#ремонтдома", "#стройматериалы", "#проект", "#ремонтподключ", "#евроремонт", "#квартира", "#дом", 
                "#ремонтванной", "#ремонткухни", "#дизайнинтерьера", "#архитектура", "#строительныематериалы", 
                "#строительнаятехника", "#ремонтофиса", "#коммерческийремонт", "#электромонтаж", "#сантехника", 
                "#отопление", "#вентиляция", "#кондиционирование", "#окна", "#двери", "#напольныепокрытия", 
                "#обои", "#плитка", "#покраска", "#штукатурка", "#малярныеработы", "#строительныенормы"
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
                    "причинно-следственные связки", "инсайт"
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
        self.test_results_pending = {}
        
        # Сразу запускаем проверку и генерацию постов при инициализации
        self.initialize_and_run_posts()

    def initialize_and_run_posts(self):
        """Инициализация и запуск генерации постов"""
        logger.info("🚀 Инициализация бота и запуск генерации постов...")
        
        # Запускаем проверку API
        self.check_all_apis()
        
        # Запускаем генерацию постов для текущего слота
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
        """Получает текущий временной слот"""
        now = self.get_moscow_time()
        current_time_str = now.strftime("%H:%M")
        current_hour, current_minute = map(int, current_time_str.split(':'))
        current_total_minutes = current_hour * 60 + current_minute
        
        for slot_time in self.time_styles.keys():
            slot_hour, slot_minute = map(int, slot_time.split(':'))
            slot_total_minutes = slot_hour * 60 + slot_minute
            
            # Проверяем окно в 30 минут после времени слота
            if slot_total_minutes <= current_total_minutes < slot_total_minutes + 30:
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
        @self.bot.message_handler(commands=['start', 'status', 'help'])
        def handle_commands(message):
            if message.text == '/start':
                self.handle_start_command(message)
            elif message.text == '/status':
                self.handle_status_command(message)
            elif message.text == '/help':
                self.handle_help_command(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            # Проверяем, что сообщение от администратора
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Сообщение не от администратора: {message.chat.id}")
                return
            
            # Обработка команд
            if message.text == "/start":
                self.handle_start_command(message)
            elif message.text == "/status":
                self.handle_status_command(message)
            elif message.text == "/help":
                self.handle_help_command(message)
            
            # Обработка ответов администратора на посты
            self.process_admin_reply(message)
        
        logger.info("✅ Обработчики сообщений настроены")
        return handle_all_messages

    def handle_start_command(self, message):
        """Обрабатывает команду /start"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            welcome_text = """
<b>🤖 Добро пожаловать в систему управления ботом!</b>

🔧 <b>Основные функции:</b>
• Автоматическая генерация постов
• Модерация через ответы
• Автоматическая публикация

🎯 <b>Быстрый старт:</b>
Посты генерируются автоматически в 09:00, 14:00, 19:00 (МСК)

📝 <b>Основные команды:</b>
• <b>/start</b> - это сообщение
• <b>/help</b> - помощь и инструкции
• <b>/status</b> - статус бота

<b>🚀 Бот готов к работе!</b>
            """
            self.bot.send_message(
                chat_id=message.chat.id,
                text=welcome_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"💥 Ошибка обработки команды /start: {e}")

    def handle_status_command(self, message):
        """Обрабатывает команду /status"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            status_text = self.get_bot_status()
            self.bot.send_message(
                chat_id=message.chat.id,
                text=status_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"💥 Ошибка обработки команды /status: {e}")

    def handle_help_command(self, message):
        """Обрабатывает команду /help"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            help_text = """
<b>📚 РУКОВОДСТВО ПО УПРАВЛЕНИЮ</b>

<b>🤖 Основные функции:</b>
• Генерация постов по расписанию
• Модерация через ответы
• Автоматическая публикация

<b>📝 Основные команды:</b>
• <b>/start</b> - это сообщение
• <b>/help</b> - это сообщение
• <b>/status</b> - статус бота

<b>🎯 Ответы на посты:</b>
✅ 'ок', 'да', '👍', '🔥' - одобрить и опубликовать пост
❌ 'нет', 'отмена', '❌' - отклонить пост
📝 'переделай текст' - перегенерировать только текст
🔄 'переделай полностью' - полная перегенерация
🖼️ 'замени фото' - найти новое изображение

<b>📅 Расписание публикаций:</b>
• 09:00 - Утренний пост
• 14:00 - Дневной пост
• 19:00 - Вечерний пост

<b>🚀 Бот работает 24/7</b>
            """
            self.bot.send_message(
                chat_id=message.chat.id,
                text=help_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"💥 Ошибка обработки команды /help: {e}")

    def get_bot_status(self):
        """Возвращает статус бота"""
        now = self.get_moscow_time()
        
        # Получаем статус GitHub
        github_status = self.github_manager.get_status()
        github_info = ""
        if "error" not in github_status:
            repo_info = github_status.get("repo", {})
            github_info = f"• <b>Репозиторий:</b> {repo_info.get('name', 'N/A')}\n"
            github_info += f"• <b>Обновлен:</b> {repo_info.get('updated_at', 'N/A')[:10]}\n"
            if "workflow_runs" in github_status:
                runs = github_status["workflow_runs"]
                if runs:
                    latest_run = runs[0]
                    github_info += f"• <b>Последний workflow:</b> {latest_run.get('conclusion', 'running')}\n"
        else:
            github_info = "• <b>GitHub API:</b> ❌ Не доступен\n"
        
        status_text = f"""
<b>📊 СТАТУС БОТА</b>

<b>⏰ Время системы:</b>
• МСК: {now.strftime('%H:%M:%S')}
• Дата: {now.strftime('%d.%m.%Y')}

<b>🤖 Состояние бота:</b>
• Polling: {'✅ Активен' if hasattr(self, 'polling_started') and self.polling_started else '❌ Не активен'}
• Ожидают модерации: {len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.PENDING])}
• Опубликовано сегодня: {len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.PUBLISHED])}
• Отклонено сегодня: {len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.REJECTED])}

<b>📦 GitHub:</b>
{github_info}
<b>📈 Производительность:</b>
• API Gemini: {'✅ Доступен' if GEMINI_API_KEY else '❌ Не доступен'}
• API Pexels: {'✅ Доступен' if PEXELS_API_KEY else '❌ Не доступен'}

<b>🎯 Следующий слот:</b>
{self.get_next_slot_time()}
        """
        return status_text

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
                    self.bot.reply_to(message, "<b>⏰ Время для внесения правок истекло. Пост автоматически отклонен.</b>", parse_mode='HTML')
                    self.handle_rejection(original_message_id, post_data, message, reason="Время истекло")
                    return
            
            # Если это тестовый пост
            if post_data.get('is_test'):
                if self.is_approval(reply_text):
                    self.bot.reply_to(
                        message,
                        "<b>✅ Тестовый пост одобрен!</b>\n\n"
                        "<b>ℹ️ Это был тестовый пост. В реальном режиме он был бы опубликован в канал.</b>",
                        parse_mode='HTML'
                    )
                    return
                elif self.is_rejection(reply_text):
                    self.bot.reply_to(
                        message,
                        "<b>❌ Тестовый пост отклонен!</b>\n\n"
                        "<b>ℹ️ Это был тестовый пост. В реальном режиме он был бы удален.</b>",
                        parse_mode='HTML'
                    )
                    return
                else:
                    self.bot.reply_to(
                        message,
                        "<b>ℹ️ Для тестовых постов используйте:</b>\n"
                        "• 'ок' - для имитации одобрения\n"
                        "• 'нет' - для имитации отклонения",
                        parse_mode='HTML'
                    )
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
                "<b>❓ Не понял команду. Используйте:</b>\n"
                "• 'ок', '👍', '🔥', '✅' или подобное - для публикации\n"
                "• 'нет', '❌', '👎', 'отмена' - для отклонения\n"
                "• 'переделай', 'перепиши текст', 'правки', 'замени фото' - для редактирования\n"
                "<b>⏰ Время на решение: 15 минут</b>",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                self.bot.reply_to(message, f"<b>❌ Ошибка:</b> {str(e)[:100]}", parse_mode='HTML')
            except:
                pass

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
                rejection_msg = "<b>⏰ Время на модерацию истекло. Пост отклонен.</b>"
            else:
                rejection_msg = f"<b>❌ Пост отклонен.</b>\n<b>📝 Причина:</b> {reason if reason else 'Решение администратора'}"
            
            if original_message:
                if hasattr(original_message, 'reply_to_message'):
                    self.bot.reply_to(original_message, rejection_msg, parse_mode='HTML')
                else:
                    self.bot.send_message(chat_id=ADMIN_CHAT_ID, text=rejection_msg, parse_mode='HTML')
            
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
            edit_timeout = self.get_moscow_time() + timedelta(minutes=15)
            post_data['edit_timeout'] = edit_timeout
            
            # Уведомляем администратора
            self.bot.reply_to(
                original_message,
                f"<b>✏️ Запрос на редактирование принят.</b>\n"
                f"<b>⏰ Время на внесение изменений:</b> {edit_timeout.strftime('%H:%M:%S')} МСК (потребуется 2 минут)\n"
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
                    logger.info("✅ Telegram пост опубликован в канал!")
                    self.bot.reply_to(original_message, "<b>✅ Telegram пост опубликован в канал!</b>", parse_mode='HTML')
                elif post_type == 'zen':
                    self.published_zen = True
                    logger.info("✅ Дзен пост опубликован в канал!")
                    self.bot.reply_to(original_message, "<b>✅ Дзен пост опубликован в канал!</b>", parse_mode='HTML')
                
                self.pending_posts[message_id] = post_data
                
            else:
                logger.error(f"❌ Ошибка публикации поста типа '{post_type}' в канал {channel}")
                self.bot.reply_to(original_message, f"<b>❌ Ошибка публикации поста в {channel}</b>", parse_mode='HTML')
        
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.bot.reply_to(original_message, f"<b>❌ Ошибка публикации:</b> {str(e)[:100]}", parse_mode='HTML')

    def regenerate_post_text(self, theme, slot_style, original_text, edit_request):
        """Перегенерирует текст поста с учетом запроса на редактирования"""
        try:
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            
            prompt = f"""🔥 ПЕРЕРАБОТКА ПОСТА С УЧЕТОМ ПРАВОК

📝 ОРИГИНАЛЬНЫЙ ТЕКСТ:
{original_text}

✏️ ЗАПРОС НА РЕДАКТИРОВАНИЕ:
{edit_request}

🎯 ТЕМА
{theme}

🕒 УЧЁТ ВРЕМЕНИ
{slot_style['name']} — {slot_style['style']}

Блок для добавления в промт (рекомендуемый):

Строгое соблюдение временного слота обязательно.
Временной слот публикации всегда указан явно и является приоритетным параметром.

• Слот «утро» — допустимы утренние приветствия и формулы, связанные с началом дня.
• Слот «день» — запрещены любые утренние и вечерние приветствия; допустим нейтральный, деловой или информационный заход без привязки ко времени суток.
• Слот «вечер» — допустим спокойный, итоговый или рефлексивный тон; утренние приветствия (включая «Доброе утро» и их смысловые аналоги) строго запрещены.

Контент обязан начинаться с захода, соответствующего указанному временному слоту.
Игнорирование временного слота считается ошибкой генерации.

✂ ЛИМИТЫ
Telegram: {slot_style['tg_chars'][0]}-{slot_style['tg_chars'][1]} символов
Дзен: {slot_style['zen_chars'][0]}-{slot_style['zen_chars'][1]} символов

💡 ФОРМАТ ПОДАЧИ
{self.current_format}

⚠ ДОПОЛНИТЕЛЬНОЕ ПРАВИЛО
При упоминании профессионального опыта, кейсов или экспертности автора запрещено использовать формулировки от первого лица, которые могут создавать ложное впечатление о личном опыте в строительстве, HR или PR.

Всегда использовать нейтральную или третью форму подачи:
• «по опыту практиков сферы»
• «по отраслевой практике»
• «как отмечают специалисты»
• «в профессиональной среде считается»
• «эксперты с большим стажем отмечают»

🚫 ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный формат работы
• Удаленный формат работы (remote work)
• Релокацию
• Любые другие форматы работы, кроме офисного

✅ РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работу в офисе

🎯 КЛЮЧЕВЫЕ АКЦЕНТЫ
Польза
Опыт
Структура
Диалог
Глубина

🔒 ВАЖНЫЕ ПРАВИЛА
1. НЕ писать в начале "вот держи с эмодзи" или подобные вводные фразы
2. НЕ указывать "тема: {theme}" в текста
3. НЕ сообщать, для какого канала предназначен пост
4. Просто дай чистый текст поста, готовый к публикации
5. Telegram пост должен начинаться с эмодзи {slot_style['emoji']}
6. Дзен пост - без эмодзи вообще
7. Хештеги только в конце
8. Мягкий финал — вопрос к аудитории

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
            
            # Настройка polling с перезапуском при ошибках
            while True:
                try:
                    self.bot.polling(none_stop=True, interval=1, timeout=30)
                except Exception as e:
                    logger.error(f"❌ Ошибка в polling: {e}")
                    logger.info("🔄 Перезапускаю polling через 5 секунд...")
                    time.sleep(5)
            
            self.polling_started = True
            logger.info("✅ Polling запущен и готов принимать сообщения")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска polling: {e}")
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
        """Создает детальный промпт согласно вашим требованиям"""
        try:
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            prompt = f"""🎯 ЗАДАЧА
Сгенерировать ДВА текста по одной теме:
1. Telegram (с эмодзи)
2. Дзен (без эмодзи)

В самом начале хук 1-2 предложения и после как сейчас идут посты.

🎯 ТЕМА
{theme}

🕒 УЧЁТ ВРЕМЕНИ
{slot_style['name']} — {slot_style['style']}

Блок для добавления в промт (рекомендуемый):

Строгое соблюдение временного слота обязательно.
Временной слот публикации всегда указан явно и является приоритетным параметром.

• Слот «утро» — допустимы утренние приветствия и формулы, связанные с началом дня.
• Слот «день» — запрещены любые утренние и вечерние приветствия; допустим нейтральный, деловой или информационный заход без привязки ко времени суток.
• Слот «вечер» — допустим спокойный, итоговый или рефлексивный тон; утренние приветствия (включая «Доброе утро» и их смысловые аналоги) строго запрещены.

Контент обязан начинаться с захода, соответствующего указанному временному слоту.
Игнорирование временного слота считается ошибкой генерации.

✂ ЛИМИТЫ
Telegram: {tg_min}-{tg_max} символов (с эмодзи)
Дзен: {zen_min}-{zen_max} символов (без эмодзи)

🧱 СТРУКТУРА TELEGRAM (с эмодзи)
• Начало с {slot_style['emoji']}
• 1–3 абзаца с глубиной и смыслом
• Мини-вывод или ключевая мысль
• Мягкий финал: "{soft_final}"
• Хештеги: {hashtags_str}

🧱 СТРУКТУРА ДЗЕН (без эмодзи)
• Заголовок БЕЗ эмодзи
• 2–4 раскрывающих абзаца с детальным объяснением
• Мини-вывод или практическое применение
• Мягкий финал: "{soft_final}"
• Хештеги: {hashtags_str}

💡 ФОРМАТ ПОДАЧИ
{text_format}

⚠ ДОПОЛНИТЕЛЬНОЕ ПРАВИЛО
При упоминании профессионального опыта, кейсов или экспертности автора запрещено использовать формулировки от первого лица, которые могут создавать ложное впечатление о личном опыте в строительстве, HR или PR.

Всегда использовать нейтральную или третью форму подачи:
• «по опыту практиков сферы»
• «по отраслевой практике»
• «как отмечают специалисты»
• «в профессиональной среде считается»
• «эксперты с большим стажем отмечают»

🚫 ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный формат работы
• Удаленный формат работы (remote work)
• Релокацию
• Любые другие форматы работы, кроме офисного

✅ РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работу в офисе

🎯 КЛЮЧЕВЫЕ АКЦЕНТЫ
• Польза
• Опыт
• Структура
• Диалог
• Глубина

🖼️ КАРТИНКА
{image_description}

🔒 ВАЖНЕЙШИЕ ПРАВИЛА ВЫВОДА:
1. НЕ пиши в начале "вот держи текст для Telegram" или подобные вводные фразы
2. НЕ указывай "тема: {theme}" в самом тексте
3. НЕ сообщай, для какого канала предназначен пост (Telegram или Яндекс.Дзен)
4. НЕ пиши комментарии вроде "вот версия с эмодзи" или "вот версия без эмодзи"
5. Просто дай ЧИСТЫЙ ТЕКСТ поста, готовый к публикации
6. Telegram пост должен НАЧИНАТЬСЯ С ЭМОДЗИ {slot_style['emoji']}
7. Дзен пост - БЕЗ ЭМОДЗИ ВООБЩЕ
8. Хештеги ТОЛЬКО В КОНЦЕ каждого поста
9. Мягкий финал — вопрос к аудитории

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (с эмодзи {slot_style['emoji']})
• Потом Дзен версия (без эмодзи)
• Разделитор: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Пример правильного вывода:
{slot_style['emoji']} Текст Telegram поста...
Второй абзац...
Третий абзац...
{soft_final}

{hashtags_str}

---

Текст Дзен поста...
Второй абзац...
Третий абзац...
{soft_final}

{hashtags_str}

Создай два разных текста по одной теме. Оба текста должны быть уникальными по структуре, но об одном смысле."""
            
            return prompt
        except Exception as e:
            logger.error(f"❌ Ошибка создания промпта: {e}")
            return ""

    def clean_generated_text(self, text):
        """Очищает сгенерированный текст от артефактов, но СОХРАНЯЕТ ХЕШТЕГИ"""
        if not text:
            return text
        
        try:
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                line_lower = line_stripped.lower()
                
                # Пропускаем строки с технической информацией
                if any(keyword in line_lower for keyword in ['длина:', 'символов', 'символы:', 'количество символов', 'символа', 'текст содержит']):
                    continue
                
                # Пропускаем строки с явными вводными фразы
                if any(phrase in line_lower for phrase in [
                    'вот держи', 'вот текст', 'вот пост', 'текст для', 'пост для',
                    'telegram:', 'telegram пост:', 'telegram версия:',
                    'дзен:', 'дзен пост:', 'дзен версия:',
                    'версия с эмодзи:', 'версия без эмодзи:',
                    'тема:', 'для канала:', 'для telegram:', 'для дзен:',
                    'первый пост:', 'второй пост:',
                ]):
                    continue
                
                # Пропускаем пустые строки с техническими разделителями
                if line_stripped in ['---', '===', '***', '___']:
                    if cleaned_lines:  # Добавляем только один разделитель
                        cleaned_lines.append('---')
                    continue
                
                # Сохраняем все остальные строки (ВКЛЮЧАЯ строки с хештегами!)
                cleaned_lines.append(line)
            
            cleaned_text = '\n'.join(cleaned_lines)
            
            # Удаляем множественные пустые строки, но сохраняем одну
            cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
            
            # Удаляем нежелательные концовки
            unwanted_endings = [
                'текст готов', 'пост готов', 'готово', 'создано', 
                'вот пост:', 'вот текст:', 'результат:', 'пост:',
                'пример поста:', 'структура поста:', 'дополнительный контент',
                'удачи', 'надеюсь', 'помогло', 'есть вопросы',
                'telegram пост готов', 'дзен пост готов'
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
            # Очищаем текст
            text = self.clean_generated_text(text)
            
            # Ищем разделитель
            if '---' in text:
                parts = text.split('---')
                if len(parts) >= 2:
                    tg_text_raw = parts[0].strip()
                    zen_text_raw = parts[1].strip()
                else:
                    # Если не нашли разделитель, делим пополам
                    lines = text.split('\n')
                    half = len(lines) // 2
                    tg_lines = lines[:half]
                    zen_lines = lines[half:]
                    tg_text_raw = '\n'.join(tg_lines)
                    zen_text_raw = '\n'.join(zen_lines)
            else:
                # Если нет разделителя, ищем другие варианты
                parts = text.split('\n\n\n')
                if len(parts) >= 2:
                    tg_text_raw = parts[0].strip()
                    zen_text_raw = parts[1].strip()
                else:
                    # Делим пополам
                    lines = text.split('\n')
                    half = len(lines) // 2
                    tg_lines = lines[:half]
                    zen_lines = lines[half:]
                    tg_text_raw = '\n'.join(tg_lines)
                    zen_text_raw = '\n'.join(zen_lines)
            
            # Дополнительная очистка
            tg_text = self.clean_generated_text(tg_text_raw)
            zen_text = self.clean_generated_text(zen_text_raw)
            
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
            
            tg_length = len(tg_text)
            zen_length = len(zen_text)
            
            logger.info(f"📊 Парсинг: Telegram {tg_length} символов, Дзен {zen_length} символов")
            
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
            logger.info(f"🤖 Попытка {attempt+1}/{max_attempts} генерации постов")
            
            generated_text = self.generate_with_gemma(prompt)
            
            if generated_text:
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    tg_final_len = len(tg_text)
                    zen_final_len = len(zen_text)
                    
                    if tg_final_len >= 300 and zen_final_len >= 400:
                        logger.info(f"✅ Успех! Telegram: {tg_final_len} символов, Дзен: {zen_final_len} символов")
                        return tg_text, zen_text
            
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
        """Форматирует Telegram текст (с эмодзи) - ГАРАНТИРУЕТ наличие хештегов"""
        if not text:
            return None
        
        text = text.strip()
        
        # Удаляем технические фразы
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        # ГАРАНТИЯ: Если нет хештегов - добавляем их принудительно
        if not re.findall(r'#\w+', text):
            logger.warning("⚠️ В Telegram посте нет хештегов. Добавляю принудительно...")
            hashtags = self.get_relevant_hashtags(self.current_theme or "HR и управление персоналом", random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            text = f"{text}\n\n{hashtags_str}"
        
        # Проверяем, начинается ли текст с нужного эмодзи
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
        
        # ФИНАЛЬНАЯ ПРОВЕРКА: убеждаемся, что хештеги есть
        final_hashtags = re.findall(r'#\w+', text)
        if not final_hashtags:
            logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: В Telegram посте нет хештегов! Добавляю резервные...")
            hashtags = ["#бизнес", "#советы", "#развитие"]
            text = f"{text}\n\n{' '.join(hashtags)}"
        
        logger.info(f"✅ Хештеги Telegram: {len(final_hashtags) if final_hashtags else len(hashtags)} шт.")
        
        return text

    def format_zen_text(self, text, slot_style):
        """Форматирует Дзен текст (без эмодзи) - ГАРАНТИРУЕТ наличие хештегов"""
        if not text:
            return None
        
        text = text.strip()
        
        # Удаляем технические фразы
        for phrase in ["Дополнительный контент для соответствия длине.", 
                      "Дополнительный контент.", 
                      "Текст для соответствия длине."]:
            text = text.replace(phrase, '').strip()
        
        # ГАРАНТИЯ: Если нет хештеги - добавляем их принудительно
        if not re.findall(r'#\w+', text):
            logger.warning("⚠️ В Дзен посте нет хештегов. Добавляю принудительно...")
            hashtags = self.get_relevant_hashtags(self.current_theme or "HR и управление персоналом", random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            text = f"{text}\n\n{hashtags_str}"
        
        # Удаляем все эмодзи из Дзен поста
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # эмоции
            u"\U0001F300-\U0001F5FF"  # символы и пиктограммы
            u"\U0001F680-\U0001F6FF"  # транспорт и карты
            u"\U0001F700-\U0001F77F"  # алхимические символы
            u"\U0001F780-\U0001F7FF"  # геометрические фигуры
            u"\U0001F800-\U0001F8FF"  # доп. стрелки
            u"\U0001F900-\U0001F9FF"  # доп. символы и пиктограммы
            u"\U0001FA00-\U0001FA6F"  # шахматы
            u"\U0001FA70-\U0001FAFF"  # символы и пиктограммы
            u"\U00002702-\U000027B0"  # доп. символы
            u"\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE)
        
        text = emoji_pattern.sub(r'', text)
        text = re.sub(r'[^\w\s#@.,!?;:"\'()\-—–«»\n]', '', text)
        
        zen_min, zen_max = slot_style['zen_chars']
        text_length = len(text)
        
        logger.info(f"📏 Дзен текст (без эмодзи): {text_length} символов ({zen_min}-{zen_max})")
        
        if text_length < zen_min:
            logger.warning(f"⚠️ Дзен текст коротковат: {text_length} < {zen_min}")
        
        if text_length > zen_max:
            logger.warning(f"⚠️ Дзен текст длинноват: {text_length} > {zen_max}")
            text = self._force_cut_text(text, zen_max)
            text_length = len(text)
        
        # ФИНАЛЬНАЯ ПРОВЕРКА: убеждаемся, что хештеги есть
        final_hashtags = re.findall(r'#\w+', text)
        if not final_hashtags:
            logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: В Дзен посте нет хештегов! Добавляю резервные...")
            hashtags = ["#бизнес", "#советы", "#развитие"]
            text = f"{text}\n\n{' '.join(hashtags)}"
        
        logger.info(f"✅ Хештеги Дзен: {len(final_hashtags) if final_hashtags else len(hashtags)} шт.")
        
        return text

    def send_to_admin_for_moderation(self, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет посты администратору на модерацию"""
        logger.info("📤 Отправляю посты администратору на модерацию...")
        
        success_count = 0
        post_ids = []
        
        edit_timeout = self.get_moscow_time() + timedelta(minutes=15)
        
        logger.info(f"📨 Отправляем Telegram пост (с эмодзи) администратору")
        
        try:
            # Создаем inline клавиатуру с иконками для модерации
            keyboard = InlineKeyboardMarkup(row_width=5)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отменить", callback_data="reject"),
                InlineKeyboardButton("📝 Переделать", callback_data="edit_text"),
                InlineKeyboardButton("📷 Переделать фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Переделать полностью", callback_data="edit_all")
            )
            
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=tg_text[:1024],
                    parse_mode='HTML',
                    reply_markup=keyboard
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
            # Создаем inline клавиатуру с иконками для модерации
            keyboard = InlineKeyboardMarkup(row_width=5)
            keyboard.add(
                InlineKeyboardButton("✅ Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отменить", callback_data="reject"),
                InlineKeyboardButton("📝 Переделать", callback_data="edit_text"),
                InlineKeyboardButton("📷 Переделать фото", callback_data="edit_photo"),
                InlineKeyboardButton("🔄 Переделать полностью", callback_data="edit_all")
            )
            
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=zen_text[:1024],
                    parse_mode='HTML',
                    reply_markup=keyboard
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
        
        instruction = f"""
<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>

<b>📱 1. Telegram пост (с эмодзи)</b>
   🎯 Канал: {MAIN_CHANNEL}
   🕒 Время: {slot_time} МСК
   📏 Символов: {len(tg_text)}
   #️⃣ Хештеги: {tg_hashtags_count} шт.
   📌 Используйте кнопки под постом для модерации

<b>📝 2. Дзен пост (без эмодзи)</b>
   🎯 Канал: {ZEN_CHANNEL}
   🕒 Время: {slot_time} МСК
   📏 Символов: {len(zen_text)}
   #️⃣ Хештеги: {zen_hashtags_count} шт.
   📌 Используйте кнопки под постом для модерации

<b>🎯 Кнопки модерации под каждым постом:</b>
• ✅ Опубликовать - одобрить и опубликовать
• ❌ Отменить - отклонить пост
• 📝 Переделать - перегенерировать только текст
• 📷 Переделать фото - найти новое изображение
• 🔄 Переделать полностью - полная перегенерация

<b>⏰ Время на решение:</b> до {timeout_str} (15 минут)
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

    def get_next_slot_time(self):
        """Возвращает время следующего слота публикации"""
        try:
            now = self.get_moscow_time()
            current_time = now.strftime("%H:%M")
            current_hour, current_minute = map(int, current_time.split(':'))
            current_total_minutes = current_hour * 60 + current_minute
            
            next_slot = None
            next_slot_time = None
            
            # Получаем все времена слотов и сортируем их
            slot_times = list(self.time_styles.keys())
            slot_times_sorted = sorted(slot_times, key=lambda x: (int(x.split(':')[0]), int(x.split(':')[1])))
            
            for slot_time in slot_times_sorted:
                slot_hour, slot_minute = map(int, slot_time.split(':'))
                slot_total_minutes = slot_hour * 60 + slot_minute
                
                if slot_total_minutes > current_total_minutes:
                    next_slot = slot_time
                    next_slot_time = slot_total_minutes
                    break
            
            # Если не нашли следующий слот сегодня, берем первый слот на следующий день
            if not next_slot:
                next_slot = slot_times_sorted[0]
                next_slot_hour, next_slot_minute = map(int, next_slot.split(':'))
                next_slot_time = next_slot_hour * 60 + next_slot_minute + 1440  # Добавляем день
            
            # Вычисляем оставшееся время
            minutes_remaining = next_slot_time - current_total_minutes
            
            if minutes_remaining > 1440:  # Если больше суток
                minutes_remaining -= 1440
            
            hours = minutes_remaining // 60
            minutes = minutes_remaining % 60
            
            if hours > 0:
                return f"{next_slot} (через {hours}ч {minutes}м)"
            else:
                return f"{next_slot} (через {minutes}м)"
                
        except Exception as e:
            logger.error(f"❌ Ошибка вычисления следующего слота: {e}")
            return "Не удалось определить"

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
            
            # Генерируем и отправляем посты для текущего слота
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
            logger.info("⏳ Ожидание обработки сообщений...")
            polling_thread.join(timeout=900)  # Ждем 15 минут для обработки ответов
            
            logger.info("✅ Однократный цикл работы завершен")
            
        except Exception as e:
            logger.error(f"💥 Ошибка в однократном цикле: {e}")
            import traceback
            logger.error(traceback.format_exc())


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 Запуск Telegram бота в однократном режиме...")
        
        # Создаем и запускаем бота
        bot = TelegramBot()
        
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
