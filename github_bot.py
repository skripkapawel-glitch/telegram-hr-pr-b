import os
import requests
import random
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ")
print("=" * 80)

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временная привязка типов постов для Telegram
        self.time_slots = {
            "09:00": {"type": "short", "name": "Утренний пост"},
            "14:00": {"type": "long", "name": "Обеденный пост"},  
            "19:00": {"type": "medium", "name": "Вечерний пост"}
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": ["office team", "business workplace", "corporate culture", "hr management", "teamwork"],
            "PR и коммуникации": ["public relations", "media communication", "social media", "marketing", "networking"],
            "ремонт и строительство": ["construction", "building renovation", "interior design", "architecture", "home improvement"]
        }

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}, "last_post_time": None}
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}, "last_post_time": None}

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом истории и времени"""
        channel_key = str(channel_id)
        themes_history = self.post_history.get("themes", {}).get(channel_key, [])
        
        # Получаем текущий час для выбора темы
        current_hour = datetime.now().hour
        available_themes = self.themes.copy()
        
        # Утренние темы (более энергичные)
        if 6 <= current_hour < 12:
            preferred_themes = ["HR и управление персоналом", "ремонт и строительство"]
        # Дневные темы (информационные)
        elif 12 <= current_hour < 18:
            preferred_themes = ["PR и коммуникации", "HR и управление персоналом"]
        # Вечерние темы (спокойные)
        else:
            preferred_themes = ["ремонт и строительство", "PR и коммуникации"]
        
        # Сортируем темы по предпочтениям времени суток
        available_themes.sort(key=lambda x: preferred_themes.index(x) if x in preferred_themes else len(preferred_themes))
        
        # Исключаем последние 2 использованные темы
        for theme in themes_history[-2:]:
            if theme in available_themes:
                available_themes.remove(theme)
        
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = available_themes[0]  # Берем наиболее подходящую тему
        
        # Сохраняем тему в историю
        if "themes" not in self.post_history:
            self.post_history["themes"] = {}
        if channel_key not in self.post_history["themes"]:
            self.post_history["themes"][channel_key] = []
        
        self.post_history["themes"][channel_key].append(theme)
        if len(self.post_history["themes"][channel_key]) > 10:
            self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-8:]
        
        self.save_post_history()
        return theme

    def get_tg_type_by_time(self):
        """Определяет тип поста для ТГ based on current time"""
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        # Находим ближайший временной слот
        closest_slot = None
        min_diff = float('inf')
        
        for slot_time in self.time_slots.keys():
            slot_datetime = datetime.strptime(slot_time, "%H:%M").replace(
                year=now.year, 
                month=now.month, 
                day=now.day
            )
            diff = abs((now - slot_datetime).total_seconds())
            
            if diff < min_diff:
                min_diff = diff
                closest_slot = slot_time
        
        post_type_info = self.time_slots[closest_slot]
        
        print(f"🕒 Текущее время: {current_time_str}")
        print(f"🎯 Ближайший слот: {closest_slot} - {post_type_info['name']}")
        print(f"📊 Тип поста: {post_type_info['type'].upper()}")
        
        return post_type_info['type'], closest_slot

    def check_last_post_time(self):
        """Проверяет, когда был последний пост"""
        last_post_time = self.post_history.get("last_post_time")
        if last_post_time:
            last_time = datetime.fromisoformat(last_post_time)
            time_since_last = datetime.now() - last_time
            hours_since_last = time_since_last.total_seconds() / 3600
            
            print(f"⏰ Последний пост был: {last_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"📅 Прошло часов: {hours_since_last:.1f}")
            
            # Если пост был менее 4 часов назад - пропускаем
            if hours_since_last < 4:
                print("⏸️  Пост был недавно, пропускаем отправку")
                return False
        
        return True

    def update_last_post_time(self):
        """Обновляет время последнего поста"""
        self.post_history["last_post_time"] = datetime.now().isoformat()
        self.save_post_history()

    def create_telegram_prompt(self, theme, post_type, time_slot):
        """Создает промпт для Telegram"""
        
        type_requirements = {
            "short": {
                "length": "80-120 слов",
                "structure": "заголовок + 1 ключевой факт + практический совет + вопрос для вовлечения + 3-5 релевантных хештегов",
                "tone": "энергичный, мотивирующий"
            },
            "medium": {
                "length": "150-220 слов", 
                "structure": "интригующий заголовок + 2-3 практических совета + мини-кейс + вопрос для обсуждения + 4-6 хештегов",
                "tone": "информативный, экспертный"
            },
            "long": {
                "length": "250-350 слов",
                "structure": "проблемный заголовок + анализ тренда + пошаговые рекомендации + пример из практики + призыв к действию + 5-7 хештегов", 
                "tone": "аналитический, углубленный"
            }
        }
        
        req = type_requirements[post_type]
        
        # Добавляем контекст времени суток
        time_context = {
            "09:00": "утренний пост для заряда энергией на день",
            "14:00": "обеденный пост для перерыва и вдохновения", 
            "19:00": "вечерний пост для анализа дня и планирования"
        }
        
        prompt = f"""Создай пост для Telegram на тему "{theme}" для 2024-2025 года.

