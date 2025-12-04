import os
import requests
import random
import json
import time
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ")
print(f"📅 Telegram (@da4a_hr): 09:00, 14:00, 19:00 (все с фото)")
print(f"📅 Яндекс.Дзен (@tehdzenm): 09:00, 14:00, 19:00 (все без фото)")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Используемые модели Gemini
        self.available_models = [
            "gemini-2.0-flash",      # Основная модель
            "gemini-2.0-flash-lite", # Более легкая версия
            "gemma-3-27b-it",        # Open-weight альтернатива
            "gemini-1.0-pro"         # Старая, но стабильная
        ]
        self.current_model = self.available_models[0]
        
        # Расписание постов
        self.schedule = [
            {"time": "09:00", "type": "short", "name": "Утренний", "channels": ["telegram", "zen"]},
            {"time": "14:00", "type": "medium", "name": "Обеденный", "channels": ["telegram", "zen"]},
            {"time": "19:00", "type": "short", "name": "Вечерний", "channels": ["telegram", "zen"]}
        ]

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": ["office team", "business workplace", "corporate culture", "teamwork"],
            "PR и коммуникации": ["public relations", "media communication", "social media", "networking"],
            "ремонт и строительство": ["construction", "building renovation", "interior design", "architecture"]
        }
        
        # Цвета для изображений
        self.image_colors = ["4A90E2", "2E8B57", "FF6B35", "6A5ACD", "20B2AA", "FF4081", "7B1FA2"]

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
                "daily_stats": {"date": None, "telegram": 0, "zen": 0}
            }
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {
                "posts": {}, 
                "themes": {}, 
                "last_post_time": None,
                "daily_stats": {"date": None, "telegram": 0, "zen": 0}
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему с учетом истории"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Получаем темы, использованные сегодня
        todays_themes = self.post_history.get("themes", {}).get(today, [])
        
        available_themes = self.themes.copy()
        
        # Исключаем темы, уже использованные сегодня
        for theme in todays_themes:
            if theme in available_themes:
                available_themes.remove(theme)
        
        # Если все темы использованы, начинаем заново
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = random.choice(available_themes)
        
        # Сохраняем тему для сегодня
        if today not in self.post_history["themes"]:
            self.post_history["themes"][today] = []
        
        self.post_history["themes"][today].append(theme)
        self.save_post_history()
        
        return theme

    def get_current_slot(self):
        """Определяет текущий временной слот"""
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        closest_slot = None
        min_diff = float('inf')
        
        for slot in self.schedule:
            slot_time = datetime.strptime(slot["time"], "%H:%M").replace(
                year=now.year, 
                month=now.month, 
                day=now.day
            )
            diff = abs((now - slot_time).total_seconds())
            
            if diff < min_diff:
                min_diff = diff
                closest_slot = slot
        
        print(f"🕒 Текущее время: {current_time_str}")
        print(f"🎯 Ближайший слот: {closest_slot['time']} - {closest_slot['name']}")
        
        return closest_slot

    def check_post_frequency(self):
        """Проверяет частоту постов"""
        last_post_time = self.post_history.get("last_post_time")
        if last_post_time:
            try:
                last_time = datetime.fromisoformat(last_post_time)
            except ValueError:
                self.post_history["last_post_time"] = None
                self.save_post_history()
                return True
            
            time_since_last = datetime.now() - last_time
            minutes_since_last = time_since_last.total_seconds() / 60
            
            print(f"⏰ Последний пост был: {last_time.strftime('%H:%M')}")
            print(f"📅 Прошло минут: {minutes_since_last:.0f}")
            
            # Минимум 10 минут между постами
            if minutes_since_last < 10:
                print("⏸️  Пост был недавно, пропускаем отправку")
                return False
        
        return True

    def update_stats(self, channel_type):
        """Обновляет статистику отправки"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.post_history["daily_stats"]["date"] != today:
            self.post_history["daily_stats"] = {
                "date": today,
                "telegram": 0,
                "zen": 0
            }
        
        self.post_history["daily_stats"][channel_type] += 1
        self.post_history["last_post_time"] = datetime.now().isoformat()
        self.save_post_history()
        
        print(f"📊 Статистика сегодня: Telegram={self.post_history['daily_stats']['telegram']}, Дзен={self.post_history['daily_stats']['zen']}")

    def create_telegram_prompt(self, theme, slot_name, post_type):
        """Создает промпт для Telegram"""
        prompt = f"""Создай пост для Telegram на тему "{theme}".

Контекст: Это {slot_name} пост ({post_type} формат).

Требования:
1. Яркий заголовок с эмодзи
2. Основной текст: {post_type} формат ({self.get_post_length(post_type)})
3. Практические советы или кейсы
4. Вопрос для вовлечения аудитории
5. 3-5 релевантных хештегов

Используй эмодзи для оформления, живой язык, будь полезным и интересным."""

        return prompt

    def create_zen_prompt(self, theme, slot_name, post_type):
        """Создает промпт для Яндекс.Дзена (адаптированный под площадку)"""
        prompt = f"""Создай пост для Яндекс.Дзен на тему "{theme}".

Контекст: Это {slot_name} пост для платформы Яндекс.Дзен.

ВАЖНО: Адаптируй контент под аудиторию Дзен:
- Более аналитический и развернутый подход
- Без эмодзи и хештегов
- Профессиональный, но доступный язык
- Глубокий анализ темы
- Структурированный текст с подзаголовками

Требования:
1. Цепляющий заголовок (не кликбейтный)
2. Введение с актуальностью темы
3. Основная часть с анализом и примерами
4. Практические рекомендации
5. Выводы и перспективы
6. Вопрос для обсуждения в комментариях

Объем: {self.get_post_length(post_type, for_zen=True)}."""

        return prompt

    def get_post_length(self, post_type, for_zen=False):
        """Возвращает описание длины поста"""
        if for_zen:
            return {
                "short": "1500-2500 знаков",
                "medium": "3000-4000 знаков",
                "long": "5000-7000 знаков"
            }.get(post_type, "2000-3000 знаков")
        else:
            return {
                "short": "80-120 слов",
                "medium": "150-200 слов", 
                "long": "250-300 слов"
            }.get(post_type, "100-150 слов")

    def test_gemini_api(self):
        """Тестирует подключение к Gemini API"""
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY не найден в .env файле")
            return False
            
        print("🧪 Тестируем подключение к Gemini API...")
        
        for model in self.available_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                
                test_data = {
                    "contents": [{
                        "parts": [{"text": "Тест соединения"}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 10,
                    }
                }
                
                response = requests.post(url, json=test_data, timeout=15)
                print(f"📡 Тест модели {model}: {response.status_code}")
                
                if response.status_code == 200:
                    self.current_model = model
                    print(f"✅ Используем модель: {model}")
                    return True
                    
            except Exception as e:
                print(f"⚠️ Ошибка при тесте модели {model}: {e}")
                continue
        
        print("❌ Не удалось подключиться к Gemini API")
        return False

    def generate_with_gemini(self, prompt, max_attempts=2):
        """Генерирует текст через Gemini API"""
        if not GEMINI_API_KEY:
            print("❌ Отсутствует GEMINI_API_KEY")
            return None
        
        # Ограничиваем промпт для безопасности
        short_prompt = prompt[:500]
        
        for attempt in range(max_attempts):
            try:
                print(f"🔄 Попытка {attempt + 1}/{max_attempts}")
                
                url = f"https://generativelanguage.googleapis.com/v1/models/{self.current_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": short_prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 800,
                    }
                }
                
                response = requests.post(url, json=data, timeout=20)
                print(f"📡 Статус: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        text = result['candidates'][0]['content']['parts'][0]['text']
                        if text and text.strip():
                            return text.strip()
                
                elif response.status_code == 403:
                    print("❌ Ошибка 403: Пробуем другую модель...")
                    # Меняем модель
                    current_idx = self.available_models.index(self.current_model)
                    next_idx = (current_idx + 1) % len(self.available_models)
                    self.current_model = self.available_models[next_idx]
                    print(f"🔧 Переключились на: {self.current_model}")
                    continue
                
                print(f"⚠️ Ошибка генерации")
                time.sleep(3)
                    
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                time.sleep(3)
        
        return None

    def get_image_url(self, theme):
        """Генерирует URL изображения для темы"""
        print(f"🖼️ Создаем изображение для темы: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            color = random.choice(self.image_colors)
            
            # Кодируем ключевое слово
            encoded_keyword = urllib.parse.quote(keyword)
            
            image_url = f"https://placehold.co/1200x630/{color}/FFFFFF?text={encoded_keyword}&font=montserrat"
            print(f"📸 Изображение готово")
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка создания изображения: {e}")
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business"

    def send_to_telegram(self, chat_id, text, image_url=None, is_zen=False):
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            print("❌ Отсутствует BOT_TOKEN")
            return False
            
        try:
            # Для Telegram канала - с фото, для Дзена - без фото
            if image_url and not is_zen:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                
                # Обрезаем текст для caption (ограничение Telegram)
                caption = text[:1024] if len(text) > 1024 else text
                
                payload = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                
                response = requests.post(url, json=payload, timeout=30)
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                
                # Обрезаем текст для обычного сообщения
                message_text = text[:4096] if len(text) > 4096 else text
                
                payload = {
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": not is_zen  # Для Дзена включаем превью
                }
                
                response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ Пост отправлен")
                return True
            else:
                print(f"❌ Ошибка отправки: {response.status_code}")
                print(f"🔧 Детали: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты для текущего слота"""
        print("\n" + "="*60)
        print("📅 ПРОВЕРКА РАСПИСАНИЯ")
        print("="*60)
        
        # Проверяем частоту постов
        if not self.check_post_frequency():
            print("⏸️  Пропускаем отправку")
            return True
            
        print("✅ Можно публиковать посты")
        
        # Тестируем API
        print("\n🔧 ПРОВЕРКА API")
        print("-"*30)
        if not self.test_gemini_api():
            print("❌ Gemini API не работает")
            return False
        print("✅ API работает")
        
        # Определяем текущий слот
        current_slot = self.get_current_slot()
        
        # Выбираем тему
        self.current_theme = self.get_smart_theme()
        print(f"\n🎯 Тема: {self.current_theme}")
        print(f"📊 Тип поста: {current_slot['type'].upper()}")
        
        try:
            # Готовим изображение (для Telegram)
            image_url = self.get_image_url(self.current_theme)
            
            # Отправляем посты для каждого канала в этом слоте
            successes = []
            
            for channel in current_slot["channels"]:
                print(f"\n📝 Генерация поста для {channel.upper()}...")
                
                # Создаем промпт в зависимости от канала
                if channel == "telegram":
                    prompt = self.create_telegram_prompt(
                        self.current_theme, 
                        current_slot["name"], 
                        current_slot["type"]
                    )
                    target_chat = MAIN_CHANNEL_ID
                    use_image = True
                else:  # zen
                    prompt = self.create_zen_prompt(
                        self.current_theme,
                        current_slot["name"],
                        current_slot["type"]
                    )
                    target_chat = ZEN_CHANNEL_ID
                    use_image = False
                
                # Генерируем пост
                post_text = self.generate_with_gemini(prompt)
                
                if not post_text:
                    print(f"❌ Не удалось сгенерировать пост для {channel}")
                    continue
                
                print(f"✅ Сгенерировано: {len(post_text)} символов")
                
                # Отправляем пост
                if channel == "telegram":
                    success = self.send_to_telegram(
                        target_chat, 
                        post_text, 
                        image_url if use_image else None,
                        is_zen=False
                    )
                else:  # zen
                    success = self.send_to_telegram(
                        target_chat,
                        post_text,
                        None,
                        is_zen=True
                    )
                
                if success:
                    successes.append(channel)
                    # Обновляем статистику
                    self.update_stats(channel)
                
                # Пауза между отправками
                if len(current_slot["channels"]) > 1:
                    time.sleep(3)
            
            # Итоги
            print(f"\n📊 ИТОГИ отправки для слота {current_slot['time']}:")
            print(f"   ✅ Успешно: {len(successes)}/{len(current_slot['channels'])}")
            print(f"   📈 Telegram сегодня: {self.post_history['daily_stats']['telegram']}")
            print(f"   📈 Дзен сегодня: {self.post_history['daily_stats']['zen']}")
            
            return len(successes) > 0
                
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Полное расписание: 6 постов в день (3 Telegram + 3 Дзен)")
    print("🎯 Telegram: все посты с фотографиями")
    print("🎯 Яндекс.Дзен: адаптированные посты без фото")
    print("=" * 80)
    
    try:
        bot = AIPostGenerator()
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n🎉 УСПЕХ! Посты отправлены!")
        else:
            print("\n⚠️  Не удалось отправить посты")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
