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
import base64
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from typing import Dict, List, Optional, Tuple, Any, Union
import telebot
from telebot.types import Message, ReactionTypeEmoji, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ========== КОНФИГУРАЦИЯ ==========
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL = os.environ.get("MAIN_CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL = os.environ.get("ZEN_CHANNEL_ID", "@tehdzenm")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
GITHUB_TOKEN = os.environ.get("MANAGER_GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME", "")
REPO_OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "")

# Валидация критических переменных
CRITICAL_VARS = {
    "BOT_TOKEN": BOT_TOKEN,
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "ADMIN_CHAT_ID": ADMIN_CHAT_ID
}

for var_name, var_value in CRITICAL_VARS.items():
    if not var_value:
        logger.error(f"❌ {var_name} не установен!")
        sys.exit(1)

if not PEXELS_API_KEY:
    logger.warning("⚠️ PEXELS_API_KEY не установен! Будут использоваться дефолтные картинки")

logger.info("📤 Режим: отправка постов в личный чат администратора")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json'
})
session.timeout = 30


# ========== КОНСТАНТЫ И КЛАССЫ ==========
class PostStatus:
    """Статусы постов"""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    PUBLISHED = "published"
    REJECTED = "rejected"


class TextPostProcessor:
    """Класс для минимальной пост-обработки текстов"""
    
    def __init__(self, theme: str, slot_style: Dict, post_type: str):
        self.theme = theme
        self.slot_style = slot_style
        self.post_type = post_type
        self.min_chars, self.max_chars = self._get_char_limits()
        
    def _get_char_limits(self) -> Tuple[int, int]:
        """Получает лимиты символов"""
        if self.post_type == 'telegram':
            return self.slot_style['tg_chars']
        return self.slot_style['zen_chars']
    
    def process(self, raw_text: str) -> str:
        """Минимальная пост-обработка текста"""
        if not raw_text or len(raw_text.strip()) < 50:
            return raw_text
            
        logger.info(f"🔧 Базовая пост-обработка {self.post_type} поста ({len(raw_text)} символов)")
        
        # 1. Удаляем звездочки из начала Telegram поста
        if self.post_type == 'telegram':
            raw_text = re.sub(r'^\*\*', '', raw_text)
            raw_text = re.sub(r'^\*\*\s*', '', raw_text)
        
        # 2. Удаляем "##вечерний пост" из Zen поста
        if self.post_type == 'zen':
            raw_text = re.sub(r'^##вечерний пост\s*\n?', '', raw_text, flags=re.IGNORECASE)
        
        # 3. Удаляем "Доброе утро", "Добрый день", "Добрый вечер" из начала поста
        if self.post_type == 'telegram':
            raw_text = re.sub(r'^(Доброе утро|Добрый день|Добрый вечер|Начало дня|Старт утра|В завершение дня|Подводя итоги)[,.!?\s]*', '', raw_text, flags=re.IGNORECASE)
            raw_text = raw_text.strip()
        
        # 4. Гарантируем эмодзи в начале Telegram поста
        if self.post_type == 'telegram' and 'emoji' in self.slot_style:
            if not raw_text.startswith(self.slot_style['emoji']):
                raw_text = f"{self.slot_style['emoji']} {raw_text}"
                logger.info("✅ Добавлен эмодзи в начало Telegram поста")
        
        # 5. Удаляем все эмодзи из Zen поста (кроме Telegram)
        if self.post_type == 'zen':
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF" 
                u"\U0001F680-\U0001F6FF"
                u"\U0001F900-\U0001F9FF"
                "]+", flags=re.UNICODE)
            raw_text = emoji_pattern.sub(r'', raw_text).strip()
        
        # 6. Проверяем и исправляем недостающие структурные элементы
        if self.post_type == 'telegram':
            # Проверяем наличие и заполненность ключевых структурных элементов
            structural_elements = [
                ('🎯 Важно:', 'фиксация сути'),
                ('📋 Шаги:', 'если уместны, но не обязательны'),
                ('🔧 Практика:', 'если есть прикладной смысл'),
                ('ВОПРОС ДЛЯ АУДИТОРИИ:', 'открывающий, не итоговый')
            ]
            
            for element, default_content in structural_elements:
                pattern = re.compile(f'{re.escape(element)}\\s*\\[содержимое\\]', re.IGNORECASE)
                if pattern.search(raw_text):
                    # Заменяем [содержимое] на дефолтное
                    raw_text = pattern.sub(f'{element} {default_content}', raw_text)
                    logger.warning(f"⚠️ Заменен шаблон {element}")
                
                # Проверяем, есть ли вообще элемент (кроме шагов и практики - они опциональны)
                if element in ['🎯 Важно:', 'ВОПРОС ДЛЯ АУДИТОРИИ:'] and element not in raw_text:
                    # Добавляем обязательные элементы
                    raw_text += f"\n\n{element} {default_content}"
                    logger.warning(f"⚠️ Добавлен обязательный элемент: {element}")
        
        elif self.post_type == 'zen':
            # Проверяем наличие и заполненность ключевых структурных элементов для Zen
            zen_elements = [
                ('Почему это важно:', 'фиксация ценности мысли'),
                ('Что из этого следует:', 'практические следствия'),
                ('Мнение экспертов:', 'обобщающая мысль'),
                ('ВОПРОС ДЛЯ ОБСУЖДЕНИЯ:', 'открывающий вопрос')
            ]
            
            for element, default_content in zen_elements:
                pattern = re.compile(f'{re.escape(element)}\\s*\\[.*?\\]', re.IGNORECASE)
                if pattern.search(raw_text):
                    # Заменяем [что-то] на дефолтное, если оно пустое или шаблонное
                    if re.search(f'{re.escape(element)}\\s*\\[(фиксация ценности мысли|практические следствия|обобщающая мысль|открывающий вопрос)\\]', raw_text, re.IGNORECASE):
                        raw_text = pattern.sub(f'{element} {default_content}', raw_text)
                        logger.warning(f"⚠️ Заменен шаблон {element}")
            
            # Проверяем обязательные элементы
            if 'ВОПРОС ДЛЯ ОБСУЖДЕНИЯ:' not in raw_text:
                raw_text += f"\n\nВОПРОС ДЛЯ ОБСУЖДЕНИЯ: открывающий вопрос"
                logger.warning("⚠️ Добавлен вопрос для обсуждения")
        
        # 7. Форматирование переносов строк
        lines = [line.strip() for line in raw_text.split('\n') if line.strip() or line == '']
        formatted_lines = []
        
        for i, line in enumerate(lines):
            if not line:
                if not formatted_lines or formatted_lines[-1] != '':
                    formatted_lines.append('')
                continue
            
            formatted_lines.append(line)
            
            # Добавляем пустую строку после шапки в Zen
            if i == 0 and self.post_type == 'zen' and (line.endswith('?') or line.endswith('!')):
                formatted_lines.append('')
        
        result = '\n'.join(formatted_lines)
        
        # 8. Проверяем, что пост заканчивается хештегами
        if self.post_type == 'telegram':
            if not re.search(r'#[a-zA-Zа-яА-ЯёЁ0-9_]+\s*$', result):
                # Добавляем стандартные хештеги если их нет
                hashtag_map = {
                    "HR и управление персоналом": "#hr #персонал #управление #работа #карьера",
                    "PR и коммуникации": "#pr #коммуникации #маркетинг #связи #бренд",
                    "ремонт и строительство": "#ремонт #строительство #дом #дизайн #интерьер"
                }
                hashtags = hashtag_map.get(self.theme, "#работа #бизнес #успех #развитие")
                result += f"\n\n{hashtags}"
                logger.info("✅ Добавлены хештеги в конец Telegram поста")
        
        elif self.post_type == 'zen':
            if not re.search(r'#[a-zA-Zа-яА-ЯёЁ0-9_]+\s*$', result):
                # Добавляем стандартные хештеги если их нет
                hashtag_map = {
                    "HR и управление персоналом": "#hr #персонал #управление #работа #карьера",
                    "PR и коммуникации": "#pr #коммуникации #маркетинг #связи #бренд",
                    "ремонт и строительство": "#ремонт #строительство #дом #дизайн #интерьер"
                }
                hashtags = hashtag_map.get(self.theme, "#работа #бизнес #успех #развитие")
                result += f"\n\n{hashtags}"
                logger.info("✅ Добавлены хештеги в конец Zen поста")
        
        # 9. Проверяем, что пост не обрывается на середине предложения
        if result.strip() and result.strip()[-1] not in ['.', '!', '?', ':', ')', ']', '}']:
            # Если пост обрывается без правильного окончания, добавляем многоточие
            result = result.rstrip() + "..."
            logger.warning("⚠️ Пост обрывался, добавлено многоточие")
        
        # 10. Валидация длины
        text_length = len(result)
        if text_length < self.min_chars:
            logger.warning(f"⚠️ Текст слишком короткий: {text_length} < {self.min_chars}")
        elif text_length > self.max_chars:
            logger.warning(f"⚠️ Текст слишком длинный: {text_length} > {self.max_chars}")
        else:
            logger.info(f"✅ Длина текста OK: {text_length} символов (нужно {self.min_chars}-{self.max_chars})")
        
        return result.strip()


