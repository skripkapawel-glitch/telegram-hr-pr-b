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
    print("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    print("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

# Настройка сессии requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
})

print("=" * 80)
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ С РЕЛЕВАНТНЫМИ ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
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
• Структура:
  1. Хук: короткий, интригующий, цепляющий
  2. Основной блок:
     - Используй аналитические наблюдения, разборы ситуаций, мини-истории с выводами
     - Структурированные советы, объяснение сложного простым языком
     - Сравнение подходов, демонстрация пользы, анализ поведения
  3. Вывод / польза для читателя
  4. Призыв к действию: вопрос, предложение обсудить, попросить поделиться мнением
  5. 5-7 релевантных хештегов
• СТИЛЬ ДЛЯ TELEGRAM:
  - Для действий можно использовать "я": "я проанализировал", "я изучил", "я нашел исследование"
  - Для кейсов и историй используй: "знакомый из строительной сферы рассказывал", "коллега по HR поделился", "специалист по PR упоминал"
  - НИКОГДА не говори: "я работаю 20 лет в маркетинге", "у меня 20 лет опыта", "мои клиенты", "у меня был клиент"
  - Опыт описывай от третьего лица: "специалисты с 20+ летним опытом отмечают", "практика показывает"
• ФОРМАТИРОВАНИЕ: Для пунктов используй • с большим отступом

════════════════════════════════════════
Дзен-пост ({zen_chars} символов):
• Без эмодзи, как мини-статья
• Структура:
  1. Хук: сильный, цепляющий
  2. Основной блок:
     - Анализ, размышления, выводы
     - Конкретные примеры, кейсы, истории из практики
     - Объяснение причинно-следственных связей
  3. КОНЦОВКА (ОБЯЗАТЕЛЬНО!):
     - Краткий вывод или ключевая мысль
     - ЭМОЦИОНАЛЬНЫЙ ПРИЗЫВ К ДЕЙСТВИЮ: открытый вопрос читателю, предложение обсудить в комментариях
     - Мотивация к взаимодействию: использовать фразы "Что думаете вы?", "Ждём ваше мнение!", "Обсудим в комментариях?"
     - Концовка должна быть такой же сильной, как в Telegram-посте!
  4. Подпись в конце: "Главная Видео Статьи Новости Подписки"
