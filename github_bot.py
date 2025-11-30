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
print("🚀 УМНЫЙ БОТ: AI-ГЕНЕРАЦИЯ С ГЛУБОКИМ АНАЛИЗОМ ИСТОРИИ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Гарантированные изображения для каждой темы
        self.guaranteed_images = {
            "HR и управление персоналом": [
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "PR и коммуникации": [
                "https://images.unsplash.com/photo-1432888622747-4eb9a8efeb07?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "ремонт и строительство": [
                "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1541976590-713941681591?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ]
        }
        
        # Резервные изображения
        self.fallback_images = [
            "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
        ]

    def load_post_history(self):
        """Загружает историю постов с полными текстами"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Инициализируем структуры если их нет
                    if "full_posts" not in data:
                        data["full_posts"] = {}
                    if "used_images" not in data:
                        data["used_images"] = {}
                    return data
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}}
        except Exception as e:
            print(f"❌ Ошибка загрузки истории: {e}")
            return {"posts": {}, "themes": {}, "full_posts": {}, "used_images": {}}
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def analyze_channel_history(self, channel_id, theme):
        """Анализирует историю постов в канале для выявления повторяющегося контента"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history:
            self.post_history["full_posts"] = {}
        if channel_key not in self.post_history["full_posts"]:
            self.post_history["full_posts"][channel_key] = []
        
        recent_posts = self.post_history["full_posts"][channel_key][-10:]  # Последние 10 постов
        
        if not recent_posts:
            return "Нет истории постов для анализа"
        
        # Собираем ключевые темы и фразы из истории
        analysis_prompt = f"""
        Проанализируй историю постов в канале и выдели основные темы, фразы и идеи, которые УЖЕ использовались.
        
        Тема для нового поста: {theme}
        
        История последних постов:
        {chr(10).join([f'{i+1}. {post[:200]}...' for i, post in enumerate(recent_posts)])}
        
        Задача: определить какие аспекты темы '{theme}' уже освещались и какие новые углы можно рассмотреть.
        Верни только список уже использованных идей и рекомендации что нового осветить.
        """
        
        try:
            analysis_result = self.generate_with_gemini(analysis_prompt)
            return analysis_result if analysis_result else "Не удалось проанализировать историю"
        except:
            return "Ошибка анализа истории"

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом полной истории"""
        last_themes = self.get_last_themes(channel_id, 3)  # Смотрим 3 последние темы
        
        available_themes = self.themes.copy()
        
        # Исключаем последние 2 темы
        for theme in last_themes[-2:]:
            if theme in available_themes:
                available_themes.remove(theme)
                print(f"🎯 Исключили недавнюю тему: {theme}")
        
        # Если все темы использовались, делаем ротацию
        if not available_themes:
            available_themes = self.themes.copy()
            print("🔄 Все темы использовались, делаем ротацию")
        
        theme = random.choice(available_themes)
        print(f"🎯 Выбрана тема: {theme} (история: {last_themes})")
        return theme

    def get_last_themes(self, channel_id, count=5):
        """Возвращает последние N тем для канала"""
        channel_key = str(channel_id)
        themes = self.post_history.get("themes", {}).get(channel_key, [])
        return themes[-count:] if len(themes) >= count else themes

    def generate_with_context(self, theme, channel_id, post_type="telegram"):
        """Генерирует пост с учетом контекста истории канала"""
        
        # Анализируем историю канала
        history_analysis = self.analyze_channel_history(channel_id, theme)
        print(f"📊 Анализ истории: {history_analysis[:100]}...")
        
        if post_type == "telegram":
            prompt = f"""
            Напиши УНИКАЛЬНЫЙ пост для Telegram на тему "{theme}" за 2024-2025 год.

            ВАЖНО: Этот пост должен кардинально отличаться от предыдущих публикаций в канале.

            Анализ истории канала:
            {history_analysis}

            Требования к посту:
            - АБСОЛЮТНАЯ УНИКАЛЬНОСТЬ: не повторяй идеи, фразы и структуры из истории
            - Новый угол зрения на тему {theme}
            - Пиши как настоящий человек, без клише
            - Используй символ • для разделения пунктов
            - Структура:
              1. Цепляющий заголовок (новый подход)
              2. 2-3 СВЕЖИХ факта или тренда (не из истории)
              3. Раздел "Что работает сейчас:" с 3 НОВЫМИ советами
              4. Уникальный вопрос для вовлечения
            - Длина: 400-600 символов
            - Избегай любых повторений из анализа истории выше

            Создай полностью оригинальный контент!
            """
        else:
            prompt = f"""
            Напиши УНИКАЛЬНЫЙ аналитический пост для Яндекс.Дзен на тему "{theme}" за 2024-2025 год.

            ВАЖНО: Этот пост должен кардинально отличаться от предыдущих публикаций в канале.

            Анализ истории канала:
            {history_analysis}

            Требования:
            - АБСОЛЮТНАЯ УНИКАЛЬНОСТЬ: не повторяй идеи, фразы и структуры из истории
            - Профессиональная аналитика с новыми данными
            - Без корпоративного жаргона
            - Конкретные примеры и цифры (новые)
            - Без эмодзи и хештегов
            - Используй символ • для визуального разделения
            - Структура:
              1. Заголовок (новый подход)
              2. Введение с АКТУАЛЬНЫМИ данными (не из истории)
              3. Раздел "Ключевые направления:" с 3 НОВЫМИ пунктами
            - Длина: 600-900 символов

            Создай полностью оригинальный контент!
            """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            # Дополнительная проверка уникальности
            if self.is_content_unique(generated_text, channel_id):
                return generated_text
            else:
                print("⚠️ Сгенерированный контент похож на существующий, пробуем снова...")
                return self.generate_with_context(theme, channel_id, post_type)
        else:
            return self.generate_fallback_post(theme, post_type)

    def is_content_unique(self, new_content, channel_id, similarity_threshold=0.8):
        """Проверяет уникальность контента по сравнению с историей"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history or channel_key not in self.post_history["full_posts"]:
            return True
        
        recent_posts = self.post_history["full_posts"][channel_key][-10:]
        
        if not recent_posts:
            return True
        
        # Простая проверка на схожесть (можно улучшить с помощью embeddings)
        new_content_lower = new_content.lower()
        
        for old_post in recent_posts:
            old_post_lower = old_post.lower()
            # Проверяем совпадение ключевых фраз
            common_words = set(new_content_lower.split()) & set(old_post_lower.split())
            similarity = len(common_words) / max(len(set(new_content_lower.split())), 1)
            
            if similarity > similarity_threshold:
                print(f"⚠️ Обнаружена схожесть: {similarity:.2f}")
                return False
        
        return True

    def get_guaranteed_image(self, theme):
        """Гарантированно возвращает изображение для темы"""
        print(f"🖼️ Поиск гарантированного изображения для темы: {theme}")
        
        theme_images = self.guaranteed_images.get(theme, []) + self.fallback_images
        
        if not theme_images:
            print("❌ Нет доступных изображений для темы")
            return None
        
        theme_key = theme
        if "used_images" not in self.post_history:
            self.post_history["used_images"] = {}
        if theme_key not in self.post_history["used_images"]:
            self.post_history["used_images"][theme_key] = []
        
        used_images = self.post_history["used_images"][theme_key]
        recent_used = used_images[-5:] if len(used_images) >= 5 else used_images
        available_images = [img for img in theme_images if img not in recent_used]
        
        if not available_images:
            print("🔄 Все изображения использовались, выбираем из всех")
            available_images = theme_images
        
        selected_image = random.choice(available_images)
        
        self.post_history["used_images"][theme_key].append(selected_image)
        if len(self.post_history["used_images"][theme_key]) > 10:
            self.post_history["used_images"][theme_key] = self.post_history["used_images"][theme_key][-5:]
        
        self.save_post_history()
        
        print(f"✅ Выбрано изображение: {selected_image}")
        return selected_image

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
                        "maxOutputTokens": 1000,
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
        """Генерирует пост для Telegram с учетом контекста"""
        return self.generate_with_context(theme, MAIN_CHANNEL_ID, "telegram")

    def generate_zen_post(self, theme):
        """Генерирует пост для Дзена с учетом контекста"""
        return self.generate_with_context(theme, ZEN_CHANNEL_ID, "zen")

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

    def generate_fallback_post(self, theme, post_type):
        """Резервные посты с вариациями"""
        fallbacks_tg = {
            "HR и управление персоналом": [
                """Современный HR: тренды 2025 года

    • 81% компаний внедряют AI в процессы найма
    • Геймификация тестов увеличивает вовлеченность на 45%

Что актуально сейчас:

    • Внедряйте системы менторства для новых сотрудников
    • Используйте данные аналитики для персонализации развития
    • Создавайте программы wellness для профилактики выгорания

Как адаптируете HR-процессы под новые реалии?

#HR #тренды2025 #управление""",
            ],
            "PR и коммуникации": [
                """PR в эпоху цифровой трансформации

    • Виртуальные ивенты собирают на 60% больше аудитории
    • Подкасты становятся ключевым каналом B2B-коммуникаций

Современные подходы:

    • Разрабатывайте интерактивный контент вместо статических пресс-релизов
    • Используйте data-driven сторителлинг в коммуникациях
    • Создавайте экосистемы партнерского контента

Какие инструменты digital-PR используете?

#PR #digital #коммуникации""",
            ]
        }
        
        fallbacks_zen = {
            "HR и управление персоналом": [
                """Эволюция управления персоналом в 2025 году

Современные исследования показывают, что 81% организаций активно внедряют искусственный интеллект в процессы подбора персонала. Геймификация оценочных тестов демонстрирует рост вовлеченности кандидатов на 45%.

Ключевые направления развития:

    • Системы наставничества и менторства. Интеграция программ адаптации для новых сотрудников ускоряет их вхождение в должность.

    • Персонализация развития. Использование аналитики данных позволяет создавать индивидуальные траектории профессионального роста.

    • Профилактика эмоционального выгорания. Внедрение wellness-программ способствует сохранению психического здоровья сотрудников.""",
            ]
        }
        
        if post_type == "telegram":
            fallback = random.choice(fallbacks_tg.get(theme, ["Актуальные тренды 2024-2025. #тренды"]))
            hashtags = self.add_tg_hashtags(theme)
            return f"{fallback}\n\n{hashtags}"
        else:
            return random.choice(fallbacks_zen.get(theme, ["Актуальные тенденции 2024-2025 года."]))

    def add_tg_hashtags(self, theme):
        hashtags = {
            "HR и управление персоналом": "#HR #управление #команда",
            "PR и коммуникации": "#PR #коммуникации #маркетинг", 
            "ремонт и строительство": "#ремонт #стройка #дизайн"
        }
        return hashtags.get(theme, "")

    def add_theme_to_history(self, channel_id, theme):
        channel_key = str(channel_id)
        
        if "themes" not in self.post_history:
            self.post_history["themes"] = {}
        if channel_key not in self.post_history["themes"]:
            self.post_history["themes"][channel_key] = []
        
        self.post_history["themes"][channel_key].append(theme)
        if len(self.post_history["themes"][channel_key]) > 15:
            self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-10:]
        
        self.save_post_history()

    def add_full_post_to_history(self, channel_id, post_text):
        """Сохраняет полный текст поста в историю"""
        channel_key = str(channel_id)
        
        if "full_posts" not in self.post_history:
            self.post_history["full_posts"] = {}
        if channel_key not in self.post_history["full_posts"]:
            self.post_history["full_posts"][channel_key] = []
        
        self.post_history["full_posts"][channel_key].append(post_text)
        if len(self.post_history["full_posts"][channel_key]) > 20:
            self.post_history["full_posts"][channel_key] = self.post_history["full_posts"][channel_key][-15:]
        
        self.save_post_history()

    def send_to_telegram(self, chat_id, text, image_url=None):
        print(f"📤 Отправка в {chat_id}...")
        
        if not image_url:
            print("❌ Нет изображения, используем гарантированное")
            image_url = self.get_guaranteed_image(self.current_theme)
            
        if not image_url:
            print("❌ Критическая ошибка: не удалось получить изображение!")
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
                self.add_full_post_to_history(chat_id, text)
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
                self.add_full_post_to_history(chat_id, text)
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
        
        # Глубокий анализ истории перед генерацией
        print("🔍 Анализируем историю постов для обеспечения уникальности...")
        
        # Гарантированное получение изображения
        theme_image = self.get_guaranteed_image(self.current_theme)
        
        if not theme_image:
            print("❌ Критическая ошибка: не удалось получить изображение!")
            return False
        
        print("🧠 Генерация УНИКАЛЬНЫХ постов с учетом истории...")
        tg_post = self.generate_tg_post(self.current_theme)
        zen_post = self.generate_zen_post(self.current_theme)
        
        print(f"📝 ТГ-пост: {len(tg_post)} символов")
        print(f"📝 Дзен-пост: {len(zen_post)} символов")
        
        # Проверка уникальности
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
            print("✅ УНИКАЛЬНЫЕ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫ!")
            return True
        else:
            print(f"⚠️ Есть ошибки: ТГ={tg_success}, Дзен={zen_success}")
            return tg_success or zen_success

def main():
    print("\n🚀 ЗАПУСК УМНОГО ГЕНЕРАТОРА")
    print("🎯 Глубокий анализ истории постов")
    print("🎯 Исключение повторяющегося контента") 
    print("🎯 Гарантированная уникальность каждого поста")
    print("🖼️ Гарантированные изображения")
    print("=" * 80)
    
    bot = SmartPostGenerator()
    success = bot.send_dual_posts()
    
    if success:
        print("\n🎉 УСПЕХ! Уникальные посты с изображениями отправлены!")
    else:
        print("\n💥 КРИТИЧЕСКАЯ ОШИБКА ОТПРАВКИ!")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
