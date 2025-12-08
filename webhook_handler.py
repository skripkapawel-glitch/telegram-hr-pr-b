# webhook_handler.py - обработчик вебхуков для системы согласования
import os
import json
import logging
import sys
from github_bot import TelegramBot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def handle_webhook(request_data):
    """Обрабатывает вебхук от Telegram"""
    try:
        bot = TelegramBot()
        
        if not isinstance(request_data, dict):
            request_data = json.loads(request_data)
        
        logger.info(f"📥 Получен вебхук: {json.dumps(request_data, ensure_ascii=False)[:200]}...")
        
        success = bot.process_webhook(request_data)
        
        if success:
            logger.info("✅ Вебхук успешно обработан")
            return {"status": "success"}
        else:
            logger.warning("⚠️ Вебхук не обработан или обработан с ошибкой")
            return {"status": "no_action"}
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Для локального тестирования
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        result = handle_webhook(test_data)
        print(f"Результат: {result}")
      