• СТИЛЬ ДЛЯ ДЗЕН:
  - Для действий можно использовать "я": "я проанализировал", "я исследовал", "я изучил кейсы"
  - Для историй используй: "знакомый специалист рассказывал", "коллега из индустрии поделился", "в практике встречается случай"
  - НИКОГДА не говори: "я работаю 20 лет", "у меня 20-летний опыт", "моя практика показывает", "за 20 лет моей работы"
  - Опыт описывай от третьего лица: "за 20+ лет практики специалисты пришли", "многолетний опыт показывает", "исследования демонстрируют"
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

    def get_fresh_image(self, theme, width=1200, height=630):
        """Находит свежую картинку (использует Picsum - работает с Telegram)"""
        try:
            # Генерируем уникальный ID на основе времени и темы
            unique_id = hash(f"{theme}{time.time()}") % 1000
            
            # Используем Picsum - всегда работает с Telegram
            image_url = f"https://picsum.photos/{width}/{height}?random={unique_id}"
            
            logger.info(f"✅ Используем Picsum для темы: {theme} (ID: {unique_id})")
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            # Fallback на стандартный Picsum
            return f"https://picsum.photos/{width}/{height}"

    def format_text_with_indent(self, text):
        """Форматирует текст с отступами для пунктов"""
        if not text:
            return ""
        
        # Сначала очищаем от HTML тегов и лишних пробелов
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем на запрещенные фразы
        text = self.fix_prohibited_phrases(text)
        
        # Разделяем на строки
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Убираем • перед заголовком (первая непустая строка)
            if not formatted_lines and line.startswith('•'):
                formatted_lines.append(line.replace('•', '', 1).strip())
                continue
            
            # Добавляем отступ для пунктов с •
            if line.startswith('•'):
                # Большой отступ: 12 пробелов (примерно 1 см при моноширинном шрифте)
                formatted_line = "            " + line
                formatted_lines.append(formatted_line)
            else:
                # Для строк, которые являются продолжением пункта (начинаются без •)
                # Проверяем, была ли предыдущая строка пунктом
                if formatted_lines and formatted_lines[-1].startswith('            •'):
                    # Добавляем такой же отступ для продолжения
                    formatted_lines.append("               " + line)
                else:
                    formatted_lines.append(line)
        
        # Объединяем строки обратно
        formatted_text = '\n'.join(formatted_lines)
        
        # Убираем лишние пустые строки
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        return formatted_text.strip()

    def fix_prohibited_phrases(self, text):
        """Исправляет запрещенные фразы в тексте"""
        prohibited_phrases = {
            # Запрещенные фразы про опыт
            "я работаю 20 лет": "специалисты с 20+ летним опытом отмечают",
            "я работал 20 лет": "за 20+ лет практики специалисты",
            "у меня 20 лет опыта": "многолетний опыт показывает",
            "мой 20-летний опыт": "многолетняя практика демонстрирует",
            "за 20 лет моей работы": "за 20+ лет практики в индустрии",
            "в моей практике": "в практике специалистов",
            "мои клиенты": "в практике встречаются случаи",
            "у меня был клиент": "знакомый специалист рассказывал",
            "клиент рассказал": "коллега из индустрии поделился",
            # Добавляем новые запрещенные фразы
            "мне рассказал клиент": "мне рассказал знакомый из сферы",
            "у меня есть клиент": "в практике специалистов встречается",
            "ко мне обратился клиент": "знакомому специалисту обратились",
        }
        
        text_lower = text.lower()
        
        for phrase, replacement in prohibited_phrases.items():
            if phrase in text_lower:
                # Заменяем с учетом регистра
                text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)
        
        return text

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен поста"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def ensure_zen_completion(self, text):
        """Проверяет и добавляет полноценную концовку для Дзен"""
        if not text:
            return text
        
        # Проверяем, есть ли уже хорошая концовка
        has_good_ending = any(marker in text.lower() for marker in [
            'что думаете', 'ваше мнение', 'пишите в комментариях',
            'обсудим', 'расскажите', 'поделитесь', 'комментируйте',
            'ваши мысли', 'а вы', 'как считаете', 'напишите в комментариях'
        ])
        
        # Если уже есть хорошая концовка - возвращаем как есть
        if has_good_ending:
            return text
        
        # Разделяем текст и стандартную подпись
        signature = "Главная Видео Статьи Новости Подписки"
        main_text = text
        
        # Убираем стандартную подпись если есть
        if signature in text:
            parts = text.split(signature)
            main_text = parts[0].strip()
        
        # Добавляем СИЛЬНУЮ концовку
        strong_endings = [
            "\n\n🔥 А что думаете ВЫ? Этот вопрос мы ждём в комментариях!",
            "\n\n💬 Ваше мнение бесценно! Поделитесь им в комментариях — обсудим вместе!",
            "\n\n🎯 Сталкивались с подобным в практике? Расскажите, как решали!",
            "\n\n🤔 Как вы видите эту ситуацию? Ждём ваши мысли в комментариях!",
            "\n\n💡 А какой подход используете ВЫ? Давайте обменяемся опытом!",
            "\n\n📝 Пишите в комментариях — самые интересные мнения обсудим отдельно!"
        ]
        
        # Выбираем случайное сильное завершение
        ending = random.choice(strong_endings)
        
        # Добавляем 2 пустые строки перед завершением для визуального разделения
        main_text = main_text.rstrip() + "\n\n" + ending.strip()
        
        # Добавляем стандартную подпись Дзен
        main_text = main_text + "\n\n" + signature
        
        return main_text

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        moscow_now = utc_now + timedelta(hours=3)
        return moscow_now

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

    def smart_truncate_text(self, text, max_length=1024):
        """Умное сокращение текста до максимальной длины, сохраняя завершенность"""
        if len(text) <= max_length:
            return text
        
        # Пытаемся найти естественное место для обрезки
        truncated = text[:max_length]
        
        # Ищем последнюю точку, восклицательный или вопросительный знак
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        # Ищем последний перенос строки
        last_newline = truncated.rfind('\n')
        
        # Ищем последний маркированный пункт
        last_bullet = truncated.rfind('\n            •')
        
        # Выбираем наилучшую точку обрезки
        best_cut = max(last_sentence_end, last_newline, last_bullet)
        
        if best_cut > max_length * 0.7:  # Если найдена хорошая точка обрезки
            return text[:best_cut + 1]
        else:
            # Если хорошей точки нет, обрезаем и добавляем эллипс
            return text[:max_length - 3] + "..."

    def send_single_post(self, chat_id, text, image_url):
        """Отправляет ОДИН пост с фото в Telegram"""
        try:
            # Форматируем текст с отступами
            formatted_text = self.format_text_with_indent(text)
            
            if chat_id == ZEN_CHANNEL_ID:
                formatted_text = self.ensure_zen_signature(formatted_text)
                formatted_text = self.ensure_zen_completion(formatted_text)
            
            # Умное сокращение текста если нужно
            formatted_text = self.smart_truncate_text(formatted_text, 1024)
            
            params = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': formatted_text,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Пост отправлен в {chat_id} ({len(formatted_text)} символов)")
                return True
            else:
                logger.error(f"❌ Ошибка при отправке: {response.status_code}")
                if response.text:
                    logger.error(f"❌ Ответ сервера: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            return False

    def generate_and_send_posts(self):
        """Главная функция: генерирует и отправляет посты"""
        try:
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к боту")
                return False
            
            if not self.test_gemini_access():
                logger.error("❌ Gemini недоступен")
                return False
            
            # Определяем текущий временной слот по UTC (для GitHub Actions)
            utc_hour = datetime.utcnow().hour
            
            # 09:00 МСК = 06:00 UTC
            # 14:00 МСК = 11:00 UTC  
            # 19:00 МСК = 16:00 UTC
            
            if utc_hour == 6:  # 09:00 МСК
                time_slot_info = self.time_slots["09:00"]
                schedule_time = "09:00"
                logger.info("🕒 Время для утреннего поста (09:00 МСК)")
            elif utc_hour == 11:  # 14:00 МСК
                time_slot_info = self.time_slots["14:00"]
                schedule_time = "14:00"
                logger.info("🕒 Время для дневного поста (14:00 МСК)")
            elif utc_hour == 16:  # 19:00 МСК
                time_slot_info = self.time_slots["19:00"]
                schedule_time = "19:00"
                logger.info("🕒 Время для вечернего поста (19:00 МСК)")
            else:
                # Если запуск вручную - определяем по текущему времени
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
            
            # Форматируем оба текста с отступами
            tg_text = self.format_text_with_indent(tg_text)
            zen_text = self.format_text_with_indent(zen_text)
            
            # Обеспечиваем базовую структуру с • для основных пунктов
            lines_tg = tg_text.split('\n')
            if not any('•' in line for line in lines_tg) and len(lines_tg) > 2:
                formatted_lines = []
                for i, line in enumerate(lines_tg):
                    if i > 0 and line.strip() and not line.strip().startswith(('#', 'Почему', 'Зачем', 'Как', 'Что')):
                        formatted_lines.append("            • " + line)
                    else:
                        formatted_lines.append(line)
                tg_text = '\n'.join(formatted_lines)
            
            lines_zen = zen_text.split('\n')
            if not any('•' in line for line in lines_zen) and len(lines_zen) > 2:
                formatted_lines = []
                for i, line in enumerate(lines_zen):
                    if i > 0 and line.strip() and not line.strip().startswith(('#', 'Почему', 'Зачем', 'Как', 'Что')):
                        formatted_lines.append("            • " + line)
                    else:
                        formatted_lines.append(line)
                zen_text = '\n'.join(formatted_lines)
            
            logger.info("🖼️ Ищем свежие картинки...")
            # Получаем УНИКАЛЬНЫЕ картинки для каждого канала
            tg_image_url = self.get_fresh_image(self.current_theme)
            time.sleep(1)  # Задержка для разных картинок
            zen_image_url = self.get_fresh_image(self.current_theme)
            
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Отправляем в основной канал (HR на даче)
            logger.info(f"  → Основной канал: {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            
            time.sleep(2)
            
            # Отправляем во второй канал (Тех Дзен)
            logger.info(f"  → Второй канал: {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            
            if success_count == 2:
                now = datetime.now()
                
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "theme": self.current_theme,
                    "time": now.strftime("%H:%M:%S")
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.post_history["last_post_time"] = now.isoformat()
                self.save_post_history()
                
                logger.info("\n" + "=" * 50)
                logger.info("🎉 УСПЕХ! Посты отправлены!")
                logger.info("=" * 50)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📱 Канал 1: {MAIN_CHANNEL_ID}")
                logger.info(f"   📱 Канал 2: {ZEN_CHANNEL_ID}")
                logger.info(f"   📊 Символов: Telegram - {len(tg_text)}, Zen - {len(zen_text)}")
                logger.info("=" * 50)
                return True
            else:
                logger.error(f"❌ Отправка не удалась. Успешно: {success_count}/2")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """Главная функция запуска бота"""
    print("\n" + "=" * 80)
    print("🤖 GITHUB TELEGRAM HR BOT - ГЕНЕРАЦИЯ ПОСТОВ")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ GITHUB БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
