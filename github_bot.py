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
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReactionTypeEmoji, InlineKeyboardMarkup, InlineKeyboardButton
import threading
import hashlib

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
MANAGE_GITHUB_TWEN = os.environ.get("MANAGE_GITHUB_TWEN")

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

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: ОТПРАВКА В ЛИЧНЫЙ ЧАТ → МОДЕРАЦИЯ → ПУБЛИКАЦИЯ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"✅ ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
print(f"🤖 Рабочая модель: gemma-3-27b-it")
print(f"📢 Основной канал (с эмодзи): {MAIN_CHANNEL}")
print(f"📢 Дзен канал (без эмодзи): {ZEN_CHANNEL}")
print(f"📋 Режим: 📤 ЛИЧНЫЙ ЧАТ → МОДЕРАЦИЯ → ПУБЛИКАЦИЯ")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)


class PostStatus:
    """Статусы постов"""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    PUBLISHED = "published"
    REJECTED = "rejected"


class BotControlManager:
    """Класс для управления ботом через Telegram"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.user_states = {}
        self.user_sessions = {}
        self.security_settings = {
            "password_protection": False,
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "session_duration": 24  # Часы
        }
        self.management_log_file = "management_log.json"
        self.load_security_settings()
        self.load_management_log()
    
    def create_left_menu_keyboard(self):
        """Создает левое меню (как на фото)"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        buttons = [
            KeyboardButton("Меню"),          # Кнопка для открытия дополнительного меню
            KeyboardButton("Сообщение")      # Кнопка для обычного сообщения
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_additional_menu_keyboard(self):
        """Создает дополнительное меню с командами Старт/Меню/Хелп"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        buttons = [
            KeyboardButton("Старт"),
            KeyboardButton("Меню"),
            KeyboardButton("Хелп")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def load_security_settings(self):
        """Загружает настройки безопасности из файла"""
        try:
            if os.path.exists("security_settings.json"):
                with open("security_settings.json", 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.security_settings.update(settings)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки настроек безопасности: {e}")
    
    def save_security_settings(self):
        """Сохраняет настройки безопасности в файл"""
        try:
            with open("security_settings.json", 'w', encoding='utf-8') as f:
                json.dump(self.security_settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения настроек безопасности: {e}")
    
    def load_management_log(self):
        """Загружает лог действий управления"""
        try:
            if os.path.exists(self.management_log_file):
                with open(self.management_log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки лога управления: {e}")
        return {"actions": [], "last_update": None}
    
    def log_action(self, user_id, action, details=""):
        """Логирует действие управления"""
        try:
            log_data = self.load_management_log()
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "action": action,
                "details": details
            }
            log_data.setdefault("actions", []).append(log_entry)
            log_data["last_update"] = datetime.now().isoformat()
            
            with open(self.management_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            logger.info(f"📝 Логировано действие: {action} - {details}")
        except Exception as e:
            logger.error(f"❌ Ошибка логирования действия: {e}")
    
    def create_menu_keyboard(self):
        """Создает меню плашек управления"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            KeyboardButton("🤖 Управление"),
            KeyboardButton("📝 Редактировать"),
            KeyboardButton("🧪 Тесты"),
            KeyboardButton("📊 Статус"),
            KeyboardButton("⚙️ Настройки"),
            KeyboardButton("❓ Помощь")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_management_submenu(self):
        """Создает подменю управления"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            KeyboardButton("🚀 Запустить"),
            KeyboardButton("⏸️ Остановить"),
            KeyboardButton("📈 Статус бота"),
            KeyboardButton("🔙 Назад")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_edit_submenu(self):
        """Создает подменю редактирования"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            KeyboardButton("📁 Выбрать файл"),
            KeyboardButton("👁️ Просмотреть"),
            KeyboardButton("✏️ Редактировать"),
            KeyboardButton("🔙 Назад")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_tests_submenu(self):
        """Создает подменю тестов"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            KeyboardButton("⚡ Быстрые тесты"),
            KeyboardButton("🔍 Полные тесты"),
            KeyboardButton("📊 Тест публикации"),
            KeyboardButton("🔙 Назад")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_status_submenu(self):
        """Создает подменю статуса"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            KeyboardButton("📈 Статистика"),
            KeyboardButton("⚠️ Ошибки"),
            KeyboardButton("📊 Дашборд"),
            KeyboardButton("🔙 Назад")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def create_settings_submenu(self):
        """Создает подменю настроек"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        protection_status = "✅ Вкл" if self.security_settings["password_protection"] else "❌ Выкл"
        buttons = [
            KeyboardButton(f"🔐 Защита: {protection_status}"),
            KeyboardButton("🔑 Сменить пароль"),
            KeyboardButton("🗝️ Вкл/Выкл защиту"),
            KeyboardButton("🔙 Назад")
        ]
        keyboard.add(*buttons)
        return keyboard
    
    def check_password_protection(self, user_id):
        """Проверяет парольную защиту"""
        if not self.security_settings["password_protection"]:
            return True
        
        if user_id in self.user_sessions:
            session_expiry = self.user_sessions[user_id].get("expiry")
            if session_expiry and datetime.now() < session_expiry:
                return True
        
        return False
    
    def authenticate_user(self, user_id, password):
        """Аутентифицирует пользователя"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash == self.security_settings["password_hash"]:
            expiry_time = datetime.now() + timedelta(hours=self.security_settings["session_duration"])
            self.user_sessions[user_id] = {
                "authenticated": True,
                "expiry": expiry_time
            }
            self.log_action(user_id, "authentication", "Успешная аутентификация")
            return True
        return False
    
    def change_password(self, new_password):
        """Меняет пароль"""
        self.security_settings["password_hash"] = hashlib.sha256(new_password.encode()).hexdigest()
        self.save_security_settings()
    
    def toggle_protection(self):
        """Включает/выключает защиту"""
        self.security_settings["password_protection"] = not self.security_settings["password_protection"]
        self.save_security_settings()
        return self.security_settings["password_protection"]


