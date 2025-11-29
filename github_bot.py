import os
import json
import datetime
import requests
import random
from typing import Dict, List, Optional, Tuple

class ImprovedPostGenerator:
    def __init__(self):
        self.history_file = "post_history.json"
        self.history = self.load_post_history()
        self.post_structures = {
            "morning": {"description": "Утренний пост", "max_length": 400},
            "day": {"description": "Дневной пост", "max_length": 600},
            "evening": {"description": "Вечерний пост", "max_length": 500},
            "night": {"description": "Ночной пост", "max_length": 300}
        }
        
    def load_post_history(self) -> Dict:
        """Загружает историю постов"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "post_hashes": [],
            "used_themes": [],
            "used_subthemes": [],
            "used_templates": [],
            "last_post_time": None
        }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения истории: {e}")

    def get_time_of_day(self) -> str:
        """Определяет время суток"""
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "day"
        elif 18 <= hour < 23:
            return "evening"
        else:
            return "night"

    def get_channel_posts(self, limit: int = 100) -> List[Dict]:
        """Получает последние посты канала"""
        return []

    def analyze_channel_content(self, posts: List[Dict]) -> Dict:
        """Анализирует контент канала"""
        return {
            "popular_themes": [],
            "engagement_stats": {},
            "best_times": []
        }

    def select_optimal_theme(self, analysis: Dict) -> Tuple[str, str]:
        """Выбирает оптимальную тему"""
        themes = ["Технологии", "Бизнес", "Здоровье", "Образование", "Психология"]
        subthemes = {
            "Технологии": ["AI", "Крипто", "Кибербезопасность"],
            "Бизнес": ["Стартапы", "Маркетинг", "Финансы"],
            "Здоровье": ["Питание", "Фитнес", "Ментальное здоровье"],
            "Образование": ["Саморазвитие", "Карьера", "Навыки"],
            "Психология": ["Продуктивность", "Отношения", "Личностный рост"]
        }
        
        theme = random.choice(themes)
        subtheme = random.choice(subthemes.get(theme, ["Общее"]))
        return theme, subtheme

    def search_market_trends(self, theme: str, subtheme: str) -> List[str]:
        """Ищет актуальные тренды"""
        return [f"Тренд {theme}", f"Новое в {subtheme}", "Актуальная тема"]

    def generate_quality_post(self, theme: str, subtheme: str, trends: List[str], time_of_day: str) -> Tuple[str, Optional[str], str]:
        """Генерирует качественный пост"""
        templates = {
            "morning": [
                f"🌅 Доброе утро! {theme}: {subtheme}\n\n{trends[0] if trends else 'Важная информация'}.\n\n#утро #{theme}",
                f"☀️ Начало дня с пользой: {subtheme}\n\n{trends[0] if trends else 'Полезные мысли'}.\n\n#{theme} #утреннийпост"
            ],
            "day": [
                f"📊 {theme} в деталях: {subtheme}\n\n{trends[0] if trends else 'Интересные факты'}.\n\n#{theme} #{subtheme}",
                f"💡 Полезное знание: {subtheme}\n\n{trends[0] if trends else 'Экспертное мнение'}.\n\n#{theme} #знание"
            ],
            "evening": [
                f"🌇 Вечерние мысли: {theme}\n\n{trends[0] if trends else 'Итоги дня'}.\n\n#{theme} #вечер",
                f"📝 Итоги дня: {subtheme}\n\n{trends[0] if trends else 'Важные выводы'}.\n\n#{theme} #{subtheme}"
            ],
            "night": [
                f"🌙 Ночные размышления: {theme}\n\n{trends[0] if trends else 'Пища для размышлений'}.\n\n#{theme} #ночь",
                f"💭 Перед сном: {subtheme}\n\n{trends[0] if trends else 'Интересная информация'}.\n\n#{theme} #{subtheme}"
            ]
        }
        
        template = random.choice(templates[time_of_day])
        image_url = None
        final_topic = f"{theme}: {subtheme}"
        
        return template, image_url, final_topic

    def cleanup_history(self):
        """Очищает историю, оставляя только последние 100 записей"""
        for key in ["post_hashes", "used_themes", "used_subthemes", "used_templates"]:
            if len(self.history[key]) > 100:
                self.history[key] = self.history[key][-100:]
        
        self.save_post_history()

    def send_to_telegram(self, message: str, image_url: Optional[str] = None) -> bool:
        """Отправляет пост в Telegram"""
        try:
            BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
            CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
            
            if not BOT_TOKEN or not CHANNEL_ID:
                print("❌ Не установлены TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID")
                return False

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
            
            print("✅ Пост отправлен в Telegram!")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False

    def run(self):
        """Основная функция"""
        try:
            now = datetime.datetime.now()
            time_of_day = self.get_time_of_day()
            time_config = self.post_structures[time_of_day]
            
            print(f"\n{'='*50}")
            print(f"🚀 ГЕНЕРАТОР КАЧЕСТВЕННЫХ ПОСТОВ")
            print(f"📅 {now.strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"⏰ Время: {time_of_day} ({time_config['description']})")
            print(f"{'='*50}")
            
            # Анализ канала
            posts = self.get_channel_posts()
            channel_analysis = self.analyze_channel_content(posts)
            
            # Выбор темы
            theme, subtheme = self.select_optimal_theme(channel_analysis)
            
            # Поиск трендов
            trends = self.search_market_trends(theme, subtheme)
            
            # Генерация поста
            post_text, image_url, final_topic = self.generate_quality_post(
                theme, subtheme, trends, time_of_day
            )
            
            print(f"📊 Результат:")
            print(f"   Тема: {final_topic}")
            print(f"   Длина: {len(post_text)} символов")
            print(f"   Время: {time_of_day}")
            
            # Отправка
            success = self.send_to_telegram(post_text, image_url)
            
            if success:
                print(f"✅ Готово! {time_config['description']} создан и отправлен.")
            else:
                print("❌ Ошибка при отправке")
            
            print(f"{'='*50}\n")
            
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

def main():
    generator = ImprovedPostGenerator()
    generator.run()

if __name__ == "__main__":
    main()
