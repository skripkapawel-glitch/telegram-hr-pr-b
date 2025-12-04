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
        
        # 🔥 ОБНОВЛЕННЫЙ СПИСОК МОДЕЛЕЙ (по вашим данным)
        self.available_models = [
            "gemini-2.0-flash",          # ✅ Основная модель
            "gemini-2.0-flash-lite",     # ✅ Облегченная версия
            "gemma-3-27b-it",            # ✅ Open-weight модель
            "gemini-2.5-flash",          # ✅ Новая модель
            "gemini-2.5-flash-lite-preview", # ✅ Preview версия
            "gemini-2.5-pro",            # ✅ Pro версия
            "gemini-1.0-pro"             # ✅ Запасная старая модель
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
            "HR и управление персоналом": ["HR management", "office team", "business workplace", "corporate"],
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
        if closest_slot:
            print(f"🎯 Ближайший слот: {closest_slot['time']} - {closest_slot['name']}")
        else:
            print("⚠️ Не найден подходящий слот")
            closest_slot = self.schedule[0]  # По умолчанию первый слот
        
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
                        "parts": [{"text": "Привет"}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 5,
                    }
                }
                
                response = requests.post(url, json=test_data, timeout=15)
                print(f"📡 Тест модели {model}: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        self.current_model = model
                        print(f"✅ Модель РАБОТАЕТ: {model}")
                        return True
                elif response.status_code == 404:
                    print(f"⚠️ Модель {model} не найдена (404)")
                elif response.status_code == 403:
                    print(f"⚠️ Модель {model} доступ запрещен (403)")
                else:
                    print(f"⚠️ Модель {model}: ошибка {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ Ошибка при тесте модели {model}: {e}")
                continue
        
        print("❌ Не удалось подключиться к Gemini API")
        return False

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерирует текст через Gemini API"""
        if not GEMINI_API_KEY:
            print("❌ Отсутствует GEMINI_API_KEY")
            return None
        
        # 🔥 УВЕЛИЧИВАЕМ лимит промпта
        short_prompt = prompt[:800]  # 800 символов вместо 500
        
        for attempt in range(max_attempts):
            try:
                print(f"🔄 Попытка {attempt + 1}/{max_attempts} (модель: {self.current_model})")
                
                url = f"https://generativelanguage.googleapis.com/v1/models/{self.current_model}:generateContent?key={GEMINI_API_KEY}"
                
                # 🔥 ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ
                data = {
                    "contents": [{
                        "parts": [{"text": short_prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,  # Немного больше креативности
                        "maxOutputTokens": 1000,  # Больше токенов на выход
                    }
                }
                
                print(f"📝 Длина промпта: {len(short_prompt)} символов")
                response = requests.post(url, json=data, timeout=25)
                print(f"📡 Статус: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        text = result['candidates'][0]['content']['parts'][0]['text']
                        if text and text.strip():
                            print(f"✅ Сгенерировано: {len(text)} символов")
                            return text.strip()
                        else:
                            print("⚠️ Получен пустой текст")
                elif response.status_code == 403:
                    print("❌ Ошибка 403: Доступ запрещен")
                    print(f"🔧 Детали: {response.text[:200]}")
                    
                    # 🔥 АГРЕССИВНАЯ СМЕНА МОДЕЛИ
                    current_idx = self.available_models.index(self.current_model)
                    if current_idx + 1 < len(self.available_models):
                        self.current_model = self.available_models[current_idx + 1]
                        print(f"🔄 Переключаемся на модель: {self.current_model}")
                        continue
                
                elif response.status_code == 429:
                    print("⚠️ Превышены лимиты, ждем...")
                    wait_time = (attempt + 1) * 5
                    time.sleep(wait_time)
                    continue
                    
                print("🔄 Пробуем снова...")
                time.sleep(3)
                    
            except requests.exceptions.Timeout:
                print("⏰ Таймаут запроса")
                time.sleep(5)
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                time.sleep(3)
        
        print("❌ Не удалось сгенерировать контент после всех попыток")
        return None

    def get_image_url(self, theme):
        """Генерирует URL изображения для темы"""
        print(f"🖼️ Создаем изображение для темы: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            color = random.choice(self.image_colors)
            
            # Упрощаем кодирование
            safe_keyword = keyword.replace(' ', '+')
            
            image_url = f"https://placehold.co/1200x630/{color}/FFFFFF?text={safe_keyword}&font=montserrat"
            print(f"📸 Изображение готово: {image_url[:70]}...")
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка создания изображения: {e}")
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business+Content"

    def send_to_telegram(self, chat_id, text, image_url=None, is_zen=False):
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            print("❌ Отсутствует BOT_TOKEN")
            return False
            
        try:
            # Для Telegram канала - с фото, для Дзена - без фото
            if image_url and not is_zen and image_url.startswith('http'):
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                
                # Обрезаем текст для caption
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
                
                # Обрезаем текст
                message_text = text[:4096] if len(text) > 4096 else text
                
                payload = {
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": not is_zen
                }
                
                response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ Пост успешно отправлен")
                return True
            else:
                print(f"❌ Ошибка отправки: {response.status_code}")
                if response.status_code == 400:
                    print(f"🔧 Детали: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def run_safe_mode(self):
        """Запускает безопасный режим с минимальными запросами"""
        print("\n🛡️ ЗАПУСК БЕЗОПАСНОГО РЕЖИМА")
        print("="*60)
        
        # Просто тестируем API
        if not self.test_gemini_api():
            print("❌ API не работает даже в безопасном режиме")
            return False
        
        # Пробуем сгенерировать один простой пост
        print("\n🧪 Тест генерации простого поста...")
        test_prompt = "Напиши короткий пост про HR на 50 слов."
        test_post = self.generate_with_gemini(test_prompt, max_attempts=2)
        
        if test_post:
            print(f"✅ Генерация работает! Длина: {len(test_post)} символов")
            return True
        else:
            print("❌ Генерация не работает")
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
            print("❌ Gemini API не работает, пробуем безопасный режим...")
            if not self.run_safe_mode():
                return False
            print("⚠️ Работаем в ограниченном режиме")
        
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
                    # Пробуем создать простой запасной пост
                    if channel == "telegram":
                        post_text = f"📢 {self.current_theme}\n\nСегодня поговорим на актуальную тему. Что вы думаете по этому поводу?\n\n#{self.current_theme.replace(' ', '').replace('и', '')}"
                    else:
                        post_text = f"{self.current_theme}. Актуальная тема для обсуждения. Поделитесь своим мнением в комментариях."
                    print(f"⚠️ Используем запасной текст")
                
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
                else:
                    print(f"⚠️ Не удалось отправить пост в {channel}")
                
                # Пауза между отправками
                if len(current_slot["channels"]) > 1:
                    time.sleep(3)
            
            # Итоги
            print(f"\n📊 ИТОГИ отправки для слота {current_slot['time']}:")
            print(f"   ✅ Успешно: {len(successes)}/{len(current_slot['channels'])}")
            
            if "daily_stats" in self.post_history:
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
    print("📅 Полное расписание: 6 постов в день (3 Telegram + 3 Дзен)")
    print("🕒 Telegram: 09:00, 14:00, 19:00 (все с фото)")
    print("📝 Яндекс.Дзен: 09:00, 14:00, 19:00 (адаптированные посты)")
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
        import traceback
        traceback.print_exc()
    
    print("=" * 80)


if __name__ == "__main__":
    # Сначала запустите тест API
    print("\n🔍 ТЕСТИРУЕМ ПОДКЛЮЧЕНИЕ...")
    print("-" * 40)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print(f"✅ Ключ найден: {api_key[:10]}...")
        
        # Простой тест
        import requests
        test_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemma-3-27b-it"]
        
        for model in test_models:
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
                    params={"key": api_key},
                    json={"contents": [{"parts": [{"text": "Тест"}]}]},
                    timeout=10
                )
                print(f"📡 {model}: {response.status_code}")
            except:
                print(f"📡 {model}: ошибка")
    else:
        print("❌ Ключ не найден в .env файле")
    
    print("-" * 40)
    
    # Запускаем основной бот
    main()
