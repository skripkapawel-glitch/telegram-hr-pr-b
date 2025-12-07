# approval_bot.py - УЛУЧШЕННАЯ СИСТЕМА СОГЛАСОВАНИЯ
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

# Сессия для запросов
session = requests.Session()
session.headers.update({
    'User-Agent': 'TelegramBot/1.0',
    'Content-Type': 'application/json'
})

def is_approval_mode():
    """Проверяем, включен ли режим согласования"""
    return bool(BOT_TOKEN and ADMIN_CHAT_ID)

def send_for_approval(tg_text, zen_text, tg_image, zen_image, theme, time_slot):
    """Отправляет пост на согласование администратору"""
    if not is_approval_mode():
        logger.warning("⚠️ Режим согласования отключен")
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
        
        logger.info(f"📁 Сохранен пост для согласования: {filename}")
        
        # Создаем клавиатуры для кнопок
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
        
        # Отправляем Telegram пост на согласование
        logger.info(f"📤 Отправляю Telegram пост на согласование...")
        
        tg_caption = (
            f"📱 <b>POST #1 — ДЛЯ TELEGRAM</b>\n\n"
            f"🎯 <b>Тема:</b> {theme}\n"
            f"🕒 <b>Время:</b> {time_slot}\n"
            f"📊 <b>Длина:</b> {len(tg_text)} символов\n\n"
        )
        
        # Добавляем предпросмотр текста
        preview = tg_text[:400] + "..." if len(tg_text) > 400 else tg_text
        tg_caption += f"<i>Предпросмотр текста:</i>\n{preview}\n\n👇 <b>Выберите действие:</b>"
        
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
            logger.error(f"❌ Ошибка отправки Telegram поста: {tg_response.text}")
            return False
        
        tg_message = tg_response.json()
        post_data["tg_message_id"] = tg_message["result"]["message_id"]
        
        # Ждем 1 секунду
        time.sleep(1)
        
        # Отправляем Яндекс.Дзен пост на согласование
        logger.info(f"📤 Отправляю Яндекс.Дзен пост на согласование...")
        
        zen_caption = (
            f"📝 <b>POST #2 — ДЛЯ ЯНДЕКС.ДЗЕН</b>\n\n"
            f"🎯 <b>Тема:</b> {theme}\n"
            f"🕒 <b>Время:</b> {time_slot}\n"
            f"📊 <b>Длина:</b> {len(zen_text)} символов\n\n"
        )
        
        preview = zen_text[:400] + "..." if len(zen_text) > 400 else zen_text
        zen_caption += f"<i>Предпросмотр текста:</i>\n{preview}\n\n👇 <b>Выберите действие:</b>"
        
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
            logger.error(f"❌ Ошибка отправки Яндекс.Дзен поста: {zen_response.text}")
            return False
        
        zen_message = zen_response.json()
        post_data["zen_message_id"] = zen_message["result"]["message_id"]
        post_data["chat_id"] = ADMIN_CHAT_ID
        
        # Обновляем файл с IDs сообщений
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Посты отправлены на согласование! ID: {approval_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в send_for_approval: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def process_callback(callback_data, callback_query_id=None):
    """
    Обрабатывает нажатие кнопки согласования
    callback_data: "approve_tg:abc123" или "reject_zen:abc123"
    """
    try:
        logger.info(f"🎯 Обработка callback: {callback_data}")
        
        if not callback_data or ":" not in callback_data:
            logger.error(f"❌ Неверный формат callback_data: {callback_data}")
            return False
        
        # Парсим данные
        action, approval_id = callback_data.split(":", 1)
        
        # Загружаем данные поста
        filename = f"pending_{approval_id}.json"
        if not os.path.exists(filename):
            logger.error(f"❌ Файл не найден: {filename}")
            return False
        
        with open(filename, "r", encoding="utf-8") as f:
            post_data = json.load(f)
        
        # Определяем тип поста и действие
        is_telegram = "tg" in action
        is_approved = action.startswith("approve_")
        
        logger.info(f"📊 Тип поста: {'Telegram' if is_telegram else 'Дзен'}")
        logger.info(f"📊 Действие: {'Одобрено' if is_approved else 'Отклонено'}")
        
        # Получаем данные для публикации
        if is_telegram:
            post_type = "Telegram"
            channel = MAIN_CHANNEL
            text = post_data["telegram_post"]
            image = post_data["telegram_image"]
            message_id = post_data.get("tg_message_id")
        else:
            post_type = "Яндекс.Дзен"
            channel = ZEN_CHANNEL
            text = post_data["zen_post"]
            image = post_data["zen_image"]
            message_id = post_data.get("zen_message_id")
        
        chat_id = post_data.get("chat_id")
        
        # Обрабатываем действие
        if is_approved:
            # Публикуем пост
            logger.info(f"✅ Публикую {post_type} пост в {channel}...")
            success = publish_post(channel, text, image, approval_id, post_type)
            
            if success:
                logger.info(f"✅ {post_type} пост опубликован")
                send_notification(chat_id, f"✅ {post_type} пост опубликован в {channel}")
            else:
                logger.error(f"❌ Ошибка публикации {post_type} поста")
                send_notification(chat_id, f"❌ Ошибка публикации {post_type} поста")
                return False
        else:
            # Отклоняем пост
            logger.info(f"❌ {post_type} пост отклонен")
            send_notification(chat_id, f"❌ {post_type} пост отклонен")
        
        # Обновляем сообщение у администратора
        if message_id and chat_id:
            update_message(chat_id, message_id, is_approved, post_type)
        
        # Отвечаем на callback query (подтверждаем получение)
        if callback_query_id:
            answer_callback(callback_query_id, is_approved, post_type)
        
        # Проверяем завершение согласования
        check_completion(approval_id, post_data, is_telegram, is_approved)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def publish_post(channel, text, image, approval_id, post_type):
    """Публикует пост в канал Telegram"""
    try:
        logger.info(f"📤 Публикация поста в {channel}")
        
        # Обрезаем текст если слишком длинный
        if len(text) > 1024:
            text = text[:1020] + "..."
            logger.info(f"✂️ Текст обрезан до 1024 символов")
        
        # Пробуем отправить с картинкой
        params = {
            "chat_id": channel,
            "photo": image,
            "caption": text,
            "parse_mode": "HTML"
        }
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(f"✅ Пост опубликован с картинкой")
                
                # Сохраняем факт публикации
                save_publication_record(approval_id, channel, post_type, text, "sendPhoto")
                return True
            else:
                logger.error(f"❌ API ошибка: {result.get('description')}")
        
        # Если не удалось с картинкой, пробуем текстом
        logger.info(f"⚠️ Пробую отправить текстом...")
        
        params = {
            "chat_id": channel,
            "text": text,
            "parse_mode": "HTML"
        }
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(f"✅ Пост опубликован текстом")
                
                # Сохраняем факт публикации
                save_publication_record(approval_id, channel, post_type, text, "sendMessage")
                return True
        
        logger.error(f"❌ Не удалось опубликовать пост")
        return False
            
    except Exception as e:
        logger.error(f"❌ Исключение при публикации: {e}")
        return False

def save_publication_record(approval_id, channel, post_type, text, method):
    """Сохраняет запись о публикации"""
    try:
        pub_file = f"published_{approval_id}.json"
        pub_data = {
            "approval_id": approval_id,
            "channel": channel,
            "post_type": post_type,
            "published_at": datetime.now().isoformat(),
            "text_preview": text[:200] + "..." if len(text) > 200 else text,
            "method": method
        }
        
        # Если файл уже существует, добавляем в список
        if os.path.exists(pub_file):
            with open(pub_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            
            if isinstance(existing, list):
                existing.append(pub_data)
            else:
                existing = [existing, pub_data]
            
            with open(pub_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        else:
            with open(pub_file, "w", encoding="utf-8") as f:
                json.dump([pub_data], f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Запись о публикации сохранена: {pub_file}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения записи: {e}")

def update_message(chat_id, message_id, is_approved, post_type):
    """Обновляет сообщение у администратора"""
    try:
        status_text = "✅ <b>Опубликовано</b>" if is_approved else "❌ <b>Отклонено</b>"
        new_caption = f"<b>{post_type} пост</b>\n\n{status_text}"
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption",
            params={
                "chat_id": chat_id,
                "message_id": message_id,
                "caption": new_caption,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✏️ Сообщение обновлено")
        else:
            logger.warning(f"⚠️ Не удалось обновить сообщение")
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка обновления сообщения: {e}")

def answer_callback(callback_query_id, is_approved, post_type):
    """Отвечает на callback query"""
    try:
        text = f"✅ {post_type} пост опубликован!" if is_approved else f"❌ {post_type} пост отклонен"
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
            params={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": True
            },
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"⚠️ Не удалось ответить на callback")
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка ответа на callback: {e}")

def send_notification(chat_id, message):
    """Отправляет уведомление администратору"""
    try:
        if not chat_id:
            return
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"📨 Уведомление отправлено")
        else:
            logger.warning(f"⚠️ Не удалось отправить уведомление")
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")

def check_completion(approval_id, post_data, is_telegram, is_approved):
    """Проверяет завершено ли согласование обоих постов"""
    try:
        status_file = f"status_{approval_id}.json"
        
        # Загружаем или создаем статус
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
        
        # Сохраняем статус
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)
        
        # Если оба решения приняты
        if status["telegram"] is not None and status["zen"] is not None:
            logger.info(f"📝 Согласование завершено!")
            logger.info(f"   Telegram: {status['telegram']}")
            logger.info(f"   Яндекс.Дзен: {status['zen']}")
            
            # Отправляем итоговое уведомление
            chat_id = post_data.get("chat_id")
            if chat_id:
                final_message = (
                    f"📋 <b>Согласование завершено!</b>\n\n"
                    f"🎯 Тема: {post_data['theme']}\n"
                    f"🕒 Время: {post_data['time_slot']}\n"
                    f"📱 Telegram: {status['telegram']}\n"
                    f"📝 Яндекс.Дзен: {status['zen']}"
                )
                send_notification(chat_id, final_message)
            
            # Удаляем pending файл после завершения
            pending_file = f"pending_{approval_id}.json"
            if os.path.exists(pending_file):
                os.remove(pending_file)
                logger.info(f"🗑️ Удален файл: {pending_file}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки завершения: {e}")

# Функция для обработки callback-ов из GitHub Actions
def process_pending_callbacks():
    """Проверяет и обрабатывает ожидающие callback-и"""
    try:
        logger.info("🔄 Проверяю ожидающие callback-и...")
        
        # Сканируем pending файлы
        import glob
        pending_files = glob.glob("pending_*.json")
        
        if not pending_files:
            logger.info("📭 Нет ожидающих callback-ов")
            return
        
        logger.info(f"📁 Найдено pending файлов: {len(pending_files)}")
        
        # Здесь будет логика обработки callback-ов из Telegram
        # (используется в отдельном workflow)
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки callback-ов: {e}")

if __name__ == "__main__":
    print("🤖 Модуль согласования постов")
    print("=" * 50)
    
    if is_approval_mode():
        print("✅ Режим согласования ВКЛЮЧЕН")
        print(f"   Администратор: {ADMIN_CHAT_ID}")
        print(f"   Telegram канал: {MAIN_CHANNEL}")
        print(f"   Яндекс.Дзен канал: {ZEN_CHANNEL}")
        
        # Проверяем pending файлы
        process_pending_callbacks()
    else:
        print("❌ Режим согласования ОТКЛЮЧЕН")
        print("   Проверьте BOT_TOKEN и ADMIN_CHAT_ID")
    
    print("=" * 50)
