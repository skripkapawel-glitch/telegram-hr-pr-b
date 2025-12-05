import os
import requests
import random
import json
import time
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus
import base64

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("MAIN_CHANNEL_ID", "@da4a_hr")  # Основной канал
YANDEX_CHANNEL_ID = os.environ.get("YANDEX_CHANNEL_ID", "@tehdzemm")  # Яндекс канал в ТГ
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Проверка обязательных переменных
if not BOT_TOKEN:
    logger.error("❌ Отсутствует BOT_TOKEN")
    exit(1)
if not GEMINI_API_KEY:
    logger.error("❌ Отсутствует GEMINI_API_KEY")
    exit(1)

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI ГЕНЕРАЦИЯ ПОСТОВ С ФОТО")
print("=" * 80)
print(f"🔑 BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Отсутствует'}")
print(f"🔑 GEMINI_API_KEY: {'✅ Установлен' if GEMINI_API_KEY else '❌ Отсутствует'}")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Яндекс канал: {YANDEX_CHANNEL_ID}")

class AIPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        self.working_model = None
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "chars": "700-1000",
                "description": "Короткий, энергичный утренний старт"
            },
            "14:00": {
                "type": "day",
                "name": "Дневной пост",
                "emoji": "🌞",
                "chars": "1500-2500",
                "description": "Самый объёмный, аналитика + живой язык"
            },
            "19:00": {
                "type": "evening",
                "name": "Вечерний пост",
                "emoji": "🌙",
                "chars": "900-1300",
                "description": "Средний, расслабленный, но цепляющий"
            }
        }

    def load_post_history(self):
        """Загружает историю постов"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {
                "posts": {},
                "themes": {},
                "last_post_time": None
            }

    def save_post_history(self):
        """Сохраняет историю постов"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения истории: {e}")

    def get_smart_theme(self):
        """Выбирает тему"""
        try:
            themes_history = self.post_history.get("themes", {}).get("global", [])
            available_themes = self.themes.copy()
            
            # Убираем последние 2 использованные темы
            for theme in themes_history[-2:]:
                if theme in available_themes:
                    available_themes.remove(theme)
            
            if not available_themes:
                available_themes = self.themes.copy()
            
            theme = random.choice(available_themes)
            
            # Сохраняем историю
            if "themes" not in self.post_history:
                self.post_history["themes"] = {}
            if "global" not in self.post_history["themes"]:
                self.post_history["themes"]["global"] = []
            
            self.post_history["themes"]["global"].append(theme)
            if len(self.post_history["themes"]["global"]) > 10:
                self.post_history["themes"]["global"] = self.post_history["themes"]["global"][-8:]
            
            self.save_post_history()
            logger.info(f"🎯 Выбрана тема: {theme}")
            return theme
            
        except Exception as e:
            logger.error(f"Ошибка выбора темы: {e}")
            return random.choice(self.themes)

    def generate_post_with_gemini(self, theme, time_slot_info):
        """Генерирует пост с текстом и предложением для картинки через Gemini"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['chars']
        
        # Промт для Gemini
        prompt = f"""Создай пост для Telegram на тему: "{theme}"

Время публикации: {time_slot_info['name']} ({time_slot_info['emoji']})
Объем: {chars_range} знаков
Стиль: {time_slot_info['description']}

Требования к посту:
1. Начни с цепляющего хука (первые 2 строки)
2. Основной текст с полезной информацией
3. 2-4 ключевых пункта (используй символ •)
4. Вопрос для вовлечения аудитории
5. 3-5 релевантных хештегов

Отдельно предложи 3 варианта поисковых запросов для картинки к этому посту.
Картинка должна быть релевантной теме и привлекательной.

Формат ответа:
[ТЕКСТ ПОСТА]

[ЗАПРОСЫ ДЛЯ КАРТИНКИ]
1. первый запрос на английском
2. второй запрос на английском  
3. третий запрос на английском

Пример:
Отличное утро начинается с правильного настроя! 🌅

Сегодня поговорим о важности командообразования в современном бизнесе.

• Регулярные тимбилдинги повышают продуктивность на 25%
• Участники чувствуют себя частью общей цели
• Улучшается коммуникация между отделами

