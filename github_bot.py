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
        """Создает промт для генерации двух текстов - УПРОЩЕННАЯ ВЕРСИЯ"""
        slot_type = time_slot_info['type']
        slot_name = time_slot_info['name']
        tg_chars = time_slot_info['tg_chars']
        zen_chars = time_slot_info['zen_chars']
        
        # УПРОЩЕННЫЙ ПРОМТ - меньше инструкций, больше концентрации на содержимом
        return f"""Тема: {theme}
Время: {slot_name}

Создай два текста:

1. Telegram-пост ({tg_chars} символов):
- Живой стиль с 2-3 эмодзи
- Интересный хук в начале
- Основная часть с полезной информацией
- Завершение и 5-7 хештегов
- Используй отступы "            •" для пунктов

2. Дзен-пост ({zen_chars} символов):
- Более формальный стиль
- Полная статья с анализом
- ОБЯЗАТЕЛЬНО ЗАВЕРШИ ПОЛНОСТЬЮ! Не обрывай на полуслове.
- В конце подпись: "Главная Видео Статьи Новости Подписки"

ВАЖНО:
1. Дай ПОЛНЫЙ текст, не обрывай!
2. Для Telegram используй "я" только для действий: "я проанализировал", "я изучил"
3. Опыт описывай как "специалисты отмечают", "практика показывает"
4. В конце Дзен-поста задай вопрос читателям

Выведи строго в таком формате:
Telegram-пост:
[текст здесь]

---

Дзен-пост:
[текст здесь]"""

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

    def generate_with_gemini(self, prompt, max_retries=3):
        """Генерирует текст через Gemini - УВЕЛИЧЕН лимит токенов"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                # УВЕЛИЧЕН maxOutputTokens до 8192 для полных текстов
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.8,
                        "maxOutputTokens": 8192,  # УВЕЛИЧЕНО с 4000
                        "topP": 0.95,
                        "topK": 40
                    }
                }
                
                logger.info("🔄 Генерируем текст...")
                response = session.post(url, json=data, timeout=90)  # Увеличен таймаут
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        
                        # ПРОВЕРКА НА ОБРЫВ
                        if self.is_text_complete(generated_text):
                            logger.info("✅ Текст сгенерирован полностью")
                            return generated_text.strip()
                        else:
                            logger.warning("⚠️ Текст обрезан, пробуем снова...")
                            if attempt < max_retries - 1:
                                time.sleep(2)
                                continue
                            
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать полный текст")
        return None

    def is_text_complete(self, text):
        """Проверяет, полный ли текст или обрезан"""
        if not text:
            return False
        
        # Проверяем наличие обоих постов
        has_telegram = "Telegram-пост:" in text
        has_zen = "Дзен-пост:" in text
        
        if not has_telegram or not has_zen:
            return False
        
        # Разделяем тексты
        parts = text.split("---")
        if len(parts) < 2:
            return False
        
        # Проверяем каждый текст на завершенность
        for part in parts:
            # Проверяем, что текст не обрывается на полуслове
            lines = part.strip().split('\n')
            if lines:
                last_line = lines[-1].strip()
                # Если последняя строка обрывается...
                if (not last_line.endswith(('.', '!', '?', '»', '"', "'", '...')) and 
                    len(last_line) > 10 and 
                    'Главная Видео Статьи Новости Подписки' not in part):
                    return False
        
        return True

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        # Ищем разделитель
        separators = ["---", "——", "––––", "*****"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("Telegram-пост:", "").strip()
                    zen_text = parts[1].replace("Дзен-пост:", "").strip()
                    
                    # Убираем возможные остатки промта
                    tg_text = tg_text.replace("Создай два текста:", "").strip()
                    zen_text = zen_text.replace("Создай два текста:", "").strip()
                    
                    return tg_text, zen_text
        
        # Если разделитель не найден, пытаемся разделить по ключевым словам
        tg_markers = ["Telegram-пост:", "1. Telegram", "Telegram пост", "Для Telegram"]
        zen_markers = ["Дзен-пост:", "2. Дзен", "Дзен пост", "Для Дзен"]
        
        tg_start = -1
        zen_start = -1
        
        for marker in tg_markers:
            if marker in combined_text:
                tg_start = combined_text.find(marker) + len(marker)
                break
        
        for marker in zen_markers:
            if marker in combined_text:
                zen_start = combined_text.find(marker) + len(marker)
                break
        
        if tg_start > 0 and zen_start > tg_start:
            tg_text = combined_text[tg_start:zen_start - len(marker)].strip()
            zen_text = combined_text[zen_start:].strip()
            return tg_text, zen_text
        
        # Крайний случай: разделяем пополам
        text_length = len(combined_text)
        if text_length > 500:
            split_point = text_length // 2
            return combined_text[:split_point].strip(), combined_text[split_point:].strip()
        
        return combined_text, combined_text

    def get_fresh_image(self, theme, width=1200, height=630):
        """Находит свежую картинку"""
        try:
            unique_id = hash(f"{theme}{time.time()}") % 1000
            image_url = f"https://picsum.photos/{width}/{height}?random={unique_id}"
            
            logger.info(f"✅ Используем Picsum для темы: {theme} (ID: {unique_id})")
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
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
                formatted_line = "            " + line
                formatted_lines.append(formatted_line)
            else:
                # Для строк, которые являются продолжением пункта
                if formatted_lines and formatted_lines[-1].startswith('            •'):
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
            "я работаю 20 лет": "специалисты с 20+ летним опытом отмечают",
            "я работал 20 лет": "за 20+ лет практики специалисты",
            "у меня 20 лет опыта": "многолетний опыт показывает",
            "мой 20-летний опыт": "многолетняя практика демонстрирует",
            "за 20 лет моей работы": "за 20+ лет практики в индустрии",
            "в моей практике": "в практике специалистов",
            "мои клиенты": "в практике встречаются случаи",
            "у меня был клиент": "знакомый специалист рассказывал",
            "клиент рассказал": "коллега из индустрии поделился",
            "мне рассказал клиент": "мне рассказал знакомый из сферы",
            "у меня есть клиент": "в практике специалистов встречается",
            "ко мне обратился клиент": "знакомому специалисту обратились",
        }
        
        text_lower = text.lower()
        
        for phrase, replacement in prohibited_phrases.items():
            if phrase in text_lower:
                text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)
        
        return text

    def ensure_zen_completion(self, text):
        """ГАРАНТИРУЕТ полную концовку для Дзен"""
        if not text:
            return text
        
        # Если уже есть стандартная подпись и завершение - возвращаем как есть
        if "Главная Видео Статьи Новости Подписки" in text:
            # Проверяем, есть ли хорошее завершение перед подписью
            signature_index = text.rfind("Главная Видео Статьи Новости Подписки")
            text_before_signature = text[:signature_index].strip()
            
            # Проверяем последнюю строку перед подписью
            lines_before = text_before_signature.split('\n')
            if lines_before:
                last_line = lines_before[-1].strip()
                # Если последняя строка обрывается или не завершена
                if (not last_line.endswith(('.', '!', '?', ':', '»', '"')) and 
                    len(last_line) > 5 and
                    not any(marker in last_line.lower() for marker in ['что думаете', 'ваше мнение', 'комментариях'])):
                    
                    # Добавляем сильное завершение
                    strong_endings = [
                        "Что думаете вы? Ждём ваше мнение в комментариях!",
                        "А как вы решаете подобные вопросы? Поделитесь опытом!",
                        "Сталкивались с таким? Расскажите в комментариях!",
                        "Ждём ваши мысли и обсуждение!",
                        "Пишите в комментариях — обсудим вместе!"
                    ]
                    
                    ending = random.choice(strong_endings)
                    text_before_signature = text_before_signature + "\n\n" + ending
                    return text_before_signature + "\n\n" + "Главная Видео Статьи Новости Подписки"
            
            return text
        
        # Если подписи нет вообще - добавляем полную концовку и подпись
        strong_endings = [
            "\n\n🔥 Что думаете вы? Этот вопрос мы ждём в комментариях!",
            "\n\n💬 Ваше мнение бесценно! Поделитесь им в комментариях — обсудим вместе!",
            "\n\n🎯 Сталкивались с подобным в практике? Расскажите, как решали!",
            "\n\n🤔 Как вы видите эту ситуацию? Ждём ваши мысли в комментариях!",
            "\n\n💡 А какой подход используете ВЫ? Давайте обменяемся опытом!"
        ]
        
        ending = random.choice(strong_endings)
        
        # Обеспечиваем, что текст заканчивается нормально
        if not text.endswith(('.', '!', '?', ':', '»', '"')):
            text = text.rstrip() + "."
        
        # Добавляем завершение и подпись
        full_text = text + ending + "\n\nГлавная Видео Статьи Новости Подписки"
        
        return full_text

    def get_moscow_time(self):
        """Возвращает текущее время по Москве"""
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
        """Умное сокращение текста до максимальной длины"""
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length]
        
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        last_newline = truncated.rfind('\n')
        last_bullet = truncated.rfind('\n            •')
        
        best_cut = max(last_sentence_end, last_newline, last_bullet)
        
        if best_cut > max_length * 0.7:
            return text[:best_cut + 1]
        else:
            return text[:max_length - 3] + "..."

    def send_single_post(self, chat_id, text, image_url):
        """Отправляет ОДИН пост с фото в Telegram"""
        try:
            # Форматируем текст с отступами
            formatted_text = self.format_text_with_indent(text)
            
            # ДЛЯ ДЗЕН: гарантируем полную концовку
            if chat_id == ZEN_CHANNEL_ID:
                formatted_text = self.ensure_zen_completion(formatted_text)
            
            # Умное сокращение если нужно
            formatted_text = self.smart_truncate_text(formatted_text, 1024)
            
            # ЛОГИРУЕМ для проверки
            logger.info(f"📝 Длина текста для {chat_id}: {len(formatted_text)} символов")
            
            # Проверяем, что текст завершен
            if len(formatted_text) > 0:
                last_100_chars = formatted_text[-100:]
                logger.info(f"📝 Последние 100 символов: ...{last_100_chars}")
            
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
                logger.info(f"✅ Пост отправлен в {chat_id}")
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
            
            # Определяем текущий временной слот
            utc_hour = datetime.utcnow().hour
            
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
                # Если запуск вручную
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
            
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            # Генерируем текст
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info)
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            # Разделяем тексты
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Форматируем тексты
            tg_text = self.format_text_with_indent(tg_text)
            zen_text = self.format_text_with_indent(zen_text)
            
            # ЛОГИРУЕМ ДЛИНУ
            logger.info(f"📊 Длина Telegram-поста: {len(tg_text)} символов")
            logger.info(f"📊 Длина Дзен-поста: {len(zen_text)} символов")
            
            # Получаем картинки
            logger.info("🖼️ Ищем свежие картинки...")
            tg_image_url = self.get_fresh_image(self.current_theme)
            time.sleep(1)
            zen_image_url = self.get_fresh_image(self.current_theme)
            
            # Отправляем посты
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Основной канал
            logger.info(f"  → Основной канал: {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url):
                success_count += 1
            
            time.sleep(2)
            
            # Второй канал
            logger.info(f"  → Второй канал: {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url):
                success_count += 1
            
            # Сохраняем историю
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
                logger.info("🎉 УСПЕХ! Посты отправлены ПОЛНОСТЬЮ!")
                logger.info("=" * 50)
                logger.info(f"   🕒 Время: {schedule_time}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {len(tg_text)} символов")
                logger.info(f"   📊 Дзен: {len(zen_text)} символов")
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
    print("🤖 GITHUB TELEGRAM HR BOT - ГЕНЕРАЦИЯ ПОЛНЫХ ПОСТОВ")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("✅ ПОСТЫ ПОЛНЫЕ И ЗАВЕРШЕННЫЕ!")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
