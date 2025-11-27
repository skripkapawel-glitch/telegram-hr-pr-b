import os
import requests
import datetime
import hashlib
import json
import random
import re
import time
from difflib import SequenceMatcher
from collections import Counter
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Файл для хранения хешей постов
HISTORY_FILE = "post_history.json"

class TelegramPostGenerator:
    def __init__(self):
        self.history = self.load_post_history()
        self.session_start = datetime.datetime.now()
        
        # Расширенные темы и форматы
        self.all_themes = [
            "HR и управление персоналом", "PR и коммуникации", "ремонт и строительство",
            "цифровая трансформация", "удаленная работа", "корпоративная культура",
            "лидерство и менеджмент", "инновации в бизнесе", "клиентский опыт",
            "стратегическое планирование", "управление проектами", "маркетинг и продажи",
            "финансы и инвестиции", "технологии и AI", "устойчивое развитие"
        ]
        
        self.post_formats = [
            "🔥 {content}", "🎯 {content}", "💡 {content}", "🚀 {content}", 
            "🤯 {content}", "💎 {content}", "🌟 {content}", "📈 {content}",
            "🎨 {content}", "⚡ {content}", "🧠 {content}", "💼 {content}"
        ]
        
        self.calls_to_action = [
            "🔥 Поделись с другом, если полезно!",
            "💬 Что думаешь? Напиши в комментах!",
            "🔄 Репостни, если согласен!",
            "👥 Покажи коллегам – обсудим вместе!",
            "💎 Сохрани себе на стену!",
            "🚀 Поделись мнением в комментариях!",
            "📌 Сохрани для вдохновения!",
            "🤝 Поделись опытом в комментариях!"
        ]

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            print(f"⚠️ Ошибка загрузки истории: {e}")
        
        return {
            "post_hashes": [],
            "used_themes": [],
            "used_formats": [],
            "used_images": [],
            "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d'),
            "channel_analysis": {
                "common_words": [],
                "recent_themes": [],
                "post_patterns": []
            }
        }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def get_telegram_channel_posts(self, limit=50):
        """Получает реальные посты из Telegram канала"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatHistory"
            payload = {
                "chat_id": CHANNEL_ID,
                "limit": limit
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            if data.get("ok") and data.get("result"):
                for message in data["result"]:
                    content = ""
                    if "text" in message:
                        content = message["text"]
                    elif "caption" in message:
                        content = message["caption"]
                    
                    if content and len(content.strip()) > 50:  # Только значимые посты
                        posts.append({
                            "content": content,
                            "date": message.get("date", ""),
                            "message_id": message.get("message_id")
                        })
            
            print(f"📊 Получено {len(posts)} постов из канала для анализа")
            return posts
            
        except Exception as e:
            print(f"⚠️ Ошибка получения постов из канала: {e}")
            return []

    def analyze_channel_content(self, posts):
        """Анализирует контент канала для избежания повторений"""
        if not posts:
            return {
                "common_words": [],
                "recent_themes": [],
                "avoid_patterns": [],
                "recent_formats": []
            }
        
        # Анализ частых слов
        all_text = " ".join([post["content"] for post in posts])
        words = re.findall(r'\b[а-яa-z]{4,}\b', all_text.lower())
        
        # Стоп-слова
        stop_words = {
            'этот', 'это', 'также', 'очень', 'можно', 'будет', 'есть', 'если', 'чтобы',
            'который', 'только', 'после', 'когда', 'потому', 'может', 'свой', 'ваш',
            'наш', 'их', 'его', 'её', 'им', 'ими', 'них', 'нами', 'вами', 'такой'
        }
        
        word_freq = Counter([word for word in words if word not in stop_words])
        common_words = [word for word, count in word_freq.most_common(20)]
        
        # Анализ форматов
        recent_formats = []
        for post in posts[:10]:
            content = post["content"]
            if "🔥" in content: recent_formats.append("🔥")
            if "🎯" in content: recent_formats.append("🎯")
            if "💡" in content: recent_formats.append("💡")
            if "🚀" in content: recent_formats.append("🚀")
        
        analysis = {
            "common_words": common_words,
            "recent_themes": self.extract_themes(posts),
            "avoid_patterns": self.find_common_patterns(posts),
            "recent_formats": list(set(recent_formats))[:5]
        }
        
        # Сохраняем анализ в историю
        self.history["channel_analysis"] = analysis
        self.save_post_history()
        
        return analysis

    def extract_themes(self, posts):
        """Извлекает темы из постов"""
        themes = []
        theme_keywords = {
            'hr': ['персонал', 'сотрудник', 'команда', 'hr', 'рекрутинг'],
            'pr': ['коммуникация', 'pr', 'публичный', 'бренд', 'репутация'],
            'строительство': ['ремонт', 'строитель', 'проект', 'объект', 'ремонт'],
            'управление': ['управлен', 'менеджмент', 'лидер', 'руководств'],
            'технологии': ['технолог', 'digital', 'ai', 'инновац', 'автоматизац']
        }
        
        for post in posts[:15]:
            content_lower = post["content"].lower()
            for theme, keywords in theme_keywords.items():
                if any(keyword in content_lower for keyword in keywords):
                    if theme not in themes:
                        themes.append(theme)
        
        return themes[:5]

    def find_common_patterns(self, posts):
        """Находит часто используемые паттерны в постах"""
        patterns = []
        
        for post in posts[:10]:
            content = post["content"]
            
            # Поиск паттернов типа "X способов сделать Y"
            ways_pattern = re.findall(r'(\d+)\s*(способ|шаг|метод|совет)', content.lower())
            if ways_pattern:
                patterns.append("number_ways")
            
            # Паттерны с вопросами
            if '?' in content and any(word in content.lower() for word in ['как', 'что', 'почему', 'когда']):
                patterns.append("question_pattern")
            
            # Паттерны со статистикой
            stat_pattern = re.findall(r'(\d+%)', content)
            if stat_pattern:
                patterns.append("statistic_pattern")
        
        return list(set(patterns))

    def calculate_similarity(self, text1, text2):
        """Вычисляет схожесть между двумя текстами"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def is_content_unique(self, content, recent_posts, similarity_threshold=0.65):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Проверка по хешу
        if content_hash in self.history["post_hashes"]:
            print("❌ Пост не уникален: одинаковый хеш")
            return False
        
        # Проверка схожести с локальной историей
        for old_hash in self.history["post_hashes"][-20:]:
            if old_hash == content_hash:
                return False
        
        # Проверка схожести с реальными постами из канала
        for post in recent_posts[:15]:
            similarity = self.calculate_similarity(content, post["content"])
            if similarity > similarity_threshold:
                print(f"❌ Схожесть с существующим постом: {similarity:.2f}")
                return False
        
        # Проверка на минимальную длину
        words = content.split()
        if len(words) < 25:
            print("⚠️ Пост слишком короткий, но принимаем")
        
        return True

    def get_unique_theme(self):
        """Выбирает уникальную тему"""
        # Исключаем недавно использованные темы
        recent_themes = self.history.get("used_themes", [])[-5:]
        available_themes = [theme for theme in self.all_themes if theme not in recent_themes]
        
        if not available_themes:
            available_themes = self.all_themes
        
        selected_theme = random.choice(available_themes)
        return selected_theme

    def get_unique_format(self):
        """Выбирает уникальный формат"""
        recent_formats = self.history.get("used_formats", [])[-3:]
        available_formats = [fmt for fmt in self.post_formats if fmt not in recent_formats]
        
        if not available_formats:
            available_formats = self.post_formats
        
        return random.choice(available_formats)

    def get_unique_image(self, attempt=1):
        """Генерирует уникальную картинку"""
        if attempt > 3:
            timestamp = int(time.time() * 1000)
            return f"https://picsum.photos/1200/800?random={timestamp}"
        
        timestamp = int(time.time() * 1000) + attempt
        image_hash = hashlib.md5(str(timestamp).encode()).hexdigest()[:12]
        image_url = f"https://picsum.photos/1200/800?random={image_hash}"
        
        # Проверяем, что картинка не использовалась
        if image_hash not in self.history.get("used_images", [])[-10:]:
            return image_url
        else:
            return self.get_unique_image(attempt + 1)

    def create_ai_prompt(self, theme, time_of_day, channel_analysis, config):
        """Создает умный промпт для ИИ с учетом анализа канала"""
        
        common_words = ", ".join(channel_analysis.get("common_words", [])[:8])
        recent_themes = ", ".join(channel_analysis.get("recent_themes", [])[:3])
        avoid_patterns = channel_analysis.get("avoid_patterns", [])
        recent_formats = ", ".join(channel_analysis.get("recent_formats", [])[:3])
        
        avoid_patterns_text = ""
        if "number_ways" in avoid_patterns:
            avoid_patterns_text += "• Избегай шаблонов 'X способов сделать Y'\n"
        if "question_pattern" in avoid_patterns:
            avoid_patterns_text += "• Не начинай с вопросов 'Как сделать...'\n"
        if "statistic_pattern" in avoid_patterns:
            avoid_patterns_text += "• Не используй шаблонную статистику\n"
        
        prompt = f"""
СОЗДАЙ АБСОЛЮТНО УНИКАЛЬНЫЙ ВИРАЛЬНЫЙ ПОСТ ДЛЯ TELEGRAM

АНАЛИЗ КАНАЛА ПОКАЗАЛ:
• Часто используемые слова: {common_words}
• Недавние темы: {recent_themes}
• Использованные форматы: {recent_formats}

ТРЕБОВАНИЯ К УНИКАЛЬНОСТИ:
1. ИЗБЕГАЙ этих слов: {common_words}
2. НЕ ИСПОЛЬЗУЙ эти темы: {recent_themes}
3. Создай СОВЕРШЕННО НОВЫЙ подход
{avoid_patterns_text}
4. Используй свежие данные 2024-2025 года

ОСНОВНАЯ ТЕМА: {theme}
ВРЕМЯ СУТОК: {time_of_day}
ЦЕЛЕВАЯ ДЛИНА: {config['ideal_length']}-{config['max_tokens']} символов

СТРУКТУРА (выбери НОВУЮ):
• Проблема → Исследование → Решение → Действие
• Тренд → Анализ → Кейс → Рекомендация
• Миф → Факты → Доказательства → Вывод
• Вызов → Стратегия → Результаты → Инсайт

СТИЛЬ И ФОРМАТ:
• Естественный разговорный язык
• Эмодзи для эмоционального акцента
• Короткие абзацы для читабельности
• Конкретные примеры и цифры
• Призыв к обсуждению

ПРИМЕРЫ УНИКАЛЬНЫХ УГЛОВ:
Вместо "Эффективная коммуникация" → "Нейролингвистика: как слова меняют химию мозга в переговорах"
Вместо "Управление командой" → "Биомиметика лидерства: чему бизнес может научиться у природы"

КОНТРОЛЬНЫЙ СПИСОК УНИКАЛЬНОСТИ:
□ Используются ли запрещенные слова?
□ Похож ли подход на недавние посты?
□ Достаточно ли свежая информация?
□ Вызывает ли пост искренний интерес?

ЦЕЛЬ: Создать контент, которым захочется поделиться немедленно!
"""

        return prompt

    def generate_post_content(self, time_of_day, attempt=1):
        """Генерирует уникальный контент поста"""
        try:
            # Получаем данные из канала
            channel_posts = self.get_telegram_channel_posts(limit=50)
            channel_analysis = self.analyze_channel_content(channel_posts)
            
            # Очищаем историю при новом дне
            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            if self.history.get("last_reset_date") != current_date:
                self.history["used_formats"] = []
                self.history["used_themes"] = []
                self.history["last_reset_date"] = current_date
                self.save_post_history()
                print("🔄 История очищена (новый день)")
            
            # Настройки длины
            length_config = {
                "morning": {"max_tokens": 600, "ideal_length": 400},
                "afternoon": {"max_tokens": 1200, "ideal_length": 800}, 
                "evening": {"max_tokens": 500, "ideal_length": 300}
            }
            config = length_config.get(time_of_day, length_config["afternoon"])
            
            # Выбираем уникальные тему и формат
            theme = self.get_unique_theme()
            post_format = self.get_unique_format()
            call_to_action = random.choice(self.calls_to_action)
            
            # Создаем промпт
            prompt = self.create_ai_prompt(theme, time_of_day, channel_analysis, config)
            
            print(f"🧠 Генерация поста ({theme})... Попытка {attempt}")
            print(f"🎯 Избегаем: {', '.join(channel_analysis.get('common_words', [])[:3])}")
            
            # Запрос к Gemini API
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": config["max_tokens"],
                        "temperature": 0.95,
                        "topP": 0.9,
                        "topK": 50
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Добавляем призыв к действию
                post_text += f"\n\n{call_to_action}"
                
                # Проверяем уникальность
                if self.is_content_unique(post_text, channel_posts):
                    # Форматируем и возвращаем результат
                    formatted_text = post_format.format(content=post_text)
                    image_url = self.get_unique_image()
                    
                    # Сохраняем в историю
                    self.mark_post_used(post_text, theme, post_format, image_url)
                    
                    print(f"✅ Уникальный пост создан! ({len(post_text)} символов)")
                    return formatted_text, image_url, theme
                else:
                    print(f"🔄 Пост не уникален, пробуем снова... ({attempt}/3)")
                    if attempt < 3:
                        return self.generate_post_content(time_of_day, attempt + 1)
                    else:
                        return self.get_emergency_post(channel_analysis)
            else:
                print(f"❌ Ошибка API: {response.status_code}")
                raise Exception(f"API error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            if attempt < 2:
                return self.generate_post_content(time_of_day, attempt + 1)
            else:
                return self.get_emergency_post({})

    def mark_post_used(self, content, theme, post_format, image_url):
        """Сохраняет пост в историю"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        image_hash = hashlib.md5(image_url.encode()).hexdigest()
        
        self.history["post_hashes"].append(content_hash)
        self.history["used_images"].append(image_hash)
        
        if theme not in self.history["used_themes"]:
            self.history["used_themes"].append(theme)
        
        if post_format not in self.history["used_formats"]:
            self.history["used_formats"].append(post_format)
        
        # Ограничиваем размер истории
        for key in ["post_hashes", "used_themes", "used_formats", "used_images"]:
            if key in self.history and len(self.history[key]) > 500:
                self.history[key] = self.history[key][-500:]
        
        self.save_post_history()

    def get_emergency_post(self, channel_analysis):
        """Создает аварийный уникальный пост"""
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        unique_id = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        
        emergency_posts = [
            f"""🚀 <b>ЭКСКЛЮЗИВ: Уникальный инсайт {timestamp}</b>

Новое исследование показывает: креативность возрастает на 73% при смене подходов!

💡 <b>Факт:</b> Каждая уникальная идея создает новую нейронную связь.
🎯 <b>Действие:</b> Попробуйте сегодня совершенно новый подход к работе.

🔥 <b>Результат гарантирован!</b>

#{unique_id} #Уникальность""",

            f"""💎 <b>МОМЕНТ ИСТИНЫ: {datetime.datetime.now().strftime('%d.%m')}</b>

Секрет успеха: в 2025 году ценность уникального контента выросла на 240%!

🌟 <b>Тренд:</b> Аудитория жаждет свежих идей и неожиданных решений.
🧠 <b>Инсайт:</b> Самые виральные посты нарушают шаблоны.

💬 <b>Что вас сегодня удивило?</b>

#{unique_id} #НовыеГоризонты""",

            f"""🎨 <b>ТВОРЧЕСКИЙ ПРОРЫВ: Генерируем уникальность</b>

Время: {timestamp}
Статус: Создано 100% уникальный контент

⚡ <b>Методология:</b> Анализ трендов + свежий взгляд = виральный эффект
📈 <b>Результат:</b> Этот пост не повторяет предыдущие публикации

🔮 <b>Будущее за уникальными решениями!</b>

#{unique_id} #Эксклюзив"""
        ]
        
        theme = "Экстренная уникальная тема"
        post_format = random.choice(self.post_formats)
        post_text = random.choice(emergency_posts)
        image_url = self.get_unique_image()
        
        self.mark_post_used(post_text, theme, post_format, image_url)
        
        return post_text, image_url, theme

    def send_to_telegram(self, message, image_url=None):
        """Отправляет пост в Telegram"""
        try:
            if image_url:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": message,
                    "parse_mode": "HTML"
                }
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            print("✅ Пост успешно отправлен в Telegram!")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")
            return False

    def run(self):
        """Основная функция запуска"""
        try:
            now = datetime.datetime.now()
            current_hour = now.hour
            
            print(f"\n{'='*60}")
            print(f"🚀 Запуск генератора постов")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"{'='*60}")
            
            # Определяем время суток
            time_mapping = {
                6: "morning",   # 9:00 МСК
                11: "afternoon", # 14:00 МСК  
                16: "evening"    # 19:00 МСК
            }
            time_of_day = time_mapping.get(current_hour, "afternoon")
            
            print(f"🎯 Генерация {time_of_day} поста...")
            
            # Генерируем и отправляем пост
            post_text, image_url, theme = self.generate_post_content(time_of_day)
            
            print(f"📝 Тема: {theme}")
            print(f"📊 Длина: {len(post_text)} символов")
            print(f"🖼️ Картинка: {image_url}")
            
            # Отправляем в Telegram
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                print("✅ Процесс завершен успешно!")
                print(f"🔐 Хеш поста: {hashlib.md5(post_text.encode()).hexdigest()[:12]}")
            else:
                print("❌ Ошибка при отправке поста")
            
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Точка входа"""
    generator = TelegramPostGenerator()
    generator.run()

if __name__ == "__main__":
    main()
