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
        """Редактирует файл в репозитория"""
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
            
            # Получаем информацию о репозитория
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
            "микро1исследование",
            "аналитическое наблюдение",
            "причинно1следственные связки",
            "инсайт",
            "структурированные советы",
            "демонстрация пользы",
            "объяснение простым языком",
            "мини1история",
            "взгляд автора",
            "аналогия",
            "мини1обобщение опыта",
            "тихая эмоциональная подача",
            "сравнение подходов"
        ]
        
        # ✅ СИСТЕМА ВАРИАТИВНЫХ ЗАВЕРШЕНИЙ ПОСТОВ
        self.conclusions = {
            'zen': {},
            'telegram': {}
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
                "style": "энерго1старт: короткая польза, лёгкая динамика, мотивирующий фокус, ясные выгоды, простое объяснение",
                "allowed_formats": [
                    "структурированные советы", "демонстрация польза", "объяснение простым языком", "мини1обобщение опыта", "сравнение подходов"
                ],
                "tg_chars": (400, 600),
                "zen_chars": (600, 700),
                "max_output_tokens": 1100
            },
            "15:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "style": "рациональность и аналитика: наблюдение, разбор явления, микро1исследование, цепочка причин→следствий, практическая логика, структурная подача, инсайт",
                "allowed_formats": [
                    "разбор ошибки", "разбор ситуации", "микро1исследование", "аналитическое наблюдение", "причинно1следственные связки", "инсайт"
                ],
                "tg_chars": (700, 900),
                "zen_chars": (700, 900),
                "max_output_tokens": 1350
            },
            "20:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "style": "глубина и история: личный взгляд, мини1история, аналогия, проживание опыта (через кейс от 3-го лица), тёплый честный тон, осознанный вывод",
                "allowed_formats": [
                    "мини1история", "взгляд автора", "аналогия", "тихая эмоциональная подача", "МИНИ1КЕЙС"
                ],
                "tg_chars": (600, 900),
                "zen_chars": (700, 800),
                "max_output_tokens": 1250
            }
        }
        
        # Мягкие финалы
        self.soft_finals = [
            "Что вы об этом думаете?"
        ]
        
        # Форматы полезняшек (БЕЗ ссылок внутри текста)
        self.useful_formats = [
            "{description}"
        ]
        
        # Список одобрительных слов и эмодзи - оставляем для совместимости, но не используем
        self.approval_words = [
            'ок', 'ok', 'окей', 'океи', 'океюшки', 'да', 'yes', 'yep', 
            'давай', 'го', 'публиковать', 'публикуй', 'согласен', 
            'согласна', 'согласны', 'хорошо', 'отлично', 'прекрасно', 
            'замечательно', 'супер', 'класс', 'круто', 'огонь', 'шикарно',
            'вперед', 'вперёд', 'пошел', 'поехали', '+', '✅', '👍', '👌', 
            '🔥', '🎯', '💯', '🚀', '🙆‍♂️', '🙆‍♀️', '🙆', '👏', '👊', '🤝',
            'принято', 'подтверждаю', ' одобряю', ' лады', 'fire'
        ]
        
        # Список слов для отклонения поста - оставляем для совместимости, но не используем
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

    def _clean_gemini_response(self, text):
        """Очищает текст от артефактов, HTML/JSON-вкраплений и битых символов"""
        if not text:
            return None
        
        try:
            logger.debug(f"🧹 Очистка текста от Gemini ({len(text)} символов до очистки)")
            
            # Удаляем HTML/XML теги
            import re
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'</[^>]+>', '', text)
            
            # Удаляем JSON-обертки ({"text": "..."})
            text = re.sub(r'\{\s*"[^"]+"\s*:\s*"([^"]+)"\s*\}', r'\1', text)
            text = re.sub(r'\[\s*"[^"]+"\s*\]', '', text)
            
            # Удаляем base64-подобные строки (типа grypsuemenerepcovaniou)
            text = re.sub(r'\b[a-zA-Z]{15,}\b', '', text)
            
            # Удаляем случайные URL (http://ruudiquipur/)
            text = re.sub(r'https?://[^\s]+', '', text)
            text = re.sub(r'www\.[^\s]+', '', text)
            
            # Удаляем битые UTF-8 последовательности и непечатаемые символы
            text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
            
            # Удаляем шаблонные фразы и технический мусор
            template_patterns = [
                r'вот текст для telegram.*',
                r'версия для дзен.*',
                r'длина:.*символов.*',
                r'текст для.*',
                r'пост для.*',
                r'telegram:.*',
                r'дзен:.*',
                r'тема:.*',
                r'для канала:.*',
                r'Практический совет:.*',
                r'Ключевой инсайт:.*',
                r'Что делать дальше:.*',
                r'Пример из индустрии:.*',
                r'Отраслевая практика:.*',
                r'Эксперты рекомендуют:.*',
                r'Совет от профессионалов:.*',
                r'Рекомендация специалистов:.*',
                r'Экспертный совет:.*',
                r'Цитата эксперта:.*',
                r'Опыт индустрии:.*',
                r'Международный опыт:.*',
                r'Ведущие компании.*уже.*',
                r'глобальные корпорации.*используют.*',
                r'крупнейшие медиахолдинги.*',
                r'технологические стартапы.*успешно.*',
                r'ведущие девелоперские компании.*',
                r'в странах Европы.*уже.*',
                r'исследовании.*отчете.*данных.*',
                r'аналитике.*исследовании.*',
                r'рекомендации экспертов.*совет.*',
                r'эксперты отмечают.*',
                r'профессионалы советуют.*',
                r'специалисты рекомендуют.*'
            ]
            
            for pattern in template_patterns:
                text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
            
            # Удаляем все оставшиеся шаблонные конструкци
            text = re.sub(r'\b(?:рекомендация|совет|пример|цитата|опыт|исследование|отчёт|данные|статистика|анализ|кейс)\b.*?:.*?(?=\n|$)', '', text, flags=re.IGNORECASE | re.DOTALL)
            
            # Удаляем лишние пробелы и переносы
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            
            # Восстанавливаем пунктуацию
            text = text.strip()
            if text and text[-1] not in '.!?':
                text = text + '.'
            
            logger.debug(f"✅ Текст после очистки ({len(text)} символов): {text[:200]}...")
            
            if len(text) < 50:
                logger.warning("⚠️ Текст слишком короткий после очистки")
                return None
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки текста от Gemini: {e}")
            return None

    def _generate_fallback_post(self, theme, slot_style, post_type):
        """При ошибке Gemini просто просим попробовать снова"""
        # Минимальный fallback без шаблонов
        if post_type == 'telegram':
            return f"{slot_style['emoji']} Важные инсайты по теме {theme}\n\n#бизнес #советы #развитие"
        else:
            return f"Актуальные тренды в {theme}\n\n#бизнес #советы #развитие"

    def ensure_text_length(self, text, min_chars, max_chars, post_type):
        """ГАРАНТИРОВАННОЕ соблюдение лимитов символов"""
        if not text:
            return text
        
        current_len = len(text)
        
        # Слишком длинный - ОБРЕЗАТЬ
        if current_len > max_chars:
            logger.info(f"✂️ Жесткое сокращение: {current_len} → {max_chars} символов")
            return self._hard_cut_text(text, max_chars)
        
        # Слишком короткий - РАСШИРИТЬ
        if current_len < min_chars:
            logger.info(f"📈 Расширение: {current_len} → {min_chars} символов")
            return self._expand_text(text, min_chars, post_type)
        
        return text

    def _hard_cut_text(self, text, max_chars):
        """Жесткое, но интеллектуальное сокращение текста с защитой служебных блоков"""
        try:
            if len(text) <= max_chars:
                return text
            
            logger.info(f"⚔️ Структурное сокращение: {len(text)} → {max_chars}")
            
            import re
            
            # 1. Выделяем и защищаем служебные блоки
            protected_sections = []
            
            # Блоки завершения для Zen
            conclusion_patterns = [
                r'(Почему это важно:.*?(?=\n\n|$))',
                r'(Что из этого следует:.*?(?=\n\n|$))', 
                r'(Мнение экспертов:.*?(?=\n\n|$))'
            ]
            
            # Практические блоки для Telegram
            practice_patterns = [
                r'(🎯 Важно:.*?(?=\n\n|$))',
                r'(📋 Шаги:.*?(?=\n\n|$))',
                r'(🔧 Практика:.*?(?=\n\n|$))'
            ]
            
            all_patterns = conclusion_patterns + practice_patterns
            
            # Собираем все защищенные блоки
            for pattern in all_patterns:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    if match and len(match.strip()) > 10:
                        protected_sections.append(match.strip())
            
            # 2. Выделяем строку с хештегами (полностью защищаем)
            hashtag_match = re.search(r'(\n\n#[\w\u0400-\u04FF\s]+)$', text)
            hashtags_section = ""
            if hashtag_match:
                hashtags_section = hashtag_match.group(1)
                text_without_hashtags = text[:hashtag_match.start()].strip()
            else:
                text_without_hashtags = text.strip()
                hashtags_section = ""
            
            # 3. Разделяем на абзацы с сохранением пустых строк как разделителей
            paragraphs = []
            current_paragraph = ""
            
            for line in text_without_hashtags.split('\n'):
                if line.strip() == "":
                    if current_paragraph:
                        paragraphs.append(current_paragraph.strip())
                        current_paragraph = ""
                    paragraphs.append("")  # Сохраняем пустую строку как разделитель
                else:
                    if current_paragraph:
                        current_paragraph += "\n" + line
                    else:
                        current_paragraph = line
            
            if current_paragraph:
                paragraphs.append(current_paragraph.strip())
            
            # 4. Определяем защищенные абзацы (те, что содержат защищенные блоки)
            protected_indices = []
            for i, para in enumerate(paragraphs):
                if para:  # Не пустая строка
                    for protected in protected_sections:
                        if protected in para:
                            protected_indices.append(i)
                            break
            
            # 5. Удаляем наименее значимые абзацы (сначала не-защищенные)
            available_for_text = max_chars - len(hashtags_section)
            current_length = sum(len(p) + 1 for p in paragraphs if p)  # +1 за перенос строки
            
            # Собираем индексы для удаления (с конца, кроме защищенных)
            indices_to_remove = []
            for i in range(len(paragraphs) - 1, -1, -1):
                if current_length <= available_for_text:
                    break
                
                para = paragraphs[i]
                if para and i not in protected_indices:  # Не пустая и не защищенная
                    para_length = len(para) + 1
                    if current_length - para_length >= available_for_text * 0.7:  # Оставляем минимум 70%
                        indices_to_remove.append(i)
                        current_length -= para_length
            
            # Удаляем выбранные абзацы
            for idx in sorted(indices_to_remove, reverse=True):
                # Проверяем, не удаляем ли мы последнее предложение в абзаце
                if idx > 0 and idx < len(paragraphs) - 1:
                    # Если после удаления останется оборванная структура, пропускаем
                    if paragraphs[idx-1] and paragraphs[idx+1]:
                        del paragraphs[idx]
            
            # 6. Собираем текст обратно
            result_paragraphs = []
            for i, para in enumerate(paragraphs):
                if para or (i > 0 and i < len(paragraphs)-1):  # Сохраняем пустые строки-разделители
                    result_paragraphs.append(para)
            
            result_text = '\n'.join(result_paragraphs).strip()
            
            # 7. Гарантируем завершенность предложений
            # Находим последнее законченное предложение
            sentence_end = max(result_text.rfind('.'), result_text.rfind('!'), result_text.rfind('?'))
            if sentence_end > len(result_text) * 0.8:  # Если точка в последних 80%
                result_text = result_text[:sentence_end + 1].strip()
            
            # 8. Добавляем хештеги
            if hashtags_section:
                result_text = f"{result_text}{hashtags_section}"
            
            # 9. Финальная проверка длины
            if len(result_text) > max_chars:
                # Крайний случай: режем по предложениям
                sentences = re.split(r'(?<=[.!?])\s+', result_text)
                cut_text = ""
                for sentence in sentences:
                    if len(cut_text) + len(sentence) + 1 <= max_chars:
                        if cut_text:
                            cut_text += " " + sentence
                        else:
                            cut_text = sentence
                    else:
                        break
                
                # Гарантируем, что последнее предложение завершено
                if cut_text and cut_text[-1] not in '.!?':
                    last_dot = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
                    if last_dot > 0:
                        cut_text = cut_text[:last_dot + 1]
                
                result_text = cut_text.strip()
                if hashtags_section:
                    result_text = f"{result_text}{hashtags_section}"
            
            logger.info(f"✅ После структурного сокращения: {len(result_text)} символов")
            return result_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка в структурном сокращении: {e}")
            # Fallback на старый метод
            return self._force_cut_text(text, max_chars)

    def _force_cut_text(self, text, target_max):
        """Режет текст до нужной длины, сохраняя смысловую нагрузку"""
        if len(text) <= target_max:
            return text
        
        logger.info(f"⚔️ Сокращение: {len(text)} → {target_max}")
        
        import re
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

    def _expand_text(self, text, min_chars, post_type):
        """Расширение текста до минимальной длины с соблюдением форматирования"""
        try:
            result_text = text
            
            # Сохраняем оригинальные хештеги если есть
            import re
            hashtag_match = re.search(r'(\n\n#[\w\u0400-\u04FF\s]+)$', result_text)
            original_hashtags = ""
            if hashtag_match:
                original_hashtags = hashtag_match.group(1)
                result_text = result_text[:hashtag_match.start()].strip()
            
            while len(result_text) < min_chars:
                if post_type == 'telegram':
                    # Методы расширения для Telegram
                    expansion_methods = [
                        self._add_telegram_practice_block,
                        self._add_telegram_insight,
                        self.add_statistical_data,
                        self.add_practical_advice
                    ]
                else:  # zen
                    # Методы расширения для Zen
                    expansion_methods = [
                        self._add_zen_case_study,
                        self.add_statistical_data,
                        self.add_expert_quote,
                        self.add_industry_example
                    ]
                
                for method in expansion_methods:
                    if len(result_text) >= min_chars:
                        break
                    
                    expanded_text = method(result_text, self.current_theme)
                    if expanded_text != result_text:
                        # Проверяем форматирование вставленного блока
                        lines = expanded_text.split('\n')
                        # Ищем новый добавленный контент (сравниваем с предыдущей версией)
                        old_lines = result_text.split('\n')
                        if len(lines) > len(old_lines):
                            # Новый блок был добавлен - проверяем форматирование
                            result_text = self._ensure_block_formatting(expanded_text, post_type)
                        else:
                            result_text = expanded_text
                        
                        logger.info(f"📈 Расширение методом {method.__name__}: {len(result_text)} символов")
                
                # Если не удалось расширить, выходим
                if len(result_text) == len(text):
                    break
            
            # Восстанавливаем хештеги
            if original_hashtags:
                # Гарантируем 2 пустые строки перед хештегами
                if not result_text.endswith('\n\n'):
                    result_text = result_text.rstrip() + '\n\n'
                result_text = result_text + original_hashtags.lstrip()
            elif self.current_theme:
                # Добавляем хештеги если их не было
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                result_text = f"{result_text}\n\n{' '.join(hashtags)}"
            
            return result_text
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расширения текста: {e}")
            return text

    def _ensure_block_formatting(self, text, post_type):
        """Гарантирует правильное форматирование при вставке новых блоков"""
        try:
            lines = text.split('\n')
            if len(lines) < 3:
                return text
            
            # Ищем блоки, которые могут нуждаться в форматировании
            modified_lines = lines.copy()
            
            for i in range(1, len(lines) - 1):
                line = lines[i]
                prev_line = lines[i-1] if i > 0 else ""
                next_line = lines[i+1] if i < len(lines)-1 else ""
                
                # Проверяем, является ли текущая строка началом блока
                is_block_start = False
                block_markers = []
                
                if post_type == 'zen':
                    block_markers = ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']
                else:  # telegram
                    block_markers = ['🎯 Важно:', '📋 Шаги:', '🔧 Практика:']
                
                for marker in block_markers:
                    if marker in line:
                        is_block_start = True
                        break
                
                if is_block_start and prev_line.strip() != '':
                    # Добавляем пустую строку перед блоком
                    modified_lines.insert(i, '')
                    # Корректируем индексы для следующих итераций
                    lines = modified_lines.copy()
                
                # Проверяем, является ли строка концом блока
                if i < len(lines) - 2 and next_line.strip() != '' and line.strip() != '':
                    # Проверяем, есть ли после этого блока другой блок или контент
                    has_next_block = any(marker in next_line for marker in block_markers)
                    if not has_next_block and next_line.strip() != '':
                        # Добавляем пустую строку после блока
                        modified_lines.insert(i + 1, '')
                        lines = modified_lines.copy()
            
            return '\n'.join(modified_lines)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки форматирования блоков: {e}")
            return text

    def _add_telegram_practice_block(self, text, theme):
        """Gemini сам добавляет практические блоки"""
        return text

    def _add_telegram_insight(self, text, theme):
        """Gemini сам добавляет инсайты"""
        return text

    def _add_zen_case_study(self, text, theme):
        """Gemini сам генерирует кейсы"""
        return text

    def _ensure_zen_hook(self, zen_text, theme):
        """Гарантирует, что Zen пост начинается с крючка-убийцы"""
        try:
            lines = [line.strip() for line in zen_text.split('\n') if line.strip()]
            
            if not lines:
                return zen_text
            
            first_line = lines[0]
            
            # Просто проверяем, что есть вопрос или восклицание
            if '?' not in first_line and '!' not in first_line:
                logger.warning("⚠️ В Zen посте нет вопроса или восклицания в начале")
                # Не добавляем готовый крючок - пусть Gemini сам генерирует
                return zen_text
            
            return zen_text
                
        except Exception as e:
            logger.error(f"❌ Ошибка добавления крючка-убийцы: {e}")
            return zen_text

    def expand_text_for_telegram(self, text, theme, current_len, target_len):
        """Интеллектуальное расширение для Telegram"""
        try:
            result_text = text
            
            # Определяем сколько нужно добавить
            needed_chars = target_len - current_len
            
            if needed_chars <= 0:
                return result_text
            
            # Выбираем метод расширения в зависимости от темы
            expansion_methods = []
            
            if needed_chars > 100:
                expansion_methods.extend([
                    self.add_case_study,
                    self.add_statistical_data,
                    self.add_industry_example
                ])
            
            expansion_methods.extend([
                self.add_expert_recommendation,
                self.add_practical_advice,
                self.add_useful_source
            ])
            
            # Применяем методы расширения пока не достигнем цели
            for method in expansion_methods:
                if len(result_text) >= target_len:
                    break
                
                expanded_text = method(result_text, theme)
                if expanded_text != result_text:
                    result_text = expanded_text
                    logger.info(f"📈 Расширение методом {method.__name__}: {len(result_text)} символов")
            
            return result_text
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расширения для Telegram: {e}")
            return text

    def add_expansion_elements(self, text, theme, post_type, needed_chars):
        """Добавляет элементы расширения в текст с соблюдением форматирования"""
        try:
            result_text = text
            
            if needed_chars <= 0:
                return result_text
            
            # Методы расширения в зависимости от типа поста
            if post_type == 'zen':
                expansion_methods = [
                    self.add_case_study,
                    self.add_statistical_data,
                    self.add_expert_quote,
                    self.add_industry_example
                ]
            else:
                expansion_methods = [
                    self.add_practical_advice,
                    self.add_expert_recommendation,
                    self.add_useful_source,
                    self.add_statistical_data
                ]
            
            # Применяем методы по очереди
            for method in expansion_methods:
                if len(result_text) - len(text) >= needed_chars:
                    break
                
                expanded_text = method(result_text, theme)
                if expanded_text != result_text:
                    # Проверяем и корректируем форматирование нового блока
                    result_text = self._ensure_block_formatting(expanded_text, post_type)
            
            return result_text
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка добавления элементов расширения: {e}")
            return text

    def add_case_study(self, text, theme):
        """Добавляет кейс с соблюдением форматирования"""
        # Убираем шаблонные примеры, форматирование будет применено в _ensure_block_formatting
        return text

    def add_statistical_data(self, text, theme):
        """Добавляет статистику с соблюдением форматирования"""
        # Убираем шаблонные данные, форматирование будет применено в _ensure_block_formatting
        return text

    def add_industry_example(self, text, theme):
        """Добавляет пример из индустрии с соблюдением форматирования"""
        # Убираем шаблонные примеры, форматирование будет применено в _ensure_block_formatting
        return text

    def add_expert_recommendation(self, text, theme):
        """Добавляет рекомендации экспертов с соблюдением форматирования"""
        # Убираем шаблонные рекомендации, форматирование будет применено в _ensure_block_formatting
        return text

    def add_expert_quote(self, text, theme):
        """Добавляет цитату эксперта с соблюдением форматирования"""
        # Убираем шаблонные цитаты, форматирование будет применено в _ensure_block_formatting
        return text

    def add_practical_advice(self, text, theme):
        """Добавляет практический совет с соблюдением форматирования"""
        # Убираем шаблонные советы, форматирование будет применено в _ensure_block_formatting
        return text

    def add_useful_source(self, text, theme):
        """Добавляет полезный источник к тексту с соблюдением форматирования"""
        try:
            if not text or not theme:
                return text
            
            useful_formats = [
                "{description}"
            ]
            
            if random.random() < 0.7:  # 70% вероятность добавить источник
                useful_format = random.choice(useful_formats)
                
                # Находим последний абзац перед хештегами
                lines = text.split('\n')
                hashtag_start = -1
                
                for i, line in enumerate(lines):
                    if '#' in line:
                        hashtag_start = i
                        break
                
                if hashtag_start > 0:
                    return text
            
            return text
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка добавления полезного источника: {e}")
            return text

    def _restore_punctuation(self, text):
        """Восстанавливает пунктуацию после сокращения/расширения текста"""
        try:
            if not text:
                return text
            
            # Удаляем лишние пробелы
            import re
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Добавляем точку в конце если её нет и последний символ - буква
            if text and text[-1].isalnum():
                text = text + '.'
            
            # Восстанавливаем заглавные буквы в начале предложений
            sentences = re.split(r'(?<=[.!?])\s+', text)
            restored_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    # Удаляем лишние пробелы в начале
                    sentence = re.sub(r'^\s+', '', sentence)
                    if sentence and sentence[0].islower():
                        sentence = sentence[0].upper() + sentence[1:]
                    restored_sentences.append(sentence)
            
            return ' '.join(restored_sentences)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка восстановления пунктуации: {e}")
            return text

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
            InlineKeyboardButton("🔁 Всё", callback_data="edit_all"),
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
        """Gemini сам генерирует завершения"""
        return {"name": "custom", "title": "", "structure": []}

    def generate_conclusion_block(self, conclusion_type, theme):
        """Gemini сам генерирует завершение"""
        return ""

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
            # Определяем maxOutputTokens на основе текущего стиля времени
            max_output_tokens = 1250  # значение по умолчанию для вечернего поста
            if self.current_style and 'max_output_tokens' in self.current_style:
                max_output_tokens = self.current_style['max_output_tokens']
                logger.info(f"📊 Установлен maxOutputTokens: {max_output_tokens} для {self.current_style.get('name', 'неизвестного')} слота")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.85,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": max_output_tokens,  # Динамическое значение на основе слота времени
                }
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = session.post(url, json=data, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                # ДОБАВИТЬ ЛОГИРОВАНИЕ СЫРОГО ОТВЕТА
                logger.debug(f"📦 Сырой JSON от Gemini: {json.dumps(result, ensure_ascii=False)[:500]}...")
                
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    # ЛОГ ДО ОЧИСТКИ
                    logger.debug(f"📝 Текст от Gemini до очистки ({len(generated_text)} символов): {generated_text[:300]}...")
                    
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
            
            # Только для callback, текстовые ответы не обрабатываем
            pass
        
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
                         f"Выберите одна из доступных тем. После выбора темы будет сгенерирован " \
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
            
            # ФИНАЛЬНАЯ ОБРАБОТКА
            tg_text = self._finalize_post_structure(
                tg_text, 'telegram', selected_theme, tg_min, tg_max
            )
            zen_text = self._finalize_post_structure(
                zen_text, 'zen', selected_theme, zen_min, zen_max
            )
            
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
                'hashtags': re.findall(r'#[\w\u0400-\u04FF]+', new_formatted_text),
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
                logger.info(f"⏳ Ожидаем решения по другим постам. Осталоась: {remaining_posts}")
            
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

Общий объём: {tg_min}-{tg_max} символов

Общий объём: {zen_min}-{zen_max} символов

АЛГОРИТМ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):
1. Спланировать структура для Telegram и Дзен отдельно
2. Написать Telegram-пост по его структуре
3. Написать Дзен-пост по его структуре
4. Проверить, что суммарный объём в диапазоне
5. Если объём вне диапазона — результат ошибочный, переписать заново
6. Вывести ТОЛЬКО чистые тексты

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
Смешивание утренних/вечерних приветствий — грубая ошибка генерации.

