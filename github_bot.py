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

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    print("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    print("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ ДЛЯ АВТОМАТИЧЕСКОЙ ПУБЛИКАЦИИ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установлен")
print(f"📢 Канал: {MAIN_CHANNEL_ID}")
print(f"📢 Дзен-канал: {ZEN_CHANNEL_ID}")

class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        
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
            "09:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "tg_chars": "400-600",
                "zen_chars": "1000-1500"
            },
            "14:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "tg_chars": "800-1500",
                "zen_chars": "1700-2300"
            },
            "19:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "tg_chars": "600-1000",
                "zen_chars": "1500-2100"
            }
        }
        
        self.current_theme = None
        self.current_format = None

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            return {
                "sent_slots": {},
                "last_post": None,
                "formats_used": [],
                "themes_used": []
            }

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
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
            
            if self.current_theme:
                if "themes_used" not in self.post_history:
                    self.post_history["themes_used"] = []
                self.post_history["themes_used"].append({
                    "date": today,
                    "time": slot_time,
                    "theme": self.current_theme
                })
            
            if self.current_format:
                if "formats_used" not in self.post_history:
                    self.post_history["formats_used"] = []
                self.post_history["formats_used"].append({
                    "date": today,
                    "time": slot_time,
                    "format": self.current_format
                })
            
            self.save_history()
            
        except:
            pass

    def get_smart_theme(self):
        """Выбирает тему"""
        try:
            recent_themes = []
            if "themes_used" in self.post_history and self.post_history["themes_used"]:
                recent_entries = self.post_history["themes_used"][-5:] if len(self.post_history["themes_used"]) >= 5 else self.post_history["themes_used"]
                recent_themes = [item.get("theme", "") for item in recent_entries if item.get("theme")]
            
            recent_unique = list(dict.fromkeys(recent_themes))
            available_themes = [theme for theme in self.themes if theme not in recent_unique[-2:]]
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            self.current_theme = theme
            return theme
            
        except:
            self.current_theme = random.choice(self.themes)
            return self.current_theme

    def get_smart_format(self):
        """Выбирает формат подачи"""
        try:
            recent_formats = []
            if "formats_used" in self.post_history and self.post_history["formats_used"]:
                recent_entries = self.post_history["formats_used"][-5:] if len(self.post_history["formats_used"]) >= 5 else self.post_history["formats_used"]
                recent_formats = [item.get("format", "") for item in recent_entries if item.get("format")]
            
            recent_unique = list(dict.fromkeys(recent_formats))
            available_formats = [fmt for fmt in self.text_formats if fmt not in recent_unique[-3:]]
            
            if not available_formats:
                available_formats = self.text_formats.copy()
            
            text_format = random.choice(available_formats)
            self.current_format = text_format
            return text_format
            
        except:
            self.current_format = random.choice(self.text_formats)
            return self.current_format

    def create_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Gemini"""
        
        format_instructions = {
            "разбор ситуации или явления": "Разбери конкретную ситуацию или явление в выбранной теме. Что происходит? Почему это важно? Какие последствия и выводы?",
            "микро-исследование (данные, цифры, вывод)": "Проведи микро-исследование по теме. Используй данные, цифры, статистику. Сделай выводы на основе этих данных.",
            "аналитическое наблюдение": "Поделись аналитическими наблюдениями по теме. Что ты заметил в практике? Какие закономерности и тренды?",
            "разбор ошибки и решение": "Выбери типичную ошибку в выбранной теме. Разбери почему она происходит, какие последствия и как её правильно решить.",
            "мини-история с выводом": "Расскажи мини-историю из практики по теме. История должна быть поучительной и заканчиваться четким выводом.",
            "взгляд автора + расширение темы": "Вырази своё авторское мнение по теме и расширь её, показав связи со смежными областями или глобальными трендами.",
            "объяснение сложного простым языком": "Возьми сложное понятие или процесс из темы и объясни его максимально простым языком с понятными примерами.",
            "элементы сторителлинга": "Используй элементы сторителлинга: создай персонажа, конфликт, развитие сюжета и разрешение в контексте выбранной темы.",
            "структурированные советы": "Дай конкретные, структурированные советы по теме. Разбей на четкие шаги, категории или принципы.",
            "объяснение через аналогию": "Объясни явление или процесс из темы через аналогию с чем-то знакомым и понятным обычному читателю.",
            "демонстрация пользы": "Покажи конкретную практическую пользу от применения знаний по теме. Что изменится, какие результаты можно получить.",
            "анализ поведения аудитории": "Проанализируй поведение людей (сотрудников, клиентов, аудитории) в контексте темы. Почему они так поступают?",
            "выявление причин «почему так происходит»": "Погрузись в глубинные причины явления в выбранной теме. Почему всё устроено именно так? Какие скрытые механизмы?",
            "логичная цепочка: факт → пример → вывод": "Используй логичную цепочку: приведи интересный факт, проиллюстрируй его конкретным примером, сделай практический вывод.",
            "список полезных шагов": "Создай список конкретных полезных шагов для решения проблемы или улучшения ситуации в выбранной теме.",
            "раскрытие одного сильного инсайта": "Сфокусируйся на одном мощном инсайте по теме. Раскрой его полностью, покажи все грани и практическое применение.",
            "тихая эмоциональная подача (без ярких эмоций)": "Используй сдержанную, глубокую подачу без излишней эмоциональности. Сосредоточься на сути и глубине содержания.",
            "сравнение разных подходов": "Сравни несколько разных подходов к решению проблемы в выбранной теме. Плюсы и минусы каждого, когда что лучше применять.",
            "мини-обобщение опыта": "Обобщи опыт практиков по выбранной теме. Что действительно работает на практике, а что является мифом или бесполезно."
        }
        
        format_guide = format_instructions.get(text_format, "Используй аналитический и практический подход к теме.")
        
        return f"""Создай два поста на тему: {theme}

