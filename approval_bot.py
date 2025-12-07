# approval_bot.py - ПОЛНАЯ СИСТЕМА СОГЛАСОВАНИЯ
import os
import json
import hashlib
import time
import requests
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MAIN_CHANNEL = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL = "@tehdzenm"

# Сессия
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def is_approval_mode():
    """Проверяем, включен ли режим согласования"""
    return bool(BOT_TOKEN and ADMIN_CHAT_ID)

def send_for_approval(tg_text, zen_text, tg_image, zen_image, theme, time_slot):
    """Основная функция отправки на согласование"""
    if not is_approval_mode():
        logger.warning("⚠️ Режим согласования отключен (нет BOT_TOKEN или ADMIN_CHAT_ID)")
        return False
    
    try:
        # Генерируем уникальный ID
        timestamp = str(time.time())
        approval_id = f"appr_{hashlib.md5(f'{theme}_{timestamp}'.encode()).hexdigest()[:8]}"
        
        # Сохраняем данные
        post_data = {
            "approval_id": approval_id,
            "theme": theme,
            "time_slot": time_slot,
            "telegram_post": tg_text,
            "zen_post": zen_text,
            "telegram_image": tg_image,
            "zen_image": zen_image,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Сохраняем в файл
        filename = f"pending_{approval_id}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📁 Сохранен пост для согласования: {approval_id}")
        
        # Создаем клавиатуры
        tg_keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Опубликовать в Telegram", "callback_data": f"approve_tg:{approval_id}"},
                {"text": "❌ Отклонить", "callback_data": f"reject_tg:{approval_id}"}
            ]]
        }
        
        zen_keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Опубликовать в Яндекс.Дзен", "callback_data": f"approve_zen:{approval_id}"},
                {"text": "❌ Отклонить", "callback_data": f"reject_zen:{approval_id}"}
            ]]
        }
        
        # Отправляем Telegram пост
        logger.info("📤 Отправляю Telegram пост на согласование...")
        
        tg_caption = (
            f"📱 <b>POST #1 — ДЛЯ TELEGRAM</b>\n\n"
            f"🎯 <b>Тема:</b> {theme}\n"
            f"🕒 <b>Время:</b> {time_slot}\n"
            f"📊 <b>Длина:</b> {len(tg_text)} символов\n\n"
        )
        
        # Добавляем предпросмотр текста
        if len(tg_text) > 600:
            preview = tg_text[:600] + "..."
        else:
            preview = tg_text
        
        tg_caption += f"<i>Текст поста:</i>\n{preview}\n\n👇 <b>Выберите действие:</b>"
        
        tg_response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            params={
                "chat_id": ADMIN_CHAT_ID,
                "photo": tg_image,
                "caption": tg_caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(tg_keyboard)
            },
            timeout=30
        )
        
        if tg_response.status_code != 200:
            logger.error(f"❌ Ошибка отправки Telegram: {tg_response.text}")
            return False
        
        tg_message = tg_response.json()
        post_data["tg_message_id"] = tg_message["result"]["message_id"]
        
        # Ждем 1 секунду
        time.sleep(1)
        
        # Отправляем Яндекс.Дзен пост
        logger.info("📤 Отправляю Яндекс.Дзен пост на согласование...")
        
        zen_caption = (
            f"📝 <b>POST #2 — ДЛЯ ЯНДЕКС.ДЗЕН</b>\n\n"
            f"🎯 <b>Тема:</b> {theme}\n"
            f"🕒 <b>Время:</b> {time_slot}\n"
            f"📊 <b>Длина:</b> {len(zen_text)} символов\n\n"
        )
        
        if len(zen_text) > 600:
            preview = zen_text[:600] + "..."
        else:
            preview = zen_text
        
        zen_caption += f"<i>Текст поста:</i>\n{preview}\n\n👇 <b>Выберите действие:</b>"
        
        zen_response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            params={
                "chat_id": ADMIN_CHAT_ID,
                "photo": zen_image,
                "caption": zen_caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(zen_keyboard)
            },
            timeout=30
        )
        
        if zen_response.status_code != 200:
            logger.error(f"❌ Ошибка отправки Яндекс.Дзен: {zen_response.text}")
            return False
        
        zen_message = zen_response.json()
        post_data["zen_message_id"] = zen_message["result"]["message_id"]
        post_data["chat_id"] = ADMIN_CHAT_ID
        
        # Обновляем файл с IDs сообщений
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        # Сохраняем в историю
        save_to_history(approval_id, "sent_for_approval")
        
        logger.info(f"✅ Посты отправлены на согласование! ID: {approval_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в send_for_approval: {e}")
        return False

