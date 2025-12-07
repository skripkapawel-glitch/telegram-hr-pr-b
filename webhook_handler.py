# webhook_handler.py - обработчик вебхуков
import os
import json
import logging
from approval_bot import process_callback

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_webhook(event):
    """
    Обрабатывает вебхук от Telegram.
    Используется в GitHub Actions или на сервере.
    event: данные вебхука в формате JSON
    """
    try:
        logger.info("📨 Получен вебхук")
        
        if isinstance(event, str):
            data = json.loads(event)
        else:
            data = event
        
        logger.info(f"📊 Тип данных: {type(data)}")
        logger.info(f"📊 Ключи: {list(data.keys()) if isinstance(data, dict) else 'не словарь'}")
        
        # Проверяем что это callback query
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback.get("data", "")
            callback_id = callback.get("id", "")
            
            logger.info(f"🔔 Callback ID: {callback_id}")
            logger.info(f"🔔 Callback data: {callback_data}")
            
            if callback_data:
                logger.info(f"🔄 Обрабатываю callback: {callback_data}")
                
                # Обрабатываем callback
                success = process_callback(callback_data, callback_id)
                
                if success:
                    logger.info("✅ Callback обработан успешно")
                    return {
                        "statusCode": 200,
                        "body": json.dumps({"status": "ok", "message": "Callback processed"})
                    }
                else:
                    logger.error("❌ Ошибка обработки callback")
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"status": "error", "message": "Callback processing failed"})
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
        
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ignored", "message": "Not a callback query"})
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }

# Для локального тестирования
if __name__ == "__main__":
    # Пример тестового callback
    test_event = {
        "callback_query": {
            "id": "test_123",
            "from": {"id": 123456},
            "data": "approve_tg:test123"
        }
    }
    
    print("🧪 Тестирую обработку вебхука...")
    result = handle_webhook(test_event)
    print(f"Результат: {result}")
