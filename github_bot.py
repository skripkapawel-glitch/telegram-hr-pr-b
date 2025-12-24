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
    """Оптимизированный класс для интеллектуальной пост-обработки текстов"""
    
    # Константы для структурного анализа
    PRACTICE_MARKERS = ['🎯 Важно:', '📋 Шаги:', '🔧 Практика:']
    CONCLUSION_MARKERS = ['Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:']
    
    # Паттерны "воды" для удаления
    WATER_PATTERNS = [
        r'очень\s+', r'крайне\s+', r'невероятно\s+', r'чрезвычайно\s+',
        r'на\s+самом\s+деле\s+', r'как\s+известно\s*,?\s*', r'как\s+правило\s*,?\s*',
    ]
    
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
        """Основной пайплайн обработки текста"""
        if not raw_text or len(raw_text.strip()) < 50:
            return raw_text
            
        logger.info(f"🔧 Начинаю пост-обработку {self.post_type} поста ({len(raw_text)} символов)")
        
        # 1. Структурный анализ
        structure = self._analyze_structure(raw_text)
        
        # 2. Структурная коррекция
        corrected = self._correct_structure(raw_text, structure)
        
        # 3. Интеллектуальное сокращение
        shortened = self._intelligently_shorten(corrected)
        
        # 4. Структурное форматирование
        structured = self._add_structural_formatting(shortened)
        
        # 5. Финальное форматирование
        final = self._apply_formatting(structured)
        
        # 6. Валидация
        validation = self._validate(final)
        if validation['valid']:
            logger.info(f"✅ Пост-обработка завершена: {len(final)} символов")
        else:
            logger.warning(f"⚠️ Пост прошел обработку с предупреждениями: {validation['warnings']}")
        
        return final
    
    def _add_structural_formatting(self, text: str) -> str:
        """Добавляет визуальное структурирование в текст"""
        if not text:
            return text
        
        # Улучшенная логика разделения на абзацы
        paragraphs = []
        current_para = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            else:
                current_para.append(line)
        
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        # Для Telegram: добавляем больше визуального разделения
        if self.post_type == 'telegram':
            # Убедимся, что есть разделение между основными блоками
            formatted_paragraphs = []
            for i, para in enumerate(paragraphs):
                formatted_paragraphs.append(para)
                # Добавляем пустую строку после каждого 2-3 абзаца (но не в конце)
                if (i + 1) % 2 == 0 and i < len(paragraphs) - 1:
                    formatted_paragraphs.append('')
            
            return '\n'.join(formatted_paragraphs)
        
        # Для Дзена: более плотное, но с ключевыми разделениями
        else:
            # Находим ключевые маркеры и добавляем разделения перед ними
            result = text
            for marker in self.CONCLUSION_MARKERS:
                if marker in result:
                    result = result.replace(marker, f'\n\n{marker}')
            
            # Добавляем разделение перед хештегами
            hashtag_match = re.search(r'\n(#[\w\u0400-\u04FF]+)', result)
            if hashtag_match:
                hashtag_pos = result.rfind('\n#')
                if hashtag_pos > 0:
                    result = result[:hashtag_pos] + '\n\n' + result[hashtag_pos+1:]
            
            return result
    
    def _analyze_structure(self, text: str) -> Dict:
        """Анализирует структуру текста"""
        structure = {
            'has_emoji_in_start': bool(re.search(r'[🌅🌞🌙]', text[:50])),
            'has_conclusion': any(marker in text for marker in self.CONCLUSION_MARKERS),
            'has_practice': any(marker in text for marker in self.PRACTICE_MARKERS),
            'sentences': re.split(r'(?<=[.!?])\s+', text),
            'hashtags': None,
            'paragraphs': [],
            'line_breaks_count': text.count('\n\n')
        }
        
        # Находим хештеги
        hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        if hashtag_match:
            structure['hashtags'] = {
                'start': hashtag_match.start(),
                'end': len(text),
                'text': hashtag_match.group()
            }
        
        # Анализируем абзацы
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        structure['paragraphs'] = paragraphs
        structure['paragraph_count'] = len(paragraphs)
        
        return structure
    
    def _correct_structure(self, text: str, structure: Dict) -> str:
        """Добавляет недостающие структурные элементы"""
        result = text
        
        if self.post_type == 'telegram':
            # Гарантируем эмодзи в начале
            if not structure['has_emoji_in_start'] and 'emoji' in self.slot_style:
                result = f"{self.slot_style['emoji']} {result}"
                logger.info("✅ Добавлен эмодзи в начало Telegram поста")
            
            # Гарантируем практический блок с правильным форматированием
            if not structure['has_practice']:
                practical_block = self._generate_practical_block()
                if practical_block:
                    # Вставляем перед хештегами или в конец с двойным переносом
                    if structure['hashtags']:
                        pos = structure['hashtags']['start']
                        result = f"{result[:pos].strip()}\n\n{practical_block}\n\n{result[pos:].strip()}"
                    else:
                        result = f"{result.strip()}\n\n{practical_block}"
                    logger.info("✅ Добавлен практический блок в Telegram пост")
        else:
            # Удаляем все эмодзи из Zen
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF" 
                u"\U0001F680-\U0001F6FF"
                u"\U0001F900-\U0001F9FF"
                "]+", flags=re.UNICODE)
            result = emoji_pattern.sub(r'', result).strip()
            
            # Гарантируем блок завершения с разделением
            if not structure['has_conclusion']:
                conclusion_block = self._generate_conclusion_block()
                if conclusion_block:
                    if structure['hashtags']:
                        pos = structure['hashtags']['start']
                        result = f"{result[:pos].strip()}\n\n{conclusion_block}\n\n{result[pos:].strip()}"
                    else:
                        result = f"{result.strip()}\n\n{conclusion_block}"
                    logger.info("✅ Добавлен блок завершения в Zen пост")
        
        # Гарантируем хештеги с разделением
        if not structure['hashtags']:
            hashtags = self._get_relevant_hashtags()
            result = f"{result.strip()}\n\n{' '.join(hashtags)}"
            logger.info("✅ Добавлены хештеги в пост")
        
        # Гарантируем минимальную структуру
        if structure['paragraph_count'] < 3:
            # Добавляем дополнительные разделения
            sentences = re.split(r'(?<=[.!?])\s+', result)
            if len(sentences) > 4:
                # Группируем предложения в абзацы
                grouped = []
                for i in range(0, len(sentences), 2):
                    if i + 1 < len(sentences):
                        grouped.append(f"{sentences[i]} {sentences[i+1]}")
                    else:
                        grouped.append(sentences[i])
                result = '\n\n'.join(grouped)
        
        return result
    
    def _generate_practical_block(self) -> str:
        """Генерирует практический блок с правильным форматированием"""
        templates = {
            "HR и управление персоналом": [
                "🎯 Важно: регулярная обратная связь повышает вовлеченность сотрудников на 30%.\n\n📋 Шаги:\n1) Проведите оценку компетенций\n2) Создайте индивидуальные планы развития\n3) Отслеживайте прогресс",
                "🔧 Практика: внедрите еженедельные 15-минутные встречи один-на-один для оперативной обратной связи.",
            ],
            "PR и коммуникации": [
                "🎯 Важно: честность в коммуникациях строит долгосрочное доверие.\n\n📋 Шаги:\n1) Определите ключевые сообщения\n2) Выберите подходящие каналы\n3) Измеряйте эффективность",
                "🔧 Практика: создайте систему мониторинга упоминаний бренда в социальных сетях.",
            ],
            "ремонт и строительство": [
                "🎯 Важно: качественная подготовка поверхностей экономит 40% времени на отделке.\n\n📋 Шаги:\n1) Составьте детальную смету\n2) Закупите материалы с запасом 10%\n3) Соблюдайте технологию работ",
                "🔧 Практика: используйте лазерный уровень для точной разметки перед началом работ.",
            ]
        }
        
        templates_list = templates.get(self.theme, [
            "🎯 Важно: начните с малого, но делайте это регулярно.\n\n📋 Шаги:\n1) Проанализируйте текущую ситуацию\n2) Определите приоритеты\n3) Действуйте последовательно",
            "🔧 Практика: установите конкретные измеримые цели на ближайшую неделю.",
        ])
        
        return random.choice(templates_list)
    
    def _generate_conclusion_block(self) -> str:
        """Генерирует блок завершения"""
        markers = self.CONCLUSION_MARKERS
        conclusions = {
            "Почему это важно:": "Понимание этой темы позволяет принимать более взвешенные решения.",
            "Что из этого следует:": "Нужно пересмотреть текущие подходы и внести корректировки.",
            "Мнение экспертов:": "Профессионалы в этой сфере сходятся во мнении, что ключ к успеху — в системном подходе."
        }
        
        marker = random.choice(markers)
        return f"{marker} {conclusions.get(marker, 'Это важно для достижения успеха.')}"
    
    def _get_relevant_hashtags(self, count: int = 3) -> List[str]:
        """Возвращает релевантные хештеги"""
        hashtags_by_theme = {
            "HR и управление персоналом": ["#HR", "#управлениеперсоналом", "#рекрутинг", "#команда"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#брендинг"],
            "ремонт и строительство": ["#ремонт", "#строительство", "#дизайн", "#интерьер"]
        }
        
        hashtags = hashtags_by_theme.get(self.theme, ["#бизнес", "#советы", "#развитие"])
        return random.sample(hashtags, min(count, len(hashtags)))
    
    def _intelligently_shorten(self, text: str) -> str:
        """Сокращает текст до max_chars, не ломая его"""
        if len(text) <= self.max_chars:
            return text
        
        logger.info(f"✂️ Сокращение: {len(text)} → {self.max_chars}")
        
        result = text
        
        # Удаление "воды"
        for pattern in self.WATER_PATTERNS:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Если все еще длиннее - обрезаем по предложениям
        if len(result) > self.max_chars:
            sentences = re.split(r'(?<=[.!?])\s+', result)
            result = ""
            for sentence in sentences:
                if len(result) + len(sentence) + 1 <= self.max_chars:
                    result = f"{result} {sentence}".strip()
                else:
                    break
        
        return self._ensure_coherent_end(result)
    
    def _ensure_coherent_end(self, text: str) -> str:
        """Гарантирует, что текст заканчивается целым предложением"""
        if not text:
            return text
            
        last_end = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_end > len(text) * 0.8:
            text = text[:last_end + 1].strip()
        
        if text and text[-1] not in '.!?':
            text = text + '.'
        
        return text
    
    def _apply_formatting(self, text: str) -> str:
        """Финальное форматирование с улучшенной структурой"""
        if not text:
            return text
        
        # Улучшенное форматирование переносов строк
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                # Сохраняем только одну пустую строку подряд для разделения
                if not lines or lines[-1] != '':
                    lines.append('')
            else:
                lines.append(stripped)
        
        # Оптимизация пустых строк для лучшей читаемости
        result_lines = []
        for i, line in enumerate(lines):
            result_lines.append(line)
            
            # Добавляем пустую строку после заголовка/эмодзи
            if i == 0 and line and any(emoji in line[:10] for emoji in ['🌅', '🌞', '🌙']):
                result_lines.append('')
            
            # Добавляем пустую строку перед практическими блоками
            elif line and any(marker in line for marker in self.PRACTICE_MARKERS):
                if i > 0 and lines[i-1] != '':
                    result_lines.insert(-1, '')
            
            # Добавляем пустую строку перед блоком завершения (для Zen)
            elif self.post_type == 'zen' and line and any(marker in line for marker in self.CONCLUSION_MARKERS):
                if i > 0 and lines[i-1] != '':
                    result_lines.insert(-1, '')
        
        result = '\n'.join(result_lines)
        
        # Гарантируем двойной перенос перед хештегами
        hashtag_match = re.search(r'\n(#[\w\u0400-\u04FF]+)', result)
        if hashtag_match:
            hashtag_pos = result.rfind('\n#')
            if hashtag_pos > 0:
                # Проверяем, есть ли уже переносы перед хештегами
                before_hashtags = result[:hashtag_pos].rstrip()
                if not before_hashtags.endswith('\n\n'):
                    if before_hashtags.endswith('\n'):
                        result = before_hashtags + '\n' + result[hashtag_pos+1:]
                    else:
                        result = before_hashtags + '\n\n' + result[hashtag_pos+1:]
        
        return result.strip()
    
    def _validate(self, text: str) -> Dict:
        """Валидация обработанного текста"""
        warnings = []
        text_length = len(text)
        
        if text_length < self.min_chars:
            warnings.append(f"Текст слишком короткий: {text_length} < {self.min_chars}")
        elif text_length > self.max_chars:
            warnings.append(f"Текст слишком длинный: {text_length} > {self.max_chars}")
        
        # Проверяем структуру
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) < 2:
            warnings.append(f"Слишком мало абзацев: {len(paragraphs)}")
        
        return {
            'valid': len(warnings) == 0,
            'warnings': warnings,
            'length': text_length
        }


