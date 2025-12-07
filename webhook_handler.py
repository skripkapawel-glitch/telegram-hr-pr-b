# webhook_handler.py - обработчик вебхуков
import os
import json
import logging
import sys
from approval_bot import process_callback

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def handle_webhook(event):
    """
    Обрабатывает вебхук от Telegram.
    Используется в GitHub Actions или на сервере.
    event: данные вебхука в формате JSON
    """
    try:
        logger.info("=" * 60)
        logger.info("📨 ПОЛУЧЕН ВЕБХУК ОТ TELEGRAM")
        logger.info("=" * 60)
        
        if isinstance(event, str):
            data = json.loads(event)
        else:
            data = event
        
        logger.info(f"📊 Тип данных: {type(data)}")
        logger.info(f"📊 Ключи в данных: {list(data.keys())}")
        
        # ВАЖНО: GitHub Actions отправляет данные в client_payload
        if "client_payload" in data:
            logger.info("🔍 Обнаружен client_payload (GitHub Actions формат)")
            data = data["client_payload"]
            logger.info(f"📊 Новые ключи: {list(data.keys())}")
        
        # Проверяем что это callback query
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback.get("data", "")
            callback_id = callback.get("id", "")
            
            logger.info(f"✅ CALLBACK ОБНАРУЖЕН!")
            logger.info(f"🔔 Callback ID: {callback_id}")
            logger.info(f"🔔 Callback data: {callback_data}")
            logger.info(f"👤 От пользователя: {callback.get('from', {}).get('id')}")
            
            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
            logger.info("📋 Полные данные callback_query:")
            logger.info(json.dumps(callback, indent=2, ensure_ascii=False))
            
            if not callback_data:
                logger.error("❌ Callback data пустой!")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"status": "error", "message": "Empty callback data"})
                }
            
            # Парсим approval_id для проверки файла
            if ":" in callback_data:
                action, approval_id = callback_data.split(":", 1)
                filename = f"pending_{approval_id}.json"
                logger.info(f"📁 Ищу файл: {filename}")
                
                if os.path.exists(filename):
                    logger.info(f"✅ Файл найден: {filename}")
                    with open(filename, "r", encoding="utf-8") as f:
                        file_content = json.load(f)
                    logger.info(f"📄 Данные файла - theme: {file_content.get('theme')}, time_slot: {file_content.get('time_slot')}")
                else:
                    logger.error(f"❌ Файл не найден: {filename}")
                    # Ищем любой pending файл
                    import glob
                    pending_files = glob.glob("pending_*.json")
                    logger.info(f"📁 Все pending файлы: {pending_files}")
            
            # Обрабатываем callback
            logger.info(f"🔄 ЗАПУСКАЮ ОБРАБОТКУ: {callback_data}")
            
            try:
                success = process_callback(callback_data, callback_id)
                
                if success:
                    logger.info("🎉 CALLBACK ОБРАБОТАН УСПЕШНО!")
                    # Проверяем создался ли published файл
                    if ":" in callback_data:
                        _, approval_id = callback_data.split(":", 1)
                        pub_file = f"published_{approval_id}.json"
                        if os.path.exists(pub_file):
                            logger.info(f"✅ Файл публикации создан: {pub_file}")
                        else:
                            logger.warning(f"⚠️ Файл публикации НЕ создан: {pub_file}")
                    
                    return {
                        "statusCode": 200,
                        "body": json.dumps({"status": "ok", "message": "Callback processed successfully"})
                    }
                else:
                    logger.error("❌ Ошибка обработки callback (process_callback вернул False)")
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"status": "error", "message": "Callback processing failed"})
                    }
                    
            except Exception as e:
                logger.error(f"💥 ИСКЛЮЧЕНИЕ в process_callback: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "body": json.dumps({"status": "error", "message": f"Exception: {str(e)}"})
                }
        
        # Если это обычное сообщение (не callback)
        elif "message" in data:
            message = data["message"]
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            
            logger.info(f"💬 Сообщение от {chat_id}: {text[:100]}...")
            
            return {
                "statusCode": 200,
                "body": json.dumps({"status": "message_received", "chat_id": chat_id})
            }
        else:
            logger.warning(f"⚠️ Неизвестный формат данных. Первые 1000 символов:")
            logger.warning(json.dumps(data, ensure_ascii=False)[:1000])
            
            return {
                "statusCode": 200,
                "body": json.dumps({"status": "ignored", "message": "Not a callback query or message"})
            }
        
    except Exception as e:
        logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА обработки вебхука: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }

# Для локального тестирования
if __name__ == "__main__":
    # Пример тестового callback с реальными данными
    test_event = {
        "callback_query": {
            "id": "123456789012345",
            "from": {"id": 12345678, "first_name": "Test", "username": "testuser"},
            "message": {
                "message_id": 123,
                "chat": {"id": 12345678, "type": "private"}
            },
            "data": "approve_tg:abc123def"
        }
    }
    
    print("🧪 Тестирую обработку вебхука...")
    result = handle_webhook(test_event)
    print(f"Результат: {result}")
