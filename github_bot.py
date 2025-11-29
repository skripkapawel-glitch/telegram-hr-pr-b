import os
import requests
import datetime
import random
import sys
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: АКТУАЛЬНАЯ ИНФОРМАЦИЯ 2024-2025")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.author = "Маркетолог • SMM • PR • Копирайтер (40 лет опыта)"
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        
        # НАДЕЖНЫЕ изображения
        self.theme_images = {
            "HR и управление персоналом": [
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?ixlib=rb-4.0.3&w=1200&h=630&fit=crop"
            ],
            "PR и коммуникации": [
                "https://images.unsplash.com/photo-1432888622747-4eb9a8efeb07?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&w=1200&h=630&fit=crop", 
                "https://images.unsplash.com/photo-1551836026-d5c88ac5c4b0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop"
            ],
            "ремонт и строительство": [
                "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1484154218962-a197022b5858?ixlib=rb-4.0.3&w=1200&h=630&fit=crop"
            ]
        }
        
        # Резервные изображения если основные не работают
        self.fallback_images = [
            "https://picsum.photos/1200/630",
            "https://placekitten.com/1200/630",
            "https://picsum.photos/1200/630?grayscale"
        ]
        
        self.knowledge_base = {
            "HR и управление персоналом": [
                "В 2024 году компании активно внедряют AI в процессы рекрутинга - автоматизированное сканирование резюме и первичные собеседования с ботами",
                "Тренд 2024: развитие soft skills становится приоритетом - 78% компаний инвестируют в обучение эмоциональному интеллекту",
                "Diversity & Inclusion: 65% компаний внедрили программы разнообразия в 2024 году",
                "Цифровая трансформация HR: внедрение HRIS систем и мобильных приложений для сотрудников"
            ],
            "PR и коммуникации": [
                "Видеоконтент доминирует в 2024: short-form видео увеличивает вовлеченность на 300%",
                "LinkedIn становится ключевой B2B платформой - 85% B2B компаний используют его для PR",
                "AI-генерация контента: 45% PR-специалистов используют ChatGPT для пресс-релизов",
                "Data-driven PR: использование аналитики для измерения эффективности кампаний"
            ],
            "ремонт и строительство": [
                "Эко-тренды 2024: натуральные материалы и энергоэффективные решения в приоритете",
                "Умный дом становится стандартом - 60% новостроек включают системы автоматизации",
                "Модульные и сборные конструкции сокращают сроки строительства на 40%",
                "Биофильный дизайн: интеграция природы в интерьеры офисов и жилых пространств"
            ]
        }
        
    def load_post_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")
    
    def get_reliable_image(self, theme):
        """Возвращает надежное изображение с fallback"""
        try:
            # Сначала пробуем тематическое изображение
            theme_image = random.choice(self.theme_images.get(theme, self.theme_images["HR и управление персоналом"]))
            print(f"🖼️ Пробуем изображение: {theme_image}")
            return theme_image
        except:
            # Если ошибка - используем fallback
            fallback = random.choice(self.fallback_images)
            print(f"🖼️ Используем fallback: {fallback}")
            return fallback
    
    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram с обработкой ошибок изображения"""
        print(f"📤 Отправка в {chat_id}...")
        
        # Если есть изображение - пробуем отправить с фото
        if image_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": text,
                "parse_mode": "HTML"
            }
            
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    self.add_to_history(text, chat_id)
                    print(f"✅ Фото-пост отправлен в {chat_id}")
                    return True
                else:
                    print(f"❌ Ошибка фото-поста в {chat_id}: {response.text}")
                    # Пробуем отправить текстовый пост как запасной вариант
                    return self.send_text_to_telegram(chat_id, text)
            except Exception as e:
                print(f"❌ Ошибка отправки фото в {chat_id}: {e}")
                return self.send_text_to_telegram(chat_id, text)
        else:
            # Если нет изображения - отправляем текстовый пост
            return self.send_text_to_telegram(chat_id, text)
    
    def send_text_to_telegram(self, chat_id, text):
        """Отправляет текстовый пост в Telegram"""
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                self.add_to_history(text, chat_id)
                print(f"✅ Текстовый пост отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка текстового поста в {chat_id}: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Ошибка отправки текста в {chat_id}: {e}")
            return False
    
    def generate_post_hash(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def is_post_unique(self, post_text, channel_id):
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if channel_key not in self.post_history:
            self.post_history[channel_key] = []
        
        recent_posts = self.post_history[channel_key][-50:]
        return post_hash not in recent_posts
    
    def add_to_history(self, post_text, channel_id):
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if channel_key not in self.post_history:
            self.post_history[channel_key] = []
        
        self.post_history[channel_key].append(post_hash)
        if len(self.post_history[channel_key]) > 100:
            self.post_history[channel_key] = self.post_history[channel_key][-50:]
        
        self.save_post_history()
    
    def generate_simple_post(self, theme, is_tg=True):
        """Генерирует простой пост для тестирования"""
        facts = random.sample(self.knowledge_base[theme], 2)
        
        if is_tg:
            return f"""🚀 {theme.upper()} 2024-2025: АКТУАЛЬНЫЕ ТРЕНДЫ