class GitHubAPIManager:
    """Оптимизированный класс для управления GitHub API"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.repo_owner = REPO_OWNER
        self.repo_name = REPO_NAME
    
    def _get_headers(self) -> Dict:
        """Возвращает заголовки для запросов"""
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
            "max_output_tokens": 1100
        },
        "15:00": {
            "name": "Дневной пост",
            "type": "day",
            "emoji": "🌞",
            "style": "рациональность и аналитика: наблюдение, разбор явления, микро1исследование",
            "tg_chars": (700, 900),
            "zen_chars": (700, 900),
            "max_output_tokens": 1350
        },
        "20:00": {
            "name": "Вечерний пост",
            "type": "evening",
            "emoji": "🌙",
            "style": "глубина и история: личный взгляд, мини1история, аналогия",
            "tg_chars": (600, 900),
            "zen_chars": (700, 800),
            "max_output_tokens": 1250
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
    def generate_with_gemini(self, prompt: str) -> Optional[str]:
        """Генерация через Gemini API"""
        try:
            max_tokens = self.current_style.get('max_output_tokens', 1250) if self.current_style else 1250
            
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
                    logger.info(f"✅ Текст получен, длина: {len(generated_text)} символов")
                    return generated_text
            
            logger.error(f"❌ Ошибка API: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"💥 Ошибка генерации: {e}")
            return None
    
    def create_detailed_prompt(self, theme: str, slot_style: Dict, text_format: str, image_description: str) -> str:
        """Создает промпт для Gemini с полными инструкциями об авторе"""
        tg_min, tg_max = slot_style['tg_chars']
        zen_min, zen_max = slot_style['zen_chars']
        
        # Правила временных слотов
        time_rules = {
            'morning': "СТРОГОЕ ПРАВИЛО: Пост должен начинаться с утреннего приветствия: 'Доброе утро', 'Начало дня', 'Старт утра'. Запрещены любые вечерние или дневные приветствия.",
            'day': "СТРОГОЕ ПРАВИЛО: Запрещены утренние ('Доброе утро') и вечерние ('Добрый вечер') приветствия. Только нейтральный деловой или информационный тон без привязки ко времени суток.",
            'evening': "СТРОГОЕ ПРАВИЛО: Запрещены утренние приветствия ('Доброе утро'). Можно использовать: 'Добрый вечер', 'В завершение дня', 'Подводя итоги'. Только спокойный рефлексивный тон."
        }.get(slot_style['type'], "")
        
        # Полный промпт с информацией об авторе
        prompt = f"""
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

