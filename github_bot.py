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
        
        # 🔥 ТОЛЬКО РАБОЧАЯ МОДЕЛЬ (из ваших логов)
        self.current_model = "gemini-2.0-flash"
        
        # Расписание постов
        self.schedule = [
            {"time": "09:00", "type": "short", "name": "Утренний", "channels": ["telegram", "zen"]},
            {"time": "14:00", "type": "medium", "name": "Обеденный", "channels": ["telegram", "zen"]},
            {"time": "19:00", "type": "short", "name": "Вечерний", "channels": ["telegram", "zen"]}
        ]

        # Ключевые слова для изображений
        self.theme_keywords = {
            "HR и управление персоналом": ["HR", "office", "teamwork"],
            "PR и коммуникации": ["PR", "media", "communication"],
            "ремонт и строительство": ["construction", "renovation", "design"]
        }
        
        # Цвета для изображений
        self.image_colors = ["4A90E2", "2E8B57", "FF6B35", "6A5ACD"]

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
        """Выбирает тему"""
        return random.choice(self.themes)

    def get_current_slot(self):
        """Определяет текущий временной слот"""
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        # Просто берем ближайший слот
        for slot in self.schedule:
            slot_time = datetime.strptime(slot["time"], "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            diff = abs((now - slot_time).total_seconds())
            if diff < 3600:  # В пределах часа
                print(f"🕒 Текущее время: {current_time_str}")
                print(f"🎯 Слот: {slot['time']} - {slot['name']}")
                return slot
        
        # Если не нашли, возвращаем первый
        print(f"🕒 Текущее время: {current_time_str}")
        print(f"🎯 Используем слот: {self.schedule[0]['time']}")
        return self.schedule[0]

    def check_post_frequency(self):
        """Проверяет частоту постов"""
        last_post_time = self.post_history.get("last_post_time")
        if last_post_time:
            try:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                minutes_since_last = time_since_last.total_seconds() / 60
                
                if minutes_since_last < 10:
                    print("⏸️  Пост был недавно, пропускаем")
                    return False
            except:
                pass
        return True

    def update_stats(self, channel_type):
        """Обновляет статистику"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.post_history["daily_stats"]["date"] != today:
            self.post_history["daily_stats"] = {"date": today, "telegram": 0, "zen": 0}
        
        self.post_history["daily_stats"][channel_type] += 1
        self.post_history["last_post_time"] = datetime.now().isoformat()
        self.save_post_history()
        
        print(f"📊 Статистика: ТГ={self.post_history['daily_stats']['telegram']}, Дзен={self.post_history['daily_stats']['zen']}")

    def create_telegram_prompt(self, theme, slot_name, post_type):
        """Создает ОЧЕНЬ КОРОТКИЙ промпт для Telegram"""
        # 🔥 СУПЕР КОРОТКИЙ промпт!
        prompt = f"Напиши пост в Telegram про {theme}. {post_type} формат. Добавь эмодзи и 3 хештега."
        print(f"📝 Длина промпта Telegram: {len(prompt)} символов")
        return prompt

    def create_zen_prompt(self, theme, slot_name, post_type):
        """Создает ОЧЕНЬ КОРОТКИЙ промпт для Дзена"""
        # 🔥 СУПЕР КОРОТКИЙ промпт!
        prompt = f"Напиши пост в Яндекс.Дзен про {theme}. Без эмодзи. Профессиональный стиль."
        print(f"📝 Длина промпта Дзен: {len(prompt)} символов")
        return prompt

    def test_gemini_api(self):
        """Быстрый тест API"""
        if not GEMINI_API_KEY:
            print("❌ Ключ не найден")
            return False
        
        print("🧪 Быстрый тест API...")
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{self.current_model}:generateContent?key={GEMINI_API_KEY}"
            
            # ОЧЕНЬ короткий тест
            data = {
                "contents": [{
                    "parts": [{"text": "Тест"}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 5,
                }
            }
            
            response = requests.post(url, json=data, timeout=10)
            print(f"📡 Модель {self.current_model}: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ API работает")
                return True
            else:
                print(f"❌ Ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def generate_with_gemini(self, prompt, max_attempts=2):
        """Генерирует текст с ОГРАНИЧЕННЫМ промптом"""
        if not GEMINI_API_KEY:
            return None
        
        # 🔥 ЖЕСТКОЕ ОГРАНИЧЕНИЕ: максимум 100 символов!
        short_prompt = prompt[:100]
        
        for attempt in range(max_attempts):
            try:
                print(f"🔄 Попытка {attempt + 1}")
                
                url = f"https://generativelanguage.googleapis.com/v1/models/{self.current_model}:generateContent?key={GEMINI_API_KEY}"
                
                # 🔥 МИНИМАЛЬНЫЙ запрос
                data = {
                    "contents": [{
                        "parts": [{"text": short_prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 300,  # Мало токенов!
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
                
                print("🔄 Пробуем снова...")
                time.sleep(2)
                    
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                time.sleep(2)
        
        # 🔥 ЗАПАСНОЙ ВАРИАНТ
        print("⚠️ Использую запасной текст")
        if "HR" in prompt:
            return "🎯 HR сегодня: развитие команды, эффективные коммуникации. Как вы строите работу с персоналом? #HR #Команда #Управление"
        elif "PR" in prompt:
            return "📱 Современный PR: работа в соцсетях, кризисные коммуникации. Ваши лучшие кейсы? #PR #Маркетинг #Медиа"
        else:
            return "🏠 Ремонт и строительство: тренды 2024, качественные материалы. Что важно в ваших проектах? #Ремонт #Дизайн #Строительство"

    def get_image_url(self, theme):
        """Генерирует URL изображения"""
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            color = random.choice(self.image_colors)
            
            image_url = f"https://placehold.co/1200x630/{color}/FFFFFF?text={keyword.replace(' ', '+')}"
            return image_url
            
        except:
            return "https://placehold.co/1200x630/4A90E2/FFFFFF?text=Business"

    def send_to_telegram(self, chat_id, text, image_url=None, is_zen=False):
        """Отправляет пост в Telegram"""
        if not BOT_TOKEN:
            return False
        
        try:
            if image_url and not is_zen:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                caption = text[:1024]
                payload = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=20)
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                message_text = text[:4096]
                payload = {
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=20)
            
            return response.status_code == 200
                
        except:
            return False

    def generate_and_send_posts(self):
        """Основная функция отправки"""
        print("\n📅 ПРОВЕРКА РАСПИСАНИЯ")
        print("-"*30)
        
        if not self.check_post_frequency():
            return True
            
        # Тест API
        print("\n🔧 ПРОВЕРКА API")
        print("-"*30)
        if not self.test_gemini_api():
            return False
        
        # Определяем слот
        current_slot = self.get_current_slot()
        self.current_theme = self.get_smart_theme()
        
        print(f"\n🎯 Тема: {self.current_theme}")
        print(f"📊 Тип: {current_slot['type'].upper()}")
        
        # Изображение
        image_url = self.get_image_url(self.current_theme)
        
        successes = []
        
        # Для каждого канала в слоте
        for channel in current_slot["channels"]:
            print(f"\n📝 Генерация для {channel.upper()}...")
            
            if channel == "telegram":
                prompt = self.create_telegram_prompt(self.current_theme, current_slot["name"], current_slot["type"])
                target_chat = MAIN_CHANNEL_ID
                use_image = True
            else:
                prompt = self.create_zen_prompt(self.current_theme, current_slot["name"], current_slot["type"])
                target_chat = ZEN_CHANNEL_ID
                use_image = False
            
            post_text = self.generate_with_gemini(prompt)
            
            if post_text:
                print(f"✅ Сгенерировано: {len(post_text)} символов")
                
                success = False
                if channel == "telegram":
                    success = self.send_to_telegram(target_chat, post_text, image_url if use_image else None)
                else:
                    success = self.send_to_telegram(target_chat, post_text, None, is_zen=True)
                
                if success:
                    successes.append(channel)
                    self.update_stats(channel)
            
            time.sleep(2)
        
        print(f"\n📊 Итог: {len(successes)}/{len(current_slot['channels'])} успешно")
        return len(successes) > 0


def main():
    print("\n🚀 ЗАПУСК БОТА")
    print("📅 6 постов в день (3 ТГ + 3 Дзен)")
    print("=" * 80)
    
    bot = AIPostGenerator()
    success = bot.generate_and_send_posts()
    
    if success:
        print("\n🎉 УСПЕХ!")
    else:
        print("\n⚠️  Не удалось отправить")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