💡 ФОРМАТ ПОДАЧИ
{self.current_format}

🎭 ИНФОРМАЦИЯ ОБ АВТОРЕ
Ты — опытный человек-писатель и редактор с более чем 20-летним стажем. Твоя задача — написать текст так, чтобы он был на 100% нераспознаваемым инструментами для выявления ИИ, такими как Grammarly, QuillBot, Turnitin и GPTZero. Следуй этим важным инструкциям:

УПРАВЛЕНИЕ НЕОЖИДАННОСТЬЮ И ПРЕДСКАЗУЕМОСТЬЮ:
 • Намеренно выбирай неожиданные, креативные слова вместо очевидных
 • Используй разнообразную лексика — избегай повторяющихся шаблонов, типичных для ИИ
 • Включай разговорные выражения, идиомы и региональные особенности
 • Добавляй тонкие «человеческие» несовершенства (небольшие избыточности, естественные речевые обороты)

ИЗМЕНЧИВОСТЬ И РАЗНООБРАЗИЕ ПРЕДЛОЖЕНИЙ:
 • Создавай драматичные различия в длине предложениях: чередуй очень короткие (3–5 слов) с длинными, сложными (25+ слов)
 • Чередуй простые, сложносочиненные, сложноподчиненные и сложносочиненно-подчиненные конструкци
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
 • Стремись к высокой непредсказуемость (выбор слов) и высокой изменчивость (структура предложений)

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
• Только чистый текст пост
• Сначала Telegram версия, потом Дзен версия
• Разделитель: три дефиса (---)