ФОРМАТ ПОДАЧИ: {text_format}
ИНСТРУКЦИЯ: {format_guide}

ПЕРВЫЙ ПОСТ (для Telegram):
• Объем: {slot_info['tg_chars']} символов
• Стиль: живой, с эмодзи {slot_info['emoji']}, разговорный
• Структура: заголовок, основной текст, вопрос, хештеги
• Требования: полезный, практичный, с примерами

ВТОРОЙ ПОСТ (для Дзен):
• Объем: {slot_info['zen_chars']} символов  
• Стиль: аналитический, глубокий, без эмодзи
• Структура: введение, анализ, выводы, вопрос
• Требования: глубокая аналитика, данные, кейсы

Формат вывода:
TG: [текст Telegram-поста]
---
DZEN: [текст Дзен-поста]"""

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "topP": 0.95,
                    "maxOutputTokens": 4000
                }
            }
            
            response = session.post(url, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if parts and 'text' in parts[0]:
                            return parts[0]['text'].strip()
            else:
                print(f"❌ Ошибка Gemini API: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка при генерации текста: {e}")
        
        return None

    def split_generated_text(self, combined_text):
        """Разделяет текст на Telegram и Дзен части"""
        if not combined_text:
            return None, None
        
        separators = ["---", "——", "––––"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("TG:", "").replace("Telegram:", "").strip()
                    zen_text = parts[1].replace("DZEN:", "").replace("Дзен:", "").strip()
                    return tg_text, zen_text
        
        lines = combined_text.split('\n')
        if len(lines) > 4:
            for i in range(len(lines) - 3):
                if lines[i].strip() and not lines[i+1].strip() and lines[i+2].strip():
                    tg_text = '\n'.join(lines[:i+1])
                    zen_text = '\n'.join(lines[i+2:])
                    return tg_text[:800], zen_text[:2000]
        
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
                "ремонт и строительство": "construction+renovation+architecture",
                "HR и управление персоналом": "office+business+teamwork",
                "PR и коммуникации": "communication+marketing+networking"
            }
            
            query = theme_queries.get(theme, "business+work")
            encoded_query = quote_plus(query)
            
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return response.url
            
        except:
            pass
        
        return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        text = re.sub(r'TG:\s*', '', text)
        
        if len(text) > 1024:
            cut_position = text[:950].rfind('.')
            if cut_position > 700:
                text = text[:cut_position + 1] + ".."
            else:
                text = text[:950] + "..."
        
        if '#' not in text:
            hashtags = "\n\n#hr #pr #бизнес #управление"
            if len(text) + len(hashtags) < 1024:
                text += hashtags
        
        return text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзен"""
        if not text:
            return ""
        
        text = re.sub(r'DZEN:\s*', '', text)
        text = re.sub(r'Дзен:\s*', '', text)
        text = re.sub(r'#\w+', '', text)
        
        return text.strip()

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram"""
        try:
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': 'HTML'
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"✅ Отправлено в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки в {chat_id}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при отправке в {chat_id}: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_info, is_test=False, force_send=False):
        """Генерирует и отправляет посты"""
        try:
            print(f"\n🎬 Создаем пост для {slot_time} - {slot_info['name']}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                print(f"⏭️ Слот {slot_time} уже отправлен, пропускаем")
                return True
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            print(f"🎯 Тема: {theme}")
            print(f"📝 Формат: {text_format}")
            
            prompt = self.create_prompt(theme, slot_info, text_format)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                print("❌ Не удалось сгенерировать текст")
                return False
            
            tg_text_raw, zen_text_raw = self.split_generated_text(combined_text)
            
            if not tg_text_raw or not zen_text_raw:
                print("❌ Не удалось разделить тексты")
                return False
            
            tg_text = self.format_telegram_text(tg_text_raw)
            zen_text = self.format_zen_text(zen_text_raw)
            
            print(f"📊 Длина: TG={len(tg_text)}, DZEN={len(zen_text)}")
            
            image_url = self.get_post_image(theme)
            
            success_count = 0
            
            if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url):
                success_count += 1
            
            time.sleep(2)
            
            if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url):
                success_count += 1
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                print("📝 История обновлена")
            
            if success_count >= 1:
                print(f"\n🎉 Успешно отправлено: {success_count}/2 постов")
                return True
            else:
                print("❌ Не удалось отправить посты")
                return False
            
        except Exception as e:
            print(f"💥 Ошибка: {e}")
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        print(f"\n🔄 Запуск в режиме once. Время МСК: {current_time}")
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Слот: {slot_time} - {slot_info['name']}")
        
        if self.was_slot_sent_today(slot_time):
            print(f"⚠️  Слот уже отправлен, отправляем снова")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            print(f"✅ Пост отправлен в {slot_time} МСК")
        else:
            print(f"❌ Ошибка отправки")
        
        return success


def main():
    """Главная функция запуска"""
    
    parser = argparse.ArgumentParser(description='Телеграм бот для автоматической публикации постов')
    parser.add_argument('--test', '-t', action='store_true', help='Ручное тестирование')
    parser.add_argument('--slot', '-s', choices=['morning', 'day', 'evening'], help='Тип поста для теста')
    parser.add_argument('--once', '-o', action='store_true', help='Однократный запуск (для GitHub Actions)')
    parser.add_argument('--now', '-n', action='store_true', help='Немедленная отправка')
    parser.add_argument('--autopilot', '-a', action='store_true', help='Автопилот')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕЛЕГРАМ БОТА")
    print("=" * 80)
    
    bot = TelegramBot()
    
    if args.now:
        print("📝 РЕЖИМ: Немедленная отправка")
        # Упрощенный режим now
        now = bot.get_moscow_time()
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = bot.schedule[slot_time]
        bot.create_and_send_posts(slot_time, slot_info, is_test=False, force_send=True)
        
    elif args.once:
        print("📝 РЕЖИМ: Однократный запуск")
        bot.run_once_mode()
        
    elif args.test:
        print("📝 РЕЖИМ: Тестирование")
        # Упрощенный тест
        now = bot.get_moscow_time()
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = bot.schedule[slot_time]
        bot.create_and_send_posts(slot_time, slot_info, is_test=True)
        
    elif args.autopilot:
        print("📝 РЕЖИМ: Автопилот")
        print("⚠️  Автопилот временно отключен, используйте --once")
        
    else:
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("python bot.py --once       # Для GitHub Actions")
        print("python bot.py --now        # Немедленная отправка")
        print("python bot.py --test       # Тестирование")
        print("\nДЛЯ GITHUB ACTIONS: python bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
