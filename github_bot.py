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
print("🚀 GITHUB BOT: ГЕНЕРАЦИЯ ПОСТОВ ПО НОВОЙ СПЕЦИФИКАЦИИ")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал (Telegram): {MAIN_CHANNEL_ID}")
print(f"📢 Второй канал (Telegram для Дзен): {ZEN_CHANNEL_ID}")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.prohibited_topics = ["удаленная работа", "гибридная работа", "оформление только по ТК"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временные слоты по спецификации
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "tg_chars": (400, 600),
                "zen_chars": (1000, 1500),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "легкий бодрящий инсайт, мини  -наблюдение, 1-2 коротких совета, лайтовый тренд/новость, микро-исследование с одним фактом, напоминание или чек-лист на день, быстрый кейс без тяжелой аналитики, ошибка + короткий вывод, пост-вопрос на разминку, позитивный настрой (мотивация без пафоса)"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "tg_chars": (800, 1500),
                "zen_chars": (1700, 2300),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "аналитический разбор ситуации, мини-исследование с цифрами, разбор ошибок + решение, сравнение подходов 'так/так лучше', экспертный кейс с деталями, логическая цепочка: факт → пример → вывод, список шагов (причины или выводы), объяснение сложного простым языком, тренд + почему он важен, разбор поведения аудитории / механизм процессов"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "tg_chars": (600, 1000),
                "zen_chars": (1500, 2100),
                "tg_style": "живой, динамичный, человеческий, много эмодзи",
                "zen_style": "глубже, аналитичнее, как мини-статья. Без эмодзи",
                "content_type": "мини-история с моралью, мнение автора + мягкая эмоция, реальная ситуация 'как было → что поняли', наблюдение за людьми или индустрией, тихая эмоциональная подача, инсайт дня, кейс через 'знакомый рассказал', легкая рефлексия (вывод дня), провокационный вопрос для обсуждения, пост, вызывающий отклик и комментарии"
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
        """Выбирает тему с исключением запрещенных тем"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            # Убираем последние 2 использованные темы
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

    def create_combined_prompt(self, theme, time_slot_info, time_key):
        """Создает промпт по новой спецификации"""
        slot_name = time_slot_info['name']
        slot_type = time_slot_info['type']
        content_type = time_slot_info['content_type']
        tg_chars_min, tg_chars_max = time_slot_info['tg_chars']
        zen_chars_min, zen_chars_max = time_slot_info['zen_chars']
        
        prompt = f"""Ты — синтез из лучших специалистов: копирайтера, контент-мейкера, SMM-стратега, редактора с ощущением ритма текста, аналитика трендов и продюсера, который упаковывает мысли в живые форматы. У тебя 30+ лет опыта в контенте, медиа и коммуникациях. Твоя задача — создавать тексты, которые цепляют с первых строк и удерживают до последнего символа.

ВРЕМЕННОЙ СЛОТ: {time_key} ({slot_name})

ТЕМА: {theme}

ТИП КОНТЕНТА ДЛЯ ЭТОГО СЛОТА: {content_type}

ЗАПРЕЩЕННЫЕ ТЕМЫ (НИКОГДА НЕ УПОМИНАТЬ): {', '.join(self.prohibited_topics)}

---

ТРЕБОВАНИЯ К ПОСТАМ:

1. ИДЕАЛЬНЫЙ ПОСТ ДОЛЖЕН ВКЛЮЧАТЬ:
• Сильный хук — сразу интрига или провокационный факт
• Живую подачу — короткие фразы, эмоции, структурность
• Ясную логику: факт → мини-кейс/наблюдение → вывод → вопрос
• Экспертность через реальные ситуации (без фантазий)
• Если опыт — через 3-е лицо («знакомый из сферы рассказал»)
• Если аналитика — от 1-го лица

2. TELEGRAM ПОСТ ({tg_chars_min}-{tg_chars_max} символов):
• Стиль: {time_slot_info['tg_style']}
• Быстро, ярко, живо, больше эмоций и эмодзи
• Короткие абзацы с отступом 1 см и точкой •
• 1–2 сильных тезиса, чтобы читатель сразу "схватил" суть
• 3-6 хештегов # по тематике
• Форматирование: используй • для пунктов

3. ДЗЕН ПОСТ ({zen_chars_min}-{zen_chars_max} символов):
• Стиль: {time_slot_info['zen_style']}
• Глубина и разборы, факты, аналитика, мини-исследования
• Чёткая структура с отступами
• Ощущение, что это мини-статья, но читается легко
• Без эмодзи
• Форматирование: используй • для пунктов

4. ОБЯЗАТЕЛЬНАЯ ЗАКРЫВАШКА (и для ТГ, и для Дзен):
• Мягкий вовлекающий финал
• Вопрос, который хочется обсудить
• Мини-итог + приглашение поделиться мнением
• "Как вы считаете…?", "А у вас было такое?"
• Лёгкий CTA без давления

5. ВАРИАНТЫ ПОДАЧИ ТЕКСТА (ИСПОЛЬЗУЙ ПОДХОДЯЩИЕ):
• разбор ситуации или явления
• микро-исследование (данные, цифры, вывод)
• аналитическое наблюдение
• разбор ошибки и решение
• мини-история с выводом
• взгляд автора + расширение темы
• объяснение сложного простым языком
• элементы сторителлинга
• структурированные советы
• объяснение через аналогию
• демонстрация пользы
• анализ поведения аудитории
• выявление причин «почему так происходит»
• логичная цепочка: факт → пример → вывод
• список полезных шагов
• раскрытие одного сильного инсайта
• тихая эмоциональная подача (без ярких эмоций)
• сравнение разных подходов
• мини-обобщение опыта

---

ВАЖНО: ГЕНЕРИРУЙ ПОЛНОЦЕННЫЕ ПОСТЫ ДОСТАТОЧНОЙ ДЛИНЫ!
• Telegram пост должен быть МИНИМУМ {tg_chars_min} символов, в идеале {tg_chars_max}
• Дзен пост должен быть МИНИМУМ {zen_chars_min} символов, в идеале {zen_chars_max}
• Не обрезай текст! Пиши развернуто и подробно!
• Увеличь объем токенов, чтобы посты писались полноценно!

---

ФОРМАТ ОТВЕТА (СОБЛЮДАЙ ТОЧНО):

Telegram-пост:
[здесь текст для Telegram с эмодзи и хештегами]

---

Дзен-пост:
[здесь текст для Дзен без эмодзи]

---

НАЧИНАЙ ГЕНЕРАЦИЮ СЕЙЧАС. УЧТИ ВСЕ ТРЕБОВАНИЯ ВЫШЕ."""

        return prompt

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

    def generate_with_gemini(self, prompt, max_retries=5):
        """Генерирует текст через Gemini с увеличенными токенами ДО 10 000"""
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
                
                # УВЕЛИЧИВАЕМ ДО 10 000 токенов для полноценных постов
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.9,
                        "maxOutputTokens": 10000,  # ⬅️ УВЕЛИЧЕНО ДО 10 000
                        "topP": 0.95,
                        "topK": 40
                    }
                }
                
                logger.info(f"🔄 Генерируем текст (попытка {attempt + 1}/{max_retries})...")
                logger.info(f"📊 Максимальные токены: {data['generationConfig']['maxOutputTokens']}")
                
                response = session.post(url, json=data, timeout=60)  # Увеличиваем таймаут
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        
                        # Логируем длину сгенерированного текста
                        total_length = len(generated_text)
                        logger.info(f"📄 Сгенерировано {total_length} символов")
                        
                        # Проверяем структуру
                        if "Telegram-пост:" in generated_text and "Дзен-пост:" in generated_text:
                            logger.info(f"✅ Текст сгенерирован успешно")
                            
                            # Проверяем общую длину текста
                            if total_length < 2000:  # Если общий текст меньше 2000 символов
                                logger.warning(f"⚠️ Текст слишком короткий ({total_length} символов), пробуем снова...")
                                if attempt < max_retries - 1:
                                    time.sleep(2)
                                    continue
                            
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Структура текста неполная, пробуем снова...")
                            time.sleep(2)
                            continue
                    else:
                        logger.warning("⚠️ Gemini не вернул кандидатов, пробуем снова...")
                        time.sleep(2)
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        logger.error("❌ Не удалось сгенерировать текст после всех попыток")
        return None

    def split_telegram_and_zen_text(self, combined_text):
        """Разделяет текст на Telegram и Zen посты"""
        if not combined_text:
            return None, None
        
        # Ищем разделители
        tg_start = combined_text.find("Telegram-пост:")
        zen_start = combined_text.find("Дзен-пост:")
        
        if tg_start != -1 and zen_start != -1:
            # Извлекаем Telegram пост
            tg_part = combined_text[tg_start:zen_start]
            tg_text = tg_part.replace("Telegram-пост:", "").strip()
            
            # Извлекаем Дзен пост
            zen_part = combined_text[zen_start:]
            zen_text = zen_part.replace("Дзен-пост:", "").strip()
            
            # Убираем возможные разделители в конце
            if "---" in zen_text:
                zen_text = zen_text.split("---")[0].strip()
            
            return tg_text, zen_text
        
        # Fallback на старый метод
        separators = ["---", "——", "––––", "\n\nДзен-пост:", "\n\nTelegram-пост:"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        
        # Если ничего не нашли, делим пополам
        text_length = len(combined_text)
        if text_length > 500:
            split_point = text_length // 2
            return combined_text[:split_point].strip(), combined_text[split_point:].strip()
        
        return combined_text, combined_text

    def check_and_regenerate_if_needed(self, tg_text, zen_text, tg_min, tg_max, zen_min, zen_max, prompt, max_retries=3):
        """Проверяет длину постов и перегенерирует если нужно"""
        tg_len = len(tg_text)
        zen_len = len(zen_text)
        
        # Проверяем соответствие требованиям
        tg_ok = tg_min <= tg_len <= tg_max * 1.2
        zen_ok = zen_min <= zen_len <= zen_max * 1.2
        
        if tg_ok and zen_ok:
            return tg_text, zen_text, True
        
        logger.warning(f"⚠️ Посты не соответствуют требованиям длины:")
        logger.warning(f"   Telegram: {tg_len} символов (требуется: {tg_min}-{tg_max})")
        logger.warning(f"   Дзен: {zen_len} символов (требуется: {zen_min}-{zen_max})")
        
        for retry in range(max_retries):
            logger.info(f"🔄 Перегенерируем посты (попытка {retry + 1}/{max_retries})...")
            
            # Увеличиваем токены для перегенерации
            time.sleep(2)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                continue
            
            new_tg_text, new_zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not new_tg_text or not new_zen_text:
                continue
            
            new_tg_len = len(new_tg_text)
            new_zen_len = len(new_zen_text)
            
            logger.info(f"📊 Новая длина: Telegram={new_tg_len}, Дзен={new_zen_len}")
            
            # Проверяем новые посты
            new_tg_ok = tg_min <= new_tg_len <= tg_max * 1.2
            new_zen_ok = zen_min <= new_zen_len <= zen_max * 1.2
            
            if new_tg_ok and new_zen_ok:
                logger.info("✅ Перегенерация успешна!")
                return new_tg_text, new_zen_text, True
            elif new_tg_len > tg_len and new_zen_len > zen_len:
                # Если новые посты длиннее, используем их
                logger.info("✅ Новые посты длиннее, используем их")
                return new_tg_text, new_zen_text, True
        
        logger.error("❌ Не удалось сгенерировать посты нужной длины")
        return tg_text, zen_text, False

    def get_fresh_image(self, theme, width=1200, height=630):
        """Находит свежую картинку (использует Picsum - работает с Telegram)"""
        try:
            # Генерируем уникальный ID на основе времени и темы
            unique_id = hash(f"{theme}{time.time()}") % 1000
            
            # Используем Picsum - всегда работает с Telegram
            image_url = f"https://picsum.photos/{width}/{height}?random={unique_id}"
            
            logger.info(f"✅ Используем Picsum для темы: {theme}")
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            # Fallback на стандартный Picsum
            return f"https://picsum.photos/{width}/{height}"

    def format_text_with_indent(self, text, is_telegram=True):
        """Форматирует текст с отступами для пунктов"""
        if not text:
            return ""
        
        # Сначала очищаем от HTML тегов и лишних пробелов
        text = re.sub(r'<[^>]+>', '', text)
        replacements = {'&nbsp;': ' ', '&emsp;': '    ', ' ': ' ', '**': '', '__': ''}
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Проверяем на запрещенные темы
        text = self.check_prohibited_topics(text)
        
        # Разделяем на строки
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Проверяем, является ли строка хештегом
            if line.startswith('#'):
                formatted_lines.append(line)
                continue
            
            # Для Telegram добавляем больше эмодзи в начале
            if is_telegram and not any(line.startswith(char) for char in ['•', '#', '📌', '🎯', '💡', '🚀', '⚠️', '✅']):
                if random.random() > 0.7 and len(formatted_lines) < 3:
                    emoji_prefix = random.choice(['🎯 ', '💡 ', '🚀 ', '👉 ', '✨ ', '🔥 '])
                    line = emoji_prefix + line
            
            # Форматируем пункты списка
            if line.startswith('•'):
                # Большой отступ: 12 пробелов (примерно 1 см)
                formatted_line = "            " + line
                formatted_lines.append(formatted_line)
            elif line.startswith(('- ', '* ', '— ')):
                formatted_line = "            • " + line[2:].strip()
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

    def check_prohibited_topics(self, text):
        """Проверяет и исправляет запрещенные темы в тексте"""
        text_lower = text.lower()
        
        for topic in self.prohibited_topics:
            if topic in text_lower:
                logger.warning(f"⚠️ Обнаружена запрещенная тема: {topic}")
                # Заменяем на нейтральные формулировки
                if "удаленная работа" in text_lower:
                    text = re.sub(r'удаленная работа', 'формат работы', text, flags=re.IGNORECASE)
                if "гибридная работа" in text_lower:
                    text = re.sub(r'гибридная работа', 'смешанный формат', text, flags=re.IGNORECASE)
                if "оформление только по тк" in text_lower:
                    text = re.sub(r'оформление только по тк', 'оформление документов', text, flags=re.IGNORECASE)
        
        return text

    def ensure_zen_signature(self, text):
        """Добавляет подпись для Дзен поста"""
        signature = "Главная Видео Статьи Новости Подписки"
        if signature not in text:
            text = f"{text}\n\n{signature}"
        return text

    def ensure_closing_hook(self, text, is_telegram=True):
        """Проверяет и добавляет вовлекающую закрывашку"""
        if not text:
            return text
        
        # Проверяем, есть ли уже хорошая концовка
        closing_patterns = [
            r'как вы считаете[^?.!]*[?.!]',
            r'а у вас было такое[^?.!]*[?.!]',
            r'что думаете[^?.!]*[?.!]',
            r'ваше мнение[^?.!]*[?.!]',
            r'пишите в комментариях[^?.!]*[?.!]',
            r'обсудим[^?.!]*[?.!]',
            r'расскажите[^?.!]*[?.!]',
            r'поделитесь[^?.!]*[?.!]'
        ]
        
        has_good_ending = False
        for pattern in closing_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                has_good_ending = True
                break
        
        # Если уже есть хорошая концовка - возвращаем как есть
        if has_good_ending:
            return text
        
        # Добавляем сильную закрывашку
        if is_telegram:
            telegram_endings = [
                "\n\nКак вы считаете, это работает? 💭",
                "\n\nА у вас был похожий опыт? Расскажите! 👇",
                "\n\nЧто думаете по этому поводу? Жду ваши мысли! 💬",
                "\n\nСталкивались с таким? Поделитесь в комментариях! ✨",
                "\n\nА как бы вы поступили? Давайте обсудим! 🗣️"
            ]
            ending = random.choice(telegram_endings)
        else:
            zen_endings = [
                "\n\nКак вы считаете, насколько этот подход эффективен?",
                "\n\nА в вашей практике было нечто подобное? Поделитесь опытом.",
                "\n\nЧто думаете об этом методе? Ваше мнение важно для обсуждения.",
                "\n\nСталкивались ли вы с такой ситуацией? Расскажите в комментариях.",
                "\n\nКакой подход ближе вам? Давайте обсудим в комментариях."
            ]
            ending = random.choice(zen_endings)
        
        # Добавляем завершение перед подписью (если она есть)
        if not is_telegram and "Главная Видео Статьи Новости Подписки" in text:
            parts = text.split("Главная Видео Статьи Новости Подписки")
            main_text = parts[0].strip()
            signature = "Главная Видео Статьи Новости Подписки"
            return f"{main_text}{ending}\n\n{signature}"
        else:
            return text.rstrip() + ending

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
        
        if best_cut > max_length * 0.7:
            return text[:best_cut + 1]
        else:
            return text[:max_length - 3] + "..."

    def add_telegram_hashtags(self, text, theme):
        """Добавляет хештеги для Telegram поста"""
        # Базовые хештеги по темам
        theme_hashtags = {
            "HR и управление персоналом": ["#HR", "#управление", "#персонал", "#карьера", "#работа", "#бизнес"],
            "PR и коммуникации": ["#PR", "#коммуникации", "#маркетинг", "#медиа", "#бренд", "#продвижение"],
            "ремонт и строительство": ["#ремонт", "#стройка", "#дизайн", "#интерьер", "#дом", "#квартира"]
        }
        
        # Выбираем хештеги по теме
        base_hashtags = theme_hashtags.get(theme, ["#контент", "#эксперт", "#советы"])
        
        # Добавляем случайные общие хештеги
        general_hashtags = ["#инсайты", "#лайфхак", "#профессия", "#развитие", "#успех", "#тренды"]
        random.shuffle(general_hashtags)
        
        # Формируем итоговый список (3-6 хештегов)
        all_hashtags = base_hashtags[:4] + general_hashtags[:3]
        hashtags_to_add = random.sample(all_hashtags, min(random.randint(4, 6), len(all_hashtags)))
        
        # Проверяем, есть ли уже хештеги
        existing_hashtags = re.findall(r'#\w+', text)
        if len(existing_hashtags) < 3:
            hashtags_line = " ".join(hashtags_to_add)
            return f"{text}\n\n{hashtags_line}"
        
        return text

    def send_single_post(self, chat_id, text, image_url, is_telegram=True):
        """Отправляет ОДИН пост с фото в Telegram"""
        try:
            # Форматируем текст с отступами
            formatted_text = self.format_text_with_indent(text, is_telegram)
            
            # Добавляем закрывашку
            formatted_text = self.ensure_closing_hook(formatted_text, is_telegram)
            
            if is_telegram:
                # Добавляем хештеги для Telegram
                formatted_text = self.add_telegram_hashtags(formatted_text, self.current_theme)
            else:
                # Для Дзен добавляем подпись
                formatted_text = self.ensure_zen_signature(formatted_text)
            
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
                logger.info(f"✅ Пост отправлен в {chat_id}")
                logger.info(f"📊 Длина текста: {len(formatted_text)} символов")
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
            
            # Определяем текущий временной слот по UTC
            utc_hour = datetime.utcnow().hour
            
            # 09:00 МСК = 06:00 UTC
            # 14:00 МСК = 11:00 UTC  
            # 19:00 МСК = 16:00 UTC
            
            if utc_hour == 6:  # 09:00 МСК
                time_key = "09:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "09:00"
                logger.info("🕒 Время для УТРЕННЕГО поста (09:00 МСК)")
            elif utc_hour == 11:  # 14:00 МСК
                time_key = "14:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "14:00"
                logger.info("🕒 Время для ДНЕВНОГО поста (14:00 МСК)")
            elif utc_hour == 16:  # 19:00 МСК
                time_key = "19:00"
                time_slot_info = self.time_slots[time_key]
                schedule_time = "19:00"
                logger.info("🕒 Время для ВЕЧЕРНЕГО поста (19:00 МСК)")
            else:
                # Если запуск вручную - определяем по текущему времени
                now = self.get_moscow_time()
                current_hour = now.hour
                
                if 5 <= current_hour < 12:
                    time_key = "09:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной УТРЕННИЙ ({now.strftime('%H:%M')} МСК)"
                elif 12 <= current_hour < 17:
                    time_key = "14:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной ДНЕВНОЙ ({now.strftime('%H:%M')} МСК)"
                else:
                    time_key = "19:00"
                    time_slot_info = self.time_slots[time_key]
                    schedule_time = f"Ручной ВЕЧЕРНИЙ ({now.strftime('%H:%M')} МСК)"
            
            logger.info(f"🕒 Запуск: {schedule_time}")
            logger.info(f"📝 Тип поста: {time_slot_info['name']}")
            logger.info(f"🎯 Тип контента: {time_slot_info['content_type']}")
            
            self.current_theme = self.get_smart_theme()
            logger.info(f"🎯 Тема: {self.current_theme}")
            
            combined_prompt = self.create_combined_prompt(self.current_theme, time_slot_info, time_key)
            logger.info(f"📝 Длина промпта: {len(combined_prompt)} символов")
            
            combined_text = self.generate_with_gemini(combined_prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать посты")
                return False
            
            tg_text, zen_text = self.split_telegram_and_zen_text(combined_text)
            
            if not tg_text or not zen_text:
                logger.error("❌ Не удалось разделить тексты")
                return False
            
            # Проверяем длину текстов
            tg_min, tg_max = time_slot_info['tg_chars']
            zen_min, zen_max = time_slot_info['zen_chars']
            
            # Проверяем и перегенерируем если нужно
            tg_text, zen_text, length_ok = self.check_and_regenerate_if_needed(
                tg_text, zen_text, tg_min, tg_max, zen_min, zen_max, combined_prompt
            )
            
            tg_len = len(tg_text)
            zen_len = len(zen_text)
            
            logger.info(f"📊 Итоговая длина Telegram поста: {tg_len} символов (требуется: {tg_min}-{tg_max})")
            logger.info(f"📊 Итоговая длина Дзен поста: {zen_len} символов (требуется: {zen_min}-{zen_max})")
            
            if not length_ok:
                logger.warning("⚠️ Посты не соответствуют требованиям длины, но продолжаем отправку")
            
            logger.info("🖼️ Ищем свежие картинки...")
            tg_image_url = self.get_fresh_image(self.current_theme)
            time.sleep(1)
            zen_image_url = self.get_fresh_image(self.current_theme)
            
            logger.info("📤 Отправляем посты...")
            success_count = 0
            
            # Отправляем в основной канал (Telegram)
            logger.info(f"  → Основной канал (Telegram): {MAIN_CHANNEL_ID}")
            if self.send_single_post(MAIN_CHANNEL_ID, tg_text, tg_image_url, is_telegram=True):
                success_count += 1
            
            time.sleep(2)
            
            # Отправляем во второй канал (Дзен)
            logger.info(f"  → Второй канал (Дзен): {ZEN_CHANNEL_ID}")
            if self.send_single_post(ZEN_CHANNEL_ID, zen_text, zen_image_url, is_telegram=False):
                success_count += 1
            
            if success_count == 2:
                now = datetime.now()
                
                slot_info = {
                    "date": now.strftime("%Y-%m-%d"),
                    "slot": schedule_time,
                    "time_key": time_key,
                    "type": time_slot_info['type'],
                    "theme": self.current_theme,
                    "content_type": time_slot_info['content_type'],
                    "telegram_length": tg_len,
                    "zen_length": zen_len,
                    "length_ok": length_ok,
                    "time": now.strftime("%H:%M:%S")
                }
                
                if "last_slots" not in self.post_history:
                    self.post_history["last_slots"] = []
                
                self.post_history["last_slots"].append(slot_info)
                if len(self.post_history["last_slots"]) > 10:
                    self.post_history["last_slots"] = self.post_history["last_slots"][-10:]
                
                self.post_history["last_post_time"] = now.isoformat()
                self.save_post_history()
                
                logger.info("\n" + "=" * 60)
                logger.info("🎉 УСПЕХ! Посты отправлены по новой спецификации!")
                logger.info("=" * 60)
                logger.info(f"   🕒 Время: {schedule_time} ({time_key})")
                logger.info(f"   📝 Тип: {time_slot_info['name']}")
                logger.info(f"   🎯 Тема: {self.current_theme}")
                logger.info(f"   📊 Telegram: {tg_len} символов")
                logger.info(f"   📊 Дзен: {zen_len} символов")
                logger.info(f"   ✅ Длина {'соответствует' if length_ok else 'не соответствует'} требованиям")
                logger.info(f"   📱 Канал Telegram: {MAIN_CHANNEL_ID}")
                logger.info(f"   📱 Канал Дзен: {ZEN_CHANNEL_ID}")
                logger.info("=" * 60)
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
    print("🤖 GITHUB TELEGRAM HR BOT - НОВАЯ СПЕЦИФИКАЦИЯ КОНТЕНТА")
    print("=" * 80)
    print("📋 Новая структура:")
    print("   • 09:00 - Утренние инсайты и советы")
    print("   • 14:00 - Аналитические разборы")
    print("   • 19:00 - Вечерние истории и рефлексии")
    print("   • Разные стили для Telegram и Дзен")
    print("   • Обязательная закрывашка с вовлечением")
    print("   • Увеличены токены до 10 000 для полноценных постов")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ БОТ УСПЕШНО ВЫПОЛНИЛ РАБОТУ!")
        print("   Посты соответствуют новой спецификации")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ РАБОТЫ!")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
