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
from typing import Optional, Dict, Tuple

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
print("🚀 УМНЫЙ БОТ: АВТОПИЛОТ ДЛЯ ПОСТОВ")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост")
print("   • 14:00 - Дневной пост")
print("   • 19:00 - Вечерний пост")
print("=" * 80)

class AIPostGenerator:
    def __init__(self, auto_mode: bool = False, test_slot: Optional[str] = None):
        self.auto_mode = auto_mode
        self.test_slot = test_slot
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        
        # Расписание постов (МСК)
        self.schedule = {
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

    def load_post_history(self) -> Dict:
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "sent_slots": {}
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None,
                "sent_slots": {}
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_moscow_time(self) -> datetime:
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def get_smart_theme(self) -> str:
        """Выбирает тему умным способом"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            # Не повторяем последние 2 темы
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            # Сохраняем в историю
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

    def create_combined_prompt(self, theme: str, slot_info: Dict) -> str:
        """Создает промт для генерации двух текстов"""
        return f"""Ты — копирайтер, продюсер, контент-менеджер и SMM-специалист с 20+ летним опытом.
Твоя задача: создать цепляющий, живой, интересный текст поста.

Тема: {theme}
Временной слот: {slot_info['name']}

Telegram-пост ({slot_info['tg_chars']} символов):
• Живой стиль с эмодзи
• Хук + Основной блок + Вывод + Призыв к действию
• 5-7 релевантных хештегов
• От первого лица

Дзен-пост ({slot_info['zen_chars']} символов):
• Без эмодзи, как мини-статья
• Хук + Анализ + Концовка
• Подпись в конце: "Главная Видео Статьи Новости Подписки"
• Анализ от 1-го лица, кейсы от 3-го лица

Теперь создай посты на тему: "{theme}" для времени "{slot_info['name']}".

Формат вывода строго такой:
Telegram-пост:
[текст Telegram поста]

---

Дзен-пост:
[текст Дзен поста]"""

    def test_gemini_access(self) -> bool:
        """Проверяет доступ к Gemini API"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            test_data = {"contents": [{"parts": [{"text": "Test"}]}]}
            response = session.post(url, json=test_data, timeout=10)
            return response.status_code == 200
        except:
            return False

    def generate_with_gemini(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """Генерирует текст через Gemini"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.8, "maxOutputTokens": 4000}
                }
                
                response = session.post(url, json=data, timeout=60)
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        return result['candidates'][0]['content']['parts'][0]['text'].strip()
                        
            except Exception as e:
                logger.error(f"Ошибка генерации (попытка {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        return None

    def split_telegram_and_zen_text(self, combined_text: str) -> Tuple[str, str]:
        """Разделяет текст на Telegram и Zen посты"""
        if not combined_text:
            return "", ""
        
        separators = ["---", "——", "––––"]
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("Telegram-пост:", "").strip()
                    zen_text = parts[1].replace("Дзен-пост:", "").strip()
                    return tg_text, zen_text
        
        return combined_text, combined_text

    def get_post_image(self, theme: str) -> str:
        """Находит картинку для поста"""
        try:
            theme_queries = {
                "ремонт и строительство": "construction renovation",
                "HR и управление персоналом": "office team business",
                "PR и коммуникации": "communication marketing"
            }
            
            query = theme_queries.get(theme, theme)
            encoded_query = quote_plus(query)
            return f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
        except:
            return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def format_text_with_indent(self, text: str) -> str:
        """Форматирует текст с отступами"""
        if not text:
            return ""
        
        text = re.sub(r'<[^>]+>', '', text)
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            if line.startswith('•'):
                formatted_lines.append("            " + line)
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines).strip()

    def test_bot_access(self) -> bool:
        """Проверяет доступ бота"""
        try:
            response = session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            return response.status_code == 200
        except:
            return False

    def send_single_post(self, chat_id: str, text: str, image_url: str) -> bool:
        """Отправляет пост с фото в Telegram"""
        try:
            formatted_text = self.format_text_with_indent(text)
            
            if chat_id == ZEN_CHANNEL_ID:
                if "Главная Видео Статьи Новости Подписки" not in formatted_text:
                    formatted_text += "\n\nГлавная Видео Статьи Новости Подписки"
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': formatted_text[:1024],
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Пост отправлен в {chat_id}")
                return True
            else:
                logger.error(f"❌ Ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self, slot_time: str, slot_info: Dict) -> bool:
        """Генерирует и отправляет посты для указанного слота"""
        try:
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {theme}")
            
            prompt = self.create_combined_prompt(theme, slot_info)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            logger.info("🖼️ Подбираем картинки...")
            image_url = self.get_post_image(theme)
            
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Основной канал
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, image_url):
                success_count += 1
            
            time.sleep(2)
            
            # Канал для Дзен
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, image_url):
                success_count += 1
            
            if success_count == 2:
                # Сохраняем в историю
                today = self.get_moscow_time().strftime("%Y-%m-%d")
                
                if "sent_slots" not in self.post_history:
                    self.post_history["sent_slots"] = {}
                
                if today not in self.post_history["sent_slots"]:
                    self.post_history["sent_slots"][today] = []
                
                self.post_history["sent_slots"][today].append(slot_time)
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                logger.info(f"\n🎉 Посты отправлены успешно!")
                logger.info(f"   🕒 Время: {slot_time}")
                logger.info(f"   🎯 Тема: {theme}")
                logger.info(f"   📊 Символов: TG={len(tg_text)}, Zen={len(zen_text)}")
                return True
            else:
                logger.error(f"❌ Отправка не удалась: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Ошибка: {e}")
            return False

    def was_slot_sent_today(self, slot_time: str) -> bool:
        """Проверяет, был ли слот уже отправлен сегодня"""
        today = self.get_moscow_time().strftime("%Y-%m-%d")
        sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
        return slot_time in sent_slots

    def calculate_sleep_time(self, target_time_str: str) -> float:
        """Вычисляет сколько секунд спать до целевого времени"""
        now = self.get_moscow_time()
        
        # Создаем datetime для целевого времени сегодня
        target_time = datetime.strptime(target_time_str, "%H:%M").time()
        target_datetime = datetime.combine(now.date(), target_time)
        
        # Если целевое время уже прошло сегодня, планируем на завтра
        if now > target_datetime:
            target_datetime += timedelta(days=1)
        
        # Вычисляем разницу в секундах
        sleep_seconds = (target_datetime - now).total_seconds()
        
        # Выводим информацию о сне
        sleep_hours = sleep_seconds // 3600
        sleep_minutes = (sleep_seconds % 3600) // 60
        
        logger.info(f"💤 Спим до {target_time_str} МСК ({sleep_hours:.0f}ч {sleep_minutes:.0f}мин)")
        
        return sleep_seconds

    def run_autopilot(self):
        """Основной цикл автопилота"""
        print("\n" + "=" * 80)
        print("🤖 ЗАПУСК АВТОПИЛОТА")
        print("=" * 80)
        print("Режим: Полностью автоматический")
        print("Бот 'спит' между постами и просыпается только для публикации")
        print("=" * 80)
        
        while True:
            try:
                now = self.get_moscow_time()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")
                
                logger.info(f"\n📅 Текущая дата: {today}")
                logger.info(f"🕒 Текущее время МСК: {current_time}")
                
                # Если полночь, очищаем историю отправленных слотов
                if now.hour == 0 and now.minute < 5:
                    if "sent_slots" in self.post_history:
                        # Оставляем только сегодняшнюю дату
                        self.post_history["sent_slots"] = {today: []}
                        self.save_post_history()
                        logger.info("🔄 Сброшена история отправленных постов (новая сутки)")
                
                # Определяем следующий слот для отправки
                next_slot = None
                next_slot_time = None
                
                for slot_time, slot_info in self.schedule.items():
                    if not self.was_slot_sent_today(slot_time):
                        next_slot = slot_info
                        next_slot_time = slot_time
                        break
                
                if not next_slot:
                    # Все посты на сегодня отправлены, ждем до завтра
                    logger.info("✅ Все посты на сегодня отправлены")
                    
                    # Спим до завтрашнего утра (08:00)
                    tomorrow_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
                    if now.hour >= 8:
                        tomorrow_8am += timedelta(days=1)
                    
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    sleep_hours = sleep_seconds // 3600
                    sleep_minutes = (sleep_seconds % 3600) // 60
                    
                    logger.info(f"💤 Спим до завтрашнего утра (08:00 МСК)")
                    logger.info(f"⏰ Сон: {sleep_hours:.0f}ч {sleep_minutes:.0f}мин")
                    
                    time.sleep(sleep_seconds)
                    continue
                
                # Вычисляем когда нужно отправить следующий пост
                slot_time_obj = datetime.strptime(next_slot_time, "%H:%M").time()
                slot_datetime = datetime.combine(now.date(), slot_time_obj)
                
                if now >= slot_datetime:
                    # Уже время отправлять!
                    logger.info(f"⏰ Время публиковать: {next_slot_time} - {next_slot['name']}")
                    
                    # Отправляем пост
                    success = self.generate_and_send_posts(next_slot_time, next_slot)
                    
                    if not success:
                        logger.error("❌ Не удалось отправить пост, пробуем через 5 минут")
                        time.sleep(300)  # Ждем 5 минут при ошибке
                    
                    # Короткий сон перед следующей проверкой
                    time.sleep(60)
                    
                else:
                    # Еще рано, вычисляем время сна
                    sleep_seconds = (slot_datetime - now).total_seconds()
                    
                    # Если до публикации больше 10 минут, спим до времени публикации
                    if sleep_seconds > 600:
                        self.print_sleep_info(sleep_seconds, next_slot_time)
                        time.sleep(sleep_seconds - 300)  # Просыпаемся за 5 минут
                    else:
                        # Меньше 10 минут, ждем и проверяем
                        logger.info(f"⏳ До публикации {next_slot_time}: {sleep_seconds//60:.0f} мин")
                        time.sleep(min(sleep_seconds, 60))
                        
            except KeyboardInterrupt:
                print("\n\n🛑 Автопилот остановлен")
                break
            except Exception as e:
                logger.error(f"💥 Ошибка в автопилоте: {e}")
                time.sleep(300)  # При ошибке спим 5 минут

    def print_sleep_info(self, sleep_seconds: float, target_time: str):
        """Красиво выводит информацию о сне"""
        sleep_hours = sleep_seconds // 3600
        sleep_minutes = (sleep_seconds % 3600) // 60
        
        print("\n" + "=" * 50)
        print(f"💤 АВТОПИЛОТ УХОДИТ В СОН")
        print("=" * 50)
        print(f"Следующая публикация: {target_time} МСК")
        print(f"Время сна: {sleep_hours:.0f}ч {sleep_minutes:.0f}мин")
        print(f"Проснется в: ~{target_time}")
        print("=" * 50)
        
        # Прогресс бар сна
        total_sleep = int(sleep_seconds)
        for i in range(min(30, total_sleep)):  # Показываем только первые 30 секунд
            time.sleep(1)
            if i % 10 == 0:
                remaining = total_sleep - i - 1
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                sys.stdout.write(f"\r⏳ Сон... осталось: {hours:.0f}ч {minutes:.0f}мин")
                sys.stdout.flush()
        
        print("\n")  # Новая строка после прогресс-бара

    def run_test(self, slot_type: str = None):
        """Тестовый запуск для проверки"""
        print("\n" + "=" * 80)
        print("🧪 ТЕСТОВЫЙ ЗАПУСК")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Время запуска: {now.strftime('%H:%M:%S')} МСК")
        
        if slot_type:
            # Ищем слот по типу
            slot_time = None
            slot_info = None
            for time_key, info in self.schedule.items():
                if info["type"] == slot_type:
                    slot_time = time_key
                    slot_info = info
                    break
            
            if not slot_info:
                print(f"❌ Неизвестный тип слота: {slot_type}")
                return False
        else:
            # Автоматически определяем по времени суток
            current_hour = now.hour
            if 5 <= current_hour < 12:
                slot_time = "09:00"
                slot_type = "morning"
            elif 12 <= current_hour < 17:
                slot_time = "14:00"
                slot_type = "day"
            else:
                slot_time = "19:00"
                slot_type = "evening"
            
            slot_info = self.schedule[slot_time]
        
        print(f"📝 Выбран слот: {slot_time} - {slot_info['name']}")
        print("=" * 80)
        
        # Временно отмечаем слот как неотправленный для теста
        if "sent_slots" in self.post_history:
            today = now.strftime("%Y-%m-%d")
            if today in self.post_history["sent_slots"]:
                if slot_time in self.post_history["sent_slots"][today]:
                    self.post_history["sent_slots"][today].remove(slot_time)
        
        success = self.generate_and_send_posts(slot_time, slot_info)
        
        if success:
            print("\n✅ Тестовый пост успешно отправлен!")
        else:
            print("\n❌ Ошибка при отправке тестового поста")
        
        return success


def main():
    """Главная функция запуска"""
    parser = argparse.ArgumentParser(description='Автопилот для публикации постов в Telegram')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Тестовый запуск (отправка одного поста сейчас)')
    parser.add_argument('--slot', '-s', choices=['morning', 'day', 'evening'],
                       help='Тип поста для тестового запуска')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК БОТА-АВТОПИЛОТА")
    print("=" * 80)
    
    bot = AIPostGenerator()
    
    if args.test:
        # Тестовый режим
        print("📝 РЕЖИМ: Тестовый (одна публикация)")
        bot.run_test(args.slot)
    else:
        # Автопилот режим
        print("📝 РЕЖИМ: Автопилот (полностью автоматический)")
        print("ℹ️  Бот будет работать постоянно, 'спать' между постами")
        print("ℹ️  Для остановки нажмите Ctrl+C")
        print("=" * 80)
        
        try:
            bot.run_autopilot()
        except KeyboardInterrupt:
            print("\n\n🏁 Работа завершена")
    
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("\n" + "=" * 80)
        print("🤖 ТЕЛЕГРАМ БОТ-АВТОПИЛОТ")
        print("=" * 80)
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("1. python bot.py                 - Автопилот (работает постоянно)")
        print("2. python bot.py --test          - Тест (один пост сейчас)")
        print("3. python bot.py --test --slot morning  - Тест утреннего поста")
        print("\nПримеры:")
        print("  python bot.py                    # Запуск автопилота")
        print("  python bot.py --test             # Тестовая отправка")
        print("  python bot.py --test --slot day  # Тест дневного поста")
        print("=" * 80)
        sys.exit(0)
    
    main()
