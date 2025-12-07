# approval_bot.py - добавляем в этот файл
import os
import json
import hashlib
import time
from datetime import datetime
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

session = requests.Session()

def send_for_approval(tg_text, zen_text, tg_image, zen_image, theme, time_slot):
    """Основная функция отправки на согласование"""
    if not ADMIN_CHAT_ID:
        print("⚠️ ADMIN_CHAT_ID не установлен, публикую сразу")
        return False
    
    try:
        # Генерируем ID
        approval_id = hashlib.md5(f"{theme}{time.time()}".encode()).hexdigest()[:10]
        
        # Сохраняем данные
        data = {
            "approval_id": approval_id,
            "theme": theme,
            "time_slot": time_slot,
            "telegram_post": tg_text,
            "zen_post": zen_text,
            "telegram_image": tg_image,
            "zen_image": zen_image
        }
        
        with open(f"pending_{approval_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        
        # Отправляем посты
        # ... (код отправки такой же как выше) ...
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# Функция для публикации после согласования
def publish_approved(approval_id, channel_type):
    """Публикует пост после согласования"""
    try:
        # Загружаем данные
        with open(f"pending_{approval_id}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if channel_type == "tg":
            channel = "@da4a_hr"
            text = data["telegram_post"]
            image = data["telegram_image"]
        else:
            channel = "@tehdzenm"
            text = data["zen_post"]
            image = data["zen_image"]
        
        # Отправляем
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            params={
                "chat_id": channel,
                "photo": image,
                "caption": text,
                "parse_mode": "HTML"
            }
        )
        
        if response.status_code == 200:
            print(f"✅ Пост опубликован в {channel}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")
        return False
