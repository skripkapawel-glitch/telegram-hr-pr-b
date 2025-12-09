# github_bot.py - ФИНАЛЬНЫЙ ВАРИАНТ с правильной логикой
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установлен!")
    sys.exit(1)

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: ОТВЕТЬ 'ОК' ДЛЯ ПУБЛИКАЦИИ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установлен")
print(f"👨‍💼 Админ: {ADMIN_CHAT_ID}")
print(f"📢 Канал Telegram: {MAIN_CHANNEL_ID}")
print(f"📢 Канал Яндекс.Дзен: {ZEN_CHANNEL_ID}")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.posts_file = "bot_posts.json"
        
        # Загружаем или создаем файл
        if os.path.exists(self.posts_file):
            with open(self.posts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.pending_posts = data.get("pending", {})
                self.published_posts = data.get("published", {})
                self.history = data.get("history", {"sent_slots": {}, "last_post": None})
        else:
            self.pending_posts = {}
            self.published_posts = {}
            self.history = {"sent_slots": {}, "last_post": None}
            self.save_all_data()
        
        self.text_formats = [
            "разбор ситуации или явления",
            "микро-исследование (данные, цифры, вывод)",
            "аналитическое наблюдение",
            "разбор ошибки и решение",
            "мини-история с выводом",
            "взгляд автора + расширение темы",
            "объяснение сложного простым языком",
            "элементы сторителлинга",
            "структурированные советы",
            "объяснение через аналогию",
            "демонстрация пользы",
            "анализ поведения аудитории",
            "выявление причин «почему так происходит»",
            "логичная цепочка: факт → пример → вывод",
            "список полезных шагов",
            "раскрытие одного сильного инсайта",
            "тихая эмоциональная подача (без ярких эмоций)",
            "сравнение разных подходов",
            "мини-обобщение опыта"
        ]
        
        self.schedule = {
            "09:00": {"name": "Утренний", "emoji": "🌅", "tg_chars": (400, 600), "zen_chars": (1000, 1500)},
            "14:00": {"name": "Дневной", "emoji": "🌞", "tg_chars": (700, 900), "zen_chars": (700, 850)},
            "19:00": {"name": "Вечерний", "emoji": "🌙", "tg_chars": (600, 900), "zen_chars": (800, 900)}
        }

    def save_all_data(self):
        """Сохраняет ВСЕ данные в ОДИН файл"""
        try:
            data = {
                "pending": self.pending_posts,
                "published": self.published_posts,
                "history": self.history
            }
            with open(self.posts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_moscow_time(self):
        """Возвращает текущее время по Москве"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            sent_slots = self.history.get("sent_slots", {}).get(today, [])
            return slot_time in sent_slots
        except:
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if "sent_slots" not in self.history:
                self.history["sent_slots"] = {}
            
            if today not in self.history["sent_slots"]:
                self.history["sent_slots"][today] = []
            
            if slot_time not in self.history["sent_slots"][today]:
                self.history["sent_slots"][today].append(slot_time)
            
            self.save_all_data()
        except:
            pass

    def send_telegram_message(self, chat_id, text, image_url=None):
        """Отправляет сообщение в Telegram"""
        try:
            if image_url:
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': text[:1024],
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['result']['message_id'] if result.get('ok') else None
            
            # Если без картинки
            params = {
                'chat_id': chat_id,
                'text': text[:4096],
                'parse_mode': 'HTML'
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['result']['message_id'] if result.get('ok') else None
            
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return None

    def get_post_image(self, theme, service="unsplash"):
        """Находит релевантную картинку для поста (несколько сервисов)"""
        try:
            # Запросы для разных тем
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "home improvement", "tools"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting", "recruitment"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social media", "public relations"]
            }
            
            # Выбираем случайный запрос для темы
            queries = theme_queries.get(theme, ["business", "success", "work"])
            query = random.choice(queries)
            
            if service == "unsplash":
                # Unsplash - бесплатные фото
                width, height = 1200, 630
                
                # Несколько вариантов Unsplash
                unsplash_urls = [
                    f"https://source.unsplash.com/featured/{width}x{height}/?{query}",
                    f"https://source.unsplash.com/{width}x{height}/?{query}",
                    f"https://images.unsplash.com/photo-{random.randint(1500000000, 1700000000)}?w={width}&h={height}&fit=crop&q=80"
                ]
                
                for url in unsplash_urls:
                    try:
                        response = requests.head(url, timeout=5, allow_redirects=True)
                        if response.status_code == 200:
                            return response.url
                    except:
                        continue
                
                # Если Unsplash не сработал, пробуем Picsum
                try:
                    picsum_url = f"https://picsum.photos/{width}/{height}?random=1"
                    response = requests.head(picsum_url, timeout=5)
                    if response.status_code == 200:
                        return picsum_url
                except:
                    pass
                
            elif service == "pixabay":
                # Pixabay API (нужен ключ, но есть демо)
                try:
                    pixabay_url = f"https://pixabay.com/api/?key=your_key_here&q={query}&image_type=photo"
                    # Нужен API ключ, пропускаем если нет
                except:
                    pass
            
            # Дефолтная картинка
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop&q=80"
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка поиска картинки: {e}")
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop&q=80"

    def generate_post(self, slot_time, slot_info):
        """Генерирует пост через Gemini с ПРАВИЛЬНОЙ логикой"""
        try:
            theme = random.choice(self.themes)
            text_format = random.choice(self.text_formats)
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            # ПРАВИЛЬНЫЙ промпт - Telegram с эмодзи, Дзен без эмодзи
            prompt = f"""Создай ДВА РАЗНЫХ текста для социальных сетей.

ТЕМА: {theme}
ФОРМАТ ПОДАЧИ: {text_format}

══ TELEGRAM (канал: {MAIN_CHANNEL_ID}) ══
• Объем: {tg_min}-{tg_max} символов
• СТИЛЬ: Живой, динамичный, ИСПОЛЬЗУЙ ЭМОДЗИ {slot_info['emoji']} в тексте
• Формат: Короткие абзацы, отступы
• Обязательно: Хештеги в конце (5-7 штук)
• Пример хорошего поста:
  {slot_info['emoji']} Заголовок с эмодзи
  Короткий факт или наблюдение.
  Еще один абзац с мыслью.
  Вопрос для обсуждения в конце.
  
  #хештег1 #хештег2 #хештег3

══ ЯНДЕКС.ДЗЕН (канал: {ZEN_CHANNEL_ID}) ══  
• Объем: {zen_min}-{zen_max} символов
• СТИЛЬ: Аналитический, глубокий, НИКАКИХ ЭМОДЗИ
• Формат: Структурированный текст, как мини-статья
• Обязательно: Без хештегов, без эмодзи
• Пример хорошего поста:
  Введение в тему. Актуальность вопроса.
  
  Основная часть с анализом. Факты и данные.
  
  Практические выводы. Рекомендации.
  
  Заключение с итогами.

ВАЖНО:
1. Telegram - с эмодзи, живой, с хештегами
2. Дзен - без эмодзи, аналитический, без хештегов
3. Тексты должны быть РАЗНЫЕ, не копировать друг друга
4. Не используй квадратные скобки [ ] в начале или конце

Формат вывода:
TG: [текст для Telegram]
---
DZEN: [текст для Яндекс.Дзен]"""
            
            # Генерируем через Gemini
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 4000
                }
            }
            
            logger.info(f"🤖 Генерирую текст через Gemini...")
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # Разделяем текст
                    tg_text = ""
                    zen_text = ""
                    
                    if "---" in text:
                        parts = text.split("---", 1)
                        tg_text = parts[0].replace("TG:", "").replace("Telegram:", "").strip()
                        zen_text = parts[1].replace("DZEN:", "").replace("Дзен:", "").strip()
                    else:
                        # Если нет разделителя
                        tg_text = text.strip()
                        zen_text = text.strip()  # Дублируем, но это плохо
                    
                    # Очищаем от скобок
                    tg_text = re.sub(r'^\[|\]$', '', tg_text).strip()
                    zen_text = re.sub(r'^\[|\]$', '', zen_text).strip()
                    
                    # Убираем эмодзи из Дзен текста (на всякий случай)
                    emoji_pattern = re.compile("["
                        u"\U0001F600-\U0001F64F"  # emoticons
                        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                        u"\U0001F680-\U0001F6FF"  # transport & map symbols
                        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                        u"\U00002700-\U000027BF"  # Dingbats
                        u"\U000024C2-\U0001F251" 
                        "]+", flags=re.UNICODE)
                    
                    zen_text = emoji_pattern.sub(r'', zen_text)
                    
                    # Убираем хештеги из Дзен
                    zen_text = re.sub(r'#\w+', '', zen_text)
                    
                    # Получаем картинку
                    image_url = self.get_post_image(theme, service="unsplash")
                    
                    # Проверяем что тексты разные
                    if tg_text and zen_text and tg_text != zen_text:
                        return {
                            "theme": theme,
                            "format": text_format,
                            "tg_text": tg_text,
                            "zen_text": zen_text,
                            "image_url": image_url,
                            "slot_time": slot_time,
                            "slot_info": slot_info
                        }
                    else:
                        logger.error("❌ Тексты одинаковые или пустые")
                        return None
            
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return None

    def send_for_approval(self, post_data):
        """Отправляет пост админу для согласования"""
        try:
            post_id = f"post_{int(time.time())}_{random.randint(100, 999)}"
            
            # Отправляем ТОЛЬКО Telegram пост админу (чтобы показать как будет в TG)
            message_id = self.send_telegram_message(
                ADMIN_CHAT_ID, 
                post_data["tg_text"], 
                post_data["image_url"]
            )
            
            if message_id:
                # Сохраняем пост
                post_data["admin_message_id"] = message_id
                post_data["created_at"] = datetime.now().isoformat()
                post_data["status"] = "pending"
                
                self.pending_posts[post_id] = post_data
                self.save_all_data()
                
                # Отправляем подсказку
                hint = f"📝 <i>Этот пост будет опубликован в двух каналах:</i>\n\n• <b>Telegram</b> (@da4a_hr) - с эмодзи\n• <b>Яндекс.Дзен</b> (@tehdzenm) - без эмодзи\n\n💬 <b>Ответьте 'ок' для публикации</b>"
                self.send_telegram_message(ADMIN_CHAT_ID, hint)
                
                logger.info(f"✅ Пост отправлен админу (ID: {post_id})")
                return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки на согласование: {e}")
            return False

    def check_admin_replies(self):
        """Проверяет, не ответил ли админ 'ок' на посты"""
        try:
            if not self.pending_posts:
                return True
            
            # Получаем последние обновления
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-100"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                updates = response.json().get("result", [])
                
                for update in updates:
                    if "message" in update:
                        msg = update["message"]
                        
                        # Проверяем что это от админа и есть текст
                        if (str(msg.get("from", {}).get("id")) == ADMIN_CHAT_ID and 
                            "text" in msg and 
                            "reply_to_message" in msg):
                            
                            reply_text = msg["text"].strip().lower()
                            replied_msg_id = msg["reply_to_message"]["message_id"]
                            
                            # Ищем пост по message_id
                            for post_id, post_data in list(self.pending_posts.items()):
                                if post_data.get("admin_message_id") == replied_msg_id:
                                    # Проверяем ключевые слова
                                    if reply_text in ["ок", "ok", "окей", "okay", "да", "yes", "👍", "✅", "го", "публикуй", "publish"]:
                                        logger.info(f"✅ Админ одобрил пост {post_id}")
                                        self.publish_post(post_id)
                                        return True
                                    
                                    elif reply_text in ["нет", "no", "не надо", "отмена", "❌", "👎", "отклонить", "reject"]:
                                        logger.info(f"❌ Админ отклонил пост {post_id}")
                                        del self.pending_posts[post_id]
                                        self.save_all_data()
                                        
                                        # Уведомляем админа
                                        self.send_telegram_message(ADMIN_CHAT_ID, f"❌ Пост отклонен")
                                        return True
            
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ответов: {e}")
            return False

    def publish_post(self, post_id):
        """ПУБЛИКУЕТ ПОСТ В ДВА КАНАЛА с правильной логикой"""
        try:
            if post_id not in self.pending_posts:
                return False
            
            post = self.pending_posts[post_id]
            
            logger.info(f"📤 Публикую пост {post_id}...")
            
            # 1. Публикуем в Telegram канал (С ЭМОДЗИ, С ХЕШТЕГАМИ)
            logger.info(f"   📢 Telegram: {MAIN_CHANNEL_ID}")
            success_tg = self.send_telegram_message(MAIN_CHANNEL_ID, post["tg_text"], post["image_url"])
            time.sleep(2)
            
            # 2. Публикуем в Яндекс.Дзен канал (БЕЗ ЭМОДЗИ, БЕЗ ХЕШТЕГОВ)
            logger.info(f"   📢 Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            success_zen = self.send_telegram_message(ZEN_CHANNEL_ID, post["zen_text"], post["image_url"])
            
            # Перемещаем из pending в published
            self.published_posts[post_id] = {
                **post,
                "published_at": datetime.now().isoformat(),
                "status": "published",
                "tg_success": success_tg is not None,
                "zen_success": success_zen is not None,
                "tg_channel": MAIN_CHANNEL_ID,
                "zen_channel": ZEN_CHANNEL_ID
            }
            
            # Удаляем из pending
            del self.pending_posts[post_id]
            
            # Отмечаем слот как отправленный
            self.mark_slot_as_sent(post["slot_time"])
            
            # Сохраняем всё
            self.save_all_data()
            
            # Уведомляем админа
            if success_tg and success_zen:
                self.send_telegram_message(ADMIN_CHAT_ID, 
                    f"✅ Пост опубликован!\n\n"
                    f"📢 Telegram: {MAIN_CHANNEL_ID}\n"
                    f"📢 Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            elif success_tg or success_zen:
                self.send_telegram_message(ADMIN_CHAT_ID, 
                    f"⚠️ Частично опубликовано\n\n"
                    f"Telegram: {'✅' if success_tg else '❌'}\n"
                    f"Дзен: {'✅' if success_zen else '❌'}")
            else:
                self.send_telegram_message(ADMIN_CHAT_ID, "❌ Не удалось опубликовать")
            
            logger.info(f"✅ Пост {post_id} опубликован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False

    def create_and_send(self, slot_time, slot_info, is_test=False):
        """Создает и обрабатывает пост"""
        try:
            # Проверяем старые ответы
            self.check_admin_replies()
            
            # Проверяем, не отправляли ли уже сегодня
            if not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен")
                return True
            
            # Генерируем пост
            post_data = self.generate_post(slot_time, slot_info)
            if not post_data:
                logger.error("❌ Не удалось сгенерировать пост")
                return False
            
            logger.info(f"🎯 Тема: {post_data['theme']}")
            logger.info(f"📝 Формат: {post_data['format']}")
            
            # Проверяем логику
            logger.info(f"📊 Проверка текстов:")
            logger.info(f"   Telegram ({len(post_data['tg_text'])} chars): {post_data['tg_text'][:50]}...")
            logger.info(f"   Дзен ({len(post_data['zen_text'])} chars): {post_data['zen_text'][:50]}...")
            
            # Проверяем есть ли эмодзи
            import emoji
            tg_has_emoji = any(char in emoji.EMOJI_DATA for char in post_data['tg_text'])
            zen_has_emoji = any(char in emoji.EMOJI_DATA for char in post_data['zen_text'])
            
            logger.info(f"   Telegram имеет эмодзи: {tg_has_emoji}")
            logger.info(f"   Дзен имеет эмодзи: {zen_has_emoji} (должно быть False)")
            
            if is_test:
                # В тестовом режиме показываем что будет
                logger.info("🧪 ТЕСТ: Вот что будет отправлено:")
                logger.info(f"   В Telegram ({MAIN_CHANNEL_ID}):")
                logger.info(f"   {post_data['tg_text'][:100]}...")
                logger.info(f"   В Яндекс.Дзен ({ZEN_CHANNEL_ID}):")
                logger.info(f"   {post_data['zen_text'][:100]}...")
                return True
            else:
                # Отправляем на согласование
                return self.send_for_approval(post_data)
            
        except Exception as e:
            logger.error(f"💥 Ошибка: {e}")
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_hour = now.hour
        
        print(f"🔄 Запуск в {now.strftime('%H:%M')} МСК")
        
        # Сначала проверяем ответы админа
        print("🔍 Проверяю ответы админа на старые посты...")
        self.check_admin_replies()
        
        # Определяем слот
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Слот: {slot_time} - {slot_info['name']}")
        
        success = self.create_and_send(slot_time, slot_info, is_test=False)
        
        if success:
            print(f"✅ Пост отправлен на согласование")
            print(f"   👉 Ответьте 'ок' в личке с ботом для публикации")
        else:
            print(f"❌ Ошибка создания поста")
        
        return success

    def run_test_mode(self):
        """Тестовый режим"""
        print("\n🧪 ТЕСТОВЫЙ РЕЖИМ")
        
        now = self.get_moscow_time()
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        
        print(f"📝 Тестовый пост для {slot_time}")
        success = self.create_and_send(slot_time, slot_info, is_test=True)
        
        if success:
            print("✅ Тест успешен - логика правильная")
        else:
            print("❌ Тест провален")
        
        return success


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Telegram бот')
    parser.add_argument('--once', action='store_true', help='Для GitHub Actions')
    parser.add_argument('--test', action='store_true', help='Тестовый режим (показать логику)')
    parser.add_argument('--check', action='store_true', help='Только проверить ответы админа')
    
    args = parser.parse_args()
    
    bot = TelegramBot()
    
    if args.check:
        print("🔍 Проверяю ответы админа...")
        bot.check_admin_replies()
        print("✅ Проверка завершена")
    
    elif args.once:
        bot.run_once_mode()
    
    elif args.test:
        bot.run_test_mode()
    
    else:
        print("\n📖 КОМАНДЫ:")
        print("python github_bot.py --once    # Для GitHub Actions")
        print("python github_bot.py --test    # Проверить логику")
        print("python github_bot.py --check   # Проверить ответы админа")
        print("\n🎯 КАК РАБОТАЕТ:")
        print("1. Бот генерирует ДВА разных текста:")
        print("   • Telegram: с эмодзи, с хештегами, живой")
        print("   • Яндекс.Дзен: без эмодзи, аналитический")
        print("2. Присылает вам Telegram-версию")
        print("3. Вы отвечаете 'ок' НА СООБЩЕНИЕ")
        print("4. Бот публикует ОБА текста в нужные каналы")
        print("\n✅ Ключевые слова для публикации: ок, ok, да, yes, 👍, ✅")
        print("❌ Ключевые слова для отклонения: нет, no, не надо, ❌")


if __name__ == "__main__":
    main()