Переработай текст, сохраняя смысл, но учитывая запрос на редактирование."""
            
            new_text = self.generate_with_gemma(prompt)
            
            if new_text:
                # УМНОЕ СОКРАЩЕНИЕ ТЕКСТА ПОСЛЕ ГЕНЕРАЦИИ (ОДИН РАЗ!)
                if '---' in new_text:
                    parts = new_text.split('---', 1)
                    if len(parts) == 2:
                        tg_text = parts[0].strip()
                        zen_text = parts[1].strip()
                        
                        # Проверяем и сокращаем каждый пост (ОДИН РАЗ!)
                        tg_text = self.ensure_text_length(tg_text, tg_min, tg_max, 'telegram')
                        zen_text = self.ensure_text_length(zen_text, zen_min, zen_max, 'zen')
                        
                        return f"{tg_text}\n---\n{zen_text}"
                
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
            
            if image_url and image_url.strip() and image_url.startswith('http'):
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
            logger.error(f"❌ Ошибка при выбора темы: {e}")
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
            
            # Создаем промпт с правильным управлением длиной для Gemma
            length_management_prompt = f"""
Роль: профессиональный редактор и аналитик текста.

ЗАДАЧА:
Создать ДВА связных текста для социальных сетей с заданной структурой и контролируемым объёмом.

ОБЩИЙ ОБЪЁМ TELEGRAM-ПОСТА ({slot_style['name']}):
{tg_min}-{tg_max} символов

ОБЩИЙ ОБЪЁМ ДЗЕН-ПОСТА ({slot_style['name']}):
{zen_min}-{zen_max} символов