ВАЖНЕЙШЕЕ ПРАВИЛО ДЛИНЫ:
Telegram пост ДОЛЖЕН быть строго {tg_min}-{tg_max} символов.
Дзен пост ДОЛЖЕН быть строго {zen_min}-{zen_max} символов.
Если длина выходит за эти пределы - это КРИТИЧЕСКАЯ ОШИБКА.

🎯 ТЕМА: {theme}
🕒 ВРЕМЕННОЙ СЛОТ: {slot_style['name']} ({slot_style['emoji']})
📝 ФОРМАТ ПОДАЧИ: {text_format}

ПРАВИЛА ВРЕМЕНИ:
{time_rules}

ТРЕБОВАНИЯ К TELEGRAM ПОСТУ:
• Начинай с эмодзи {slot_style['emoji']} и цепляющего заголовка
• Основная часть: 2-3 абзаца с анализом и примерами
• Практический блок с конкретными действиями (используй: 🎯 Важно:, 📋 Шаги:, 🔧 Практика:)
• Вопрос для вовлечения аудитории
• 3-5 релевантных хештегов в конце
• Объём: {tg_min}-{tg_max} символов (ОБЯЗАТЕЛЬНО!)
• ВИЗУАЛЬНАЯ СТРУКТУРА: Используй пустые строки для разделения логических блоков. Пост должен быть легко читаемым!

