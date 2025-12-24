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


class Humanizer:
    """Класс для добавления естественных несовершенств в текст"""
    
    @staticmethod
    def add_typos(text: str, error_rate: float = 0.001) -> str:
        """Добавляет опечатки в текст с заданной частотой"""
        if random.random() > 0.1:  # Только в 10% постов
            return text
            
        chars = list(text)
        num_errors = max(1, int(len(chars) * error_rate))
        
        for _ in range(num_errors):
            if len(chars) < 3:
                break
                
            idx = random.randint(0, len(chars) - 1)
            error_type = random.choice(['swap', 'delete', 'duplicate'])
            
            if error_type == 'swap' and idx < len(chars) - 1:
                chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            elif error_type == 'delete':
                del chars[idx]
            elif error_type == 'duplicate':
                chars.insert(idx, chars[idx])
        
        return ''.join(chars)
    
    @staticmethod
    def vary_sentence_length(text: str) -> str:
        """Вариирует длину предложений"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 3:
            return text
            
        # Создаем драматичные различия в длине
        varied = []
        for i, sentence in enumerate(sentences):
            if i % 4 == 0 and len(sentence.split()) > 5:
                # Очень короткое предложение
                words = sentence.split()
                if len(words) > 3:
                    varied.append(' '.join(words[:3]) + '.')
                    varied.append(' '.join(words[3:]))
                else:
                    varied.append(sentence)
            elif i % 3 == 0 and len(sentence.split()) < 15:
                # Удлиняем предложение
                varied.append(sentence + " " + "и поэтому " * random.randint(1, 2))
            else:
                varied.append(sentence)
        
        return ' '.join(varied)
    
    @staticmethod
    def add_colloquial_phrases(text: str) -> str:
        """Добавляет разговорные выражения"""
        if random.random() > 0.1:  # Только в 10% постов
            return text
            
        colloquial = [
            "как говорится,", "ну,", "в общем,", "понимаешь,", 
            "так сказать,", "вот,", "знаешь,", "честно говоря,"
        ]
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 2:
            insert_idx = random.randint(0, min(3, len(sentences) - 1))
            sentences[insert_idx] = f"{random.choice(colloquial)} {sentences[insert_idx].lower()}"
        
        return ' '.join(sentences)


class TextPostProcessor:
    """Оптимизированный класс для интеллектуальной пост-обработки текстов"""
    
    # Константы для структурного анализа
    PRACTICE_MARKERS = [
        '🎯 Важно:', '📋 Шаги:', '🔧 Практика:', '💡 Совет:', '⚡ Действие:',
        '📝 План:', '✅ Задание:', '🎓 Рекомендация:', '🛠️ Инструкция:', '🚀 Стратегия:'
    ]
    CONCLUSION_MARKERS = [
        'Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:', 
        'Вывод:', 'Итог:', 'В результате:', 'Таким образом:', 
        'Следовательно:', 'В заключение:', 'Подводя итоги:'
    ]
    
    # Паттерны "воды" для удаления
    WATER_PATTERNS = [
        r'очень\s+', r'крайне\s+', r'невероятно\s+', r'чрезвычайно\s+',
        r'на\s+самом\s+деле\s+', r'как\s+известно\s*,?\s*', r'как\s+правило\s*,?\s*',
    ]
    
    # Тематически-зависимые правила
    THEME_SPECIFIC_RULES = {
        "ремонт и строительство": {
            "allowed_work_mentions": ["работа на объекте", "работа на стройке", "работа на площадке", "офисная работа"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        },
        "HR и управление персоналом": {
            "allowed_work_mentions": ["офисная работа", "работа в офисе"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        },
        "PR и коммуникации": {
            "allowed_work_mentions": ["офисная работа", "работа в офисе"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        }
    }
    
    def __init__(self, theme: str, slot_style: Dict, post_type: str):
        self.theme = theme
        self.slot_style = slot_style
        self.post_type = post_type
        self.min_chars, self.max_chars = self._get_char_limits()
        self.last_used_markers = self._load_last_used_markers()
        
    def _get_char_limits(self) -> Tuple[int, int]:
        """Получает лимиты символов"""
        if self.post_type == 'telegram':
            return 600, 900  # Обновлено: 600-900 символов
        return 800, 1200  # Обновлено: 800-1200 символов
    
    def _load_last_used_markers(self) -> Dict:
        """Загружает историю использования маркеров"""
        try:
            if os.path.exists("marker_history.json"):
                with open("marker_history.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"practice": [], "conclusion": []}
    
    def _save_marker_usage(self, marker_type: str, marker: str):
        """Сохраняет использование маркера"""
        if marker_type in self.last_used_markers:
            self.last_used_markers[marker_type].append(marker)
            # Храним только последние 3 дня
            if len(self.last_used_markers[marker_type]) > 20:
                self.last_used_markers[marker_type] = self.last_used_markers[marker_type][-20:]
            
            try:
                with open("marker_history.json", 'w', encoding='utf-8') as f:
                    json.dump(self.last_used_markers, f, ensure_ascii=False, indent=2)
            except:
                pass
    
    def _get_available_marker(self, markers: List[str], marker_type: str) -> str:
        """Получает доступный маркер с учетом ротации"""
        if not markers:
            return ""
            
        # Фильтруем маркеры, использованные в последние 2 дня
        recent_used = set(self.last_used_markers.get(marker_type, []))
        available = [m for m in markers if m not in recent_used]
        
        if not available:
            available = markers
            
        marker = random.choice(available)
        self._save_marker_usage(marker_type, marker)
        return marker
    
    def _get_time_appropriate_greeting(self) -> str:
        """Возвращает приветствие в зависимости от реального времени"""
        now = datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            return random.choice(["Доброе утро", "Начало дня", "Старт утра"])
        elif 12 <= hour < 18:
            return random.choice(["Добрый день", "В разгар дня", "После обеда"])
        elif 18 <= hour < 23:
            return random.choice(["Добрый вечер", "В завершение дня", "Подводя итоги"])
        else:
            return random.choice(["Здравствуйте", "Приветствую", "Доброго времени суток"])
    
    def needs_practical_block(self, text: str) -> bool:
        """Определяет, нужен ли практический блок на основе семантического анализа"""
        # Проверяем наличие маркеров практики
        if any(marker in text for marker in self.PRACTICE_MARKERS):
            return False
            
        # Проверяем наличие практических индикаторов
        practical_indicators = [
            'шаг', 'действие', 'план', 'инструкция', 'рекомендация',
            'совет', 'практика', 'упражнение', 'задание', 'алгоритм'
        ]
        
        text_lower = text.lower()
        indicators_count = sum(1 for indicator in practical_indicators if indicator in text_lower)
        
        # Если мало практических указаний, добавляем блок
        return indicators_count < 2
    
    def process(self, raw_text: str) -> str:
        """Основной пайплайн обработки текста"""
        if not raw_text or len(raw_text.strip()) < 50:
            return raw_text
            
        logger.info(f"🔧 Начинаю пост-обработку {self.post_type} поста ({len(raw_text)} символов)")
        
        # 1. Добавление естественных несовершенств
        humanized = Humanizer.add_typos(raw_text)
        humanized = Humanizer.vary_sentence_length(humanized)
        humanized = Humanizer.add_colloquial_phrases(humanized)
        
        # 2. Структурный анализ
        structure = self._analyze_structure(humanized)
        
        # 3. Структурная коррекция
        corrected = self._correct_structure(humanized, structure)
        
        # 4. Интеллектуальное сокращение
        shortened = self._intelligently_shorten(corrected)
        
        # 5. Финальное форматирование
        final = self._apply_formatting(shortened)
        
        # 6. Валидация
        validation = self._validate(final)
        if validation['valid']:
            logger.info(f"✅ Пост-обработка завершена: {len(final)} символов")
        else:
            logger.warning(f"⚠️ Пост прошел обработку с предупреждениями: {validation['warnings']}")
        
        return final
    
    def _analyze_structure(self, text: str) -> Dict:
        """Анализирует структуру текста"""
        structure = {
            'has_emoji_in_start': bool(re.search(r'[🌅🌞🌙]', text[:50])),
            'has_conclusion': any(marker in text for marker in self.CONCLUSION_MARKERS),
            'has_practice': any(marker in text for marker in self.PRACTICE_MARKERS),
            'sentences': re.split(r'(?<=[.!?])\s+', text),
            'hashtags': None,
            'questions': []
        }
        
        # Находим хештеги
        hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        if hashtag_match:
            structure['hashtags'] = {
                'start': hashtag_match.start(),
                'end': len(text),
                'text': hashtag_match.group()
            }
        
        return structure
    
    def _correct_structure(self, text: str, structure: Dict) -> str:
        """Добавляет недостающие структурные элементы"""
        result = text
        
        if self.post_type == 'telegram':
            # Гарантируем эмодзи в начале
            if not structure['has_emoji_in_start'] and 'emoji' in self.slot_style:
                result = f"{self.slot_style['emoji']} {result}"
                logger.info("✅ Добавлен эмодзи в начало Telegram поста")
            
            # Гарантируем практический блок только если нужен
            if self.needs_practical_block(result):
                practical_block = self._generate_practical_block()
                if practical_block:
                    # Вставляем перед хештегами или в конец
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
            
            # Гарантируем блок завершения
            if not structure['has_conclusion']:
                conclusion_block = self._generate_conclusion_block()
                if conclusion_block:
                    if structure['hashtags']:
                        pos = structure['hashtags']['start']
                        result = f"{result[:pos].strip()}\n\n{conclusion_block}\n\n{result[pos:].strip()}"
                    else:
                        result = f"{result.strip()}\n\n{conclusion_block}"
                    logger.info("✅ Добавлен блок завершения в Zen пост")
        
        # Гарантируем хештеги
        if not structure['hashtags']:
            hashtags = self._get_relevant_hashtags()
            result = f"{result.strip()}\n\n{' '.join(hashtags)}"
            logger.info("✅ Добавлены хештеги в пост")
        
        return result
    
    def _generate_practical_block(self) -> str:
        """Генерирует практический блок"""
        templates = {
            "HR и управление персоналом": [
                "🎯 Важно: регулярная обратная связь повышает вовлеченность сотрудников на 30%.",
                "📋 Шаги: 1) проведите оценку компетенций, 2) создайте индивидуальные планы развития, 3) отслеживайте прогресс.",
                "💡 Совет: используйте методику 360 градусов для объективной оценки.",
                "⚡ Действие: проведите блиц-опрос в команде на этой неделе.",
                "📝 План: составьте матрицу компетенций для каждого сотрудника.",
                "✅ Задание: назначьте регулярные one-on-one встречи.",
                "🎓 Рекомендация: внедрите систему геймификации для мотивации.",
                "🛠️ Инструкция: создайте чек-лист для проведения собеседований.",
                "🚀 Стратегия: разработайте карьерные треки для ключевых специалистов.",
            ],
            "PR и коммуникации": [
                "🎯 Важно: честность в коммуникациях строит долгосрочное доверие.",
                "📋 Шаги: 1) определите ключевые сообщения, 2) выберите подходящие каналы, 3) измеряйте эффективность.",
                "💡 Совет: всегда имейте заготовленные ответы на критические вопросы.",
                "⚡ Действие: проанализируйте последнюю кампанию конкурентов.",
                "📝 План: составьте контент-план на месяц вперед.",
                "✅ Задание: проведите аудит текущих коммуникационных каналов.",
                "🎓 Рекомендация: используйте storytelling для усиления сообщений.",
                "🛠️ Инструкция: создайте шаблоны для пресс-релизов.",
                "🚀 Стратегия: разработайте систему мониторинга медиапространства.",
            ],
            "ремонт и строительство": [
                "🎯 Важно: качественная подготовка поверхностей экономит 40% времени на отделке.",
                "📋 Шаги: 1) составьте детальную смета, 2) закупите материалы с запасом 10%, 3) соблюдайте технологию работ.",
                "💡 Совет: всегда делайте пробные выкрасы перед основной покраской.",
                "⚡ Действие: проверьте уровень влажности в помещении перед началом работ.",
                "📝 План: создайте поэтапный план работ с контрольными точками.",
                "✅ Задание: составьте чек-лист приемки материалов.",
                "🎓 Рекомендация: используйте лазерный уровень для точной разметки.",
                "🛠️ Инструкция: следуйте технологии сушки между слоями краски.",
                "🚀 Стратегия: внедрите систему контроля качества на каждом этапе.",
            ]
        }
        
        templates_list = templates.get(self.theme, [
            "🎯 Важно: начните с малого, но делайте это регулярно.",
            "📋 Шаги: 1) проанализируйте текущую ситуацию, 2) определите приоритеты, 3) действуйте последовательно."
        ])
        
        marker = self._get_available_marker(self.PRACTICE_MARKERS, "practice")
        template = random.choice(templates_list)
        
        # Заменяем стандартный маркер на выбранный
        for std_marker in self.PRACTICE_MARKERS:
            if template.startswith(std_marker):
                template = template.replace(std_marker, marker, 1)
                break
        else:
            template = f"{marker} {template}"
        
        return template
    
    def _generate_conclusion_block(self) -> str:
        """Генерирует блок завершения"""
        marker = self._get_available_marker(self.CONCLUSION_MARKERS, "conclusion")
        conclusions = {
            "Почему это важно:": "Понимание этой темы позволяет принимать более взвешенные решения.",
            "Что из этого следует:": "Нужно пересмотреть текущие подходы и внести корректировки.",
            "Мнение экспертов:": "Профессионалы в этой сфере сходятся во мнении, что ключ к успеху — в системном подходе.",
            "Вывод:": "Качественная реализация требует комплексного подхода и внимания к деталям.",
            "Итог:": "Системный подход обеспечивает стабильный результат в долгосрочной перспективе.",
            "В результате:": "Эффективность работы значительно повышается при соблюдении всех рекомендаций.",
            "Таким образом:": "Оптимизация процессов приводит к предсказуемому и качественному результату.",
            "Следовательно:": "Инвестиции в правильные методики окупаются многократно.",
            "В заключение:": "Баланс теории и практики — основа профессионального роста.",
            "Подводя итоги:": "Регулярный анализ и корректировка — залог непрерывного развития."
        }
        
        return f"{marker} {conclusions.get(marker, 'Это важно для достижения успеха.')}"
    
    def _get_relevant_hashtags(self, count: int = 3) -> List[str]:
        """Возвращает релевантные хештеги"""
        hashtags_by_theme = {
            "HR и управление персоналом": ["#HR", "#управлениеперсоналом", "#рекрутинг", "#команда", "#кадры", "#персонал", "#бизнес", "#управление"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#брендинг", "#медиа", "#продвижение", "#соцсети", "#контент"],
            "ремонт и строительство": ["#ремонт", "#строительство", "#дизайн", "#интерьер", "#дом", "#квартира", "#отделка", "#материалы"]
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
        
        # Если все еще длиннее - обрезаем по предложениям, но сохраняем структуру
        if len(result) > self.max_chars:
            # Сохраняем хештеги
            hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', result)
            hashtags = ""
            if hashtag_match:
                hashtags = hashtag_match.group()
                result = result[:hashtag_match.start()].strip()
            
            # Сохраняем практический блок если есть
            practical_block = ""
            for marker in self.PRACTICE_MARKERS:
                if marker in result:
                    # Находим позицию практического блока
                    marker_pos = result.find(marker)
                    if marker_pos != -1:
                        # Ищем конец блока (до следующего маркера или до хештегов)
                        next_newline = result.find('\n\n', marker_pos)
                        if next_newline != -1:
                            practical_block = result[marker_pos:next_newline].strip()
                            result = result[:marker_pos].strip() + "\n\n" + result[next_newline:].strip()
                        else:
                            practical_block = result[marker_pos:].strip()
                            result = result[:marker_pos].strip()
                    break
            
            # Сохраняем заключение если есть
            conclusion_block = ""
            for marker in self.CONCLUSION_MARKERS:
                if marker in result:
                    marker_pos = result.find(marker)
                    if marker_pos != -1:
                        next_newline = result.find('\n\n', marker_pos)
                        if next_newline != -1:
                            conclusion_block = result[marker_pos:next_newline].strip()
                            result = result[:marker_pos].strip() + "\n\n" + result[next_newline:].strip()
                        else:
                            conclusion_block = result[marker_pos:].strip()
                            result = result[:marker_pos].strip()
                    break
            
            # Сокращаем основной текст
            sentences = re.split(r'(?<=[.!?])\s+', result)
            result_parts = []
            current_length = 0
            max_allowed = self.max_chars - len(hashtags) - len(practical_block) - len(conclusion_block) - 20
            
            for sentence in sentences:
                if current_length + len(sentence) + 1 <= max_allowed:
                    result_parts.append(sentence)
                    current_length += len(sentence) + 1
                else:
                    break
            
            result = ' '.join(result_parts).strip()
            
            # Восстанавливаем блоки в правильном порядке
            if practical_block:
                result = f"{result}\n\n{practical_block}"
            
            if conclusion_block:
                result = f"{result}\n\n{conclusion_block}"
            
            if hashtags:
                result = f"{result}\n\n{hashtags}"
        
        return self._ensure_coherent_end(result)
    
    def _ensure_coherent_end(self, text: str) -> str:
        """Гарантирует, что текст заканчивается целым предложением"""
        if not text:
            return text
            
        last_end = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_end > len(text) * 0.8:
            text = text[:last_end + 1].strip()
        
        # Проверяем, не обрезали ли мы хештеги
        if '#' in text:
            hashtag_pos = text.find('#')
            if hashtag_pos > 0:
                # Проверяем, что перед хештегами есть перенос строки
                if text[hashtag_pos-2:hashtag_pos] != '\n\n':
                    text = text[:hashtag_pos].strip() + '\n\n' + text[hashtag_pos:].strip()
        
        if text and text[-1] not in '.!?' and '#' not in text[-10:]:
            text = text + '.'
        
        return text
    
    def _apply_formatting(self, text: str) -> str:
        """Финальное форматирование"""
        if not text:
            return text
        
        # Форматирование переносов строк
        lines = [line.strip() for line in text.split('\n') if line.strip() or line == '']
        formatted_lines = []
        
        for i, line in enumerate(lines):
            if not line:
                if not formatted_lines or formatted_lines[-1] != '':
                    formatted_lines.append('')
                continue
            
            formatted_lines.append(line)
            
            # Добавляем пустую строку после шапки
            if i == 0 and line and len(line) > 10:
                formatted_lines.append('')
        
        result = '\n'.join(formatted_lines)
        
        # Обработка хештеги
        hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', result)
        if hashtag_match:
            hashtags = hashtag_match.group()
            text_without = result[:hashtag_match.start()].strip()
            if not text_without.endswith('\n\n'):
                text_without = text_without + '\n\n'
            result = text_without + hashtags.strip()
        
        return result.strip()
    
    def _validate(self, text: str) -> Dict:
        """Валидация обработанного текста"""
        warnings = []
        text_length = len(text)
        
        if text_length < self.min_chars:
            warnings.append(f"Текст слишком короткий: {text_length} < {self.min_chars}")
        elif text_length > self.max_chars:
            warnings.append(f"Текст слишком длинный: {text_length} > {self.max_chars}")
        
        # Проверка тематических правил
        theme_rules = self.THEME_SPECIFIC_RULES.get(self.theme, {})
        if theme_rules:
            for disallowed in theme_rules.get("disallowed_work_mentions", []):
                if disallowed.lower() in text.lower():
                    warnings.append(f"Найдено запрещенное упоминание: {disallowed}")
        
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


class QualityMonitor:
    """Класс для мониторинга качества постов"""
    
    def __init__(self):
        self.metrics = self._load_metrics()
        
    def _load_metrics(self) -> Dict:
        """Загружает метрики"""
        try:
            if os.path.exists("quality_metrics.json"):
                with open("quality_metrics.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {
            "daily_stats": {},
            "structure_repetition": {},
            "ai_detection_scores": [],
            "engagement_trends": []
        }
    
    def _save_metrics(self):
        """Сохраняет метрики"""
        try:
            with open("quality_metrics.json", 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def track_post(self, post_data: Dict):
        """Отслеживает пост"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.metrics["daily_stats"]:
            self.metrics["daily_stats"][today] = {
                "post_count": 0,
                "total_length": 0,
                "telegram_lengths": [],
                "zen_lengths": []
            }
        
        stats = self.metrics["daily_stats"][today]
        stats["post_count"] += 1
        stats["total_length"] += len(post_data.get("text", ""))
        
        if post_data.get("type") == "telegram":
            stats["telegram_lengths"].append(len(post_data.get("text", "")))
        else:
            stats["zen_lengths"].append(len(post_data.get("text", "")))
        
        self._save_metrics()
    
    def check_avg_post_length(self, post_type: str, length: int) -> bool:
        """Проверяет среднюю длину поста"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today in self.metrics["daily_stats"]:
            if post_type == "telegram":
                lengths = self.metrics["daily_stats"][today].get("telegram_lengths", [])
                if lengths:
                    avg = sum(lengths) / len(lengths)
                    return 600 <= avg <= 900
            else:
                lengths = self.metrics["daily_stats"][today].get("zen_lengths", [])
                if lengths:
                    avg = sum(lengths) / len(lengths)
                    return 800 <= avg <= 1200
        
        return True
    
    def alert_if_needed(self, bot):
        """Отправляет алерт при отклонениях"""
        warnings = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today in self.metrics["daily_stats"]:
            stats = self.metrics["daily_stats"][today]
            
            # Проверка длины Telegram постов
            if stats.get("telegram_lengths"):
                avg_tg = sum(stats["telegram_lengths"]) / len(stats["telegram_lengths"])
                if not (600 <= avg_tg <= 900):
                    warnings.append(f"Средняя длина TG постов: {avg_tg:.0f} (цель: 600-900)")
            
            # Проверка длины Zen постов
            if stats.get("zen_lengths"):
                avg_zen = sum(stats["zen_lengths"]) / len(stats["zen_lengths"])
                if not (800 <= avg_zen <= 1200):
                    warnings.append(f"Средняя длина Zen постов: {avg_zen:.0f} (цель: 800-1200)")
        
        if warnings:
            message = "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ КАЧЕСТВА</b>\n\n" + "\n".join(warnings)
            try:
                bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=message,
                    parse_mode='HTML'
                )
            except:
                pass


class FallbackGenerator:
    """Класс для генерации резервных постов при сбоях"""
    
    def __init__(self):
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict:
        """Загружает шаблоны"""
        return {
            "HR и управление персоналом": {
                "telegram": [
                    "🌅 Доброе утро! Эффективное управление командой начинается с ясных целей. Когда каждый понимает свою роль, продуктивность растет.\n\n🎯 Важно: регулярные встречи 1 на 1 помогают вовремя решать проблемы.\n\n📋 Шаги: 1) Поставьте четкие KPI, 2) Обеспечьте обратную связь, 3) Мотивируйте достижения.\n\nКак вы оцениваете коммуникацию в своей команде?\n\n#HR #управление #команда",
                    "🌞 В середине дня важно оценить процессы. Анализ workflow помогает найти узкие места в работе отдела.\n\n💡 Совет: используйте диаграммы Ганта для визуализации проектов.\n\n⚡ Действие: проведите аудит текущих процессов на этой неделе.\n\nКакие инструменты вы используете для управления проектами?\n\n#управление #процессы #бизнес"
                ],
                "zen": [
                    "Почему даже сильная команда может работать неэффективно? Часто проблема не в людях, а в процессах. Эксперты отмечают: 70% проблем в командах связаны с нечеткими ролями и отсутствием обратной связи.\n\nМнение экспертов: регулярные ретроспективы и открытая коммуникация снижают конфликты на 40%.\n\nКак выстроить прозрачную систему обратной связи в команде?\n\n#HR #команда #управление",
                    "Что важнее для сотрудника: зарплата или признание? Исследования показывают, что баланс материального и нематериального мотивирования дает лучшие результаты. Профессионалы с большим стажем отмечают: публичное признание достижений повышает вовлеченность.\n\nВывод: система мотивации должна быть комплексной и персонализированной.\n\nКак вы мотивируете свою команду?\n\n#мотивация #HR #развитие"
                ]
            },
            "ремонт и строительство": {
                "telegram": [
                    "🌅 Начало рабочего дня на объекте. Качественная подготовка - залог успешного ремонта. Проверьте все материалы до начала работ.\n\n🎯 Важно: запас материалов 10-15% страхует от простоев.\n\n📋 Шаги: 1) Составьте детальный план, 2) Подготовьте инструменты, 3) Соблюдайте технологию.\n\nКак вы организуете работу на объекте?\n\n#ремонт #строительство #объект",
                    "🌞 Работа на стройке в разгаре. Контроль качества на каждом этапе экономит время и ресурсы. Не пропускайте промежуточные проверки.\n\n💡 Совет: делайте фотофиксацию каждого этапа работ.\n\n⚡ Действие: проверьте ровность стен лазерным уровнем.\n\nКакие технологии контроля вы используете?\n\n#стройка #качество #технологии"
                ],
                "zen": [
                    "Почему даже дорогой ремонт может разочаровать? Часто причина в несоблюдении базовых принципов работы с материалами. По опыту практиков сферы: 60% проблем возникают из-за нарушения технологии сушки и подготовки поверхностей.\n\nЧто из этого следует: экономия на подготовительных работах ведет к удорожанию в 2-3 раза на этапе отделки.\n\nКак избежать типичных ошибок при ремонте?\n\n#ремонт #технологии #советы",
                    "Можно ли сэкономить на строительных материалах без потери качества? Эксперты с большим стажем отмечают: разумная экономия возможна при грамотном планировании и выборе альтернативных материалов с аналогичными характеристиками.\n\nВ результате: профессиональный расчет материалов позволяет снизить стоимость на 15-20% без ущерба качеству.\n\nКак вы выбираете материалы для объекта?\n\n#строительство #материалы #экономия"
                ]
            },
            "PR и коммуникации": {
                "telegram": [
                    "🌅 Доброе утро! Первые впечатления важны в коммуникациях. Как ваш бренд выглядит со стороны?\n\n🎯 Важно: consistency в сообщениях строит доверие.\n\n📋 Шаги: 1) Анализ аудитории, 2) Ключевые сообщения, 3) Подходящие каналы.\n\nКак вы проверяете восприятие вашего бренда?\n\n#PR #коммуникации #бренд",
                    "🌞 Время для анализа медиаактивности. Что говорят о вашей компании в сети? Мониторинг упоминаний помогает вовремя реагировать.\n\n💡 Совет: настройте алерты по ключевым словам.\n\n⚡ Действие: проанализируйте последнюю неделю упоминаний.\n\nКакие инструменты мониторинга вы используете?\n\n#медиа #аналитика #PR"
                ],
                "zen": [
                    "Почему некоторые компании становятся медиа-героями, а другие остаются незамеченными? Секрет в стратегии storytelling. Как отмечают специалисты: истории, а не факты, вызывают эмоциональный отклик аудитории.\n\nТаким образом: трансформация сухих данных в нарратив увеличивает вовлеченность на 300%.\n\nКак создавать истории вокруг вашего бренда?\n\n#сторителлинг #PR #бренд",
                    "Кризис в соцсетях: как не потерять лицо компании? Профессионалы в этой сфере сходятся во мнении: скорость и искренность реакции важнее безупречности формулировок. В профессиональной среде считается: первые 60 минут определяют развитие ситуации.\n\nВывод: подготовленный план действий в кризисной ситуации экономит репутацию.\n\nЕсть ли у вас антикризисный протокол?\n\n#кризис #репутация #соцсети"
                ]
            }
        }
    
    def generate_fallback_post(self, theme: str, post_type: str) -> str:
        """Генерирует резервный пост"""
        theme_templates = self.templates.get(theme, {})
        type_templates = theme_templates.get(post_type, [])
        
        if type_templates:
            return random.choice(type_templates)
        
        # Универсальный шаблон
        if post_type == "telegram":
            return "🌅 Важная тема для обсуждения. Практический опыт показывает, что системный подход дает лучшие результаты.\n\n🎯 Важно: начинайте с анализа текущей ситуации.\n\n📋 Шаги: 1) Изучите проблему, 2) Составьте план, 3) Действуйте последовательно.\n\nКак вы решаете подобные задачи?\n\n#советы #бизнес #развитие"
        else:
            return "Актуальный вопрос для профессионалов. Эксперты отмечают важность комплексного подхода к решению задач. По отраслевой практике: глубокий анализ и поэтапная реализация обеспечивают стабильный результат.\n\nМнение экспертов: инвестиции в системность окупаются многократно в долгосрочной перспективе.\n\nКакой подход вы считаете наиболее эффективным?\n\n#экспертиза #анализ #результат"


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
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
            "max_output_tokens": 1100
        },
        "15:00": {
            "name": "Дневной пост",
            "type": "day",
            "emoji": "🌞",
            "style": "рациональность и аналитика: наблюдение, разбор явления, микро1исследование",
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
            "max_output_tokens": 1350
        },
        "20:00": {
            "name": "Вечерний пост",
            "type": "evening",
            "emoji": "🌙",
            "style": "глубина и история: личный взгляд, мини1история, аналогия",
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
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
        self.quality_monitor = QualityMonitor()
        self.fallback_generator = FallbackGenerator()
        
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
        tg_min, tg_max = 600, 900  # Обновленные лимиты
        zen_min, zen_max = 800, 1200  # Обновленные лимиты
        
        # Динамические временные правила
        now_hour = self.get_moscow_time().hour
        if 5 <= now_hour < 12:
            time_rules = "СТРОГОЕ ПРАВИЛО: Пост должен начинаться с утреннего приветствия: 'Доброе утро', 'Начало дня', 'Старт утра'. Запрещены любые вечерние или дневные приветствия."
        elif 12 <= now_hour < 18:
            time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние ('Доброе утро') и вечерние ('Добрый вечер') приветствия. Только нейтральный деловой или информационный тон без привязки ко времени суток."
        elif 18 <= now_hour < 23:
            time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние приветствия ('Доброе утро'). Можно использовать: 'Добрый вечер', 'В завершение дня', 'Подводя итоги'. Только спокойный рефлексивный тон."
        else:
            time_rules = "СТРОГОЕ ПРАВИЛО: Используйте нейтральные приветствия без привязки ко времени суток: 'Здравствуйте', 'Приветствую', 'Доброго времени суток'."
        
        # Тематически-зависимые правила работы
        work_mentions = TextPostProcessor.THEME_SPECIFIC_RULES.get(theme, {})
        allowed_work = work_mentions.get("allowed_work_mentions", ["офисная работа"])
        disallowed_work = work_mentions.get("disallowed_work_mentions", [])
        
        allowed_text = "РАЗРЕШЕНО УПОМИНАТЬ:\n" + "\n".join(f"• {work}" for work in allowed_work)
        disallowed_text = "ЗАПРЕЩЕНО УПОМИНАТЬ:\n" + "\n".join(f"• {work}" for work in disallowed_work)
        
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
 • Сделай так, чтобы текст звучал как написанный настоящим человек с живым голосом
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

🚫 {disallowed_text}

✅ {allowed_text}

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
• Практический блок с конкретными действиями (используй разнообразные маркеры: {', '.join(TextPostProcessor.PRACTICE_MARKERS[:5])})
• Вопрос для вовлечения аудитории
• 3-5 релевантных хештегов в конце
• Объём: {tg_min}-{tg_max} символов (ОБЯЗАТЕЛЬНО!)

ТРЕБОВАНИЯ К ZEN ПОСТУ:
• Начало: провокационный вопрос или утверждение ("крючок-убийца")
• Основная часть: глубина анализа, экспертные мнения
• Завершение: естественный вывод (можно использовать разнообразные маркеры: {', '.join(TextPostProcessor.CONCLUSION_MARKERS[:5])})
• Вопрос для обсуждения
• 3-5 релевантных хештегов в конце
• Объём: {zen_min}-{zen_max} символов (ОБЯЗАТЕЛЬНО!)

🖼️ КАРТИНКА: {image_description}

🚫 ЗАПРЕЩЕНО В ТЕКСТЕ:
• Использовать формулировки от первого лица о личном опыте
• Шаблонные фразы, которые звучат как ИИ
• Писать "вот текст для Telegram/Дзен"
• Указывать "тема: {theme}" в тексте

✅ ОБЯЗАТЕЛЬНО В ТЕКСТЕ:
• Естественный человеческий язык
• Практическая польза
• Уникальность каждого поста
• Соблюдение лимитов символов
• Телеграм пост начинается с эмодзи {slot_style['emoji']}
• Дзен пост начинается без эмодзи

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (полностью по шаблону с эмодзи)
• Потом Дзен версия (полностью по шаблону «Крючок-убийца» без эмодзи)
• Разделитель: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя всем правилам выше."""
        
        return prompt
    
    def parse_generated_texts(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Парсит сгенерированные тексты с умным разделением"""
        if not text:
            return None, None
        
        # Множество разделителей
        separators = ["\n---\n", "\n***\n", "\n###\n", "\n––––\n"]
        
        # Пробуем каждый разделитель
        for separator in separators:
            if separator in text:
                parts = text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # Базовая валидация
                    if len(tg_text) > 100 and len(zen_text) > 100:
                        return tg_text, zen_text
        
        # ML-подход: ищем смену стиля по эмодзи в начале
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Ищем первую строку без эмодзи (предположительно начало Zen)
        for i, line in enumerate(lines):
            if i > 0 and not re.search(r'[🌅🌞🌙🎯📋🔧💡⚡📝✅🎓🛠️🚀]', line[:10]):
                tg_text = '\n'.join(lines[:i]).strip()
                zen_text = '\n'.join(lines[i:]).strip()
                
                if len(tg_text) > 100 and len(zen_text) > 100:
                    return tg_text, zen_text
        
        # Fallback: разделяем пополам
        half = len(lines) // 2
        tg_text = '\n'.join(lines[:half]).strip()
        zen_text = '\n'.join(lines[half:]).strip()
        
        if len(tg_text) > 100 and len(zen_text) > 100:
            return tg_text, zen_text
        
        # Если все еще не удалось - отправляем уведомление
        logger.error("❌ Не удалось распарсить сгенерированный текст")
        self.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="⚠️ <b>ПРОБЛЕМА ПАРСИНГА</b>\n\nНе удалось распарсить сгенерированный текст. Использую резервные шаблоны.",
            parse_mode='HTML'
        )
        
        return None, None
    
    def generate_with_retry(self, prompt: str, tg_min: int, tg_max: int, zen_min: int, zen_max: int, 
                           max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Генерация с повторными попытками и fallback"""
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
        
        logger.error("❌ Все попытки генерации провалились, использую fallback")
        
        # Используем резервные шаблоны
        tg_fallback = self.fallback_generator.generate_fallback_post(self.current_theme, 'telegram')
        zen_fallback = self.fallback_generator.generate_fallback_post(self.current_theme, 'zen')
        
        # Отправляем уведомление
        self.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ <b>ИСПОЛЬЗОВАН FALLBACK</b>\n\nГенерация поста для темы '{self.current_theme}' не удалась после {max_attempts} попыток. Использованы резервные шаблоны.",
            parse_mode='HTML'
        )
        
        return tg_fallback, zen_fallback
    
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
            
            # Отслеживаем качество
            self.quality_monitor.track_post(post_data)
            
            # Проверяем среднюю длину
            if not self.quality_monitor.check_avg_post_length(post_data.get('type', ''), len(post_data.get('text', ''))):
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\nДлина {post_data.get('type', '')} поста ({len(post_data.get('text', ''))}) выходит за целевые пределы.",
                    parse_mode='HTML'
                )
            
            # Обновляем статус в сообщении с учетом лимита Telegram (1024 символа)
            try:
                status_text = f"\n\n<b>✅ Опубликовано в {post_data.get('channel', 'канал')}</b>"
                caption_text = post_data['text'][:1020 - len(status_text)] if len(post_data['text']) > 1020 - len(status_text) else post_data['text']
                
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=f"{caption_text}{status_text}",
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
            
            # Обновляем статус с учетом лимита Telegram
            try:
                status_text = f"\n\n<b>❌ Отклонено</b>"
                caption_text = post_data['text'][:1020 - len(status_text)] if len(post_data['text']) > 1020 - len(status_text) else post_data['text']
                
                if 'image_url' in post_data and post_data['image_url']:
                    self.bot.edit_message_caption(
                        chat_id=ADMIN_CHAT_ID,
                        message_id=message_id,
                        caption=f"{caption_text}{status_text}",
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
                # Обрезаем текст для подписи если нужно
                caption_text = post_data['text'][:1024] if len(post_data['text']) > 1024 else post_data['text']
                self.bot.edit_message_caption(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=message_id,
                    caption=caption_text,
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
            
            # Ночная зона: 23:00-04:59 → Нейтральный слот
            if hour >= 23 or hour < 5:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            # Утренняя зона: 05:00-10:59 → Утренний слот
            if hour >= 5 and hour < 11:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            # Дневная зона: 11:00-14:59 → Дневной слот
            if hour >= 11 and hour < 15:
                return "15:00", self.TIME_STYLES.get("15:00")
            
            # Вечерняя зона: 15:00-22:59 → Вечерний слот
            return "20:00", self.TIME_STYLES.get("20:00")
            
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
                    # Telegram ограничивает подпись к фото 1024 символами
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
                instruction = (f"<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
                              f"<b>📱 Telegram пост</b>\n"
                              f"   Канал: {MAIN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(tg_text)}\n\n"
                              f"<b>📝 Дзен пост</b>\n"
                              f"   Канал: {ZEN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(zen_text)}\n\n"
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
            
            # Создаем промпт
            prompt = self.create_detailed_prompt(theme, slot_style, text_format, image_description)
            if not prompt:
                return False
            
            # Генерируем посты
            tg_min, tg_max = 600, 900
            zen_min, zen_max = 800, 1200
            
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
                
                # Проверяем качество
                self.quality_monitor.alert_if_needed(self.bot)
                
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
    main()# github_bot.py - Telegram бот для автоматической публикации постов
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


class Humanizer:
    """Класс для добавления естественных несовершенств в текст"""
    
    @staticmethod
    def add_typos(text: str, error_rate: float = 0.001) -> str:
        """Добавляет опечатки в текст с заданной частотой"""
        if random.random() > 0.1:  # Только в 10% постов
            return text
            
        chars = list(text)
        num_errors = max(1, int(len(chars) * error_rate))
        
        for _ in range(num_errors):
            if len(chars) < 3:
                break
                
            idx = random.randint(0, len(chars) - 1)
            error_type = random.choice(['swap', 'delete', 'duplicate'])
            
            if error_type == 'swap' and idx < len(chars) - 1:
                chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            elif error_type == 'delete':
                del chars[idx]
            elif error_type == 'duplicate':
                chars.insert(idx, chars[idx])
        
        return ''.join(chars)
    
    @staticmethod
    def vary_sentence_length(text: str) -> str:
        """Вариирует длину предложений"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 3:
            return text
            
        # Создаем драматичные различия в длине
        varied = []
        for i, sentence in enumerate(sentences):
            if i % 4 == 0 and len(sentence.split()) > 5:
                # Очень короткое предложение
                words = sentence.split()
                if len(words) > 3:
                    varied.append(' '.join(words[:3]) + '.')
                    varied.append(' '.join(words[3:]))
                else:
                    varied.append(sentence)
            elif i % 3 == 0 and len(sentence.split()) < 15:
                # Удлиняем предложение
                varied.append(sentence + " " + "и поэтому " * random.randint(1, 2))
            else:
                varied.append(sentence)
        
        return ' '.join(varied)
    
    @staticmethod
    def add_colloquial_phrases(text: str) -> str:
        """Добавляет разговорные выражения"""
        if random.random() > 0.1:  # Только в 10% постов
            return text
            
        colloquial = [
            "как говорится,", "ну,", "в общем,", "понимаешь,", 
            "так сказать,", "вот,", "знаешь,", "честно говоря,"
        ]
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) > 2:
            insert_idx = random.randint(0, min(3, len(sentences) - 1))
            sentences[insert_idx] = f"{random.choice(colloquial)} {sentences[insert_idx].lower()}"
        
        return ' '.join(sentences)


class TextPostProcessor:
    """Оптимизированный класс для интеллектуальной пост-обработки текстов"""
    
    # Константы для структурного анализа
    PRACTICE_MARKERS = [
        '🎯 Важно:', '📋 Шаги:', '🔧 Практика:', '💡 Совет:', '⚡ Действие:',
        '📝 План:', '✅ Задание:', '🎓 Рекомендация:', '🛠️ Инструкция:', '🚀 Стратегия:'
    ]
    CONCLUSION_MARKERS = [
        'Почему это важно:', 'Что из этого следует:', 'Мнение экспертов:', 
        'Вывод:', 'Итог:', 'В результате:', 'Таким образом:', 
        'Следовательно:', 'В заключение:', 'Подводя итоги:'
    ]
    
    # Паттерны "воды" для удаления
    WATER_PATTERNS = [
        r'очень\s+', r'крайне\s+', r'невероятно\s+', r'чрезвычайно\s+',
        r'на\s+самом\s+деле\s+', r'как\s+известно\s*,?\s*', r'как\s+правило\s*,?\s*',
    ]
    
    # Тематически-зависимые правила
    THEME_SPECIFIC_RULES = {
        "ремонт и строительство": {
            "allowed_work_mentions": ["работа на объекте", "работа на стройке", "работа на площадке", "офисная работа"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        },
        "HR и управление персоналом": {
            "allowed_work_mentions": ["офисная работа", "работа в офисе"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        },
        "PR и коммуникации": {
            "allowed_work_mentions": ["офисная работа", "работа в офисе"],
            "disallowed_work_mentions": ["удаленная работа", "remote work", "релокация", "гибридный формат"]
        }
    }
    
    def __init__(self, theme: str, slot_style: Dict, post_type: str):
        self.theme = theme
        self.slot_style = slot_style
        self.post_type = post_type
        self.min_chars, self.max_chars = self._get_char_limits()
        self.last_used_markers = self._load_last_used_markers()
        
    def _get_char_limits(self) -> Tuple[int, int]:
        """Получает лимиты символов"""
        if self.post_type == 'telegram':
            return 600, 900  # Обновлено: 600-900 символов
        return 800, 1200  # Обновлено: 800-1200 символов
    
    def _load_last_used_markers(self) -> Dict:
        """Загружает историю использования маркеров"""
        try:
            if os.path.exists("marker_history.json"):
                with open("marker_history.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"practice": [], "conclusion": []}
    
    def _save_marker_usage(self, marker_type: str, marker: str):
        """Сохраняет использование маркера"""
        if marker_type in self.last_used_markers:
            self.last_used_markers[marker_type].append(marker)
            # Храним только последние 3 дня
            if len(self.last_used_markers[marker_type]) > 20:
                self.last_used_markers[marker_type] = self.last_used_markers[marker_type][-20:]
            
            try:
                with open("marker_history.json", 'w', encoding='utf-8') as f:
                    json.dump(self.last_used_markers, f, ensure_ascii=False, indent=2)
            except:
                pass
    
    def _get_available_marker(self, markers: List[str], marker_type: str) -> str:
        """Получает доступный маркер с учетом ротации"""
        if not markers:
            return ""
            
        # Фильтруем маркеры, использованные в последние 2 дня
        recent_used = set(self.last_used_markers.get(marker_type, []))
        available = [m for m in markers if m not in recent_used]
        
        if not available:
            available = markers
            
        marker = random.choice(available)
        self._save_marker_usage(marker_type, marker)
        return marker
    
    def _get_time_appropriate_greeting(self) -> str:
        """Возвращает приветствие в зависимости от реального времени"""
        now = datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            return random.choice(["Доброе утро", "Начало дня", "Старт утра"])
        elif 12 <= hour < 18:
            return random.choice(["Добрый день", "В разгар дня", "После обеда"])
        elif 18 <= hour < 23:
            return random.choice(["Добрый вечер", "В завершение дня", "Подводя итоги"])
        else:
            return random.choice(["Здравствуйте", "Приветствую", "Доброго времени суток"])
    
    def needs_practical_block(self, text: str) -> bool:
        """Определяет, нужен ли практический блок на основе семантического анализа"""
        # Проверяем наличие маркеров практики
        if any(marker in text for marker in self.PRACTICE_MARKERS):
            return False
            
        # Проверяем наличие практических индикаторов
        practical_indicators = [
            'шаг', 'действие', 'план', 'инструкция', 'рекомендация',
            'совет', 'практика', 'упражнение', 'задание', 'алгоритм'
        ]
        
        text_lower = text.lower()
        indicators_count = sum(1 for indicator in practical_indicators if indicator in text_lower)
        
        # Если мало практических указаний, добавляем блок
        return indicators_count < 2
    
    def process(self, raw_text: str) -> str:
        """Основной пайплайн обработки текста"""
        if not raw_text or len(raw_text.strip()) < 50:
            return raw_text
            
        logger.info(f"🔧 Начинаю пост-обработку {self.post_type} поста ({len(raw_text)} символов)")
        
        # 1. Добавление естественных несовершенств
        humanized = Humanizer.add_typos(raw_text)
        humanized = Humanizer.vary_sentence_length(humanized)
        humanized = Humanizer.add_colloquial_phrases(humanized)
        
        # 2. Структурный анализ
        structure = self._analyze_structure(humanized)
        
        # 3. Структурная коррекция
        corrected = self._correct_structure(humanized, structure)
        
        # 4. Интеллектуальное сокращение
        shortened = self._intelligently_shorten(corrected)
        
        # 5. Финальное форматирование
        final = self._apply_formatting(shortened)
        
        # 6. Валидация
        validation = self._validate(final)
        if validation['valid']:
            logger.info(f"✅ Пост-обработка завершена: {len(final)} символов")
        else:
            logger.warning(f"⚠️ Пост прошел обработку с предупреждениями: {validation['warnings']}")
        
        return final
    
    def _analyze_structure(self, text: str) -> Dict:
        """Анализирует структуру текста"""
        structure = {
            'has_emoji_in_start': bool(re.search(r'[🌅🌞🌙]', text[:50])),
            'has_conclusion': any(marker in text for marker in self.CONCLUSION_MARKERS),
            'has_practice': any(marker in text for marker in self.PRACTICE_MARKERS),
            'sentences': re.split(r'(?<=[.!?])\s+', text),
            'hashtags': None,
            'questions': []
        }
        
        # Находим хештеги
        hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', text)
        if hashtag_match:
            structure['hashtags'] = {
                'start': hashtag_match.start(),
                'end': len(text),
                'text': hashtag_match.group()
            }
        
        return structure
    
    def _correct_structure(self, text: str, structure: Dict) -> str:
        """Добавляет недостающие структурные элементы"""
        result = text
        
        if self.post_type == 'telegram':
            # Гарантируем эмодзи в начале
            if not structure['has_emoji_in_start'] and 'emoji' in self.slot_style:
                result = f"{self.slot_style['emoji']} {result}"
                logger.info("✅ Добавлен эмодзи в начало Telegram поста")
            
            # Гарантируем практический блок только если нужен
            if self.needs_practical_block(result):
                practical_block = self._generate_practical_block()
                if practical_block:
                    # Вставляем перед хештегами или в конец
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
            
            # Гарантируем блок завершения
            if not structure['has_conclusion']:
                conclusion_block = self._generate_conclusion_block()
                if conclusion_block:
                    if structure['hashtags']:
                        pos = structure['hashtags']['start']
                        result = f"{result[:pos].strip()}\n\n{conclusion_block}\n\n{result[pos:].strip()}"
                    else:
                        result = f"{result.strip()}\n\n{conclusion_block}"
                    logger.info("✅ Добавлен блок завершения в Zen пост")
        
        # Гарантируем хештеги
        if not structure['hashtags']:
            hashtags = self._get_relevant_hashtags()
            result = f"{result.strip()}\n\n{' '.join(hashtags)}"
            logger.info("✅ Добавлены хештеги в пост")
        
        return result
    
    def _generate_practical_block(self) -> str:
        """Генерирует практический блок"""
        templates = {
            "HR и управление персоналом": [
                "🎯 Важно: регулярная обратная связь повышает вовлеченность сотрудников на 30%.",
                "📋 Шаги: 1) проведите оценку компетенций, 2) создайте индивидуальные планы развития, 3) отслеживайте прогресс.",
                "💡 Совет: используйте методику 360 градусов для объективной оценки.",
                "⚡ Действие: проведите блиц-опрос в команде на этой неделе.",
                "📝 План: составьте матрицу компетенций для каждого сотрудника.",
                "✅ Задание: назначьте регулярные one-on-one встречи.",
                "🎓 Рекомендация: внедрите систему геймификации для мотивации.",
                "🛠️ Инструкция: создайте чек-лист для проведения собеседований.",
                "🚀 Стратегия: разработайте карьерные треки для ключевых специалистов.",
            ],
            "PR и коммуникации": [
                "🎯 Важно: честность в коммуникациях строит долгосрочное доверие.",
                "📋 Шаги: 1) определите ключевые сообщения, 2) выберите подходящие каналы, 3) измеряйте эффективность.",
                "💡 Совет: всегда имейте заготовленные ответы на критические вопросы.",
                "⚡ Действие: проанализируйте последнюю кампанию конкурентов.",
                "📝 План: составьте контент-план на месяц вперед.",
                "✅ Задание: проведите аудит текущих коммуникационных каналов.",
                "🎓 Рекомендация: используйте storytelling для усиления сообщений.",
                "🛠️ Инструкция: создайте шаблоны для пресс-релизов.",
                "🚀 Стратегия: разработайте систему мониторинга медиапространства.",
            ],
            "ремонт и строительство": [
                "🎯 Важно: качественная подготовка поверхностей экономит 40% времени на отделке.",
                "📋 Шаги: 1) составьте детальную смета, 2) закупите материалы с запасом 10%, 3) соблюдайте технологию работ.",
                "💡 Совет: всегда делайте пробные выкрасы перед основной покраской.",
                "⚡ Действие: проверьте уровень влажности в помещении перед началом работ.",
                "📝 План: создайте поэтапный план работ с контрольными точками.",
                "✅ Задание: составьте чек-лист приемки материалов.",
                "🎓 Рекомендация: используйте лазерный уровень для точной разметки.",
                "🛠️ Инструкция: следуйте технологии сушки между слоями краски.",
                "🚀 Стратегия: внедрите систему контроля качества на каждом этапе.",
            ]
        }
        
        templates_list = templates.get(self.theme, [
            "🎯 Важно: начните с малого, но делайте это регулярно.",
            "📋 Шаги: 1) проанализируйте текущую ситуацию, 2) определите приоритеты, 3) действуйте последовательно."
        ])
        
        marker = self._get_available_marker(self.PRACTICE_MARKERS, "practice")
        template = random.choice(templates_list)
        
        # Заменяем стандартный маркер на выбранный
        for std_marker in self.PRACTICE_MARKERS:
            if template.startswith(std_marker):
                template = template.replace(std_marker, marker, 1)
                break
        else:
            template = f"{marker} {template}"
        
        return template
    
    def _generate_conclusion_block(self) -> str:
        """Генерирует блок завершения"""
        marker = self._get_available_marker(self.CONCLUSION_MARKERS, "conclusion")
        conclusions = {
            "Почему это важно:": "Понимание этой темы позволяет принимать более взвешенные решения.",
            "Что из этого следует:": "Нужно пересмотреть текущие подходы и внести корректировки.",
            "Мнение экспертов:": "Профессионалы в этой сфере сходятся во мнении, что ключ к успеху — в системном подходе.",
            "Вывод:": "Качественная реализация требует комплексного подхода и внимания к деталям.",
            "Итог:": "Системный подход обеспечивает стабильный результат в долгосрочной перспективе.",
            "В результате:": "Эффективность работы значительно повышается при соблюдении всех рекомендаций.",
            "Таким образом:": "Оптимизация процессов приводит к предсказуемому и качественному результату.",
            "Следовательно:": "Инвестиции в правильные методики окупаются многократно.",
            "В заключение:": "Баланс теории и практики — основа профессионального роста.",
            "Подводя итоги:": "Регулярный анализ и корректировка — залог непрерывного развития."
        }
        
        return f"{marker} {conclusions.get(marker, 'Это важно для достижения успеха.')}"
    
    def _get_relevant_hashtags(self, count: int = 3) -> List[str]:
        """Возвращает релевантные хештеги"""
        hashtags_by_theme = {
            "HR и управление персоналом": ["#HR", "#управлениеперсоналом", "#рекрутинг", "#команда", "#кадры", "#персонал", "#бизнес", "#управление"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#брендинг", "#медиа", "#продвижение", "#соцсети", "#контент"],
            "ремонт и строительство": ["#ремонт", "#строительство", "#дизайн", "#интерьер", "#дом", "#квартира", "#отделка", "#материалы"]
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
        """Финальное форматирование"""
        if not text:
            return text
        
        # Форматирование переносов строк
        lines = [line.strip() for line in text.split('\n') if line.strip() or line == '']
        formatted_lines = []
        
        for i, line in enumerate(lines):
            if not line:
                if not formatted_lines or formatted_lines[-1] != '':
                    formatted_lines.append('')
                continue
            
            formatted_lines.append(line)
            
            # Добавляем пустую строку после шапки
            if i == 0 and line and len(line) > 10:
                formatted_lines.append('')
        
        result = '\n'.join(formatted_lines)
        
        # Обработка хештеги
        hashtag_match = re.search(r'\n\n(#[\w\u0400-\u04FF]+(?:\s+#[\w\u0400-\u04FF]+)*\s*)$', result)
        if hashtag_match:
            hashtags = hashtag_match.group()
            text_without = result[:hashtag_match.start()].strip()
            if not text_without.endswith('\n\n'):
                text_without = text_without + '\n\n'
            result = text_without + hashtags.strip()
        
        return result.strip()
    
    def _validate(self, text: str) -> Dict:
        """Валидация обработанного текста"""
        warnings = []
        text_length = len(text)
        
        if text_length < self.min_chars:
            warnings.append(f"Текст слишком короткий: {text_length} < {self.min_chars}")
        elif text_length > self.max_chars:
            warnings.append(f"Текст слишком длинный: {text_length} > {self.max_chars}")
        
        # Проверка тематических правил
        theme_rules = self.THEME_SPECIFIC_RULES.get(self.theme, {})
        if theme_rules:
            for disallowed in theme_rules.get("disallowed_work_mentions", []):
                if disallowed.lower() in text.lower():
                    warnings.append(f"Найдено запрещенное упоминание: {disallowed}")
        
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


class QualityMonitor:
    """Класс для мониторинга качества постов"""
    
    def __init__(self):
        self.metrics = self._load_metrics()
        
    def _load_metrics(self) -> Dict:
        """Загружает метрики"""
        try:
            if os.path.exists("quality_metrics.json"):
                with open("quality_metrics.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {
            "daily_stats": {},
            "structure_repetition": {},
            "ai_detection_scores": [],
            "engagement_trends": []
        }
    
    def _save_metrics(self):
        """Сохраняет метрики"""
        try:
            with open("quality_metrics.json", 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def track_post(self, post_data: Dict):
        """Отслеживает пост"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today not in self.metrics["daily_stats"]:
            self.metrics["daily_stats"][today] = {
                "post_count": 0,
                "total_length": 0,
                "telegram_lengths": [],
                "zen_lengths": []
            }
        
        stats = self.metrics["daily_stats"][today]
        stats["post_count"] += 1
        stats["total_length"] += len(post_data.get("text", ""))
        
        if post_data.get("type") == "telegram":
            stats["telegram_lengths"].append(len(post_data.get("text", "")))
        else:
            stats["zen_lengths"].append(len(post_data.get("text", "")))
        
        self._save_metrics()
    
    def check_avg_post_length(self, post_type: str, length: int) -> bool:
        """Проверяет среднюю длину поста"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today in self.metrics["daily_stats"]:
            if post_type == "telegram":
                lengths = self.metrics["daily_stats"][today].get("telegram_lengths", [])
                if lengths:
                    avg = sum(lengths) / len(lengths)
                    return 600 <= avg <= 900
            else:
                lengths = self.metrics["daily_stats"][today].get("zen_lengths", [])
                if lengths:
                    avg = sum(lengths) / len(lengths)
                    return 800 <= avg <= 1200
        
        return True
    
    def alert_if_needed(self, bot):
        """Отправляет алерт при отклонениях"""
        warnings = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        if today in self.metrics["daily_stats"]:
            stats = self.metrics["daily_stats"][today]
            
            # Проверка длины Telegram постов
            if stats.get("telegram_lengths"):
                avg_tg = sum(stats["telegram_lengths"]) / len(stats["telegram_lengths"])
                if not (600 <= avg_tg <= 900):
                    warnings.append(f"Средняя длина TG постов: {avg_tg:.0f} (цель: 600-900)")
            
            # Проверка длины Zen постов
            if stats.get("zen_lengths"):
                avg_zen = sum(stats["zen_lengths"]) / len(stats["zen_lengths"])
                if not (800 <= avg_zen <= 1200):
                    warnings.append(f"Средняя длина Zen постов: {avg_zen:.0f} (цель: 800-1200)")
        
        if warnings:
            message = "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ КАЧЕСТВА</b>\n\n" + "\n".join(warnings)
            try:
                bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=message,
                    parse_mode='HTML'
                )
            except:
                pass


class FallbackGenerator:
    """Класс для генерации резервных постов при сбоях"""
    
    def __init__(self):
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict:
        """Загружает шаблоны"""
        return {
            "HR и управление персоналом": {
                "telegram": [
                    "🌅 Доброе утро! Эффективное управление командой начинается с ясных целей. Когда каждый понимает свою роль, продуктивность растет.\n\n🎯 Важно: регулярные встречи 1 на 1 помогают вовремя решать проблемы.\n\n📋 Шаги: 1) Поставьте четкие KPI, 2) Обеспечьте обратную связь, 3) Мотивируйте достижения.\n\nКак вы оцениваете коммуникацию в своей команде?\n\n#HR #управление #команда",
                    "🌞 В середине дня важно оценить процессы. Анализ workflow помогает найти узкие места в работе отдела.\n\n💡 Совет: используйте диаграммы Ганта для визуализации проектов.\n\n⚡ Действие: проведите аудит текущих процессов на этой неделе.\n\nКакие инструменты вы используете для управления проектами?\n\n#управление #процессы #бизнес"
                ],
                "zen": [
                    "Почему даже сильная команда может работать неэффективно? Часто проблема не в людях, а в процессах. Эксперты отмечают: 70% проблем в командах связаны с нечеткими ролями и отсутствием обратной связи.\n\nМнение экспертов: регулярные ретроспективы и открытая коммуникация снижают конфликты на 40%.\n\nКак выстроить прозрачную систему обратной связи в команде?\n\n#HR #команда #управление",
                    "Что важнее для сотрудника: зарплата или признание? Исследования показывают, что баланс материального и нематериального мотивирования дает лучшие результаты. Профессионалы с большим стажем отмечают: публичное признание достижений повышает вовлеченность.\n\nВывод: система мотивации должна быть комплексной и персонализированной.\n\nКак вы мотивируете свою команду?\n\n#мотивация #HR #развитие"
                ]
            },
            "ремонт и строительство": {
                "telegram": [
                    "🌅 Начало рабочего дня на объекте. Качественная подготовка - залог успешного ремонта. Проверьте все материалы до начала работ.\n\n🎯 Важно: запас материалов 10-15% страхует от простоев.\n\n📋 Шаги: 1) Составьте детальный план, 2) Подготовьте инструменты, 3) Соблюдайте технологию.\n\nКак вы организуете работу на объекте?\n\n#ремонт #строительство #объект",
                    "🌞 Работа на стройке в разгаре. Контроль качества на каждом этапе экономит время и ресурсы. Не пропускайте промежуточные проверки.\n\n💡 Совет: делайте фотофиксацию каждого этапа работ.\n\n⚡ Действие: проверьте ровность стен лазерным уровнем.\n\nКакие технологии контроля вы используете?\n\n#стройка #качество #технологии"
                ],
                "zen": [
                    "Почему даже дорогой ремонт может разочаровать? Часто причина в несоблюдении базовых принципов работы с материалами. По опыту практиков сферы: 60% проблем возникают из-за нарушения технологии сушки и подготовки поверхностей.\n\nЧто из этого следует: экономия на подготовительных работах ведет к удорожанию в 2-3 раза на этапе отделки.\n\nКак избежать типичных ошибок при ремонте?\n\n#ремонт #технологии #советы",
                    "Можно ли сэкономить на строительных материалах без потери качества? Эксперты с большим стажем отмечают: разумная экономия возможна при грамотном планировании и выборе альтернативных материалов с аналогичными характеристиками.\n\nВ результате: профессиональный расчет материалов позволяет снизить стоимость на 15-20% без ущерба качеству.\n\nКак вы выбираете материалы для объекта?\n\n#строительство #материалы #экономия"
                ]
            },
            "PR и коммуникации": {
                "telegram": [
                    "🌅 Доброе утро! Первые впечатления важны в коммуникациях. Как ваш бренд выглядит со стороны?\n\n🎯 Важно: consistency в сообщениях строит доверие.\n\n📋 Шаги: 1) Анализ аудитории, 2) Ключевые сообщения, 3) Подходящие каналы.\n\nКак вы проверяете восприятие вашего бренда?\n\n#PR #коммуникации #бренд",
                    "🌞 Время для анализа медиаактивности. Что говорят о вашей компании в сети? Мониторинг упоминаний помогает вовремя реагировать.\n\n💡 Совет: настройте алерты по ключевым словам.\n\n⚡ Действие: проанализируйте последнюю неделю упоминаний.\n\nКакие инструменты мониторинга вы используете?\n\n#медиа #аналитика #PR"
                ],
                "zen": [
                    "Почему некоторые компании становятся медиа-героями, а другие остаются незамеченными? Секрет в стратегии storytelling. Как отмечают специалисты: истории, а не факты, вызывают эмоциональный отклик аудитории.\n\nТаким образом: трансформация сухих данных в нарратив увеличивает вовлеченность на 300%.\n\nКак создавать истории вокруг вашего бренда?\n\n#сторителлинг #PR #бренд",
                    "Кризис в соцсетях: как не потерять лицо компании? Профессионалы в этой сфере сходятся во мнении: скорость и искренность реакции важнее безупречности формулировок. В профессиональной среде считается: первые 60 минут определяют развитие ситуации.\n\nВывод: подготовленный план действий в кризисной ситуации экономит репутацию.\n\nЕсть ли у вас антикризисный протокол?\n\n#кризис #репутация #соцсети"
                ]
            }
        }
    
    def generate_fallback_post(self, theme: str, post_type: str) -> str:
        """Генерирует резервный пост"""
        theme_templates = self.templates.get(theme, {})
        type_templates = theme_templates.get(post_type, [])
        
        if type_templates:
            return random.choice(type_templates)
        
        # Универсальный шаблон
        if post_type == "telegram":
            return "🌅 Важная тема для обсуждения. Практический опыт показывает, что системный подход дает лучшие результаты.\n\n🎯 Важно: начинайте с анализа текущей ситуации.\n\n📋 Шаги: 1) Изучите проблему, 2) Составьте план, 3) Действуйте последовательно.\n\nКак вы решаете подобные задачи?\n\n#советы #бизнес #развитие"
        else:
            return "Актуальный вопрос для профессионалов. Эксперты отмечают важность комплексного подхода к решению задач. По отраслевой практике: глубокий анализ и поэтапная реализация обеспечивают стабильный результат.\n\nМнение экспертов: инвестиции в системность окупаются многократно в долгосрочной перспективе.\n\nКакой подход вы считаете наиболее эффективным?\n\n#экспертиза #анализ #результат"


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
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
            "max_output_tokens": 1100
        },
        "15:00": {
            "name": "Дневной пост",
            "type": "day",
            "emoji": "🌞",
            "style": "рациональность и аналитика: наблюдение, разбор явления, микро1исследование",
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
            "max_output_tokens": 1350
        },
        "20:00": {
            "name": "Вечерний пост",
            "type": "evening",
            "emoji": "🌙",
            "style": "глубина и история: личный взгляд, мини1история, аналогия",
            "tg_chars": (600, 900),  # Обновлено
            "zen_chars": (800, 1200),  # Обновлено
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
        self.quality_monitor = QualityMonitor()
        self.fallback_generator = FallbackGenerator()
        
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
        tg_min, tg_max = 600, 900  # Обновленные лимиты
        zen_min, zen_max = 800, 1200  # Обновленные лимиты
        
        # Динамические временные правила
        now_hour = self.get_moscow_time().hour
        if 5 <= now_hour < 12:
            time_rules = "СТРОГОЕ ПРАВИЛО: Пост должен начинаться с утреннего приветствия: 'Доброе утро', 'Начало дня', 'Старт утра'. Запрещены любые вечерние или дневные приветствия."
        elif 12 <= now_hour < 18:
            time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние ('Доброе утро') и вечерние ('Добрый вечер') приветствия. Только нейтральный деловой или информационный тон без привязки ко времени суток."
        elif 18 <= now_hour < 23:
            time_rules = "СТРОГОЕ ПРАВИЛО: Запрещены утренние приветствия ('Доброе утро'). Можно использовать: 'Добрый вечер', 'В завершение дня', 'Подводя итоги'. Только спокойный рефлексивный тон."
        else:
            time_rules = "СТРОГОЕ ПРАВИЛО: Используйте нейтральные приветствия без привязки ко времени суток: 'Здравствуйте', 'Приветствую', 'Доброго времени суток'."
        
        # Тематически-зависимые правила работы
        work_mentions = TextPostProcessor.THEME_SPECIFIC_RULES.get(theme, {})
        allowed_work = work_mentions.get("allowed_work_mentions", ["офисная работа"])
        disallowed_work = work_mentions.get("disallowed_work_mentions", [])
        
        allowed_text = "РАЗРЕШЕНО УПОМИНАТЬ:\n" + "\n".join(f"• {work}" for work in allowed_work)
        disallowed_text = "ЗАПРЕЩЕНО УПОМИНАТЬ:\n" + "\n".join(f"• {work}" for work in disallowed_work)
        
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

🚫 {disallowed_text}

✅ {allowed_text}

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
• Практический блок с конкретными действиями (используй разнообразные маркеры: {', '.join(TextPostProcessor.PRACTICE_MARKERS[:5])})
• Вопрос для вовлечения аудитории
• 3-5 релевантных хештегов в конце
• Объём: {tg_min}-{tg_max} символов (ОБЯЗАТЕЛЬНО!)

ТРЕБОВАНИЯ К ZEN ПОСТУ:
• Начало: провокационный вопрос или утверждение ("крючок-убийца")
• Основная часть: глубина анализа, экспертные мнения
• Завершение: естественный вывод (можно использовать разнообразные маркеры: {', '.join(TextPostProcessor.CONCLUSION_MARKERS[:5])})
• Вопрос для обсуждения
• 3-5 релевантных хештегов в конце
• Объём: {zen_min}-{zen_max} символов (ОБЯЗАТЕЛЬНО!)

🖼️ КАРТИНКА: {image_description}

🚫 ЗАПРЕЩЕНО В ТЕКСТЕ:
• Использовать формулировки от первого лица о личном опыте
• Шаблонные фразы, которые звучат как ИИ
• Писать "вот текст для Telegram/Дзен"
• Указывать "тема: {theme}" в тексте

✅ ОБЯЗАТЕЛЬНО В ТЕКСТЕ:
• Естественный человеческий язык
• Практическая польза
• Уникальность каждого поста
• Соблюдение лимитов символов
• Телеграм пост начинается с эмодзи {slot_style['emoji']}
• Дзен пост начинается без эмодзи

📝 ФОРМАТ ВЫВОДА:
• Сначала Telegram версия (полностью по шаблону с эмодзи)
• Потом Дзен версия (полностью по шаблону «Крючок-убийца» без эмодзи)
• Разделитель: три дефиса (---)
• БЕЗ ЛИШНИХ КОММЕНТАРИЕВ
• ТОЛЬКО ЧИСТЫЙ ТЕКСТ ГОТОВЫХ ПОСТОВ

Создай два РАЗНЫХ текста по одной теме, СТРОГО следуя всем правилам выше."""
        
        return prompt
    
    def parse_generated_texts(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Парсит сгенерированные тексты с умным разделением"""
        if not text:
            return None, None
        
        # Множество разделителей
        separators = ["\n---\n", "\n***\n", "\n###\n", "\n––––\n"]
        
        # Пробуем каждый разделитель
        for separator in separators:
            if separator in text:
                parts = text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].strip()
                    zen_text = parts[1].strip()
                    
                    # Базовая валидация
                    if len(tg_text) > 100 and len(zen_text) > 100:
                        return tg_text, zen_text
        
        # ML-подход: ищем смену стиля по эмодзи в начале
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Ищем первую строку без эмодзи (предположительно начало Zen)
        for i, line in enumerate(lines):
            if i > 0 and not re.search(r'[🌅🌞🌙🎯📋🔧💡⚡📝✅🎓🛠️🚀]', line[:10]):
                tg_text = '\n'.join(lines[:i]).strip()
                zen_text = '\n'.join(lines[i:]).strip()
                
                if len(tg_text) > 100 and len(zen_text) > 100:
                    return tg_text, zen_text
        
        # Fallback: разделяем пополам
        half = len(lines) // 2
        tg_text = '\n'.join(lines[:half]).strip()
        zen_text = '\n'.join(lines[half:]).strip()
        
        if len(tg_text) > 100 and len(zen_text) > 100:
            return tg_text, zen_text
        
        # Если все еще не удалось - отправляем уведомление
        logger.error("❌ Не удалось распарсить сгенерированный текст")
        self.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="⚠️ <b>ПРОБЛЕМА ПАРСИНГА</b>\n\nНе удалось распарсить сгенерированный текст. Использую резервные шаблоны.",
            parse_mode='HTML'
        )
        
        return None, None
    
    def generate_with_retry(self, prompt: str, tg_min: int, tg_max: int, zen_min: int, zen_max: int, 
                           max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Генерация с повторными попытками и fallback"""
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
        
        logger.error("❌ Все попытки генерации провалились, использую fallback")
        
        # Используем резервные шаблоны
        tg_fallback = self.fallback_generator.generate_fallback_post(self.current_theme, 'telegram')
        zen_fallback = self.fallback_generator.generate_fallback_post(self.current_theme, 'zen')
        
        # Отправляем уведомление
        self.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ <b>ИСПОЛЬЗОВАН FALLBACK</b>\n\nГенерация поста для темы '{self.current_theme}' не удалась после {max_attempts} попыток. Использованы резервные шаблоны.",
            parse_mode='HTML'
        )
        
        return tg_fallback, zen_fallback
    
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
            
            # Отслеживаем качество
            self.quality_monitor.track_post(post_data)
            
            # Проверяем среднюю длину
            if not self.quality_monitor.check_avg_post_length(post_data.get('type', ''), len(post_data.get('text', ''))):
                self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\nДлина {post_data.get('type', '')} поста ({len(post_data.get('text', ''))}) выходит за целевые пределы.",
                    parse_mode='HTML'
                )
            
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
            
            # Ночная зона: 23:00-04:59 → Нейтральный слот
            if hour >= 23 or hour < 5:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            # Утренняя зона: 05:00-10:59 → Утренний слот
            if hour >= 5 and hour < 11:
                return "11:00", self.TIME_STYLES.get("11:00")
            
            # Дневная зона: 11:00-14:59 → Дневной слот
            if hour >= 11 and hour < 15:
                return "15:00", self.TIME_STYLES.get("15:00")
            
            # Вечерняя зона: 15:00-22:59 → Вечерний слот
            return "20:00", self.TIME_STYLES.get("20:00")
            
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
                instruction = (f"<b>✅ ПОСТЫ ОТПРАВЛЕНЫ НА МОДЕРАЦИЮ</b>\n\n"
                              f"<b>📱 Telegram пост</b>\n"
                              f"   Канал: {MAIN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(tg_text)}\n\n"
                              f"<b>📝 Дзен пост</b>\n"
                              f"   Канал: {ZEN_CHANNEL}\n"
                              f"   Время: {slot_time} МСК\n"
                              f"   Символов: {len(zen_text)}\n\n"
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
            
            # Создаем промпт
            prompt = self.create_detailed_prompt(theme, slot_style, text_format, image_description)
            if not prompt:
                return False
            
            # Генерируем посты
            tg_min, tg_max = 600, 900
            zen_min, zen_max = 800, 1200
            
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
                
                # Проверяем качество
                self.quality_monitor.alert_if_needed(self.bot)
                
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
