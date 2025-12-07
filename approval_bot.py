def process_callback(callback_data, callback_query_id=None):
    """
    Обрабатывает нажатие кнопки
    callback_data: "approve_tg:abc123" или "reject_zen:abc123"
    """
    try:
        print(f"🔥 DEBUG: process_callback ЗАПУЩЕН! callback_data={callback_data}")
        
        if not callback_data:
            print("❌ Callback data пустой")
            return False
        
        print(f"📋 Получен callback: {callback_data}")
        
        # Парсим данные
        if ":" not in callback_data:
            print(f"❌ Неверный формат callback_data: {callback_data}")
            return False
        
        action, approval_id = callback_data.split(":", 1)
        print(f"✅ Распарсено: action={action}, approval_id={approval_id}")
        
        # Загружаем данные поста
        filename = f"pending_{approval_id}.json"
        print(f"📁 Ищу файл: {filename}")
        
        if not os.path.exists(filename):
            print(f"❌ Файл не найден: {filename}")
            # Ищем по шаблону
            import glob
            all_pending = glob.glob("pending_*.json")
            print(f"📁 Все pending файлы: {all_pending}")
            
            if all_pending:
                filename = all_pending[-1]  # Берем последний
                print(f"🔄 Берем последний файл: {filename}")
                # Пытаемся извлечь approval_id из имени файла
                import re
                match = re.search(r'pending_(.+?)\.json', filename)
                if match:
                    approval_id = match.group(1)
                    print(f"🔄 Новый approval_id: {approval_id}")
            else:
                print("❌ Нет pending файлов вообще!")
                return False
        
        print(f"✅ Загружаю данные из {filename}")
        with open(filename, "r", encoding="utf-8") as f:
            post_data = json.load(f)
        
        print(f"📊 Данные поста: theme={post_data.get('theme')}, time_slot={post_data.get('time_slot')}")
        
        # Определяем тип поста
        is_telegram = "tg" in action
        is_approved = action.startswith("approve_")
        
        print(f"🎯 Тип поста: {'Telegram' if is_telegram else 'Дзен'}")
        print(f"🎯 Действие: {'Одобрено' if is_approved else 'Отклонено'}")
        
        # Если одобрено - публикуем
        if is_approved:
            if is_telegram:
                channel = MAIN_CHANNEL
                text = post_data["telegram_post"]
                image = post_data["telegram_image"]
                post_type = "Telegram"
            else:
                channel = ZEN_CHANNEL
                text = post_data["zen_post"]
                image = post_data["zen_image"]
                post_type = "Яндекс.Дзен"
            
            print(f"🚀 Публикую {post_type} пост в {channel}")
            print(f"📝 Текст ({len(text)} символов): {text[:100]}...")
            print(f"🖼️ Картинка: {image[:100]}...")
            
            success = publish_post(channel, text, image, approval_id, post_type)
            
            if success:
                print(f"✅ {post_type} пост опубликован!")
            else:
                print(f"❌ Ошибка публикации {post_type} поста")
                return False
        else:
            print(f"❌ {post_type} пост отклонен")
        
        return True
        
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА в process_callback: {e}")
        import traceback
        traceback.print_exc()
        return False
