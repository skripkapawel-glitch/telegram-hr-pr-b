# github_bot.py - Telegram бот с согласованием через "ок"
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
        
        # Доступные модели Gemini
        self.available_models = [
            "gemini-2.5-flash-preview-04-17",
            "gemini-2.5-pro-exp-03-25",
            "gemma-3-27b-it",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest"
        ]

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
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")

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
        except Exception as e:
            logger.error(f"❌ Ошибка отметки слота: {e}")

    def send_telegram_message(self, chat_id, text, image_url=None):
        """Отправляет сообщение в Telegram"""
        try:
            # Очищаем текст от артефактов
            text = self.clean_text(text)
            
            if image_url:
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': text[:1024],
                    'parse_mode': 'HTML',
                    'disable_notification': False
                }
                
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        return result['result']['message_id']
            
            # Если без картинки или картинка не отправилась
            params = {
                'chat_id': chat_id,
                'text': text[:4096],
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
                'disable_notification': False
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    return result['result']['message_id']
            
            logger.error(f"❌ Ошибка отправки в {chat_id}: {response.text if response else 'No response'}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return None

    def clean_text(self, text):
        """Очищает текст от артефактов"""
        if not text:
            return ""
        
        # Убираем начальные и конечные квадратные скобки
        text = re.sub(r'^\[+\s*', '', text)
        text = re.sub(r'\s*\]+$', '', text)
        
        # Убираем метки TG:/DZEN:
        text = re.sub(r'^(TG|DZEN|Telegram|Дзен):\s*', '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def get_post_image(self, theme):
        """Находит релевантную картинку для поста"""
        try:
            # Запросы для разных тем
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "home", "tools"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting", "recruitment"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social media", "public relations"]
            }
            
            queries = theme_queries.get(theme, ["business", "success", "work"])
            query = random.choice(queries)
            encoded_query = quote_plus(query)
            
            # Пробуем разные сервисы
            services = [
                f"https://source.unsplash.com/featured/1200x630/?{encoded_query}",
                f"https://source.unsplash.com/1200x630/?{encoded_query}",
                f"https://picsum.photos/1200/630?random=1",
                f"https://images.unsplash.com/photo-{random.randint(1500000000, 1700000000)}?w=1200&h=630&fit=crop"
            ]
            
            for url in services:
                try:
                    response = requests.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        logger.info(f"🖼️ Картинка найдена: {url[:50]}...")
                        return response.url
                except:
                    continue
            
            # Дефолтная картинка
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка поиска картинки: {e}")
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API (пробует все доступные модели)"""
        for model_name in self.available_models:
            try:
                logger.info(f"🤖 Пробуем модель: {model_name}")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topP": 0.95,
                        "maxOutputTokens": 4000
                    }
                }
                
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                        logger.info(f"✅ Текст сгенерирован моделью {model_name}")
                        logger.info(f"📊 Длина текста: {len(generated_text)} символов")
                        return generated_text, model_name
                else:
                    logger.warning(f"⚠️ Модель {model_name} недоступна: {response.status_code}")
                    if response.status_code == 400:
                        logger.warning(f"Детали: {response.text[:200]}")
                        
            except Exception as e:
                logger.warning(f"⚠️ Ошибка с моделью {model_name}: {str(e)[:100]}")
                continue
        
        logger.error("❌ Все модели недоступны")
        return None, None

    def generate_post(self, slot_time, slot_info):
        """Генерирует пост через Gemini"""
        try:
            theme = random.choice(self.themes)
            text_format = random.choice(self.text_formats)
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            # ПРАВИЛЬНЫЙ промпт
            prompt = f"""Создай ДВА РАЗНЫХ текста для социальных сетей.

ТЕМА: {theme}
ФОРМАТ ПОДАЧИ: {text_format}

══ TELEGRAM (канал: {MAIN_CHANNEL_ID}) ══
• Объем: {tg_min}-{tg_max} символов
• СТИЛЬ: Живой, динамичный, ИСПОЛЬЗУЙ ЭМОДЗИ {slot_info['emoji']} в тексте
• Обязательно: Хештеги в конце (5-7 штук)

══ ЯНДЕКС.ДЗЕН (канал: {ZEN_CHANNEL_ID}) ══  
• Объем: {zen_min}-{zen_max} символов
• СТИЛЬ: Аналитический, глубокий, НИКАКИХ ЭМОДЗИ
• Обязательно: Без хештегов, без эмодзи

ВАЖНО:
1. Telegram - с эмодзи, живой, с хештегами
2. Дзен - без эмодзи, аналитический, без хештегов
3. Тексты должны быть РАЗНЫЕ
4. Не используй квадратные скобки [ ] в начале или конце

Формат вывода:
TG: [текст для Telegram]
---
DZEN: [текст для Яндекс.Дзен]"""
            
            # Генерируем текст
            generated_text, model_used = self.generate_with_gemini(prompt)
            
            if not generated_text:
                return None
            
            # Разделяем текст
            tg_text_raw, zen_text_raw = None, None
            
            if "---" in generated_text:
                parts = generated_text.split("---", 1)
                tg_text_raw = parts[0].strip()
                zen_text_raw = parts[1].strip()
            else:
                # Если нет разделителя
                tg_text_raw = generated_text.strip()
                zen_text_raw = generated_text.strip()
            
            # Очищаем тексты
            tg_text = self.clean_text(tg_text_raw)
            zen_text = self.clean_text(zen_text_raw)
            
            # Убираем эмодзи из Дзен текста
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"  # emoticons
                u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                u"\U0001F680-\U0001F6FF"  # transport & map symbols
                u"\U0001F1E0-\U0001F1FF"  # flags
                u"\U00002700-\U000027BF"  # Dingbats
                "]+", flags=re.UNICODE)
            
            zen_text = emoji_pattern.sub(r'', zen_text)
            
            # Убираем хештеги из Дзен
            zen_text = re.sub(r'#\w+', '', zen_text)
            
            # Получаем картинку
            image_url = self.get_post_image(theme)
            
            if tg_text and zen_text and len(tg_text) > 50 and len(zen_text) > 50:
                return {
                    "theme": theme,
                    "format": text_format,
                    "tg_text": tg_text,
                    "zen_text": zen_text,
                    "image_url": image_url,
                    "slot_time": slot_time,
                    "slot_info": slot_info,
                    "model_used": model_used
                }
            else:
                logger.error("❌ Тексты пустые или слишком короткие")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации поста: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def send_for_approval(self, post_data):
        """Отправляет пост админу для согласования"""
        try:
            post_id = f"post_{int(time.time())}_{random.randint(100, 999)}"
            
            logger.info(f"📨 Отправляю пост на согласование (ID: {post_id})")
            
            # Отправляем Telegram пост админу
            message_id = self.send_telegram_message(
                ADMIN_CHAT_ID, 
                post_data["tg_text"], 
                post_data["image_url"]
            )
            
            if not message_id:
                logger.error("❌ Не удалось отправить пост админу")
                return False
            
            # Сохраняем пост
            post_data["admin_message_id"] = message_id
            post_data["created_at"] = datetime.now().isoformat()
            post_data["status"] = "pending"
            
            self.pending_posts[post_id] = post_data
            self.save_all_data()
            
            # Отправляем подсказку
            hint = f"📝 <b>Этот пост будет опубликован в двух каналах:</b>\n\n• <b>Telegram</b> ({MAIN_CHANNEL_ID}) - с эмодзи\n• <b>Яндекс.Дзен</b> ({ZEN_CHANNEL_ID}) - без эмодзи\n\n💬 <b>Ответьте 'ок' на этот пост для публикации</b>"
            self.send_telegram_message(ADMIN_CHAT_ID, hint)
            
            logger.info(f"✅ Пост отправлен админу (ID: {post_id}, сообщение: {message_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки на согласование: {e}")
            return False

    def check_admin_replies(self):
        """Проверяет, не ответил ли админ 'ок' на посты"""
        try:
            if not self.pending_posts:
                logger.info("📭 Нет постов на согласовании")
                return True
            
            # Получаем последние обновления
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10&offset=-50"
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"❌ Ошибка getUpdates: {response.status_code}")
                return False
            
            updates = response.json().get("result", [])
            logger.info(f"📥 Получено обновлений: {len(updates)}")
            
            for update in updates:
                if "message" in update:
                    msg = update["message"]
                    
                    # Проверяем что это от админа
                    if str(msg.get("from", {}).get("id")) != ADMIN_CHAT_ID:
                        continue
                    
                    # Проверяем что есть текст и reply
                    if "text" not in msg or "reply_to_message" not in msg:
                        continue
                    
                    reply_text = msg["text"].strip().lower()
                    replied_msg_id = msg["reply_to_message"]["message_id"]
                    
                    logger.info(f"🔍 Найден ответ админа: '{reply_text}' на сообщение {replied_msg_id}")
                    
                    # Ищем пост по message_id
                    for post_id, post_data in list(self.pending_posts.items()):
                        if post_data.get("admin_message_id") == replied_msg_id:
                            # Проверяем ключевые слова
                            approve_words = ["ок", "ok", "окей", "okay", "да", "yes", "👍", "✅", "го", "публикуй", "publish"]
                            reject_words = ["нет", "no", "не надо", "отмена", "❌", "👎", "отклонить", "reject"]
                            
                            if any(word in reply_text for word in approve_words):
                                logger.info(f"✅ Админ одобрил пост {post_id}")
                                return self.publish_post(post_id)
                            
                            elif any(word in reply_text for word in reject_words):
                                logger.info(f"❌ Админ отклонил пост {post_id}")
                                del self.pending_posts[post_id]
                                self.save_all_data()
                                self.send_telegram_message(ADMIN_CHAT_ID, f"❌ Пост отклонен")
                                return True
            
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ответов: {e}")
            return False

    def publish_post(self, post_id):
        """Публикует пост в два канала"""
        try:
            if post_id not in self.pending_posts:
                logger.error(f"❌ Пост {post_id} не найден")
                return False
            
            post = self.pending_posts[post_id]
            
            logger.info(f"📤 Публикую пост {post_id}...")
            
            # Публикуем в Telegram канал
            logger.info(f"   📢 Публикую в Telegram: {MAIN_CHANNEL_ID}")
            success_tg = self.send_telegram_message(MAIN_CHANNEL_ID, post["tg_text"], post["image_url"])
            time.sleep(2)
            
            # Публикуем в Яндекс.Дзен канал
            logger.info(f"   📢 Публикую в Яндекс.Дзен: {ZEN_CHANNEL_ID}")
            success_zen = self.send_telegram_message(ZEN_CHANNEL_ID, post["zen_text"], post["image_url"])
            
            # Перемещаем из pending в published
            post["published_at"] = datetime.now().isoformat()
            post["status"] = "published"
            post["tg_success"] = success_tg is not None
            post["zen_success"] = success_zen is not None
            
            self.published_posts[post_id] = post
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
            
            logger.info(f"✅ Пост {post_id} опубликован (TG: {success_tg is not None}, Дзен: {success_zen is not None})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_hour = now.hour
        
        print(f"\n🔄 Запуск в {now.strftime('%H:%M')} МСК")
        
        # 1. Проверяем ответы админа
        print("🔍 Проверяю ответы админа на старые посты...")
        self.check_admin_replies()
        
        # 2. Определяем слот
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Слот: {slot_time} - {slot_info['name']}")
        
        # 3. Проверяем, не отправляли ли уже сегодня
        if self.was_slot_sent_today(slot_time):
            print(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
            return True
        
        # 4. Генерируем пост
        print(f"🎬 Генерирую пост...")
        post_data = self.generate_post(slot_time, slot_info)
        
        if not post_data:
            print(f"❌ Не удалось сгенерировать пост")
            return False
        
        print(f"✅ Пост сгенерирован:")
        print(f"   🎯 Тема: {post_data['theme']}")
        print(f"   📝 Формат: {post_data['format']}")
        print(f"   🤖 Модель: {post_data.get('model_used', 'неизвестно')}")
        print(f"   📊 TG текст: {len(post_data['tg_text'])} символов")
        print(f"   📊 Дзен текст: {len(post_data['zen_text'])} символов")
        
        # 5. Отправляем на согласование
        success = self.send_for_approval(post_data)
        
        if success:
            print(f"✅ Пост отправлен на согласование")
            print(f"   👉 Ответьте 'ок' в личке с ботом для публикации")
        else:
            print(f"❌ Ошибка отправки на согласование")
        
        return success

    def run_test_mode(self):
        """Тестовый режим"""
        print("\n" + "=" * 80)
        print("🧪 ТЕСТОВЫЙ РЕЖИМ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Текущее время МСК: {now.strftime('%H:%M:%S')}")
        
        current_hour = now.hour
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📝 Тестовый пост для {slot_time}")
        
        # Генерируем пост (но не отправляем)
        post_data = self.generate_post(slot_time, slot_info)
        
        if post_data:
            print(f"✅ Тест успешен!")
            print(f"   🎯 Тема: {post_data['theme']}")
            print(f"   📝 Формат: {post_data['format']}")
            print(f"   🤖 Модель: {post_data.get('model_used', 'неизвестно')}")
            print(f"\n📄 Telegram текст (первые 200 символов):")
            print(f"{post_data['tg_text'][:200]}...")
            print(f"\n📄 Яндекс.Дзен текст (первые 200 символов):")
            print(f"{post_data['zen_text'][:200]}...")
            print(f"\n🖼️ Картинка: {post_data['image_url']}")
            return True
        else:
            print(f"❌ Тест провален")
            return False


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Telegram бот для публикации постов')
    parser.add_argument('--once', action='store_true', help='Однократный запуск (для GitHub Actions)')
    parser.add_argument('--test', action='store_true', help='Тестовый режим (показать логику)')
    parser.add_argument('--check', action='store_true', help='Только проверить ответы админа')
    
    args = parser.parse_args()
    
    bot = TelegramBot()
    
    if args.check:
        print("🔍 Проверяю ответы админа...")
        bot.check_admin_replies()
        print("✅ Проверка завершена")
    
    elif args.once:
        success = bot.run_once_mode()
        if not success:
            sys.exit(1)
    
    elif args.test:
        bot.run_test_mode()
    
    else:
        print("\n📖 КОМАНДЫ:")
        print("python github_bot.py --once    # Для GitHub Actions")
        print("python github_bot.py --test    # Проверить логику")
        print("python github_bot.py --check   # Проверить ответы админа")
        print("\n🎯 КАК РАБОТАЕТ:")
        print("1. Бот генерирует ДВА разных текста:")
        print("   • Telegram: с эмодзи, с хештегами")
        print("   • Яндекс.Дзен: без эмодзи, аналитический")
        print("2. Присылает вам Telegram-версию")
        print("3. Вы отвечаете 'ок' НА СООБЩЕНИЕ")
        print("4. Бот публикует ОБА текста в нужные каналы")


if __name__ == "__main__":
    main()
