#!/usr/bin/env python3
"""
Скрипт для ручной проверки callback-ов
"""

import os
import sys
import requests

def main():
    """Основная функция"""
    print("🔍 РУЧНАЯ ПРОВЕРКА CALLBACK-ОВ")
    print("=" * 50)
    
    # Читаем BOT_TOKEN
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не установлен")
        print("   Установите: export BOT_TOKEN='ваш_токен'")
        sys.exit(1)
    
    # Читаем offset
    try:
        with open('last_offset.txt', 'r') as f:
            offset = int(f.read().strip())
        print(f"📊 Текущий offset: {offset}")
    except:
        offset = 0
        print(f"📊 Offset не найден, начинаем с 0")
    
    # Получаем обновления
    print(f"\n📨 Получаю обновления от Telegram...")
    
    try:
        response = requests.get(
            f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
            params={
                'offset': offset,
                'timeout': 5
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                updates = data.get('result', [])
                print(f"📊 Получено обновлений: {len(updates)}")
                
                if updates:
                    print("\n📋 ОБНОВЛЕНИЯ:")
                    print("-" * 40)
                    
                    for i, update in enumerate(updates):
                        print(f"#{i+1}: Update ID: {update.get('update_id')}")
                        
                        if 'callback_query' in update:
                            callback = update['callback_query']
                            print(f"   ✅ CALLBACK!")
                            print(f"      Data: {callback.get('data')}")
                            print(f"      ID: {callback.get('id')}")
                            print(f"      User: {callback.get('from', {}).get('id')}")
                        elif 'message' in update:
                            message = update['message']
                            print(f"   💬 Сообщение")
                            print(f"      Text: {message.get('text', '')[:50]}...")
                        else:
                            print(f"   ⚠️  Другой тип")
                        
                        print()
                    
                    # Предлагаем обновить offset
                    new_offset = updates[-1]['update_id'] + 1
                    choice = input(f"📝 Обновить offset на {new_offset}? (y/N): ").strip().lower()
                    
                    if choice == 'y':
                        with open('last_offset.txt', 'w') as f:
                            f.write(str(new_offset))
                        print(f"✅ Offset обновлен до {new_offset}")
                
                else:
                    print("📭 Нет новых обновлений")
                    
            else:
                print(f"❌ Ошибка API: {data}")
                
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            
    except Exception as e:
        print(f"💥 Ошибка: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 ПРОВЕРКА ЗАВЕРШЕНА")

if __name__ == "__main__":
    main()