class GitHubAPIManager:
    """Оптимизированный класс для управления GitHub API"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.repo_owner = REPO_OWNER
        self.repo_name = REPO_NAME
    
    def _get_headers(self) -> Dict:
        """Возвращает заголовки для запросы"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers
    
    def get_file_content(self, file_path: str) -> Union[Dict, str]:
        """Получает содержимое файла из репозитория"""
        try:
            if not self.github_token or not self.repo_owner or not self.repo_name:
                return {"error": "Недостаточно данных для доступа к репозиторию"}
            
            url = f"{self.BASE_URL}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = session.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                content = response.json()
                if "content" in content and content.get("encoding") == "base64":
                    decoded = base64.b64decode(content["content"]).decode('utf-8')
                    return decoded
                return {"error": "Неожиданный формат ответа"}
            return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            logger.error(f"❌ Ошибка GitHub API: {e}")
            return {"error": str(e)}
    
    def edit_file(self, file_path: str, new_content: str, commit_message: str) -> Dict:
        """Редактирует файл в репозитории"""
        try:
            if not self.github_token or not self.repo_owner or not self.repo_name:
                return {"error": "Недостаточно данных для доступа к репозиторию"}
            
            # Получаем текущий файл для SHA
            url = f"{self.BASE_URL}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = session.get(url, headers=self._get_headers())
            
            if response.status_code != 200:
                return {"error": "Файл не найден"}
            
            current_file = response.json()
            sha = current_file["sha"]
            
            # Кодируем новый контент
            encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
            
            data = {
                "message": commit_message,
                "content": encoded_content,
                "sha": sha
            }
            
            response = session.put(url, headers=self._get_headers(), json=data)
            return response.json()
        except Exception as e:
            logger.error(f"❌ Ошибка редактирования файла: {e}")
            return {"error": str(e)}


