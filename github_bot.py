import os
import requests
import datetime
import hashlib
import json
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
                return json.load(f)
    except Exception:
        pass
    return {"post_hashes": [], "last_reset_date": datetime.datetime.now().strftime('%Y-%m-%d')}

def save_post_history(history):
    """Сохраняет историю постов"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def is_post_unique(content, history):
    """Проверяет, уникален ли пост"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    return content_hash not in history["post_hashes"]

def mark_post_as_used(content, history):
    """Помечает пост как использованный"""
    content_hash = hashlib.md5(content.encode()).hexdigest()
    history["post_hashes"].append(content_hash)
    save_post_history(history)

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

def get_unique_image():
    """Получает абсолютно уникальную картинку"""
    timestamp = datetime.datetime.now().timestamp()
    unique_hash = int(hashlib.md5(str(timestamp).encode()).hexdigest()[:12], 16)
    image_url = f"https://picsum.photos/1200/800?random={unique_hash}"
    print(f"🖼️ Уникальная картинка: {image_url}")
    return image_url

def generate_viral_post(time_of_day, attempt=1):
    """Генерирует виральный пост без повторений"""
    
    history = load_post_history()
    
    # Очищаем историю если новый день
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    if history.get("last_reset_date") != current_date:
        history["post_hashes"] = []
        history["last_reset_date"] = current_date
        save_post_history(history)
    
    length_config = {
        "morning": {"max_tokens": 600, "ideal_length": 400},
        "afternoon": {"max_tokens": 1200, "ideal_length": 800}, 
        "evening": {"max_tokens": 500, "ideal_length": 300}
    }
    
    config = length_config[time_of_day]
    
    # СЛУЧАЙНЫЕ ТЕМАТИКИ БЕЗ ФИКСИРОВАННЫХ СПИСКОВ
    themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
    random_theme = random.choice(themes)
    
    # СЛУЧАЙНЫЕ ФОРМАТЫ ДЛЯ ВИРАЛЬНОСТИ
    formats = [
        "🔥 {content}",
        "🎯 {content}", 
        "💡 {content}",
        "🚀 {content}",
        "🤯 {content}",
        "💎 {content}"
    ]
    
    # СЛУЧАЙНЫЕ ПРИЗЫВЫ К ДЕЙСТВИЮ
    calls_to_action = [
        "🔥 Поделись с другом, если полезно!",
        "💬 Что думаешь? Напиши в комментах!",
        "🔄 Репостни, если согласен!",
        "👥 Покажи коллегам – обсудим вместе!",
        "💎 Сохрани себе на стену!",
        "🚀 Поделись мнением в комментариях!"
    ]
    
    prompt = f"""
    СОЗДАЙ АБСОЛЮТНО УНИКАЛЬНЫЙ ВИРАЛЬНЫЙ ПОСТ ДЛЯ TELEGRAM
    
    ТЕМАТИКА: {random_theme}
    ВРЕМЯ: {time_of_day}
    
    КРИТИЧЕСКИ ВАЖНО:
    - Пост ДОЛЖЕН БЫТЬ НА 100% УНИКАЛЬНЫМ
    - Никаких повторений с предыдущими постами
    - Только свежие идеи и актуальные тренды 2024-2025
    - Контент должен вызывать желание делиться
    
    ФОРМАТЫ ДЛЯ ВИРАЛЬНОСТИ (выбери один):
    • Провокационный вопрос
    • Шокирующая статистика  
    • Полезный лайфхак
    • Интерактивный опрос
    • Забавный случай из практики
    • Неочевидный факт
    • Практическая инструкция
    • Кейс успеха/провала
    
    СТРУКТУРА:
    1. ЦЕПЛЯЮЩИЙ ЗАГОЛОВОК (с эмодзи)
    2. ИНТЕРЕСНЫЙ КОНТЕНТ (с цифрами, фактами, примерами)
    3. ПРИЗЫВ К ДЕЙСТВИЮ (один из вариантов ниже)
    
    ТРЕБОВАНИЯ:
    - Длина: {config['ideal_length']}-{config['max_tokens']} символов
    - Максимальная уникальность
    - Только актуальная информация
    - Конкретные цифры и примеры
    - Естественный разговорный стиль
    - Много эмодзи для эмоций
    
    ПРИЗЫВ К ДЕЙСТВИЮ (добавь в конце):
    {random.choice(calls_to_action)}
    
    НЕ ИСПОЛЬЗУЙ:
    - Удаленную работу/гибридный формат
    - Шаблонные фразы
    - То, что уже было в предыдущих постах
    
    СДЕЛАЙ ТАК, ЧТОБЫ:
    - Хотелось немедленно поделиться
    - Возникло желание обсудить в комментах
    - Запомнилось надолго
    - Вызывало эмоции
    """
    
    try:
        print(f"🧠 Генерация вирального поста ({random_theme})... Попытка: {attempt}")
        
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": config["max_tokens"],
                    "temperature": 0.98,  # МАКСИМАЛЬНАЯ КРЕАТИВНОСТЬ
                    "topP": 0.95,
                    "topK": 50
                }
            },
            timeout=45
        )
        
        if response.status_code == 200:
            data = response.json()
            post_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Проверяем уникальность
            if is_post_unique(post_text, history):
                # Применяем случайный формат
                formatted_text = random.choice(formats).format(content=post_text)
                mark_post_as_used(post_text, history)
                return formatted_text, get_unique_image(), random_theme
            else:
                print("🔄 Пост не уникален, пробуем снова...")
                if attempt < 5:  # Максимум 5 попыток
                    return generate_viral_post(time_of_day, attempt + 1)
                else:
                    raise Exception("Не удалось сгенерировать уникальный пост")
            
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
    
    # Критический запасной вариант
    return get_emergency_fallback(time_of_day)

