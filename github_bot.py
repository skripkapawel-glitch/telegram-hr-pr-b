# github_bot.py - Telegram бот с согласованием через ответ "ок"
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
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")  # Ваш ID из @userinfobot

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

if not ADMIN_CHAT_ID:
    logger.warning("⚠️ ADMIN_CHAT_ID не установлен - бот будет публиковать сразу")

APPROVAL_ENABLED = bool(ADMIN_CHAT_ID)  # Если есть ADMIN_CHAT_ID - включаем согласование

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: ПРОСТАЯ СИСТЕМА СОГЛАСОВАНИЯ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установлен")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
if ADMIN_CHAT_ID:
    print(f"👨‍💼 Админ для согласования: {ADMIN_CHAT_ID}")
    print(f"📝 Система: Отвечайте 'ок' на пост для публикации")
else:
    print(f"👨‍💼 Админ: Не установлен (публикация сразу)")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.pending_file = "pending_posts.json"
        self.reply_mapping_file = "reply_mapping.json"  # Связь reply_to_message_id -> post_id
        self.post_history = self.load_history()
        self.pending_posts = self.load_pending()
        self.reply_mapping = self.load_reply_mapping()
        
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
            "09:00": {"name": "Утренний пост", "emoji": "🌅", "tg_chars": (400, 600), "zen_chars": (1000, 1500)},
            "14:00": {"name": "Дневной пост", "emoji": "🌞", "tg_chars": (700, 900), "zen_chars": (700, 850)},
            "19:00": {"name": "Вечерний пост", "emoji": "🌙", "tg_chars": (600, 900), "zen_chars": (800, 900)}
        }
        
        # Ключевые слова для одобрения
        self.approve_keywords = ["ок", "ok", "окей", "okay", "👍", "✅", "да", "yes", "го", "публикуй", "публикуйся"]
        
        # Ключевые слова для отклонения
        self.reject_keywords = ["нет", "no", "не надо", "отмена", "отклоняю", "❌", "👎", "стоп"]

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {"sent_slots": {}, "last_post": None}
        return {"sent_slots": {}, "last_post": None}

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_pending(self):
        """Загружает посты на согласовании"""
        try:
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {}
        return {}

    def save_pending(self):
        """Сохраняет посты на согласовании"""
        try:
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                json.dump(self.pending_posts, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_reply_mapping(self):
        """Загружает связь reply_to_message_id -> post_id"""
        try:
            if os.path.exists(self.reply_mapping_file):
                with open(self.reply_mapping_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {}
        return {}

    def save_reply_mapping(self):
        """Сохраняет связь reply_to_message_id -> post_id"""
        try:
            with open(self.reply_mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.reply_mapping, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
            return slot_time in sent_slots
        except:
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if "sent_slots" not in self.post_history:
                self.post_history["sent_slots"] = {}
            
            if today not in self.post_history["sent_slots"]:
                self.post_history["sent_slots"][today] = []
            
            if slot_time not in self.post_history["sent_slots"][today]:
                self.post_history["sent_slots"][today].append(slot_time)
            
            self.save_history()
        except:
            pass

    def get_smart_theme(self):
        """Выбирает тему умным способом"""
        try:
            available_themes = self.themes.copy()
            return random.choice(available_themes)
        except:
            return random.choice(self.themes)

    def get_smart_format(self):
        """Выбирает формат подачи умным способом"""
        try:
            return random.choice(self.text_formats)
        except:
            return random.choice(self.text_formats)

    def create_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Gemini"""
        tg_min, tg_max = slot_info['tg_chars']
        zen_min, zen_max = slot_info['zen_chars']
        
        prompt = f"""Создай ДВА разных текста для Telegram и Яндекс.Дзен.

ТЕМА: {theme}
ФОРМАТ: {text_format}

══ TELEGRAM-ПОСТ ({MAIN_CHANNEL_ID}) ══
• Объем: {tg_min}-{tg_max} символов
• Стиль: Живой, динамичный, используй эмодзи {slot_info['emoji']}
• Структура: Хук → факт → вывод → вопрос
• Хештеги: 5-7 релевантных хештегов

══ ДЗЕН-ПОСТ ({ZEN_CHANNEL_ID}) ══  
• Объем: {zen_min}-{zen_max} символов
• Стиль: Глубокий, аналитический, БЕЗ ЭМОДЗИ
• Структура: Введение → разбор → анализ → итог

НЕ используй квадратные скобки [ ] в начале или конце текста!

Формат вывода:
TG: [текст Telegram-поста]
---
DZEN: [текст Дзен-поста]"""
        
        return prompt

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 4000
                }
            }
            
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return None

    def split_generated_text(self, combined_text):
        """Разделяет текст на Telegram и Дзен части"""
        if not combined_text:
            return None, None
        
        if "---" in combined_text:
            parts = combined_text.split("---", 1)
            tg_text = parts[0].replace("TG:", "").strip()
            zen_text = parts[1].replace("DZEN:", "").strip()
            return tg_text, zen_text
        
        text_length = len(combined_text)
        split_point = text_length // 2
        
        for i in range(split_point, min(split_point + 100, text_length - 1)):
            if combined_text[i] in ['.', '!', '?']:
                split_point = i + 1
                break
        
        return combined_text[:split_point].strip(), combined_text[split_point:].strip()

    def get_post_image(self, theme):
        """Находит картинку для поста"""
        try:
            theme_queries = {
                "ремонт и строительство": "construction+renovation+architecture+home",
                "HR и управление персоналом": "office+business+teamwork+meeting",
                "PR и коммуникации": "communication+marketing+networking+social+media"
            }
            
            query = theme_queries.get(theme, "business+success+work")
            encoded_query = quote_plus(query)
            
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = requests.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return response.url
            
        except:
            pass
        
        return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def clean_text(self, text):
        """Очищает текст от артефактов"""
        if not text:
            return ""
        
        text = re.sub(r'^\[+\s*', '', text)
        text = re.sub(r'\s*\]+$', '', text)
        text = re.sub(r'^(TG|DZEN|Telegram|Дзен):\s*', '', text, flags=re.IGNORECASE)
        return text.strip()

    def send_telegram_message(self, chat_id, text, image_url=None, reply_to_message_id=None):
        """Отправляет сообщение в Telegram"""
        try:
            text = self.clean_text(text)
            
            if image_url:
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': text[:1024],
                    'parse_mode': 'HTML'
                }
                
                if reply_to_message_id:
                    params['reply_to_message_id'] = reply_to_message_id
                
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['result']['message_id'] if result.get('ok') else None
            
            # Если без картинки или картинка не отправилась
            params = {
                'chat_id': chat_id,
                'text': text[:4096],
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            if reply_to_message_id:
                params['reply_to_message_id'] = reply_to_message_id
            
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

    def send_for_approval(self, post_id, slot_time, tg_text, zen_text, image_url, theme):
        """Отправляет пост на согласование - просто присылает пост как есть"""
        try:
            if not ADMIN_CHAT_ID:
                return False
            
            logger.info(f"📨 Отправляю пост {post_id} на согласование...")
            
            # Отправляем пост админу КАК БУДТО ЭТО УЖЕ ГОТОВЫЙ ПОСТ
            # Не говорим что это для согласования - просто присылаем готовый пост
            
            # 1. Сначала отправляем сам пост (как он будет выглядеть в канале)
            message_id = self.send_telegram_message(ADMIN_CHAT_ID, tg_text, image_url)
            
            if message_id:
                # Сохраняем связь message_id -> post_id
                self.reply_mapping[str(message_id)] = post_id
                self.save_reply_mapping()
                
                # Сохраняем в pending
                self.pending_posts[post_id] = {
                    "message_id": message_id,
                    "slot_time": slot_time,
                    "tg_text": tg_text,
                    "zen_text": zen_text,
                    "image_url": image_url,
                    "theme": theme,
                    "created_at": datetime.now().isoformat()
                }
                self.save_pending()
                
                # 2. Отправляем подсказку (отдельным сообщением)
                hint = f"📝 <i>Ответьте 'ок' на этот пост для публикации в каналы</i>"
                self.send_telegram_message(ADMIN_CHAT_ID, hint, reply_to_message_id=message_id)
                
                logger.info(f"✅ Пост {post_id} отправлен админу (сообщение {message_id})")
                return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки на согласование: {e}")
            return False

    def process_reply(self, reply_text, replied_to_message_id):
        """Обрабатывает ответ на пост"""
        try:
            # Находим post_id по message_id
            post_id = self.reply_mapping.get(str(replied_to_message_id))
            
            if not post_id:
                logger.warning(f"⚠️ Не найден пост для сообщения {replied_to_message_id}")
                return False
            
            # Проверяем ключевые слова
            reply_lower = reply_text.strip().lower()
            
            # Одобрение
            if any(keyword in reply_lower for keyword in self.approve_keywords):
                logger.info(f"✅ Получено одобрение для поста {post_id}")
                return self.publish_post(post_id)
            
            # Отклонение
            elif any(keyword in reply_lower for keyword in self.reject_keywords):
                logger.info(f"❌ Получен отказ для поста {post_id}")
                return self.reject_post(post_id)
            
            # Непонятный ответ
            else:
                logger.info(f"📝 Непонятный ответ на пост {post_id}: {reply_text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ответа: {e}")
            return False

    def publish_post(self, post_id):
        """Публикует одобренный пост"""
        try:
            if post_id not in self.pending_posts:
                logger.error(f"❌ Пост {post_id} не найден")
                return False
            
            post = self.pending_posts[post_id]
            
            logger.info(f"📤 Публикую пост {post_id} в каналы...")
            
            # 1. Публикуем в основной канал Telegram (как оригинальный пост)
            tg_success = self.send_telegram_message(MAIN_CHANNEL_ID, post["tg_text"], post["image_url"])
            
            time.sleep(2)
            
            # 2. Публикуем в Дзен канал (как оригинальный пост)
            zen_success = self.send_telegram_message(ZEN_CHANNEL_ID, post["zen_text"], post["image_url"])
            
            # 3. Очищаем данные
            # Удаляем из pending
            del self.pending_posts[post_id]
            self.save_pending()
            
            # Удаляем из mapping
            if str(post["message_id"]) in self.reply_mapping:
                del self.reply_mapping[str(post["message_id"])]
                self.save_reply_mapping()
            
            # 4. Отмечаем в истории
            self.mark_slot_as_sent(post["slot_time"])
            
            # 5. Уведомляем админа
            if ADMIN_CHAT_ID:
                success_count = sum([tg_success is not None, zen_success is not None])
                
                if success_count == 2:
                    notification = f"✅ Пост опубликован в оба канала!"
                elif success_count == 1:
                    notification = f"⚠️ Пост опубликован в {success_count} из 2 каналов"
                else:
                    notification = f"❌ Не удалось опубликовать пост"
                
                self.send_telegram_message(ADMIN_CHAT_ID, notification)
            
            logger.info(f"✅ Пост {post_id} опубликован (TG: {tg_success is not None}, Дзен: {zen_success is not None})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False

    def reject_post(self, post_id):
        """Отклоняет пост"""
        try:
            if post_id not in self.pending_posts:
                logger.error(f"❌ Пост {post_id} не найден")
                return False
            
            post = self.pending_posts[post_id]
            theme = post["theme"]
            
            # Очищаем данные
            del self.pending_posts[post_id]
            self.save_pending()
            
            if str(post["message_id"]) in self.reply_mapping:
                del self.reply_mapping[str(post["message_id"])]
                self.save_reply_mapping()
            
            # Уведомляем админа
            if ADMIN_CHAT_ID:
                self.send_telegram_message(ADMIN_CHAT_ID, f"❌ Пост отклонен\nТема: {theme}")
            
            logger.info(f"✅ Пост {post_id} отклонен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отклонения: {e}")
            return False

    def check_pending_reminders(self):
        """Проверяет старые посты и напоминает админу"""
        try:
            if not self.pending_posts:
                return True
            
            now = datetime.now()
            reminders_sent = 0
            
            for post_id, post in self.pending_posts.items():
                created_at = datetime.fromisoformat(post["created_at"])
                hours_passed = (now - created_at).total_seconds() / 3600
                
                # Если пост висит больше 3 часов - напоминаем
                if hours_passed > 3:
                    reminder = (
                        f"⏰ <b>Напоминание</b>\n\n"
                        f"Пост от {created_at.strftime('%H:%M')} все еще ждет решения!\n"
                        f"Тема: {post['theme']}\n\n"
                        f"<i>Ответьте 'ок' на оригинальное сообщение для публикации</i>"
                    )
                    
                    self.send_telegram_message(ADMIN_CHAT_ID, reminder)
                    reminders_sent += 1
            
            if reminders_sent > 0:
                logger.info(f"📨 Отправлено {reminders_sent} напоминаний")
            
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка проверки напоминаний: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_info, is_test=False):
        """Создает и отправляет посты"""
        try:
            logger.info(f"🎬 Создаю пост для {slot_time}")
            
            # Проверяем, не отправляли ли уже сегодня
            if not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен")
                return True
            
            # Выбираем тему и формат
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат: {text_format}")
            
            # Генерируем текст
            prompt = self.create_prompt(theme, slot_info, text_format)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            # Разделяем на части
            tg_text_raw, zen_text_raw = self.split_generated_text(combined_text)
            
            if not tg_text_raw or not zen_text_raw:
                logger.error("❌ Не удалось разделить текст")
                return False
            
            # Очищаем тексты
            tg_text = self.clean_text(tg_text_raw)
            zen_text = self.clean_text(zen_text_raw)
            
            # Получаем картинку
            image_url = self.get_post_image(theme)
            
            # Создаем ID поста
            post_id = f"post_{int(time.time())}_{random.randint(1000, 9999)}"
            
            if APPROVAL_ENABLED and not is_test:
                # Отправляем на согласование (просто как готовый пост)
                return self.send_for_approval(post_id, slot_time, tg_text, zen_text, image_url, theme)
            else:
                # Публикуем сразу (тестовый режим или нет админа)
                if is_test:
                    logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ: Публикую сразу")
                
                # Публикуем в каналы
                success_tg = self.send_telegram_message(MAIN_CHANNEL_ID, tg_text, image_url)
                time.sleep(2)
                success_zen = self.send_telegram_message(ZEN_CHANNEL_ID, zen_text, image_url)
                
                if (success_tg or success_zen) and not is_test:
                    self.mark_slot_as_sent(slot_time)
                
                return bool(success_tg or success_zen)
            
        except Exception as e:
            logger.error(f"💥 Ошибка: {e}")
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        current_hour = now.hour
        
        print(f"🔄 Запуск в {current_time} МСК")
        
        # 1. Проверяем старые посты и напоминаем
        if ADMIN_CHAT_ID:
            self.check_pending_reminders()
        
        # 2. Определяем слот
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Слот: {slot_time} - {slot_info['name']}")
        
        # 3. Создаем новый пост
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            mode = "отправлен на согласование" if APPROVAL_ENABLED else "опубликован"
            print(f"✅ Пост {mode} для слота {slot_time}")
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
        
        print(f"📝 Создаю тестовый пост для {slot_time}")
        success = self.create_and_send_posts(slot_time, slot_info, is_test=True)
        
        if success:
            print("✅ Тестовый пост создан")
        else:
            print("❌ Ошибка создания тестового поста")
        
        return success

    def handle_webhook_update(self, update_json):
        """Обрабатывает вебхук от Telegram (для ручной обработки)"""
        try:
            if 'message' in update_json:
                message = update_json['message']
                
                # Проверяем что сообщение от админа
                if str(message['from']['id']) != ADMIN_CHAT_ID:
                    return False
                
                # Проверяем что это reply на какое-то сообщение
                if 'reply_to_message' in message and 'text' in message:
                    replied_to_id = message['reply_to_message']['message_id']
                    reply_text = message['text']
                    
                    logger.info(f"📥 Получен reply от админа: {reply_text} на сообщение {replied_to_id}")
                    return self.process_reply(reply_text, replied_to_id)
            
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка обработки вебхука: {e}")
            return False


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Telegram бот для публикации постов')
    parser.add_argument('--once', action='store_true', help='Однократный запуск (для GitHub Actions)')
    parser.add_argument('--test', action='store_true', help='Тестовый режим')
    parser.add_argument('--webhook', help='Обработать вебхук JSON (для ручной обработки)')
    
    args = parser.parse_args()
    
    bot = TelegramBot()
    
    if args.webhook:
        # Обработка вебхука вручную (для тестирования)
        print(f"🌐 Обрабатываю вебхук...")
        try:
            import json as json_module
            webhook_data = json_module.loads(args.webhook)
            bot.handle_webhook_update(webhook_data)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    elif args.once:
        bot.run_once_mode()
    
    elif args.test:
        bot.run_test_mode()
    
    else:
        print("\n📖 Справка:")
        print("python github_bot.py --once    # Для GitHub Actions")
        print("python github_bot.py --test    # Тестовый режим")
        print("\n💬 Как согласовывать посты:")
        print("1. Бот пришлет вам готовый пост в личку")
        print("2. Вы отвечаете на этот пост 'ок' (или окей, да, 👍, ✅)")
        print("3. Бот опубликует пост в каналах")
        print("\n🗑️  Как отклонить пост:")
        print("Ответьте 'нет' (или не надо, ❌, 👎)")
        print("\n⚠️  Отвечайте именно НА ПОСТ (используйте reply)!")


if __name__ == "__main__":
    main()