class GitHubAPIManager:
    """Класс для управления GitHub API"""
    
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        self.repo_owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
        self.repo_name = os.environ.get("GITHUB_REPOSITORY", "").split('/')[-1] if os.environ.get("GITHUB_REPOSITORY") else ""
        
    def get_headers(self):
        """Возвращает заголовки для запросов"""
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def manage_workflow(self, action, workflow_id):
        """Управляет workflow GitHub Actions"""
        try:
            if not self.github_token:
                return {"error": "GitHub токен не установлен"}
            
            if action == "enable":
                url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/workflows/{workflow_id}/enable"
                method = "PUT"
            elif action == "disable":
                url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/workflows/{workflow_id}/disable"
                method = "PUT"
            elif action == "dispatch":
                url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/workflows/{workflow_id}/dispatches"
                method = "POST"
            else:
                return {"error": f"Неизвестное действие: {action}"}
            
            response = requests.request(method, url, headers=self.get_headers(), json={})
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_file_content(self, file_path):
        """Получает содержимое файла из репозитория"""
        try:
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
        
        # Инициализация менеджера управления
        self.control_manager = BotControlManager(self)
        self.github_manager = GitHubAPIManager()
        
        # Добавляем левое меню
        self.left_menu_keyboard = self.control_manager.create_left_menu_keyboard()
        
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
                "#обои", "#плитка", "#покраска", "# штукатурка", "#малярныеработы", "#строительныенормы"
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
            'принято', 'подтверждаю', 'одобряю', ' ладно', 'лады', 'fire'
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
        @self.bot.message_handler(commands=['menu', 'start', 'status', 'help'])
        def handle_commands(message):
            if message.text == '/menu':
                self.handle_menu_command(message)
            elif message.text == '/start':
                self.handle_start_command(message)
            elif message.text == '/status':
                self.handle_status_command(message)
            elif message.text == '/help':
                self.handle_help_command(message)
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            # Обработка левого меню
            if message.text == "Меню":
                keyboard = self.control_manager.create_additional_menu_keyboard()
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="<b>📋 Дополнительное меню</b>\n\n<b>Выберите команду:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                return
            
            elif message.text == "Сообщение":
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="<b>✍️ Введите ваше сообщение:</b>",
                    parse_mode='HTML',
                    reply_markup=self.left_menu_keyboard
                )
                return
            
            # Обработка дополнительного меню
            if message.text in ["Старт", "Меню", "Хелп"]:
                self.handle_additional_menu(message)
                return
            
            # Обработка нажатий на плашки основного меню
            if message.text in ["🤖 Управление", "📝 Редактировать", "🧪 Тесты", "📊 Статус", "⚙️ Настройки", "❓ Помощь"]:
                self.handle_menu_button(message)
                return
            
            # Обработка подменю управления
            if message.text in ["🚀 Запустить", "⏸️ Остановить", "📈 Статус бота", "🔙 Назад"]:
                self.handle_management_button(message)
                return
            
            # Обработка подменю редактирования
            if message.text in ["📁 Выбрать файл", "👁️ Просмотреть", "✏️ Редактировать"]:
                self.handle_edit_button(message)
                return
            
            # Обработка подменю тестов
            if message.text in ["⚡ Быстрые тесты", "🔍 Полные тесты", "📊 Тест публикации"]:
                self.handle_tests_button(message)
                return
            
            # Обработка подменю статуса
            if message.text in ["📈 Статистика", "⚠️ Ошибки", "📊 Дашборд"]:
                self.handle_status_button(message)
                return
            
            # Обработка подменю настроек
            if message.text in ["🔐 Защита:", "🔑 Сменить пароль", "🗝️ Вкл/Выкл защиту"] or "Защита:" in message.text:
                self.handle_settings_button(message)
                return
            
            # Обработка команды "Назад"
            if message.text == "🔙 Назад":
                keyboard = self.control_manager.create_menu_keyboard()
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="🎛️ <b>Главное меню</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                return
            
            # Обработка паролей и состояний
            user_id = message.chat.id
            if user_id in self.control_manager.user_states:
                user_state = self.control_manager.user_states[user_id]
                
                if user_state.get("awaiting_password"):
                    password = message.text
                    if self.control_manager.authenticate_user(user_id, password):
                        action = user_state.get("action", "")
                        if action == "toggle_protection":
                            new_status = self.control_manager.toggle_protection()
                            status_text = "✅ Включена" if new_status else "❌ Выключена"
                            self.bot.send_message(chat_id=user_id, text=f"<b>🔐 Защита {status_text}</b>", parse_mode='HTML')
                        elif action == "change_password":
                            self.bot.send_message(chat_id=user_id, text="<b>🔑 Введите новый пароль:</b>", parse_mode='HTML')
                            self.control_manager.user_states[user_id] = {"awaiting_new_password": True}
                        elif action == "start_bot":
                            self.handle_start_bot(message)
                        elif action == "stop_bot":
                            self.handle_stop_bot(message)
                        elif action == "edit_file":
                            self.handle_file_edit(message, user_state.get("file_path"))
                    else:
                        self.bot.send_message(chat_id=user_id, text="<b>❌ Неверный пароль</b>", parse_mode='HTML')
                    del self.control_manager.user_states[user_id]
                    return
                
                elif user_state.get("awaiting_new_password"):
                    new_password = message.text
                    self.control_manager.change_password(new_password)
                    self.bot.send_message(chat_id=user_id, text="<b>✅ Пароль изменен</b>", parse_mode='HTML')
                    self.control_manager.log_action(user_id, "security_change", "Смена пароля")
                    del self.control_manager.user_states[user_id]
                    return
                
                elif user_state.get("awaiting_file_content"):
                    file_path = user_state.get("file_path")
                    new_content = message.text
                    self.handle_file_save(message, file_path, new_content)
                    del self.control_manager.user_states[user_id]
                    return
            
            # Обработка ответов администратора на посты
            self.process_admin_reply(message)
        
        # Настройка обработчика inline кнопок
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_inline_callback(call):
            self.handle_inline_button(call)
        
        logger.info("✅ Обработчики сообщений и inline кнопок настроены")
        return handle_all_messages

    def handle_additional_menu(self, message):
        """Обрабатывает дополнительные команды меню"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            button_text = message.text
            
            if button_text == "Старт":
                self.handle_start_command(message)
            elif button_text == "Меню":
                keyboard = self.control_manager.create_menu_keyboard()
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="<b>🎛️ ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ</b>\n\n<b>Выберите раздел:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            elif button_text == "Хелп":
                self.handle_help_command(message)
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки дополнительного меню: {e}")

    def handle_start_command(self, message):
        """Обрабатывает команду /start"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            welcome_text = """
