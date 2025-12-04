import os
import requests
import random
import json
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Список доступных моделей для тестирования
GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
]

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Канал: {MAIN_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.working_model = None
        
        # Временные слоты с объемами
        self.time_slots = {
            "09:00": {
                "type": "short", 
                "name": "Утренний пост", 
                "emoji": "🌅",
                "tg_words": "130-160 слов",
                "zen_words": "600-800 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },
            "14:00": {
                "type": "long", 
                "name": "Обеденный пост", 
                "emoji": "🌞",
                "tg_words": "150-180 слов",
                "zen_words": "800-1000 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            },  
            "19:00": {
                "type": "medium", 
                "name": "Вечерний пост", 
                "emoji": "🌙",
                "tg_words": "140-170 слов",
                "zen_words": "700-900 слов",
                "tg_photos": "1 фото",
                "zen_photos": "1 фото"
            }
        }

        # Ключевые слова для поиска изображений
        self.theme_keywords = {
            "HR и управление персоналом": [
                "office team meeting", "business workplace", "corporate culture", 
                "hr management", "teamwork collaboration", "recruitment interview",
                "employee engagement", "workplace diversity", "career growth"
            ],
            "PR и коммуникации": [
                "public relations", "media communication", "social media marketing", 
                "brand strategy", "networking event", "press conference",
                "crisis management", "content creation", "influencer marketing"
            ],
            "ремонт и строительство": [
                "construction site", "building renovation", "interior design", 
                "architecture modern", "home improvement", "construction workers",
                "renovation project", "building materials", "construction machinery"
            ]
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

    def test_gemini_model(self, model_name):
        """Тестирует конкретную модель Gemini"""
        print(f"🧪 Тестируем модель: {model_name}")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        test_data = {
            "contents": [{
                "parts": [{"text": "Ответь одним словом: 'OK'"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10,
            }
        }
        
        try:
            response = requests.post(url, json=test_data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    print(f"✅ Модель {model_name} работает!")
                    return model_name
                else:
                    print(f"⚠️ Модель {model_name}: неверный формат ответа")
                    return None
            else:
                print(f"❌ Модель {model_name}: ошибка {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Модель {model_name}: ошибка подключения - {e}")
            return None

    def find_working_model(self):
        """Ищет рабочую модель Gemini"""
        print("\n🔍 Ищем рабочую модель Gemini...")
        
        for model in GEMINI_MODELS:
            working_model = self.test_gemini_model(model)
            if working_model:
                self.working_model = working_model
                print(f"\n🎯 Выбрана модель: {self.working_model}")
                return True
        
        print("\n❌ Не найдено ни одной рабочей модели!")
        return False

    def get_smart_theme(self, channel_id):
        """Выбирает тему с учетом истории и времени"""
        channel_key = str(channel_id)
        themes_history = self.post_history.get("themes", {}).get(channel_key, [])
        
        current_hour = datetime.now().hour
        available_themes = self.themes.copy()
        
        if 6 <= current_hour < 12:
            preferred_themes = ["HR и управление персоналом", "ремонт и строительство"]
        elif 12 <= current_hour < 18:
            preferred_themes = ["PR и коммуникации", "HR и управление персоналом"]
        else:
            preferred_themes = ["ремонт и строительство", "PR и коммуникации"]
        
        available_themes.sort(key=lambda x: preferred_themes.index(x) if x in preferred_themes else len(preferred_themes))
        
        for theme in themes_history[-2:]:
            if theme in available_themes:
                available_themes.remove(theme)
        
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = available_themes[0]
        
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
        print(f"📝 Объем ТГ: {post_type_info['tg_words']}")
        print(f"📝 Объем Дзен: {post_type_info['zen_words']}")
        
        return post_type_info['type'], closest_slot, post_type_info['emoji'], post_type_info

    def check_last_post_time(self):
        """Проверяет, когда был последний пост"""
        last_post_time = self.post_history.get("last_post_time")
        if last_post_time:
            last_time = datetime.fromisoformat(last_post_time)
            time_since_last = datetime.now() - last_time
            hours_since_last = time_since_last.total_seconds() / 3600
            
            print(f"⏰ Последний пост был: {last_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"📅 Прошло часов: {hours_since_last:.1f}")
            
            if hours_since_last < 4:
                print("⏸️  Пост был недавно, пропускаем отправку")
                return False
        
        return True

    def update_last_post_time(self):
        """Обновляет время последнего поста"""
        self.post_history["last_post_time"] = datetime.now().isoformat()
        self.save_post_history()

    def format_telegram_text(self, text):
        """Форматирует текст для Telegram с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Если строка начинается с маркера списка (включая разные варианты)
            if line.startswith('•') or line.startswith('-') or line.startswith('⁃') or line.startswith('▪'):
                # Удаляем лишние пробелы и добавляем правильный отступ
                clean_line = line.lstrip('•-⁃▪ ')
                formatted_line = f" • {clean_line}"
                formatted_lines.append(formatted_line)
            elif '•' in line and line.find('•') < 10:
                # Если маркер где-то в начале строки
                parts = line.split('•', 1)
                if len(parts) > 1:
                    formatted_line = f" • {parts[1].strip()}"
                    formatted_lines.append(formatted_line)
                else:
                    formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def create_telegram_prompt(self, theme, time_slot_info):
        """Создает промпт для Telegram"""
        time_emoji = time_slot_info['emoji']
        tg_words = time_slot_info['tg_words']
        tg_photos = time_slot_info['tg_photos']
        
        prompt = f"""Создай пост для Telegram на тему "{theme}" для 2024-2025 года.

СТРУКТУРА ПОСТА ДЛЯ TELEGRAM:

Объем: {tg_words} (500–900 символов)
Эмодзи: да, обязательно
Фото: {tg_photos} (ИИ выбирает по теме анализа поста: люди, рабочие процессы, стройка, офис, динамика, эмоции)

ИСПОЛЬЗУЙ ТОЧНО ЭТУ СТРУКТУРУ:

{time_emoji} [ХУК: 1-2 строки]
Цепляем вниманием, эмоцией, болью или неожиданным фактом. Используй эмодзи.

📌 [Короткое объяснение сути: 2-3 строки]
Что произошло / почему важно / какой инсайт. Можно упомянуть конкретные компании (Google, Microsoft, Яндекс, Сбер) или исследования (McKinsey, Gartner, HBR).

🎯 [Основной блок: 5-7 строк]
 • ключевая мысль
 • тренд или кейс (используй названия компаний: Apple, Tesla, Amazon, Ozon, Wildberries)
 • что делать, что применять на практике

💡 [Вывод + CTA: 1-2 строки]
Вопрос для обсуждения, вовлечение аудитории, призыв к действию.

🏷️ [Хештеги]
3-5 релевантных хештегов на русском

ТРЕБОВАНИЯ:
1. Используй только русский язык, кроме названий компаний и исследований
2. Все списки начинай с отступа " " + «•»
3. Используй эмодзи в каждом разделе
4. Конкретные цифры и данные 2024-2025
5. Объем: {tg_words}
6. Живой, вовлекающий язык
7. Не используй HTML-теги (<b>, <i> и т.д.)
8. Каждый раздел с новой строки
9. Между разделами оставляй пустую строку
10. ОБЯЗАТЕЛЬНО 1 фото к посту

Пример правильного формата:
🌅 67% сотрудников хотят сменять работу. Почему?

📌 По данным Gartner, кадровая текучка обходится компаниям в 1.5 годовых оклада. Это не просто цифры — это реальные потери бизнеса.

🎯 
 • Ключевая проблема: отсутствие карьерных перспектив
 • Решение: внедрение системы персонального развития в Microsoft
 • Практика: ежеквартальные 1-on-1 встречи с руководителем

💡 Что мешает внедрить такую систему в вашей компании?

🏷️ #HR #карьера #развитие #управление #бизнес"""

        return prompt

    def create_zen_prompt(self, theme, time_slot_info):
        """Создает промпт для Яндекс.Дзена"""
        zen_words = time_slot_info['zen_words']
        zen_photos = time_slot_info['zen_photos']
        
        prompt = f"""Напиши развернутый аналитический пост для Яндекс.Дзен на тему "{theme}" в 2024-2025 году.

СТРУКТУРА ПОСТА ДЛЯ ЯНДЕКС.ДЗЕН:

Объем: {zen_words} (4000–7000 символов)
Эмодзи: НЕТ
Фото: {zen_photos} (по смыслу поста: инфографика, люди, предметы, процессы)

СТРУКТУРА:
1. Хук (1 абзац)
Факт, инсайт, парадокс, боль, важная ситуация. Начинай с сильного утверждения.

2. Введение (1 абзац)
Что разберём, почему это важно сейчас. Обозначь рамки и цели статьи.

3. Основная часть (3-5 блоков)
Каждый блок начинается с подзаголовка.
Текст объясняет тему глубже, чем в ТГ:
 • примеры из практики
 • реальные кейсы (можно упоминать Google, Amazon, Яндекс, Сбер, Ozon)
 • исследования и статистика (McKinsey, Deloitte, PwC)
 • текущие тренды

4. Практическая польза (1 блок)
Что применить прямо сейчас. Конкретные шаги, чек-листы, рекомендации.

5. Вывод (1 абзац)
Чёткое резюме + завершение мысли. Подведи итог, но оставь пространство для размышлений.

ТРЕБОВАНИЯ:
- Объем: {zen_words}
- Русский язык, профессиональный но доступный
- Без эмодзи и хештегов
- Конкретные данные, статистика, исследования
- Можно использовать английские названия компаний и исследований
- Глубокий анализ с практической ценностью
- Абзацы не длиннее 5-7 строк
- Между абзацами оставляй пустую строку
- Списки с отступами " " + «•»
- ОБЯЗАТЕЛЬНО 1 фото к посту

Создай экспертное содержание, которое будет полезно профессионалам."""

        return prompt

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерирует текст с повторными попытками"""
        if not self.working_model:
            print("❌ Не выбрана рабочая модель Gemini")
            return None
            
        for attempt in range(max_attempts):
            try:
                print(f"🔄 Попытка {attempt + 1}/{max_attempts} (модель: {self.working_model})...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.working_model}:generateContent?key={GEMINI_API_KEY}"
                
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.8,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 4096,
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

    def generate_tg_post(self, theme, time_slot_info):
        """Генерирует пост для Telegram"""
        prompt = self.create_telegram_prompt(theme, time_slot_info)
        raw_text = self.generate_with_gemini(prompt)
        if raw_text:
            return self.format_telegram_text(raw_text)
        return None

    def generate_zen_post(self, theme, time_slot_info):
        """Генерирует пост для Дзена"""
        prompt = self.create_zen_prompt(theme, time_slot_info)
        raw_text = self.generate_with_gemini(prompt)
        if raw_text:
            return self.format_telegram_text(raw_text)
        return None

    def get_image_url(self, theme):
        """Получает изображение для темы"""
        print(f"🖼️ Получаем изображение для: {theme}")
        
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            encoded_keyword = quote_plus(keyword)
            
            colors = ["4A90E2", "2E8B57", "FF6B35", "6A5ACD", "20B2AA", "FFD700", "8B4513", "2F4F4F"]
            color = random.choice(colors)
            
            # 1 фото для каждого поста
            image_url = f"https://via.placeholder.com/1200x630/{color}/FFFFFF?text={encoded_keyword}"
            print(f"📸 Изображение: {image_url}")
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка получения изображения: {e}")
            return "https://via.placeholder.com/1200x630/4A90E2/FFFFFF?text=Business+Post"

    def download_image(self, url):
        """Скачивает изображение для отправки"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"❌ Ошибка скачивания изображения: {e}")
        return None

    def send_to_telegram(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram"""
        print(f"📤 Отправка в {chat_id}...")
        
        if not BOT_TOKEN:
            print("❌ Отсутствует BOT_TOKEN")
            return False
        
        # Обрезаем текст если слишком длинный
        max_length = 1024 if image_url else 4096
        
        if len(text) > max_length:
            print(f"⚠️ Текст длинный ({len(text)}), обрезаем до {max_length}...")
            cutoff = text[:max_length-50].rfind('.')
            if cutoff > max_length * 0.7:
                text = text[:cutoff+1]
            else:
                text = text[:max_length-3] + "..."
        
        try:
            # ВСЕГДА отправляем с фото (1 фото на пост)
            if image_url:
                print(f"📸 Отправляем с изображением...")
                
                # Пробуем скачать изображение
                image_data = self.download_image(image_url)
                
                if image_data:
                    # Отправляем фото с подписью (скачанное изображение)
                    files = {'photo': ('image.jpg', image_data)}
                    data = {
                        'chat_id': chat_id,
                        'caption': text,
                        'parse_mode': None
                    }
                    
                    response = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data=data,
                        files=files,
                        timeout=30
                    )
                else:
                    # Если не удалось скачать, отправляем по URL
                    response = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        json={
                            'chat_id': chat_id,
                            'photo': image_url,
                            'caption': text,
                            'parse_mode': None
                        },
                        timeout=30
                    )
            else:
                # Если почему-то нет фото, создаем дефолтное
                print("⚠️ Нет изображения, создаем дефолтное...")
                default_image = "https://via.placeholder.com/1200x630/4A90E2/FFFFFF?text=Business+Post"
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={
                        'chat_id': chat_id,
                        'photo': default_image,
                        'caption': text,
                        'parse_mode': None
                    },
                    timeout=30
                )
            
            if response.status_code == 200:
                print(f"✅ Пост с фото отправлен в {chat_id}")
                return True
            else:
                print(f"❌ Ошибка отправки ({response.status_code}): {response.text[:100]}")
                # Пробуем отправить только текст
                print("🔄 Пробуем отправить без изображения...")
                try:
                    response = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            'chat_id': chat_id,
                            'text': text,
                            'parse_mode': None
                        },
                        timeout=30
                    )
                    if response.status_code == 200:
                        print(f"✅ Текстовый пост отправлен в {chat_id}")
                        return True
                except:
                    pass
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def send_dual_posts(self):
        """Основной метод отправки постов"""
        if not self.check_last_post_time():
            print("⏸️  Пропускаем отправку - недавно уже был пост")
            return True
            
        if not self.find_working_model():
            print("❌ Не удалось найти рабочую модель Gemini")
            return False
            
        try:
            self.current_theme = self.get_smart_theme(MAIN_CHANNEL_ID)
            tg_type, time_slot, time_emoji, time_slot_info = self.get_tg_type_by_time()
            
            print(f"🎯 Тема: {self.current_theme}")
            print(f"📊 Тип поста: {tg_type.upper()}")
            
            print("🧠 Генерация постов через AI...")
            
            # Генерируем посты
            print("📝 Генерация Telegram поста...")
            tg_post = self.generate_tg_post(self.current_theme, time_slot_info)
            if not tg_post:
                print("❌ Не удалось сгенерировать пост для Telegram")
                return False
            
            print("📝 Генерация Дзен поста...")
            zen_post = self.generate_zen_post(self.current_theme, time_slot_info)
            if not zen_post:
                print("❌ Не удалось сгенерировать пост для Дзена")
                return False
            
            print(f"📊 Статистика постов:")
            print(f"   📝 ТГ-пост: {len(tg_post)} символов")
            print(f"   📝 Дзен-пост: {len(zen_post)} символов")
            
            print("\n📤 Отправка постов...")
            
            # Получаем ОТДЕЛЬНЫЕ изображения для каждого поста
            print("🖼️ Получаем изображения...")
            tg_image_url = self.get_image_url(self.current_theme)
            time.sleep(1)  # Пауза между запросами
            zen_image_url = self.get_image_url(self.current_theme)
            
            # Отправляем Telegram пост с фото
            tg_success = self.send_to_telegram(MAIN_CHANNEL_ID, tg_post, tg_image_url)
            time.sleep(2)
            
            # Отправляем Дзен пост с фото
            zen_success = self.send_to_telegram(ZEN_CHANNEL_ID, zen_post, zen_image_url)
            
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
    print("🎯 Автоматический подбор рабочей модели Gemini")
    print("🎯 Умный подбор тем по времени суток")
    print("🎯 Контроль частоты постов")
    print("🎯 1 фото в каждом посте")
    print("=" * 80)
    
    if not BOT_TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден!")
        return
    
    if not GEMINI_API_KEY:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: GEMINI_API_KEY не найден!")
        return
    
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
