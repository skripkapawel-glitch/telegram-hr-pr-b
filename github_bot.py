import os
import requests
import datetime
import hashlib
import json
import random
import time
import re
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "post_history.json"

class ProfessionalPostGenerator:
    def __init__(self):
        print("🔧 Инициализация генератора постов...")
        self.history = self.load_post_history()
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        self.main_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.time_configs = {
            "morning": {"target_chars": 800, "description": "энергичный, мотивирующий, практичный"},
            "afternoon": {"target_chars": 1200, "description": "аналитический, экспертный, информативный"}, 
            "evening": {"target_chars": 1000, "description": "рефлексивный, вдохновляющий, дружеский"}
        }
        
        self.hashtags = {
            "HR и управление персоналом": [
                "#HR", "#рекрутинг", "#управлениеперсоналом", "#мотивация", "#команда",
                "#кадры", "#HRаналитика", "#развитиеперсонала", "#брендработодателя", 
                "#корпоративнаякультура", "#лидерство", "#управление", "#бизнес",
                "#карьера", "#работа", "#2025", "#тренды2025"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#пиар", "#бренд", "#репутация", 
                "#медиа", "#соцсети", "#маркетинг", "#контент", "#SMM",
                "#кризисныекоммуникации", "#брендинг", "#инфлюенсеры",
                "#digital", "#продвижение", "#2025", "#новоевPR"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер", "#квартира",
                "#дом", "#евроремонт", "#стройка", "#материалы", "#технологии",
                "#умныйдом", "#энергоэффективность", "#перепланировка",
                "#недвижимость", "#жилье", "#2025", "#трендыремонта"
            ]
        }
        print("✅ Генератор инициализирован")

    def load_post_history(self):
        """Загружает историю и сразу обновляет файл"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                print("✅ История загружена")
            else:
                history = {
                    "post_hashes": [],
                    "daily_posts": {},
                    "channel_analysis": {},
                    "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
                }
                print("✅ Создана новая история")
            
            # Очищаем старые данные (больше 7 дней)
            self.clean_old_history(history)
            return history
            
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {
                "post_hashes": [],
                "daily_posts": {},
                "channel_analysis": {},
                "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')
            }

    def clean_old_history(self, history):
        """Очищает историю старше 7 дней"""
        today = datetime.datetime.now()
        dates_to_remove = []
        
        for date_str in history.get("daily_posts", {}):
            try:
                post_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                if (today - post_date).days > 7:
                    dates_to_remove.append(date_str)
            except:
                continue
        
        for date_str in dates_to_remove:
            del history["daily_posts"][date_str]

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            print("✅ История сохранена")
        except Exception as e:
            print(f"❌ Ошибка сохранения истории: {e}")

    def get_time_of_day(self):
        current_hour = datetime.datetime.now().hour
        if 6 <= current_hour < 12:
            return "morning"
        elif 12 <= current_hour < 18:
            return "afternoon"
        else:
            return "evening"

    def get_channel_posts(self, limit=50):
        """Получает посты из Telegram канала"""
        print("📊 Анализируем посты в канале...")
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatHistory"
            payload = {
                "chat_id": CHANNEL_ID,
                "limit": limit
            }
            
            print(f"🔗 Запрос к Telegram API: {url}")
            print(f"📝 Параметры: {payload}")
            
            response = requests.post(url, json=payload, timeout=10)
            print(f"📡 Статус ответа: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            print(f"📊 Ответ от Telegram: {data.get('ok', False)}")
            
            posts = []
            
            if data.get("ok") and data.get("result"):
                for message in data["result"]:
                    content = ""
                    if "text" in message:
                        content = message["text"]
                    elif "caption" in message:
                        content = message["caption"]
                    
                    if content and len(content.strip()) > 30:
                        posts.append({
                            "content": content,
                            "date": message.get("date", ""),
                            "message_id": message.get("message_id")
                        })
            
            print(f"✅ Получено {len(posts)} постов из канала")
            return posts
            
        except requests.exceptions.Timeout:
            print("❌ Таймаут при получении постов из канала")
            return []
        except Exception as e:
            print(f"❌ Ошибка получения постов: {e}")
            return []

    def analyze_channel_content(self, posts):
        """Анализирует контент канала"""
        if not posts:
            print("ℹ️ В канале нет постов для анализа")
            return {
                "used_themes": [],
                "frequent_words": [],
                "post_frequency": {}
            }
        
        analysis = {
            "used_themes": [],
            "frequent_words": [],
            "post_frequency": {}
        }
        
        all_content = " ".join([post["content"] for post in posts])
        
        # Анализ тем
        for theme in self.main_themes:
            theme_keywords = self.get_theme_keywords(theme)
            for keyword in theme_keywords:
                if keyword in all_content.lower():
                    if theme not in analysis["used_themes"]:
                        analysis["used_themes"].append(theme)
                    break
        
        print(f"📋 Найдены темы в канале: {analysis['used_themes']}")
        return analysis

    def get_theme_keywords(self, theme):
        """Ключевые слова для определения темы"""
        keywords = {
            "HR и управление персоналом": [
                "hr", "персонал", "сотрудник", "команда", "рекрутинг", "найм",
                "мотивация", "обучение", "развитие", "кадр", "hrbp", "kpi"
            ],
            "PR и коммуникации": [
                "pr", "коммуникация", "бренд", "репутац", "медиа", "пиар",
                "публичный", "сми", "информация", "комьюнити"
            ],
            "ремонт и строительство": [
                "ремонт", "строитель", "квартир", "дом", "дизайн", "интерьер",
                "отделк", "материал", "проект", "ремонт", "строит", "объект"
            ]
        }
        return keywords.get(theme, [])

    def select_optimal_theme(self, channel_analysis):
        """Выбирает оптимальную тему на основе анализа канала"""
        used_themes = channel_analysis.get("used_themes", [])
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Сразу обновляем историю перед выбором темы
        self.history = self.load_post_history()
        
        # Учитываем посты за сегодня
        today_posts = self.history.get("daily_posts", {}).get(today, [])
        
        print(f"📅 Сегодня уже были темы: {today_posts}")
        
        # Доступные темы (которые еще не использовались сегодня)
        available_themes = [theme for theme in self.main_themes if theme not in today_posts]
        
        if available_themes:
            # Выбираем из доступных тем ту, что реже всего использовалась в истории
            theme_counts = {}
            for theme in available_themes:
                theme_counts[theme] = used_themes.count(theme)
            
            min_count = min(theme_counts.values()) if theme_counts else 0
            best_themes = [theme for theme, count in theme_counts.items() if count == min_count]
            selected_theme = random.choice(best_themes) if best_themes else random.choice(available_themes)
        else:
            # Если все темы уже использовались сегодня, выбираем случайную
            selected_theme = random.choice(self.main_themes)
        
        print(f"🎯 Выбрана тема: {selected_theme}")
        return selected_theme

    def generate_thematic_image(self, theme):
        """Генерирует тематическое изображение"""
        theme_keywords = {
            "HR и управление персоналом": "business,team,office,professional,meeting",
            "PR и коммуникации": "media,communication,social,network,marketing",
            "ремонт и строительство": "construction,design,architecture,home,renovation"
        }
        
        keywords = theme_keywords.get(theme, "business,development")
        timestamp = int(time.time() * 1000)
        
        image_url = f"https://picsum.photos/1200/800?random={timestamp}&blur=1"
        print(f"🖼️ Сгенерировано изображение: {image_url}")
        return image_url

    def add_hashtags(self, post_text, theme):
        """Добавляет релевантные хештеги к посту"""
        theme_hashtags = self.hashtags.get(theme, [])
        
        # Выбираем 5-7 самых релевантных хештегов
        selected_hashtags = random.sample(theme_hashtags, min(7, len(theme_hashtags)))
        
        hashtags_string = " ".join(selected_hashtags)
        
        # Добавляем хештеги в конец поста
        return f"{post_text}\n\n{hashtags_string}"

    def generate_ai_post_with_retry(self, theme, time_of_day, max_attempts=3):
        """Генерирует пост через ИИ с повторными попытками"""
        tone = self.time_configs[time_of_day]["description"]
        
        prompt = f"""
        Создай уникальный пост для Telegram на тему: {theme}
        Тон: {tone}
        Время суток: {time_of_day}

        Структура:
        1. Цепляющий заголовок с эмодзи
        2. Краткое введение в проблему
        3. Ключевой инсайт
        4. 4 практических совета списком
        5. Реальный кейс
        6. Сильный вывод
        7. Вопрос для обсуждения

        Требования:
        - Уникальный контент
        - Конкретные цифры 2024-2025
        - Практическая польза
        - Естественный язык
        - Без хештегов
        """

        for attempt in range(max_attempts):
            print(f"🧠 Попытка {attempt + 1}: Генерируем пост через Gemini...")
            
            try:
                url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                print(f"🔗 Запрос к Gemini API...")
                
                response = requests.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": 1500,
                            "temperature": 0.9,
                        }
                    },
                    timeout=30
                )
                
                print(f"📡 Статус ответа Gemini: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print("✅ Успешный ответ от Gemini")
                    
                    if "candidates" in data and len(data["candidates"]) > 0:
                        post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        print(f"📝 Длина сгенерированного текста: {len(post_text)} символов")
                        
                        if post_text and len(post_text) > 100:
                            # Проверяем уникальность
                            if self.is_content_unique(post_text):
                                # Добавляем хештеги к сгенерированному посту
                                post_with_hashtags = self.add_hashtags(post_text, theme)
                                print("✅ Уникальный пост сгенерирован успешно через ИИ")
                                return post_with_hashtags
                            else:
                                print("⚠️ Пост не уникален, пробуем снова...")
                                continue
                        else:
                            print("❌ Пустой или слишком короткий ответ от Gemini")
                            continue
                    else:
                        print("❌ Нет candidates в ответе Gemini")
                        continue
                else:
                    print(f"❌ Ошибка Gemini API: {response.status_code}")
                    print(f"📄 Текст ответа: {response.text}")
                    if attempt < max_attempts - 1:
                        time.sleep(2)
                    continue
                    
            except requests.exceptions.Timeout:
                print("❌ Таймаут при генерации поста")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                continue
            except Exception as e:
                print(f"❌ Ошибка генерации: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                continue
        
        print("❌ Не удалось сгенерировать пост через ИИ после всех попыток")
        return None

    def is_content_unique(self, content):
        """Проверяет уникальность контента"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Сразу обновляем историю перед проверкой
        self.history = self.load_post_history()
        
        is_unique = content_hash not in self.history["post_hashes"]
        
        if not is_unique:
            print("⚠️ Обнаружен повторяющийся контент")
        
        return is_unique

    def mark_post_sent(self, content, theme):
        """Сохраняет пост в историю СРАЗУ ЖЕ"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Сначала загружаем актуальную историю
        self.history = self.load_post_history()
        
        # Добавляем данные
        self.history["post_hashes"].append(content_hash)
        
        if today not in self.history["daily_posts"]:
            self.history["daily_posts"][today] = []
        
        self.history["daily_posts"][today].append(theme)
        
        # Ограничиваем размер истории
        if len(self.history["post_hashes"]) > 200:
            self.history["post_hashes"] = self.history["post_hashes"][-200:]
        
        # СРАЗУ сохраняем
        self.save_post_history()
        
        print(f"💾 Пост сохранен в историю: {theme}")

    def send_to_telegram(self, message, image_url=None):
        """Отправляет пост в Telegram"""
        print("📤 Отправляем пост в Telegram...")
        
        try:
            if image_url:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": message,
                    "parse_mode": "HTML"
                }
                print(f"🔗 Отправка фото: {url}")
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
                print(f"🔗 Отправка сообщения: {url}")
            
            print(f"📝 Параметры отправки: chat_id={CHANNEL_ID}, длина_текста={len(message)}")
            
            response = requests.post(url, json=payload, timeout=15)
            print(f"📡 Статус ответа Telegram: {response.status_code}")
            
            response.raise_for_status()
            
            result = response.json()
            print(f"📊 Результат отправки: {result.get('ok', False)}")
            
            if result.get('ok'):
                print("✅ Пост успешно отправлен в Telegram!")
                return True
            else:
                print(f"❌ Ошибка в ответе Telegram: {result}")
                return False
            
        except requests.exceptions.Timeout:
            print("❌ Таймаут при отправке в Telegram")
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")
            return False

    def run(self):
        """Основная функция запуска"""
        try:
            print("🚀 Запуск генератора постов...")
            start_time = time.time()
            
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            time_config = self.time_configs[time_of_day]
            
            print(f"\n{'='*60}")
            print(f"🚀 ПРОФЕССИОНАЛЬНЫЙ ГЕНЕРАТОР ПОСТОВ")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"⏰ Время: {time_of_day} ({time_config['description']})")
            print(f"🆔 Сессия: {self.session_id}")
            print(f"{'='*60}")
            
            # Проверяем наличие необходимых переменных
            print("🔍 Проверка переменных окружения...")
            print(f"   BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
            print(f"   CHANNEL_ID: {'✅' if CHANNEL_ID else '❌'}")
            print(f"   GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌'}")
            
            if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_API_KEY]):
                print("💥 Критическая ошибка: отсутствуют необходимые переменные окружения")
                return
            
            # Анализ канала
            posts = self.get_channel_posts()
            channel_analysis = self.analyze_channel_content(posts)
            
            # Выбор темы на основе анализа
            theme = self.select_optimal_theme(channel_analysis)
            
            # Генерация поста ТОЛЬКО через ИИ
            post_text = self.generate_ai_post_with_retry(theme, time_of_day, max_attempts=3)
            
            if not post_text:
                print("💥 НЕУДАЧА: Не удалось сгенерировать пост через ИИ")
                return
            
            # Генерация изображения
            image_url = self.generate_thematic_image(theme)
            
            print(f"📊 Результат генерации:")
            print(f"   Тема: {theme}")
            print(f"   Длина: {len(post_text)} символов")
            print(f"   Время: {time_of_day}")
            
            # Отправка в Telegram
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                # СРАЗУ сохраняем в историю
                self.mark_post_sent(post_text, theme)
                print(f"✅ Готово! Уникальный пост создан и отправлен.")
            else:
                print("❌ Ошибка при отправке в Telegram")
            
            elapsed_time = time.time() - start_time
            print(f"⏱️ Общее время выполнения: {elapsed_time:.2f} секунд")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    print("🤖 Инициализация бота...")
    bot = ProfessionalPostGenerator()
    bot.run()

if __name__ == "__main__":
    main()