<b>🤖 Добро пожаловать в систему управления ботом!</b>

🔧 <b>Основные функции:</b>
• Автоматическая генерация постов
• Модерация через inline кнопки
• Управление через меню
• Редактирование кода
• Тестирование системы

🎯 <b>Быстрый старт:</b>
1. Используйте кнопку <b>"Меню"</b> слева для открытия дополнительного меню
2. Используйте кнопку <b>"Сообщение"</b> для отправки текста
3. Посты генерируются автоматически в 09:00, 14:00, 19:00 (МСК)

📝 <b>Основные команды:</b>
• <b>Старт</b> - это сообщение
• <b>Меню</b> - открыть главное меню управления
• <b>Хелп</b> - помощь и инструкции

<b>🚀 Бот готов к работе!</b>
            """
            self.bot.send_message(
                chat_id=message.chat.id,
                text=welcome_text,
                parse_mode='HTML',
                reply_markup=self.left_menu_keyboard
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
• Модерация через inline кнопки
• Управление через меню плашек
• Редактирование кода через GitHub API
• Тестирование системы
• Мониторинг статуса

<b>📝 Основные команды:</b>
• <b>Старт</b> - запуск бота и главное меню
• <b>Меню</b> - открыть меню управления
• <b>Хелп</b> - это сообщение

<b>🎯 Inline кнопки под постами:</b>
✅ Опубликовать - одобрить и опубликовать пост
❌ Отклонить - отклонить пост
📝 Переделать текст - перегенерировать только текст
🔄 Переделать полностью - полная перегенерация
🖼️ Заменить фото - найти новое изображение

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

    def handle_menu_command(self, message):
        """Обрабатывает команду /menu"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                logger.debug(f"Попытка доступа к меню не от администратора: {message.chat.id}")
                return
            
            keyboard = self.control_manager.create_menu_keyboard()
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="<b>🎛️ ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ</b>\n\n<b>Выберите раздел:</b>",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            self.control_manager.log_action(message.chat.id, "menu_access", "Открыто главное меню")
        except Exception as e:
            logger.error(f"💥 Ошибка обработки команды /menu: {e}")

    def handle_menu_button(self, message):
        """Обрабатывает нажатия на плашки меню"""
        try:
            if str(message.chat.id) != ADMIN_CHAT_ID:
                return
            
            button_text = message.text
            user_id = message.chat.id
            
            if button_text == "🤖 Управление":
                keyboard = self.control_manager.create_management_submenu()
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>⚙️ Управление ботом</b>\n\n<b>Выберите действие:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                self.control_manager.log_action(user_id, "menu_navigation", "Переход в Управление")
            
            elif button_text == "📝 Редактировать":
                keyboard = self.control_manager.create_edit_submenu()
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>📝 Редактирование кода</b>\n\n<b>Выберите действие:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                self.control_manager.log_action(user_id, "menu_navigation", "Переход в Редактирование")
            
            elif button_text == "🧪 Тесты":
                keyboard = self.control_manager.create_tests_submenu()
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>🧪 Тестирование</b>\n\n<b>Выберите тип тестов:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                self.control_manager.log_action(user_id, "menu_navigation", "Переход в Тесты")
            
            elif button_text == "📊 Статус":
                keyboard = self.control_manager.create_status_submenu()
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>📊 Статус системы</b>\n\n<b>Выберите информацию:</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                self.control_manager.log_action(user_id, "menu_navigation", "Переход в Статус")
            
            elif button_text == "⚙️ Настройки":
                keyboard = self.control_manager.create_settings_submenu()
                protection_status = "✅ Включена" if self.control_manager.security_settings["password_protection"] else "❌ Выключена"
                self.bot.send_message(
                    chat_id=user_id,
                    text=f"<b>⚙️ Настройки</b>\n\n<b>Защита:</b> {protection_status}\n<b>Сессия:</b> {self.control_manager.security_settings['session_duration']} часов",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                self.control_manager.log_action(user_id, "menu_navigation", "Переход в Настройки")
            
            elif button_text == "❓ Помощь":
                self.handle_help_command(message)
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки меню: {e}")

    def handle_management_button(self, message):
        """Обрабатывает кнопки подменю управления"""
        try:
            button_text = message.text
            user_id = message.chat.id
            
            if button_text == "🔙 Назад":
                keyboard = self.control_manager.create_menu_keyboard()
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>🎛️ Главное меню</b>",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            elif button_text == "🚀 Запустить":
                # Проверка парольной защиты
                if not self.control_manager.check_password_protection(user_id):
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🔐 Требуется аутентификация. Отправьте пароль:</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.user_states[user_id] = {"awaiting_password": True, "action": "start_bot"}
                    return
                
                self.handle_start_bot(message)
                
            elif button_text == "⏸️ Остановить":
                if not self.control_manager.check_password_protection(user_id):
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🔐 Требуется аутентификация. Отправьте пароль:</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.user_states[user_id] = {"awaiting_password": True, "action": "stop_bot"}
                    return
                
                self.handle_stop_bot(message)
                
            elif button_text == "📈 Статус бота":
                status_text = self.get_bot_status()
                self.bot.send_message(
                    chat_id=user_id,
                    text=status_text,
                    parse_mode='HTML'
                )
                self.control_manager.log_action(user_id, "bot_control", "Просмотр статуса")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки управления: {e}")

    def handle_start_bot(self, message):
        """Обрабатывает запуск бота"""
        try:
            result = self.github_manager.manage_workflow("enable", "main.yml")
            if "error" not in result:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="<b>✅ Бот запущен. Workflow активирован.</b>",
                    parse_mode='HTML'
                )
                self.control_manager.log_action(message.chat.id, "bot_control", "Запуск бота")
            else:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>❌ Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}",
                    parse_mode='HTML'
                )
        except Exception as e:
            self.bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>❌ Ошибка запуска:</b> {str(e)}",
                parse_mode='HTML'
            )

    def handle_stop_bot(self, message):
        """Обрабатывает остановку бота"""
        try:
            result = self.github_manager.manage_workflow("disable", "main.yml")
            if "error" not in result:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text="<b>⏸️ Бот остановлен. Workflow отключен.</b>",
                    parse_mode='HTML'
                )
                self.control_manager.log_action(message.chat.id, "bot_control", "Остановка бота")
            else:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>❌ Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}",
                    parse_mode='HTML'
                )
        except Exception as e:
            self.bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>❌ Ошибка остановки:</b> {str(e)}",
                parse_mode='HTML'
            )

    def handle_edit_button(self, message):
        """Обрабатывает кнопки редактирования"""
        try:
            button_text = message.text
            user_id = message.chat.id
            
            if button_text == "📁 Выбрать файл":
                files_list = """
<b>📁 Доступные файлы:</b>
• <code>github_bot.py</code> - основной файл бота
• <code>requirements.txt</code> - зависимости
• <code>post_history.json</code> - история постов
• <code>image_history.json</code> - история изображений

<b>Отправьте имя файла для редактирования.</b>
                """
                self.bot.send_message(
                    chat_id=user_id,
                    text=files_list,
                    parse_mode='HTML'
                )
                self.control_manager.user_states[user_id] = {"awaiting_file_selection": True}
                
            elif button_text == "👁️ Просмотреть":
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>Отправьте имя файла для просмотра:</b>",
                    parse_mode='HTML'
                )
                self.control_manager.user_states[user_id] = {"awaiting_file_view": True}
                
            elif button_text == "✏️ Редактировать":
                if not self.control_manager.check_password_protection(user_id):
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🔐 Требуется аутентификация. Отправьте пароль:</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.user_states[user_id] = {"awaiting_password": True, "action": "edit_file"}
                    return
                
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>Отправьте имя файла для редактирования:</b>",
                    parse_mode='HTML'
                )
                self.control_manager.user_states[user_id] = {"awaiting_file_edit": True}
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки редактирования: {e}")

    def handle_file_edit(self, message, file_path=None):
        """Обрабатывает редактирование файла"""
        try:
            if not file_path:
                file_path = message.text
            
            content = self.github_manager.get_file_content(file_path)
            if content:
                # Обрезаем длинный контент для Telegram
                if len(content) > 4000:
                    preview = content[:4000] + "\n\n... (файл слишком большой, показаны первые 4000 символов)"
                else:
                    preview = content
                
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>📄 Содержимое файла {file_path}:</b>\n\n<pre><code class='language-python'>{preview}</code></pre>\n\n<b>Отправьте новое содержимое файла:</b>",
                    parse_mode='HTML'
                )
                self.control_manager.user_states[message.chat.id] = {
                    "awaiting_file_content": True,
                    "file_path": file_path
                }
            else:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>❌ Не удалось загрузить файл {file_path}</b>",
                    parse_mode='HTML'
                )
        except Exception as e:
            self.bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>❌ Ошибка:</b> {str(e)}",
                parse_mode='HTML'
            )

    def handle_file_save(self, message, file_path, new_content):
        """Сохраняет изменения в файле"""
        try:
            result = self.github_manager.edit_file(
                file_path, 
                new_content, 
                f"Редактирование через Telegram от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            if "error" not in result:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>✅ Файл {file_path} успешно обновлен!</b>",
                    parse_mode='HTML'
                )
                self.control_manager.log_action(message.chat.id, "file_edit", f"Редактирование {file_path}")
            else:
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>❌ Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}",
                    parse_mode='HTML'
                )
        except Exception as e:
            self.bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>❌ Ошибка сохранения:</b> {str(e)}",
                parse_mode='HTML'
            )

    def handle_tests_button(self, message):
        """Обрабатывает кнопки тестов"""
        try:
            button_text = message.text
            user_id = message.chat.id
            
            if button_text == "⚡ Быстрые тесты":
                result = self.github_manager.run_tests("quick")
                if "error" not in result:
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🧪 Быстрые тесты запущены. Результат через 30 секунд.</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.log_action(user_id, "tests", "Запуск быстрых тестов")
                else:
                    self.bot.send_message(
                        chat_id=user_id,
                        text=f"<b>❌ Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}",
                        parse_mode='HTML'
                    )
                    
            elif button_text == "🔍 Полные тесты":
                result = self.github_manager.run_tests("full")
                if "error" not in result:
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🧪 Полные тесты запущены. Результат через 2-3 минуты.</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.log_action(user_id, "tests", "Запуск полных тестов")
                else:
                    self.bot.send_message(
                        chat_id=user_id,
                        text=f"<b>❌ Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}",
                        parse_mode='HTML'
                    )
                    
            elif button_text == "📊 Тест публикации":
                # Запускаем тестовый пост
                now = self.get_moscow_time()
                current_hour = now.hour
                
                if 5 <= current_hour < 12:
                    slot_time = "09:00"
                elif 12 <= current_hour < 17:
                    slot_time = "14:00"
                else:
                    slot_time = "19:00"
                
                slot_style = self.time_styles[slot_time]
                
                self.bot.send_message(
                    chat_id=user_id,
                    text=f"<b>🧪 Запускаю тестовую публикацию для слота {slot_time}...</b>",
                    parse_mode='HTML'
                )
                
                success = self.create_and_send_posts(slot_time, slot_style, is_test=True)
                
                if success:
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>✅ Тест публикации пройден успешно!</b>",
                        parse_mode='HTML'
                    )
                else:
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>❌ Тест публикации не пройден. Проверьте логи.</b>",
                        parse_mode='HTML'
                    )
                
                self.control_manager.log_action(user_id, "tests", "Тест публикации")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки тестов: {e}")

    def handle_status_button(self, message):
        """Обрабатывает кнопки статуса"""
        try:
            button_text = message.text
            user_id = message.chat.id
            
            if button_text == "📈 Статистика":
                stats = self.get_post_statistics()
                self.bot.send_message(
                    chat_id=user_id,
                    text=stats,
                    parse_mode='HTML'
                )
                self.control_manager.log_action(user_id, "status", "Просмотр статистики")
                
            elif button_text == "⚠️ Ошибки":
                errors = self.get_error_log()
                self.bot.send_message(
                    chat_id=user_id,
                    text=errors,
                    parse_mode='HTML'
                )
                self.control_manager.log_action(user_id, "status", "Просмотр ошибок")
                
            elif button_text == "📊 Дашборд":
                dashboard = self.get_dashboard()
                self.bot.send_message(
                    chat_id=user_id,
                    text=dashboard,
                    parse_mode='HTML'
                )
                self.control_manager.log_action(user_id, "status", "Просмотр дашборда")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки статуса: {e}")

    def get_post_statistics(self):
        """Возвращает статистику постов"""
        today = self.get_moscow_time().strftime("%Y-%m-%d")
        sent_today = len(self.post_history.get("sent_slots", {}).get(today, []))
        pending = len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.PENDING])
        published = len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.PUBLISHED])
        rejected = len([p for p in self.pending_posts.values() if p.get('status') == PostStatus.REJECTED])
        
        stats = f"""
<b>📊 СТАТИСТИКА ПОСТОВ</b>

<b>📅 Сегодня ({today}):</b>
• Отправлено слотов: {sent_today}
• Ожидают модерации: {pending}
• Опубликовано: {published}
• Отклонено: {rejected}

<b>📈 Общая статистика:</b>
• Всего тем: {len(self.themes)}
• Форматы подачи: {len(self.text_formats)}
• Использовано изображений: {len(self.image_history.get('used_images', []))}

<b>⏰ Следующий слот:</b>
{self.get_next_slot_time()}
        """
        return stats

    def get_error_log(self):
        """Возвращает лог ошибок"""
        try:
            error_count = 0
            recent_errors = []
            
            # Читаем файл логов
            if os.path.exists("management_log.json"):
                with open("management_log.json", 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                    errors = [entry for entry in log_data.get("actions", []) 
                             if "error" in entry.get("action", "").lower() or 
                                "ошибка" in entry.get("details", "").lower()]
                    error_count = len(errors)
                    recent_errors = errors[-5:]  # Последние 5 ошибок
            
            errors_text = f"""
<b>⚠️ ЛОГ ОШИБОК</b>

<b>📊 Статистика:</b>
• Всего ошибок: {error_count}
• Последние 5 ошибок:

"""
            for error in recent_errors:
                errors_text += f"• <b>{error.get('timestamp', '')}</b>: {error.get('action', '')} - {error.get('details', '')}\n"
            
            if error_count == 0:
                errors_text += "\n<b>✅ Ошибок не обнаружено!</b>"
            
            return errors_text
        except Exception as e:
            return f"<b>❌ Ошибка при чтении лога:</b> {str(e)}"

    def get_dashboard(self):
        """Возвращает дашборд"""
        now = self.get_moscow_time()
        
        dashboard = f"""
<b>📊 ДАШБОРД СИСТЕМЫ</b>

<b>⏰ Время системы:</b>
• МСК: {now.strftime('%H:%M:%S')}
• Дата: {now.strftime('%d.%m.%Y')}

<b>🤖 Статус бота:</b>
• Polling: {'✅ Активен' if hasattr(self, 'polling_started') and self.polling_started else '❌ Не активен'}
• Постов в обработке: {len(self.pending_posts)}
• Последний пост: {self.post_history.get('last_post', 'Нет данных')}

<b>🔐 Безопасность:</b>
• Защита: {'✅ Включена' if self.control_manager.security_settings['password_protection'] else '❌ Выключена'}
• Активные сессии: {len(self.control_manager.user_sessions)}

<b>📈 Производительность:</b>
• API Gemini: {'✅ Доступен' if GEMINI_API_KEY else '❌ Не доступен'}
• API Pexels: {'✅ Доступен' if PEXELS_API_KEY else '❌ Не доступен'}
• GitHub API: {'✅ Доступен' if GITHUB_TOKEN else '❌ Не доступен'}

<b>🎯 Следующие действия:</b>
{self.get_next_slot_time()}
        """
        return dashboard

    def get_next_slot_time(self):
        """Возвращает время следующего слота"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        if current_time < "09:00":
            next_slot = "09:00"
        elif current_time < "14:00":
            next_slot = "14:00"
        elif current_time < "19:00":
            next_slot = "19:00"
        else:
            next_slot = "09:00 (завтра)"
        
        return f"• Следующий слот: {next_slot}"

    def handle_settings_button(self, message):
        """Обрабатывает кнопки настроек"""
        try:
            button_text = message.text
            user_id = message.chat.id
            
            if "Защита:" in button_text:
                protection_status = "✅ Включена" if self.control_manager.security_settings["password_protection"] else "❌ Выключена"
                self.bot.send_message(
                    chat_id=user_id,
                    text=f"<b>🔐 Текущие настройки безопасности:</b>\n\n• <b>Защита:</b> {protection_status}\n• <b>Длительность сессии:</b> {self.control_manager.security_settings['session_duration']} часов\n• <b>Хэш пароля:</b> {self.control_manager.security_settings['password_hash'][:16]}...",
                    parse_mode='HTML'
                )
            
            elif button_text == "🗝️ Вкл/Выкл защиту":
                if not self.control_manager.check_password_protection(user_id):
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🔐 Требуется аутентификация. Отправьте пароль:</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.user_states[user_id] = {"awaiting_password": True, "action": "toggle_protection"}
                    return
                
                # Переключение защиты
                new_status = self.control_manager.toggle_protection()
                status_text = "✅ Включена" if new_status else "❌ Выключена"
                self.bot.send_message(
                    chat_id=user_id,
                    text=f"<b>🔐 Защита {status_text}</b>",
                    parse_mode='HTML'
                )
                action = "включена" if new_status else "выключена"
                self.control_manager.log_action(user_id, "security_change", f"Защита {action}")
            
            elif button_text == "🔑 Сменить пароль":
                if not self.control_manager.check_password_protection(user_id):
                    self.bot.send_message(
                        chat_id=user_id,
                        text="<b>🔐 Требуется аутентификация. Отправьте пароль:</b>",
                        parse_mode='HTML'
                    )
                    self.control_manager.user_states[user_id] = {"awaiting_password": True, "action": "change_password"}
                    return
                
                self.bot.send_message(
                    chat_id=user_id,
                    text="<b>🔑 Введите новый пароль:</b>",
                    parse_mode='HTML'
                )
                self.control_manager.user_states[user_id] = {"awaiting_new_password": True}
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки кнопки настроек: {e}")

    def create_inline_keyboard(self):
        """Создает inline клавиатуру с кнопками модерации"""
        keyboard = InlineKeyboardMarkup(row_width=3)
        buttons = [
            InlineKeyboardButton("✅ Опубликовать", callback_data="approve"),
            InlineKeyboardButton("❌ Отклонить", callback_data="reject"),
            InlineKeyboardButton("📝 Переделать текст", callback_data="edit_text"),
            InlineKeyboardButton("🔄 Переделать полностью", callback_data="edit_full"),
            InlineKeyboardButton("🖼️ Заменить фото", callback_data="replace_photo")
        ]
        keyboard.add(*buttons)
        return keyboard

    def handle_inline_button(self, call):
        """Обрабатывает нажатия inline кнопок"""
        try:
            message_id = call.message.message_id
            user_id = call.from_user.id
            
            if str(user_id) != ADMIN_CHAT_ID:
                self.bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            # Получаем данные поста
            if message_id not in self.pending_posts:
                self.bot.answer_callback_query(call.id, "❌ Пост не найден")
                return
            
            post_data = self.pending_posts[message_id]
            button_type = call.data
            
            # Обновляем сообщение с результатом
            if button_type == "approve":
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=f"{post_data.get('text', '')}\n\n<b>✅ Опубликовано</b>",
                    parse_mode='HTML'
                )
                self.handle_approval(message_id, post_data, None)
                self.bot.answer_callback_query(call.id, "✅ Пост опубликован")
                self.control_manager.log_action(user_id, "post_moderation", "Одобрен через inline кнопку")
            
            elif button_type == "reject":
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=f"{post_data.get('text', '')}\n\n<b>❌ Отклонено</b>",
                    parse_mode='HTML'
                )
                self.handle_rejection(message_id, post_data, None, reason="Отклонено через inline кнопку")
                self.bot.answer_callback_query(call.id, "❌ Пост отклонен")
                self.control_manager.log_action(user_id, "post_moderation", "Отклонен через inline кнопку")
            
            elif button_type == "edit_text":
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=f"{post_data.get('text', '')}\n\n<b>📝 Переделываю текст...</b>",
                    parse_mode='HTML'
                )
                self.handle_edit_request(message_id, post_data, "переделай текст", None)
                self.bot.answer_callback_query(call.id, "📝 Переделываю текст")
                self.control_manager.log_action(user_id, "post_moderation", "Редактирование текста через inline кнопку")
            
            elif button_type == "edit_full":
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=f"{post_data.get('text', '')}\n\n<b>🔄 Полная перегенерация...</b>",
                    parse_mode='HTML'
                )
                self.handle_edit_request(message_id, post_data, "переделай полностью", None)
                self.bot.answer_callback_query(call.id, "🔄 Переделываю полностью")
                self.control_manager.log_action(user_id, "post_moderation", "Полная перегенерация через inline кнопку")
            
            elif button_type == "replace_photo":
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=f"{post_data.get('text', '')}\n\n<b>🖼️ Ищу новое фото...</b>",
                    parse_mode='HTML'
                )
                self.handle_edit_request(message_id, post_data, "замени фото", None)
                self.bot.answer_callback_query(call.id, "🖼️ Заменяю фото")
                self.control_manager.log_action(user_id, "post_moderation", "Замена фото через inline кнопку")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки inline кнопки: {e}")
            try:
                self.bot.answer_callback_query(call.id, "❌ Ошибка обработки")
            except:
                pass

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

<b>🔐 Безопасность:</b>
• Защита: {'✅ Включена' if self.control_manager.security_settings['password_protection'] else '❌ Выключена'}
• Активные сессии: {len(self.control_manager.user_sessions)}

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
            
            # Проверяем состояния пользователя
            user_id = message.chat.id
            if user_id in self.control_manager.user_states:
                user_state = self.control_manager.user_states[user_id]
                
                if user_state.get("awaiting_file_selection"):
                    file_name = message.text
                    self.handle_file_edit(message, file_name)
                    del self.control_manager.user_states[user_id]
                    return
                
                elif user_state.get("awaiting_file_view"):
                    file_name = message.text
                    content = self.github_manager.get_file_content(file_name)
                    if content:
                        if len(content) > 4000:
                            content = content[:4000] + "\n\n... (файл слишком большой, показаны первые 4000 символов)"
                        self.bot.send_message(
                            chat_id=user_id,
                            text=f"<b>📄 Содержимое файла {file_name}:</b>\n\n<pre><code>{content}</code></pre>",
                            parse_mode='HTML'
                        )
                    else:
                        self.bot.send_message(
                            chat_id=user_id,
                            text=f"<b>❌ Не удалось загрузить файл {file_name}</b>",
                            parse_mode='HTML'
                        )
                    del self.control_manager.user_states[user_id]
                    return
                
                elif user_state.get("awaiting_file_edit"):
                    file_name = message.text
                    self.handle_file_edit(message, file_name)
                    del self.control_manager.user_states[user_id]
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
                    parse_mode='HTML',
                    reply_markup=self.create_inline_keyboard()
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=post_text,
                    parse_mode='HTML',
                    reply_markup=self.create_inline_keyboard()
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
                
                # Пропускаем строки с явными вводными фразами
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
        
        # ГАРАНТИЯ: Если нет хештегов - добавляем их принудительно
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
            inline_keyboard = self.create_inline_keyboard()
            
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=tg_text[:1024],
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=tg_text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
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
            inline_keyboard = self.create_inline_keyboard()
            
            if image_url:
                sent_message = self.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=image_url,
                    caption=zen_text[:1024],
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            else:
                sent_message = self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=zen_text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
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
   📌 Используйте кнопки под постом или ответьте «ок»

<b>📝 2. Дзен пост (без эмодзи)</b>
   🎯 Канал: {ZEN_CHANNEL}
   🕒 Время: {slot_time} МСК
   📏 Символов: {len(zen_text)}
   #️⃣ Хештеги: {zen_hashtags_count} шт.
   📌 Используйте кнопки под постом или ответьте «ок»

<b>🎯 Inline кнопки:</b>
• ✅ Опубликовать - одобрить и опубликовать
• ❌ Отклонить - отклонить пост
• 📝 Переделать текст - перегенерировать текст
• 🔄 Переделать полностью - полная перегенерация
• 🖼️ Заменить фото - найти новое изображение

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
            
            logger.info(f"✅ Хештеги перед публикацией: {len(hashtags)} шт.")
            
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

    def run_schedule(self):
        """Запускает расписание публикаций"""
        try:
            logger.info("⏰ Запускаю расписание публикаций")
            self.polling_started = True
            
            # Запускаем polling в отдельном потоке
            polling_thread = threading.Thread(target=self.start_polling_thread, daemon=True)
            polling_thread.start()
            logger.info("✅ Polling запущен в отдельном потоке")
            
            # Основной цикл расписания
            while True:
                try:
                    now = self.get_moscow_time()
                    current_time_str = now.strftime("%H:%M")
                    
                    logger.info(f"⏰ Текущее время (МСК): {current_time_str}")
                    
                    # Проверяем каждый слот
                    for slot_time, slot_style in self.time_styles.items():
                        if current_time_str == slot_time:
                            logger.info(f"🎯 Время слота {slot_time}!")
                            
                            # Проверяем, не был ли уже отправлен этот слот сегодня
                            if not self.was_slot_sent_today(slot_time):
                                logger.info(f"📅 Создаю посты для слота {slot_time}")
                                success = self.create_and_send_posts(slot_time, slot_style)
                                
                                if success:
                                    logger.info(f"✅ Посты для слота {slot_time} отправлены на модерацию")
                                else:
                                    logger.error(f"❌ Ошибка создания постов для слота {slot_time}")
                            else:
                                logger.info(f"⚠️ Слот {slot_time} уже был отправлен сегодня, пропускаю")
                    
                    # Ждем минуту до следующей проверки
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"💥 Ошибка в цикле расписания: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    time.sleep(60)
                    
        except Exception as e:
            logger.error(f"💥 Фатальная ошибка в расписании: {e}")
            import traceback
            logger.error(traceback.format_exc())

def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 Запуск Telegram бота")
        bot = TelegramBot()
        
        logger.info("⏰ Запуск расписания публикаций")
        bot.run_schedule()
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
