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

# Импортируем систему согласования
try:
    from approval_bot import send_for_approval, is_approval_mode
    APPROVAL_ENABLED = True
    logger.info("✅ Система согласования загружена")
except ImportError:
    logger.warning("⚠️ Модуль approval_bot не найден, согласование отключено")
    APPROVAL_ENABLED = False

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: АВТОПИЛОТ С СИСТЕМОЙ СОГЛАСОВАНИЯ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установлен")
print(f"✅ GEMINI_API_KEY: Установлен")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
print(f"📋 Режим согласования: {'✅ ВКЛЮЧЕН' if ADMIN_CHAT_ID and APPROVAL_ENABLED else '❌ ОТКЛЮЧЕН'}")
if ADMIN_CHAT_ID and APPROVAL_ENABLED:
    print(f"👨‍💼 Администратор: {ADMIN_CHAT_ID}")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 1000-1500)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-850)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 800-900)")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        
        # 19 форматов подачи текста
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
        
        # Обновленные объемы по временным слотам
        self.schedule = {
            "09:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "tg_chars": (400, 600),
                "zen_chars": (1000, 1500)
            },
            "14:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "tg_chars": (700, 900),
                "zen_chars": (700, 850)
            },
            "19:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "tg_chars": (600, 900),
                "zen_chars": (800, 900)
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
            logger.info(f"✅ Слот {slot_time} помечен как отправленный")
        except:
            pass

    def get_smart_theme(self):
        """Выбирает тему умным способом"""
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
            logger.info(f"🎯 Выбрана тема: {theme}")
            return theme
        except:
            self.current_theme = random.choice(self.themes)
            logger.info(f"🎯 Выбрана тема (случайно): {self.current_theme}")
            return self.current_theme

    def get_smart_format(self):
        """Выбирает формат подачи умным способом"""
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
            logger.info(f"📝 Выбран формат: {text_format}")
            return text_format
        except:
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def create_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Gemini с выбранным форматом"""
        
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
            "сравнение разных подходов": "Сравни несколько разных подходов к решении проблемы в выбранной теме. Плюсы и минусы каждого, когда что лучше применять.",
            "мини-обобщение опыта": "Обобщи опыт практиков по выбранной теме. Что действительно работает на практике, а что является мифом или бесполезно."
        }
        
        format_guide = format_instructions.get(text_format, "Используй аналитический и практический подход к теме.")
        
        tg_min, tg_max = slot_info['tg_chars']
        zen_min, zen_max = slot_info['zen_chars']
        
        prompt = f"""Ты — эксперт в создании контента. Создай ДВА разных текста для одной темы.

🎯 ТЕМА: {theme}
📋 ФОРМАТ ПОДАЧИ: {text_format}
📝 ИНСТРУКЦИЯ ДЛЯ ФОРМАТА: {format_guide}

══ TELEGRAM-ПОСТ (для канала {MAIN_CHANNEL_ID}) ══
• Объем: {tg_min}-{tg_max} символов
• Стиль: Живой, динамичный, человеческий, используй эмодзи {slot_info['emoji']}
• Структура:
  1. СИЛЬНЫЙ ХУК с первых слов
  2. Ясная логика: факт → наблюдение → вывод
  3. Короткие фразы с отступами
  4. 1-2 сильных тезиса
  5. Мягкий финал с вовлекающим вопросом
  6. 5-7 релевантных хештегов

══ ДЗЕН-ПОСТ (для канала {ZEN_CHANNEL_ID}) ══  
• Объем: {zen_min}-{zen_max} символов
• Стиль: Глубокий, аналитический, как мини-статья. БЕЗ ЭМОДЗИ.
• Структура:
  1. Введение: актуальность темы
  2. Основная часть: глубокий разбор
  3. Анализ: факты, выводы
  4. Четкая структура с отступами
  5. Заключение с мини-итогом

🎯 ТИП ПОСТА: {slot_info['name']} ({slot_info['type']})
🕒 ВРЕМЯ СУТОК: {slot_info['emoji']} {slot_info['name'].lower()}

ВАЖНО:
1. Telegram — быстро и живо. Дзен — глубина и анализ.
2. Используй конкретику: цифры, примеры, кейсы.
3. Избегай клише и шаблонных фраз.
4. Каждый текст должен быть уникальным.