ТРЕБОВАНИЯ К ZEN ПОСТУ:
• Начало: провокационный вопрос или утверждение ("крючок-убийца")
• Основная часть: глубина анализа, экспертные мнения
• Завершение: естественный вывод (можно использовать: 'Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:')
• Вопрос для обсуждения
• 3-5 релевантных хештегов в конце
• Объём: {zen_min}-{zen_max} символов (ОБЯЗАТЕЛЬНО!)
• ВИЗУАЛЬНАЯ СТРУКТУРА: Разделяй текст на логические абзацы. Ключевые блоки должны быть отделены пустыми строками.

СТРУКТУРНЫЕ ПРАВИЛА ДЛЯ ОБОИХ ФОРМАТОВ:
1. НИКОГДА не пиши монолитный текст без абзацев
2. Разделяй введение, основную часть и заключение пустыми строками
3. Практические советы и списки выделяй отдельными абзацами
4. Хештеги всегда отделяй двойным переносом строки
5. Создавай визуальную иерархию с помощью пустых строк

🖼️ КАРТИНКА: {image_description}

🚫 ЗАПРЕЩЕНО В ТЕКСТЕ:
• Упоминать удаленную работу, релокацию
• Использовать формулировки от первого лица о личном опыте
• Шаблонные фразы, которые звучат как ИИ
• Писать "вот текст для Telegram/Дзен"
• Указывать "тема: {theme}" в тексте
• Писать монолитные тексты без абзацев

