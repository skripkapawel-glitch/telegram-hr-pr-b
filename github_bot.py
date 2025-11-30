import os
import requests
import random
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI-ГЕНЕРАЦИЯ С АНАЛИЗОМ ИЗОБРАЖЕНИЙ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Категории изображений для анализа схожести
        self.image_categories = {
            "HR и управление персоналом": ["офис", "команда", "встреча", "рабочее место", "презентация"],
            "PR и коммуникации": ["коммуникация", "медиа", "соцсети", "бренд", "презентация"],
            "ремонт и строительство": ["стройка", "инструменты", "интерьер", "архитектура", "материалы"]
        }

    def load_post_history(self):
        """Загружает историю постов и использованных изображений"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "used_images" not in data:
                        data["used_images"] = {}
                    if "image_analysis" not in data:
                        data["image_analysis"] = {}
                    return data
            return {"posts": {}, "themes": {}, "used_images": {}, "image_analysis": {}}
        except:
            return {"posts": {}, "themes": {}, "used_images": {}, "image_analysis": {}}
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def analyze_channel_images(self, channel_id):
        """Анализирует изображения в канале и возвращает их описание"""
        print(f"🔍 Анализируем изображения в канале {channel_id}...")
        
        # Здесь будет интеграция с AI для анализа изображений
        # Пока используем заглушку с категоризацией по темам
        
        channel_key = str(channel_id)
        if channel_key in self.post_history.get("image_analysis", {}):
            return self.post_history["image_analysis"][channel_key]
        
        # Заглушка - возвращаем случайные категории из последних постов
        recent_categories = []
        theme_categories = self.image_categories.get(self.current_theme, [])
        
        # Симулируем анализ 3 последних изображений
        for _ in range(min(3, len(theme_categories))):
            recent_categories.append(random.choice(theme_categories))
        
        analysis_result = {
            "dominant_colors": [],
            "common_subjects": recent_categories,
            "style": random.choice(["деловой", "креативный", "технический"]),
            "last_images_count": random.randint(1, 5)
        }
        
        # Сохраняем анализ
        if "image_analysis" not in self.post_history:
            self.post_history["image_analysis"] = {}
        self.post_history["image_analysis"][channel_key] = analysis_result
        
        return analysis_result

    def generate_image_prompt(self, theme, channel_id):
        """Генерирует промпт для создания уникального изображения"""
        channel_analysis = self.analyze_channel_images(channel_id)
        used_categories = channel_analysis.get("common_subjects", [])
        
        # Выбираем категории, которые НЕ использовались недавно
        available_categories = [cat for cat in self.image_categories.get(theme, []) 
                              if cat not in used_categories]
        
        # Если все категории использовались, берем наименее частые
        if not available_categories:
            available_categories = self.image_categories.get(theme, [])
        
        selected_category = random.choice(available_categories)
        style = channel_analysis.get("style", "профессиональный")
        
        prompt = f"""
        Создай изображение для поста на тему "{theme}".

        Требования к изображению:
        - Категория: {selected_category}
        - Стиль: {style}
        - Избегай: {', '.join(used_categories[:3]) if used_categories else 'стандартных решений'}
        - Формат: горизонтальный 1200x630 пикселей
        - Качество: профессиональное, четкое
        - Тон: соответствует бизнес-тематике

        Особенности:
        • Должно визуально отличаться от недавних постов в канале
        • Уникальная композиция
        • Современный дизайн
        """
        
        print(f"🎨 Промпт для изображения: {selected_category} (избегаем: {used_categories})")
        return prompt, selected_category

    def find_unique_image(self, theme, channel_id):
        """Находит уникальное изображение через AI анализ"""
        try:
            image_prompt, selected_category = self.generate_image_prompt(theme, channel_id)
            
            # Интеграция с AI для генерации/поиска изображения
            # Пока возвращаем заглушку для демонстрации
            print(f"🖼️ AI ищет уникальное изображение для темы '{theme}'")
            print(f"📋 Критерии: категория '{selected_category}', отличается от недавних постов")
            
            # В реальной реализации здесь будет вызов API для генерации изображения
            # Например: DALL-E, Midjourney, Stable Diffusion или поиск через Unsplash API
            
            # Заглушка - возвращаем None, так как нет реального API
            print("⚠️ Режим демонстрации: изображения не генерируются")
            return None
            
        except Exception as e:
            print(f"❌ Ошибка поиска изображения: {e}")
            return None

    def get_smart_theme(self, channel_id):
        last_themes = self.get_last_themes(channel_id, 2)
        
        available_themes = self.themes.copy()
        
        if last_themes:
            last_theme = last_themes[-1]
            if last_theme in available_themes:
                available_themes.remove(last_theme)
                print(f"🎯 Исключили последнюю тему: {last_theme}")
        
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = random.choice(available_themes)
        print(f"🎯 Выбрана тема: {theme} (история: {last_themes})")
        return theme

    def get_last_themes(self, channel_id, count=3):
        channel_key = str(channel_id)
        themes = self.post_history.get("themes", {}).get(channel_key, [])
        return themes[-count:] if len(themes) >= count else themes
    
    def add_theme_to_history(self, channel_id, theme):
        channel_key = str(channel_id)
        
        if "themes" not in self.post_history:
            self.post_history["themes"] = {}
        if channel_key not in self.post_history["themes"]:
            self.post_history["themes"][channel_key] = []
        
        self.post_history["themes"][channel_key].append(theme)
        if len(self.post_history["themes"][channel_key]) > 10:
            self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-10:]
        
        self.save_post_history()

    def generate_with_gemini(self, prompt):
        try:
            print("🧠 Запрос к Gemini API...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            response = requests.post(
                url,
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 800,
                        "temperature": 0.9,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                generated_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print("✅ Текст сгенерирован")
                return generated_text
            else:
                print(f"❌ Ошибка Gemini: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return None

    def generate_tg_post(self, theme):
        prompt = f"""
        Напиши пост для Telegram на тему "{theme}" за 2024-2025 год.

        Требования:
        - Пиши как настоящий человек
        - Будь профессионален, но естественен
        - Избегай клише и корпоративного жаргона
        - Используй символ • для разделения пунктов
        - Каждый пункт с новой строки
        - Пост должен содержать:
          1. Цепляющий заголовок
          2. 2-3 актуальных факта или тренда (через •)
          3. Раздел "Что работает сейчас:" с 3 пунктами
          4. Вопрос для вовлечения аудитории
        - Длина: 400-600 символов
        - Говори о реальных кейсах

        Тема: {theme}
        """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            formatted_text = self.format_tg_post(generated_text)
            hashtags = self.add_tg_hashtags(theme)
            return f"{formatted_text}\n\n{hashtags}"
        else:
            return self.generate_fallback_tg_post(theme)

    def format_tg_post(self, text):
        """Форматирует пост для Telegram с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                if line.startswith('•'):
                    line = f"    {line}"
                elif any(keyword in line.lower() for keyword in ['что работает', 'советы:', 'рекомендации:']):
                    if formatted_lines:
                        formatted_lines.append('')
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_zen_post(self, theme):
        prompt = f"""
        Напиши структурированный пост для Яндекс.Дзен на тему "{theme}" за 2024-2025 год.

        Требования:
        - Стиль: профессиональная аналитика, но человеческим языком
        - Четкая структура с подзаголовками
        - Без корпоративного жаргона
        - Конкретные примеры и цифры
        - Без эмодзи и хештегов
        - Используй символ • для визуального разделения пунктов
        - Каждый пункт должен быть законченным предложением с точкой
        - Пост должен содержать:
          1. Заголовок
          2. Введение с актуальными данными
          3. Раздел "Ключевые направления:" 
          4. 3 пункта с символом • и конкретными рекомендациями
        - Длина: 600-900 символов

        Тема: {theme}
        """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            return self.format_zen_post(generated_text)
        else:
            return self.generate_fallback_zen_post(theme)

    def format_zen_post(self, text):
        """Форматирует пост для Дзена с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                if line.startswith('•'):
                    line = f"    {line}"
                elif any(keyword in line.lower() for keyword in ['ключевые направления', 'основные тренды', 'рекомендации:']):
                    if formatted_lines:
                        formatted_lines.append('')
                
                if not line.endswith(('.', '!', '?')) and len(line.split()) > 3:
                    line = line + '.'
                    
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_fallback_tg_post(self, theme):
        """Резервные посты для Telegram"""
        fallbacks = {
            "HR и управление персоналом": [
                """HR в 2024: нанимают не навыки, а mindset

    • 78% компаний ищут кандидатов с эмоциональным интеллектом
    • AI обрабатывает 65% резюме

