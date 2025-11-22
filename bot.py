import os
import logging
import random
import requests
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TZ = os.getenv("TIMEZONE", "UTC")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

def generate_post():
    styles = [
        "профессиональный совет",
        "неочевидный факт",
        "вопрос для размышления",
        "практический лайфхак",
        "цитата с комментарием",
        "миф и правда"
    ]
    topics = ["HR", "PR", "HR и PR", "работодатель", "бренд", "команда", "карьера", "репутация"]
    
    style = random.choice(styles)
    topic = random.choice(topics)
    
    prompt = f"""
    Напиши короткий пост (не более 250 символов) для Telegram на тему {topic} в стиле "{style}".
    Пост должен быть полезным, лаконичным и без клише.
    Не используй эмодзи в начале. Не пиши "Пост:", "Тема:" — только сам текст.
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
        text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        
        emojis = ["💡", "📣", "🧠", "🎯", "📊", "✨", "🚀", "🤝", "🌱", "💬"]
        emoji = random.choice(emojis)
        return f"{emoji} {text}"
        
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return random.choice([
            "💡 HR: Доверие строится быстрее, чем разрушается. Но разрушается — мгновенно.",
            "📣 PR: Не объясняйте, почему вы хороши. Покажите, как клиенту станет лучше.",
            "🧠 Факт: 73% соискателей исследуют репутацию компании перед откликом. Ваш HR-бренд — ваш найм."
        ])

def send_post():
    try:
        message = generate_post()
        
        images = [
            "https://source.unsplash.com/1200x630/?hr",
            "https://source.unsplash.com/1200x630/?pr",
            "https://source.unsplash.com/1200x630/?team",
            "https://source.unsplash.com/1200x630/?business",
            "https://source.unsplash.com/1200x630/?leadership",
            "https://source.unsplash.com/1200x630/?office"
        ]
        image_url = random.choice(images)
        
        bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=message)
        logger.info(f"✅ Отправлен пост с фото: {message[:40]}...")
        
    except TelegramError as e:
        logger.error(f"❌ Ошибка Telegram: {e}")
        bot.send_message(chat_id=CHANNEL_ID, text=message)

# Планировщик: 3 раза в день
scheduler = BlockingScheduler(timezone=timezone(TZ))
scheduler.add_job(send_post, CronTrigger(hour=9, minute=0, timezone=timezone(TZ)))
scheduler.add_job(send_post, CronTrigger(hour=14, minute=0, timezone=timezone(TZ)))
scheduler.add_job(send_post, CronTrigger(hour=19, minute=0, timezone=timezone(TZ)))

if __name__ == "__main__":
    logger.info("🚀 Умный бот запущен. Ждём расписания...")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен.")