КОНТЕКСТ: Это {time_context.get(time_slot, 'пост')} для профессиональной аудитории.

ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
- Объем: {req['length']}
- Структура: {req['structure']}
- Тон: {req['tone']}
- Язык: русский
- Форматирование: используй эмодзи для визуального разделения, абзацы

СОДЕРЖАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
- Актуальные данные и тренды 2024-2025
- Практическая польза для читателя
- Конкретные примеры и кейсы
- Вовлекающий вопрос в конце
- Релевантные хештеги

Создай уникальный, полезный контент без общих фраз."""

        return prompt

    def create_zen_prompt(self, theme):
        """Создает промпт для Яндекс.Дзена"""
        prompt = f"""Напиши развернутый аналитический пост для Яндекс.Дзен на тему "{theme}" в 2024-2025 году.

ТРЕБОВАНИЯ К СТРУКТУРЕ:
1. Цепляющий заголовок (не кликбейтный)
2. Введение с обозначением актуальности темы
3. Анализ текущей ситуации и трендов
4. 3-4 ключевые проблемы/вызовы
5. Практические решения и рекомендации
6. Реальный кейс или пример из практики
7. Выводы и перспективы развития
8. Вопрос для обсуждения с аудиторией

ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
- Объем: 4000-7000 знаков
- Язык: русский, профессиональный но доступный
- Без эмодзи и хештегов
- Конкретные данные, статистика (можно условная)
- Глубокий анализ с практической ценностью

