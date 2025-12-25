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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL = os.environ.get("MAIN_CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL = os.environ.get("ZEN_CHANNEL_ID", "@tehdzenm")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
GITHUB_TOKEN = os.environ.get("MANAGER_GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME", "")
REPO_OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "")

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

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json'
})
session.timeout = 30


# ========== КОНСТАНТЫ И КЛАССЫ ==========
class PostStatus:
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EDIT = "needs_edit"
    PUBLISHED = "published"
    REJECTED = "rejected"


class GitHubAPIManager:
    BASE_URL = "https://api.github.com"
    
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.repo_owner = REPO_OWNER
        self.repo_name = REPO_NAME
    
    def _get_headers(self) -> Dict:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers
    
    def get_file_content(self, file_path: str) -> Union[Dict, str]:
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
        try:
            if not self.github_token or not self.repo_owner or not self.repo_name:
                return {"error": "Недостаточно данных для доступа к репозиторию"}
            
            url = f"{self.BASE_URL}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            response = session.get(url, headers=self._get_headers())
            
            if response.status_code != 200:
                return {"error": "Файл не найден"}
            
            current_file = response.json()
            sha = current_file["sha"]
            
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
    THEMES = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
    
    TIME_STYLES = {
        "11:00": {
            "name": "Утренний пост",
            "type": "morning",
            "emoji": "🌅",
            "style": "энергостарт: короткая польза, лёгкая динамика, мотивирующий фокус",
            "tg_chars": (400, 600),
            "zen_chars": (600, 700),
            "tg_tokens": (100, 135),
            "zen_tokens": (135, 155),
            "total_tokens": (235, 290)
        },
        "15:00": {
            "name": "Дневной пост",
            "type": "day",
            "emoji": "🌞",
            "style": "рациональность и аналитика: наблюдение, разбор явления, микроисследование",
            "tg_chars": (700, 900),
            "zen_chars": (700, 900),
            "tg_tokens": (155, 200),
            "zen_tokens": (155, 200),
            "total_tokens": (310, 400)
        },
        "20:00": {
            "name": "Вечерний пост",
            "type": "evening",
            "emoji": "🌙",
            "style": "глубина и история: личный взгляд, миниистория, аналогия",
            "tg_chars": (600, 900),
            "zen_chars": (700, 800),
            "tg_tokens": (135, 200),
            "zen_tokens": (155, 180),
            "total_tokens": (290, 380)
        }
    }
    
    def __init__(self, target_slot: str = None, auto: bool = False):
        self.target_slot = target_slot
        self.auto = auto
        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
        self.github_manager = GitHubAPIManager()
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
        self.published_posts_count = 0
        self.workflow_complete = False
        self.stop_polling = False
        self.publish_lock = threading.Lock()
        self.completion_lock = threading.Lock()
        self.polling_lock = threading.Lock()
        self.polling_thread = None
        
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
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки {filename}: {e}")
        return default_data
    
    def _save_json(self, filename: str, data: Dict) -> bool:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения {filename}: {e}")
            return False
    
    def get_moscow_time(self) -> datetime:
        return datetime.utcnow() + timedelta(hours=3)
    
    def _clean_metadata(self, text: str, post_type: str) -> str:
        """Удаляет маркеры и метаданные из текста"""
        if not text:
            return text
        
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                lines.append('')
                continue
            
            # Удаляем нумерацию типа [1], [2], [3] и т.д.
            line = re.sub(r'^\[\d+\]\s*', '', line)
            
            # Удаляем метки типа "ЗАГОЛОВОК:", "АБЗАЦ 1:", "ЯКОРЬ:" и т.д.
            markers_to_remove = [
                'заголовок:', 'абзац 1:', 'абзац 2:', 'ключевая мысль:', 'вопрос:', 'хештеги:',
                'якорь:', 'в итоге:', 'anchor:', 'header:', 'paragraph:', 'key thought:',
                'question:', 'hashtags:', 'абзац:', 'блок:'
            ]
            
            for marker in markers_to_remove:
                if line.lower().startswith(marker):
                    # Удаляем метку, оставляем только текст после двоеточия
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        line = parts[1].strip()
                    else:
                        line = line[len(marker):].strip()
                    break
            
            # Telegram: сохраняем эмодзи в начале
            if post_type == 'telegram' and self.current_style:
                emoji = self.current_style.get('emoji', '')
                if emoji and line.startswith(emoji):
                    # Оставляем эмодзи + заголовок
                    pass
            
            lines.append(line)
        
        # Объединяем обратно, убирая лишние пустые строки
        cleaned_text = '\n'.join(lines)
        
        # Убираем повторяющиеся пустые строки (больше 2 подряд)
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        
        return cleaned_text.strip()
    
    # ========== ОБНОВЛЕННЫЕ ПРОМПТЫ С НОВОЙ СТРУКТУРОЙ ==========
    def create_telegram_prompt(self, theme: str, slot_style: Dict, text_format: str, image_description: str) -> str:
        """Создает промпт для Telegram поста - НОВАЯ СТРУКТУРА"""
        prompt = f"""
ТОЧНЫЙ ФОРМАТ — НЕ УДАЛЯЙ НИКАКИЕ БЛОКИ:

[1] {slot_style['emoji']} ЗАГОЛОВОК: Создай провокационный вопрос или утверждение по теме "{theme}". Начни сразу с эмодзи {slot_style['emoji']}.

[2] АБЗАЦ 1: Свободный вход в мысль и небольшое развитие. 2-3 предложения. 

[3] 🎯 КЛЮЧЕВАЯ МЫСЛЬ: одна явная и конкретная мысль по теме. Начни с 🎯. 1 прелдожение. 

[4] ВОПРОС: Задай вопрос читателю. Отдельная строка. Заканчивается знаком ?.

[5] ХЕШТЕГИ: Добавь 3-5 хештегов по теме. Только #слово #слово #слово.

ТЕМА: {theme}

ЖЕСТКИЕ ПРАВИЛА:
1. Начинай СРАЗУ с {slot_style['emoji']} и заголовка
2. Обязательно используй 🎯 для ключевой мысли
3. Между всеми элементами [1]-[5] оставляй пустую строку
4. Вопрос заканчивается знаком ?
5. Хештеги в последней строке
6. НЕ ПРОПУСКАЙ ни один блок
7. Следуй строго порядку [1]-[5]
"""
        return prompt.strip()
    
    def create_zen_prompt(self, theme: str, slot_style: Dict, text_format: str, image_description: str) -> str:
        """Создает промпт для Zen поста - НОВАЯ СТРУКТУРА"""
        prompt = f"""
ТОЧНЫЙ ФОРМАТ — НЕ УДАЛЯЙ НИКАКИЕ БЛОКИ:

[1] ЗАГОЛОВОК: Создай провокационный вопрос или утверждение по теме "{theme}". Без эмодзи.

[2] АБЗАЦ 1: Разверни тему и небольшое развитие мысли. 2-3 предложения.

[3] ЯКОРЬ: Фиксируй значение или вывод. Начни ТОЛЬКО со слов "В итоге:". 1 предложение. 

[4] ВОПРОС: Задай вопрос для обсуждения. Отдельная строка. Заканчивается знаком ?.

[5] ХЕШТЕГИ: Добавь 3-5 хештегов по теме. Только #слово #слово #слово.

ТЕМА: {theme}

ЖЕСТКИЕ ПРАВИЛА:
1. НИКАКИХ эмодзи, смайликов, символов
2. Между всеми элементами [1]-[5] оставляй пустую строку
3. Якорь начинается ТОЛЬКО со слов "В итоге:"
4. Вопрос заканчивается знаком ?
5. Хештеги в последней строке
6. НЕ ПРОПУСКАЙ ни один блок
7. Следуй строго порядку [1]-[5]
"""
        return prompt.strip()
    
    def generate_with_gemini(self, prompt: str, post_type: str) -> Optional[str]:
        """Генерация через Gemini API"""
        try:
            if post_type == 'telegram':
                token_range = self.current_style.get('tg_tokens', (80, 120)) if self.current_style else (80, 120)
                max_tokens = token_range[1]
            else:
                token_range = self.current_style.get('zen_tokens', (120, 140)) if self.current_style else (120, 140)
                max_tokens = token_range[1]
            
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
                    logger.info(f"✅ {post_type.upper()} текст получен, длина: {len(generated_text)} символов")
                    
                    # Сразу очищаем метаданные
                    cleaned_text = self._clean_metadata(generated_text, post_type)
                    
                    return cleaned_text.strip()
            
            logger.error(f"❌ Ошибка API: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"💥 Ошибка генерации {post_type}: {e}")
            return None
    
    def validate_post_structure(self, text: str, post_type: str, slot_style: Dict = None) -> Tuple[bool, str]:
        """Проверяет структуру поста и принудительно исправляет"""
        if not text:
            return False, "Пустой текст"
        
        # Текст уже очищен в generate_with_gemini, но на всякий случай еще раз
        text = self._clean_metadata(text, post_type)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Telegram проверка
        if post_type == 'telegram':
            # 1. Проверяем наличие эмодзи в начале
            if slot_style and 'emoji' in slot_style:
                emoji = slot_style['emoji']
                if not text.strip().startswith(emoji):
                    # Добавляем эмодзи к первой непустой строке
                    if lines:
                        lines[0] = f"{emoji} {lines[0]}"
                    else:
                        lines.append(emoji)
                    text = '\n'.join(lines)
            
            # 2. Проверяем наличие 🎯
            if '🎯' not in text:
                # Добавляем 🎯 после первого абзаца
                emoji_found = False
                for i, line in enumerate(lines):
                    if slot_style and 'emoji' in slot_style and line.startswith(slot_style['emoji']):
                        emoji_found = True
                        # Ищем конец первого абзаца (пустую строку или конец)
                        for j in range(i + 1, len(lines)):
                            if lines[j] == '' or j == len(lines) - 1:
                                lines.insert(j + 1, "🎯")
                                break
                        break
                
                if not emoji_found and lines:
                    # Просто вставляем после первой строки
                    lines.insert(1, "🎯")
                
                text = '\n'.join(lines)
            
            # 3. Проверяем наличие вопроса
            if '?' not in text:
                # Ищем хештеги для вставки вопроса перед ними
                hashtag_found = False
                for i, line in enumerate(lines):
                    if line.startswith('#'):
                        lines.insert(i, "Что думаете об этом?")
                        hashtag_found = True
                        break
                
                if not hashtag_found:
                    lines.append("Что думаете об этом?")
                
                text = '\n'.join(lines)
        
        # Zen проверка
        elif post_type == 'zen':
            # 1. Удаляем эмодзи
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF" 
                u"\U0001F680-\U0001F6FF"
                u"\U0001F900-\U0001F9FF"
                "]+", flags=re.UNICODE)
            
            if emoji_pattern.search(text):
                text = emoji_pattern.sub('', text)
                lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # 2. Проверяем наличие якоря "В итоге:" и УДАЛЯЕМ "В итоге:"
            has_anchor = any('в итоге:' in line.lower() for line in lines)
            if has_anchor:
                # Удаляем "В итоге:" из всех строк
                new_lines = []
                for line in lines:
                    if 'в итоге:' in line.lower():
                        # Удаляем "В итоге:" и оставляем только текст после
                        line = line.replace('В итоге:', '').replace('в итоге:', '').strip()
                    new_lines.append(line)
                lines = new_lines
            
            # 3. Проверяем наличие вопроса
            if '?' not in text:
                # Ищем хештеги для вставки вопроса перед ними
                hashtag_found = False
                for i, line in enumerate(lines):
                    if line.startswith('#'):
                        lines.insert(i, "Что думаете об этом?")
                        hashtag_found = True
                        break
                
                if not hashtag_found:
                    lines.append("Что думаете об этом?")
                
                text = '\n'.join(lines)
            
            # 4. Добавляем пустые строки между блоками
            if lines:
                result_lines = []
                for i, line in enumerate(lines):
                    result_lines.append(line)
                    # Добавляем пустую строку после каждого блока, кроме последнего и не перед хештегами
                    if i < len(lines) - 1 and line and not line.startswith('#') and not lines[i+1].startswith('#'):
                        result_lines.append('')
                text = '\n'.join(result_lines)
        
        # 5. Проверяем наличие хештегов
        hashtag_count = len(re.findall(r'#\w+', text))
        if hashtag_count == 0:
            theme_hashtags = {
                "HR и управление персоналом": "#HR #управление #персонал #кадры",
                "PR и коммуникации": "#PR #коммуникации #маркетинг #общение",
                "ремонт и строительство": "#ремонт #строительство #дизайн #интерьер"
            }
            default_hashtags = theme_hashtags.get(self.current_theme, "#тема #обсуждение #вопрос")
            
            # Убираем лишние пустые строки в конце
            text = text.rstrip()
            if not text.endswith('\n'):
                text += '\n'
            text += f"\n{default_hashtags}"
        
        return True, text
    
    def check_post_complete(self, text: str, post_type: str, slot_style: Dict = None) -> bool:
        """Проверяет, что пост содержит все обязательные элементы"""
        if not text:
            return False
        
        if post_type == 'telegram':
            # Telegram: эмодзи, 🎯, вопрос, хештеги
            has_emoji = slot_style and 'emoji' in slot_style and text.strip().startswith(slot_style['emoji'])
            has_target = '🎯' in text
            has_question = '?' in text
            has_hashtags = '#' in text
            
            return has_emoji and has_target and has_question and has_hashtags
        
        elif post_type == 'zen':
            # Zen: вопрос, хештеги, без эмодзи
            has_question = '?' in text
            has_hashtags = '#' in text
            
            # Проверка на эмодзи
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF" 
                u"\U0001F680-\U0001F6FF"
                u"\U0001F900-\U0001F9FF"
                "]+", flags=re.UNICODE)
            has_no_emoji = not bool(emoji_pattern.search(text))
            
            return has_question and has_hashtags and has_no_emoji
        
        return False
    
    def generate_with_retry(self, theme: str, slot_style: Dict, text_format: str, image_description: str,
                           max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Генерация постов с повторными попытками и валидацией"""
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
                # Валидируем структуру
                valid, fixed_tg = self.validate_post_structure(generated_tg, 'telegram', slot_style)
                
                if valid:
                    tg_length = len(fixed_tg)
                    is_complete = self.check_post_complete(fixed_tg, 'telegram', slot_style)
                    
                    if tg_min <= tg_length <= tg_max and is_complete:
                        tg_text = fixed_tg
                        logger.info(f"✅ Telegram успех! {tg_length} символов, все элементы на месте")
                        break
                    else:
                        logger.warning(f"⚠️ Telegram не прошел проверку: "
                                      f"длина={tg_length}({tg_min}-{tg_max}), "
                                      f"полный={is_complete}")
            
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
        
        # Генерируем Zen пост
        logger.info("🤖 Генерация Zen поста...")
        for attempt in range(max_attempts):
            logger.info(f"🤖 Zen попытка {attempt+1}/{max_attempts}")
            
            zen_prompt = self.create_zen_prompt(theme, slot_style, text_format, image_description)
            generated_zen = self.generate_with_gemini(zen_prompt, 'zen')
            
            if generated_zen:
                # Валидируем структуру
                valid, fixed_zen = self.validate_post_structure(generated_zen, 'zen')
                
                if valid:
                    zen_length = len(fixed_zen)
                    is_complete = self.check_post_complete(fixed_zen, 'zen')
                    
                    if zen_min <= zen_length <= zen_max and is_complete:
                        zen_text = fixed_zen
                        logger.info(f"✅ Zen успех! {zen_length} символов, все элементы на месте")
                        break
                    else:
                        logger.warning(f"⚠️ Zen не прошел проверку: "
                                      f"длина={zen_length}({zen_min}-{zen_max}), "
                                      f"полный={is_complete}")
            
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
        
        # Если сгенерировался только один пост из двух - это неудача
        if (tg_text and not zen_text) or (not tg_text and zen_text):
            logger.error("❌ Не удалось сгенерировать оба поста - это неудача!")
            return None, None
        
        if not tg_text and not zen_text:
            logger.error("❌ Не удалось сгенерировать ни одного поста")
        
        return tg_text, zen_text
    
    # ========== ОСТАЛЬНЫЕ МЕТОДЫ ==========
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
            
            if PEXELS_API_KEY:
                url = "https://api.pexels.com/v1/search"
                params = {"query": query, "per_page": 10, "orientation": "landscape"}
                headers = {"Authorization": PEXELS_API_KEY}
                
                response = session.get(url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    photos = data.get("photos", [])
                    if photos:
                        used = self.image_history.get("used_images", [])
                        available = [p for p in photos if p.get("src", {}).get("large") not in used]
                        photo = random.choice(available if available else photos)
                        
                        image_url = photo.get("src", {}).get("large", "")
                        if image_url:
                            if "used_images" not in self.image_history:
                                self.image_history["used_images"] = []
                            self.image_history["used_images"].append(image_url)
                            self._save_json("image_history.json", self.image_history)
                            
                            return image_url, f"Фото на тему '{query}'"
            
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
            
            if callback_data.startswith("theme_"):
                self._handle_theme_selection(message_id, post_data, call, callback_data)
                return
            
            if callback_data in self.callback_handlers:
                self.callback_handlers[callback_data](message_id, post_data, call)
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки callback: {e}")
    
    def _handle_approval(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка одобрения поста"""
        try:
            self.bot.answer_callback_query(call.id, "✅ Пост одобрен!")
            
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
            
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                
        except Exception as e:
            logger.error(f"💥 Ошибка обработки одобрения: {e}")
    
    def _handle_rejection(self, message_id: int, post_data: Dict, call: CallbackQuery):
        """Обработка отклонения поста"""
        try:
            self.bot.answer_callback_query(call.id, "❌ Пост отклонен!")
            
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
            
            if message_id in self.pending_posts:
                del self.pending_posts[message_id]
                
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
        return str(message.chat.id) == ADMIN_CHAT_ID
    
    def _get_slot_for_time(self, target_time: datetime, auto: bool = False) -> Tuple[Optional[str], Optional[Dict]]:
        try:
            hour, minute = target_time.hour, target_time.minute
            
            if hour >= 20 or hour < 4:
                return "20:00", self.TIME_STYLES.get("20:00")
            
            if hour >= 4 and hour < 11:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            current_minutes = hour * 60 + minute
            
            if auto:
                for slot_time, slot_style in self.TIME_STYLES.items():
                    slot_hour, slot_minute = map(int, slot_time.split(':'))
                    slot_minutes = slot_hour * 60 + slot_minute
                    
                    if abs(current_minutes - slot_minutes) <= 10:
                        return slot_time, slot_style
                return None, None
            
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
            
            return "11:00", self.TIME_STYLES.get("11:00")
            
        except Exception as e:
            logger.error(f"❌ Ошибка определения слота: {e}")
            return None, None
    
    def _get_smart_theme(self) -> str:
        try:
            theme_rotation = self.post_history.get("theme_rotation", [])
            
            # Если есть история тем
            if theme_rotation:
                # Получаем последнюю использованную тему
                last_theme = theme_rotation[-1]
                
                # Создаем список доступных тем, исключая последнюю использованную
                available_themes = [theme for theme in self.THEMES if theme != last_theme]
                
                if available_themes:
                    # Выбираем случайную тему из доступных
                    self.current_theme = random.choice(available_themes)
                else:
                    # Если все темы использовались, выбираем любую
                    self.current_theme = random.choice(self.THEMES)
            else:
                # Если истории нет, выбираем случайную тему
                self.current_theme = random.choice(self.THEMES)
            
            return self.current_theme
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора темы: {e}")
            self.current_theme = random.choice(self.THEMES)
            return self.current_theme
    
    def _publish_to_channel(self, text: str, image_url: str, channel: str) -> bool:
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
        logger.info("📤 Отправляю посты на модерацию...")
        
        success_count = 0
        edit_timeout = self.get_moscow_time() + timedelta(minutes=10)
        
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
        
        tg_message_id = None
        zen_message_id = None
        
        if tg_text and tg_text.strip():
            tg_message_id = send_post('telegram', tg_text, MAIN_CHANNEL)
            time.sleep(1)
        
        if zen_text and zen_text.strip():
            zen_message_id = send_post('zen', zen_text, ZEN_CHANNEL)
            time.sleep(1)
        
        if tg_message_id or zen_message_id:
            try:
                tg_token_min, tg_token_max = self.current_style['tg_tokens']
                zen_token_min, zen_token_max = self.current_style['zen_tokens']
                total_token_min, total_token_max = self.current_style['total_tokens']
                
                instruction = (f"<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n")
                
                if tg_text:
                    instruction += (f"<b>📱 Telegram пост</b>\n"
                                  f"   Канал: {MAIN_CHANNEL}\n"
                                  f"   Время: {slot_time} МСК\n"
                                  f"   Символов: {len(tg_text)} (нужно {self.current_style['tg_chars'][0]}-{self.current_style['tg_chars'][1]})\n"
                                  f"   Токенов: {tg_token_min}-{tg_token_max}\n\n")
                
                if zen_text:
                    instruction += (f"<b>📝 Дзен пост</b>\n"
                                  f"   Канал: {ZEN_CHANNEL}\n"
                                  f"   Время: {slot_time} МСК\n"
                                  f"   Символов: {len(zen_text)} (нужно {self.current_style['zen_chars'][0]}-{self.current_style['zen_chars'][1]})\n"
                                  f"   Токенов: {zen_token_min}-{zen_token_max}\n\n")
                
                instruction += (f"<b>📊 Итог по токенам:</b> {total_token_min}-{total_token_max} токенов\n\n"
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
        try:
            logger.info(f"🎬 Создание постов для {slot_time}")
            self.current_style = slot_style
            
            theme = self._get_smart_theme()
            text_format = "разбор ситуации"
            
            image_url, image_description = self.get_post_image_and_description(theme)
            
            tg_text, zen_text = self.generate_with_retry(theme, slot_style, text_format, image_description)
            
            # ЕСЛИ НЕ СГЕНЕРИРОВАЛСЯ ХОТЯ БЫ ОДИН ПОСТ - ВОЗВРАЩАЕМ False
            if not tg_text and not zen_text:
                logger.error("❌ Не удалось создать ни одного поста")
                return False
            
            success_count = self.send_to_admin_for_moderation(
                slot_time, 
                tg_text if tg_text else "", 
                zen_text if zen_text else "", 
                image_url, 
                theme
            )
            
            if success_count > 0:
                today = self.get_moscow_time().strftime("%Y-%m-%d")
                if "sent_slots" not in self.post_history:
                    self.post_history["sent_slots"] = {}
                if today not in self.post_history["sent_slots"]:
                    self.post_history["sent_slots"][today] = []
                
                self.post_history["sent_slots"][today].append(slot_time)
                
                if "theme_rotation" not in self.post_history:
                    self.post_history["theme_rotation"] = []
                self.post_history["theme_rotation"].append(theme)
                
                self._save_json("post_history.json", self.post_history)
                
                logger.info(f"✅ {success_count} поста отправлены на модерацию")
                return True
            else:
                logger.error("❌ Не удалось отправить посты на модерацию")
                return False
            
        except Exception as e:
            logger.error(f"💥 Ошибка создания постов: {e}")
            return False
    
    def run_single_cycle(self):
        try:
            logger.info("🚀 Запуск однократного цикла")
            
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
            
            success = self.create_and_send_posts(slot_time, slot_style)
            
            if not success:
                logger.error("❌ Не удалось создать посты")
                return
            
            self.bot.delete_webhook(drop_pending_updates=True)
            
            @self.bot.callback_query_handler(func=lambda call: True)
            def handle_callback(call):
                self._handle_callback(call)
            
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
            
            logger.info("⏳ Ожидание обработки (10 минут)...")
            start_time = time.time()
            timeout = 600
            
            while time.time() - start_time < timeout:
                with self.completion_lock:
                    if self.workflow_complete:
                        logger.info("✅ Workflow завершен")
                        break
                
                remaining = len([p for p in self.pending_posts.values() 
                               if p.get('status') in [PostStatus.PENDING, PostStatus.NEEDS_EDIT]])
                if remaining == 0:
                    logger.info("✅ Все посты обработаны")
                    break
                
                time.sleep(1)
            
            logger.info("🛑 Останавливаю polling...")
            self.stop_polling = True
            
            if self.polling_thread and self.polling_thread.is_alive():
                self.polling_thread.join(timeout=5)
            
            logger.info("✅ Работа завершена")
            
        except Exception as e:
            logger.error(f"💥 Ошибка в цикле работы: {e}")


def main():
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
