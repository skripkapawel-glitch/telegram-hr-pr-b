import os
import requests
import random
import json
import time
import logging
import re
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
    exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    exit(1)

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: РАСШИРЕННЫЕ ВАРИАНТЫ ПОДАЧИ")
print("=" * 80)
print(f"📢 Канал 1: {MAIN_CHANNEL_ID}")
print(f"📢 Канал 2: {ZEN_CHANNEL_ID}")
print("\n⏰ РАСПИСАНИЕ (МСК):")
print("   • 09:00 - Утренний пост")
print("   • 14:00 - Дневной пост")
print("   • 19:00 - Вечерний пост")
print("=" * 80)

class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        
        # Варианты подачи текста
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
        
        # Расписание по МСК
        self.schedule = {
            "09:00": {"name": "Утренний пост", "type": "morning", "emoji": "🌅"},
            "14:00": {"name": "Дневной пост", "type": "day", "emoji": "🌞"},
            "19:00": {"name": "Вечерний пост", "type": "evening", "emoji": "🌙"}
        }

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"sent": {}, "last_post": None, "formats_used": []}

    def save_history(self):
        """Сохраняет историю"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def get_moscow_time(self):
        """Текущее время по МСК"""
        return datetime.utcnow() + timedelta(hours=3)

    def was_sent_today(self, slot_time):
        """Проверяет, отправлен ли уже пост в этот слот сегодня"""
        today = self.get_moscow_time().strftime("%Y-%m-%d")
        return slot_time in self.post_history.get("sent", {}).get(today, [])

    def mark_as_sent(self, slot_time, theme, text_format):
        """Помечает слот как отправленный сегодня"""
        today = self.get_moscow_time().strftime("%Y-%m-%d")
        
        if "sent" not in self.post_history:
            self.post_history["sent"] = {}
        
        if today not in self.post_history["sent"]:
            self.post_history["sent"][today] = []
        
        if slot_time not in self.post_history["sent"][today]:
            self.post_history["sent"][today].append(slot_time)
        
        # Сохраняем историю форматов
        if "formats_used" not in self.post_history:
            self.post_history["formats_used"] = []
        
        self.post_history["formats_used"].append({
            "date": today,
            "time": slot_time,
            "theme": theme,
            "format": text_format,
            "timestamp": datetime.now().isoformat()
        })
        
        # Ограничиваем историю форматов
        if len(self.post_history["formats_used"]) > 50:
            self.post_history["formats_used"] = self.post_history["formats_used"][-30:]
        
        self.post_history["last_post"] = {
            "time": datetime.now().isoformat(),
            "slot": slot_time,
            "theme": theme,
            "format": text_format
        }
        
        self.save_history()

    def get_theme(self):
        """Выбирает тему"""
        try:
            # Простая ротация тем
            last_themes = []
            for day in list(self.post_history.get("sent", {}).values())[-3:]:
                if isinstance(day, list):
                    last_themes.extend(day)
            
            available = self.themes.copy()
            for theme in last_themes[-2:]:
                if theme in available:
                    available.remove(theme)
            
            if not available:
                available = self.themes.copy()
            
            self.current_theme = random.choice(available)
            return self.current_theme
        except:
            return random.choice(self.themes)

    def get_text_format(self):
        """Выбирает формат подачи текста"""
        try:
            # Получаем последние использованные форматы
            used_formats = [item.get("format", "") for item in self.post_history.get("formats_used", [])[-10:]]
            
            # Доступные форматы (не использовались в последних 5 постах)
            available_formats = [f for f in self.text_formats if f not in used_formats[-5:]]
            
            if not available_formats:
                available_formats = self.text_formats.copy()
            
            return random.choice(available_formats)
        except:
            return random.choice(self.text_formats)

    def create_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Gemini с выбранным форматом"""
        
        format_instructions = {
            "разбор ситуации или явления": "Разбери конкретную ситуацию или явление в теме. Что происходит? Почему? Какие последствия?",
            "микро-исследование (данные, цифры, вывод)": "Приведи данные, цифры, статистику по теме. Сделай выводы на основе этих данных.",
            "аналитическое наблюдение": "Поделись наблюдениями по теме. Что ты заметил? Какие закономерности выявил?",
            "разбор ошибки и решение": "Выбери типичную ошибку в теме. Разбери почему она происходит и как её избежать.",
            "мини-история с выводом": "Расскажи короткую историю из практики по теме. Сделай вывод из этой истории.",
            "взгляд автора + расширение темы": "Вырази своё мнение по теме и расширь её, показав связи с другими областями.",
            "объяснение сложного простым языком": "Возьми сложное понятие из темы и объясни его простыми словами с примерами.",
            "элементы сторителлинга": "Используй storytelling: персонажи, конфликт, развитие, разрешение в контексте темы.",
            "структурированные советы": "Дай конкретные, структурированные советы по теме. Разбей на шаги или категории.",
            "объяснение через аналогию": "Объясни явление из темы через аналогию с чем-то знакомым читателю.",
            "демонстрация пользы": "Покажи конкретную пользу от применения знаний по теме. Что изменится?",
            "анализ поведения аудитории": "Проанализируй поведение людей в контексте темы. Почему они так поступают?",
            "выявление причин «почему так происходит»": "Погрузись в глубинные причины явления в теме. Почему всё устроено именно так?",
            "логичная цепочка: факт → пример → вывод": "Используй цепочку: приведи факт, проиллюстрируй примером, сделай вывод.",
            "список полезных шагов": "Создай список конкретных шагов для решения проблемы в теме.",
            "раскрытие одного сильного инсайта": "Сфокусируйся на одном мощном инсайте по теме. Раскрой его полностью.",
            "тихая эмоциональная подача (без ярких эмоций)": "Используй сдержанную, глубокую подачу без излишней эмоциональности.",
            "сравнение разных подходов": "Сравни несколько подходов к решению проблемы в теме. Плюсы и минусы каждого.",
            "мини-обобщение опыта": "Обобщи опыт практиков по теме. Что работает, а что нет на самом деле?"
        }
        
        format_guide = format_instructions.get(text_format, "Используй аналитический подход к теме.")
        
        return f"""Ты — эксперт в теме: {theme}

📋 ФОРМАТ ПОДАЧИ: {text_format}
📝 ИНСТРУКЦИЯ: {format_guide}

══ TELEGRAM (для канала @da4a_hr) ══
• Объем: 300-500 символов
• Стиль: живой, с эмодзи {slot_info['emoji']}, разговорный
• Структура:
  1. Хук (цепляющая первая фраза с эмодзи)
  2. Основной контент в выбранном формате
  3. Конкретная польза для читателя
  4. Вопрос для вовлечения аудитории
  5. 5-7 релевантных хештегов
• Тон: дружеский, экспертный но без заумностей

══ ДЗЕН (для канала @tehdzenm) ══  
• Объем: 800-1200 символов
• Стиль: аналитический, глубже чем Telegram
• Структура:
  1. Введение (проблематика темы)
  2. Основная часть (развернуто в выбранном формате)
  3. Анализ и выводы
  4. Открытый вопрос для дискуссии
• Особое: без хештегов, без эмодзи, без подписей
• Тон: профессиональный, но доступный

ТИП ПОСТА: {slot_info['name']} ({slot_info['type']})

Создай УНИКАЛЬНЫЕ тексты, не шаблонные. Избегай клише.
Используй конкретные примеры, цифры, кейсы где уместно.

Формат ответа (строго соблюдай!):
TG: [текст Telegram поста]
---
DZEN: [текст Дзен поста]"""

    def generate_text(self, prompt):
        """Генерирует текст через Gemini"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.85,
                    "topP": 0.95,
                    "maxOutputTokens": 2500
                }
            }
            
            response = session.post(url, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                logger.error(f"❌ Gemini ошибка: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
        return None

    def get_image(self, theme):
        """Получает картинку по теме"""
        try:
            theme_map = {
                "ремонт и строительство": "construction+renovation+architecture",
                "HR и управление персоналом": "office+business+teamwork",
                "PR и коммуникации": "communication+marketing+networking"
            }
            query = theme_map.get(theme, "business+success")
            return f"https://source.unsplash.com/featured/1200x630/?{query}"
        except:
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def send_to_telegram(self, chat_id, text, image_url):
        """Отправляет пост в Telegram"""
        try:
            # Ограничиваем текст для Telegram
            if len(text) > 1024:
                # Ищем хорошее место для обрезки
                cut_pos = text[:1000].rfind('.')
                if cut_pos > 800:
                    text = text[:cut_pos+1] + ".."
                else:
                    text = text[:1000] + "..."
            
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
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
            return False

    def create_and_send_post(self, slot_time, slot_info, is_test=False):
        """Создает и отправляет пост"""
        logger.info(f"🎬 Начинаем создание поста для {slot_time}")
        
        # 1. Выбираем тему и формат
        theme = self.get_theme()
        text_format = self.get_text_format()
        
        logger.info(f"🎯 Тема: {theme}")
        logger.info(f"📝 Формат подачи: {text_format}")
        
        # 2. Генерируем промпт и текст
        prompt = self.create_prompt(theme, slot_info, text_format)
        logger.info("🤖 Генерируем текст через Gemini...")
        
        generated = self.generate_text(prompt)
        if not generated:
            logger.error("❌ Не удалось сгенерировать текст")
            return False
        
        # 3. Разделяем на TG и DZEN
        if "---" in generated:
            tg_part, dzen_part = generated.split("---", 1)
            tg_text = tg_part.replace("TG:", "").strip()
            dzen_text = dzen_part.replace("DZEN:", "").strip()
        else:
            # Фолбэк если формат нарушен
            lines = generated.split('\n')
            if len(lines) > 10:
                split_point = len(lines) // 2
                tg_text = '\n'.join(lines[:split_point])[:500]
                dzen_text = '\n'.join(lines[split_point:])[:1200]
            else:
                tg_text = generated[:500]
                dzen_text = generated[500:1200] if len(generated) > 500 else generated
        
        logger.info(f"📊 Длина текстов: TG={len(tg_text)}, DZEN={len(dzen_text)}")
        
        # 4. Получаем картинку
        logger.info("🖼️ Получаем картинку...")
        image_url = self.get_image(theme)
        
        # 5. Отправляем в Telegram
        logger.info("📤 Отправляем посты...")
        
        success_count = 0
        
        # В основной канал (Telegram стиль)
        if self.send_to_telegram(MAIN_CHANNEL_ID, tg_text, image_url):
            logger.info(f"✅ Отправлено в {MAIN_CHANNEL_ID}")
            success_count += 1
        else:
            logger.error(f"❌ Ошибка отправки в {MAIN_CHANNEL_ID}")
        
        time.sleep(2)
        
        # В Дзен канал
        if self.send_to_telegram(ZEN_CHANNEL_ID, dzen_text, image_url):
            logger.info(f"✅ Отправлено в {ZEN_CHANNEL_ID}")
            success_count += 1
        else:
            logger.error(f"❌ Ошибка отправки в {ZEN_CHANNEL_ID}")
        
        # 6. Сохраняем в историю если не тест
        if success_count >= 1 and not is_test:
            self.mark_as_sent(slot_time, theme, text_format)
            logger.info(f"📝 Сохранено в историю: {slot_time}, {text_format}")
        
        return success_count >= 1

    def run_test(self, slot_type=None):
        """Ручное тестирование"""
        print("\n" + "=" * 80)
        print("🧪 РУЧНОЕ ТЕСТИРОВАНИЕ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Время МСК: {now.strftime('%H:%M')}")
        
        if slot_type:
            # Ищем слот по типу
            for slot_time, info in self.schedule.items():
                if info["type"] == slot_type:
                    print(f"📝 Тестируем: {slot_time} - {info['name']}")
                    success = self.create_and_send_post(slot_time, info, is_test=True)
                    break
            else:
                print(f"❌ Неизвестный тип: {slot_type}")
                return False
        else:
            # Автовыбор по времени суток
            hour = now.hour
            if 5 <= hour < 12:
                slot_time = "09:00"
            elif 12 <= hour < 17:
                slot_time = "14:00"
            else:
                slot_time = "19:00"
            
            info = self.schedule[slot_time]
            print(f"📝 Тестируем: {slot_time} - {info['name']} (автовыбор)")
            success = self.create_and_send_post(slot_time, info, is_test=True)
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ТЕСТ УСПЕШЕН! Пост отправлен.")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН!")
        print("=" * 80)
        
        return success

    def run_autopilot(self):
        """Автопилот - работает постоянно"""
        print("\n" + "=" * 80)
        print("🤖 АВТОПИЛОТ ЗАПУЩЕН")
        print("=" * 80)
        print("Режим: Полностью автоматический")
        print(f"Доступно форматов подачи: {len(self.text_formats)}")
        print("Для остановки: Ctrl+C")
        print("=" * 80)
        
        while True:
            try:
                now = self.get_moscow_time()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")
                
                logger.info(f"\n📅 Дата: {today}, Время МСК: {current_time}")
                
                # Проверяем все слоты расписания
                for slot_time, slot_info in self.schedule.items():
                    if self.was_sent_today(slot_time):
                        continue
                    
                    # Проверяем время (с допуском ±5 минут)
                    slot_hour, slot_minute = map(int, slot_time.split(":"))
                    slot_dt = now.replace(hour=slot_hour, minute=slot_minute, second=0)
                    
                    time_diff = (now - slot_dt).total_seconds() / 60
                    if -5 <= time_diff <= 5:
                        logger.info(f"⏰ Время публикации: {slot_time}")
                        
                        # Отправляем пост
                        success = self.create_and_send_post(slot_time, slot_info, is_test=False)
                        
                        if success:
                            logger.info(f"✅ Пост для {slot_time} успешно отправлен")
                        else:
                            logger.error(f"❌ Ошибка отправки для {slot_time}")
                        
                        time.sleep(30)
                
                # Ждем до следующей проверки
                wait_time = self.calculate_wait_time()
                if wait_time > 300:  # Если больше 5 минут
                    logger.info(f"💤 Спим {wait_time//60:.0f} минут")
                    time.sleep(wait_time)
                else:
                    time.sleep(60)  # Проверяем каждую минуту
                    
            except KeyboardInterrupt:
                print("\n\n🛑 Автопилот остановлен")
                break
            except Exception as e:
                logger.error(f"💥 Ошибка в автопилоте: {e}")
                time.sleep(300)

    def calculate_wait_time(self):
        """Вычисляет время до следующей проверки"""
        now = self.get_moscow_time()
        
        # Ищем ближайший несделанный слот
        for slot_time in self.schedule.keys():
            if not self.was_sent_today(slot_time):
                slot_hour, slot_minute = map(int, slot_time.split(":"))
                slot_dt = now.replace(hour=slot_hour, minute=slot_minute, second=0)
                
                # Если время уже прошло
                if now > slot_dt:
                    continue  # Этот слот пропустили сегодня
                
                # Время до слота в секундах
                wait_seconds = (slot_dt - now).total_seconds()
                
                # Просыпаемся за 5 минут до поста
                return max(60, wait_seconds - 300)
        
        # Все посты отправлены, ждем до завтра
        tomorrow = now.replace(hour=8, minute=0, second=0)
        if now >= tomorrow:
            tomorrow += timedelta(days=1)
        
        return (tomorrow - now).total_seconds()

    def run_once(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        print(f"\n🔄 Запуск в режиме once. Время МСК: {current_time}")
        
        # Ищем ближайший несделанный слот
        for slot_time, slot_info in self.schedule.items():
            if not self.was_sent_today(slot_time):
                slot_hour, slot_minute = map(int, slot_time.split(":"))
                slot_dt = now.replace(hour=slot_hour, minute=slot_minute, second=0)
                
                # Проверяем, что мы в пределах 15 минут от времени поста
                time_diff = abs((now - slot_dt).total_seconds() / 60)
                if time_diff <= 15:
                    print(f"📅 Найден слот для отправки: {slot_time}")
                    return self.create_and_send_post(slot_time, slot_info, is_test=False)
        
        print("⏭️ Нет постов для отправки в ближайшее время")
        return True


def main():
    """Главная функция запуска"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Телеграм бот с расширенными форматами подачи')
    parser.add_argument('--test', action='store_true', help='Ручное тестирование')
    parser.add_argument('--slot', choices=['morning', 'day', 'evening'], help='Тип поста для теста')
    parser.add_argument('--once', action='store_true', help='Однократный запуск')
    
    args = parser.parse_args()
    
    bot = TelegramBot()
    
    if args.test:
        bot.run_test(args.slot)
    elif args.once:
        bot.run_once()
    else:
        bot.run_autopilot()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("\n" + "=" * 80)
        print("🤖 ТЕЛЕГРАМ БОТ - РАСШИРЕННЫЕ ФОРМАТЫ")
        print("=" * 80)
        print("\nДОСТУПНЫЕ ФОРМАТЫ ПОДАЧИ:")
        formats = [
            "• разбор ситуации или явления",
            "• микро-исследование (данные, цифры, вывод)",
            "• аналитическое наблюдение", 
            "• разбор ошибки и решение",
            "• мини-история с выводом",
            "• взгляд автора + расширение темы",
            "• объяснение сложного простым языком",
            "• элементы сторителлинга",
            "• структурированные советы",
            "• объяснение через аналогию",
            "• демонстрация пользы",
            "• анализ поведения аудитории",
            "• выявление причин «почему так происходит»",
            "• логичная цепочка: факт → пример → вывод",
            "• список полезных шагов",
            "• раскрытие одного сильного инсайта",
            "• тихая эмоциональная подача (без ярких эмоций)",
            "• сравнение разных подходов",
            "• мини-обобщение опыта"
        ]
        
        for fmt in formats:
            print(fmt)
        
        print("\n" + "=" * 80)
        print("РЕЖИМЫ ЗАПУСКА:")
        print("1. python bot.py                 - Автопилот (работает постоянно)")
        print("2. python bot.py --test          - Тест (ручная отправка)")
        print("3. python bot.py --test --slot morning  - Тест утреннего поста")
        print("4. python bot.py --once          - Один пост для GitHub Actions")
        print("=" * 80)
        sys.exit(0)
    
    main()
