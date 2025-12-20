[file name]: github_bot.py
[file content begin]
import os
import json
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
import telebot
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOPICS = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
CONTENT_FORMATS = [
    "разбор ошибки", "разбор ситуации", "микро исследование", "аналитическое наблюдение",
    "причинно следственные связки", "инсайт", "структурированные советы", "демонстрация пользы",
    "объяснение простым языком", "мини история", "взгляд автора", "аналогия", "мини обобщение опыта",
    "тихая эмоциональная подача", "сравнение подходов"
]

MORNING_FORMATS = ["структурированные советы", "демонстрация пользы", "объяснение простым языком", "мини обобщение опыта", "сравнение подходов"]
DAY_FORMATS = ["разбор ошибки", "разбор ситуации", "микро исследование", "аналитическое наблюдение", "причинно следственные связки", "инсайт"]
EVENING_FORMATS = ["мини история", "взгляд автора", "аналогия", "тихая эмоциональная подача", "МИНИ КЕЙС"]

RESERVE_HASHTAGS = {
    "HR и управление персоналом": [
        "#hr", "#hrменеджер", "#hrроссия", "#hrмосква", "#подборперсонала", "#рекрутинг",
        "#работа", "#работавмоскве", "#вакансии", "#вакансиимосква", "#карьера", "#карьерныйрост",
        "#поискработы", "#работарф", "#кадры", "#кадровик", "#персонал", "#управлениеперсоналом",
        "#мотивацияперсонала", "#корпоративнаякультура", "#hrбренд", "#обучениеперсонала",
        "#адаптацияперсонала", "#онбординг", "#оффер", "#найм", "#headhunting", "#hrсообщество",
        "#работодатель", "#рыноктруда"
    ],
    "PR и коммуникации": [
        "#pr", "#prменеджер", "#prроссия", "#prмосква", "#связиссобщественностью", "#медиа",
        "#бренд", "#брендинг", "#личныйбренд", "#репутация", "#управлениерепутацией", "#продвижение",
        "#коммуникации", "#маркетинг", "#контент", "#контентмаркетинг", "#инфоповод", "#публикации",
        "#сми", "#новости", "#пиаркампания", "#digitalpr", "#онлайнпродвижение", "#соцсети",
        "#медиапространство", "#имидж", "#брендстратегия", "#бизнессообщество", "#предпринимательство",
        "#экспертность"
    ],
    "ремонт и строительство": [
        "#ремонт", "#ремонтквартир", "#ремонтмосква", "#ремонтрф", "#отделка", "#отделкаподключ",
        "#черноваяотделка", "#чистоваяотделка", "#ремонтподключ", "#дизайнремонта", "#дизайнинтерьера",
        "#интерьер", "#квартиравмоскве", "#стройка", "#строительныеработы", "#электрика", "#сантехника",
        "#плитка", "#малярныеработы", "#ремонтванной", "#ремонткухни", "#новостройка", "#вторичка",
        "#капремонт", "#ремонтбезголовнойболи", "#ремонтдома", "#ремонтстудии", "#ремонтподключмосква",
        "#строительнаябригада", "#мастера", "#строительство", "#строительстводомов", "#строительствомосква",
        "#строительстворф", "#стройка2025", "#строительнаякомпания", "#строительныйбизнес",
        "#загородныйдом", "#домподключ", "#частныйдом", "#коттедж", "#фундамент", "#монолит",
        "#каркасныйдом", "#кирпичныйдом", "#проектирование", "#архитектура", "#генподрядчик",
        "#подрядчик", "#стройматериалы", "#стройконтроль", "#технадзор", "#инженерныесети",
        "#девелопмент", "#недвижимость", "#жилойкомплекс", "#строитель", "#объект", "#инфраструктура"
    ]
}

class PostStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    EXPIRED = "expired"

class TimeSlot(Enum):
    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"