Что работает сейчас:

    • Смотрите на soft skills — технике научить проще
    • Внедрите пробный день вместо собеседований  
    • Давайте фидбек даже отказанным кандидатам

Что сработало в вашей практике?

#HR #управление #команда""",
            ],
            "PR и коммуникации": [
                """PR в 2024: что реально работает

    • LinkedIn стал главной B2B-площадкой
    • Короткие видео +300% к вовлеченности

Что работает сейчас:

    • Делайте личный бренд руководителей
    • Снимите 30-секундное видео вместо пресс-релиза
    • Дайте эксперту пообщаться в комментариях

Какие тренды пробовали?

#PR #коммуникации #LinkedIn""",
            ],
            "ремонт и строительство": [
                """Ремонт в 2024: тренды, которые останутся

    • 72% выбирают натуральные материалы
    • Умный дом стал must-have

Что работает сейчас:

    • Используйте локальные материалы
    • Заложите умные системы заранее
    • Сделайте универсальную базу

Что из этого пробовали?

#ремонт #стройка #дизайн""",
            ]
        }
        return random.choice(fallbacks.get(theme, ["Актуальные тренды 2024-2025. #тренды"]))

    def generate_fallback_zen_post(self, theme):
        """Резервные посты для Дзена"""
        fallbacks = {
            "HR и управление персоналом": [
                """Современные подходы к управлению персоналом

68% сотрудников остаются там, где есть возможности для развития. Гибкий график работы стал новым стандартом в индустрии.

Ключевые направления:

    • Развитие вместо денежных стимулов. Создавайте индивидуальные карты профессионального роста для каждого сотрудника.

    • Баланс работы и личных интересов. Возможность работать над персональными проектами значительно снижает риски выгорания.

    • Открытая коммуникация. Регулярные встречи должны фокусироваться на стратегических целях и текущем состоянии команды.""",
            ],
            "PR и коммуникации": [
                """Трансформация PR-коммуникаций

45% компаний уже используют искусственный интеллект для создания материалов. Современная аудитория больше доверяет микроинфлюенсерам, чем крупным блогерам.

Ключевые направления:

    • Простота и ясность сообщений. Необходимо говорить на языке целевой аудитории, избегая профессионального жаргона.

    • Прозрачность и аутентичность контента. Демонстрация рабочего процесса создает устойчивое доверие у подписчиков.

    • Формирование активного сообщества. Регулярные ответы на комментарии превращают пассивную аудиторию в активных участников.""",
            ]
        }
        return random.choice(fallbacks.get(theme, ["Актуальные тенденции 2024-2025 года."]))

    def add_tg_hashtags(self, theme):
        hashtags = {
            "HR и управление персоналом": "#HR #управление #команда",
            "PR и коммуникации": "#PR #коммуникации #маркетинг", 
            "ремонт и строительство": "#ремонт #стройка #дизайн"
        }
        return hashtags.get(theme, "")
    
    def send_to_telegram(self, chat_id, text, image_url=None):
        print(f"📤 Отправка в {chat_id}...")
        
        if not image_url:
            return self.send_text_to_telegram(chat_id, text)
            
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
                if self.current_theme:
                    self.add_theme_to_history(chat_id, self.current_theme)
                print(f"✅ Пост с изображением отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки с изображением: {response.text}")
                return self.send_text_to_telegram(chat_id, text)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return self.send_text_to_telegram(chat_id, text)
    
    def send_text_to_telegram(self, chat_id, text):
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
                if self.current_theme:
                    self.add_theme_to_history(chat_id, self.current_theme)
                print(f"✅ Текстовый пост отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False
    
    def generate_post_hash(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def is_post_unique(self, post_text, channel_id):
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if "posts" not in self.post_history:
            self.post_history["posts"] = {}
        if channel_key not in self.post_history["posts"]:
            self.post_history["posts"][channel_key] = []
        
        recent_posts = self.post_history["posts"][channel_key][-50:]
        return post_hash not in recent_posts
    
    def add_to_history(self, post_text, channel_id):
        post_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if "posts" not in self.post_history:
            self.post_history["posts"] = {}
        if channel_key not in self.post_history["posts"]:
            self.post_history["posts"][channel_key] = []
        
        self.post_history["posts"][channel_key].append(post_hash)
        if len(self.post_history["posts"][channel_key]) > 100:
            self.post_history["posts"][channel_key] = self.post_history["posts"][channel_key][-50:]
        
        self.save_post_history()
    
    def send_dual_posts(self):
        self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
        
        print(f"🎯 Умный выбор темы: {self.current_theme}")
        
        # AI анализ и поиск уникального изображения
        theme_image = self.find_unique_image(self.current_theme, MAIN_CHANNEL_ID)
        
        print("🧠 Генерация постов...")
        tg_post = self.generate_tg_post(self.current_theme)
        zen_post = self.generate_zen_post(self.current_theme)
        
        print(f"📝 ТГ-пост: {len(tg_post)} символов")
        print(f"📝 Дзен-пост: {len(zen_post)} символов")
        
        if not self.is_post_unique(tg_post, MAIN_CHANNEL_ID):
            print("⚠️ Пост для ТГ не уникален, генерируем заново...")
            return self.send_dual_posts()
            
        if not self.is_post_unique(zen_post, ZEN_CHANNEL_ID):
            print("⚠️ Пост для Дзена не уникален, генерируем заново...")  
            return self.send_dual_posts()
        
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

def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА")
    print("🎯 Проверка истории перед генерацией")
    print("🎯 Исключение повторяющихся тем")
    print("🖼️ AI анализ изображений в каналах")
    print("🎨 Поиск уникальных визуальных решений")
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