def get_emergency_fallback(time_of_day):
    """Аварийный пост когда все остальное fails"""
    fallbacks = [
        f"""🔥 <b>СЕКРЕТ РОСТА: Что объединяет все успешные компании 2025?</b>

Новое исследование: 92% лидеров рынка делают акцент на развитии soft skills!

💡 <b>Неочевидный факт:</b> Инвестиции в обучение сотрудников окупаются в 3 раза быстрее, чем в технологии.

🚀 <b>Действие:</b> Проведите на этой неделе мини-тренинг по коммуникациям.

💬 <b>Что думаешь? Напиши в комментах!</b>

#{random.choice(["HR", "Бизнес", "Развитие"])}""",

        f"""🎯 <b>КОММУНИКАЦИОННЫЙ ВЗРЫВ: Как говорить так, чтобы слушали?</b>

По данным neuroscience: первые 7 секунд разговора определяют 80% восприятия!

🧠 <b>Лайфхак:</b> Используйте "правило 3-х секунд" - пауза перед ответом увеличивает доверие на 40%.

💎 <b>Практика:</b> Завтра попробуйте в одном разговоре сделать осознанную паузу.

👥 <b>Поделись с другом, если полезно!</b>

#{random.choice(["Коммуникации", "Психология", "Переговоры"])}""",

        f"""💡 <b>РЕМОНТНАЯ РЕВОЛЮЦИЯ: Технологии, которые меняют всё</b>

2025 год: "умные" материалы сокращают сроки ремонта на 60%!

🏗️ <b>Тренд:</b> Биодизайн в отделке - природные материалы становятся на 30% популярнее.

🌟 <b>Совет:</b> При планировании ремонта закладывайте +15% бюджета на технологичные решения.

🔄 <b>Репостни, если согласен!</b>

#{random.choice(["Ремонт", "Дизайн", "Технологии"])}"""
    ]
    
    fallback = random.choice(fallbacks)
    return fallback, get_unique_image(), "Экстренная тема"

def main():
    """Основная функция"""
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
    
    success = send_post_with_image(post_text, image_url)
    if success:
        print(f"✅ УНИКАЛЬНЫЙ пост отправлен!")
    else:
        print(f"❌ Ошибка отправки")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
