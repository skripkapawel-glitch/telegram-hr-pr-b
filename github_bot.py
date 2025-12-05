import os
import requests
import random
import json
import time
import logging
import re
import argparse
import sys
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

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    print("❌ BOT_TOKEN не установлен!")
    exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    print("❌ GEMINI_API_KEY не установлен!")
    exit(1)

# Настройка сессии requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 УМНЫЙ БОТ: ГЕНЕРАЦИЯ ПОСТОВ С РЕЛЕВАНТНЫМИ ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("\n⏰ РАСПИСАНИЕ ОТПРАВКИ (МСК):")
print("   • 09:00 - Утренний пост")
print("   • 14:00 - Дневной пост")
print("   • 19:00 - Вечерний пост")
print("=" * 80)

class AIPostGenerator:
    def __init__(self, manual_mode=True):
        self.manual_mode = manual_mode
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": "400-600",
                "zen_chars": "1000-1500"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": "800-1500",
                "zen_chars": "1700-2300"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": "600-1000",
                "zen_chars": "1500-2100"
            }
        }
        
        self.manual_slots = {
            "morning": self.time_slots["09:00"],
            "day": self.time_slots["14:00"],
            "evening": self.time_slots["19:00"]
        }

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": []
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "last_slots": []
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            if "themes" not in self.post_history:
                self.post_history["themes"] = {}
            if "global" not in self.post_history["themes"]:
                self.post_history["themes"]["global"] = []
            
            self.post_history["themes"]["global"].append(theme)
            if len(self.post_history["themes"]["global"]) > 10:
                self.post_history["themes"]["global"] = self.post_history["themes"]["global"][-8:]
            
            self.save_post_history()
            logger.info(f"🎯 Выбрана тема: {theme}")
            return theme
            
        except Exception as e:
            logger.error(f"Ошибка выбора темы: {e}")
            return random.choice(self.themes)

    def create_combined_prompt(self, theme, time_slot_info):
        """Создает промт для генерации двух текстов"""
        slot_type = time_slot_info['type']
        slot_name = time_slot_info['name']
        tg_chars = time_slot_info['tg_chars']
        zen_chars = time_slot_info['zen_chars']
        
        return f"""Ты — копирайтер, продюсер, контент-менеджер и SMM-специалист с 20+ летним опытом.
Твоя задача: создать цепляющий, живой, интересный текст поста, который заставляет читать дальше, подписываться и обсуждать.

ВАЖНО: Выводи строго два текста без комментариев, инструкций или пояснений!

Тема: {theme}
Временной слот: {slot_name}

════════════════════════════════════════
Telegram-пост ({tg_chars} символов):
• Живой стиль с эмодзи
• Блоки с отступом + «•»
• Структура:
  1. Хук: короткий, интригующий, цепляющий
  2. Основной блок (выбери один вариант подачи):
     - разбор ситуации или явления
     - микро-исследование (данные, цифры, вывод)
     - аналитическое наблюдение
     - разбор ошибки и решение
     - мини-история с выводом
     - взгляд автора + расширение темы
     - объяснение сложного простым языком
     - элементы сторителлинга
     - структурированные советы
     - объяснение через аналогию
     - демонстрация пользы
     - анализ поведения аудитории
     - выявление причин «почему так происходит»
     - логичная цепочка: факт → пример → вывод
     - список полезных шагов
     - раскрытие одного сильного инсайта
     - тихая эмоциональная подача (без ярких эмоций)
     - сравнение разных подходов
     - мини-обобщение опыта
  3. Вывод / польза для читателя
  4. Вопрос или мягкий призыв к действию
  5. 5-7 релевантных хештегов
• ОБЩИЙ СТИЛЬ: Пиши от первого лица ("я", "мне", "мой опыт")
• ИСКЛЮЧЕНИЕ: Когда приводишь примеры/кейсы/истории из практики — переходи на третье лицо ("специалист", "компания", "клиент")
  Например: "Вчера я анализировал ситуацию..." — это от первого лица
            "Кейс: один клиент столкнулся с..." — это от третьего лица

════════════════════════════════════════
Дзен-пост ({zen_chars} символов):
• Без эмодзи, как мини-статья
• Блоки с отступом + «•»
• Структура:
  1. Хук: сильный, цепляющий
  2. Основной блок (используй те же варианты подачи, что и для Telegram)
  3. Вывод / польза для читателя
  4. Вопрос или мягкий призыв к действию
  5. Подпись в конце: "Главная Видео Статьи Новости Подписки"
• ОБЩИЙ СТИЛЬ: Пиши от первого лица ("я", "мне", "мой опыт")
• ИСКЛЮЧЕНИЕ: Когда приводишь примеры/кейсы/истории из практики — переходи на третье лицо
• Без хештегов

════════════════════════════════════════
Теперь создай посты на тему: "{theme}" для времени "{slot_name}".

Формат вывода строго такой (без лишних слов):
Telegram-пост:
[текст Telegram поста]

---

Дзен-пост:
[текст Дзен поста]"""

    def test_gemini_access(self):
        """Проверяет доступ к Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            test_data = {
                "contents": [{"parts": [{"text": "Test"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            
            response = session.post(url, json=test_data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Gemini доступен")
                return True
            return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки Gemini: {e}")
            return False

    def generate_with_gemini(self, prompt, max_retries=2):
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "maxOutputTokens": 4000,
                    }
                }
                
                logger.info("🔄 Генерируем текст...")
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        logger.info("✅ Текст сгенерирован")
                        return generated_text.strip()
                        
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        separators = ["---", "——", "––––"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("Telegram-пост:", "").strip()
                    zen_text = parts[1].replace("Дзен-пост:", "").strip()
                    return tg_text, zen_text
        
        text_length = len(combined_text)
        if text_length > 500:
            split_point = text_length // 2
            return combined_text[:split_point].strip(), combined_text[split_point:].strip()
        
        return combined_text, combined_text

    def get_post_image(self, theme):
        """Находит картинку для поста"""
        try:
            theme_queries = {
                "ремонт и строительство": "construction renovation",
                "HR и управление персоналом": "office team business",
                "PR и коммуникации": "communication marketing"
            }
            
            query = theme_queries.get(theme, theme)
            encoded_query = quote_plus(query)
            
            width, height = 1200, 630
            unsplash_url = f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return response.url
            
            fallback_images = {
                "ремонт и строительство": [
                    "https://images.unsplash.com/photo-1504307651254-35680f356dfd",
                    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00",
                ],
                "HR и управление персоналом": [
                    "https://images.unsplash.com/photo-1552664730-d307ca884978",
                    "https://images.unsplash.com/photo-1560264280-88b68371db39",
                ],
                "PR и коммуникации": [
                    "https://images.unsplash.com/photo-1533750349088-cd871a92f312",
                    "https://images.unsplash.com/photo-1542744095-fcf48d80b0fd",
                ]
            }
            
            images = fallback_images.get(theme, ["https://images.unsplash.com/photo-1497366754035-f200968a6e72"])
            return random.choice(images) + f"?w={width}&h={height}&fit=crop"
            
        except Exception as e:
            logger.error(f"Ошибка поиска картинки: {e}")
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        if len(text) > 4090:
            text = text[:4080]
            last_period = text.rfind('.')
            if last_period > 3800:
                text = text[:last_period+1]
            text = text + "..."
        
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен поста"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        moscow_now = utc_now + timedelta(hours=3)
        return moscow_now

    def check_schedule_time(self):
        """Проверяет время для автоматической отправки"""
        if self.manual_mode:
            return "manual"
        
        now = self.get_moscow_time()
        current_time_str = now.strftime("%H:%M")
        
        schedule_times = ["09:00", "14:00", "19:00"]
        
        for schedule_time in schedule_times:
            schedule_dt = datetime.strptime(schedule_time, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            
            time_diff = abs((now - schedule_dt).total_seconds() / 60)
            
            if time_diff <= 2:
                last_slots = self.post_history.get("last_slots", [])
                today = now.strftime("%Y-%m-%d")
                
                for slot in last_slots:
                    if slot.get("date") == today and slot.get("slot") == schedule_time:
                        logger.info(f"⏭️ Пост в {schedule_time} уже отправлен сегодня")
                        return None
                
                logger.info(f"✅ Время для отправки: {schedule_time}")
                return schedule_time
        
        logger.info(f"⏭️ Не время для отправки (текущее МСК: {current_time_str})")
        return None

    def test_bot_access(self):
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            if response.status_code != 200:
                logger.error("❌ Бот не доступен")
                return False
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост с фото в Telegram"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            if chat_id == ZEN_CHANNEL_ID:
                clean_text = self.ensure_zen_signature(clean_text)
            
            caption = clean_text[:150] + "..." if len(clean_text) > 150 else clean_text
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': caption[:1024],
                'parse_mode': 'HTML'
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в {chat_id}")
                
                time.sleep(1)
                
                text_params = {
                    'chat_id': chat_id,
                    'text': clean_text,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
                
                text_response = session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    params=text_params,
                    timeout=30
                )
                
                if text_response.status_code == 200:
                    logger.info(f"✅ Текст отправлен в {chat_id}")
                    return True
            
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self, slot_type=None):
        """Главная функция: генерирует и отправляет посты"""
        try:
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            if self.manual_mode:
                if slot_type:
                    if slot_type in self.manual_slots:
                        time_slot_info = self.manual_slots[slot_type]
                        schedule_time = f"Ручной ({slot_type})"
                    else:
                        time_slot_info = self.time_slots["14:00"]
                        schedule_time = "Ручной (day)"
                else:
                    now = self.get_moscow_time()
                    current_hour = now.hour
                    
                    if 5 <= current_hour < 12:
                        time_slot_info = self.time_slots["09:00"]
                        schedule_time = f"Ручной утренний ({now.strftime('%H:%M')} МСК)"
                    elif 12 <= current_hour < 17:
                        time_slot_info = self.time_slots["14:00"]
                        schedule_time = f"Ручной дневной ({now.strftime('%H:%M')} МСК)"
                    else:
                        time_slot_info = self.time_slots["19:00"]
                        schedule_time = f"Ручной вечерний ({now.strftime('%H:%M')} МСК)"
            else:
                schedule_time = self.check_schedule_time()
                if not schedule_time:
                    logger.info("⏭️ Не время для отправки")
                    return False
                
                time_slot_info = self.time_slots.get(schedule_time, self.time_slots["14:00"])
            
            logger.info(f"🕒 Запуск: {schedule_time}")
            logger.info(f"📝 Слот: {time_slot_info['name']}")
            
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info)
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            if "•" not in tg_text:
                sentences = re.split(r'(?<=[.!?])\s+', tg_text)
                tg_text = "\n• ".join(sentences)
                tg_text = "• " + tg_text
            
            if "•" not in zen_text:
                sentences = re.split(r'(?<=[.!?])\s+', zen_text)
                zen_text = "\n• ".join(sentences)
                zen_text = "• " + zen_text
            
            tg_text = self.clean_telegram_text(tg_text)
            zen_text = self.ensure_zen_signature(self.clean_telegram_text(zen_text))
            
            logger.info("🖼️ Подбираем картинки...")
            tg_image_url = self.get_post_image(self.current_theme)
            zen_image_url = self.get_post_image(self.current_theme)
            
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            logger.info(f"  → Основной канал: {MAIN_CHANNEL_ID}")
            if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            
            time.sleep(3)
            
            logger.info(f"  → Второй канал: {ZEN_CHANNEL_ID}")
            if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            
            if success_count > 0:
                now = datetime.now()
                
                if self.manual_mode:
                    mode_text = " (manual)"
                else:
                    mode_text = ""
                
                self.post_history["last_post_time"] = now.isoformat() + mode_text
                
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "time": now.strftime("%H:%M:%S"),
                    "mode": "manual" if self.manual_mode else "auto"
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.save_post_history()
                
                logger.info("\n" + "=" * 50)
                logger.info("🎉 УСПЕХ! Посты отправлены!")
                logger.info("=" * 50)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📱 Канал 1: {MAIN_CHANNEL_ID}")
                logger.info(f"   📱 Канал 2: {ZEN_CHANNEL_ID}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_scheduled(self):
        """Запуск по расписанию"""
        print("\n" + "=" * 80)
        print("⏰ АВТОМАТИЧЕСКИЙ ЗАПУСК ПО РАСПИСАНИЮ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Текущее время МСК: {now.strftime('%H:%M')}")
        
        success = self.generate_and_send_posts()
        
        if not success:
            print("⏭️ Не время для отправки или ошибка")
        else:
            print("✅ Посты отправлены по расписанию")
        
        print("=" * 80)
        return success

    def run_manual(self, slot_type=None):
        """Ручной запуск"""
        print("\n" + "=" * 80)
        print("👨‍💻 РУЧНОЙ ЗАПУСК ДЛЯ ТЕСТИРОВАНИЯ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Время запуска МСК: {now.strftime('%H:%M:%S')}")
        
        if slot_type:
            print(f"Выбран тип поста: {slot_type}")
        else:
            print("Тип поста: определяется автоматически по времени суток")
        
        success = self.generate_and_send_posts(slot_type)
        
        if not success:
            print("❌ Ошибка при отправке постов")
        else:
            print("✅ Тестовые посты отправлены успешно!")
        
        print("=" * 80)
        return success


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Телеграм бот для генерации постов')
    parser.add_argument('--auto', '-a', action='store_true', 
                       help='Автоматический режим (только по расписанию)')
    parser.add_argument('--slot', '-s', choices=['morning', 'day', 'evening'],
                       help='Тип поста для ручного режима')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК БОТА ДЛЯ ОТПРАВКИ ПОСТОВ")
    print("=" * 80)
    
    manual_mode = not args.auto
    
    if manual_mode:
        print("📝 РЕЖИМ: Ручной (тестирование в любое время)")
        print("ℹ️  Посты будут отправлены немедленно")
    else:
        print("📝 РЕЖИМ: Автоматический (строго по расписанию)")
        print("ℹ️  Посты отправятся только в 09:00, 14:00, 19:00 (МСК)")
    
    print("\n📅 Расписание (МСК):")
    print("   • 09:00 - Утренний пост")
    print("   • 14:00 - Дневной пост")
    print("   • 19:00 - Вечерний пост")
    print(f"\n📢 Каналы:")
    print(f"   • {MAIN_CHANNEL_ID} (Telegram стиль)")
    print(f"   • {ZEN_CHANNEL_ID} (Дзен стиль)")
    print("=" * 80)
    
    bot = AIPostGenerator(manual_mode=manual_mode)
    
    if manual_mode:
        success = bot.run_manual(args.slot)
    else:
        success = bot.run_scheduled()
    
    if success:
        print("\n✅ Бот успешно выполнил задание")
    else:
        print("\n⚠️  Бот завершил работу")
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("\n" + "=" * 80)
        print("🤖 ТЕЛЕГРАМ БОТ ДЛЯ ГЕНЕРАЦИИ ПОСТОВ")
        print("=" * 80)
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("1. python github_bot.py              - Ручной режим (по умолчанию)")
        print("2. python github_bot.py --auto       - Автоматический режим")
        print("3. python github_bot.py --slot day   - Ручной режим с выбором типа")
        print("\nПримеры:")
        print("  python github_bot.py                 # Тест в любое время")
        print("  python github_bot.py --slot morning  # Тест утреннего поста")
        print("  python github_bot.py --auto          # Только по расписанию")
        print("=" * 80)
    
    main()