А как часто вы проводите командные мероприятия?

#тимбилдинг #команда #бизнес #hr

[ЗАПРОСЫ ДЛЯ КАРТИНКИ]
1. team building office business
2. workplace collaboration meeting
3. happy team professionals"""

        try:
            # Используем Gemini 1.5 Flash как наиболее стабильную
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "topK": 40,
                    "topP": 0.9,
                    "maxOutputTokens": 2000,
                }
            }
            
            logger.info("🧠 Генерация поста с помощью Gemini...")
            response = requests.post(url, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # Парсим результат
                    if "[ЗАПРОСЫ ДЛЯ КАРТИНКИ]" in generated_text:
                        post_text, image_part = generated_text.split("[ЗАПРОСЫ ДЛЯ КАРТИНКИ]", 1)
                        post_text = post_text.strip()
                        
                        # Извлекаем запросы для картинки
                        image_queries = []
                        lines = image_part.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if line and any(char.isalpha() for char in line):
                                # Убираем нумерацию "1. ", "2. " и т.д.
                                query = re.sub(r'^\d+\.\s*', '', line)
                                if query and len(query) > 3:
                                    image_queries.append(query)
                        
                        # Если не нашли запросы, создаем свои
                        if not image_queries:
                            theme_keywords = {
                                "HR и управление персоналом": ["office team meeting", "human resources", "business professionals"],
                                "PR и коммуникации": ["public relations", "social media marketing", "communication"],
                                "ремонт и строительство": ["construction workers", "building renovation", "tools architecture"]
                            }
                            image_queries = theme_keywords.get(theme, ["business"])
                        
                        logger.info("✅ Пост сгенерирован успешно")
                        return post_text, image_queries[:3]  # Берем до 3 запросов
                    
                    else:
                        # Если формат не совпадает, используем весь текст
                        logger.warning("Формат ответа не совпал, используем весь текст")
                        return generated_text, [f"{theme} business"]
            
            logger.error(f"Ошибка API Gemini: {response.status_code}")
            return None, []
                
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return None, []

    def get_image_from_unsplash(self, query):
        """Получает изображение с Unsplash по запросу"""
        try:
            # Кодируем запрос
            encoded_query = quote_plus(query)
            
            # Unsplash URL с разными вариантами
            urls = [
                f"https://source.unsplash.com/1200x630/?{encoded_query}",
                f"https://source.unsplash.com/featured/1200x630/?{encoded_query}",
                f"https://images.unsplash.com/photo-{random.randint(1000000000, 9999999999)}?fit=crop&w=1200&h=630&q=80",
            ]
            
            # Добавляем рандомный ID для избежания кэша
            timestamp = int(time.time())
            for i, url in enumerate(urls):
                if "?" in url:
                    urls[i] = f"{url}&t={timestamp}&random={random.randint(1, 10000)}"
                else:
                    urls[i] = f"{url}?t={timestamp}&random={random.randint(1, 10000)}"
            
            # Пробуем каждый URL
            for url in urls:
                try:
                    logger.info(f"🔍 Поиск картинки: {url[:80]}...")
                    
                    # HEAD запрос для проверки
                    head_response = requests.head(url, timeout=5, allow_redirects=True)
                    
                    if head_response.status_code in [200, 301, 302]:
                        final_url = head_response.url
                        
                        # GET запрос для проверки что это действительно картинка
                        img_response = requests.get(final_url, timeout=10)
                        if img_response.status_code == 200:
                            # Проверяем content-type
                            content_type = img_response.headers.get('content-type', '')
                            if 'image' in content_type:
                                logger.info(f"✅ Картинка найдена: {final_url[:80]}...")
                                return final_url
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"URL недоступен: {e}")
                    continue
            
            # Fallback - случайная картинка с Unsplash
            fallback_url = f"https://source.unsplash.com/1200x630/?{quote_plus('business')}&t={timestamp}"
            logger.warning(f"🔄 Используем fallback картинку")
            return fallback_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return None

    def clean_text_for_telegram(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы
        replacements = {
            '&nbsp;': ' ',
            '&emsp;': '    ',
            '&ensp;': '  ',
            ' ': '    ',
            ' ': '  ',
            ' ': ' ',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Удаляем лишние пустые строки
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # Обрезаем если слишком длинный
        if len(text) > 4096:
            text = text[:4000] + "\n\n..."
        
        return text

    def send_telegram_photo(self, chat_id, photo_url, caption=""):
        """Отправляет фото в Telegram"""
        try:
            # Сначала пробуем отправить по URL
            logger.info(f"📤 Отправка фото в {chat_id}...")
            
            # Очищаем caption
            clean_caption = self.clean_text_for_telegram(caption)
            if len(clean_caption) > 1024:
                clean_caption = clean_caption[:1000] + "..."
            
            # Метод 1: Отправка по URL
            params = {
                'chat_id': chat_id,
                'photo': photo_url,
            }
            
            if clean_caption:
                params['caption'] = clean_caption
                params['parse_mode'] = 'HTML'  # Пробуем HTML
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в {chat_id}")
                return True
            
            # Если HTML не работает, пробуем без parse_mode
            if clean_caption:
                params['parse_mode'] = None
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено (без parse_mode) в {chat_id}")
                return True
            
            # Метод 2: Скачиваем и отправляем файлом
            logger.info("🔄 Пробуем скачать и отправить файлом...")
            
            try:
                img_response = requests.get(photo_url, timeout=15)
                if img_response.status_code == 200 and len(img_response.content) > 10240:
                    
                    # Сохраняем временно
                    with open('temp_image.jpg', 'wb') as f:
                        f.write(img_response.content)
                    
                    # Отправляем как файл
                    with open('temp_image.jpg', 'rb') as photo_file:
                        files = {'photo': photo_file}
                        data = {'chat_id': chat_id}
                        
                        if clean_caption:
                            data['caption'] = clean_caption
                        
                        response = requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                            data=data,
                            files=files,
                            timeout=30
                        )
                    
                    # Удаляем временный файл
                    try:
                        os.remove('temp_image.jpg')
                    except:
                        pass
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Фото (файлом) отправлено в {chat_id}")
                        return True
                        
            except Exception as e:
                logger.warning(f"Ошибка скачивания: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            return False

    def send_telegram_message(self, chat_id, text):
        """Отправляет текстовое сообщение в Telegram"""
        try:
            clean_text = self.clean_text_for_telegram(text)
            
            if not clean_text:
                logger.error("Пустой текст")
                return False
            
            params = {
                'chat_id': chat_id,
                'text': clean_text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен в {chat_id}")
                return True
            
            # Пробуем без parse_mode
            params['parse_mode'] = None
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен (без HTML) в {chat_id}")
                return True
            
            logger.error(f"❌ Ошибка отправки текста: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты в оба канала"""
        try:
            logger.info("⏰ Проверка времени последнего поста...")
            
            # Проверка интервала между постами
            last_post_time = self.post_history.get("last_post_time")
            if last_post_time:
                last_time = datetime.fromisoformat(last_post_time)
                time_since_last = datetime.now() - last_time
                hours_since_last = time_since_last.total_seconds() / 3600
                
                if hours_since_last < 3:
                    logger.info(f"⏭️ Пропускаем - прошло всего {hours_since_last:.1f} часов")
                    return True
            
            # Выбор темы
            self.current_theme = self.get_smart_theme()
            
            # Определение временного слота
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            slots = list(self.time_slots.keys())
            time_objects = [datetime.strptime(slot, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day) for slot in slots]
            
            closest_slot = min(time_objects, key=lambda x: abs((now - x).total_seconds()))
            slot_name = closest_slot.strftime("%H:%M")
            time_slot_info = self.time_slots.get(slot_name, self.time_slots["14:00"])
            
            logger.info(f"🕒 Текущее время: {current_time_str}")
            logger.info(f"📅 Выбран слот: {slot_name} - {time_slot_info['emoji']} {time_slot_info['name']}")
            logger.info(f"📏 Объем: {time_slot_info['chars']} знаков")
            
            # Генерация поста с помощью Gemini
            logger.info("🧠 Генерация поста через Gemini...")
            post_text, image_queries = self.generate_post_with_gemini(self.current_theme, time_slot_info)
            
            if not post_text:
                logger.error("❌ Не удалось сгенерировать пост")
                # Fallback текст
                post_text = f"{self.current_theme}\n\n{time_slot_info['emoji']} {time_slot_info['description']}\n\nОбсудим в комментариях?\n\n#{self.current_theme.replace(' ', '').replace('и', '')}"
                image_queries = [self.current_theme]
            
            logger.info(f"📊 Длина поста: {len(post_text)} знаков")
            logger.info(f"🔍 Запросы для картинки: {image_queries}")
            
            # Поиск картинки
            logger.info("🖼️ Поиск картинки...")
            image_url = None
            
            for query in image_queries:
                image_url = self.get_image_from_unsplash(query)
                if image_url:
                    logger.info(f"✅ Картинка найдена по запросу: '{query}'")
                    break
            
            if not image_url:
                # Последняя попытка с общей картинкой
                image_url = self.get_image_from_unsplash("business professional")
                if not image_url:
                    logger.warning("❌ Не удалось найти картинку")
            
            # Отправка в оба канала
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку постов...")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал
            logger.info(f"📤 Отправка в основной канал: {MAIN_CHANNEL_ID}")
            if image_url:
                main_success = self.send_telegram_photo(MAIN_CHANNEL_ID, image_url, post_text)
            else:
                main_success = self.send_telegram_message(MAIN_CHANNEL_ID, post_text)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной канал: УСПЕХ")
            else:
                logger.error("❌ Основной канал: НЕУДАЧА")
            
            time.sleep(3)  # Пауза между отправками
            
            # Яндекс канал (в ТГ)
            logger.info(f"📤 Отправка в Яндекс канал: {YANDEX_CHANNEL_ID}")
            
            # Для Яндекс канала можно добавить префикс
            yandex_text = f"📰 {post_text}"
            
            if image_url:
                yandex_success = self.send_telegram_photo(YANDEX_CHANNEL_ID, image_url, yandex_text)
            else:
                yandex_success = self.send_telegram_message(YANDEX_CHANNEL_ID, yandex_text)
            
            if yandex_success:
                success_count += 1
                logger.info("✅ Яндекс канал: УСПЕХ")
            else:
                logger.error("❌ Яндекс канал: НЕУДАЧА")
            
            # Обновляем историю
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count == 2:
                    logger.info("🎉 УСПЕХ! Посты отправлены в ОБА канала!")
                else:
                    logger.info(f"⚠️  Частичный успех: отправлено в {success_count} из 2 каналов")
                return True
            else:
                logger.error("❌ НЕУДАЧА! Не удалось отправить ни в один канал")
                return False
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
            return False


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Отправка в ДВА Telegram канала")
    print("🎯 Каждый пост с уникальной картинкой")
    print("🎯 Gemini генерирует текст и ищет картинки")
    print("🎯 Временные слоты: утро/день/вечер")
    print("🎯 Год: 2025-2026")
    print("=" * 80)
    
    print("✅ Все переменные окружения загружены")
    
    # Создание бота
    bot = AIPostGenerator()
    
    print("\n" + "=" * 80)
    print("🚀 НАЧИНАЕМ ГЕНЕРАЦИЮ И ОТПРАВКУ ПОСТОВ...")
    print("=" * 80)
    
    try:
        success = bot.generate_and_send_posts()
        
        if success:
            print("\n" + "=" * 80)
            print("🎉 УСПЕХ! Посты успешно сгенерированы и отправлены!")
            print("=" * 80)
            print("📅 Следующий пост можно будет отправить через 3 часа")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("ℹ️  Возможные причины:")
            print("  • Проблемы с интернет-соединением")
            print("  • Ошибки API Gemini")
            print("  • Проблемы с Telegram API")
            print("  • Не удалось найти картинку")
            print("\n🔄 Попробуйте запустить снова через несколько минут")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("\n🔧 Рекомендации:")
        print("1. Проверьте переменные окружения")
        print("2. Убедитесь что бот добавлен в оба канала")
        print("3. Проверьте лимиты Gemini API")
        print("4. Убедитесь в наличии интернета")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