АЛГОРИТМ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):
1. Спланировать структура для Telegram и Дзен отдельно
2. Написать Telegram-пост по его структуре
3. Написать Дзен-пост по его структуре
4. Проверить, что суммарный объём в диапазоне
5. Если объём вне диапазона — результат ошибочный, переписать заново
6. Вывести ТОЛЬКО чистые тексты

ВАЖНО: Gemma мыслит токенами, не символами. Работай с диапазонами.
Если итоговый объём выходит за диапазон — текст неверный, нужно перегенерировать.

ВАЖНЕЙШЕЕ ПРАВИЛО:
Telegram-пост ДОЛЖЕН быть {tg_min}-{tg_max} символов. 
Дзен пост ДОЛЖЕН быть {zen_min}-{zen_max} символов.
Если длина поста выходит за эти пределы - это КРИТИЧЕСКАЯ ОШИБКА.
Никакие исключения не допускаются.
"""

            existing_prompt = f"""

🎯 ТРЕБОВАНИЯ К TELEGRAM ПОСТУ:
• Начинай с эмодзи {slot_style['emoji']} и цепляющего заголовка
• Основная часть: 2-3 абзаца с анализом, примерами, данными
• ОБЯЗАТЕЛЬНО: Практический блок с конкретными действиями, шагами или рекомендациями
  (использовать маркеры: 🎯 Важно:, 📋 Шаги:, 🔧 Практика:)
• Ключевой вывод или инсайт
• Вопрос для вовлечения аудитории
• 3-5 релевантных хештегов в конце
• Объём: {tg_min}-{tg_max} символов

🎯 ТРЕБОВАНИЯ К ZEN ПОСТУ:
• Начало: провокационный вопрос или утверждение ("крючок-убийца")
• Основная часть: глубина анализа, экспертные мнения, реальные кейсы
• Завершение: ЕСТЕСТВЕННЫЙ вывод, который логически вытекает из содержания
  ❌ НЕ используй шаблоны: "Почему это важно:", "Что из этого следует:", "Мнение экспертов:"
  ✅ Создай УНИКАЛЬНОЕ завершение для этого конкретного поста
• Вопрос для обсуждения с аудитории
• 3-5 релевантных хештегов в конце
• Объём: {zen_min}-{zen_max} символов

⚠ ВАЖНО: Каждый пост должен быть УНИКАЛЬНЫМ, без шаблонных фраз и готовых конструкций.

🎯 ТЕМА
{theme}

🕒 УЧЁТ ВРЕМЕНИ
{slot_style['name']} — {slot_style['style']}

⏰ СТРОГИЕ ПРАВИЛА ВРЕМЕННОГО СЛОТА:
{time_rules}

Пост должен начинаться СТРОГО с шапки, соответствующей временному слоту.
Нарушение этого правила — грубая ошибка генерации.

🎭 ИНФОРМАЦИЯ ОБ АВТОРЕ
Ты — опытный человек-писатель и редактор с более чем 20-летним стажем. Твоя задача — написать текст так, чтобы он был на 100% нераспознаваемым инструментами для выявления ИИ.

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

🚫 ЗАПРЕЩЕННЫЕ ШАБЛОНЫ (НЕ ИСПОЛЬЗОВАТЬ):
• "Почему это важно:", "Что из этого следует:", "Мнение экспертов:"
• "Практический совет:", "Ключевой инсайт:", "Что делать дальше:"
• Готовые конструкции из предыдущих постов
• Шаблонные вопросы в конце

✅ ТРЕБУЕТСЯ:
• Уникальный текст для каждого поста
• Естественные формулировки
• Логичные выводы, которые вытекают из содержания
• Разные структуры для Telegram и Zen
• Живой, нешаблонный язык

