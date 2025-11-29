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
print("🚀 УМНЫЙ БОТ: AI-ГЕНЕРАЦИЯ С ПРОВЕРКОЙ УНИКАЛЬНОСТИ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        self.theme_images = {
            "HR и управление персоналом": [
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "PR и коммуникации": [
                "https://images.unsplash.com/photo-1432888622747-4eb9a8efeb07?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&w=1200&h=630&fit=crop", 
            ],
            "ремонт и строительство": [
                "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ]
        }
        
        self.fallback_images = [
            "https://picsum.photos/1200/630",
            "https://placekitten.com/1200/630",
        ]

    def load_post_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            return {"posts": {}, "themes": {}}
        except:
            return {"posts": {}, "themes": {}}
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")
    
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

    def get_reliable_image(self, theme):
        try:
            theme_image = random.choice(self.theme_images.get(theme, self.theme_images["HR и управление персоналом"]))
            print(f"🖼️ Используем изображение: {theme_image}")
            return theme_image
        except:
            fallback = random.choice(self.fallback_images)
            print(f"🖼️ Используем fallback: {fallback}")
            return fallback

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
        - Пост должен содержать:
          1. Цепляющий заголовок
          2. 2-3 актуальных факта или тренда
          3. 3 практических совета
          4. Вопрос для вовлечения аудитории
        - Длина: 400-600 символов
        - Говори о реальных кейсах

        Тема: {theme}
        """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            hashtags = self.add_tg_hashtags(theme)
            return f"{generated_text}\n\n{hashtags}"
        else:
            return self.generate_fallback_tg_post(theme)

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
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                if not line.endswith(('.', '!', '?')) and len(line.split()) > 3:
                    line = line + '.'
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_fallback_tg_post(self, theme):
        fallbacks = {
            "HR и управление персоналом": [
                """HR в 2024: нанимают не навыки, а mindset

78% компаний ищут кандидатов с эмоциональным интеллектом • AI обрабатывает 65% резюме

Что работает сейчас:
Смотрите на soft skills — технике научить проще
Внедрите пробный день вместо собеседований
Давайте фидбек даже отказанным кандидатам

Что сработало в вашей практике?

#HR #управление #команда""",
                
                """Как удерживать команду в 2024

68% сотрудников ценят обучение выше зарплаты • Гибкий график стал стандартом

Что работает сейчас:
Создайте карту развития для каждой позиции
Разрешите работать над личными проектами
Проводите встречи о целях, а не задачах

Как мотивируете команду?

#HR #управление #развитие"""
            ],
            
            "PR и коммуникации": [
                """PR в 2024: что реально работает

LinkedIn стал главной B2B-площадкой • Короткие видео +300% к вовлеченности

Что работает сейчас:
Делайте личный бренд руководителей
Снимите 30-секундное видео вместо пресс-релиза
Дайте эксперту пообщаться в комментариях

Какие тренды пробовали?

#PR #коммуникации #LinkedIn""",
                
                """Коммуникации, которые доходят до людей

45% используют AI для материалов • Микро-инфлюенсерам доверяют больше

Что работает сейчас:
Говорите на языке клиента
Показывайте закулисье проектов
Отвечайте на комментарии лично

Что лучше сработало у вас?

#PR #коммуникации #бренд"""
            ],
            
            "ремонт и строительство": [
                """Ремонт в 2024: тренды, которые останутся

72% выбирают натуральные материалы • Умный дом стал must-have

Что работает сейчас:
Используйте локальные материалы
Заложите умные системы заранее
Сделайте универсальную базу

Что из этого пробовали?

#ремонт #стройка #дизайн""",
                
                """Строительство без стресса в 2024

Модульные конструкции экономят 40% времени • Дроны экономят 25% бюджета

Что работает сейчас:
Создайте цифровой двойник объекта
Используйте BIM-моделирование
Ведите онлайн-дневник стройки

Как оптимизируете процессы?

#ремонт #стройка #технологии"""
            ]
        }
        return random.choice(fallbacks.get(theme, ["Актуальные тренды 2024-2025. #тренды"]))

    def generate_fallback_zen_post(self, theme):
        fallbacks = {
            "HR и управление персоналом": [
                """Современные подходы к управлению персоналом

68% сотрудников остаются где есть развитие. Гибкий график стал стандартом.

Ключевые направления:

•Развитие вместо денежных стимулов. Создавайте карты профессионального роста.

•Баланс работы и личных интересов. Работа над персональными проектами снижает выгорание.

•Открытая коммуникация. Встречи должны фокусироваться на целях и состоянии.""",
                
                """Как изменился HR в 2024: новые правила найма

78% компаний ищут кандидатов с эмоциональным интеллектом. AI обрабатывает 65% резюме.

Ключевые направления:

•Мягкие навыки вместо жестких требований. Техническим навыкам можно научить, а мышление меняется долго.

•Прозрачность процесса найма. Внедрите пробный день вместо многоэтапных собеседований.

•Постоянная обратная связь. Давайте фидбек даже тем, кого не взяли."""
            ],
            
            "PR и коммуникации": [
                """Трансформация PR-коммуникаций

45% используют искусственный интеллект. Аудитория доверяет микроинфлюенсерам.

Ключевые направления:

•Простота и ясность. Говорите на языке аудитории.

•Прозрачность и аутентичность. Демонстрация закулисья создает доверие.

•Формирование сообщества. Ответы на комментарии создают активное сообщество.""",
                
                """PR в 2024: коммуникации, которые работают

LinkedIn стал главной B2B-площадкой. Короткие видео дают +300% вовлеченности.

Ключевые направления:

•Личный бренд вместо корпоративного. Люди доверяют людям, а не компаниям.

•Видеоконтент вместо текстового. Короткие видео собирают в 3 раза больше просмотров.

•Диалог с аудиторией вместо монолога. Комментарии стали важнее контента."""
            ],
            
            "ремонт и строительство": [
                """Строительство и ремонт в 2024: новые тренды

72% выбирают натуральные материалы. Умный дом стал must-have для новостроек.

Ключевые направления:

•Натуральные и локальные материалы. Использование местных материалов экологичнее.

•Технологии как основа. Заложите умные системы на этапе отделки.

•Гибкость пространства. Универсальная база дешевле нового ремонта.""",
                
                """Инновации в строительстве 2024

Модульные конструкции экономят 40% времени. Дроны экономят 25% бюджета.

Ключевые направления:

•Цифровое проектирование. Цифровые двойники помогают устранить ошибки.

•Прозрачность для заказчика. Онлайн-дневник стройки информирует клиента.

•Оптимизация через технологии. BIM-моделирование показывает проблемы заранее."""
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
                    if self.current_theme:
                        self.add_theme_to_history(chat_id, self.current_theme)
                    print(f"✅ Пост отправлен в {chat_id}")
                    return True
                else:
                    print(f"❌ Ошибка: {response.text}")
                    return self.send_text_to_telegram(chat_id, text)
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                return self.send_text_to_telegram(chat_id, text)
        else:
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
        
        theme_image = self.get_reliable_image(self.current_theme)
        
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
