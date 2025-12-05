import os
import requests
import random
import json
import time
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAIN_CHANNEL_ID = os.environ.get("MAIN_CHANNEL_ID", "@da4a_hr")
YANDEX_CHANNEL_ID = os.environ.get("YANDEX_CHANNEL_ID", "@tehdzemm")
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
        
        # Временные слоты
        self.time_slots = {
            "09:00": {
                "type": "morning",
                "name": "Утренний пост",
                "emoji": "🌅",
                "chars": "700-1000",
                "description": "Короткий, энергичный утренний стар트"
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

        # Английские ключевые слова для картинок
        self.theme_keywords = {
            "HR и управление персоналом": ["office", "team", "business", "meeting", "workplace"],
            "PR и коммуникации": ["public relations", "media", "communication", "social media", "marketing"],
            "ремонт и строительство": ["construction", "renovation", "building", "tools", "architecture"]
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
        """Генерирует пост с помощью Gemini"""
        slot_type = time_slot_info['type']
        chars_range = time_slot_info['chars']
        
        prompt = f"""Create a Telegram post in Russian on the topic: "{theme}"

Time: {time_slot_info['name']} ({time_slot_info['emoji']})
Length: {chars_range} characters
Style: {time_slot_info['description']}

Requirements:
1. Start with an engaging hook (first 2 lines)
2. Main content with useful information
3. 2-4 key points (use • symbol)
4. Question to engage audience
5. 3-5 relevant hashtags in Russian
6. Add relevant emojis
7. Year: 2025-2026
8. Do NOT use markdown or HTML formatting
9. Write in natural Russian language

Example structure:
[Engaging hook with emoji]

[Main content]

• First point
• Second point

[Engagement question]

#hashtag1 #hashtag2 #hashtag3

Theme: {theme}"""

        try:
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
                    logger.info("✅ Текст сгенерирован успешно")
                    return generated_text.strip()
            
            logger.error(f"❌ Ошибка Gemini API: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return None

    def get_unsplash_image(self, theme):
        """Получает изображение с Unsplash"""
        try:
            # Берем английские ключевые слова
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Правильное кодирование для Unsplash
            search_query = keyword.replace(' ', ',')
            
            # Формируем URL
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Варианты URL
            urls = [
                f"https://source.unsplash.com/{width}x{height}/?{search_query}&sig={timestamp}",
                f"https://source.unsplash.com/featured/{width}x{height}/?{search_query}&sig={timestamp}",
                f"https://images.unsplash.com/photo-{random.randint(1000000000, 9999999999)}?ixlib=rb-4.0.3&auto=format&fit=crop&w={width}&h={height}&q=80",
            ]
            
            for url in urls:
                try:
                    logger.info(f"🔍 Поиск картинки: {url[:80]}...")
                    
                    # Пробуем получить изображение
                    response = requests.get(url, timeout=10, stream=True)
                    
                    if response.status_code == 200:
                        # Проверяем что это изображение
                        content_type = response.headers.get('content-type', '')
                        if 'image' in content_type:
                            # Получаем финальный URL
                            final_url = response.url
                            logger.info(f"✅ Картинка найдена: {final_url}")
                            return final_url
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"URL недоступен: {e}")
                    continue
            
            # Fallback
            fallback_url = f"https://source.unsplash.com/{width}x{height}/?business&sig={timestamp}"
            logger.warning(f"🔄 Используем fallback картинку")
            return fallback_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return None

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        # Удаляем HTML/XML теги
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
        
        # Обрезаем если слишком длинный
        if len(text) > 4096:
            cutoff = text[:4000].rfind('\n')
            if cutoff > 3500:
                text = text[:cutoff] + "\n\n..."
            else:
                text = text[:4000] + "..."
        
        return text.strip()

    def test_bot_access(self):
        """Проверяет доступ бота к каналам"""
        logger.info("🔍 Проверка доступа бота к каналам...")
        
        channels = [
            (MAIN_CHANNEL_ID, "Основной канал"),
            (YANDEX_CHANNEL_ID, "Яндекс канал")
        ]
        
        for channel_id, channel_name in channels:
            try:
                # Проверяем информацию о чате
                response = requests.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
                    params={"chat_id": channel_id},
                    timeout=10
                )
                
                if response.status_code == 200:
                    chat_info = response.json()
                    logger.info(f"✅ {channel_name}: доступ есть")
                    logger.info(f"   Название: {chat_info.get('result', {}).get('title', 'N/A')}")
                else:
                    logger.error(f"❌ {channel_name}: нет доступа. Код: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки {channel_name}: {e}")
        
        # Проверяем информацию о боте
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
                timeout=10
            )
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"🤖 Бот: {bot_info.get('result', {}).get('username', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")

    def send_telegram_photo(self, chat_id, photo_url, caption=""):
        """Отправляет фото в Telegram"""
        try:
            # Очищаем caption
            clean_caption = self.clean_telegram_text(caption)
            if len(clean_caption) > 1024:
                clean_caption = clean_caption[:1000] + "..."
            
            # Параметры для отправки
            params = {
                'chat_id': chat_id,
                'photo': photo_url,
            }
            
            if clean_caption:
                params['caption'] = clean_caption
            
            # Отправляем запрос
            logger.info(f"📤 Отправка фото в {chat_id}...")
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                params=params,
                timeout=30
            )
            
            result = response.json() if response.content else {}
            
            if response.status_code == 200:
                logger.info(f"✅ Фото отправлено в {chat_id}")
                return True
            else:
                logger.error(f"❌ Ошибка отправки фото в {chat_id}: {response.status_code}")
                
                # Пробуем без caption
                if clean_caption:
                    logger.info("🔄 Пробуем без caption...")
                    params.pop('caption', None)
                    
                    response2 = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        params=params,
                        timeout=30
                    )
                    
                    if response2.status_code == 200:
                        logger.info(f"✅ Фото отправлено (без caption) в {chat_id}")
                        
                        # Отправляем текст отдельно
                        text_params = {
                            'chat_id': chat_id,
                            'text': clean_caption,
                            'disable_web_page_preview': True
                        }
                        
                        text_response = requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            params=text_params,
                            timeout=30
                        )
                        
                        if text_response.status_code == 200:
                            logger.info(f"✅ Текст отправлен отдельно в {chat_id}")
                            return True
                
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при отправке фото: {e}")
            return False

    def send_telegram_message(self, chat_id, text):
        """Отправляет текстовое сообщение"""
        try:
            clean_text = self.clean_telegram_text(text)
            
            if not clean_text:
                return False
            
            params = {
                'chat_id': chat_id,
                'text': clean_text,
                'disable_web_page_preview': True
            }
            
            logger.info(f"📤 Отправка текста в {chat_id}...")
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Текст отправлен в {chat_id}")
                return True
            else:
                result = response.json() if response.content else {}
                logger.error(f"❌ Ошибка отправки текста: {response.status_code}")
                logger.error(f"   Ответ: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при отправке текста: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            # Сначала проверяем доступ
            self.test_bot_access()
            
            # Проверка интервала
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
            
            # Генерация поста
            logger.info("🧠 Генерация поста...")
            post_text = self.generate_post_with_gemini(self.current_theme, time_slot_info)
            
            if not post_text:
                # Fallback текст
                post_text = f"""{time_slot_info['emoji']} {time_slot_info['name']}: {self.current_theme}

Обсуждаем актуальные вопросы {self.current_theme.lower()}!

• Важный аспект 1
• Ключевой момент 2
• Полезный инсайт 3

Как вы относитесь к этой теме? Ждем ваше мнение в комментариях!

#{self.current_theme.replace(' ', '').replace('и', '')} #новости #тренды2025"""
            
            logger.info(f"📊 Длина поста: {len(post_text)} знаков")
            
            # Поиск картинки
            logger.info("🖼️ Поиск картинки...")
            image_url = self.get_unsplash_image(self.current_theme)
            
            if not image_url:
                logger.warning("⚠️ Картинка не найдена, будет только текст")
            
            # Отправка
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку постов...")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал
            if image_url:
                main_success = self.send_telegram_photo(MAIN_CHANNEL_ID, image_url, post_text)
            else:
                main_success = self.send_telegram_message(MAIN_CHANNEL_ID, post_text)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной канал: УСПЕХ")
            else:
                logger.error("❌ Основной канал: НЕУДАЧА")
            
            time.sleep(2)
            
            # Яндекс канал (немного другой текст)
            yandex_post = f"📰 {post_text}"
            
            if image_url:
                yandex_success = self.send_telegram_photo(YANDEX_CHANNEL_ID, image_url, yandex_post)
            else:
                yandex_success = self.send_telegram_message(YANDEX_CHANNEL_ID, yandex_post)
            
            if yandex_success:
                success_count += 1
                logger.info("✅ Яндекс канал: УСПЕХ")
            else:
                logger.error("❌ Яндекс канал: НЕУДАЧА")
            
            # Сохранение результата
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
    print("🎯 Каждый пост с картинкой из интернета")
    print("🎯 Gemini генерирует уникальный текст")
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
            print("🎉 УСПЕХ! Посты успешно отправлены!")
            print("=" * 80)
            print("📅 Следующий пост через 3 часа")
        else:
            print("\n" + "=" * 80)
            print("⚠️  ВНИМАНИЕ: Не удалось отправить посты")
            print("=" * 80)
            print("🔧 Диагностика:")
            print("1. Проверьте что бот - админ в каналах")
            print("2. Убедитесь что каналы публичные")
            print("3. Проверьте BOT_TOKEN")
            print("4. Убедитесь в наличии интернета")
            print("\n🔄 Попробуйте запустить снова")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