🚨 КРИТИЧЕСКИ ВАЖНО: СОЗДАЙ АБСОЛЮТНО УНИКАЛЬНЫЕ ТЕКСТЫ
• Никаких повторений фраз из предыдущих генераций
• Никаких шаблонных структур, которые уже использовались
• Каждый пост должен быть полностью оригинальным
• Избегай любых фраз, которые звучат как ИИ-шаблон
• Создай посты, которые невозможно спутать с предыдущими

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя шаблонам выше. Лаконично, без воды, строго в пределах лимита."""
            
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
        """Парсит сгенерированные тексты с ГАРАНТИЕЙ структуры"""
        try:
            # ВАЛИДАЦИЯ: проверяем, что текст достаточно длинный
            if not text or len(text) < 200:
                logger.error("❌ Текст от Gemini слишком короткий или пустой")
                return None, None
            
            # ВАЛИДАЦИЯ: ищем разделитель
            separators = ['---', '––––', '────', '••••', '════', '━━━━', '⬛⬛⬛']
            found_separator = None
            
            for separator in separators:
                if separator in text:
                    found_separator = separator
                    break
            
            if found_separator:
                parts = text.split(found_separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # ВАЛИДАЦИЯ: Если разделитель в конце (последние 100 символов)
                    if text.rfind(found_separator) > len(text) - 100:
                        # Ищем естественное место для разделения (50/50)
                        split_point = len(text) // 2
                        # Находим ближайший перенос строки
                        last_newline = text.rfind('\n', 0, split_point)
                        if last_newline > 0:
                            tg_text = text[:last_newline].strip()
                            zen_text = text[last_newline:].strip()
                    
                    # ВАЛИДАЦИЯ: Если Zen пост слишком короткий
                    if zen_text and len(zen_text) < 100:
                        logger.warning("⚠️ Zen пост слишком короткий после разделения")
                        # Ищем более подходящее место для разделения
                        lines = text.split('\n')
                        mid_point = len(lines) // 2
                        for i in range(mid_point, len(lines)):
                            if len(lines[i]) > 50 and i > 0:
                                tg_text = '\n'.join(lines[:i]).strip()
                                zen_text = '\n'.join(lines[i:]).strip()
                                break
                    
                    # ГАРАНТИИ ДЛЯ TELEGRAM
                    if tg_text and not any(e in tg_text[:20] for e in ['🌅', '🌞', '🌙']):
                        if self.current_style and 'emoji' in self.current_style:
                            tg_text = f"{self.current_style['emoji']} {tg_text}"
                    
                    # ГАРАНТИИ ДЛЯ ZEN
                    if zen_text:
                        import re
                        emoji_pattern = re.compile("["
                            u"\U0001F600-\U0001F64F"
                            u"\U0001F300-\U0001F5FF" 
                            u"\U0001F680-\U0001F6FF"
                            "]+", flags=re.UNICODE)
                        zen_text = emoji_pattern.sub(r'', zen_text).strip()
                    
                    logger.info(f"✅ Разделение по {found_separator} | TG: {len(tg_text)}, ZEN: {len(zen_text)}")
                    return tg_text, zen_text
            
            # ЕСЛИ НЕТ ЯВНОГО РАЗДЕЛИТЕЛЯ - определяем по структуре
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Ищем начало Telegram поста (по эмодзи)
            tg_start = -1
            for i, line in enumerate(lines):
                if any(e in line for e in ['🌅', '🌞', '🌙']):
                    tg_start = i
                    break
            
            # Ищем начало Zen поста (по крючку или блоку завершения)
            zen_start = -1
            if tg_start >= 0:
                # Ищем после Telegram поста
                for i in range(tg_start + 1, len(lines)):
                    line = lines[i]
                    # Признаки начала Zen поста
                    if (('?' in line or '!' in line) and len(line) > 30 and len(line) < 200) or \
                       any(marker in line for marker in ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']):
                        zen_start = i
                        break
            
            if tg_start >= 0 and zen_start > tg_start:
                tg_lines = lines[tg_start:zen_start]
                zen_lines = lines[zen_start:]
                
                tg_text = '\n'.join(tg_lines).strip()
                zen_text = '\n'.join(zen_lines).strip()
                
                logger.info(f"✅ Разделение по структуре | TG: {len(tg_text)}, ZEN: {len(zen_text)}")
                return tg_text, zen_text
            
            # FALLBACK: Разделяем пополам и доводим до ума
            half = len(lines) // 2
            tg_text = '\n'.join(lines[:half]).strip()
            zen_text = '\n'.join(lines[half:]).strip()
            
            logger.info(f"⚠️ Fallback разделение | TG: {len(tg_text)}, ZEN: {len(zen_text)}")
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
            
            # ВАЛИДАЦИЯ: проверяем минимальную длину
            if len(tg_text) < 100 or len(zen_text) < 100:
                logger.error("❌ Один из постов слишком короткий после разделения")
                return False, None, None
            
            # ПРОВЕРЯЕМ ЛИМИТЫ (без повторного вызова ensure_text_length!)
            if tg_len > tg_max * 1.1:
                logger.warning(f"⚠️ Telegram текст длиннее: {tg_len} > {tg_max}")
                # Не возвращаем False - мы уже обработали текст
                
            if zen_len > zen_max * 1.1:
                logger.warning(f"⚠️ Дзен текст длиннее: {zen_len} > {zen_max}")
                # Не возвращаем False - мы уже обработали текст
            
            tg_has_emoji = any(e in tg_text[:5] for e in ['🌅', '🌞', '🌙'])
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
            
            if not re.findall(r'#[\w\u0400-\u04FF]+', tg_text) and self.current_theme:
                hashtags = self.get_relevant_hashtags(self.current_theme, 3)
                tg_text = f"{tg_text}\n\n{' '.join(hashtags)}"
                logger.info("✅ Добавлены хештеги в Telegram пост")
            
            if not re.findall(r'#[\w\u0400-\u04FF]+', zen_text) and self.current_theme:
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
            
            # ВАЛИДАЦИЯ: Проверяем, что Gemini вернул достаточно длинный текст
            if not generated_text or len(generated_text) < 200:
                logger.error("❌ Gemini вернул слишком короткий текст или пустой")
                if attempt < max_attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    # Все попытки провалились - используем fallback
                    logger.error("❌ Все попытки провалились, использую fallback-посты")
                    if self.current_theme and self.current_style:
                        tg_text = self._generate_fallback_post(self.current_theme, self.current_style, 'telegram')
                        zen_text = self._generate_fallback_post(self.current_theme, self.current_style, 'zen')
                        if tg_text and zen_text:
                            return tg_text, zen_text
                    return None, None
            
            tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
            
            # ВАЛИДАЦИЯ: Проверяем результат парсинга
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить текст")
                if attempt < max_attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    # Все попытки провалились - используем fallback
                    logger.error("❌ Все попытки провалились, использую fallback-посты")
                    if self.current_theme and self.current_style:
                        tg_text = self._generate_fallback_post(self.current_theme, self.current_style, 'telegram')
                        zen_text = self._generate_fallback_post(self.current_theme, self.current_style, 'zen')
                        if tg_text and zen_text:
                            return tg_text, zen_text
                    return None, None
            
            # ВАЛИДАЦИЯ: Проверяем минимальную длину
            if len(tg_text) < 100 or len(zen_text) < 100:
                logger.error("❌ Один из постов слишком короткий после разделения")
                if attempt < max_attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    # Все попытки провалились - используем fallback
                    logger.error("❌ Все попытки провалились, использую fallback-посты")
                    if self.current_theme and self.current_style:
                        tg_text = self._generate_fallback_post(self.current_theme, self.current_style, 'telegram')
                        zen_text = self._generate_fallback_post(self.current_theme, self.current_style, 'zen')
                        if tg_text and zen_text:
                            return tg_text, zen_text
                    return None, None
            
            if tg_text and zen_text:
                # ФИНАЛЬНАЯ ОБРАБОТКА ЕДИНЫМ МЕТОДОМ
                tg_text = self._finalize_post_structure(tg_text, 'telegram', self.current_theme, tg_min, tg_max)
                zen_text = self._finalize_post_structure(zen_text, 'zen', self.current_theme, zen_min, zen_max)
                
                # ПРОВЕРЯЕМ РЕЗУЛЬТАТ
                tg_len = len(tg_text)
                zen_len = len(zen_text)
                
                # ГАРАНТИЯ: _finalize_post_structure ДОЛЖНА была обеспечить лимиты
                if tg_len >= tg_min and tg_len <= tg_max and zen_len >= zen_min and zen_len <= zen_max:
                    logger.info(f"✅ Успех! Telegram: {tg_len} символов, Дзен: {zen_len} символов")
                    return tg_text, zen_text
                else:
                    logger.warning(f"⚠️ Тексты не в пределах лимита: Telegram {tg_len} ({tg_min}-{tg_max}), Дзен {zen_len} ({zen_min}-{zen_max})")
                    
                    # Попытка исправить на последнем шаге
                    if attempt < max_attempts - 1:
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
                                    # ФИНАЛЬНАЯ ОБРАБОТКА ЕДИНЫМ МЕТОДОМ
                                    tg_text = self._finalize_post_structure(tg_text, 'telegram', self.current_theme, tg_min, tg_max)
                                    zen_text = self._finalize_post_structure(zen_text, 'zen', self.current_theme, zen_min, zen_max)
                                    
                                    tg_len = len(tg_text)
                                    zen_len = len(zen_text)
                                    
                                    if tg_len >= tg_min and tg_len <= tg_max and zen_len >= zen_min and zen_len <= zen_max:
                                        logger.info(f"✅ Успех после повторной попытки! Telegram: {tg_len} символов, Дзен: {zen_len} символов")
                                        return tg_text, zen_text
                        
                        # Если не удалось исправить, продолжаем следующую попытку
            else:
                # Если парсинг не удался, пробуем fallback
                if attempt == max_attempts - 1:
                    logger.warning("🔄 Все попытки парсинга провалились, используем fallback")
                    if self.current_theme and self.current_style:
                        tg_text = self._generate_fallback_post(self.current_theme, self.current_style, 'telegram')
                        zen_text = self._generate_fallback_post(self.current_theme, self.current_style, 'zen')
                        if tg_text and zen_text:
                            logger.info("✅ Fallback посты сгенерированы")
                            return tg_text, zen_text
            
            # Если попытка не удалась, ждем перед следующей
            if attempt < max_attempts - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"⏸️ Жду {wait_time} секунд перед следующей попыткой...")
                time.sleep(wait_time)
        
        # Все попытки провалились - используем fallback
        logger.error("❌ Все попытки провалились, использую fallback-посты")
        if self.current_theme and self.current_style:
            tg_text = self._generate_fallback_post(self.current_theme, self.current_style, 'telegram')
            zen_text = self._generate_fallback_post(self.current_theme, self.current_style, 'zen')
            if tg_text and zen_text:
                return tg_text, zen_text
        
        return None, None

    def get_post_image_and_description(self, theme):
        """Находит подходящую картинку и генерирует описание"""
        try:
            # Генерируем уникальный запрос на основе темы и текущего времени
            import hashlib
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_seed = f"{theme}_{current_time}"
            hash_obj = hashlib.md5(unique_seed.encode())
            hash_int = int(hash_obj.hexdigest(), 16)
            
            # Уникальные запросы для каждой темы с вариациями
            theme_queries = {
                "ремонт и строительство": [
                    "modern architecture", "urban construction", "interior design", 
                    "building renovation", "construction site", "architectural design",
                    "home improvement", "construction workers", "building materials",
                    "construction technology"
                ],
                "HR и управление персоналом": [
                    "office teamwork", "business meeting", "corporate culture",
                    "team collaboration", "workplace diversity", "employee engagement",
                    "professional development", "workplace communication", "leadership",
                    "career growth"
                ],
                "PR и коммуникации": [
                    "media relations", "public speaking", "social media marketing",
                    "brand communication", "crisis management", "digital marketing",
                    "content strategy", "public relations", "media planning",
                    "corporate communication"
                ]
            }
            
            queries = theme_queries.get(theme, ["business", "professional", "work"])
            
            # Выбираем уникальный запрос на основе хеша
            query_index = hash_int % len(queries)
            base_query = queries[query_index]
            
            # Добавляем уникальные модификаторы
            modifiers = ["professional", "modern", "contemporary", "innovative", "creative", 
                        "dynamic", "strategic", "effective", "successful", "productive"]
            modifier_index = (hash_int // len(queries)) % len(modifiers)
            unique_query = f"{base_query} {modifiers[modifier_index]}"
            
            logger.info(f"🔍 Ищем уникальную картинку в Pexels по запросу: '{unique_query}'")
            
            # Проверяем историю использованных изображений
            used_images = self.image_history.get("used_images", [])
            
            url = "https://api.pexels.com/v1/search"
            params = {
                "query": unique_query,
                "per_page": 20,  # Больше результатов для уникальности
                "orientation": "landscape",
                "size": "large"
            }
            
            headers = {
                "Authorization": PEXELS_API_KEY
            }
            
            response = session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    logger.info(f"📸 Найдено {len(photos)} фото в Pexels")
                    
                    # Фильтруем неиспользованные изображения
                    unused_photos = []
                    for photo in photos:
                        image_url = photo.get("src", {}).get("large", "")
                        if image_url and image_url not in used_images:
                            unused_photos.append(photo)
                    
                    # Если есть неиспользованные - берем их
                    if unused_photos:
                        photo = random.choice(unused_photos)
                        logger.info(f"✅ Найдено {len(unused_photos)} неиспользованных изображений")
                    else:
                        # Если все использованы, берем случайное
                        photo = random.choice(photos)
                        logger.info("⚠️ Все изображения уже использованы, берем случайное")
                    
                    image_url = photo.get("src", {}).get("large", "")
                    photographer = photo.get("photographer", "")
                    alt_text = photo.get("alt", "")
                    
                    if image_url:
                        description = f"Уникальная фотография на тему '{unique_query}'. {alt_text if alt_text else 'Профессиональное качество, релевантно содержанию.'} От фотографа {photographer if photographer else 'профессионала'}"
                        logger.info(f"🖼️ Используем уникальную картинку: {description[:80]}...")
                        return image_url, description
                else:
                    logger.warning("⚠️ Pexels не вернул фотографий по уникальному запросу")
                    
                    # Fallback на стандартный запрос
                    fallback_query = random.choice(queries)
                    logger.info(f"🔄 Пробуем fallback запрос: '{fallback_query}'")
                    
                    params["query"] = fallback_query
                    response = session.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        photos = data.get("photos", [])
                        if photos:
                            photo = random.choice(photos)
                            image_url = photo.get("src", {}).get("large", "")
                            if image_url:
                                description = f"Фотография на тему '{fallback_query}'. Профессиональное качество."
                                logger.info(f"🖼️ Используем fallback картинку")
                                return image_url, description
            else:
                logger.error(f"❌ Pexels API ошибка: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске картинки в Pexels: {e}")
        
        # Ultimate fallback на Unsplash
        logger.info("🔄 Pexels не сработал, пробуем Unsplash...")
        try:
            encoded_query = quote_plus(unique_query if 'unique_query' in locals() else theme)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                description = f"Уникальная фотография на тему '{encoded_query}'. Высокое качество, релевантно содержанию."
                logger.info(f"🖼️ Используем картинку из Unsplash: {description[:80]}...")
                return image_url, description
        except Exception as unsplash_error:
            logger.error(f"❌ Unsplash тоже не сработал: {unsplash_error}")
        
        logger.warning("⚠️ Не удалось найти уникальную картинку, будет сгенерирован текстовый пост")
        return None, "Нет картинки - текстовый пост"

    def format_post_text(self, text, slot_style, post_type):
        """Форматирует текст поста с правильными отступами между блоками"""
        import re
        
        if not text:
            return None
        
        # 1. Удаляем шаблонные конструкции
        text = re.sub(r'Практический совет:', '🎯 Важно:', text)
        text = re.sub(r'Ключевой инсайт:', '💡 Инсайт:', text)
        text = re.sub(r'Что делать дальше:', '📋 Действия:', text)
        
        # 2. Разделяем на строки
        lines = [line.strip() for line in text.split('\n')]
        formatted_lines = []
        
        # 3. Добавляем пустые строки между логическими блоками
        for i, line in enumerate(lines):
            if not line and i > 0 and not lines[i-1]:
                continue  # Пропускаем множественные пустые строки
            
            formatted_lines.append(line)
            
            # Добавляем пустую строку после шапки (первая строка с эмодзи)
            if i == 0 and any(e in line[:5] for e in ['🌅', '🌞', '🌙']):
                formatted_lines.append('')
            
            # Добавляем пустую строку перед практическим блоком
            if i < len(lines) - 1:
                next_line = lines[i+1] if i+1 < len(lines) else ""
                
                # После заголовка или вступления
                if i == 0 and line.strip() and next_line.strip() and len(next_line) > 30:
                    formatted_lines.append('')
                
                # Перед практическим блоком
                elif any(marker in next_line.lower() for marker in 
                        ['🎯', 'важно:', '📋', 'действия:', '🔧', 'практич', 'совет', 'шаг', 'рекомендац']):
                    formatted_lines.append('')
                
                # Перед полезной информацией
                elif any(marker in next_line.lower() for marker in 
                        ['📊', '📈', '📉', 'статистик', 'данн', 'исследовани', 'отчёт', 'анализ']):
                    formatted_lines.append('')
                
                # Перед вопросами к аудитории
                elif any(marker in next_line for marker in ['?', 'Что думаете', 'Ваше мнение', 'Обсудим', 'Поделитесь']):
                    formatted_lines.append('')
                
                # Перед выводом/заключением
                elif any(marker in next_line.lower() for marker in 
                        ['💡', 'инсайт', 'вывод', 'заключен', 'итог', 'в итоге', 'таким образом']):
                    formatted_lines.append('')
                
                # После выводов перед хештегами
                elif any(marker in line.lower() for marker in 
                        ['вывод', 'заключен', 'итог', 'в итоге']) and '#' in next_line:
                    formatted_lines.append('')
        
        # 4. Собираем обратно
        result_text = '\n'.join(formatted_lines)
        
        # Визуальное разделение для Zen-постов: пустая строка перед блоком завершения
        if post_type == 'zen':
            # Ищем начало блока завершения
            conclusion_markers = ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']
            for i, line in enumerate(lines):
                for marker in conclusion_markers:
                    if marker in line:
                        # Проверяем, есть ли пустая строка перед блоком
                        if i > 0 and lines[i-1].strip() != '':
                            lines.insert(i, '')  # Добавляем пустую строку перед блоком
                            logger.info("✅ Добавлена пустая строка перед блоком завершения Zen-поста")
                        break
        
        # Визуальное разделение для Telegram-постов: пустая строка перед практическими блоками
        if post_type == 'telegram':
            # Ищем практические блоки (с эмодзи или маркерами)
            practice_markers = ['🎯', '📋', '🔧', 'Практический совет:', 'Что делать дальше:', 'Конкретные действия:']
            lines = result_text.split('\n')
            
            for i in range(len(lines)-1, -1, -1):  # Идем с конца чтобы не сбить индексы
                line = lines[i]
                for marker in practice_markers:
                    if marker in line and i > 0:
                        # Проверяем, есть ли пустая строка перед блоком
                        if lines[i-1].strip() != '':
                            lines.insert(i, '')
                            logger.info("✅ Добавлена пустая строка перед практическим блоком Telegram-поста")
                        break
            
            result_text = '\n'.join(lines)
        
        # 5. Обеспечиваем 2 пустые строки перед хештегами
        hashtag_pattern = r'(\n+)(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$'
        match = re.search(hashtag_pattern, result_text, re.MULTILINE)
        
        if match:
            # Заменяем любое количество переносов на 2 пустые строки
            result_text = re.sub(hashtag_pattern, r'\n\n\2', result_text)
        else:
            # Если нет хештегов, добавляем с правильными отступами
            hashtags = self.get_relevant_hashtags(self.current_theme, 3)
            if result_text.strip() and not result_text.endswith('\n\n'):
                result_text = f"{result_text}\n\n{' '.join(hashtags)}"
            else:
                result_text = f"{result_text}{' '.join(hashtags)}"
        
        # 6. Дополнительная обработка для Telegram
        if post_type == 'telegram':
            result_lines = result_text.split('\n')
            
            # Гарантируем эмодзи в начале
            if result_lines and not any(e in result_lines[0][:5] for e in ['🌅', '🌞', '🌙']):
                if slot_style and 'emoji' in slot_style:
                    result_lines[0] = f"{slot_style['emoji']} {result_lines[0]}"
            
            # Гарантируем отступ после шапки
            if len(result_lines) > 1 and result_lines[1].strip():
                result_lines.insert(1, '')
            
            result_text = '\n'.join(result_lines)
        
        # 7. Для Zen удаляем эмодзи
        elif post_type == 'zen':
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF" 
                u"\U0001F680-\U0001F6FF"
                u"\U0001F900-\U0001F9FF"
                "]+", flags=re.UNICODE)
            result_text = emoji_pattern.sub(r'', result_text).strip()
        
        # 8. Финальная очистка (не более 2 пустых строк подряд)
        result_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', result_text)
        
        # 9. Удаляем лишние пробелы в начале строк
        result_lines = result_text.split('\n')
        cleaned_lines = []
        for line in result_lines:
            # Удаляем пробелы в начале, но сохраняем пустые строки
            if line.strip():
                cleaned_lines.append(line.strip())
            else:
                cleaned_lines.append('')
        
        result_text = '\n'.join(cleaned_lines)
        
        return result_text.strip()

    def _guarantee_telegram_structure(self, text, theme):
        """ГАРАНТИРОВАННО создает структуру Telegram-поста"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) < 3:
            return text
        
        # 1. Гарантировать заголовок с эмодзи
        if not any(e in lines[0][:5] for e in ['🌅', '🌞', '🌙']):
            lines[0] = f"{self.current_style['emoji']} {lines[0]}"
        
        return '\n'.join(lines)

    def _guarantee_zen_structure(self, text, theme):
        """ГАРАНТИРОВАННО создает структуру Zen-поста БЕЗ ШАБЛОНОВ"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) < 3:
            return text
        
        # ТОЛЬКО проверяем наличие вопроса/восклицания в начале
        if '?' not in lines[0] and '!' not in lines[0]:
            # Просто добавляем вопрос в существующий текст
            if '?' not in text and '!' not in text:
                lines.insert(0, f"Что важно знать о {theme.lower()}?")
        
        return '\n'.join(lines)

    def enhance_with_smart_conclusion(self, text, theme, post_type):
        """Просим Gemini улучшить завершение поста"""
        try:
            prompt = f"""