Формат вывода (строго соблюдай!):
TG: [текст Telegram-поста]
---
DZEN: [текст Дзен-поста]"""
        
        logger.info(f"📝 Создан промпт для Gemini")
        return prompt

    def generate_with_gemini(self, prompt):
        """Генерирует текст через Gemini API"""
        try:
            available_models = [
                "gemini-2.5-flash-preview-04-17",
                "gemini-2.5-pro-exp-03-25",
                "gemma-3-27b-it",
                "gemini-1.5-flash-latest",
                "gemini-1.5-pro-latest"
            ]
            
            for model_name in available_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                    
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.8,
                            "topP": 0.95,
                            "maxOutputTokens": 4000
                        }
                    }
                    
                    logger.info(f"🤖 Пробуем модель: {model_name}")
                    response = session.post(url, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'candidates' in result and result['candidates']:
                            generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                            logger.info(f"✅ Текст сгенерирован моделью {model_name}")
                            logger.info(f"📊 Длина текста: {len(generated_text)} символов")
                            return generated_text
                    else:
                        logger.warning(f"⚠️ Модель {model_name} недоступна: {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка с моделью {model_name}: {str(e)[:100]}")
                    continue
            
            logger.error("❌ Все модели недоступны")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации текста: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def split_generated_text(self, combined_text):
        """Разделяет сгенерированный текст на Telegram и Дзен части"""
        if not combined_text:
            return None, None
        
        # Ищем разделитель
        separators = ["---", "——", "––––", "***", "\nDZEN:", "\nДзен:"]
        
        for separator in separators:
            if separator in combined_text:
                parts = combined_text.split(separator, 1)
                if len(parts) == 2:
                    tg_text = parts[0].replace("TG:", "").replace("Telegram:", "").strip()
                    zen_text = parts[1].replace("DZEN:", "").replace("Дзен:", "").strip()
                    return tg_text, zen_text
        
        # Если разделитель не найден, разделяем пополам
        text_length = len(combined_text)
        split_point = text_length // 2
        
        for i in range(split_point, min(split_point + 100, text_length - 1)):
            if combined_text[i] in ['.', '!', '?']:
                split_point = i + 1
                break
        
        return combined_text[:split_point].strip(), combined_text[split_point:].strip()

    def get_post_image(self, theme):
        """Находит подходящую картинку для поста"""
        try:
            theme_queries = {
                "ремонт и строительство": "construction+renovation+architecture+home",
                "HR и управление персоналом": "office+business+teamwork+meeting",
                "PR и коммуникации": "communication+marketing+networking+social+media"
            }
            
            query = theme_queries.get(theme, "business+success+work")
            encoded_query = quote_plus(query)
            
            width, height = 1200, 630
            unsplash_url = f"https://source.unsplash.com/featured/{width}x{height}/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                logger.info(f"🖼️ Найдена картинка: {image_url[:100]}...")
                return image_url
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при поиске картинки: {e}")
        
        # Дефолтная картинка
        return "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram"""
        if not text:
            return ""
        
        # Убираем метки
        text = re.sub(r'TG:\s*', '', text)
        text = re.sub(r'Telegram:\s*', '', text)
        
        # Обрезаем если слишком длинный
        if len(text) > 1024:
            cut_position = text[:950].rfind('.')
            if cut_position > 700:
                text = text[:cut_position + 1] + ".."
            else:
                text = text[:950] + "..."
        
        # Добавляем хештеги если нет
        if '#' not in text:
            hashtags = "\n\n#hr #pr #бизнес #управление #коммуникации"
            if len(text) + len(hashtags) < 1024:
                text += hashtags
        
        return text.strip()

    def format_zen_text(self, text):
        """Форматирует текст для Дзен"""
        if not text:
            return ""
        
        # Убираем метки
        text = re.sub(r'DZEN:\s*', '', text)
        text = re.sub(r'Дзен:\s*', '', text)
        text = re.sub(r'TG:\s*', '', text)
        text = re.sub(r'Telegram:\s*', '', text)
        
        # Убираем хештеги
        text = re.sub(r'#\w+', '', text)
        
        return text.strip()

    def publish_directly(self, slot_time, tg_text, zen_text, image_url, theme):
        """Публикует посты напрямую (без согласования)"""
        logger.info("📤 Публикую посты напрямую в каналы...")
        
        success_count = 0
        
        # Отправляем в основной канал
        logger.info(f"📨 Отправляем в ОСНОВНОЙ КАНАЛ: {MAIN_CHANNEL_ID}")
        if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {MAIN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {MAIN_CHANNEL_ID}")
        
        time.sleep(2)
        
        # Отправляем в Дзен канал
        logger.info(f"📨 Отправляем в ДЗЕН КАНАЛ: {ZEN_CHANNEL_ID}")
        if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {ZEN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {ZEN_CHANNEL_ID}")
        
        return success_count

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram канал"""
        try:
            logger.info(f"📤 Отправляем пост в {chat_id}")
            
            if not text or len(text.strip()) < 10:
                logger.error(f"❌ Текст слишком короткий")
                return False
            
            # Пробуем отправить с картинкой
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
                    logger.info(f"✅ Успешно отправлено с картинкой в {chat_id}")
                    return True
            
            logger.warning(f"⚠️ Не удалось с картинкой, пробуем текстом...")
            
            # Пробуем отправить только текст
            text_params = {
                'chat_id': chat_id,
                'text': text[:4096],
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response2 = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=text_params,
                timeout=30
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                if result2.get('ok'):
                    logger.info(f"✅ Успешно отправлено как текст в {chat_id}")
                    return True
            
            logger.error(f"❌ Оба метода не сработали для {chat_id}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке в {chat_id}: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_info, is_test=False, force_send=False):
        """Генерирует и отправляет посты для указанного слота"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_info['name']}")
            
            # Проверяем, не отправляли ли уже сегодня
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
            # Выбираем тему и формат
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            # Генерируем текст
            prompt = self.create_prompt(theme, slot_info, text_format)
            combined_text = self.generate_with_gemini(prompt)
            
            if not combined_text:
                logger.error("❌ Не удалось сгенерировать текст")
                return False
            
            logger.info(f"📝 Сгенерированный текст: {len(combined_text)} символов")
            
            # Разделяем на Telegram и Дзен
            tg_text_raw, zen_text_raw = self.split_generated_text(combined_text)
            
            if not tg_text_raw:
                logger.error("❌ Не удалось извлечь Telegram текст")
                return False
            
            if not zen_text_raw:
                logger.warning("⚠️ Не удалось извлечь Дзен текст, используем Telegram текст")
                zen_text_raw = tg_text_raw
            
            # Форматируем тексты
            tg_text = self.format_telegram_text(tg_text_raw)
            zen_text = self.format_zen_text(zen_text_raw)
            
            logger.info(f"📊 Длина текстов: TG={len(tg_text)}, DZEN={len(zen_text)}")
            
            if len(tg_text) < 50:
                logger.error(f"❌ Telegram текст слишком короткий")
                return False
            
            # Получаем картинку
            logger.info("🖼️ Подбираем картинку...")
            image_url = self.get_post_image(theme)
            
            # РЕЖИМ РАБОТЫ
            if ADMIN_CHAT_ID and APPROVAL_ENABLED and not is_test:
                # РЕЖИМ СОГЛАСОВАНИЯ
                logger.info("📨 РЕЖИМ СОГЛАСОВАНИЯ: отправляем пост администратору")
                
                try:
                    success = send_for_approval(
                        tg_text=tg_text,
                        zen_text=zen_text,
                        tg_image=image_url,
                        zen_image=image_url,
                        theme=theme,
                        time_slot=slot_time
                    )
                    
                    if success:
                        logger.info(f"✅ Пост успешно отправлен на согласование администратору {ADMIN_CHAT_ID}")
                        
                        if not is_test:
                            self.mark_slot_as_sent(slot_time)
                        
                        return True
                    else:
                        logger.error("❌ Не удалось отправить на согласование")
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ Критическая ошибка при отправке на согласование: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return False
            else:
                # РЕЖИМ БЕЗ СОГЛАСОВАНИЯ (прямая публикация)
                logger.info("📤 РЕЖИМ БЕЗ СОГЛАСОВАНИЯ: публикую посты напрямую")
                
                success_count = self.publish_directly(slot_time, tg_text, zen_text, image_url, theme)
                
                if success_count >= 1 and not is_test:
                    self.mark_slot_as_sent(slot_time)
                    logger.info(f"📝 Информация сохранена в историю")
                
                if success_count >= 1:
                    logger.info(f"\n🎉 УСПЕХ! Отправлено постов: {success_count}/2")
                    logger.info(f"   🕒 Время: {slot_time} МСК")
                    logger.info(f"   🎯 Тема: {theme}")
                    logger.info(f"   📝 Формат: {text_format}")
                    return True
                else:
                    logger.error(f"❌ Не удалось отправить ни одного поста")
                    return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_once_mode(self):
        """Однократный запуск для GitHub Actions"""
        now = self.get_moscow_time()
        current_time = now.strftime("%H:%M")
        
        print(f"\n🔄 Запуск в режиме once. Время МСК: {current_time}")
        
        # Определяем слот
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Найден слот для отправки: {slot_time} - {slot_info['name']}")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            if ADMIN_CHAT_ID and APPROVAL_ENABLED:
                print(f"✅ Пост отправлен на согласование в {slot_time} МСК")
            else:
                print(f"✅ Пост опубликован в каналы в {slot_time} МСК")
        else:
            print(f"❌ Ошибка отправки поста")
        
        return success

    def run_test_mode(self):
        """Тестовый режим"""
        print("\n" + "=" * 80)
        print("🧪 ТЕСТОВЫЙ РЕЖИМ")
        print("=" * 80)
        
        now = self.get_moscow_time()
        print(f"Текущее время МСК: {now.strftime('%H:%M:%S')}")
        
        # Выбираем слот
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📝 Выбран слот: {slot_time} - {slot_info['name']}")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=True)
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ТЕСТ ПРОЙДЕН!")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН")
        print("=" * 80)
        
        return success


def main():
    """Главная функция запуска"""
    
    parser = argparse.ArgumentParser(description='Телеграм бот для автоматической публикации постов')
    parser.add_argument('--test', '-t', action='store_true', help='Тестовый режим')
    parser.add_argument('--once', '-o', action='store_true', help='Однократный запуск (для GitHub Actions)')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕЛЕГРАМ БОТА")
    print("=" * 80)
    
    bot = TelegramBot()
    
    if args.once:
        print("📝 РЕЖИМ: Однократный запуск (GitHub Actions)")
        bot.run_once_mode()
    elif args.test:
        print("📝 РЕЖИМ: Тестирование")
        bot.run_test_mode()
    else:
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("python github_bot.py --once   # Для GitHub Actions")
        print("python github_bot.py --test   # Тестирование")
        print("\nДЛЯ GITHUB ACTIONS: python github_bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    main()
