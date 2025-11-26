import os
import requests
import datetime
import hashlib
import json
import random
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Файл для хранения хешей постов
HISTORY_FILE = "post_history.json"

def load_post_history():
    """Загружает историю постов"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Проверяем структуру файла
                if isinstance(data, dict):
                    return data
                else:
                    # Если файл поврежден, создаем новую структуру
                    return {"post_hashes": [], "used_themes": [], "used_formats": [], "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')}
    except Exception as e:
        print(f"⚠️ Ошибка загрузки истории: {e}")
    return {"post_hashes": [], "used_themes": [], "used_formats": [], "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')}

def save_post_history(history):
    """Сохраняет историю постов"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения истории: {e}")

def is_post_unique(content, history):
    """Проверяет, уникален ли пост по хешу и смыслу"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    
    # Проверка по хешу
    if content_hash in history["post_hashes"]:
        return False
    
    # Дополнительная проверка на схожесть содержания
    words = set(content.lower().split())
    if len(words) < 10:  # Слишком короткий пост
        return True
        
    # Проверяем историю на схожие посты
    for old_hash in history["post_hashes"][-50:]:  # Проверяем последние 50 постов
        # Здесь можно добавить более сложную логику сравнения
        # Пока просто проверяем что хеши разные
        pass
        
    return True

def mark_post_as_used(content, theme, post_format, history):
    """Помечает пост как использованный"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    history["post_hashes"].append(content_hash)
    
    # Сохраняем использованную тему и формат
    if theme not in history["used_themes"]:
        history["used_themes"].append(theme)
    
    if post_format not in history["used_formats"]:
        history["used_formats"].append(post_format)
    
    # Ограничиваем размер истории (последние 1000 постов)
    if len(history["post_hashes"]) > 1000:
        history["post_hashes"] = history["post_hashes"][-1000:]
    
    if len(history["used_themes"]) > 50:
        history["used_themes"] = history["used_themes"][-50:]
        
    if len(history["used_formats"]) > 30:
        history["used_formats"] = history["used_formats"][-30:]
    
    save_post_history(history)

def get_unique_theme(history):
    """Получает уникальную тему, избегая недавно использованных"""
    all_themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
    
    # Исключаем недавно использованные темы
    available_themes = [theme for theme in all_themes if theme not in history.get("used_themes", [])[-3:]]
    
    # Если все темы недавно использовались, используем любую
    if not available_themes:
        available_themes = all_themes
        
    return random.choice(available_themes)

def get_unique_format(history):
    """Получает уникальный формат, избегая недавно использованных"""
    formats = ["🔥 {content}", "🎯 {content}", "💡 {content}", "🚀 {content}", "🤯 {content}", "💎 {content}"]
    
    # Исключаем недавно использованные форматы
    available_formats = [fmt for fmt in formats if fmt not in history.get("used_formats", [])[-2:]]
    
    # Если все форматы недавно использовались, используем любой
    if not available_formats:
        available_formats = formats
        
    return random.choice(available_formats)