def process_callback(callback_data, callback_query_id=None):
    """
    Обрабатывает нажатие кнопки
    callback_data: "approve_tg:abc123" или "reject_zen:abc123"
    """
    try:
        if not callback_data:
            return False
        
        logger.info(f"🔄 Обрабатываю callback: {callback_data}")
        
        # Парсим данные
        if ":" not in callback_data:
            logger.error(f"❌ Неверный формат callback_data: {callback_data}")
            return False
        
        action, approval_id = callback_data.split(":", 1)
        
        # Загружаем данные поста
        filename = f"pending_{approval_id}.json"
        if not os.path.exists(filename):
            logger.error(f"❌ Файл не найден: {filename}")
            return False
        
        with open(filename, "r", encoding="utf-8") as f:
            post_data = json.load(f)
        
        # Определяем тип поста
        is_telegram = "tg" in action
        is_approved = action.startswith("approve_")
        
        # Обновляем статус сообщения
        if is_telegram:
            message_id = post_data.get("tg_message_id")
            post_type = "Telegram"
            channel = MAIN_CHANNEL
            text = post_data["telegram_post"]
            image = post_data["telegram_image"]
        else:
            message_id = post_data.get("zen_message_id")
            post_type = "Яндекс.Дзен"
            channel = ZEN_CHANNEL
            text = post_data["zen_post"]
            image = post_data["zen_image"]
        
        chat_id = post_data.get("chat_id")
        
        # Обновляем сообщение у администратора
        if message_id and chat_id:
            update_message(chat_id, message_id, is_approved, post_type)
        
        # Если одобрено - публикуем
        if is_approved:
            logger.info(f"✅ Публикую {post_type} пост...")
            success = publish_post(channel, text, image, approval_id, post_type)
            
            if success:
                action_type = f"{'telegram' if is_telegram else 'zen'}_approved"
                save_to_history(approval_id, action_type)
            else:
                logger.error(f"❌ Ошибка публикации {post_type} поста")
                return False
        else:
            logger.info(f"❌ {post_type} пост отклонен")
            action_type = f"{'telegram' if is_telegram else 'zen'}_rejected"
            save_to_history(approval_id, action_type)
        
        # Отвечаем на callback
        if callback_query_id:
            answer_callback(callback_query_id, is_approved, post_type)
        
        # Проверяем, все ли решения приняты
        check_completion(approval_id, post_data, is_telegram, is_approved)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_callback: {e}")
        return False

def update_message(chat_id, message_id, is_approved, post_type):
    """Обновляет сообщение у администратора"""
    try:
        status_text = "✅ <b>Согласовано — пост отправлен в канал</b>" if is_approved else "❌ <b>Не согласовано — пост не опубликован</b>"
        
        # Получаем текущее сообщение
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
            params={"chat_id": chat_id}
        )
        
        # Просто пытаемся отредактировать заголовок
        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption"
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": f"<b>{post_type} пост</b>\n\n{status_text}",
            "parse_mode": "HTML"
        }
        
        session.post(edit_url, params=params, timeout=10)
        logger.info(f"✏️ Обновлено сообщение {message_id}")
        
    except Exception as e:
        logger.warning(f"⚠️ Не удалось обновить сообщение: {e}")

def publish_post(channel, text, image, approval_id, post_type):
    """Публикует пост в канал"""
    try:
        # Проверяем длину
        if len(text) > 1024:
            text = text[:1020] + "..."
        
        logger.info(f"📤 Публикую в {channel}...")
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            params={
                "chat_id": channel,
                "photo": image,
                "caption": text,
                "parse_mode": "HTML"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"✅ {post_type} пост опубликован в {channel}")
            
            # Сохраняем факт публикации
            pub_file = f"published_{approval_id}.json"
            pub_data = {
                "approval_id": approval_id,
                "channel": channel,
                "post_type": post_type,
                "published_at": datetime.now().isoformat()
            }
            
            if os.path.exists(pub_file):
                with open(pub_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing.append(pub_data)
                with open(pub_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2)
            else:
                with open(pub_file, "w", encoding="utf-8") as f:
                    json.dump([pub_data], f, indent=2)
            
            return True
        else:
            logger.error(f"❌ Ошибка публикации: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Исключение при публикации: {e}")
        return False

def answer_callback(callback_query_id, is_approved, post_type):
    """Отвечает на callback query"""
    try:
        text = f"✅ {post_type} пост опубликован!" if is_approved else f"❌ {post_type} пост отклонен"
        
        session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
            params={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": True
            },
            timeout=10
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось ответить на callback: {e}")

def check_completion(approval_id, post_data, is_telegram, is_approved):
    """Проверяет завершено ли согласование"""
    try:
        # Проверяем статусы
        status_file = f"status_{approval_id}.json"
        
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                status = json.load(f)
        else:
            status = {"telegram": None, "zen": None}
        
        # Обновляем статус
        if is_telegram:
            status["telegram"] = "approved" if is_approved else "rejected"
        else:
            status["zen"] = "approved" if is_approved else "rejected"
        
        # Сохраняем
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)
        
        # Если оба решения приняты, можно удалить временные файлы
        if status["telegram"] is not None and status["zen"] is not None:
            logger.info(f"📝 Согласование {approval_id} завершено")
            # Здесь можно добавить очистку файлов
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки завершения: {e}")

def save_to_history(approval_id, action):
    """Сохраняет действие в историю"""
    try:
        history_file = "approval_history.json"
        history = []
        
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        
        record = {
            "approval_id": approval_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        
        history.append(record)
        
        # Ограничиваем размер
        if len(history) > 200:
            history = history[-200:]
        
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения истории: {e}")

# Простая функция для ручного тестирования
if __name__ == "__main__":
    print("🤖 Модуль согласования постов")
    print("=" * 50)
    
    if is_approval_mode():
        print("✅ Режим согласования ВКЛЮЧЕН")
        print(f"   Администратор: {ADMIN_CHAT_ID}")
    else:
        print("❌ Режим согласования ОТКЛЮЧЕН")
        print("   Проверьте BOT_TOKEN и ADMIN_CHAT_ID")
    
    print("=" * 50)