✅ ОБЯЗАТЕЛЬНО В ТЕКСТЕ:
• Естественный человеческий язык
• Практическая польза
• Уникальность каждого поста
• Соблюдение лимитов символов
• Визуальная структура с абзацами
• Телеграм пост начинается с эмодзи {slot_style['emoji']}
• Дзен пост начинается без эмодзи

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (полностью по шаблону с эмодзи и структурой)
• Потом Дзен версия (полностью по шаблону «Крючок-убийца» без эмодзи с структурой)
• Разделитель: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя всем правилам выше."""
        
        return prompt
    
    def parse_generated_texts(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Парсит сгенерированные тексты"""
        if not text:
            return None, None
        
        # Ищем разделитель
        if '---' in text:
            parts = text.split('---', 1)
            if len(parts) == 2:
                tg_text = parts[0].strip()
                zen_text = parts[1].strip()
                
                # Базовая валидация
                if len(tg_text) > 100 and len(zen_text) > 100:
                    return tg_text, zen_text
        
        # Fallback: разделяем пополам
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        half = len(lines) // 2
        tg_text = '\n'.join(lines[:half]).strip()
        zen_text = '\n'.join(lines[half:]).strip()
        
        if len(tg_text) > 100 and len(zen_text) > 100:
            return tg_text, zen_text
        
        return None, None
    
    def generate_with_retry(self, prompt: str, tg_min: int, tg_max: int, zen_min: int, zen_max: int, 
                           max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Генерация с повторными попытками"""
        for attempt in range(max_attempts):
            logger.info(f"🤖 Попытка {attempt+1}/{max_attempts}")
            
            generated = self.generate_with_gemini(prompt)
            if not generated:
                continue
            
            tg_text, zen_text = self.parse_generated_texts(generated)
            if not tg_text or not zen_text:
                continue
            
            # Используем TextPostProcessor для обработки
            tg_processor = TextPostProcessor(self.current_theme, self.current_style, 'telegram')
            zen_processor = TextPostProcessor(self.current_theme, self.current_style, 'zen')
            
            tg_processed = tg_processor.process(tg_text)
            zen_processed = zen_processor.process(zen_text)
            
            # Проверяем лимиты после обработки
            if (tg_min <= len(tg_processed) <= tg_max and 
                zen_min <= len(zen_processed) <= zen_max):
                logger.info(f"✅ Успех! TG: {len(tg_processed)}, ZEN: {len(zen_processed)}")
                return tg_processed, zen_processed
            
            # Ждем перед следующей попыткой
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
        
        logger.error("❌ Все попытки генерации провалились")
        return None, None
    
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
                # Исправленная f-строка - убраны обратные слеши в выражениях
                telegram_paragraphs = tg_text.count('\n\n') + 1
                zen_paragraphs = zen_text.count('\n\n') + 1
                
                instruction = (f"<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
                              f"<b>📱 Telegram пост</b>\n"
                              f"   Канал: {MAIN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(tg_text)}\n"
                              f"   Абзацев: {telegram_paragraphs}\n\n"
                              f"<b>📝 Дзен пост</b>\n"
                              f"   Канал: {ZEN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(zen_text)}\n"
                              f"   Абзацев: {zen_paragraphs}\n\n"
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
            text_format = "разбор ситуации"  # Упрощенно, можно расширить
            
            # Получаем картинку
            image_url, image_description = self.get_post_image_and_description(theme)
            
            # Создаем промпт
            prompt = self.create_detailed_prompt(theme, slot_style, text_format, image_description)
            if not prompt:
                return False
            
            # Генерируем посты
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            tg_text, zen_text = self.generate_with_retry(prompt, tg_min, tg_max, zen_min, zen_max)
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
            
            # Настраиваем обработчики
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
            
            # Определяем слот
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
            
            # Создаем посты
            success = self.create_and_send_posts(slot_time, slot_style)
            
            if not success:
                logger.error("❌ Не удалось создать посты")
                return
            
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