class TelegramBot:
    """Основной класс Telegram бота с оптимизированной структурой"""
    
    # Константы
    THEMES = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
    
    TIME_STYLES = {
        "11:00": {
            "name": "Утренний пост",
            "type": "morning",
            "emoji": "🌅",
            "style": "энерго1старт: короткая польза, лёгкая динамика, мотивирующий фокус",
            "tg_chars": (400, 600),
            "zen_chars": (600, 700),
            "tg_tokens": (80, 120),
            "zen_tokens": (120, 140),
            "total_tokens": (200, 260)
        },
        "15:00": {
            "name": "Дневной пост",
            "type": "day",
            "emoji": "🌞",
            "style": "рациональность и аналитика: наблюдение, разбор явления, микро1исследование",
            "tg_chars": (700, 900),
            "zen_chars": (700, 900),
            "tg_tokens": (140, 180),
            "zen_tokens": (140, 180),
            "total_tokens": (280, 360)
        },
        "20:00": {
            "name": "Вечерний пост",
            "type": "evening",
            "emoji": "🌙",
            "style": "глубина и история: личный взгляд, мини1история, аналогия",
            "tg_chars": (600, 900),
            "zen_chars": (700, 800),
            "tg_tokens": (120, 180),
            "zen_tokens": (140, 160),
            "total_tokens": (260, 340)
        }
    }
    
    def __init__(self, target_slot: str = None, auto: bool = False):
        self.target_slot = target_slot
        self.auto = auto
        
        # Инициализация бота
        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
        
        # Менеджеры
        self.github_manager = GitHubAPIManager()
        
        # Состояние
        self.pending_posts: Dict[int, Dict] = {}
        self.post_history = self._load_json("post_history.json", {
            "sent_slots": {},
            "rejected_slots": {}
        })
        self.image_history = self._load_json("image_history.json", {
            "used_images": []
        })
        
        self.current_theme = None
        self.current_format = None
        self.current_style = None
        
        # Флаги и блокировки
        self.published_posts_count = 0
        self.workflow_complete = False
        self.stop_polling = False
        self.publish_lock = threading.Lock()
        self.completion_lock = threading.Lock()
        self.polling_lock = threading.Lock()
        
        # Поток polling
        self.polling_thread = None
        
        # Callback обработчики
        self.callback_handlers = {
            "publish": self._handle_approval,
            "reject": self._handle_rejection,
            "edit_text": lambda msg_id, post_data, call: self._handle_edit_request(msg_id, post_data, call, "переделай текст"),
            "edit_photo": lambda msg_id, post_data, call: self._handle_edit_request(msg_id, post_data, call, "замени фото"),
            "edit_all": lambda msg_id, post_data, call: self._handle_edit_request(msg_id, post_data, call, "переделай полностью"),
            "new_post": self._handle_new_post_request,
            "back_to_main": self._handle_back_to_main
        }
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    def _load_json(self, filename: str, default_data: Dict) -> Dict:
        """Загружает данные из JSON файла"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки {filename}: {e}")
        return default_data
    
    def _save_json(self, filename: str, data: Dict) -> bool:
        """Сохраняет данные в JSON файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения {filename}: {e}")
            return False
    
    def get_moscow_time(self) -> datetime:
        """Возвращает текущее время по Москве (UTC+3)"""
        return datetime.utcnow() + timedelta(hours=3)
    
    # ========== ОСНОВНАЯ ЛОГИКА ==========
    def generate_with_gemini(self, prompt: str, post_type: str) -> Optional[str]:
        """Генерация через Gemini API с учетом типа поста"""
        try:
            if post_type == 'telegram':
                token_range = self.current_style.get('tg_tokens', (80, 120)) if self.current_style else (80, 120)
                max_tokens = token_range[1]  # Берем максимальное значение из диапазона
            else:  # zen
                token_range = self.current_style.get('zen_tokens', (120, 140)) if self.current_style else (120, 140)
                max_tokens = token_range[1]  # Берем максимальное значение из диапазона
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.85,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": max_tokens,
                }
            }
            
            response = session.post(url, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    logger.info(f"✅ {post_type.upper()} текст получен, длина: {len(generated_text)} символов, токены: до {max_tokens}")
                    return generated_text
            
            logger.error(f"❌ Ошибка API: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"💥 Ошибка генерации {post_type}: {e}")
            return None
    
    def create_telegram_prompt(self, theme: str, slot_style: Dict, text_format: str, image_description: str) -> str:
        """Создает промпт для Telegram поста"""
        tg_min, tg_max = slot_style['tg_chars']
        tg_token_min, tg_token_max = slot_style['tg_tokens']
        
        # Хештеги для тем
        hashtag_map = {
            "HR и управление персоналом": "#hr #персонал #управление",
            "PR и коммуникации": "#pr #коммуникации #маркетинг",
            "ремонт и строительство": "#ремонт #строительство #дом"
        }
        hashtags = hashtag_map.get(theme, "#работа #бизнес #успех")
        
        prompt = f"""
TELEGRAM — УНИВЕРСАЛЬНАЯ СТРУКТУРА (100% покрытие)

ТЕКУЩИЙ СЛОТ: {slot_style['name']} ({slot_style['emoji']})
ТИП ПОСТА: Telegram
ЛИМИТ СИМВОЛОВ: {tg_min}-{tg_max} символов (ВКЛЮЧАЯ ХЕШТЕГИ И ВСЕ СИМВОЛЫ!)
ЛИМИТ ТОКЕНОВ: {tg_token_min}-{tg_token_max} токенов

🎯 ТЕМА: {theme}
📝 ФОРМАТ ПОДАЧИ: {text_format}
🏷️ ХЕШТЕГИ: 2-5 хештегов по теме (используй: {hashtags})

СТРОГАЯ СТРУКТУРА (НЕ МЕНЯТЬ):

1. ЗАГОЛОВОК (с эмодзи {slot_style['emoji']})
   {slot_style['emoji']} [заголовок: фиксирует тему или мысль, сразу задает позицию]
   НЕ анонс и НЕ кликбейт
   ЗАПРЕЩЕНО: "Доброе утро", "Добрый день", "Добрый вечер"

2. ПЕРВЫЙ БЛОК — ВХОД В МЫСЛЬ
   Начало рассуждения, обозначение темы, задание тона
   Форма: утверждение, наблюдение, сомнение, тезис

3. ВТОРОЙ БЛОК — РАЗВИТИЕ
   Развертывание мысли, углубление, усложнение
   Форма не фиксирована

4. ТРЕТИЙ БЛОК — УСИЛЕНИЕ ИЛИ УТОЧНЕНИЕ (опционально)
   Сделать мысль объемнее, показать границы, уточнить о чем речь
   МОЖНО пропустить если не нужно

5. СТРУКТУРИРУЮЩИЕ ЭЛЕМЕНТЫ (выборочно, не все сразу):
   🎯 Важно — фиксация сути (ОБЯЗАТЕЛЬНО)
   📋 Шаги — если уместны, но не обязательны
   🔧 Практика — если есть прикладной смысл
   Критично для недопущения зацикливания

6. ВОПРОС ДЛЯ АУДИТОРИИ (ОБЯЗАТЕЛЬНО)
   Открывающий вопрос, а не итоговый
   Возвращает инициативу читателю

7. ХЕШТЕГИ (2-5 по теме) (ОБЯЗАТЕЛЬНО)
   {hashtags}

ГЛАВНЫЕ ПРИНЦИПЫ:
• Нет обязательных смыслов (боль, проблема, кейс — опциональны)
• Каждый блок — функция, а не тема
• Блоки можно пропускать, кроме заголовка и вопроса
• Мысль может начинаться где угодно
• Ты не контент пишешь — ты строишь пространство для мысли

СТРОГИЕ ТРЕБОВАНИЯ:
• Весь пост ДОЛЖЕН быть {tg_min}-{tg_max} символов
• Начинай с {slot_style['emoji']} и заголовка, БЕЗ приветствий
• Хештеги ВКЛЮЧЕНЫ в лимит символов
• Пост должен быть ЗАКОНЧЕННЫМ
• ЗАПРЕЩЕНО оставлять [содержимое] или шаблоны
• Каждый элемент должен содержать реальный текст

ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный/удаленный формат работы
• Релокацию
• Приветствия

РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работа в офисе

🖼️ КАРТИНКА: {image_description}

КОНЕЧНЫЙ РЕЗУЛЬТАТ ДОЛЖЕН БЫТЬ ГОТОВЫМ TELEGRAM ПОСТОМ С ВЫШЕУКАЗАННОЙ СТРУКТУРОЙ."""
        
        return prompt
    
    def create_zen_prompt(self, theme: str, slot_style: Dict, text_format: str, image_description: str) -> str:
        """Создает промпт для Zen поста"""
        zen_min, zen_max = slot_style['zen_chars']
        zen_token_min, zen_token_max = slot_style['zen_tokens']
        
        # Хештеги для тем
        hashtag_map = {
            "HR и управление персоналом": "#hr #персонал #управление",
            "PR и коммуникации": "#pr #коммуникации #маркетинг",
            "ремонт и строительство": "#ремонт #строительство #дом"
        }
        hashtags = hashtag_map.get(theme, "#работа #бизнес #успех")
        
        prompt = f"""
ЯНДЕКС ДЗЕН — УНИВЕРСАЛЬНАЯ СТРУКТУРА (100% покрытие)

ТЕКУЩИЙ СЛОТ: {slot_style['name']}
ТИП ПОСТА: Дзен
ЛИМИТ СИМВОЛОВ: {zen_min}-{zen_max} символов (ВКЛЮЧАЯ ХЕШТЕГИ И ВСЕ СИМВОЛЫ!)
ЛИМИТ ТОКЕНОВ: {zen_token_min}-{zen_token_max} токенов

🎯 ТЕМА: {theme}
📝 ФОРМАТ ПОДАЧИ: {text_format}
🏷️ ХЕШТЕГИ: 2-5 хештегов по теме (используй: {hashtags})

СТРОГАЯ СТРУКТУРА (НЕ МЕНЯТЬ):

1. ШАПКА — ТОЧКА ВХОДА
   [провокационный вопрос или утверждение]
   Задает угол зрения, обозначает напряжение, фиксирует позицию
   После шапки ОБЯЗАТЕЛЬНО пустая строка

2. ПЕРВЫЙ БЛОК — РАЗВЕРТЫВАНИЕ ТЕМЫ
   Раскрывает направление мысли, а не "описывает реальность"
   МОЖНО: поставить вопрос, начать рассуждение, обозначить тему
   НЕЛЬЗЯ: делать выводы, давать советы, закрывать мысль

3. ВТОРОЙ БЛОК — РАЗВИТИЕ ИЛИ УГЛУБЛЕНИЕ
   Двигает мысль дальше
   Форма: анализ, сравнение, противопоставление, логическое продолжение
   Это ядро текста, не обязано быть про проблему

4. ТРЕТИЙ БЛОК — СМЫСЛОВОЙ ПОВОРОТ (опционально)
   Изменяет траекторию мышления читателя
   МОЖНО: парадокс, неожиданное следствие, снятие иллюзии
   Это не вывод, а поворот

5. СМЫСЛОВОЙ ЯКОРЬ (ОБЯЗАТЕЛЬНО выбрать ОДИН):
   Почему это важно: [фиксация ценности мысли]
   или
   Что из этого следует: [практические следствия]
   или
   Мнение экспертов: [обобщающая мысль]
   Зафиксировать ценность, показать зачем эта мысль читателю

6. ВОПРОС ДЛЯ ОБСУЖДЕНИЯ (ОБЯЗАТЕЛЬНО)
   Возвращает инициативу читателю
   Расширяет поле темы, провоцирует опыт или позицию
   Вопрос не закрывает тему, а открывает её дальше

7. ХЕШТЕГИ (2-5 по теме) (ОБЯЗАТЕЛЬНО)
   {hashtags}

СТРОГИЕ ТРЕБОВАНИЯ:
• Весь пост ДОЛЖЕН быть {zen_min}-{zen_max} символов
• НИКАКИХ ЭМОДЗИ во всем посте
• После шапки ОБЯЗАТЕЛЬНО пустая строка
• Хештеги ВКЛЮЧЕНЫ в лимит символов
• Пост должен быть ЗАКОНЧЕННЫМ
• ЗАПРЕЩЕНО оставлять шаблоны типа [ключевые выводы]
• Каждый элемент должен содержать реальный текст
• Шапка ничего не обещает и не объясняет, существует отдельно от текста

ЗАПРЕЩЕНО УПОМИНАТЬ:
• Гибридный/удаленный формат работы
• Релокацию

РАЗРЕШЕНО УПОМИНАТЬ:
• Офисную работу
• Работа в офисе

🖼️ КАРТИНКА: {image_description}

КОНЕЧНЫЙ РЕЗУЛЬТАТ ДОЛЖЕН БЫТЬ ГОТОВЫМ ДЗЕН ПОСТОМ С ВЫШЕУКАЗАННОЙ СТРУКТУРОЙ."""
        
        return prompt
    
    def generate_with_retry(self, theme: str, slot_style: Dict, text_format: str, image_description: str,
                           max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Генерация постов с повторными попытками"""
        tg_min, tg_max = slot_style['tg_chars']
        zen_min, zen_max = slot_style['zen_chars']
        
        tg_text = None
        zen_text = None
        
        # Генерируем Telegram пост
        logger.info("🤖 Генерация Telegram поста...")
        for attempt in range(max_attempts):
            logger.info(f"🤖 Telegram попытка {attempt+1}/{max_attempts}")
            
            tg_prompt = self.create_telegram_prompt(theme, slot_style, text_format, image_description)
            generated_tg = self.generate_with_gemini(tg_prompt, 'telegram')
            
            if generated_tg:
                tg_processor = TextPostProcessor(theme, slot_style, 'telegram')
                tg_processed = tg_processor.process(generated_tg)
                tg_length = len(tg_processed)
                
                # Дополнительная проверка на шаблоны и структуру
                if '[содержимое]' in tg_processed.lower():
                    logger.warning(f"⚠️ Telegram содержит шаблон [содержимое]")
                    continue
                
                # Проверяем наличие обязательных элементов
                if '🎯 Важно:' not in tg_processed or 'ВОПРОС ДЛЯ АУДИТОРИИ:' not in tg_processed:
                    logger.warning(f"⚠️ Telegram не содержит обязательные элементы")
                    continue
                
                if tg_min <= tg_length <= tg_max:
                    tg_text = tg_processed
                    logger.info(f"✅ Telegram успех! {tg_length} символов (нужно {tg_min}-{tg_max})")
                    break
                else:
                    logger.warning(f"⚠️ Telegram не прошел валидацию: {tg_length} символов, нужно {tg_min}-{tg_max}")
            
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
        
        # Генерируем Zen пост
        logger.info("🤖 Генерация Zen поста...")
        for attempt in range(max_attempts):
            logger.info(f"🤖 Zen попытка {attempt+1}/{max_attempts}")
            
            zen_prompt = self.create_zen_prompt(theme, slot_style, text_format, image_description)
            generated_zen = self.generate_with_gemini(zen_prompt, 'zen')
            
            if generated_zen:
                zen_processor = TextPostProcessor(theme, slot_style, 'zen')
                zen_processed = zen_processor.process(generated_zen)
                zen_length = len(zen_processed)
                
                # Дополнительная проверка на шаблоны и структуру
                template_patterns = ['[ключевые выводы]', '[практические следствия]', '[обобщающая мысль]', '[вопрос для дискуссии]']
                if any(pattern in zen_processed.lower() for pattern in template_patterns):
                    logger.warning(f"⚠️ Zen содержит шаблон")
                    continue
                
                # Проверяем наличие обязательных элементов
                if 'ВОПРОС ДЛЯ ОБСУЖДЕНИЯ:' not in zen_processed:
                    logger.warning(f"⚠️ Zen не содержит обязательный вопрос")
                    continue
                
                if zen_min <= zen_length <= zen_max:
                    zen_text = zen_processed
                    logger.info(f"✅ Zen успех! {zen_length} символов (нужно {zen_min}-{zen_max})")
                    break
                else:
                    logger.warning(f"⚠️ Zen не прошел валидацию: {zen_length} символов, нужно {zen_min}-{zen_max}")
            
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
        
        if not tg_text:
            logger.error("❌ Не удалось сгенерировать Telegram пост")
        if not zen_text:
            logger.error("❌ Не удалось сгенерировать Zen пост")
        
        return tg_text, zen_text
    
    def get_post_image_and_description(self, theme: str) -> Tuple[Optional[str], str]:
        """Находит подходящую картинку"""
        try:
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture"],
                "HR и управление персоналом": ["office", "business", "teamwork"],
                "PR и коммуникации": ["communication", "marketing", "media"]
            }
            
            queries = theme_queries.get(theme, ["business", "professional"])
            query = random.choice(queries)
            
            logger.info(f"🔍 Ищем фото по запросу: '{query}'")
            
            # Пробуем Pexels
            if PEXELS_API_KEY:
                url = "https://api.pexels.com/v1/search"
                params = {"query": query, "per_page": 10, "orientation": "landscape"}
                headers = {"Authorization": PEXELS_API_KEY}
                
                response = session.get(url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    photos = data.get("photos", [])
                    if photos:
                        # Фильтруем неиспользованные
                        used = self.image_history.get("used_images", [])
                        available = [p for p in photos if p.get("src", {}).get("large") not in used]
                        photo = random.choice(available if available else photos)
                        
                        image_url = photo.get("src", {}).get("large", "")
                        if image_url:
                            # Сохраняем в историю
                            if "used_images" not in self.image_history:
                                self.image_history["used_images"] = []
                            self.image_history["used_images"].append(image_url)
                            self._save_json("image_history.json", self.image_history)
                            
                            return image_url, f"Фото на тему '{query}'"
            
            # Fallback на Unsplash
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return response.url, f"Фото на тему '{query}'"
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
        
        return None, "Нет картинки"
    
    def create_inline_keyboard(self) -> InlineKeyboardMarkup:
        """Создает inline клавиатуру"""
        keyboard = InlineKeyboardMarkup(row_width=3)
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
    
    # ========== CALLBACK ОБРАБОТЧИКИ ==========
    def _handle_callback(self, call: CallbackQuery):
        """Основной обработчик callback"""
        try:
            if not self._is_admin_message(call.message):
                return
            
            message_id = call.message.message_id
            callback_data = call.data
            
            if message_id not in self.pending_posts:
                return
            
            post_data = self.pending_posts[message_id]
            
            # Обработка тем
            if callback_data.startswith("theme_"):
                self._handle_theme_selection(message_id, post_data, call, callback_data)
                return
            
            # Вызов обработчика из словаря
            if callback_data in self.callback_handlers:
                self.callback_handlers[callback_data](message_id, post_data, call)
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки callback: {e}")
    
    def _handle_approval(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка одобрения поста"""
        try:
            self.bot.answer_callback_query(call.id, "✅ Пост одобрен!")
            
            # Обновляем статус в сообщении
            try:
                status_text = f"\n\n<b>✅ Опубликовано в {post_data.get('channel', 'канал')}</b>"
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=f"{post_data['text'][:1020]}{status_text}",
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
            
            # Публикуем в канал
            success = self._publish_to_channel(
                post_data.get('text', ''),
                post_data.get('image_url', ''),
                post_data.get('channel', '')
            )
            
            if success:
                post_data['status'] = PostStatus.PUBLISHED
                post_data['published_at'] = datetime.now().isoformat()
                
                with self.publish_lock:
                    self.published_posts_count += 1
                    
                    if self.published_posts_count >= 2:
                        with self.completion_lock:
                            self.workflow_complete = True
            
            # Удаляем из ожидания
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения: {e}")
    
    def _handle_rejection(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка отклонения поста"""
        try:
            self.bot.answer_callback_query(call.id, "❌ Пост отклонен!")
            
            # Обновляем статус
            try:
                status_text = f"\n\n<b>❌ Отклонено</b>"
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=f"{post_data['text'][:1020]}{status_text}",
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
            
            # Сохраняем в историю отклоненных
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            slot_time = post_data.get('slot_time', '')
            
            if slot_time:
                if "rejected_slots" not in self.post_history:
                    self.post_history["rejected_slots"] = {}
                
                if today not in self.post_history["rejected_slots"]:
                    self.post_history["rejected_slots"][today] = []
                
                self.post_history["rejected_slots"][today].append({
                    "time": slot_time,
                    "type": post_data.get('type'),
                    "theme": post_data.get('theme'),
                    "reason": "Отклонено через кнопку"
                })
                self._save_json("post_history.json", self.post_history)
            
            # Удаляем из ожидания
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                
            # Проверяем, все ли посты обработаны
            remaining = len([p for p in self.pending_posts.values() 
                           if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
            if remaining == 0:
                with self.completion_lock:
                    self.workflow_complete = True
                    
        except Exception as e:
            logger.error(f"💥 Ошибка обработки отклонения: {e}")
    
    def _handle_edit_request(self, message_id: int, post_data: Dict, call: CallbackQuery, edit_type: str):
        """Обработка запроса на редактирование"""
        try:
            self.bot.answer_callback_query(call.id, f"✏️ {edit_type}...")
            
            edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
            post_data['edit_timeout'] = edit_timeout
            
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>✏️ Запрос на редактирование '{edit_type}' принят.</b>\n"
                     f"<b>⏰ Время на изменения до:</b> {edit_timeout.strftime('%H:%M')} МСК",
                parse_mode='HTML'
            )
            
            # Здесь должна быть логика перегенерации
            # Для краткости оставляем заглушку
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="<b>⚠️ Функция редактирования в разработке</b>",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на редактирование: {e}")
    
    def _handle_new_post_request(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка запроса на новый пост"""
        try:
            self.bot.answer_callback_query(call.id, "🎯 Выберите тему...")
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            for theme in self.THEMES:
                keyboard.add(InlineKeyboardButton(
                    f"🎯 {theme}",
                    callback_data=f"theme_{theme}"
                ))
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            try:
                caption = (f"<b>🎯 ВЫБЕРИТЕ ТЕМУ ДЛЯ НОВОГО ПОСТА</b>\n\n"
                          f"Текущая тема: {post_data.get('theme', 'Не указана')}")
                
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
            except Exception as e:
                logger.warning(f"⚠️ Не удалось редактировать сообщение: {e}")
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки запроса на новый пост: {e}")
    
    def _handle_theme_selection(self, message_id: int, post_data: Dict, call: CallbackQuery, callback_data: str):
        """Обработка выбора темы"""
        try:
            selected_theme = callback_data.replace("theme_", "")
            self.bot.answer_callback_query(call.id, f"✅ Выбрана тема: {selected_theme}")
            
            self.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"<b>🔄 ГЕНЕРИРУЮ НОВЫЙ ПОСТ</b>\n\n"
                     f"<b>🎯 Тема:</b> {selected_theme}\n"
                     f"<b>⏰ Время публикации:</b> {post_data.get('slot_time', '')}",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"💥 Ошибка обработки выбора темы: {e}")
    
    def _handle_back_to_main(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка возврата к основным кнопкам"""
        try:
            self.bot.answer_callback_query(call.id, "⬅️ Возврат")
            self._restore_main_buttons(message_id, post_data)
        except Exception as e:
            logger.error(f"💥 Ошибка возврата: {e}")
    
    def _restore_main_buttons(self, message_id: int, post_data: Dict):
        """Восстанавливает основные кнопки"""
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
                
        except Exception as e:
            logger.warning(f"⚠️ Не удалось восстановить кнопки: {e}")
    
    # ========== ОСНОВНЫЕ МЕТОДЫ ==========
    def _is_admin_message(self, message: Message) -> bool:
        """Проверяет, что сообщение от администратора"""
        return str(message.chat.id) == ADMIN_CHAT_ID
    
    def _get_slot_for_time(self, target_time: datetime, auto: bool = False) -> Tuple[Optional[str], Optional[Dict]]:
        """Определяет слот для заданного времени"""
        try:
            hour, minute = target_time.hour, target_time.minute
            
            # Ночная зона: 20:00-03:59 → Вечерний слот
            if hour >= 20 or hour < 4:
                return "20:00", self.TIME_STYLES.get("20:00")
            
            # Утренняя зона: 04:00-10:59 → Утренний слот
            if hour >= 4 and hour < 11:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            current_minutes = hour * 60 + minute
            
            # Для автопостинга ищем слот ±10 минут
            if auto:
                for slot_time, slot_style in self.TIME_STYLES.items():
                    slot_hour, slot_minute = map(int, slot_time.split(':'))
                    slot_minutes = slot_hour * 60 + slot_minute
                    
                    if abs(current_minutes - slot_minutes) <= 10:
                        return slot_time, slot_style
                return None, None
            
            # Для ручного запуска - ближайший будущий слот
            future_slots = []
            for slot_time in self.TIME_STYLES.keys():
                slot_hour, slot_minute = map(int, slot_time.split(':'))
                slot_minutes = slot_hour * 60 + slot_minute
                
                if slot_minutes > current_minutes:
                    future_slots.append((slot_time, slot_minutes))
            
            if future_slots:
                future_slots.sort(key=lambda x: x[1])
                slot_time = future_slots[0][0]
                return slot_time, self.TIME_STYLES.get(slot_time)
            
            # Если все слоты прошли - утренний на завтра
            return "11:00", self.TIME_STYLES.get("11:00")
            
        except Exception as e:
            logger.error(f"❌ Ошибка определения слота: {e}")
            return None, None
    
    def _get_smart_theme(self) -> str:
        """Выбирает тему с умной ротацией"""
        try:
            theme_rotation = self.post_history.get("theme_rotation", [])
            last_themes = theme_rotation[-3:] if len(theme_rotation) >= 3 else theme_rotation
            
            # Ищем тему, которая не использовалась слишком часто
            for theme in self.THEMES:
                if theme not in last_themes:
                    self.current_theme = theme
                    return theme
            
            # Если все использовались - берем случайную
            self.current_theme = random.choice(self.THEMES)
            return self.current_theme
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора темы: {e}")
            self.current_theme = random.choice(self.THEMES)
            return self.current_theme
    
    def _publish_to_channel(self, text: str, image_url: str, channel: str) -> bool:
        """Публикует пост в канал"""
        try:
            logger.info(f"📤 Публикую в {channel}")
            
            if image_url and image_url.strip() and image_url.startswith('http'):
                try:
                    caption = text[:1024] if len(text) > 1024 else text
                    self.bot.send_photo(
                        chat_id=channel,
                        photo=image_url,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    if len(text) > 1024:
                        self.bot.send_message(
                            chat_id=channel,
                            text=text[1024:],
                            parse_mode='HTML'
                        )
                except Exception as photo_error:
                    logger.warning(f"⚠️ Не удалось с картинкой: {photo_error}")
                    self.bot.send_message(
                        chat_id=channel,
                        text=text,
                        parse_mode='HTML'
                    )
            else:
                self.bot.send_message(
                    chat_id=channel,
                    text=text,
                    parse_mode='HTML'
                )
            
            logger.info(f"✅ Опубликовано в {channel}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в {channel}: {e}")
            return False
    
    def send_to_admin_for_moderation(self, slot_time: str, tg_text: str, zen_text: str, 
                                    image_url: str, theme: str) -> int:
        """Отправляет посты администратору на модерацию"""
        logger.info("📤 Отправляю посты на модерацию...")
        
        success_count = 0
        edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
        
        # Функция отправки одного поста
        def send_post(post_type: str, text: str, channel: str) -> Optional[int]:
            nonlocal success_count
            try:
                keyboard = self.create_inline_keyboard()
                caption_length = 1024
                
                if image_url and image_url.strip() and image_url.startswith('http'):
                    try:
                        caption = text[:caption_length]
                        sent = self.bot.send_photo(
                            chat_id=ADMIN_CHAT_ID,
                            photo=image_url,
                            caption=caption,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        message_id = sent.message_id
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось с фото: {e}")
                        sent = self.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=text,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        message_id = sent.message_id
                else:
                    sent = self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=text,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                    message_id = sent.message_id
                
                # Сохраняем в ожидании
                self.pending_posts[message_id] = {
                    'type': post_type,
                    'text': text,
                    'image_url': image_url or '',
                    'channel': channel,
                    'status': PostStatus.PENDING,
                    'theme': theme,
                    'slot_style': self.current_style,
                    'slot_time': slot_time,
                    'edit_timeout': edit_timeout
                }
                
                success_count += 1
                return message_id
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки {post_type} поста: {e}")
                return None
        
        # Отправляем оба поста
        tg_message_id = send_post('telegram', tg_text, MAIN_CHANNEL)
        time.sleep(1)
        zen_message_id = send_post('zen', zen_text, ZEN_CHANNEL)
        
        # Отправляем инструкции
        if tg_message_id or zen_message_id:
            try:
                tg_token_min, tg_token_max = self.current_style['tg_tokens']
                zen_token_min, zen_token_max = self.current_style['zen_tokens']
                total_token_min, total_token_max = self.current_style['total_tokens']
                
                instruction = (f"<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
                              f"<b>📱 Telegram пост</b>\n"
                              f"   Канал: {MAIN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(tg_text)} (нужно {self.current_style['tg_chars'][0]}-{self.current_style['tg_chars'][1]})\n"
                              f"   Токенов: {tg_token_min}-{tg_token_max}\n\n"
                              f"<b>📝 Дзен пост</b>\n"
                              f"   Канал: {ZEN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(zen_text)} (нужно {self.current_style['zen_chars'][0]}-{self.current_style['zen_chars'][1]})\n"
                              f"   Токенов: {zen_token_min}-{zen_token_max}\n\n"
                              f"<b>📊 Итог по токенам:</b> {total_token_min}-{total_token_max} токенов на 2 поста\n\n"
                              f"<b>⏰ Время на решение:</b> до {edit_timeout.strftime('%H:%M')} МСК")
                
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=instruction,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки инструкции: {e}")
        
        return success_count
    
    def create_and_send_posts(self, slot_time: str, slot_style: Dict) -> bool:
        """Создает и отправляет посты"""
        try:
            logger.info(f"🎬 Создание постов для {slot_time}")
            self.current_style = slot_style
            
            # Выбираем тему и формат
            theme = self._get_smart_theme()
            text_format = "разбор ситуации"
            
            # Получаем картинку
            image_url, image_description = self.get_post_image_and_description(theme)
            
            # Генерируем посты
            tg_text, zen_text = self.generate_with_retry(theme, slot_style, text_format, image_description)
            if not tg_text or not zen_text:
                return False
            
            # Отправляем на модерацию
            success_count = self.send_to_admin_for_moderation(
                slot_time, tg_text, zen_text, image_url, theme
            )
            
            if success_count > 0:
                # Сохраняем в историю
                today = self.get_moscow_time().strftime("%Y-%m-%d")
                if "sent_slots" not in self.post_history:
                    self.post_history["sent_slots"] = {}
                if today not in self.post_history["sent_slots"]:
                    self.post_history["sent_slots"][today] = []
                
                self.post_history["sent_slots"][today].append(slot_time)
                
                # Сохраняем тему
                if "theme_rotation" not in self.post_history:
                    self.post_history["theme_rotation"] = []
                self.post_history["theme_rotation"].append(theme)
                
                self._save_json("post_history.json", self.post_history)
                
                logger.info(f"✅ {success_count}/2 поста отправлены на модерацию")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"💥 Ошибка создания постов: {e}")
            return False
    
    def run_single_cycle(self):
        """Запускает однократный цикл работы бота"""
        try:
            logger.info("🚀 Запуск однократного цикла")
            
            # Определяем слот ДО запуска polling
            now = self.get_moscow_time()
            if self.target_slot:
                slot_style = self.TIME_STYLES.get(self.target_slot)
                if not slot_style:
                    logger.error(f"❌ Неверный слот: {self.target_slot}")
                    return
                slot_time = self.target_slot
            else:
                slot_time, slot_style = self._get_slot_for_time(now, self.auto)
                if not slot_time or not slot_style:
                    logger.info("⏰ Не время для публикации")
                    return
            
            # Создаем посты ДО запуска polling
            success = self.create_and_send_posts(slot_time, slot_style)
            
            if not success:
                logger.error("❌ Не удалось создать посты")
                return
            
            # Теперь настраиваем обработчики и запускаем polling
            self.bot.delete_webhook(drop_pending_updates=True)
            
            @self.bot.callback_query_handler(func=lambda call: True)
            def handle_callback(call):
                self._handle_callback(call)
            
            # Запускаем polling в отдельном потоке
            def polling_task():
                try:
                    while not self.stop_polling:
                        try:
                            self.bot.polling(none_stop=True, interval=1, timeout=30)
                        except Exception as e:
                            logger.error(f"❌ Ошибка polling: {e}")
                            time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Критическая ошибка в polling: {e}")
            
            self.polling_thread = threading.Thread(target=polling_task, daemon=True)
            self.polling_thread.start()
            
            # Ждем завершения workflow (10 минут)
            logger.info("⏳ Ожидание обработки (10 минут)...")
            start_time = time.time()
            timeout = 600
            
            while time.time() - start_time < timeout:
                with self.completion_lock:
                    if self.workflow_complete:
                        logger.info("✅ Workflow завершен")
                        break
                
                # Проверяем, есть ли еще посты на модерации
                remaining = len([p for p in self.pending_posts.values() 
                               if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
                if remaining == 0:
                    logger.info("✅ Все посты обработаны")
                    break
                
                time.sleep(1)
            
            # Останавливаем polling
            logger.info("🛑 Останавливаю polling...")
            self.stop_polling = True
            
            if self.polling_thread and self.polling_thread.is_alive():
                self.polling_thread.join(timeout=5)
            
            logger.info("✅ Работа завершена")
            
        except Exception as e:
            logger.error(f"💥 Ошибка в цикле работы: {e}")


def main():
    """Основная функция"""
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--slot', help='Конкретный слот (формат HH:MM)')
        parser.add_argument('--auto', action='store_true', help='Автоматический запуск')
        
        args = parser.parse_args()
        
        bot = TelegramBot(target_slot=args.slot, auto=args.auto)
        bot.run_single_cycle()
        
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по команде пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
