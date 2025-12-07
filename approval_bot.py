# approval_bot.py - УЛУЧШЕННАЯ И РАБОТАЮЩАЯ СИСТЕМА СОГЛАСОВАНИЯ
import os
import json
import hashlib
import time
import requests
import logging
from datetime import datetime
import sys

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

# Проверка конфигурации
logger.info(f"🔧 Конфигурация:")
logger.info(f"   BOT_TOKEN: {'✅' if BOT_TOKEN else '❌ НЕТ!'}")
logger.info(f"   ADMIN_CHAT_ID: {ADMIN_CHAT_ID if ADMIN_CHAT_ID else '❌ НЕТ!'}")
logger.info(f"   MAIN_CHANNEL: {MAIN_CHANNEL}")
logger.info(f"   ZEN_CHANNEL: {ZEN_CHANNEL}")

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
        logger.warning("⚠️ Режим согласования отключен (нет BOT_TOKEN или ADMIN_CHAT_ID)")
        return False
    
    try:
        # Генерируем уникальный ID
        timestamp = str(time.time())
        approval_id = f"appr_{hashlib.md5(f'{theme}_{timestamp}'.encode()).hexdigest()[:8]}"
        
        logger.info(f"📝 Создаю пост для согласования: {approval_id}")
        logger.info(f"   Тема: {theme}")
        logger.info(f"   Время: {time_slot}")
        logger.info(f"   Длина TG: {len(tg_text)} симв.")
        logger.info(f"   Длина Дзен: {len(zen_text)} симв.")
        
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
            "status": "pending",
            "chat_id": ADMIN_CHAT_ID
        }
        
        # Сохраняем в файл
        filename = f"pending_{approval_id}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📁 Сохранен файл: {filename}")
        
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
        
        # Отправляем Telegram пост на согласование
        logger.info(f"📤 Отправляю Telegram пост на согласование...")
        
        tg_caption = (
            f"📱 <b>POST #1 — ДЛЯ TELEGRAM</b>\n\n"
            f"🎯 <b>Тема:</b> {theme}\n"
            f"🕒 <b>Время:</b> {time_slot}\n"
            f"📊 <b>Длина:</b> {len(tg_text)} символов\n\n"
        )
        
        # Добавляем предпросмотр текста
        preview_length = 300
        if len(tg_text) > preview_length:
            preview = tg_text[:preview_length] + "..."
        else:
            preview = tg_text
        
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
            logger.error(f"❌ Ошибка отправки Telegram: {tg_response.status_code}")
            logger.error(f"❌ Ответ: {tg_response.text}")
            return False
        
        tg_result = tg_response.json()
        if not tg_result.get("ok"):
            logger.error(f"❌ Ошибка Telegram API: {tg_result}")
            return False
        
        post_data["tg_message_id"] = tg_result["result"]["message_id"]
        logger.info(f"✅ Telegram пост отправлен, message_id: {post_data['tg_message_id']}")
        
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
        
        if len(zen_text) > preview_length:
            preview = zen_text[:preview_length] + "..."
        else:
            preview = zen_text
        
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
            logger.error(f"❌ Ошибка отправки Яндекс.Дзен: {zen_response.status_code}")
            logger.error(f"❌ Ответ: {zen_response.text}")
            return False
        
        zen_result = zen_response.json()
        if not zen_result.get("ok"):
            logger.error(f"❌ Ошибка Telegram API (Дзен): {zen_result}")
            return False
        
        post_data["zen_message_id"] = zen_result["result"]["message_id"]
        logger.info(f"✅ Яндекс.Дзен пост отправлен, message_id: {post_data['zen_message_id']}")
        
        # Обновляем файл с IDs сообщений
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"🎉 Посты успешно отправлены на согласование!")
        logger.info(f"   ID: {approval_id}")
        logger.info(f"   Тема: {theme}")
        logger.info(f"   Время: {time_slot}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в send_for_approval: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def process_callback(callback_data, callback_query_id=None):
    """
    Обрабатывает нажатие кнопки
    callback_data: "approve_tg:abc123" или "reject_zen:abc123"
    """
    try:
        logger.info(f"🎯 НАЧАЛО process_callback")
        logger.info(f"📨 Callback data: {callback_data}")
        logger.info(f"📨 Callback query ID: {callback_query_id}")
        
        if not callback_data:
            logger.error("❌ Callback data пустой!")
            return False
        
        # Парсим данные
        if ":" not in callback_data:
            logger.error(f"❌ Неверный формат callback_data: {callback_data}")
            return False
        
        action, approval_id = callback_data.split(":", 1)
        logger.info(f"📊 Action: {action}, Approval ID: {approval_id}")
        
        # Загружаем данные поста
        filename = f"pending_{approval_id}.json"
        if not os.path.exists(filename):
            logger.error(f"❌ Файл не найден: {filename}")
            return False
        
        with open(filename, "r", encoding="utf-8") as f:
            post_data = json.load(f)
        
        logger.info(f"📁 Загружен пост:")
        logger.info(f"   Тема: {post_data.get('theme')}")
        logger.info(f"   Время: {post_data.get('time_slot')}")
        logger.info(f"   Статус: {post_data.get('status', 'unknown')}")
        
        # Определяем тип поста и действие
        is_telegram = "tg" in action
        is_approved = action.startswith("approve_")
        
        logger.info(f"📊 Детали:")
        logger.info(f"   Тип поста: {'Telegram' if is_telegram else 'Яндекс.Дзен'}")
        logger.info(f"   Действие: {'Одобрено' if is_approved else 'Отклонено'}")
        
        # Получаем данные для публикации
        if is_telegram:
            post_type = "Telegram"
            channel = MAIN_CHANNEL
            text = post_data.get("telegram_post", "")
            image = post_data.get("telegram_image", "")
            message_id = post_data.get("tg_message_id")
        else:
            post_type = "Яндекс.Дзен"
            channel = ZEN_CHANNEL
            text = post_data.get("zen_post", "")
            image = post_data.get("zen_image", "")
            message_id = post_data.get("zen_message_id")
        
        chat_id = post_data.get("chat_id", ADMIN_CHAT_ID)
        
        logger.info(f"📊 Данные для обработки:")
        logger.info(f"   Post type: {post_type}")
        logger.info(f"   Channel: {channel}")
        logger.info(f"   Text length: {len(text)} chars")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Chat ID: {chat_id}")
        
        # Если одобрено - публикуем
        if is_approved:
            logger.info(f"✅ Публикую {post_type} пост в канал {channel}...")
            success = publish_post(channel, text, image, approval_id, post_type)
            
            if success:
                logger.info(f"✅ {post_type} пост успешно опубликован!")
                
                # Сохраняем запись о публикации
                save_publication_record(approval_id, channel, post_type, text)
                
                # Отправляем уведомление
                send_notification(chat_id, f"✅ {post_type} пост опубликован в {channel}")
            else:
                logger.error(f"❌ Ошибка публикации {post_type} поста")
                send_notification(chat_id, f"❌ Ошибка публикации {post_type} поста")
                return False
        else:
            logger.info(f"❌ {post_type} пост отклонен")
            send_notification(chat_id, f"❌ {post_type} пост отклонен")
        
        # Обновляем сообщение у администратора
        if message_id and chat_id:
            update_message(chat_id, message_id, is_approved, post_type)
        
        # Отвечаем на callback query
        if callback_query_id:
            answer_callback(callback_query_id, is_approved, post_type)
        
        # Проверяем завершение согласования
        check_completion(approval_id, post_data, is_telegram, is_approved)
        
        logger.info(f"🎉 process_callback завершен успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в process_callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def publish_post(channel, text, image, approval_id, post_type):
    """Публикует пост в канал Telegram"""
    try:
        logger.info(f"🚀 НАЧАЛО publish_post")
        logger.info(f"📤 Канал: {channel}")
        logger.info(f"📝 Тип: {post_type}")
        logger.info(f"🔑 ID: {approval_id}")
        logger.info(f"📊 Длина текста: {len(text)} симв.")
        
        # Проверяем длину текста для Telegram
        if len(text) > 1024:
            text = text[:1020] + "..."
            logger.info(f"✂️ Текст обрезан до 1024 символов")
        
        # Пробуем отправить с картинкой
        logger.info(f"🔄 Пробую отправить с картинкой...")
        
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
                return True
            else:
                logger.error(f"❌ API вернул ошибку: {result.get('description', 'Unknown')}")
        else:
            logger.warning(f"⚠️ Не удалось отправить с картинкой: {response.status_code}")
        
        # Если не удалось с картинкой, пробуем текстом
        logger.info(f"🔄 Пробую отправить текстом...")
        
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
                return True
            else:
                logger.error(f"❌ API вернул ошибку: {result.get('description', 'Unknown')}")
        else:
            logger.error(f"❌ Не удалось отправить текстом: {response.status_code}")
        
        logger.error(f"❌ Все методы отправки не сработали!")
        return False
            
    except Exception as e:
        logger.error(f"❌ Исключение при публикации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def save_publication_record(approval_id, channel, post_type, text):
    """Сохраняет запись о публикации"""
    try:
        pub_file = f"published_{approval_id}.json"
        pub_data = {
            "approval_id": approval_id,
            "channel": channel,
            "post_type": post_type,
            "published_at": datetime.now().isoformat(),
            "text_preview": text[:200] + "..." if len(text) > 200 else text
        }
        
        # Проверяем существует ли файл
        if os.path.exists(pub_file):
            try:
                with open(pub_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                
                # Если это список, добавляем в него
                if isinstance(existing, list):
                    existing.append(pub_data)
                else:
                    # Если это объект, создаем список
                    existing = [existing, pub_data]
            except:
                existing = [pub_data]
        else:
            existing = [pub_data]
        
        # Сохраняем
        with open(pub_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Запись о публикации сохранена: {pub_file}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения записи: {e}")

def update_message(chat_id, message_id, is_approved, post_type):
    """Обновляет сообщение у администратора"""
    try:
        status_text = "✅ <b>Опубликовано в канале</b>" if is_approved else "❌ <b>Отклонено</b>"
        new_caption = f"<b>{post_type} пост</b>\n\n{status_text}"
        
        logger.info(f"✏️ Обновляю сообщение {message_id}...")
        
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
            logger.info(f"✅ Сообщение обновлено")
        else:
            logger.warning(f"⚠️ Не удалось обновить сообщение: {response.text}")
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка обновления сообщения: {e}")

def answer_callback(callback_query_id, is_approved, post_type):
    """Отвечает на callback query"""
    try:
        text = f"✅ {post_type} пост опубликован!" if is_approved else f"❌ {post_type} пост отклонен"
        
        logger.info(f"📤 Отвечаю на callback: {text}")
        
        response = session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
            params={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": True
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Ответ на callback отправлен")
        else:
            logger.warning(f"⚠️ Не удалось отправить ответ на callback: {response.text}")
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка отправки ответа на callback: {e}")

def send_notification(chat_id, message):
    """Отправляет уведомление администратору"""
    try:
        if not chat_id:
            logger.warning("⚠️ Нет chat_id для отправки уведомления")
            return
        
        logger.info(f"📨 Отправляю уведомление: {message}")
        
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
            logger.info(f"✅ Уведомление отправлено")
        else:
            logger.warning(f"⚠️ Не удалось отправить уведомление: {response.text}")
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")

def check_completion(approval_id, post_data, is_telegram, is_approved):
    """Проверяет завершено ли согласование обоих постов"""
    try:
        status_file = f"status_{approval_id}.json"
        
        # Загружаем существующий статус или создаем новый
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
        
        logger.info(f"📊 Статус обновлен:")
        logger.info(f"   Telegram: {status['telegram']}")
        logger.info(f"   Яндекс.Дзен: {status['zen']}")
        
        # Сохраняем статус
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)
        
        # Если оба решения приняты
        if status["telegram"] is not None and status["zen"] is not None:
            logger.info(f"🎉 Согласование завершено!")
            
            # Отправляем итоговое уведомление
            chat_id = post_data.get("chat_id", ADMIN_CHAT_ID)
            if chat_id:
                final_message = (
                    f"📋 <b>Согласование завершено!</b>\n\n"
                    f"🎯 Тема: {post_data.get('theme', 'неизвестно')}\n"
                    f"🕒 Время: {post_data.get('time_slot', 'неизвестно')}\n"
                    f"📱 Telegram: {status['telegram']}\n"
                    f"📝 Яндекс.Дзен: {status['zen']}"
                )
                send_notification(chat_id, final_message)
            
            # Удаляем pending файл после завершения
            pending_file = f"pending_{approval_id}.json"
            if os.path.exists(pending_file):
                try:
                    os.remove(pending_file)
                    logger.info(f"🗑️ Удален файл: {pending_file}")
                except:
                    logger.warning(f"⚠️ Не удалось удалить файл: {pending_file}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки завершения: {e}")

# Вспомогательные функции
def get_updates(offset=0):
    """Получает обновления от Telegram"""
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 10},
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def check_pending_files():
    """Проверяет pending файлы"""
    import glob
    pending_files = glob.glob("pending_*.json")
    return pending_files

# Точка входа для тестирования
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 approval_bot.py - СИСТЕМА СОГЛАСОВАНИЯ ПОСТОВ")
    print("=" * 60)
    
    if is_approval_mode():
        print("✅ Режим согласования ВКЛЮЧЕН")
        print(f"   Администратор: {ADMIN_CHAT_ID}")
        print(f"   Telegram канал: {MAIN_CHANNEL}")
        print(f"   Яндекс.Дзен канал: {ZEN_CHANNEL}")
    else:
        print("❌ Режим согласования ОТКЛЮЧЕН")
        print("   Для работы установите BOT_TOKEN и ADMIN_CHAT_ID")
    
    # Проверяем pending файлы
    pending = check_pending_files()
    print(f"\n📁 Pending файлов: {len(pending)}")
    
    for file in pending[:3]:  # Показываем первые 3
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"   • {file}: {data.get('theme')} ({data.get('time_slot')})")
        except:
            print(f"   • {file}: ошибка чтения")
    
    if len(pending) > 3:
        print(f"   ... и еще {len(pending) - 3}")
    
    print("=" * 60)