Создай экспертное содержание, которое будет полезно профессионалам."""

        return prompt

    def test_gemini_api(self):
        """Тестирует подключение к Gemini API"""
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY не найден в .env файле")
            return False
            
        print("🧪 Тестируем подключение к Gemini API...")
        
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        
        test_data = {
            "contents": [{
                "parts": [{"text": "Ответь одним словом: 'Работает'"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10,
            }
        }
        
        try:
            response = requests.post(url, json=test_data, timeout=15)
            print(f"📡 Статус теста: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    print("✅ Gemini API работает корректно!")
                    return True
                else:
                    print("❌ Неверный формат ответа от Gemini")
                    return False
            else:
                print(f"❌ Ошибка Gemini API: {response.status_code}")
                if response.status_code == 400:
                    error_data = response.json()
                    print(f"🔧 Детали ошибки: {error_data}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерирует текст с повторными попытками"""
        if not GEMINI_API_KEY:
            print("❌ Отсутствует GEMINI_API_KEY")
            return None
            
        for attempt in range(max_attempts):
            try:
                print(f"🔄 Попытка {attempt + 1}/{max_attempts}...")
                
                url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 2048,
                    }
                }
                
                response = requests.post(url, json=data, timeout=30)
                print(f"📡 Статус: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        if generated_text and generated_text.strip():
                            print("✅ Текст успешно сгенерирован!")
                            return generated_text.strip()
                        else:
                            print("⚠️ Получен пустой текст")
                    else:
                        print("⚠️ Неверный формат ответа")
                else:
                    print(f"⚠️ Ошибка {response.status_code}")
                
                # Ждем перед следующей попыткой
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⏳ Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                    
            except requests.exceptions.Timeout:
                print("⏰ Таймаут запроса")
            except requests.exceptions.ConnectionError:
                print("🔌 Ошибка подключения")
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⏳ Ждем {wait_time} секунд...")
                    time.sleep(wait_time)
        
        print("❌ Не удалось сгенерировать контент после всех попыток")
        return None

    def generate_tg_post(self, theme, post_type, time_slot):
        """Генерирует пост для Telegram"""
        prompt = self.create_telegram_prompt(theme, post_type, time_slot)
        return self.generate_with_gemini(prompt)

    def generate_zen_post(self, theme):
        """Генерирует пост для Дзена"""
        prompt = self.create_zen_prompt(theme)
        return self.generate_with_gemini(prompt)

    def get_image_url(self, theme):
        """Получает изображение для темы"""
        print(f"🖼️ Получаем изображение для: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Создаем тематическое изображение через сервис placeholder
            colors = ["4A90E2", "2E8B57", "FF6B35", "6A5ACD", "20B2AA"]
            color = random.choice(colors)
            
            image_url = f"https://placehold.co/1200x630/{color}/FFFFFF?text={keyword.replace(' ', '+')}&font=montserrat"
            print(f"📸 Изображение: {image_url}")
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка получения изображения: {e}")
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business+Post"

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            print("❌ Отсутствует BOT_TOKEN")
            return False
            
        try:
            # Обрезаем текст если он слишком длинный для Telegram
            if len(text) > 1024:
                print("⚠️ Текст слишком длинный, обрезаем...")
                text = text[:1000] + "..."
            
            if image_url and image_url.startswith('http'):
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": text,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=30)
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ Пост отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def send_dual_posts(self):
        """Основной метод отправки постов"""
        # Проверяем время последнего поста
        if not self.check_last_post_time():
            print("⏸️  Пропускаем отправку - недавно уже был пост")
            return True  # Возвращаем True чтобы не ломать расписание
            
        # Тестируем API
        if not self.test_gemini_api():
            print("❌ Gemini API не работает, отменяем отправку")
            return False
            
        try:
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            tg_type, time_slot = self.get_tg_type_by_time()
            
            print(f"🎯 Тема: {self.current_theme}")
            print(f"📊 Тип ТГ-поста: {tg_type.upper()}")
            
            # Получаем изображение
            image_url = self.get_image_url(self.current_theme)
            
            print("🧠 Генерация постов через AI...")
            
            # Генерируем Telegram пост
            print("📝 Генерация Telegram поста...")
            tg_post = self.generate_tg_post(self.current_theme, tg_type, time_slot)
            if not tg_post:
                print("❌ Не удалось сгенерировать пост для Telegram")
                return False
            
            # Генерируем Дзен пост
            print("📝 Генерация Дзен поста...")
            zen_post = self.generate_zen_post(self.current_theme)
            if not zen_post:
                print("❌ Не удалось сгенерировать пост для Дзена")
                return False
            
            print(f"📊 Статистика постов:")
            print(f"   📝 ТГ-пост ({tg_type}): {len(tg_post)} символов")
            print(f"   📝 Дзен-пост: {len(zen_post)} символов")
            
            # Отправляем посты
            print("\n📤 Отправка постов...")
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, image_url)
            time.sleep(2)  # Пауза между отправками
            
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, None)  # Дзен без изображения
            
            if tg_success and zen_success:
                print("🎉 ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ!")
                self.update_last_post_time()
                return True
            else:
                print(f"⚠️ Ошибки отправки: ТГ={tg_success}, Дзен={zen_success}")
                return False
                
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Умный подбор тем по времени суток")
    print("🎯 Контроль частоты постов")
    print("🎯 Оптимизированные промпты")
    print("=" * 80)
    
    try:
        bot = AIPostGenerator()
        success = bot.send_dual_posts()
        
        if success:
            print("\n🎉 УСПЕХ! AI посты отправлены или пропущены по расписанию!")
        else:
            print("\n💥 ОШИБКА: Не удалось сгенерировать или отправить посты")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