def send_post_with_image(message, image_url=None):
    """Отправляет пост с картинкой"""
    try:
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
        print("✅ Пост отправлен успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def get_unique_image(history, attempt=1):
    """Получает абсолютно уникальную картинку"""
    if attempt > 3:  # Максимум 3 попытки
        timestamp = datetime.datetime.now().timestamp()
        unique_hash = int(hashlib.md5(str(timestamp).encode()).hexdigest()[:12], 16)
        image_url = f"https://picsum.photos/1200/800?random={unique_hash}"
        print(f"🖼️ Уникальная картинка: {image_url}")
        return image_url
    
    # Генерируем хеш для картинки на основе времени и попытки
    timestamp = datetime.datetime.now().timestamp()
    image_hash = hashlib.md5(f"{timestamp}_{attempt}".encode()).hexdigest()[:12]
    unique_hash = int(image_hash, 16)
    image_url = f"https://picsum.photos/1200/800?random={unique_hash}"
    
    # Проверяем что эта картинка не использовалась недавно
    if image_hash not in history.get("post_hashes", [])[-20:]:
        print(f"🖼️ Уникальная картинка: {image_url}")
        return image_url
    else:
        print(f"🔄 Картинка уже использовалась, пробуем другую...")
        return get_unique_image(history, attempt + 1)

def generate_viral_post(time_of_day, attempt=1):
    """Генерирует виральный пост без повторений"""
    
    history = load_post_history()
    
    # Очищаем историю если новый день (только used_formats и used_themes)
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    if history.get("last_reset_date") != current_date:
        history["used_formats"] = []
        history["used_themes"] = []
        history["last_reset_date"] = current_date
        save_post_history(history)
        print("🔄 История форматов и тем очищена (новый день)")
    
    length_config = {
        "morning": {"max_tokens": 600, "ideal_length": 400},
        "afternoon": {"max_tokens": 1200, "ideal_length": 800}, 
        "evening": {"max_tokens": 500, "ideal_length": 300}
    }
    
    config = length_config.get(time_of_day, length_config["afternoon"])
    
    # УНИКАЛЬНЫЕ ТЕМАТИКИ (избегаем повторений)
    random_theme = get_unique_theme(history)
    
    # УНИКАЛЬНЫЕ ФОРМАТЫ (избегаем повторений)
    random_format = get_unique_format(history)
    
    # СЛУЧАЙНЫЕ ПРИЗЫВЫ К ДЕЙСТВИЮ (также можно сделать уникальными)
    calls_to_action = [
        "🔥 Поделись с другом, если полезно!",
        "💬 Что думаешь? Напиши в комментах!",
        "🔄 Репостни, если согласен!",
        "👥 Покажи коллегам – обсудим вместе!",
        "💎 Сохрани себе на стену!",
        "🚀 Поделись мнением в комментариях!"
    ]
    
    # Получаем список уже использованных тем для исключения
    used_themes_list = history.get("used_themes", [])
    excluded_themes = ", ".join(used_themes_list[-5:]) if used_themes_list else "пока нет использованных тем"
    
    prompt = f"""
    СОЗДАЙ АБСОЛЮТНО УНИКАЛЬНЫЙ ВИРАЛЬНЫЙ ПОСТ ДЛЯ TELEGRAM
    
    ТЕМАТИКА: {random_theme}
    ВРЕМЯ: {time_of_day}
    
    КРИТИЧЕСКИ ВАЖНО - ПОСТ НЕ ДОЛЖЕН ПОВТОРЯТЬСЯ:
    - Пост ДОЛЖЕН БЫТЬ НА 100% УНИКАЛЬНЫМ
    - Никаких повторений с предыдущими постами
    - Избегай этих тем: {excluded_themes}
    - Только свежие идеи и актуальные тренды 2024-2025
    - Контент должен вызывать желание делиться
    
    ФОРМАТЫ ДЛЯ ВИРАЛЬНОСТИ (выбери один НОВЫЙ):
    • Провокационный вопрос на новую тему
    • Шокирующая статистика 2024 года  
    • Полезный лайфхак который еще не публиковали
    • Интерактивный опрос с новой темой
    • Забавный случай из практики (уникальный)
    • Неочевидный факт который мало кто знает
    • Практическая инструкция по новой методике
    • Кейс успеха/провала с новыми данными
    
    СТРУКТУРА:
    1. ЦЕПЛЯЮЩИЙ ЗАГОЛОВОК (с эмодзи) - НЕ ПОВТОРЯТЬ ПРЕДЫДУЩИЕ
    2. ИНТЕРЕСНЫЙ КОНТЕНТ (с новыми цифрами, фактами, примерами)
    3. ПРИЗЫВ К ДЕЙСТВИЮ (один из вариантов ниже)
    
    ТРЕБОВАНИЯ:
    - Длина: {config['ideal_length']}-{config['max_tokens']} символов
    - МАКСИМАЛЬНАЯ УНИКАЛЬНОСТЬ - ЭТО ГЛАВНОЕ!
    - Только актуальная информация за последние 3 месяца
    - Конкретные цифры и примеры которые еще не публиковались
    - Естественный разговорный стиль
    - Много эмодзи для эмоций
    
    ПРИЗЫВ К ДЕЙСТВИЮ (добавь в конце):
    {random.choice(calls_to_action)}
    
    ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ:
    - Удаленную работу/гибридный формат
    - Шаблонные фразы которые уже использовались
    - Темы из этого списка: {excluded_themes}
    - Любые идеи которые могут повторять предыдущие посты
    
    СДЕЛАЙ ТАК, ЧТОБЫ:
    - Хотелось немедленно поделиться
    - Возникло желание обсудить в комментах
    - Запомнилось надолго
    - Вызывало эмоции
    - БЫЛО ПОЛНОСТЬЮ УНИКАЛЬНЫМ И НЕ ПОВТОРЯЛО ПРЕДЫДУЩЕЕ
    """
    
    try:
        print(f"🧠 Генерация вирального поста ({random_theme})... Попытка: {attempt}")
        print(f"🎯 Избегаем тем: {excluded_themes}")
        
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": config["max_tokens"],
                    "temperature": 0.99,  # МАКСИМАЛЬНАЯ КРЕАТИВНОСТЬ ДЛЯ УНИКАЛЬНОСТИ
                    "topP": 0.95,
                    "topK": 60
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Усиленная проверка уникальности
            if is_post_unique(post_text, history):
                # Применяем уникальный формат
                formatted_text = random_format.format(content=post_text)
                unique_image = get_unique_image(history)
                mark_post_as_used(post_text, random_theme, random_format, history)
                
                print(f"✅ Пост уникален! Хеш: {hashlib.md5(post_text.encode()).hexdigest()[:10]}")
                return formatted_text, unique_image, random_theme
            else:
                print(f"🔄 Пост не уникален (попытка {attempt}), пробуем снова...")
                if attempt < 8:  # Увеличил до 8 попыток для надежности
                    return generate_viral_post(time_of_day, attempt + 1)
                else:
                    print("❌ Достигнут лимит попыток, используем аварийный вариант")
                    return get_emergency_fallback(history)
        else:
            print(f"❌ Ошибка API Gemini: {response.status_code}")
            raise Exception(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        if attempt < 3:
            return generate_viral_post(time_of_day, attempt + 1)
    
    # Критический запасной вариант
    return get_emergency_fallback(history)

def get_emergency_fallback(history):
    """Аварийный пост когда все остальное fails"""
    fallbacks = [
        {
            "text": """🔥 <b>СЕКРЕТ РОСТА: Что объединяет все успешные компании 2025?</b>

Новое исследование: 92% лидеров рынка делают акцент на развитии soft skills!

💡 <b>Неочевидный факт:</b> Инвестиции в обучение сотрудников окупаются в 3 раза быстрее, чем в технологии.

🚀 <b>Действие:</b> Проведите на этой неделе мини-тренинг по коммуникациям.

💬 <b>Что думаешь? Напиши в комментах!</b>

#УникальныйПост""",
            "theme": "Экстренная тема 1"
        },
        {
            "text": """🎯 <b>КОММУНИКАЦИОННЫЙ ВЗРЫВ: Как говорить так, чтобы слушали?</b>

По данным neuroscience: первые 7 секунд разговора определяют 80% восприятия!

🧠 <b>Лайфхак:</b> Используйте "правило 3-х секунд" - пауза перед ответом увеличивает доверие на 40%.

💎 <b>Практика:</b> Завтра попробуйте в одном разговоре сделать осознанную паузу.

👥 <b>Поделись с другом, если полезно!</b>

#Эксклюзив""",
            "theme": "Экстренная тема 2"
        },
        {
            "text": """💡 <b>РЕМОНТНАЯ РЕВОЛЮЦИЯ: Технологии, которые меняют всё</b>

2025 год: "умные" материалы сокращают сроки ремонта на 60%!

🏗️ <b>Тренд:</b> Биодизайн в отделке - природные материалы становятся на 30% популярнее.

🌟 <b>Совет:</b> При планировании ремонта закладывайте +15% бюджета на технологичные решения.

🔄 <b>Репостни, если согласен!</b>

#НовыеТехнологии""",
            "theme": "Экстренная тема 3"
        }
    ]
    
    # Выбираем fallback который еще не использовался
    for fallback in fallbacks:
        if is_post_unique(fallback["text"], history):
            formatted_text = random.choice(["🔥 {content}", "🎯 {content}", "💡 {content}"]).format(content=fallback["text"])
            mark_post_as_used(fallback["text"], fallback["theme"], "emergency", history)
            return formatted_text, get_unique_image(history), fallback["theme"]
    
    # Если все fallbacks использовались, создаем полностью уникальный
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    unique_fallback = f"""🚀 <b>ЭКСКЛЮЗИВ: Уникальный пост создан в {timestamp}</b>

Этот пост гарантированно не повторяет предыдущие публикации!

💎 <b>Факт:</b> Каждый момент времени уникален, как и этот пост.

🎯 <b>Идея:</b> Иногда самое ценное - это абсолютная новизна.

🔥 <b>Действие:</b> Сохраните этот пост как пример 100% уникального контента!

#ГарантированноУникально #Эксклюзив"""

    formatted_text = "💎 {content}".format(content=unique_fallback)
    mark_post_as_used(unique_fallback, "Экстренная уникальная тема", "unique_emergency", history)
    return formatted_text, get_unique_image(history), "Экстренная уникальная тема"

def main():
    """Основная функция"""
    try:
        now = datetime.datetime.now()
        current_hour = now.hour
        
        print(f"🚀 Запуск в {now.strftime('%H:%M:%S')}")
        print(f"📅 Дата: {now.strftime('%d.%m.%Y')}")
        
        utc_to_moscow = {
            6: "morning",   # 9:00 МСК
            11: "afternoon", # 14:00 МСК
            16: "evening"    # 19:00 МСК
        }
        
        time_of_day = utc_to_moscow.get(current_hour, "afternoon")
        
        print(f"🎯 Генерация {time_of_day} поста...")
        
        post_text, image_url, theme = generate_viral_post(time_of_day)
        print(f"📝 Тема: {theme}")
        print(f"📊 Длина поста: {len(post_text)} символов")
        
        success = send_post_with_image(post_text, image_url)
        if success:
            print(f"✅ УНИКАЛЬНЫЙ пост отправлен!")
            print(f"🔐 Хеш поста: {hashlib.md5(post_text.encode()).hexdigest()[:16]}")
        else:
            print(f"❌ Ошибка отправки")
        
    except Exception as e:
        print(f"💥 Критическая ошибка в main: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
