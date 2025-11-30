import os
import requests
import random
import json
import hashlib
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: ГЕНЕРАЦИЯ ПОСТОВ С ПОВТОРНЫМИ ПОПЫТКАМИ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Временная привязка типов постов для Telegram
        self.time_slots = {
            "09:00": "short",    # Утро - короткий пост
            "14:00": "long",     # Обед - длинный пост  
            "19:00": "medium"    # Вечер - средний пост
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": ["office team", "business workplace", "corporate culture"],
            "PR и коммуникации": ["public relations", "media communication", "social media"],
            "ремонт и строительство": ["construction", "building renovation", "interior design"]
        }
        
        self.image_sources = [
            self.search_unsplash_image,
            self.search_pexels_image,
            self.get_fallback_image
        ]

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}}
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}}

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом истории"""
        channel_key = str(channel_id)
        themes_history = self.post_history.get("themes", {}).get(channel_key, [])
        
        available_themes = self.themes.copy()
        
        # Исключаем последние 2 темы
        for theme in themes_history[-2:]:
            if theme in available_themes:
                available_themes.remove(theme)
        
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = random.choice(available_themes)
        
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
        now = datetime.now().strftime("%H:%M")
        
        # Находим ближайший временной слот
        current_time = datetime.now()
        time_differences = {}
        
        for slot_time, post_type in self.time_slots.items():
            slot_datetime = datetime.strptime(slot_time, "%H:%M").replace(
                year=current_time.year, 
                month=current_time.month, 
                day=current_time.day
            )
            diff = abs((current_time - slot_datetime).total_seconds())
            time_differences[post_type] = diff
        
        # Выбираем тип поста с минимальной разницей во времени
        selected_type = min(time_differences, key=time_differences.get)
        
        print(f"🕒 Текущее время: {now}")
        print(f"📊 Выбран тип поста: {selected_type.upper()}")
        
        return selected_type

    def create_telegram_prompt(self, theme, post_type, time_slot):
        """Создает промпт для Telegram"""
        
        type_requirements = {
            "short": {
                "words": "50-100 слов",
                "structure": "Заголовок + 1 факт + вопрос + хештеги"
            },
            "medium": {
                "words": "120-220 слов", 
                "structure": "Заголовок + 2-3 факта + 2 совета + вопрос + хештеги"
            },
            "long": {
                "words": "300-450 слов",
                "structure": "Заголовок + 3-4 тренда + рекомендации + кейс + вопрос + хештеги"
            }
        }
        
        req = type_requirements[post_type]
        
        prompt = f"""
        Создай пост для Telegram на тему "{theme}" для 2024-2025 года.

        Требования:
        - Тип: {post_type} ({req['words']})
        - Время публикации: {time_slot}
        - Структура: {req['structure']}
        - Язык: русский
        - Стиль: профессиональный, но доступный
        - Добавь релевантные хештеги в конце

        Создай уникальный, полезный пост без лишней воды.
        """
        
        return prompt

    def create_zen_prompt(self, theme):
        """Создает промпт для Яндекс.Дзена"""
        prompt = f"""
        Напиши развернутый пост для Яндекс.Дзен на тему "{theme}" в 2024-2025 году.

        Требования:
        - Объем: 4000-7000 знаков
        - Структура: заголовок, введение, проблема, решение, кейс, вывод, вопрос
        - Язык: русский, профессиональный но доступный
        - Без эмодзи и хештегов
        - Конкретные примеры и данные

        Создай глубокий, аналитический пост с практической ценностью.
        """
        
        return prompt

    def generate_with_gemini_retry(self, prompt, max_attempts=5):
        """Генерирует текст с повторными попытками"""
        if not GEMINI_API_KEY:
            print("❌ Отсутствует GEMINI_API_KEY")
            return None
            
        for attempt in range(max_attempts):
            try:
                print(f"🧠 Попытка {attempt + 1}/{max_attempts} к Gemini API...")
                
                url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 2048,
                    }
                }
                
                response = requests.post(url, json=data, timeout=30)
                print(f"📡 Статус ответа: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        generated_text = result['candidates'][0]['content']['parts'][0]['text']
                        if generated_text.strip():
                            print("✅ Текст успешно сгенерирован")
                            return generated_text.strip()
                        else:
                            print("⚠️ Получен пустой текст, пробуем снова...")
                    else:
                        print("⚠️ Неверный формат ответа, пробуем снова...")
                else:
                    print(f"⚠️ Ошибка Gemini {response.status_code}, пробуем снова...")
                
                # Ждем перед следующей попыткой
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2  # Увеличиваем время ожидания
                    print(f"⏳ Ждем {wait_time} секунд перед следующей попыткой...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                print(f"⚠️ Ошибка подключения: {e}, пробуем снова...")
                if attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⏳ Ждем {wait_time} секунд перед следующей попыткой...")
                    time.sleep(wait_time)
        
        print("❌ Все попытки исчерпаны, не удалось сгенерировать контент")
        return None

    def generate_tg_post(self, theme, post_type, time_slot):
        """Генерирует пост для Telegram с повторными попытками"""
        prompt = self.create_telegram_prompt(theme, post_type, time_slot)
        return self.generate_with_gemini_retry(prompt)

    def generate_zen_post(self, theme):
        """Генерирует пост для Дзена с повторными попытками"""
        prompt = self.create_zen_prompt(theme)
        return self.generate_with_gemini_retry(prompt)

    def get_unique_image(self, theme):
        """Находит изображение для темы"""
        print(f"🖼️ Поиск изображения для: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Пробуем разные источники
            for source in self.image_sources:
                image_url = source(theme)
                if image_url:
                    return image_url
            
            # Fallback
            return f"https://placehold.co/1200x630/4A90E2/FFFFFF?text={keyword.replace(' ', '+')}"
            
        except Exception as e:
            print(f"❌ Ошибка поиска изображения: {e}")
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business"

    def search_unsplash_image(self, theme):
        """Поиск в Unsplash"""
        if not UNSPLASH_ACCESS_KEY:
            return None
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            url = f"https://api.unsplash.com/photos/random?query={keyword}&client_id={UNSPLASH_ACCESS_KEY}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data['urls']['regular']
        except:
            return None

    def search_pexels_image(self, theme):
        """Поиск в Pexels"""
        if not PEXELS_API_KEY:
            return None
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
            headers = {"Authorization": PEXELS_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['photos']:
                    return data['photos'][0]['src']['large']
        except:
            return None

    def get_fallback_image(self, theme):
        """Резервное изображение"""
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            return f"https://placehold.co/1200x630/4A90E2/FFFFFF?text={keyword.replace(' ', '+')}"
        except:
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business"

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            print("❌ Отсутствует BOT_TOKEN")
            return False
            
        try:
            if image_url:
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
        try:
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            current_time = datetime.now().strftime("%H:%M")
            tg_type = self.get_tg_type_by_time()
            
            # Определяем временной слот
            time_slot = min(self.time_slots.keys(), 
                           key=lambda x: abs(datetime.strptime(x, "%H:%M") - 
                                           datetime.strptime(current_time, "%H:%M")))
            
            print(f"🎯 Тема: {self.current_theme}")
            print(f"🕒 Время: {current_time} (слот: {time_slot})")
            print(f"📊 Тип ТГ-поста: {tg_type.upper()}")
            
            # Получаем изображение
            theme_image = self.get_unique_image(self.current_theme)
            
            print("🧠 Генерация постов с повторными попытками...")
            tg_post = self.generate_tg_post(self.current_theme, tg_type, time_slot)
            zen_post = self.generate_zen_post(self.current_theme)
            
            if not tg_post:
                print("❌ Не удалось сгенерировать пост для Telegram после всех попыток")
                return False
                
            if not zen_post:
                print("❌ Не удалось сгенерировать пост для Дзена после всех попыток")
                return False
            
            print(f"📝 ТГ-пост ({tg_type}): {len(tg_post)} символов")
            print(f"📝 Дзен-пост: {len(zen_post)} символов")
            
            # Отправляем посты
            print("📤 Отправка в @da4a_hr...")
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, theme_image)
            
            print("📤 Отправка в @tehdzenm...")
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, theme_image)
            
            if tg_success and zen_success:
                print("✅ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ!")
                return True
            else:
                print(f"⚠️ Есть ошибки: ТГ={tg_success}, Дзен={zen_success}")
                return tg_success or zen_success
                
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            return False


def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА ПОСТОВ")
    print("🎯 Временная оптимизация: 9:00-короткие, 14:00-длинные, 19:00-средние")
    print("🎯 Яндекс.Дзен: 4000-7000 знаков глубины")
    print("🎯 Повторные попытки Gemini API")
    print("=" * 80)
    
    try:
        bot = SmartPostGenerator()
        success = bot.send_dual_posts()
        
        if success:
            print("\n🎉 УСПЕХ! Посты отправлены!")
        else:
            print("\n💥 ОШИБКА ОТПРАВКИ!")
            
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
