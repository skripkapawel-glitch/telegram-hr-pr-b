# github_bot.py - Telegram бот для автоматической публикации постов
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
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)

if not PEXELS_API_KEY:
    logger.error("❌ PEXELS_API_KEY не установлен! Обязательно получи ключ на pexels.com/api")
    sys.exit(1)

# Система согласования отключена - прямая публикация в каналы
logger.info("📤 Режим: прямая публикация в каналы")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: АВТОПИЛОТ С ПРЯМОЙ ПУБЛИКАЦИЕЙ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
print(f"📋 Режим: 📤 ПРЯМАЯ ПУБЛИКАЦИЯ В КАНАЛЫ")
if ADMIN_CHAT_ID:
    print(f"👨‍💼 Уведомления для: {ADMIN_CHAT_ID}")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)


class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        self.image_history_file = "image_history.json"
        self.image_history = self.load_image_history()
        
        # 19 форматов подачи текста
        self.text_formats = [
            "разбор ситуации",
            "микро-исследование",
            "аналитическое наблюдение",
            "разбор ошибки",
            "мини-история",
            "взгляд автора",
            "объяснение простым языком",
            "сторителлинг",
            "структурированные советы",
            "аналогия",
            "демонстрация пользы",
            "анализ поведения аудитории",
            "причинно-следственные связи",
            "цепочка «факт → пример → вывод»",
            "список шагов",
            "инсайт",
            "тихая эмоциональная подача",
            "сравнение подходов",
            "мини-обобщение опыта"
        ]
        
        # Эмодзи для Telegram
        self.tg_emojis = ["📊", "💡", "🎯", "🔥", "✨", "⚡", "🚀", "💎", "🏆", "👑", "💼", "📈", "🤔", "💬", "👥", "🎪", "📌", "🔍", "📝", "🎨"]
        
        # Хэштеги по темам
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#кадры", 
                "#команда", "#лидерство", "#мотивация", "#развитиеперсонала",
                "#бизнес", "#управление", "#работа", "#карьера"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#продвижение", 
                "#брендинг", "#соцсети", "#медиа", "#пиар", 
                "#общение", "#публичность", "#репутация", "#инфоповод"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", 
                "#ремонтквартир", "#строитель", "#отделка", "#ремонтдома",
                "#стройматериалы", "#проект", "#ремонтподключ", "#евроремонт"
            ]
        }
        
        # Объемы по временным слотам
        self.schedule = {
            "09:00": {
                "name": "Утренний пост",
                "type": "morning",
                "emoji": "🌅",
                "tg_chars": (400, 600),
                "zen_chars": (600, 700)
            },
            "14:00": {
                "name": "Дневной пост",
                "type": "day",
                "emoji": "🌞",
                "tg_chars": (700, 900),
                "zen_chars": (700, 900)
            },
            "19:00": {
                "name": "Вечерний пост",
                "type": "evening",
                "emoji": "🌙",
                "tg_chars": (600, 900),
                "zen_chars": (700, 800)
            }
        }
        
        # Закрывающие фразы для Дзен
        self.zen_closings = [
            "━\nЧто думаете по этому поводу? 👇",
            "━\nЖду ваших комментариев! 👇",
            "━\nА как у вас с этим? 👇",
            "━\nПоделитесь своим опытом в комментариях! 👇",
            "━\nВаше мнение важно — напишите в комментариях! 👇",
            "━\nБуду рад обсудить в комментариях! 👇",
            "━\nЖду ваших историй и мнений ниже! 👇"
        ]
        
        self.current_theme = None
        self.current_format = None

    def load_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки истории: {e}")
        return {
            "sent_slots": {},
            "last_post": None,
            "formats_used": [],
            "themes_used": [],
            "theme_rotation": []
        }

    def load_image_history(self):
        """Загружает историю использованных картинок"""
        try:
            if os.path.exists(self.image_history_file):
                with open(self.image_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {
            "used_images": [],
            "last_update": None
        }

    def save_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception:
        pass

    def save_image_history(self, image_url):
        """Сохраняет историю использованных картинок"""
        try:
            if image_url not in self.image_history.get("used_images", []):
                self.image_history.setdefault("used_images", []).append(image_url)
                self.image_history["last_update"] = datetime.utcnow().isoformat()
                
                with open(self.image_history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.image_history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_moscow_time(self):
        """Возвращает текущее время по Москве (UTC+3)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=3)

    def was_slot_sent_today(self, slot_time):
        """Проверяет, был ли слот уже отправлен сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            if self.post_history and "sent_slots" in self.post_history:
                sent_slots = self.post_history.get("sent_slots", {}).get(today, [])
                return slot_time in sent_slots
            return False
        except Exception:
            return False

    def mark_slot_as_sent(self, slot_time):
        """Помечает слот как отправленный сегодня"""
        try:
            today = self.get_moscow_time().strftime("%Y-%m-%d")
            
            if not self.post_history:
                self.post_history = {}
            
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
                
                # Обновляем ротацию тем
                if "theme_rotation" not in self.post_history:
                    self.post_history["theme_rotation"] = []
                self.post_history["theme_rotation"].append(self.current_theme)
                # Ограничиваем историю последними 10 темами
                if len(self.post_history["theme_rotation"]) > 10:
                    self.post_history["theme_rotation"] = self.post_history["theme_rotation"][-10:]
            
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
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с умной ротацией - НЕ повторяем темы подряд"""
        try:
            if not self.post_history:
                self.post_history = {"theme_rotation": []}
            
            if "theme_rotation" not in self.post_history:
                self.post_history["theme_rotation"] = []
            
            theme_rotation = self.post_history.get("theme_rotation", [])
            
            if not theme_rotation:
                theme = random.choice(self.themes)
                self.current_theme = theme
                logger.info(f"🎯 Выбрана тема (первая): {theme}")
                return theme
            
            last_theme = theme_rotation[-1] if theme_rotation else None
            available_themes = [t for t in self.themes if t != last_theme]
            
            if not available_themes:
                theme_counts = {theme: 0 for theme in self.themes}
                for used_theme in reversed(theme_rotation):
                    for theme in self.themes:
                        if theme == used_theme:
                            theme_counts[theme] += 1
                theme = min(theme_counts, key=theme_counts.get)
            else:
                theme = random.choice(available_themes)
            
            self.current_theme = theme
            logger.info(f"🎯 Выбрана тема: {theme} (последняя была: {last_theme})")
            return theme
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выборе темы: {e}")
            self.current_theme = random.choice(self.themes)
            logger.info(f"🎯 Выбрана тема (случайно): {self.current_theme}")
            return self.current_theme

    def get_smart_format(self):
        """Выбирает формат подачи умным способом"""
        try:
            if not self.post_history or "formats_used" not in self.post_history:
                self.current_format = random.choice(self.text_formats)
                logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
                return self.current_format
            
            recent_formats = []
            if self.post_history.get("formats_used"):
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
        except Exception:
            self.current_format = random.choice(self.text_formats)
            logger.info(f"📝 Выбран формат (случайно): {self.current_format}")
            return self.current_format

    def get_relevant_hashtags(self, theme, count=3):
        """Возвращает релевантные хэштеги для темы"""
        hashtags = self.hashtags_by_theme.get(theme, [])
        if len(hashtags) >= count:
            return random.sample(hashtags, count)
        return hashtags[:count] if hashtags else ["#бизнес", "#советы", "#развитие"]

    def create_telegram_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Telegram поста"""
        tg_min, tg_max = slot_info['tg_chars']
        
        # Целевая длина - среднее значение
        target_length = (tg_min + tg_max) // 2
        
        # Получаем релевантные хэштеги для темы
        hashtags = self.get_relevant_hashtags(theme, 3)
        hashtags_str = ' '.join(hashtags)
        
        prompt = f"""СОЗДАЙ TELEGRAM ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
ЦЕЛЕВАЯ ДЛИНА: {target_length} символов (СТРОГО не более {tg_max} символов)

СТРУКТУРА:
1. {slot_info['emoji']} Заголовок - цепляющая первая фраза
2. Первый абзац: 2-3 предложения
3. Второй абзац: 2-3 предложения
4. Вывод: 1 четкое предложение
5. Вопрос к читателям: 1 конкретный вопрос
6. Хэштеги: {hashtags_str}

ВАЖНЫЕ ПРАВИЛА:
• МАКСИМУМ {tg_max} символов, МИНИМУМ {tg_min} символов
• Не пиши "Длина:" или счетчик символов
• Не используй ** вокруг текста
• Каждый абзац - законченная мысль
• Используй эмодзи умеренно

ПРИМЕР ПРАВИЛЬНОГО ПОСТА (примерно {target_length} символов):
{slot_info['emoji']} Почему HR важен для бизнеса? 💡

HR - это стратегический партнер бизнеса, а не просто отдел кадров.

Эффективный HR повышает продуктивность, снижает текучку, строит культуру.

Инвестиции в HR окупаются ростом прибыли и лояльности сотрудников.

Какую роль HR играет в вашей компании?

{hashtags_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОЗДАЙ ПОСТ О ТЕМЕ "{theme}" В ФОРМАТЕ "{text_format}".
МАКСИМУМ {tg_max} символов!

ТВОЙ ПОСТ:"""

        return prompt

    def create_zen_prompt(self, theme, slot_info, text_format):
        """Создает промпт для Дзен поста с ОЧЕНЬ ЖЕСТКИМИ ограничениями"""
        zen_min, zen_max = slot_info['zen_chars']
        
        # Для Дзена ставим цель ниже максимума, чтобы был запас
        target_length = (zen_min + zen_max) // 2
        
        # Выбираем случайную закрывающую фразу
        closing = random.choice(self.zen_closings)
        
        # Получаем релевантные хэштеги для темы
        hashtags = self.get_relevant_hashtags(theme, 4)
        hashtags_str = ' '.join(hashtags)
        
        prompt = f"""СОЗДАЙ КОРОТКИЙ ДЗЕН ПОСТ

ТЕМА: {theme}
ФОРМАТ: {text_format}
СТРОГОЕ ТРЕБОВАНИЕ: МАКСИМУМ {zen_max} символов, МИНИМУМ {zen_min} символов
ИДЕАЛЬНАЯ ДЛИНА: {target_length} символов

СТРУКТУРА (сокращенная):
1. Заголовок: 1 короткая строка
2. Введение: 2-3 предложения
3. Основная часть: 2-3 предложения  
4. Заключение: 1-2 предложения
5. Вопрос для обсуждения: 1 короткий вопрос
6. {closing}
7. Хэштеги: {hashtags_str}

ВАЖНЕЙШИЕ ПРАВИЛА:
• АБСОЛЮТНЫЙ МАКСИМУМ: {zen_max} символов
• Если больше {zen_max} - УДАЛИ ЛИШНЕЕ
• Никаких эмодзи в тексте
• Никаких "Длина:" или счетчиков
• Никаких ** вокруг текста
• Короткие предложения, лаконично

ПРИМЕР КОРОТКОГО ПОСТА (примерно {target_length} символов):
Стратегии развития персонала

Эффективное развитие персонала - ключ к успеху. Современный бизнес требует обучения.

HR используют тренинги, менторство, онлайн-курсы. Важно персонализировать программы.

Инвестиции в развитие окупаются производительностью и лояльностью.

Какие методы развития работают у вас?

{closing}
{hashtags_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОЗДАЙ КОРОТКИЙ ПОСТ О ТЕМЕ "{theme}" В ФОРМАТЕ "{text_format}".
МАКСИМУМ {zen_max} СИМВОЛОВ! НИКАКИХ ЭМОДЗИ!

ТВОЙ КОРОТКИЙ ПОСТ:"""

        return prompt

    def clean_generated_text(self, text):
        """Очищает сгенерированный текст от артефактов"""
        if not text:
            return text
        
        # Удаляем строки со счетчиком символов
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Пропускаем строки содержащие "Длина:", "символов", "Символов:"
            if any(keyword in line.lower() for keyword in ['длина:', 'символов', 'символы:', 'количество символов', 'символа', 'текст содержит']):
                continue
            
            # Удаляем ** с начала и конца строки
            stripped_line = line.strip()
            if stripped_line.startswith('**') and stripped_line.endswith('**'):
                cleaned_line = stripped_line[2:-2].strip()
                cleaned_lines.append(cleaned_line)
            else:
                cleaned_lines.append(line)
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Удаляем возможные артефакты
        cleaned_text = re.sub(r'━+$', '', cleaned_text, flags=re.MULTILINE)
        cleaned_text = re.sub(r'=+$', '', cleaned_text, flags=re.MULTILINE)
        
        # Удаляем возможные фразы в конце
        unwanted_endings = [
            'текст готов', 'пост готов', 'готово', 'создано', 
            'вот пост:', 'вот текст:', 'результат:', 'пост:',
            'пример поста:', 'структура поста:'
        ]
        
        for ending in unwanted_endings:
            if cleaned_text.lower().endswith(ending.lower()):
                cleaned_text = cleaned_text[:-len(ending)].strip()
        
        return cleaned_text.strip()

    def _aggressive_rewrite(self, text, target_min, target_max, text_type, current_length):
        """
        Агрессивная перезапись для Дзен постов
        """
        logger.info(f"🔥 Агрессивная перезапись {text_type}: {current_length} → {target_min}-{target_max}")
        
        excess = current_length - target_max
        
        rewrite_prompt = f"""СДЕЛАЙ ЭТОТ ТЕКСТ КОРОЧЕ. УДАЛИ {excess} СИМВОЛОВ.

ТЕКСТ:
{text}

ЗАДАЧА:
• Сделай текст короче на {excess} символов
• Удали повторы и лишние слова
• Сохрани основную мысль
• Сделай предложения короче
• Не трогай заголовок, вопрос и хэштеги
• Итог: {target_max} символов МАКСИМУМ

ПРАВИЛА СОКРАЩЕНИЯ:
1. Объедини похожие предложения
2. Удали вводные слова ("итак", "таким образом")
3. Сократи длинные описания
4. Удали избыточные прилагательные
5. Оставь только суть

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СОКРАЩЕННЫЙ ТЕКСТ (максимум {target_max} символов):"""
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": rewrite_prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,  # Очень низкая для точного сокращения
                    "topP": 0.3,
                    "topK": 20,
                    "maxOutputTokens": int(target_max * 1.1),
                }
            }
            
            response = session.post(url, json=data, timeout=50)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    rewritten_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    rewritten_text = self.clean_generated_text(rewritten_text)
                    new_len = len(rewritten_text)
                    
                    logger.info(f"📊 После агрессивной перезаписи: {new_len} символов")
                    
                    if target_min <= new_len <= target_max:
                        logger.info(f"✅ {text_type} успешно сокращен")
                        return rewritten_text
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при агрессивной перезаписи: {str(e)[:100]}")
            return None

    def generate_with_retry(self, prompt, target_min, target_max, post_type, max_attempts=3):
        """Генерация поста с повторными попытками"""
        for attempt in range(max_attempts):
            try:
                logger.info(f"🤖 Попытка {attempt+1}/{max_attempts}: {post_type}")
                
                # Для Дзена используем более низкую температуру
                temperature = 0.2 if "Дзен" in post_type else 0.3
                max_tokens = int(target_max * 1.2)  # Меньше токенов для контроля длины
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature,
                        "topP": 0.5 if "Дзен" in post_type else 0.7,
                        "topK": 30 if "Дзен" in post_type else 40,
                        "maxOutputTokens": max_tokens,
                    }
                }
                
                response = session.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                        generated_text = self.clean_generated_text(generated_text)
                        length = len(generated_text)
                        
                        logger.info(f"📊 Сгенерировано: {length} символов (нужно {target_min}-{target_max})")
                        
                        # Если сразу попало в диапазон - отлично!
                        if target_min <= length <= target_max:
                            logger.info(f"✅ {post_type} соответствует длине!")
                            return generated_text
                        
                        # Если Дзен пост слишком длинный - агрессивная перезапись
                        if "Дзен" in post_type and length > target_max and attempt < max_attempts - 1:
                            logger.info(f"🔥 Дзен слишком длинный, агрессивно сокращаем...")
                            rewritten = self._aggressive_rewrite(
                                generated_text,
                                target_min,
                                target_max,
                                post_type,
                                length
                            )
                            
                            if rewritten:
                                rewritten_len = len(rewritten)
                                if target_min <= rewritten_len <= target_max:
                                    logger.info(f"✅ Дзен успешно сокращен: {rewritten_len} символов")
                                    return rewritten
                
                # Пауза между попытками
                if attempt < max_attempts - 1:
                    wait_time = 2 * (attempt + 1)
                    logger.info(f"⏳ Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при генерации {post_type}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(3)
        
        logger.error(f"❌ Не удалось сгенерировать {post_type} нужной длины за {max_attempts} попыток")
        return None

    def get_post_image(self, theme):
        """Находит подходящую картинку через Pexels API"""
        try:
            theme_queries = {
                "ремонт и строительство": ["construction", "renovation", "architecture", "building"],
                "HR и управление персоналом": ["office", "business", "teamwork", "meeting"],
                "PR и коммуникации": ["communication", "marketing", "networking", "social"]
            }
            
            queries = theme_queries.get(theme, ["business", "work", "success"])
            query = random.choice(queries)
            
            logger.info(f"🔍 Ищем картинку в Pexels по запросу: '{query}'")
            
            url = "https://api.pexels.com/v1/search"
            params = {
                "query": query,
                "per_page": 10,
                "orientation": "landscape",
                "size": "large"
            }
            
            headers = {
                "Authorization": PEXELS_API_KEY
            }
            
            response = session.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                photos = data.get("photos", [])
                
                if photos:
                    logger.info(f"📸 Найдено {len(photos)} фото в Pexels")
                    photo = random.choice(photos)
                    image_url = photo.get("src", {}).get("large", "")
                    
                    if image_url:
                        logger.info(f"🖼️ Используем картинку из Pexels: {image_url[:80]}...")
                        return image_url
                else:
                    logger.warning("⚠️ Pexels не вернул фотографий по запросу")
            else:
                logger.error(f"❌ Pexels API ошибка: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске картинки в Pexels: {e}")
        
        logger.info("🔄 Pexels не сработал, пробуем Unsplash...")
        try:
            encoded_query = quote_plus(query)
            unsplash_url = f"https://source.unsplash.com/featured/1200x630/?{encoded_query}"
            
            response = session.head(unsplash_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                image_url = response.url
                logger.info(f"🖼️ Используем картинку из Unsplash: {image_url[:80]}...")
                return image_url
        except Exception as unsplash_error:
            logger.error(f"❌ Unsplash тоже не сработал: {unsplash_error}")
        
        default_image = "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&h=630&fit=crop"
        logger.info(f"🖼️ Используем дефолтную картинку")
        return default_image

    def format_telegram_text(self, text, slot_info):
        """Форматирует текст для Telegram"""
        if not text:
            return None
        
        text = text.strip()
        text = self.clean_generated_text(text)
        
        # Добавляем стартовый эмодзи слота если его нет
        if not text.startswith(slot_info['emoji']):
            lines = text.split('\n')
            if lines and lines[0].strip():
                lines[0] = f"{slot_info['emoji']} {lines[0]}"
                text = '\n'.join(lines)
        
        # Проверяем длину
        tg_min, tg_max = slot_info['tg_chars']
        text_length = len(text)
        
        if text_length < tg_min:
            logger.error(f"❌ Telegram текст слишком короткий: {text_length} < {tg_min}")
            return None
        
        if text_length > tg_max:
            logger.error(f"❌ Telegram текст слишком длинный: {text_length} > {tg_max}")
            return None
        
        logger.info(f"✅ Telegram: {text_length} символов ({tg_min}-{tg_max})")
        return text

    def format_zen_text(self, text, slot_info):
        """Форматирует текст для Дзен"""
        if not text:
            return None
        
        text = text.strip()
        text = self.clean_generated_text(text)
        
        # Проверяем длину
        zen_min, zen_max = slot_info['zen_chars']
        text_length = len(text)
        
        if text_length < zen_min:
            logger.error(f"❌ Дзен текст слишком короткий: {text_length} < {zen_min}")
            return None
        
        if text_length > zen_max:
            logger.error(f"❌ Дзен текст слишком длинный: {text_length} > {zen_max}")
            return None
        
        logger.info(f"✅ Дзен: {text_length} символов ({zen_min}-{zen_max})")
        return text

    def publish_directly(self, slot_time, tg_text, zen_text, image_url, theme):
        """Публикует посты напрямую в каналы"""
        logger.info("📤 Публикую посты напрямую в каналы...")
        
        success_count = 0
        
        logger.info(f"📨 Отправляем в ОСНОВНОЙ КАНАЛ: {MAIN_CHANNEL_ID}")
        if self.send_telegram_post(MAIN_CHANNEL_ID, tg_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {MAIN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {MAIN_CHANNEL_ID}")
        
        time.sleep(2)
        
        logger.info(f"📨 Отправляем в ДЗЕН КАНАЛ: {ZEN_CHANNEL_ID}")
        if self.send_telegram_post(ZEN_CHANNEL_ID, zen_text, image_url):
            success_count += 1
            logger.info(f"✅ Успешно отправлено в {ZEN_CHANNEL_ID}")
        else:
            logger.error(f"❌ Не удалось отправить в {ZEN_CHANNEL_ID}")
        
        if ADMIN_CHAT_ID and success_count > 0:
            self.send_admin_notification(slot_time, theme, success_count)
        
        return success_count

    def send_admin_notification(self, slot_time, theme, success_count):
        """Отправляет уведомление администратору"""
        try:
            notification = (
                f"✅ <b>Посты опубликованы автоматически</b>\n\n"
                f"🎯 <b>Тема:</b> {theme}\n"
                f"🕒 <b>Время слота:</b> {slot_time} МСК\n"
                f"📊 <b>Успешно опубликовано:</b> {success_count}/2 каналов\n\n"
                f"📢 Каналы:\n"
                f"• {MAIN_CHANNEL_ID}\n"
                f"• {ZEN_CHANNEL_ID}"
            )
            
            params = {
                'chat_id': ADMIN_CHAT_ID,
                'text': notification,
                'parse_mode': 'HTML',
                'disable_notification': False
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"📨 Уведомление отправлено администратору")
                return True
            else:
                logger.warning(f"⚠️ Не удалось отправить уведомление администратору")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")
            return False

    def send_telegram_post(self, chat_id, text, image_url):
        """Отправляет пост в Telegram канал"""
        try:
            logger.info(f"📤 Отправляем пост в {chat_id}")
            
            if not text or len(text.strip()) < 50:
                logger.error(f"❌ Текст слишком короткий")
                return False
            
            # Сначала пробуем с картинкой
            try:
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
            except Exception as photo_error:
                logger.warning(f"⚠️ Ошибка отправки с картинкой: {photo_error}")
            
            # Если с картинкой не вышло, пробуем текстом
            logger.warning(f"⚠️ Пробуем отправить текстовый пост в {chat_id}")
            
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
            
            logger.error(f"❌ Не удалось отправить пост в {chat_id}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке в {chat_id}: {e}")
            return False

    def create_and_send_posts(self, slot_time, slot_info, is_test=False, force_send=False):
        """Генерирует и отправляет посты"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_info['name']}")
            logger.info(f"📏 Лимиты: Telegram {slot_info['tg_chars'][0]}-{slot_info['tg_chars'][1]}, Дзен {slot_info['zen_chars'][0]}-{slot_info['zen_chars'][1]}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format()
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            tg_min, tg_max = slot_info['tg_chars']
            zen_min, zen_max = slot_info['zen_chars']
            
            # ШАГ 1: Генерация Telegram поста
            logger.info("\n📱 ГЕНЕРАЦИЯ TELEGRAM ПОСТА")
            tg_prompt = self.create_telegram_prompt(theme, slot_info, text_format)
            tg_text = self.generate_with_retry(tg_prompt, tg_min, tg_max, "Telegram пост", max_attempts=3)
            
            if not tg_text:
                logger.error("❌ Не удалось сгенерировать Telegram пост")
                return False
            
            tg_formatted = self.format_telegram_text(tg_text, slot_info)
            if not tg_formatted:
                logger.error("❌ Telegram текст не прошел проверку")
                return False
            
            tg_length = len(tg_formatted)
            logger.info(f"✅ Telegram готов: {tg_length} символов")
            
            # ШАГ 2: Генерация Дзен поста
            logger.info("\n📰 ГЕНЕРАЦИЯ ДЗЕН ПОСТА")
            zen_prompt = self.create_zen_prompt(theme, slot_info, text_format)
            zen_text = self.generate_with_retry(zen_prompt, zen_min, zen_max, "Дзен пост", max_attempts=4)  # Больше попыток для Дзен
            
            if not zen_text:
                logger.error("❌ Не удалось сгенерировать Дзен пост")
                return False
            
            zen_formatted = self.format_zen_text(zen_text, slot_info)
            if not zen_formatted:
                logger.error("❌ Дзен текст не прошел проверку")
                return False
            
            zen_length = len(zen_formatted)
            logger.info(f"✅ Дзен готов: {zen_length} символов")
            
            # ФИНАЛЬНАЯ ПРОВЕРКА
            logger.info(f"\n🔴 ФИНАЛЬНАЯ ПРОВЕРКА:")
            
            tg_ok = tg_min <= tg_length <= tg_max
            zen_ok = zen_min <= zen_length <= zen_max
            
            logger.info(f"   Telegram: {tg_length} символов ({tg_min}-{tg_max}) {'✅' if tg_ok else '❌'}")
            logger.info(f"   Дзен: {zen_length} символов ({zen_min}-{zen_max}) {'✅' if zen_ok else '❌'}")
            
            if not tg_ok or not zen_ok:
                logger.error("❌ Тексты не соответствуют лимитам")
                return False
            
            logger.info("🖼️ Подбираем картинку...")
            image_url = self.get_post_image(theme)
            
            if not is_test:
                logger.info("📤 ПУБЛИКУЮ ПОСТЫ НАПРЯМУЮ В КАНАЛЫ")
                success_count = self.publish_directly(slot_time, tg_formatted, zen_formatted, image_url, theme)
            else:
                logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ - публикация пропущена")
                success_count = 1
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                logger.info(f"📝 Информация сохранена в историю")
            
            if success_count >= 1:
                logger.info(f"\n🎉 УСПЕХ! Отправлено постов: {success_count}/2")
                logger.info(f"   🕒 Время: {slot_time} МСК")
                logger.info(f"   🎯 Тема: {theme} (ротация активна)")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Telegram: {tg_length} символов ({tg_min}-{tg_max} ✅)")
                logger.info(f"   📏 Дзен: {zen_length} символов ({zen_min}-{zen_max} ✅)")
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
        
        current_hour = now.hour
        
        if 5 <= current_hour < 12:
            slot_time = "09:00"
        elif 12 <= current_hour < 17:
            slot_time = "14:00"
        else:
            slot_time = "19:00"
        
        slot_info = self.schedule[slot_time]
        print(f"📅 Найден слот для отправки: {slot_time} - {slot_info['name']}")
        print(f"📏 Лимиты: Telegram {slot_info['tg_chars'][0]}-{slot_info['tg_chars'][1]} символов")
        print(f"📏 Лимиты: Дзен {slot_info['zen_chars'][0]}-{slot_info['zen_chars'][1]} символов")
        print(f"🎯 Система ротации тем: одинаковые темы не будут идти подряд")
        print(f"🔄 Пошаговая генерация с умной корректировкой")
        print(f"🔖 Релевантные хэштеги для каждой темы")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=False)
        
        if success:
            print(f"✅ Посты опубликованы в каналы в {slot_time} МСК")
        else:
            print(f"❌ Ошибка публикации постов")
        
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
        print(f"📝 Выбран слот: {slot_time} - {slot_info['name']}")
        
        success = self.create_and_send_posts(slot_time, slot_info, is_test=True)
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ТЕСТ ПРОЙДЕН! Текст соответствует лимитам.")
        else:
            print("❌ ТЕСТ ПРОВАЛЕН (текст не соответствует лимитам)")
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