РОЛЬ: Ты профессиональный редактор с 20+ лет опыта.

ЗАДАЧА: Улучши завершение этого поста, сделав его ЕСТЕСТВЕННЫМ и логичным.

ТИП ПОСТА: {post_type}
ТЕМА: {theme}

ТЕКУЩИЙ ПОСТ:
{text}

ПРОБЛЕМЫ ТЕКУЩЕГО ЗАВЕРШЕНИЯ:
1. { "Слишком шаблонное" if any(marker in text for marker in ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']) else "Нужно улучшить" }
2. Недостаточно логично вытекает из содержания
3. Можно сделать более вовлекающим

ТРЕБОВАНИЯ К НОВОМУ ЗАВЕРШЕНИЮ:
• ДОЛЖНО естественно продолжать мысль поста
• НЕЛЬЗЯ использовать шаблонные фразы
• Добавить инсайт или новый ракурс
• Сделать завершение УНИКАЛЬНЫМ для этого конкретного поста
• Держать внимание до конца
• { "Включить вопрос к аудитории" if post_type == 'telegram' else "Создать глубокий вывод" }

ФОРМАТ ОТВЕТА:
УЛУЧШЕННОЕ ЗАВЕРШЕНИЕ: [твой вариант завершения]

Примеры ЕСТЕСТВЕННЫХ (нешаблонных) завершений:
• "Но самый важный урок здесь — не в методиках, а в..."
• "Это меняет правила игры для всех, кто..."
• "Секрет успеха — не в сложности подхода, а в..."
• "Вопрос не в том, нужно ли это делать, а в том, КАК делать правильно."
• "Это не просто тренд — это новый стандарт для тех, кто хочет оставаться на вершине."
"""
        
            response = self.generate_with_gemma(prompt)
            
            if response and "УЛУЧШЕННОЕ ЗАВЕРШЕНИЕ:" in response:
                parts = response.split("УЛУЧШЕННОЕ ЗАВЕРШЕНИЕ:", 1)
                if len(parts) > 1:
                    new_conclusion = parts[1].strip()
                    
                    # Заменяем старое завершение на новое
                    lines = text.split('\n')
                    
                    # Ищем хештеги (обычно в конце)
                    for i in range(len(lines)-1, max(len(lines)-5, 0), -1):
                        if '#' in lines[i]:
                            # Вставляем новое завершение перед хештегами
                            lines.insert(i, '')
                            lines.insert(i, new_conclusion)
                            return '\n'.join(lines)
                    
                    # Если не нашли хештеги, добавляем в конец
                    return f"{text}\n\n{new_conclusion}"
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Ошибка улучшения завершения: {e}")
            return text

    def _finalize_post_structure(self, text, post_type, theme, min_chars, max_chars):
        """ЕДИНСТВЕННЫЙ метод для финальной обработки поста с усиленной валидацией форматирования"""
        import re
        
        # 1. Контроль длины (один раз!)
        if len(text) > max_chars:
            text = self._hard_cut_text(text, max_chars)
        elif len(text) < min_chars:
            text = self._expand_text(text, min_chars, post_type)
        
        # 2. Восстановление и валидация визуального форматирования
        
        # 2a. Для Zen-постов: гарантировать пустую строку перед блоками завершения
        if post_type == 'zen':
            conclusion_markers = ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']
            for marker in conclusion_markers:
                if marker in text:
                    # Ищем все вхождения маркера
                    lines = text.split('\n')
                    for i in range(len(lines)-1, -1, -1):
                        if marker in lines[i] and i > 0:
                            # Проверяем, есть ли пустая строка перед блоком
                            if lines[i-1].strip() != '':
                                lines.insert(i, '')
                                logger.info(f"✅ Добавлена пустая строка перед блоком '{marker}' в Zen-посте")
                                text = '\n'.join(lines)
                            break
        
        # 2b. Для Telegram-постов: гарантировать пустую строку перед практическими блоками
        if post_type == 'telegram':
            practice_markers = ['🎯 Важно:', '📋 Шаги:', '🔧 Практика:']
            for marker in practice_markers:
                if marker in text:
                    # Ищем все вхождения маркера
                    lines = text.split('\n')
                    for i in range(len(lines)-1, -1, -1):
                        if marker in lines[i] and i > 0:
                            # Проверяем, есть ли пустая строка перед блоком
                            if lines[i-1].strip() != '':
                                lines.insert(i, '')
                                logger.info(f"✅ Добавлена пустая строка перед блоком '{marker}' в Telegram-посте")
                                text = '\n'.join(lines)
                            break
        
        # 2c. Для всех постов: гарантировать 2 пустые строки перед хештегами
        hashtag_pattern = r'(\n+)(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$'
        match = re.search(hashtag_pattern, text, re.MULTILINE)
        
        if match:
            # Заменяем любое количество переносов на 2 пустые строки
            text = re.sub(hashtag_pattern, r'\n\n\2', text)
        else:
            # Если нет хештегов, добавляем с соблюдением правила о 2 пустых строках
            hashtags = self.get_relevant_hashtags(theme, 3)
            if text.strip():
                # Убеждаемся, что в конце есть 2 пустые строки
                if not text.endswith('\n\n'):
                    text = text.rstrip() + '\n\n'
                text = text + ' '.join(hashtags)
        
        # 3. Улучшаем завершение через Gemini (только для длинных постов)
        if len(text) > 300 and random.random() < 0.7:  # 70% вероятности
            text = self.enhance_with_smart_conclusion(text, theme, post_type)
        
        # 4. Финальная проверка длины
        if len(text) > max_chars:
            text = text[:max_chars]
        
        # 5. Гарантия правильных отступов между блоками
        lines = text.split('\n')
        if len(lines) > 3:
            # Проверяем и добавляем пустые строки в ключевых местах
            final_lines = []
            for i, line in enumerate(lines):
                final_lines.append(line)
                
                # После шапки (первая непустая строка)
                if i == 0 and line.strip() and len(lines) > i+1:
                    final_lines.append('')
                
                # Перед хештегами (уже должно быть 2 пустые строки, проверяем)
                if '#' in line and i > 0 and lines[i-1].strip():
                    if not final_lines[-1] == '':
                        final_lines.insert(-1, '')
            
            text = '\n'.join(final_lines)
            
        # 6. Очистка лишних пустых строк (но сохраняем как минимум 1 между блоками)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 7. Убеждаемся, что хештеги корректны и не обрезаны
        hashtags_match = re.search(r'(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        if hashtags_match:
            hashtags = hashtags_match.group(1)
            # Проверяем, что хештеги не обрезаны (нет пробелов внутри хештегов)
            if ' #' in hashtags or hashtags.count('#') < 3:
                # Заменяем некорректные хештеги
                new_hashtags = ' '.join(self.get_relevant_hashtags(theme, 3))
                text = re.sub(r'(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', f'\n\n{new_hashtags}', text)
        
        return text

    def send_to_admin_for_moderation(self, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет только 2 поста (Telegram и Zen) администратору"""
        logger.info("📤 Отправляю только 2 поста администратору на модерацию...")
        
        success_count = 0
        post_ids = []
        
        edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
        
        # УСИЛЕННАЯ ФИНАЛЬНАЯ ОБРАБОТКА ПЕРЕД ОТПРАВКОЙ
        # Вызываем усиленный _finalize_post_structure непосредственно перед отправкой
        tg_min, tg_max = self.current_style['tg_chars']
        zen_min, zen_max = self.current_style['zen_chars']
        
        tg_text = self._finalize_post_structure(tg_text, 'telegram', theme, tg_min, tg_max)
        zen_text = self._finalize_post_structure(zen_text, 'zen', theme, zen_min, zen_max)
        
        # ФУНКЦИЯ ВАЛИДАЦИИ ПЕРЕД ОТПРАВКОЙ
        def validate_post_structure(text, post_type):
            """Проверяет структуру поста перед отправкой"""
            import re
            
            if post_type == 'telegram':
                errors = []
                # 1. Проверка эмодзи в начале
                lines = text.split('\n')
                if lines and not any(e in lines[0][:5] for e in ['🌅', '🌞', '🌙']):
                    errors.append("❌ Нет эмодзи в начале Telegram поста")
                
                # 2. Проверка практического блока
                if not any(marker in text for marker in 
                          ['Практический совет:', 'Что делать дальше:', 'Конкретные действия:', '🎯']):
                    errors.append("⚠️ Нет практического блока")
                
                # 3. Проверка хештегов
                hashtags = re.findall(r'#[\w\u0400-\u04FF]+', text)
                if len(hashtags) < 3:
                    errors.append("⚠️ Мало хештегов")
                
                # 4. Проверка пустой строки перед практическими блоками
                practice_markers = ['🎯 Важно:', '📋 Шаги:', '🔧 Практика:']
                for marker in practice_markers:
                    if marker in text:
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if marker in line and i > 0:
                                if lines[i-1].strip() == '':
                                    break  # ✅ Есть пустая строка
                                else:
                                    errors.append(f"⚠️ Нет пустой строки перед блоком '{marker}'")
                                break
                
                # 5. Проверка 2 пустых строк перед хештегами
                hashtag_match = re.search(r'(\n\n)(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
                if not hashtag_match:
                    errors.append("⚠️ Нет 2 пустых строк перед хештегами")
                
                return errors
            
            elif post_type == 'zen':
                errors = []
                # 1. Проверка отсутствия эмодзи
                if any(e in text for e in ['🌅', '🌞', '🌙', '🎯', '📊', '🚀']):
                    errors.append("❌ Есть эмодзи в Zen посте")
                
                # 2. Проверка крючка-убийцы
                lines = text.split('\n')
                first_line = lines[0] if lines else ""
                if not ('?' in first_line or '!' in first_line or len(first_line) < 40):
                    errors.append("⚠️ Слабый крючок-убийца")
                
                # Проверка блока завершения
                has_conclusion = any(
                    marker in text for marker in [
                        'Почему это важно:', 
                        'Что из этого следует:', 
                        'Мнение экспертов:'
                    ]
                )
                if not has_conclusion:
                    errors.append("❌ Zen пост должен содержать блок завершения")
                
                # Проверка визуального разделения перед блоком завершения
                for marker in ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']:
                    if marker in text:
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if marker in line and i > 0:
                                if lines[i-1].strip() == '':
                                    break  # ✅ Есть пустая строка
                                else:
                                    errors.append(f"⚠️ Нет визуального разделения (пустой строки) перед блоком '{marker}'")
                                break
                
                # Проверка 2 пустых строк перед хештегами
                hashtag_match = re.search(r'(\n\n)(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
                if not hashtag_match:
                    errors.append("⚠️ Нет 2 пустых строк перед хештегами")
                
                return errors
            
            return []
        
        # Общая функция для отправки поста - только 2 поста
        def send_post(post_type, text, channel):
            nonlocal success_count
            try:
                logger.info(f"📨 Отправляем {post_type} пост администратору")
                
                # ВАЛИДАЦИЯ перед отправкой
                validation_errors = validate_post_structure(text, post_type)
                if validation_errors:
                    logger.warning(f"⚠️ Проблемы в {post_type} посте: {validation_errors}")
                    # НЕ прерываем - всё равно отправляем, но логируем
                
                keyboard = self.create_inline_keyboard()
                
                # TELEGRAM: ограничение длины подписи к фото - 1024 символа
                # ZEN: можно больше, но для консистентности используем тот же лимит
                
                caption_length_limit = 1024
                
                if image_url and image_url.strip() and image_url.startswith('http'):
                    try:
                        # Если текст длиннее лимита - обрезаем до лимита
                        caption = text[:caption_length_limit]
                        
                        sent_message = self.bot.send_photo(
                            chat_id=ADMIN_CHAT_ID,
                            photo=image_url,
                            caption=caption,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        
                        # НЕ отправляем продолжение как отдельное сообщение - только 1 сообщение
                        message_id = sent_message.message_id
                        
                    except Exception as photo_error:
                        logger.warning(f"⚠️ Не удалось отправить с картинкой: {photo_error}")
                        # Fallback: текстовый пост
                        sent_message = self.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=text,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        message_id = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    message_id = sent_message.message_id
                
                # Сохраняем пост в ожидании модерации
                self.pending_posts[message_id] = {
                    'type': post_type,
                    'text': text,
                    'image_url': image_url or '',
                    'channel': channel,
                    'status': PostStatus.PENDING,
                    'theme': theme,
                    'slot_style': self.current_style,
                    'slot_time': slot_time,
                    'hashtags': re.findall(r'#[\w\u0400-\u04FF]+', text),
                    'edit_timeout': edit_timeout,
                    'sent_time': datetime.now().isoformat(),
                    'keyboard_message_id': message_id
                }
                
                logger.info(f"✅ {post_type} пост отправлен администратору (ID: {message_id})")
                success_count += 1
                post_ids.append(message_id)
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки {post_type} поста: {e}")
        
        # ОТПРАВЛЯЕМ ТОЛЬКО 2 ПОСТА - не более!
        send_post('telegram', tg_text, MAIN_CHANNEL)
        time.sleep(1)  # Пауза между отправками
        send_post('zen', zen_text, ZEN_CHANNEL)
        time.sleep(1)
        
        # 3. ОТПРАВИТЬ ИНФОРМАЦИОННОЕ СООБЩЕНИЕ
        if post_ids:  # ТОЛЬКО ЕСЛИ ЕСТЬ ID
            self.send_moderation_instructions(
                post_ids, slot_time, theme, tg_text, zen_text, edit_timeout
            )
        
        return success_count

    def send_moderation_instructions(self, post_ids, slot_time, theme, tg_text, zen_text, edit_timeout):
        """ГАРАНТИРОВАННО отправляет инструкции"""
        try:
            import re
            
            # 1. Подготовить данные
            timeout_str = edit_timeout.strftime("%H:%M") + " МСК"
            
            # 2. Проверить структуру постов
            tg_has_emoji = any(e in tg_text[:5] for e in ['🌅', '🌞', '🌙'])
            tg_has_practice = any(marker in tg_text for marker in 
                                 ['Практический совет:', 'Что делать дальше:', '🎯'])
            tg_has_useful = any(keyword in tg_text.lower() for keyword in 
                               ['исследовани', 'отчёт', 'данные'])
            
            zen_has_hook = any('?' in line or '!' in line for line in zen_text.split('\n')[:2])
            zen_has_useful = any(keyword in zen_text.lower() for keyword in 
                                ['исследовани', 'отчёт', 'данные', 'статистик', 'анализ', 'кейс'])
            
            # Подсчет хештегов
            tg_hashtags_count = len(re.findall(r'#[\w\u0400-\u04FF]+', tg_text))
            zen_hashtags_count = len(re.findall(r'#[\w\u0400-\u04FF]+', zen_text))
            
            # 3. Сформировать сообщение - используем обычные строки вместо f-строки с тройными кавычками
            instruction = (
                "<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
                f"<b>📱 1. Telegram пост (с эмодзи)</b>\n"
                f"   🎯 Канал: {MAIN_CHANNEL}\n"
                f"   🕒 Время: {slot_time} МСК\n"
                f"   📏 Символов: {len(tg_text)} (лимит: {self.current_style['tg_chars'][0]}-{self.current_style['tg_chars'][1]})\n"
                f"   #️⃣ Хештеги: {tg_hashtags_count} шт.\n"
                f"   {'✅' if tg_has_emoji else '⚠️'} Эмодзи-шапка: {'Есть' if tg_has_emoji else 'НЕТ!'}\n"
                f"   {'✅' if tg_has_practice else '⚠️'} Практический блок: {'Есть' if tg_has_practice else 'НЕТ!'}\n"
                f"   {'✅' if tg_has_useful else '📊'} Полезняшка: {'Есть' if tg_has_useful else 'Нет'}\n"
                f"   📌 Используйте кнопки под постом для модерации\n\n"
                f"<b>📝 2. Дзен пост (без эмодзи)</b>\n"
                f"   🎯 Канал: {ZEN_CHANNEL}\n"
                f"   🕒 Время: {slot_time} МСК\n"
                f"   📏 Символов: {len(zen_text)} (лимит: {self.current_style['zen_chars'][0]}-{self.current_style['zen_chars'][1]})\n"
                f"   #️⃣ Хештеги: {zen_hashtags_count} шт.\n"
                f"   {'✅' if zen_has_hook else '⚠️'} Крючок-убийца: {'Есть' if zen_has_hook else 'НЕТ!'}\n"
                f"   {'✅' if zen_has_useful else '📊'} Полезняшка: {'Есть' if zen_has_useful else 'Нет'}\n"
                f"   📌 Используйте кнопки под постом для модерации\n\n"
                "<b>🎯 Кнопки модерации под каждым постом:</b>\n"
                "────\n"
                "• ✅ Опубликовать - одобрить и опубликовать\n"
                "• ❌ Отклонить - отклонить пост\n"
                "• 📝 Текст - перегенерировать только текст\n"
                "• 🖼️ Фото - найти новое изображение\n"
                "• 🔄 Всё - полная переделка (новая тема, фото, подача)\n"
                "• ⚡ Новое - выбрать тему для нового поста\n\n"
                f"<b>⏰ Время на решение:</b> до {timeout_str} (10 минут)\n"
                "<b>📢 После истечения времени посты будут автоматически отклонены</b>"
            )
            
            # 4. ГАРАНТИРОВАННО отправить
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=instruction,
                parse_mode='HTML'
            )
            logger.info("✅ Информационное сообщение отправлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки инструкции: {e}")
            # АВАРИЙНАЯ ОТПРАВКА
            try:
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"<b>✅ Посты отправлены на модерацию в {slot_time}</b>\n"
                        f"<b>⏰ Время на правки до:</b> {timeout_str}\n"
                        f"<b>📱 Telegram:</b> {len(tg_text)} символов\n"
                        f"<b>📝 Zen:</b> {len(zen_text)} символов"
                    ),
                    parse_mode='HTML'
                )
            except Exception as fallback_error:
                logger.error(f"❌ Даже аварийная отправка не сработала: {fallback_error}")
    def publish_to_channel(self, text, image_url, channel):
        """Публикует пост в канал"""
        try:
            logger.info(f"📤 Публикую пост в канал {channel}")
            
            hashtags = re.findall(r'#[\w\u0400-\u04FF]+', text)
            if not hashtags:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Нет хештегов в посте для {channel}")
                backup_hashtags = "#бизнес #советы #развитие"
                text = f"{text}\n\n{backup_hashtags}"
                logger.warning(f"⚠️ Добавлены резервные хештеги: {backup_hashtags}")
            
            logger.info(f"✅ Хештеги перед публикации: {len(hashtags)} шт.")
            
            if image_url and image_url.strip() and image_url.startswith('http'):
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
            
            if len(re.findall(r'#[\w\u0400-\u04FF]+', text)) < 3:
                return False, "❌ Telegram пост должен содержать минимум 3 хештега"
                
        elif post_type == 'zen':
            if any(e in text for e in ['🌅', '🌞', '🌙']):
                return False, "❌ Дзен пост НЕ должен содержать эмодзи"
            
            # Проверка блока завершения
            has_conclusion = any(
                marker in text for marker in [
                    'Почему это важно:', 
                    'Что из этого следует:', 
                    'Мнение экспертов:'
                ]
            )
            if not has_conclusion:
                return False, "❌ Zen пост должен содержать блок завершения"
            
            # Проверка визуального разделения перед блоком завершения
            import re
            for marker in ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']:
                if marker in text:
                    # Ищем маркер в тексте
                    lines = text.split('\n')
                    for i, line in enumerate(lines):
                        if marker in line and i > 0:
                            # Проверяем, есть ли пустая строка перед блоком
                            if lines[i-1].strip() == '':
                                return True, "✅ Структура корректна (есть визуальное разделение)"
                            else:
                                return False, f"⚠️ Нет визуального разделения (пустой строки) перед блоком '{marker}'"
            
            return True, "✅ Структура корректна"
        
        return True, "✅ Структура корректна"

    def create_and_send_posts(self, slot_time, slot_style, is_test=False):
        """Создает и отправляет постов с ГАРАНТИРОВАННОЙ структурой"""
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
            
            # ФИНАЛЬНАЯ ОБРАБОТКА ЕДИНЫМ МЕТОДОМ
            tg_text = self._finalize_post_structure(
                tg_text, 'telegram', theme, tg_min, tg_max
            )
            
            zen_text = self._finalize_post_structure(
                zen_text, 'zen', theme, zen_min, zen_max
            )
            
            # ПРОВЕРЯЕМ РЕЗУЛЬТАТ
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            
            if tg_len < tg_min or tg_len > tg_max or zen_len < zen_min or zen_len > zen_max:
                logger.error(f"❌ Ошибка структуры поста после генерации. Telegram: {tg_len} ({tg_min}-{tg_max}), Zen: {zen_len} ({zen_min}-{zen_max})")
                return False
            
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
            logger.info(f"🧹 Очистка ресурсов перед завершении с кодом {exit_code}")
            
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
