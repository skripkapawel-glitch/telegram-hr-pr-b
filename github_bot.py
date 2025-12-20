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
import threading
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
MAIN_CHANNEL = os.environ.get("MAIN_CHANNEL_ID", "@da4a_hr")  # Основной канал (числовой ID или username)
ZEN_CHANNEL = os.environ.get("ZEN_CHANNEL_ID", "@tehdzenm")   # Дзен канал (числовой ID или username)
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
    logger.warning("⚠️ PEXELS_API_KEY не установен! Будут использоваться дефолтные картинки")

if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установен! Укажите ваш chat_id")
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
                logger.error("❌ GitHub токен (MANAGER_GITHUB_TOKEN) не установен, операция невозможна")
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                logger.error("❌ Не указаны репозиторий или владелец")
                return {"error": "Не указаны репозиторий или владелец"}
            
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = session.get(url, headers=self.get_headers())
            if response.status_code == 200:
                content = response.json()
                if "content" in content and content.get("encoding") == "base64":
                    import base64
                    decoded_content = base64.b64decode(content["content"]).decode('utf-8')
                    return decoded_content
                elif "error" in content:
                    logger.error(f"❌ Ошибка GitHub API: {content.get('error', 'Unknown error')}")
                    return {"error": content.get('error', 'Unknown error')}
                else:
                    logger.error(f"❌ Неожиданный формат ответа GitHub API: ключ 'content' отсутствует")
                    return {"error": "Unexpected response format: 'content' key missing"}
            else:
                logger.error(f"❌ Ошибка GitHub API: {response.status_code} - {response.text[:100]}")
                return {"error": f"API error: {response.status_code}"}
            return None
        except Exception as e:
            logger.error(f"❌ Исключение в GitHub API: {e}")
            return {"error": str(e)}
    
    def edit_file(self, file_path, new_content, commit_message):
        """Редактирует файл в репозитории"""
        try:
            if not self.github_token:
                logger.error("❌ GitHub токен (MANAGER_GITHUB_TOKEN) не установен, операция невозможна")
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                logger.error("❌ Не указаны репозиторий или владелец")
                return {"error": "Не указаны репозиторий или владелец"}
            
            # Сначала получаем текущий файл
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = session.get(url, headers=self.get_headers())
            
            if response.status_code != 200:
                logger.error(f"❌ Файл не найден: {response.status_code}")
                return {"error": "Файл не найден"}
            
            current_file = response.json()
            if "error" in current_file:
                logger.error(f"❌ Ошибка GitHub API: {current_file.get('error', 'Unknown error')}")
                return {"error": current_file.get('error', 'Unknown error')}
            
            sha = current_file["sha"]
            
            import base64
            encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
            
            data = {
                "message": commit_message,
                "content": encoded_content,
                "sha": sha
            }
            
            response = session.put(url, headers=self.get_headers(), json=data)
            result = response.json()
            if "error" in result:
                logger.error(f"❌ Ошибка GitHub API при редактировании: {result.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            logger.error(f"❌ Исключение в GitHub API: {e}")
            return {"error": str(e)}
    
    def get_status(self):
        """Получает статус репозитория и workflow"""
        try:
            if not self.github_token:
                logger.error("❌ GitHub токен (MANAGER_GITHUB_TOKEN) не установен, операция невозможна")
                return {"error": "GitHub токен (MANAGER_GITHUB_TOKEN) не установен"}
            
            if not self.repo_owner or not self.repo_name:
                logger.error("❌ Не указаны репозиторий или владелец")
                return {"error": "Не указаны репозиторий или владелец"}
            
            status_info = {}
            
            # Получаем информацию о репозитории
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
            response = session.get(url, headers=self.get_headers())
            if response.status_code == 200:
                repo_info = response.json()
                if "error" in repo_info:
                    logger.error(f"❌ Ошибка GitHub API: {repo_info.get('error', 'Unknown error')}")
                    return {"error": repo_info.get('error', 'Unknown error')}
                status_info["repo"] = {
                    "name": repo_info["name"],
                    "private": repo_info["private"],
                    "updated_at": repo_info["updated_at"],
                    "size": repo_info["size"]
                }
            else:
                logger.error(f"❌ Ошибка GitHub API: {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
            
            # Получаем последние workflow runs
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/runs"
            response = session.get(url, headers=self.get_headers())
            if response.status_code == 200:
                runs = response.json()
                if "error" in runs:
                    logger.error(f"❌ Ошибка GitHub API: {runs.get('error', 'Unknown error')}")
                    return {"error": runs.get('error', 'Unknown error')}
                status_info["workflow_runs"] = runs.get("workflow_runs", [])[:5]
            else:
                logger.error(f"❌ Ошибка GitHub API: {response.status_code}")
                return {"error": f"API error: {response.status_code}"}
            
            return status_info
        except Exception as e:
            logger.error(f"❌ Исключение в GitHub API: {e}")
            return {"error": str(e)}


class TelegramBot:
    def __init__(self, target_slot=None, auto=False):
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
        
        # Трекер для отслеживания опубликованных постов с блокировкой
        self.published_posts_count = 0
        self.publish_lock = threading.Lock()
        
        # Флаг завершения workflow
        self.workflow_complete = False
        self.completion_lock = threading.Lock()
        
        # Флаг остановки polling
        self.stop_polling = False
        self.polling_lock = threading.Lock()
        
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
        
        # ✅ СИСТЕМА ВАРИАТИВНЫХ ЗАВЕРШЕНИЙ ПОСТОВ
        self.conclusions = {
            'zen': {
                'why_important': {
                    'title': 'Почему это важно:',
                    'structure': ['• Контекст:', '• Сдвиг:', '• Импликация:'],
                    'probability': 0.4
                },
                'practical_takeaways': {
                    'title': 'Что из этого следует:',
                    'structure': ['🎯 ', '📊 ', '🚀 '],
                    'probability': 0.3
                },
                'expert_insights': {
                    'title': 'Мнение экспертов:',
                    'structure': ['По данным исследования...', 
                                'Эксперты отмечают...', 
                                'Тренд показывает...'],
                    'probability': 0.29
                },
                'no_special_section': {
                    'title': 'Почему это важно:',
                    'structure': ['• Ключевой момент:'],
                    'probability': 0.01
                }
            },
            'telegram': {
                'key_insights': {
                    'emoji': '💡',
                    'templates': ['Ключевой инсайт:', 'Главный вывод:', 'Самое важное:'],
                    'probability': 0.5
                },
                'action_steps': {
                    'emoji': '🎯',
                    'templates': ['Что делать дальше:', 'Практические шаги:', 'Конкретные действия:'],
                    'probability': 0.4
                },
                'simple_close': {
                    'emoji': '✨',
                    'templates': [],
                    'probability': 0.1
                }
            }
        }
        
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
                "Этика AI в кадровых процессаи",
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
                "Нейромаркетинг в PR-кампанияи",
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
        self.target_slot = target_slot
        self.auto = auto
        
        # Поток polling
        self.polling_thread = None
        self.polling_started = False
        
        # Кэш для хештегов
        self._hashtags_cache = {}
        
        # Callback обработчики
        self.callback_handlers = {
            "publish": self.handle_approval_from_callback,
            "reject": self.handle_rejection_from_callback,
            "edit_text": lambda msg_id, post_data, call: self.handle_edit_request_from_callback(msg_id, post_data, call, "переделай текст"),
            "edit_photo": lambda msg_id, post_data, call: self.handle_edit_request_from_callback(msg_id, post_data, call, "замени фото"),
            "edit_all": lambda msg_id, post_data, call: self.handle_edit_request_from_callback(msg_id, post_data, call, "переделай полностью"),
            "new_post": self.handle_new_post_request,
            "back_to_main": self.handle_back_to_main
        }

    def create_inline_keyboard(self, row_width=3):
        """Создает inline клавиатуру с улучшенными кнопками"""
        keyboard = InlineKeyboardMarkup(row_width=row_width)
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
        return keyboard

    def is_admin_message(self, message):
        """Проверяет, что сообщение от администратора"""
        return str(message.chat.id) == ADMIN_CHAT_ID

    def load_data(self, filename, default_data):
        """Загружает данные из JSON файла"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки {filename}: {e}")
        return default_data

    def save_data(self, filename, data):
        """Сохраняет данные в JSON файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения {filename}: {e}")

    def load_history(self):
        """Загружает историю постов"""
        return self.load_data(self.history_file, {
            "sent_slots": {},
            "last_post": None,
            "formats_used": [],
            "themes_used": [],
            "theme_rotation": [],
            "rejected_slots": {}
        })

    def load_image_history(self):
        """Загружает историю использованных картинок"""
        return self.load_data(self.image_history_file, {
            "used_images": [],
            "last_update": None
        })

    def save_history(self):
        """Сохраняет историю постов"""
        self.save_data(self.history_file, self.post_history)

    def save_image_history(self, image_url):
        """Сохраняет историю использованных картинок"""
        try:
            if image_url and image_url not in self.image_history.get("used_images", []):
                self.image_history.setdefault("used_images", []).append(image_url)
                self.image_history["last_update"] = datetime.now().isoformat()
                self.save_data(self.image_history_file, self.image_history)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения истории картинок: {e}")

    def select_conclusion_type(self, post_type='zen'):
        """Выбирает тип завершения поста"""
        conclusions = self.conclusions.get(post_type, {})
        
        # Взвешенный случайный выбор
        rand = random.random()
        cumulative = 0
        
        for key, config in conclusions.items():
            cumulative += config['probability']
            if rand <= cumulative:
                config['name'] = key
                return config
        
        # Fallback - возвращаем первый тип завершения
        first_key = list(conclusions.keys())[0]
        conclusions[first_key]['name'] = first_key
        return conclusions[first_key]

    def generate_context(self, theme):
        """Генерирует контекст для блока завершения"""
        return f"Сейчас в сфере {theme.lower()} происходит..."

    def generate_shift(self, theme):
        """Генерирует сдвиг для блока завершения"""
        return f"Основной тренд смещается в сторону..."

    def generate_implication(self, theme):
        """Генерирует импликацию для блока завершения"""
        return f"Это приведет к изменениям в..."

    def generate_practical_tip(self, theme):
        """Генерирует практический совет"""
        return f"Начните с малого: внедрите одну полезную привычку"

    def generate_stat_insight(self, theme):
        """Генерирует статистический инсайт"""
        return f"Согласно данным, эффективность возрастает на 30%"

    def generate_action_step(self, theme):
        """Генерирует шаг к действию"""
        return f"Попробуйте применить это на практике уже сегодня"

    def generate_warning(self, theme):
        """Генерирует предупреждение"""
        return f"Избегайте распространённой ошибки: не торопитесь"

    def generate_conclusion_block(self, conclusion_type, theme):
        """Генерирует блок завершения поста"""
        if not conclusion_type:
            # Если тип завершения не указан, используем 'why_important' как fallback
            conclusion_type = self.conclusions['zen']['why_important']
            conclusion_type['name'] = 'why_important'
        
        if conclusion_type.get('title') is None:
            # Для случая 'no_special_section' всё равно добавляем минимальный блок
            conclusion_type = self.conclusions['zen']['why_important']
            conclusion_type['name'] = 'why_important'
        
        conclusion = conclusion_type['title'] + "\n"
        
        if conclusion_type['name'] == 'why_important':
            # Генерация структуры "Контекст-Сдвиг-Импликация"
            conclusions = [
                f"• Контекст: {self.generate_context(theme)}",
                f"• Сдвиг: {self.generate_shift(theme)}", 
                f"• Импликация: {self.generate_implication(theme)}"
            ]
            conclusion += "\n".join(conclusions)
        
        elif conclusion_type['name'] == 'practical_takeaways':
            # Практические выводы с эмодзи
            takeaways = random.sample([
                f"🎯 {self.generate_practical_tip(theme)}",
                f"📊 {self.generate_stat_insight(theme)}",
                f"🚀 {self.generate_action_step(theme)}",
                f"⚠️ {self.generate_warning(theme)}"
            ], 3)
            conclusion += "\n".join(takeaways)
        
        elif conclusion_type['name'] == 'expert_insights':
            # Экспертное мнение
            insights = random.sample(conclusion_type['structure'], 2)
            conclusion += "\n\n".join(insights)
        
        elif conclusion_type['name'] == 'no_special_section':
            # Упрощённое завершение с минимальным блоком
            conclusion = f"{conclusion_type['title']}\n{conclusion_type['structure'][0]} {self.generate_practical_tip(theme)}"
        
        return conclusion + "\n"

    def initialize_and_run_posts(self):
        """Инициализация и запуск генерации постов"""
        logger.info("🚀 Инициализация бота и запуск генерации постов...")
        
        # Запускаем проверку API
        self.check_all_apis()
        
        if self.target_slot:  # Если указан конкретный слот (--slot HH:MM)
            slot_style = self.time_styles.get(self.target_slot)
            if slot_style:
                self.create_and_send_posts(self.target_slot, slot_style)
            else:
                logger.error(f"❌ Указан неверный слот: {self.target_slot}")
                sys.exit(1)
            return
        
        # Автоматический или ручной запуск
        now = self.get_moscow_time()
        
        if self.auto:
            logger.info(f"🤖 АВТОМАТИЧЕСКИЙ ЗАПУСК (по расписанию) в {now.strftime('%H:%M')} МСК")
            slot_time, slot_style = self.get_slot_for_time(now, auto=True)
            if not slot_time:
                logger.info("⏰ Не время для автопубликации (нет слота ±10 минут)")
                sys.exit(0)  # Корректный выход без ошибки
        else:
            logger.info(f"📅 РУЧНОЙ ЗАПУСК в {now.strftime('%H:%M')} МСК")
            slot_time, slot_style = self.get_slot_for_time(now)
        
        if slot_time and slot_style:
            logger.info(f"✅ Выбран слот: {slot_time} ({slot_style['name']})")
            self.create_and_send_posts(slot_time, slot_style)
        else:
            logger.error("❌ Не удалось определить слот для запуска")
            sys.exit(1)

    def get_slot_for_time(self, target_time, auto=False):
        """Определяет слот для заданного времени"""
        try:
            hour = target_time.hour
            minute = target_time.minute
            
            logger.info(f"⏰ Определяем слот для времени {hour:02d}:{minute:02d} МСК")
            
            # Ночная зона: 20:00-03:59 → Вечерний слот (20:00) ВЧЕРА
            if (hour >= 20) or (hour < 4):
                logger.info(f"🌙 Ночная зона (20:00-03:59) → Вечерний слот (20:00) вчерашнего дня")
                return "20:00", self.time_styles.get("20:00")
            
            # Утренняя зона: 04:00-10:59 → Утренний слот (11:00) СЕГОДНЯ
            if hour >= 4 and hour < 11:
                logger.info(f"🌅 Утренняя зона (04:00-10:59) → Утренний слот (11:00) сегодняшнего дня")
                return "11:00", self.time_styles.get("11:00")
            
            current_total_minutes = hour * 60 + minute
            
            # Для автопостинга ищем слот в ближайшие ±10 минут
            if auto:
                for slot_time, slot_style in self.time_styles.items():
                    slot_hour, slot_minute = map(int, slot_time.split(':'))
                    slot_total_minutes = slot_hour * 60 + slot_minute
                    
                    time_diff = abs(current_total_minutes - slot_total_minutes)
                    if time_diff <= 10:
                        logger.info(f"✅ Найден слот {slot_time} (разница: {time_diff} мин)")
                        return slot_time, slot_style
                logger.info("⏰ Не найден слот в пределах ±10 минут")
                return None, None
            
            # Для ручного запуска - ближайший будущий слот
            logger.info(f"☀️ Дневная/вечерняя зона (11:00-19:59) → Ищем ближайший будущий слот")
            
            future_slots = []
            for slot_time in self.time_styles.keys():
                slot_hour, slot_minute = map(int, slot_time.split(':'))
                slot_total_minutes = slot_hour * 60 + slot_minute
                
                if slot_total_minutes > current_total_minutes:
                    future_slots.append((slot_time, slot_total_minutes))
            
            if future_slots:
                future_slots.sort(key=lambda x: x[1])
                slot_time = future_slots[0][0]
                return slot_time, self.time_styles.get(slot_time)
            
            # Если все будущие слоты прошли, берем утренний слот (11:00) на завтра
            logger.info("⚠️ Все слоты на сегодня прошли → Утренний слот (11:00) на завтра")
            return "11:00", self.time_styles.get("11:00")
            
        except Exception as e:
            logger.error(f"❌ Ошибка определения слота для времени: {e}")
            return None, None

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

    def generate_with_gemma(self, prompt):
        """Генерация через Gemma 3 модель"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.85,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": 2200,  # Жесткий лимит для двух постов
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
            if not self.is_admin_message(message):
                logger.debug(f"Сообщение не от администратора: {message.chat.id}")
                return
            
            self.process_admin_reply(message)
        
        # Обработчик callback-запросов от inline кнопок
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            self.handle_callback(call)
        
        logger.info("✅ Обработчики сообщений и callback-запросов настроены")

    def handle_callback(self, call):
        """Обрабатывает callback-запросы от inline кнопок"""
        try:
            if not call or not call.message:
                logger.error("❌ Callback без сообщения")
                return
            
            if not self.is_admin_message(call.message):
                logger.debug(f"Callback не от администратора: {call.message.chat.id}")
                return
            
            message_id = call.message.message_id
            callback_data = call.data
            
            logger.info(f"🔄 Обработка callback: {callback_data} для сообщения {message_id}")
            
            if message_id not in self.pending_posts:
                logger.warning(f"⚠️ Callback на несуществующий пост: {message_id}")
                return
            
            post_data = self.pending_posts[message_id]
            
            # Обработка темы отдельно
            if callback_data.startswith("theme_"):
                self.handle_theme_selection(message_id, post_data, call, callback_data)
                return
            
            # Обработка остальных callback через словарь
            if callback_data in self.callback_handlers:
                self.callback_handlers[callback_data](message_id, post_data, call)
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки callback: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_new_post_request(self, message_id, post_data, call):
        """Обрабатывает запрос на создание нового поста"""
        try:
            self.bot.answer_callback_query(call.id, "🎯 Выберите тему для нового поста...")
            logger.info(f"🎯 Запрос на новый пост для сообщения {message_id}")
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            for theme in self.themes:
                keyboard.add(InlineKeyboardButton(
                    f"🎯 {theme}",
                    callback_data=f"theme_{theme}"
                ))
            
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            try:
                caption = f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n" \
                         f"Выберите одну из доступных тем. После выбора темы будет сгенерирован " \
                         f"новый пост с новой фотографией и вариантами подачи.\n\n" \
                         f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>"
                
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=caption,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                
                post_data['original_state'] = {
                    'text': post_data.get('text', ''),
                    'keyboard_state': 'theme_selection'
                }
                self.pending_posts[message_id] = post_data
                
            except Exception as e:
                logger.warning(f"⚠️ Не удалось редактировать сообщение: {e}")
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=caption,
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
            selected_theme = callback_data.replace("theme_", "")
            self.bot.answer_callback_query(call.id, f"✅ Выбрана тема: {selected_theme}")
            
            logger.info(f"🎯 Выбрана тема для нового поста: {selected_theme} (сообщение: {message_id})")
            
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>🔄 ГЕНЕРИРУЮ НОВЫЙ ПОСТ</b>\n\n"
                     f"<b>🎯 Тема:</b> {selected_theme}\n"
                     f"<b>⏰ Время публикации:</b> {post_data.get('slot_time', '')}\n"
                     f"<b>📝 Создаю пост с новой фотографией и вариантами подачи...</b>",
                parse_mode='HTML'
            )
            
            self.restore_main_buttons(message_id, post_data)
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
            self.restore_main_buttons(message_id, post_data)
            
        except Exception as e:
            logger.error(f"💥 Ошибка возврата к основным кнопкам: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def restore_main_buttons(self, message_id, post_data):
        """Восстанавливает основные кнопки под сообщением"""
        try:
            keyboard = self.create_inline_keyboard()
            
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
            
            new_format = self.get_smart_format(slot_style)
            new_image_url, new_description = self.get_post_image_and_description(selected_theme)
            
            if new_image_url:
                self.save_image_history(new_image_url)
            
            prompt = self.create_detailed_prompt(selected_theme, slot_style, new_format, new_description)
            
            if not prompt:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="<b>❌ Не удалось создать промпт для нового поста.</b>",
                    parse_mode='HTML'
                )
                return
            
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
            
            tg_valid, tg_error = self.validate_post_structure(tg_text, 'telegram')
            zen_valid, zen_error = self.validate_post_structure(zen_text, 'zen')
            
            if not tg_valid or not zen_valid:
                logger.error(f"❌ Ошибка структуры после генерации: Telegram - {tg_error}, Zen - {zen_error}")
                tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=2)
                if not tg_text or not zen_text:
                    self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text="<b>❌ Не удалось сгенерировать корректные тексты после валидации.</b>",
                        parse_mode='HTML'
                    )
                    return
            
            if random.random() < 0.5:
                tg_text = self.add_useful_source(tg_text, selected_theme)
                zen_text = self.add_useful_source(zen_text, selected_theme)
            
            if post_type == 'telegram':
                new_formatted_text = self.format_post_text(tg_text, slot_style, 'telegram')
                channel = MAIN_CHANNEL
            else:
                new_formatted_text = self.format_post_text(zen_text, slot_style, 'zen')
                channel = ZEN_CHANNEL
            
            if not new_formatted_text:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="<b>❌ Не удалось отформатировать новый текст.</b>",
                    parse_mode='HTML'
                )
                return
            
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            keyboard = self.create_inline_keyboard()
            
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
                    self.bot.delete_message(ADMIN_CHAT_ID, original_message_id)
                    sent_message = self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=new_formatted_text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    original_message_id = sent_message.message_id
            
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
            
            try:
                status_text = f"\n\n<b>✅ Опубликовано в {post_data.get('channel', 'канал')}</b>"
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + status_text,
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}{status_text}",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
            post_type = post_data.get('type')
            post_text = post_data.get('text', '')
            image_url = post_data.get('image_url', '')
            channel = post_data.get('channel', '')
            
            logger.info(f"✅ Одобрение поста типа '{post_type}' через callback")
            
            success = self.publish_to_channel(post_text, image_url, channel)
            
            if success:
                post_data['status'] = PostStatus.PUBLISHED
                post_data['published_at'] = datetime.now().isoformat()
                
                with self.publish_lock:
                    if post_type == 'telegram':
                        self.published_telegram = True
                        self.published_posts_count += 1
                        logger.info("✅ Telegram пост опубликован в канал!")
                    elif post_type == 'zen':
                        self.published_zen = True
                        self.published_posts_count += 1
                        logger.info("✅ Дзен пост опубликован в канал!")
                    
                    self.pending_posts[message_id] = post_data
                    
                    if self.published_posts_count >= 2:
                        logger.info("✅ Оба посты опубликованы! Устанавливаем флаг завершения.")
                        with self.completion_lock:
                            self.workflow_complete = True
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
            
            try:
                status_text = f"\n\n<b>❌ Отклонено</b>"
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + status_text,
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}{status_text}",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
            post_type = post_data.get('type')
            theme = post_data.get('theme', '')
            slot_style = post_data.get('slot_style', {})
            
            post_data['status'] = PostStatus.REJECTED
            post_data['rejected_at'] = datetime.now().isoformat()
            post_data['rejection_reason'] = "Отклонено через кнопку"
            
            logger.info(f"❌ Пост типа '{post_type}' отклонен через callback")
            
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                logger.info(f"🗑️ Пост {message_id} удален из ожидания")
            
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
            
            remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining_posts == 0:
                logger.info("✅ Все посты отклонены. Устанавливаем флаг завершения.")
                with self.completion_lock:
                    self.workflow_complete = True
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
            
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            post_data['edit_timeout'] = edit_timeout
            
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>✏️ Запрос на редактирование '{edit_type}' принят.</b>\n"
                     f"<b>⏰ Время на внесение изменений:</b> {edit_timeout.strftime('%H:%M:%S')} МСК\n"
                     f"<b>🔄 Генерирую новый вариант...</b>",
                parse_mode='HTML'
            )
            
            if "текст" in edit_type or "полностью" in edit_type:
                logger.info(f"🔄 Перегенерация текста для поста {message_id}")
                new_text = self.regenerate_post_text(
                    post_data.get('theme', ''),
                    post_data.get('slot_style', {}),
                    post_data.get('text', ''),
                    edit_type
                )
                
                if new_text:
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
            if not self.is_admin_message(message) or not message.reply_to_message:
                return
            
            original_message_id = message.reply_to_message.message_id
            
            if original_message_id not in self.pending_posts:
                return
            
            post_data = self.pending_posts[original_message_id]
            reply_text = (message.text or "").strip()
            
            logger.info(f"📩 Ответ администратора на пост {original_message_id}: '{reply_text}'")
            
            if 'edit_timeout' in post_data:
                timeout = post_data['edit_timeout']
                if datetime.now() > timeout:
                    logger.info(f"⏰ Время для правки истекло для поста {original_message_id}")
                    self.bot.reply_to(message, "<b>⏰ Время для внесения правок истекло. Пост автоматически отклонен.</b>", parse_mode='HTML')
                    if original_message_id in self.pending_posts:
                        del self.pending_posts[original_message_id]
                    return
            
            if post_data.get('is_test'):
                return
            
            if self.is_edit_request(reply_text):
                logger.info(f"✏️ Получен запрос на редактирование для поста {original_message_id}")
                self.handle_edit_request(original_message_id, post_data, reply_text, message)
                return
            
            if self.is_rejection(reply_text):
                logger.info(f"❌ Получено отклонение для поста {original_message_id}")
                self.handle_rejection(original_message_id, post_data, message, reason=reply_text)
                return
            
            if self.is_approval(reply_text):
                logger.info(f"✅ Получено одобрение для поста {original_message_id}")
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
        
        if text_lower in self.approval_words:
            return True
        
        for word in self.approval_words:
            if word in text_lower:
                return True
        
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
        
        if text_lower in self.rejection_words:
                return True
        
        for word in self.rejection_words:
            if word in text_lower:
                return True
        
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
            
            post_data['status'] = PostStatus.REJECTED
            post_data['rejected_at'] = datetime.now().isoformat()
            post_data['rejection_reason'] = reason[:100] if reason else "Отклонено администратором"
            
            try:
                status_text = f"\n\n<b>❌ Отклонено</b>\n<b>📝 Причина:</b> {reason if reason else 'Решение администратора'}"
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=post_data['text'][:1024] + status_text,
                        parse_mode='HTML',
                        reply_markup=None
                    )
                else:
                    self.bot.edit_message_text(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        text=f"{post_data['text']}{status_text}",
                        parse_mode='HTML',
                        reply_markup=None
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
            
            logger.info(f"❌ Пост типа '{post_type}' отклонен. Причина: {reason}")
            
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                logger.info(f"🗑️ Пост {message_id} удален из ожидания")
            
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
            
            remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining_posts == 0:
                logger.info("✅ Все посты отклонены. Устанавливаем флаг завершения.")
                with self.completion_lock:
                    self.workflow_complete = True
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
            
            if 'original_data' not in post_data:
                post_data['original_data'] = {
                    'text': original_text,
                    'image_url': original_image_url,
                    'theme': post_data.get('theme', '')
                }
            
            post_data['status'] = PostStatus.NEEDS_EDIT
            
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            post_data['edit_timeout'] = edit_timeout
            
            self.bot.reply_to(
                original_message,
                f"<b>✏️ Запрос на редактирование принят.</b>\n"
                f"<b>⏰ Время на внесение изменений:</b> {edit_timeout.strftime('%H:%M:%S')} МСК\n"
                f"<b>🔄 Генерирую новый вариант...</b>",
                parse_mode='HTML'
            )
            
            edit_lower = edit_request.lower()
            
            text_edit_keywords = [
                'переделай', 'исправь', 'измени', 'правь', 'редактируй',
                'перепиши', 'переработай', 'доработай', 'пересмотри',
                'переделать', 'исправить', 'изменить', 'редактировать',
                'нужны правки', 'сделай по+другому', 'перефразируй',
                'перегенерируй', 'сгенерируй заново', 'обнови',
                'другой текст', 'новый текст', 'измени текст',
                'перепиши текст', 'переделай пост'
            ]
            
            photo_edit_keywords = ['фото', 'картинк', 'изображен', 'картинку', 'изображение']
            complete_edit_keywords = ['полностью', 'с нуля', 'заново', 'новая тема', 'другая тематика']
            
            if any(word in edit_lower for word in complete_edit_keywords):
                logger.info(f"🔄 Полная переделка поста {message_id}")
                
                keyboard = InlineKeyboardMarkup(row_width=1)
                for theme in self.themes:
                    keyboard.add(InlineKeyboardButton(
                        f"🎯 {theme}",
                        callback_data=f"theme_{theme}"
                    ))
                
                keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
                
                try:
                    caption = f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n" \
                             f"Выберите одну из доступных тем. После выбора темы будет сгенерирован " \
                             f"новый пост с новой фотографией и вариантами подачи.\n\n" \
                             f"<i>Текущая тема: {post_data.get('theme', 'Не указана')}</i>"
                    
                    if original_image_url:
                        self.bot.edit_message_caption(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            caption=caption,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    else:
                        self.bot.edit_message_text(
                            chat_id=ADMIN_CHAT_ID,
                            message_id=message_id,
                            text=caption,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    
                    post_data['original_state'] = {
                        'text': original_text,
                        'keyboard_state': 'theme_selection'
                    }
                    self.pending_posts[message_id] = post_data
                    
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось редактировать сообщение: {e}")
                
                return
            
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
            
            success = self.publish_to_channel(post_text, image_url, channel)
            
            if success:
                post_data['status'] = PostStatus.PUBLISHED
                post_data['published_at'] = datetime.now().isoformat()
                
                with self.publish_lock:
                    if post_type == 'telegram':
                        self.published_telegram = True
                        self.published_posts_count += 1
                        logger.info("✅ Telegram пост опубликован в канал!")
                    elif post_type == 'zen':
                        self.published_zen = True
                        self.published_posts_count += 1
                        logger.info("✅ Дзен пост опубликован в канал!")
                    
                    try:
                        status_text = f"\n\n<b>✅ Опубликовано в {channel}</b>"
                        if 'image_url' in post_data and post_data['image_url']:
                            self.bot.edit_message_caption(
                                chat_id=ADMIN_CHAT_ID,
                                message_id=message_id,
                                caption=post_data['text'][:1024] + status_text,
                                parse_mode='HTML',
                                reply_markup=None
                            )
                        else:
                            self.bot.edit_message_text(
                                chat_id=ADMIN_CHAT_ID,
                                message_id=message_id,
                                text=f"{post_data['text']}{status_text}",
                                parse_mode='HTML',
                                reply_markup=None
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")
                    
                    self.pending_posts[message_id] = post_data
                    
                    if self.published_posts_count >= 2:
                        logger.info("✅ Оба посты опубликованы! Устанавливаем флаг завершения.")
                        with self.completion_lock:
                            self.workflow_complete = True
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
            if random.random() > 0.5:
                return text
            
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
            
            if not source_info['link'].startswith("http"):
                logger.warning("⚠️ Источник отклонён: некорректная ссылка")
                return text
            
            format_template = random.choice(self.useful_formats)
            
            useful_text = format_template.format(
                description=source_info['description']
            )
            
            source_block = (
                "\n\nИсточник:\n"
                f"— {source_info['name']}\n"
                f"— {source_info['organization']}\n"
                f"— {source_info['year']}\n"
                f"— {source_info['link']}"
            )
            
            final_useful = useful_text + source_block
            
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
            
            # Получаем лимиты символов для текущего слота
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            # Создаем промпт с правильным управлением длиной для Gemma
            length_management_prompt = f"""
Роль: профессиональный редактор и аналитик текста.

ЗАДАЧА:
Создать связный текст для социальной сети с заданной структурой и контролируемым объёмом.

СТРУКТУРА И ОБЪЁМ TELEGRAM-ПОСТА ({slot_style['name']}):
1. Шапка с эмодзи {slot_style['emoji']} — 80-120 символов
2. Основная часть — {tg_min-200}-{tg_max-200} символов
3. Практический блок — 100-150 символов
4. Хештеги — 30-50 символов
ОБЩИЙ ОБЪЁМ: {tg_min}-{tg_max} символов

СТРУКТУРА И ОБЪЁМ ДЗЕН-ПОСТА ({slot_style['name']}):
1. Крючок-убийца (без эмодзи) — 100-150 символов
2. Основная часть — {zen_min-300}-{zen_max-300} символов
3. Блок завершения (ОБЯЗАТЕЛЬНО один из трёх) — 150-200 символов
4. Хештеги — 30-50 символов
ОБЩИЙ ОБЪЁМ: {zen_min}-{zen_max} символов

БЛОКИ ЗАВЕРШЕНИЯ ДЛЯ ДЗЕН (ОБЯЗАТЕЛЬНО ВЫБРАТЬ ОДИН):
• "Почему это важно:" с маркерами •
• "Что из этого следует:" с эмодзи 🎯📊🚀
• "Мнение экспертов:" с данными/цитатами

АЛГОРИТМ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):
1. Спланировать структуру для Telegram и Дзен отдельно
2. Распределить объём по блокам для каждого поста
3. Написать Telegram-пост по его структуре
4. Написать Дзен-пост по его структуре
5. Проверить, что суммарный объём в диапазоне
6. Если объём вне диапазона — результат ошибочный, переписать заново
7. Вывести ТОЛЬКО чистые тексты

ВАЖНО: Gemma мыслит токенами, не символами. Работай с диапазонами.
Если итоговый объём выходит за диапазон — текст неверный, нужно перегенерировать.
"""

            prompt = f"""{length_management_prompt}

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
 • Создавай драматичные различия в длине предложениях: чередуй очень короткие (3–5 слов) с длинными, сложными (25+ слов)
 • Чередуй простые, сложносочинённые, сложноподчинённые и сложносочинённо-подчинённые конструкци
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
 • Используй нестандартные конструкций предложений и избегай шаблонных переходов
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
2. НЕ указывать "тема: {theme}" в текста
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
        
        hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
        hashtags_str = ' '.join(hashtags)
        
        lines = text.split('\n')
        clean_lines = [line for line in lines if '#' not in line]
        clean_text = '\n'.join(clean_lines).strip()
        
        return f"{clean_text}\n\n{hashtags_str}"

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
            
            keyboard = self.create_inline_keyboard()
            
            if image_url and image_url.strip():
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
            
            self.pending_posts[message_id] = post_data
            
            logger.info(f"🔄 Пост обновлен, ID: {message_id}")
            
            return message_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления поста: {e}")
            return None

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
            
            last_themes = theme_rotation[-3:] if len(theme_rotation) >= 3 else theme_rotation
            
            available_themes = []
            for theme in self.themes:
                theme_count = last_themes.count(theme)
                if theme_count < 2:
                    available_themes.append(theme)
            
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
            logger.error(f"❌ Ошибка при выбора формата: {e}")
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def get_relevant_hashtags(self, theme, count=None):
        """Возвращает релевантные хэштеги для темы"""
        try:
            if count is None:
                count = random.randint(3, 5)
            
            # Проверяем кэш
            cache_key = f"{theme}_{count}"
            if cache_key in self._hashtags_cache:
                return self._hashtags_cache[cache_key]
            
            hashtags = self.hashtags_by_theme.get(theme, [])
            if len(hashtags) >= count:
                result = random.sample(hashtags, count)
            else:
                result = hashtags[:count] if hashtags else ["#бизнес", "#советы", "#развитие"]
            
            # Сохраняем в кэш
            self._hashtags_cache[cache_key] = result
            return result
            
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

    # Шаблоны для промптов
    ZEN_TEMPLATE = """[КРЮЧОК-УБИЙЦА БЕЗ ЭМОДЗИ!]

[ОСНОВНАЯ ЧАСТЬ: Анализ, экспертные мнения, данные, кейсы.
2-3 абзаца с аргументацией и примерами.]

[ПРИМЕР ИЗ ПРАКТИКИ/КЕЙС (если уместно):
Кейс из практики одной компании показывает...]

{conclusion_text}

{useful_template}

{soft_final}

{hashtags_str}"""

    TELEGRAM_TEMPLATE = """{emoji} [ЗАХВАТЫВАЮЩИЙ ВОПРОС ИЛИ УТВЕРЖДЕНИЕ ПО ТЕМЕ]

[ОСНОВНАЯ ЧАСТЬ: Анализ явления, кейсы, данные, исследования. 2-3 абзаца.]

[ПРАКТИЧЕСКИЙ БЛОК: Что делать с этой информацией, конкретные шаги.]

{useful_template}

[МИНИ1ВЫВОД ИЛИ КЛЮЧЕВАЯ МЫСЛЬ (ИНСАЙТ)]

{soft_final}

{hashtags_str}"""

    def create_detailed_prompt(self, theme, slot_style, text_format, image_description):
        """Создает детальный промпт согласно новым требованиям"""
        try:
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            hashtags = self.get_relevant_hashtags(theme, random.randint(3, 5))
            hashtags_str = ' '.join(hashtags)
            soft_final = self.get_soft_final()
            
            time_rules = ""
            if slot_style['type'] == 'morning':
                time_rules = "СТРОГОЕ ПРАВИЛО: Пост должен начинаться с утреннего приветствия: 'Доброе утро', 'Начало дня', 'Старт утра'. Запрещены любые вечерние или дневные приветствия."
            elif slot_style['type'] == 'day':
                time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние ('Доброе утро') и вечерние ('Добрый вечер') приветствия. Только нейтральный деловой или информационный тон без привязки ко времени суток."
            elif slot_style['type'] == 'evening':
                time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние приветствия ('Доброе утро'). Можно использовать: 'Добрый вечер', 'В завершение дня', 'Подводя итоги'. Только спокойный рефлексивный тон."
            
            trends = self.trends_by_theme.get(theme, [])
            selected_trends = random.sample(trends, min(3, len(trends)))
            trends_text = "\n".join([f"• {trend}" for trend in selected_trends])
            
            conclusion_type = self.select_conclusion_type('zen')
            conclusion_text = self.generate_conclusion_block(conclusion_type, theme)
            
            zen_template = self.ZEN_TEMPLATE.format(
                conclusion_text=conclusion_text,
                useful_template=random.choice(self.useful_formats).format(description="[ОПИСАНИЕ ИССЛЕДОВАНИЯ]"),
                soft_final=soft_final,
                hashtags_str=hashtags_str
            )
            
            telegram_template = self.TELEGRAM_TEMPLATE.format(
                emoji=slot_style['emoji'],
                useful_template=random.choice(self.useful_formats).format(description="[ОПИСАНИЕ ИССЛЕДОВАНИЯ]"),
                soft_final=soft_final,
                hashtags_str=hashtags_str
            )
            
            # Создаем промпт с правильным управлением длиной для Gemma
            length_management_prompt = f"""
Роль: профессиональный редактор и аналитик текста.

ЗАДАЧА:
Создать ДВА связных текста для социальных сетей с заданной структурой и контролируемым объёмом.

СТРУКТУРА И ОБЪЁМ TELEGRAM-ПОСТА ({slot_style['name']}):
1. Шапка с эмодзи {slot_style['emoji']} — 80-120 символов
2. Основная часть — {tg_min-200}-{tg_max-200} символов
3. Практический блок — 100-150 символов
4. Хештеги — 30-50 символов
ОБЩИЙ ОБЪЁМ: {tg_min}-{tg_max} символов

СТРУКТУРА И ОБЪЁМ ДЗЕН-ПОСТА ({slot_style['name']}):
1. Крючок-убийца (без эмодзи) — 100-150 символов
2. Основная часть — {zen_min-300}-{zen_max-300} символов
3. Блок завершения (ОБЯЗАТЕЛЬНО один из трёх) — 150-200 символов
4. Хештеги — 30-50 символов
ОБЩИЙ ОБЪЁМ: {zen_min}-{zen_max} символов

БЛОКИ ЗАВЕРШЕНИЯ ДЛЯ ДЗЕН (ОБЯЗАТЕЛЬНО ВЫБРАТЬ ОДИН):
• "Почему это важно:" с маркерами •
• "Что из этого следует:" с эмодзи 🎯📊🚀
• "Мнение экспертов:" с данными/цитатами

АЛГОРИТМ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):
1. Спланировать структуру для Telegram и Дзен отдельно
2. Распределить объём по блокам для каждого поста
3. Написать Telegram-пост по его структуре
4. Написать Дзен-пост по его структуре
5. Проверить, что суммарный объём в диапазоне
6. Если объём вне диапазона — результат ошибочный, переписать заново
7. Вывести ТОЛЬКО чистые тексты

ВАЖНО: Gemma мыслит токенами, не символами. Работай с диапазонами.
Если итоговый объём выходит за диапазон — текст неверный, нужно перегенерировать.

ВАЖНЕЙШЕЕ ПРАВИЛО:
Telegram пост ДОЛЖЕН быть {tg_min}-{tg_max} символов. 
Дзен пост ДОЛЖЕН быть {zen_min}-{zen_max} символов.
Если длина поста выходит за эти пределы - это КРИТИЧЕСКАЯ ОШИБКА.
Никакие исключения не допускаются.

СОВЕТ ПО СТРУКТУРЕ:
Для Telegram: 1 эмодзи + 3 коротких абзаца + хештеги
Для Дзен: 1 крючок + 3 абзаца + блок завершения + хештеги
Короткие абзацы = 3-5 предложений максимум.
"""

            existing_prompt = f"""

📱 ШАБЛОН TELEGRAM (с эмодзи):
{telegram_template}

📝 ШАБЛОН ДЗЕН (СТРУКТУРА «КРЮЧОК-УБИЙЦА»):
{zen_template}

ВАРИАТИВНЫЕ ФОРМАТЫ ЗАВЕРШЕНИЯ ПОСТА (используй только ОДИН):

1. "Почему это важно:" с маркерами • (использовать в ~40% постов)
2. "Что из этого следует:" с эмодзи 🎯📊🚀 (30% постов)  
3. "Мнение экспертов:" с цитатами/данными (29% постов)
4. "Упрощённое завершение с одним из трёх блоков" (1% постов)

ВАЖНО: Каждый Дзен-пост ДОЛЖЕН содержать один из трёх блоков завершения: 'Почему это важно:', 'Что из этого следует:' или 'Мнение экспертов:'.

НЕ ИСПОЛЬЗУЙ "Почему это важно:" в каждом посте!
Чередуй форматы для естественности и избегания шаблонности.

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
3. НЕ сообщай, для какого канал пост
4. Telegram пост начинается СТРОГО по шаблону Telegram с эмодзи {slot_style['emoji']}
5. Дзен пост — СТРОГО по шаблону «Крючок -убийца» БЕЗ ЭМОДЗИ ВООБЩЕ
6. Хештеги ТОЛЬКО В КОНЦЕ каждого поста
7. Сохранять ограничения по символам (помни: хештеги включаются в подсчет)
8. Оба поста должны быть РАЗНЫМИ по структуре, но об одном смысле
9. Каждый Дзен-пост ДОЛЖЕН содержать один из трёх блоков завершения

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (полностью по шаблону с эмодзи)
• Потом Дзен версия (полностью по шаблону «Крючок-убийца» без эмодзи)
• Разделитель: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя шаблонам выше."""
            
            prompt = length_management_prompt + "\n\n" + existing_prompt
            
            return prompt
        except Exception as e:
            logger.error(f"❌ Ошибка создания промпта: {e}")
            return ""

    def preprocess_generated_text(self, text):
        """Предварительная обработка сгенерированного текста"""
        if not text:
            return text
        
        technical_phrases = [
            'вот текст для telegram',
            'версия для дзен',
            'длина:',
            'символов',
            'символы:',
            'количество симвоволов',
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
            
            is_technical = False
            for phrase in technical_phrases:
                if phrase in line_lower:
                    if line_lower.startswith(phrase) or line_lower.endswith(phrase) or len(line_lower) < 50:
                        is_technical = True
                        break
            
            if not is_technical:
                cleaned_lines.append(line)
        
        result = []
        for i, line in enumerate(cleaned_lines):
            result.append(line)
            if i < len(cleaned_lines) - 1 and cleaned_lines[i + 1] == '':
                result.append('')
        
        processed_text = '\n'.join(result)
        
        if '---' not in processed_text:
            lines = processed_text.split('\n')
            
            tg_end = None
            for i in range(len(lines) - 1):
                if i > 0 and any(e in lines[i] for e in ['🌅', '🌞', '🌙']):
                    tg_end = i - 1
                    break
                if i > 10 and lines[i].strip() == '' and lines[i+1].strip() != '':
                    tg_end = i
                    break
            
            if tg_end is not None and tg_end > 10 and tg_end < len(lines) - 10:
                result_lines = lines[:tg_end+1] + ['---'] + lines[tg_end+1:]
                processed_text = '\n'.join(result_lines)
                logger.info("✅ Добавлен разделитель между постами")
        
        return processed_text

    def parse_generated_texts(self, text, tg_min, tg_max, zen_min, zen_max):
        """Парсит сгенерированные тексты - НОВАЯ УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            processed_text = self.preprocess_generated_text(text)
            
            if '---' in processed_text:
                parts = processed_text.split('---', 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    if not tg_text or not zen_text:
                        logger.warning("⚠️ Одна из частей пустая после разделения по ---")
                        return None, None
                    
                    if len(tg_text) < 50 or len(zen_text) < 50:
                        logger.warning("⚠️ Одна из частей слишком короткая после разделения по ---")
                        return None, None
                    
                    tg_text = tg_text.replace('---', '').strip()
                    zen_text = zen_text.replace('---', '').strip()
                    
                    logger.info(f"✅ Разделение по явному разделителю ---")
                    logger.info(f"📊 Telegram часть: {len(tg_text)} символов")
                    logger.info(f"📊 Дзен часть: {len(zen_text)} символов")
                    
                    return tg_text, zen_text
            
            lines = processed_text.split('\n')
            
            tg_start = -1
            for i, line in enumerate(lines):
                if any(e in line for e in ['🌅', '🌞', '🌙']):
                    tg_start = i
                    break
            
            zen_start = -1
            if tg_start >= 0:
                for i in range(tg_start + 1, len(lines)):
                    line = lines[i].strip()
                    if line and not any(e in line for e in ['🌅', '🌞', '🌙']):
                        if '?' in line or '!' in line or 'Почему это важно:' in line or 'Что из этого следует:' in line or 'Мнение экспертов:' in line:
                            zen_start = i
                            break
            else:
                for i, line in enumerate(lines):
                    if line.strip() and ('Почему это важно:' in line or 'Что из этого следует:' in line or 'Мнение экспертов:' in line):
                        zen_start = i
                        break
            
            if tg_start >= 0 and zen_start > tg_start:
                tg_lines = lines[tg_start:zen_start]
                zen_lines = lines[zen_start:]
                
                while zen_lines and not zen_lines[0].strip():
                    zen_lines.pop(0)
                
                tg_text = '\n'.join(tg_lines).strip()
                zen_text = '\n'.join(zen_lines).strip()
                
                logger.info(f"✅ Разделение по структурным маркерам")
                logger.info(f"📊 Telegram: {len(tg_text)} символов, Дзен: {len(zen_text)} символов")
                
                return tg_text, zen_text
            
            empty_line_indices = []
            for i, line in enumerate(lines):
                if i > 0 and i < len(lines) - 1:
                    if lines[i].strip() == '' and lines[i-1].strip() == '' and lines[i+1].strip() == '':
                        empty_line_indices.append(i)
            
            if empty_line_indices:
                split_index = empty_line_indices[0]
                
                start_empty = split_index
                while start_empty > 0 and lines[start_empty-1].strip() == '':
                    start_empty -= 1
                
                end_empty = split_index
                while end_empty < len(lines) - 1 and lines[end_empty+1].strip() == '':
                    end_empty += 1
                
                tg_text = '\n'.join(lines[:start_empty]).strip()
                zen_text = '\n'.join(lines[end_empty+1:]).strip()
                
                logger.info(f"✅ Разделение по большой пустой строке (индекс {split_index})")
                logger.info(f"📊 Telegram: {len(tg_text)} символов, Дзен: {len(zen_text)} символов")
                
                return tg_text, zen_text
            
            half = len(lines) // 2
            
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
            import re
            
            if not tg_text or not zen_text:
                logger.error("❌ Один из текстов пустой")
                return False, None, None
            
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            
            if tg_len > tg_max * 1.1:  # Не более 10% сверх лимита
                logger.error(f"❌ Telegram текст СЛИШКОМ ДЛИННЫЙ: {tg_len} > {tg_max}")
                return False, None, None
                
            if zen_len > zen_max * 1.1:  # Не более 10% сверх лимита  
                logger.error(f"❌ Дзен текст СЛИШКОМ ДЛИННЫЙ: {zen_len} > {zen_max}")
                return False, None, None
            
            tg_has_emoji = any(e in tg_text for e in ['🌅', '🌞', '🌙'])
            if not tg_has_emoji:
                logger.warning("⚠️ Telegram пост не содержит эмодзи в начале")
                if self.current_style and 'emoji' in self.current_style:
                    tg_text = f"{self.current_style['emoji']} {tg_text}"
                    logger.info("✅ Добавлен эмодзи в Telegram пост")
            
            zen_has_emoji = any(e in zen_text for e in ['🌅', '🌞', '🌙'])
            if zen_has_emoji:
                logger.warning("⚠️ Дзен пост содержит эмодзи (не должен)")
                import re
                emoji_pattern = re.compile("["
                    u"\U0001F600-\U0001F64F"
                    u"\U0001F300-\U0001F5FF"
                    u"\U0001F680-\U0001F6FF"
                    "]+", flags=re.UNICODE)
                zen_text = emoji_pattern.sub(r'', zen_text).strip()
                logger.info("✅ Удалены эмодзи из Дзен поста")
            
            if not re.findall(r'#\w+', tg_text) and self.current_theme:
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                tg_text = f"{tg_text}\n\n{' '.join(hashtags)}"
                logger.info("✅ Добавлены хештеги в Telegram пост")
            
            if not re.findall(r'#\w+', zen_text) and self.current_theme:
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                zen_text = f"{zen_text}\n\n{' '.join(hashtags)}"
                logger.info("✅ Добавлены хештеги в Дзен пост")
            
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
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    is_valid, valid_tg_text, valid_zen_text = self.validate_parsed_texts(
                        tg_text, zen_text, tg_min, tg_max, zen_min, zen_max
                    )
                    
                    if not is_valid and attempt < max_attempts - 1:
                        has_conclusion = any(
                            marker in zen_text for marker in [
                                'Почему это важно:', 
                                'Что из этого следует:', 
                                'Мнение экспертов:'
                            ]
                        )
                        
                        if not has_conclusion:
                            logger.info("🔄 Добавляю требование блока завершения в промпт для повторной попытки")
                            enhanced_prompt = prompt + "\n\nВАЖНО: Дзен-пост ДОЛЖЕН содержать один из трёх блоков завершения: 'Почему это важно:', 'Что из этого следует:' или 'Мнение экспертов:'."
                            generated_text = self.generate_with_gemma(enhanced_prompt)
                            if generated_text:
                                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                                if tg_text and zen_text:
                                    is_valid, valid_tg_text, valid_zen_text = self.validate_parsed_texts(
                                        tg_text, zen_text, tg_min, tg_max, zen_min, zen_max
                                    )
                    
                    if valid_tg_text and valid_zen_text:
                        tg_final_len = len(valid_tg_text)
                        zen_final_len = len(valid_zen_text)
                        
                        if tg_final_len >= tg_min and zen_final_len >= zen_min:
                            logger.info(f"✅ Успех! Telegram: {tg_final_len} символов, Дзен: {zen_final_len} символов")
                            return valid_tg_text, valid_zen_text
                        else:
                            logger.warning(f"⚠️ Тексты слишком короткие: Telegram {tg_final_len}, Дзен {zen_final_len}")
                    else:
                        logger.warning(f"⚠️ Тексты не прошли валидации")
            
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

    def format_post_text(self, text, slot_style, post_type):
        """Форматирует текст поста в зависимости от типа"""
        if not text:
            return None
        
        # Общие проверки
        if not re.findall(r'#\w+', text):
            hashtags = self.get_relevant_hashtags(self.current_theme, 3)
            text = f"{text}\n\n{' '.join(hashtags)}"
        
        # Специфичные для типа поста проверки
        if post_type == 'telegram':
            if not any(line.strip().startswith(('🌅', '🌞', '🌙')) for line in text.split('\n')[:2]):
                text = f"{slot_style['emoji']} {text}"
            
            lines = text.split('\n')
            if len(lines) > 3 and lines[1].strip() != '':
                lines.insert(1, '')
                text = '\n'.join(lines)
                
        elif post_type == 'zen':
            import re
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF"
                u"\U0001F680-\U0001F6FF"
                "]+", flags=re.UNICODE)
            text = emoji_pattern.sub(r'', text)
            
            # Проверяем наличие блока завершения
            has_conclusion_block = any(
                marker in text for marker in [
                    'Почему это важно:', 
                    'Что из этого следует:', 
                    'Мнение экспертов:'
                ]
            )
            
            if not has_conclusion_block:
                logger.info("⚠️ В Дзен посте отсутствует блок завершения, добавляем...")
                valid_conclusion_types = [k for k in self.conclusions['zen'].keys() if k != 'no_special_section']
                conclusion_type_key = random.choice(valid_conclusion_types)
                conclusion_type = self.conclusions['zen'][conclusion_type_key]
                conclusion_type['name'] = conclusion_type_key
                
                conclusion_block = self.generate_conclusion_block(conclusion_type, self.current_theme)
                
                lines = text.split('\n')
                
                hashtag_line_index = -1
                for i, line in enumerate(lines):
                    if '#' in line:
                        hashtag_line_index = i
                        break
                
                if hashtag_line_index > 0:
                    lines.insert(hashtag_line_index, '')
                    lines.insert(hashtag_line_index, conclusion_block.strip())
                else:
                    text = text.rstrip() + "\n\n" + conclusion_block.strip()
                    return text
                
                text = '\n'.join(lines)
                logger.info(f"✅ Добавлен блок завершения '{conclusion_type['title']}' в Дзен пост")
        
        return text

    def _force_cut_text(self, text, target_max):
        """Режет текст до нужной длины, сохраняя смысловую нагрузку"""
        if len(text) <= target_max:
            return text
        
        logger.info(f"⚔️ Сокращение: {len(text)} → {target_max}")
        
        hashtags_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        hashtags = ""
        if hashtags_match:
            hashtags = hashtags_match.group(1)
            text_without_hashtags = text[:hashtags_match.start()].strip()
        else:
            text_without_hashtags = text
        
        cut_points = []
        
        for i, char in enumerate(text_without_hashtags):
            if char == '\n' and i > len(text_without_hashtags) * 0.7:
                cut_points.append(i)
        
        for i, char in enumerate(text_without_hashtags):
            if char in '.!?' and i > len(text_without_hashtags) * 0.7:
                cut_points.append(i + 1)
        
        best_cut = -1
        for point in sorted(cut_points, reverse=True):
            if point <= target_max - len(hashtags) - 50:
                best_cut = point
                break
        
        if best_cut > 0:
            cut_text = text_without_hashtags[:best_cut].strip()
            if not cut_text[-1] in '.!?':
                last_sentence_end = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
                if last_sentence_end > 0:
                    cut_text = cut_text[:last_sentence_end + 1].strip()
        else:
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
            if cut_text and cut_text[-1] not in '.!?':
                last_punct = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
                if last_punct > len(cut_text) * 0.8:
                    cut_text = cut_text[:last_punct + 1].strip()
        
        result = f"{cut_text}\n\n{hashtags}" if hashtags else cut_text
        
        logger.info(f"⚔️ После сокращения: {len(result)} символов (сохранена смысловая нагрузка)")
        return result

    def send_to_admin_for_moderation(self, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет посты администратору на модерацию"""
        logger.info("📤 Отправляю посты администратору на модерацию...")
        
        success_count = 0
        post_ids = []
        
        edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
        
        # Общая функция для отправки поста
        def send_post(post_type, text, channel):
            nonlocal success_count
            try:
                logger.info(f"📨 Отправляем {post_type} пост администратору")
                
                keyboard = self.create_inline_keyboard()
                
                if image_url:
                    caption = text[:1024] if len(text) > 1024 else text
                    sent_message = self.bot.send_photo(
                        chat_id=ADMIN_CHAT_ID,
                        photo=image_url,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    
                    if len(text) > 1024:
                        remaining_text = text[1024:]
                        self.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=f"<i>Продолжение {post_type} поста:</i>\n\n{remaining_text}",
                            parse_mode='HTML',
                            reply_to_message_id=sent_message.message_id
                        )
                else:
                    sent_message = self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                
                post_ids.append((post_type, sent_message.message_id))
                
                self.pending_posts[sent_message.message_id] = {
                    'type': post_type,
                    'text': text,
                    'image_url': image_url or '',
                    'channel': channel,
                    'status': PostStatus.PENDING,
                    'theme': theme,
                    'slot_style': self.current_style,
                    'slot_time': slot_time,
                    'hashtags': re.findall(r'#\w+', text),
                    'edit_timeout': edit_timeout,
                    'sent_time': datetime.now().isoformat(),
                    'keyboard_message_id': sent_message.message_id
                }
                
                logger.info(f"✅ {post_type} пост отправлен администратору (ID сообщения: {sent_message.message_id})")
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки {post_type} поста: {e}")
        
        send_post('telegram', tg_text, MAIN_CHANNEL)
        time.sleep(1)
        send_post('zen', zen_text, ZEN_CHANNEL)
        time.sleep(1)
        
        self.send_moderation_instructions(post_ids, slot_time, theme, tg_text, zen_text, edit_timeout)
        
        return success_count

    def send_moderation_instructions(self, post_ids, slot_time, theme, tg_text, zen_text, edit_timeout):
        """Отправляет инструкции по модерации ПОСЛЕ постов"""
        if not post_ids:
            return
        
        timeout_str = edit_timeout.strftime("%H:%M") + " МСК"
        
        tg_hashtags_count = len(re.findall(r'#\w+', tg_text))
        zen_hashtags_count = len(re.findall(r'#\w+', zen_text))
        
        zen_has_bullets = '•' in zen_text
        zen_has_hook = any('?' in line or '!' in line for line in zen_text.split('\n')[:3])
        
        zen_has_conclusion = any(
            marker in zen_text for marker in [
                'Почему это важно:', 
                'Что из этого следует:', 
                'Мнение экспертов:'
            ]
        )
        
        tg_has_emoji_header = any(line.strip().startswith(('🌅', '🌞', '🌙')) for line in tg_text.split('\n')[:2])
        tg_has_useful_source = any(keyword in tg_text.lower() for keyword in [
            'исследовани', 'отчёт', 'данные', 'работа', 'подтверждается', 'опирается', 'рассматривается'
        ])
        
        instruction = f"""<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>

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
   {'✅' if zen_has_conclusion else '⚠️'} Блок завершения: {'Есть' if zen_has_conclusion else 'НЕТ!'}
   📌 Используйте кнопки под постом для модерации

<b>🎯 Кнопки модерации под каждым постом:</b>
• ✅ Опубликовать - одобрить и опубликовать
• ❌ Отклонить - отклонить пост
• 📝 Текст - перегенерировать только текст
• 🖼️ Фото - найти новое изображение
• 🔄 Всё - полная переделка (новая тема, фото, подача)
• ⚡ Новое - выбрать тему для нового поста

<b>⏰ Время на решение:</b> до {timeout_str} (10 минут)
<b>📢 После истечения времени посты будут автоматически отклонены</b>"""
        
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
            
            hashtags = re.findall(r'#\w+', text)
            if not hashtags:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Нет хештегов в посте для {channel}")
                backup_hashtags = "#бизнес #советы #развитие"
                text = f"{text}\n\n{backup_hashtags}"
                logger.warning(f"⚠️ Добавлены резервные хештеги: {backup_hashtags}")
            
            logger.info(f"✅ Хештеги перед публикации: {len(hashtags)} шт.")
            
            if image_url and image_url.startswith('http'):
                try:
                    if channel == MAIN_CHANNEL and len(text) > 1024:
                        self.bot.send_photo(
                            chat_id=channel,
                            photo=image_url
                        )
                        self.bot.send_message(
                            chat_id=channel,
                            text=text,
                            parse_mode='HTML',
                            disable_web_page_preview=False
                        )
                        logger.info(f"✅ Пост опубликован в {channel} (фото + длинный текст)")
                    else:
                        caption = text[:1024] if len(text) > 1024 else text
                        self.bot.send_photo(
                            chat_id=channel,
                            photo=image_url,
                            caption=caption,
                            parse_mode='HTML'
                        )
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

    def validate_post_structure(self, text, post_type):
        """Валидация структуры поста перед отправкой"""
        
        if post_type == 'telegram':
            if not any(e in text[:100] for e in ['🌅', '🌞', '🌙']):
                return False, "❌ Telegram пост должен начинаться с эмодзи"
            
            if len(re.findall(r'#\w+', text)) < 3:
                return False, "❌ Telegram пост должен содержать минимум 3 хештега"
                
        elif post_type == 'zen':
            if any(e in text for e in ['🌅', '🌞', '🌙']):
                return False, "❌ Дзен пост НЕ должен содержать эмодзи"
            
            has_conclusion = any(
                marker in text for marker in [
                    'Почему это важно:', 
                    'Что из этого следует:', 
                    'Мнение экспертов:'
                ]
            )
            if not has_conclusion:
                return False, "❌ Дзен пост должен содержать один из трёх блоков завершения: 'Почему это важно:', 'Что из этого следует:' или 'Мнение экспертов:'"
            
            if '•' not in text and '-' not in text:
                return False, "❌ Дзен пост должен содержать маркеры списка"
        
        return True, "✅ Структура корректна"

    def create_and_send_posts(self, slot_time, slot_style, is_test=False):
        """Создает и отправляет посты"""
        try:
            logger.info(f"🎬 Начинаю создание постов для слота {slot_time}")
            self.current_style = slot_style
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format(slot_style)
            
            logger.info(f"🎯 Тема: {theme}, Формат: {text_format}")
            
            image_url, image_description = self.get_post_image_and_description(theme)
            
            if image_url:
                self.save_image_history(image_url)
            
            prompt = self.create_detailed_prompt(theme, slot_style, text_format, image_description)
            
            if not prompt:
                logger.error("❌ Не удалось создать промпт")
                return False
            
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось сгенерировать тексты постов")
                return False
            
            tg_valid, tg_error = self.validate_post_structure(tg_text, 'telegram')
            zen_valid, zen_error = self.validate_post_structure(zen_text, 'zen')
            
            if not tg_valid or not zen_valid:
                logger.error(f"❌ Ошибка структуры поста после генерации. Telegram: {tg_error}, Zen: {zen_error}")
                logger.info("🔄 Инициирую автоматическую перегенерацию текста из-за ошибок структуры")
                tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=2)
                
                if not tg_text or not zen_text:
                    logger.error("❌ Не удалось сгенерировать корректные тексты после перегенерации")
                    return False
                
                tg_valid, tg_error = self.validate_post_structure(tg_text, 'telegram')
                zen_valid, zen_error = self.validate_post_structure(zen_text, 'zen')
                
                if not tg_valid or not zen_valid:
                    logger.error(f"❌ Ошибка структуры поста после перегенерации. Telegram: {tg_error}, Zen: {zen_error}")
                    return False
            
            if random.random() < 0.5:
                tg_text = self.add_useful_source(tg_text, theme)
                zen_text = self.add_useful_source(zen_text, theme)
            
            tg_formatted = self.format_post_text(tg_text, slot_style, 'telegram')
            zen_formatted = self.format_post_text(zen_text, slot_style, 'zen')
            
            if not tg_formatted or not zen_formatted:
                logger.error("❌ Не удалось отформатировать тексты")
                return False
            
            if is_test:
                logger.info("🧪 Тестовые посты успешно созданы")
                return True
            
            success_count = self.send_to_admin_for_moderation(
                slot_time, tg_formatted, zen_formatted, image_url, theme
            )
            
            if success_count > 0:
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
            
            if self.polling_thread and self.polling_thread.is_alive():
                logger.info("🛑 Останавливаю polling поток...")
                try:
                    self.bot.stop_polling()
                except:
                    pass
                
                with self.polling_lock:
                    self.stop_polling = True
                
                self.polling_thread.join(timeout=3)
                if self.polling_thread.is_alive():
                    logger.warning("⚠️ Polling поток не завершился в течение 3 секунд")
                else:
                    logger.info("✅ Polling поток остановлен")
            
            self.save_history()
            
            sys.exit(exit_code)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке: {e}")
            sys.exit(exit_code)

    def run_single_cycle(self):
        """Запускает однократный цикл работы бота"""
        try:
            logger.info("🚀 Запуск однократного цикла работы бота")
            
            self.check_all_apis()
            self.remove_webhook()
            self.setup_message_handler()
            
            logger.info("🔄 Запускаю polling для обработки сообщений...")
            
            def polling_task():
                try:
                    while True:
                        with self.polling_lock:
                            if self.stop_polling:
                                logger.info("🛑 Получен сигнал остановки polling")
                                break
                        
                        try:
                            self.bot.polling(none_stop=True, interval=1, timeout=30)
                        except Exception as e:
                            logger.error(f"❌ Ошибка в polling: {e}")
                            time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Критическая ошибка в polling потоке: {e}")
            
            self.polling_thread = threading.Thread(target=polling_task, daemon=True)
            self.polling_thread.start()
            
            self.polling_started = True
            logger.info("✅ Polling запущен для обработки сообщений")
            
            self.initialize_and_run_posts()
            
            logger.info("⏳ Ожидание обработки сообщений (10 минут)...")
            
            start_time = time.time()
            timeout = 600
            
            while time.time() - start_time < timeout:
                with self.completion_lock:
                    if self.workflow_complete:
                        logger.info("✅ Workflow успешно завершен. Подготовка к выходу.")
                        break
                
                remaining_posts = len([p for p in self.pending_posts.values() if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
                if remaining_posts == 0:
                    logger.info("✅ Все посты обработаны. Подготовка к выходу.")
                    break
                
                time.sleep(1)
            
            logger.info("🛑 Останавливаю polling...")
            with self.polling_lock:
                self.stop_polling = True
            
            try:
                self.bot.stop_polling()
            except:
                pass
            
            if self.polling_thread and self.polling_thread.is_alive():
                self.polling_thread.join(timeout=5)
                logger.info("✅ Polling поток остановлен")
            
            with self.completion_lock:
                if self.workflow_complete:
                    logger.info("✅ Workflow успешно завершен. Завершаем выполнение.")
                    self.cleanup_and_exit(0)
                else:
                    logger.info("⚠️ Workflow не завершен по таймауту или ошибке. Завершаем с кодом 1.")
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
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--slot', help='Конкретный слот (формат HH:MM)')
        parser.add_argument('--auto', action='store_true', help='Автоматический запуск по расписанию')
        
        args = parser.parse_args()
        
        bot = TelegramBot(
            target_slot=args.slot,
            auto=args.auto
        )
        
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
