import os
import random
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_post():
    styles = [
        "совет",
        "неочевидный факт",
        "вопрос для размышления", 
        "практический лайфхак",
        "цитата с комментарием",
        "миф и правда"
    ]
    themes = ["HR", "PR", "HR и PR", "работодатель", "бренд", "команда", "карьера", "репутация"]
    
    style = random.choice(styles)
    theme = random.choice(themes)
    
    prompt = f"""
    Напишите короткий пост (не более 250 символов) для Telegram на тему {theme} в стиле "{style}".
    Пост должен быть активным, лаконичным и без клише.
    Не используйте эмодзи раньше. Не пиши "Пост:", "Тема:" — только сам текст.
    """
    
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 200,
                    "temperature": 0.8
                }
            }
        )
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        
        emojis = ["💡", "📣", "🧠", "🎯", "📊", "✨", "🚀", "🤝", "🌱", "💬"]
        emoji = random.choice(emojis)
        return f"{emoji} {text}"
        
    except Exception as e:
        print(f"Ошибка генерации: {e}")
        return random.choice([
            "💡 HR: Доверие строится быстрее, чем разрушение. Но разрушение происходит мгновенно.",
            "📣 PR: Не объясняйте, почему вы хороши. Покажите, как клиент станет лучше.",
            "🧠 Факт: 73% соискателей исследуют репутацию компании перед откликом. Ваш HR-бренд — ваш найм."
        ])

def send_post():
    try:
        message = generate_post()
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHANNEL_ID, "text": message}
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("✅ Пост отправлен успешно!")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

if __name__ == "__main__":
    send_post()
