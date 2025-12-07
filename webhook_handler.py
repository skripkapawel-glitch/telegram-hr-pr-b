# Проверяем что это callback query
if "callback_query" in data:
    callback = data["callback_query"]
    callback_data = callback.get("data", "")
    callback_id = callback.get("id", "")
    
    logger.info(f"🔔 Callback ID: {callback_id}")
    logger.info(f"🔔 Callback data: {callback_data}")
    
    # ЛОГИРУЕМ ВСЕ ДАННЫЕ
    logger.info(f"📋 Полные данные callback_query:")
    logger.info(json.dumps(callback, indent=2, ensure_ascii=False)[:1000])
    
    if callback_data:
        logger.info(f"🔄 Обрабатываю callback: {callback_data}")
        
        # Проверяем существование файла перед обработкой
        if ":" in callback_data:
            _, approval_id = callback_data.split(":", 1)
            filename = f"pending_{approval_id}.json"
            logger.info(f"📁 Проверяю файл: {filename}")
            
            if os.path.exists(filename):
                logger.info(f"✅ Файл найден: {filename}")
                with open(filename, "r", encoding="utf-8") as f:
                    file_content = json.load(f)
                logger.info(f"📄 Содержимое файла: {json.dumps(file_content, ensure_ascii=False)[:500]}")
            else:
                logger.error(f"❌ Файл не найден: {filename}")
        
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