@dataclass
class Post:
    id: str
    topic: str
    format: str
    telegram_text: str
    zen_text: str
    image_url: Optional[str] = None
    pexels_query: Optional[str] = None
    status: PostStatus = PostStatus.PENDING
    created_at: datetime = None
    moderated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    channel_message_id: Optional[int] = None
    zen_message_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if self.moderated_at:
            data['moderated_at'] = self.moderated_at.isoformat()
        if self.published_at:
            data['published_at'] = self.published_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data['status'] = PostStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('moderated_at'):
            data['moderated_at'] = datetime.fromisoformat(data['moderated_at'])
        if data.get('published_at'):
            data['published_at'] = datetime.fromisoformat(data['published_at'])
        return cls(**data)

class BotManager:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.channel_id = os.getenv('CHANNEL_ID', '@da4a_hr')
        self.zen_channel_id = os.getenv('ZEN_CHANNEL_ID', '@tehdzenm')
        self.admin_chat_id = os.getenv('ADMIN_CHAT_ID')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.pexels_api_key = os.getenv('PEXELS_API_KEY')
        
        if not self.bot_token or not self.gemini_api_key:
            raise ValueError("BOT_TOKEN and GEMINI_API_KEY must be set")
        
        self.bot = telebot.TeleBot(self.bot_token, parse_mode='HTML')
        self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        
        self.pending_posts: Dict[str, Post] = {}
        self.published_posts: Dict[str, Post] = {}
        
        self.history_file = Path("post_history.json")
        self.status_file = Path("status_cache.json")
        self.load_history()
    
    def load_history(self):
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for post_data in data.get('published', []):
                        post = Post.from_dict(post_data)
                        self.published_posts[post.id] = post
        except Exception as e:
            logger.error(f"Error loading history: {e}")
    
    def save_history(self):
        try:
            data = {
                'published': [post.to_dict() for post in self.published_posts.values()],
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def generate_post_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"{timestamp}_{random_suffix}"
    
    def get_current_time_slot(self) -> Tuple[TimeSlot, str]:
        now = datetime.now(timezone(timedelta(hours=3)))
        hour = now.hour
        
        if 11 <= hour < 15:
            return TimeSlot.MORNING, "11:00"
        elif 15 <= hour < 20:
            return TimeSlot.DAY, "15:00"
        else:
            return TimeSlot.EVENING, "20:00"
    
    def get_slot_char_limits(self, slot: TimeSlot) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        if slot == TimeSlot.MORNING:
            return (0, 600), (0, 700)
        elif slot == TimeSlot.DAY:
            return (0, 900), (0, 900)
        else:
            return (0, 900), (0, 800)
    
    def get_slot_formats(self, slot: TimeSlot) -> List[str]:
        if slot == TimeSlot.MORNING:
            return MORNING_FORMATS
        elif slot == TimeSlot.DAY:
            return DAY_FORMATS
        else:
            return EVENING_FORMATS
    
    def get_slot_greeting(self, slot: TimeSlot) -> str:
        if slot == TimeSlot.MORNING:
            return "Доброе утро"
        elif slot == TimeSlot.DAY:
            return ""
        else:
            return "Добрый вечер"
    
    def select_topic_and_format(self, slot: TimeSlot) -> Tuple[str, str]:
        topic = random.choice(TELEGRAM_TOPICS)
        available_formats = self.get_slot_formats(slot)
        content_format = random.choice(available_formats)
        return topic, content_format
    
    def build_gemini_prompt(self, topic: str, content_format: str, slot: TimeSlot, tg_min: int, tg_max: int, dz_min: int, dz_max: int) -> str:
        slot_name = slot.value
        greeting = self.get_slot_greeting(slot)
        
        prompt = f"""Создай два отдельных поста на тему "{topic}" в формате "{content_format}".

ТЕМА: {topic}
ФОРМАТ: {content_format}
ВРЕМЯ ПУБЛИКАЦИИ: {slot_name} ({greeting})

ТЕБЕ НУЖНО СОЗДАТЬ ДВА РАЗНЫХ ПОСТА:

1. ПОСТ ДЛЯ TELEGRAM:
   - Длина: ДО {tg_max} СИМВОЛОВ (ВКЛЮЧАЯ ХЕШТЕГИ)
   - Начинай с эмодзи + вопрос
   - Структура:
     1. Эмодзи + провокационный вопрос
     2. Основной текст (2-3 абзаца)
     3. Практический совет или кейс
     4. Инсайт или вывод
     5. Мягкий финал с вопросом к аудитории
     6. "ПОЛЕЗНЯШКА: [название статьи] - [ссылка]"
     7. Хештеги (3-5 релевантных)

2. ПОСТ ДЛЯ ДЗЕН:
   - Длина: ДО {dz_max} СИМВОЛОВ (ВКЛЮЧАЯ ХЕШТЕГИ)
   - Начинай с провокационного вопроса БЕЗ эмодзи
   - Структура:
     1. Провокационный вопрос (без эмодзи)
     2. Основной текст (более подробный, чем для Telegram)
     3. Конкретный пример из практики или кейс
     4. Блок "Почему это важно" или "Эксперты отмечают"
     5. "ПОЛЕЗНЯШКА: [название статьи] - [ссылка]"
     6. Мягкий финал с вопросом к аудитории
     7. Хештеги (3-5 релевантных)

ОБЩИЕ ПРАВИЛА:
- Не упоминай удалённую или гибридную работу
- Используй живые формулировки, как человек
- Чередуй короткие и длинные предложения
- Добавь 2-3 неидеальные формулировки (как в живой речи)
- Используй разговорные выражения
- Включи личные мнения ("на мой взгляд", "кажется мне")
- В Дзене используй "эксперты отмечают", "по опыту практиков"

ВАЖНО:
- Каждый пост должен быть ПОЛНОСТЬЮ ЗАВЕРШЁННЫМ
- Проверь длину КАЖДОГО поста перед отправкой
- Telegram: до {tg_max} символов
- Дзен: до {dz_max} символов

ВЫВЕДИ В ФОРМАТЕ:
[TELEGRAM]
полный текст поста для Telegram
[DZEN]
полный текст поста для Дзен

Без дополнительных комментариев, только два поста с маркерами."""

        return prompt
    
    def generate_content_with_retry(self, topic: str, content_format: str, slot: TimeSlot, max_attempts: int = 15) -> Optional[Tuple[str, str]]:
        tg_min, tg_max = self.get_slot_char_limits(slot)[0]
        dz_min, dz_max = self.get_slot_char_limits(slot)[1]
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 Попытка {attempt} из {max_attempts}")
                logger.info(f"Диапазоны: Telegram до {tg_max}, Дзен до {dz_max}")
                
                prompt = self.build_gemini_prompt(topic, content_format, slot, tg_min, tg_max, dz_min, dz_max)
                
                response = self.gemini_client.models.generate_content(
                    model='gemma-3-27b-it',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        top_p=0.8,
                        max_output_tokens=2000
                    )
                )
                
                text = response.text.strip()
                
                if '[TELEGRAM]' in text and '[DZEN]' in text:
                    # Извлекаем тексты
                    tg_start = text.find('[TELEGRAM]') + len('[TELEGRAM]')
                    tg_end = text.find('[DZEN]')
                    dz_start = text.find('[DZEN]') + len('[DZEN]')
                    
                    telegram_text = text[tg_start:tg_end].strip()
                    dz_text = text[dz_start:].strip()
                    
                    # Проверяем длину
                    tg_len = len(telegram_text)
                    dz_len = len(dz_text)
                    
                    logger.info(f"Telegram: {tg_len} символов, Дзен: {dz_len} символов")
                    
                    if tg_len <= tg_max and dz_len <= dz_max:
                        logger.info(f"✅ УСПЕХ на попытке {attempt}")
                        return telegram_text, dz_text
                    else:
                        logger.warning(f"❌ Длина вне диапазона. Пробуем снова...")
                        continue
                else:
                    logger.warning(f"❌ Нет маркеров [TELEGRAM] или [DZEN]")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                continue
        
        logger.error(f"🔥 Все {max_attempts} попыток провалились")
        return None
    
    def generate_content(self, topic: str, content_format: str, slot: TimeSlot) -> Optional[Tuple[str, str]]:
        return self.generate_content_with_retry(topic, content_format, slot, max_attempts=15)
    
    def search_pexels_image(self, query: str) -> Optional[str]:
        if not self.pexels_api_key:
            logger.warning("PEXELS_API_KEY not set, using default image")
            return None
            
        try:
            headers = {'Authorization': self.pexels_api_key}
            params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
            
            response = requests.get(
                'https://api.pexels.com/v1/search',
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos'):
                    return data['photos'][0]['src']['large']
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching Pexels: {e}")
            return None
    
    def create_moderation_keyboard(self, post_id: str):
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=3)
        
        keyboard.add(
            telebot.types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{post_id}"),
            telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post_id}")
        )
        
        keyboard.add(
            telebot.types.InlineKeyboardButton("📝 Текст", callback_data=f"regenerate_text_{post_id}"),
            telebot.types.InlineKeyboardButton("🖼️ Фото", callback_data=f"new_image_{post_id}"),
            telebot.types.InlineKeyboardButton("🔄 Всё", callback_data=f"regenerate_all_{post_id}")
        )
        
        keyboard.add(
            telebot.types.InlineKeyboardButton("⚡ Новое", callback_data=f"new_topic_{post_id}")
        )
        
        return keyboard
    
    def add_hashtags_if_missing(self, text: str, topic: str) -> str:
        if '#' not in text:
            hashtags = RESERVE_HASHTAGS.get(topic, [])
            if hashtags:
                random.shuffle(hashtags)
                selected = hashtags[:5]
                return f"{text}\n\n{' '.join(selected)}"
        return text
    
    def send_for_moderation(self, post: Post):
        try:
            tg_min, tg_max = self.get_slot_char_limits(self.get_current_time_slot()[0])[0]
            dz_min, dz_max = self.get_slot_char_limits(self.get_current_time_slot()[0])[1]
            
            caption = f"<b>НОВЫЙ ПОСТ ДЛЯ МОДЕРАЦИИ</b>\n\n"
            caption += f"<b>Тема:</b> {post.topic}\n"
            caption += f"<b>Формат:</b> {post.format}\n"
            caption += f"<b>ID:</b> <code>{post.id}</code>\n"
            caption += f"<b>Время слота:</b> {post.created_at.strftime('%H:%M')} МСК\n"
            caption += f"<b>Лимиты символов:</b> Telegram до {tg_max}, Дзен до {dz_max}\n"
            caption += f"<b>Фактически:</b> Telegram {len(post.telegram_text)} симв, Дзен {len(post.zen_text)} симв\n\n"
            caption += f"<b>Telegram:</b>\n<code>{post.telegram_text[:100]}...</code>\n\n"
            caption += f"<b>Дзен:</b>\n<code>{post.zen_text[:100]}...</code>"
            
            keyboard = self.create_moderation_keyboard(post.id)
            
            if post.image_url:
                self.bot.send_photo(
                    chat_id=self.admin_chat_id,
                    photo=post.image_url,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=caption,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            
            logger.info(f"Post {post.id} sent for moderation")
            
        except Exception as e:
            logger.error(f"Error sending for moderation: {e}")
    
    def publish_post(self, post: Post):
        try:
            tg_text = self.add_hashtags_if_missing(post.telegram_text, post.topic)
            dz_text = self.add_hashtags_if_missing(post.zen_text, post.topic)
            
            if post.image_url:
                tg_message = self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=post.image_url,
                    caption=tg_text,
                    parse_mode='HTML'
                )
                post.channel_message_id = tg_message.message_id
                
                dz_message = self.bot.send_photo(
                    chat_id=self.zen_channel_id,
                    photo=post.image_url,
                    caption=dz_text,
                    parse_mode='HTML'
                )
                post.zen_message_id = dz_message.message_id
            else:
                tg_message = self.bot.send_message(
                    chat_id=self.channel_id,
                    text=tg_text,
                    parse_mode='HTML'
                )
                post.channel_message_id = tg_message.message_id
                
                dz_message = self.bot.send_message(
                    chat_id=self.zen_channel_id,
                    text=dz_text,
                    parse_mode='HTML'
                )
                post.zen_message_id = dz_message.message_id
            
            post.status = PostStatus.PUBLISHED
            post.published_at = datetime.now(timezone.utc)
            self.published_posts[post.id] = post
            self.save_history()
            
            logger.info(f"✅ Post {post.id} published successfully")
            
            if self.admin_chat_id:
                self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"✅ Пост {post.id} опубликован\nTelegram: {len(post.telegram_text)} симв\nДзен: {len(post.zen_text)} симв",
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            if self.admin_chat_id:
                self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"❌ Ошибка публикации поста {post.id}: {str(e)}",
                    parse_mode='HTML'
                )
    
    def check_expired_posts(self):
        expired_posts = []
        now = datetime.now(timezone.utc)
        
        for post_id, post in list(self.pending_posts.items()):
            if post.status == PostStatus.PENDING:
                time_diff = now - post.created_at
                if time_diff.total_seconds() > 600:
                    post.status = PostStatus.EXPIRED
                    expired_posts.append(post_id)
                    logger.info(f"Post {post_id} expired (10 minutes timeout)")
        
        for post_id in expired_posts:
            self.pending_posts.pop(post_id, None)
        
        return len(expired_posts) > 0
    
    def process_callback(self, call):
        try:
            data = call.data
            post_id = data.split('_')[-1]
            
            post = self.pending_posts.get(post_id)
            if not post:
                self.bot.answer_callback_query(call.id, "Пост не найден или устарел")
                return
            
            if data.startswith('approve_'):
                post.status = PostStatus.APPROVED
                post.moderated_at = datetime.now(timezone.utc)
                
                self.publish_post(post)
                self.pending_posts.pop(post_id, None)
                
                self.bot.answer_callback_query(call.id, "Пост опубликован!")
                self.bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=None
                )
                
            elif data.startswith('reject_'):
                post.status = PostStatus.REJECTED
                post.moderated_at = datetime.now(timezone.utc)
                post.rejection_reason = "Отклонено администратором"
                
                self.pending_posts.pop(post_id, None)
                
                self.bot.answer_callback_query(call.id, "Пост отклонен")
                self.bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=None
                )
                
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=f"❌ Пост {post_id} отклонен",
                    parse_mode='HTML'
                )
            
            elif data.startswith('regenerate_text_'):
                self.bot.answer_callback_query(call.id, "Перегенерируем текст...")
                
                new_content = self.generate_content(post.topic, post.format, self.get_current_time_slot()[0])
                if new_content:
                    post.telegram_text, post.zen_text = new_content
                    self.send_for_moderation(post)
                    
                    self.bot.edit_message_reply_markup(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=None
                    )
                else:
                    self.bot.answer_callback_query(call.id, "Не удалось сгенерировать текст", show_alert=True)
            
            elif data.startswith('new_image_'):
                self.bot.answer_callback_query(call.id, "Ищем новое изображение...")
                
                new_image = self.search_pexels_image(post.pexels_query or post.topic)
                if new_image:
                    post.image_url = new_image
                    self.send_for_moderation(post)
                    
                    self.bot.edit_message_reply_markup(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=None
                    )
                else:
                    self.bot.answer_callback_query(call.id, "Не удалось найти изображение", show_alert=True)
            
            elif data.startswith('regenerate_all_'):
                self.bot.answer_callback_query(call.id, "Полная перегенерация...")
                
                slot = self.get_current_time_slot()[0]
                new_topic, new_format = self.select_topic_and_format(slot)
                new_content = self.generate_content(new_topic, new_format, slot)
                
                if new_content:
                    post.topic = new_topic
                    post.format = new_format
                    post.telegram_text, post.zen_text = new_content
                    
                    new_image = self.search_pexels_image(new_topic)
                    if new_image:
                        post.image_url = new_image
                    
                    self.send_for_moderation(post)
                    
                    self.bot.edit_message_reply_markup(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=None
                    )
                else:
                    self.bot.answer_callback_query(call.id, "Не удалось перегенерировать", show_alert=True)
            
            elif data.startswith('new_topic_'):
                self.bot.answer_callback_query(call.id, "Выбираем новую тему...")
                
                slot = self.get_current_time_slot()[0]
                new_topic, new_format = self.select_topic_and_format(slot)
                
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(
                    telebot.types.InlineKeyboardButton(f"✅ {new_topic}", callback_data=f"confirm_topic_{post.id}_{new_topic}_{new_format}")
                )
                
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=f"Новая тема: <b>{new_topic}</b>\nФормат: <b>{new_format}</b>\n\nПодтвердить?",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        
        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            self.bot.answer_callback_query(call.id, "Ошибка обработки")
    
    def run_auto_mode(self):
        try:
            slot, slot_time = self.get_current_time_slot()
            topic, content_format = self.select_topic_and_format(slot)
            
            logger.info(f"🚀 Начинаем генерацию для слота {slot.value} ({slot_time})")
            logger.info(f"Тема: {topic}, Формат: {content_format}")
            
            content = self.generate_content(topic, content_format, slot)
            if not content:
                logger.error("❌ Не удалось сгенерировать контент")
                return False
            
            telegram_text, dz_text = content
            
            post_id = self.generate_post_id()
            
            image_query = topic
            image_url = self.search_pexels_image(image_query)
            
            post = Post(
                id=post_id,
                topic=topic,
                format=content_format,
                telegram_text=telegram_text,
                zen_text=dz_text,
                image_url=image_url,
                pexels_query=image_query
            )
            
            self.pending_posts[post_id] = post
            
            if self.admin_chat_id:
                self.send_for_moderation(post)
                logger.info(f"📨 Пост {post.id} отправлен на модерацию")
                return True
            else:
                logger.warning("ADMIN_CHAT_ID not set, auto-publishing")
                self.publish_post(post)
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка в auto mode: {e}")
            return False
    
    def run_manual_mode(self):
        try:
            now = datetime.now(timezone(timedelta(hours=3)))
            current_hour = now.hour
            current_minute = now.minute
            
            next_slots = []
            
            if current_hour < 11 or (current_hour == 11 and current_minute < 5):
                next_slots.append(("11:00", TimeSlot.MORNING))
            
            if current_hour < 15 or (current_hour == 15 and current_minute < 5):
                next_slots.append(("15:00", TimeSlot.DAY))
            
            if current_hour < 20 or (current_hour == 20 and current_minute < 5):
                next_slots.append(("20:00", TimeSlot.EVENING))
            
            if not next_slots:
                logger.info("No upcoming slots within 10 minutes")
                return False
            
            next_time, next_slot = next_slots[0]
            
            logger.info(f"Manual mode: generating for next slot {next_time} ({next_slot.value})")
            
            topic, content_format = self.select_topic_and_format(next_slot)
            content = self.generate_content(topic, content_format, next_slot)
            
            if not content:
                logger.error("Failed to generate content with all models")
                return False
            
            telegram_text, dz_text = content
            
            post_id = self.generate_post_id()
            image_url = self.search_pexels_image(topic)
            
            post = Post(
                id=post_id,
                topic=topic,
                format=content_format,
                telegram_text=telegram_text,
                zen_text=dz_text,
                image_url=image_url,
                pexels_query=topic
            )
            
            self.pending_posts[post_id] = post
            
            if self.admin_chat_id:
                self.send_for_moderation(post)
                logger.info(f"Post {post_id} sent for moderation")
                return True
            else:
                logger.warning("ADMIN_CHAT_ID not set, auto-publishing")
                self.publish_post(post)
                return True
                
        except Exception as e:
            logger.error(f"Error in manual mode: {e}")
            return False
    
    def start_polling(self):
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.process_callback(call)
        
        logger.info("Starting bot polling...")
        self.bot.infinity_polling(timeout=60, long_polling_timeout=60)

def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Telegram Bot for automatic posting')
    parser.add_argument('--auto', action='store_true', help='Run in automatic mode (for scheduled runs)')
    args = parser.parse_args()
    
    try:
        bot_manager = BotManager()
        
        if args.auto:
            success = bot_manager.run_auto_mode()
            if success:
                logger.info("✅ Auto mode completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Auto mode failed")
                sys.exit(1)
        else:
            success = bot_manager.run_manual_mode()
            if success:
                logger.info("✅ Manual mode completed successfully")
                if os.getenv('GITHUB_ACTIONS'):
                    logger.info("GitHub Actions: Exiting after generation")
                    sys.exit(0)
                else:
                    logger.info("Starting polling for moderation...")
                    bot_manager.start_polling()
            else:
                logger.warning("No suitable time slot found for manual mode")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
[file content end]