{facts[0]}

⸻

{facts[1]}

⸻

• Практический совет 1
• Практический совет 2  
• Практический совет 3

⸻

Что думаете об этих трендах?

#{theme.replace(' ', '')} #тренды2025 #бизнес"""
        else:
            return f"""Актуальные тенденции {theme.lower()} 2024-2025

{facts[0]}

⸻

{facts[1]}

⸻

Современные вызовы требуют новых решений. Компании адаптируются к изменяющимся условиям.

⸻

Ключевые направления:

Цифровая трансформация
Внедрение современных технологических решений

Оптимизация процессов
Пересмотр традиционных подходов

Развитие компетенций  
Непрерывное обучение персонала

⸻

Стратегический подход позволяет создавать основу для будущего развития."""

    def add_tg_hashtags(self, theme):
        hashtags = {
            "HR и управление персоналом": "#HR #управление #команда #офис #персонал #2025",
            "PR и коммуникации": "#PR #коммуникации #бренд #медиа #маркетинг #2025", 
            "ремонт и строительство": "#ремонт #стройка #дизайн #интерьер #квартира #2025"
        }
        return hashtags.get(theme, "#2025")
    
    def send_dual_posts(self):
        theme = random.choice(self.themes)
        print(f"🎯 Выбрана тема: {theme}")
        
        # Получаем надежное изображение
        theme_image = self.get_reliable_image(theme)
        
        # Генерируем посты
        print("🧠 Генерация постов...")
        tg_post = self.generate_simple_post(theme, is_tg=True)
        zen_post = self.generate_simple_post(theme, is_tg=False)
        
        tg_full_post = f"{tg_post}\n\n{self.add_tg_hashtags(theme)}"
        
        print(f"📝 ТГ-пост: {len(tg_full_post)} символов")
        print(f"📝 Дзен-пост: {len(zen_post)} символов")
        
        # Отправляем в оба канала
        tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_full_post, theme_image)
        zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, theme_image)
        
        if tg_success and zen_success:
            print("✅ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ В ОБА КАНАЛА!")
            return True
        else:
            print(f"⚠️ ЕСТЬ ОШИБКИ: ТГ={tg_success}, Дзен={zen_success}")
            return tg_success or zen_success  # Возвращаем True если хоть один пост отправлен

def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА")
    print("🎯 Актуальная информация 2024-2025")
    print("🎯 Надежные изображения")
    print("=" * 80)
    
    bot = SmartPostGenerator()
    success = bot.send_dual_posts()
    
    if success:
        print("\n🎉 УСПЕХ! Посты отправлены!")
    else:
        print("\n💥 ЕСТЬ ОШИБКИ ОТПРАВКИ!")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
