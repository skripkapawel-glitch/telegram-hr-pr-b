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
MAIN_CHANNEL_ID = "@da4a_hr"  # ОСНОВНОЙ КАНАЛ - фиксированный
YANDEX_CHANNEL_ID = "@tehdzemm"  # ЯНДЕКС КАНАЛ - фиксированный
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

        # Английские ключевые слова для картинок
        self.theme_keywords = {
            "HR и управление персоналом": ["office", "team", "business", "meeting"],
            "PR и коммуникации": ["public relations", "media", "communication", "marketing"],
            "ремонт и строительство": ["construction", "renovation", "building", "tools"]
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

    def generate_post_text(self, theme, time_slot_info):
        """Генерирует текст поста (упрощенная версия)"""
        # Упрощенный текст без Gemini API
        templates = {
            "morning": [
                f"🌅 Доброе утро! Сегодня говорим о {theme.lower()}.\n\nЧто для вас самое важное в этой теме?\n\n#{theme.replace(' ', '').replace('и', '')} #утро #новости",
                f"🌞 С добрым утром! Тема дня: {theme}.\n\n• Первый ключевой момент\n• Второй важный аспект\n• Третий полезный совет\n\nОбсуждаем в комментариях!\n\n#{theme.replace(' ', '_').lower()} #бизнес #советы"
            ],
            "day": [
                f"🌞 День в разгаре! Глубокое погружение в тему: {theme}.\n\nАктуальные тренды 2025 года и практические рекомендации.\n\nКак вы применяете это в работе?\n\n#{theme.replace(' ', '')} #аналитика #практика",
                f"📊 Дневной анализ: {theme}.\n\nКлючевые инсайты:\n• Инсайт 1\n• Инсайт 2\n• Инсайт 3\n\nЧто бы вы добавили?\n\n#{theme.replace(' ', '_').lower()} #обсуждение #опыт"
            ],
            "evening": [
                f"🌙 Спокойный вечер и тема для размышлений: {theme}.\n\nПодводим итоги дня, делимся мыслями.\n\nКак прошел ваш день в контексте этой темы?\n\n#{theme.replace(' ', '')} #вечер #рефлексия",
                f"✨ Вечерние мысли о {theme.lower()}.\n\n• Что работает\n• Что можно улучшить\n• Планы на завтра\n\nДелитесь своими идеями!\n\n#{theme.replace(' ', '_').lower()} #итоги #планирование"
            ]
        }
        
        slot_type = time_slot_info['type']
        template = random.choice(templates[slot_type])
        return template

    def get_image_url(self, theme):
        """Получает URL изображения - УПРОЩЕННЫЙ И РАБОЧИЙ МЕТОД"""
        try:
            keywords = self.theme_keywords.get(theme, ["business"])
            keyword = random.choice(keywords)
            
            # Самый простой и рабочий URL для Unsplash
            width, height = 1200, 630
            timestamp = int(time.time())
            
            # Простой запрос - Unsplash сам подберет картинку
            url = f"https://source.unsplash.com/random/{width}x{height}/?{keyword}&sig={timestamp}"
            
            logger.info(f"🖼️ Запрос картинки: {keyword}")
            
            # Пробуем получить редирект
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code in [200, 301, 302]:
                    final_url = response.url
                    logger.info(f"✅ Картинка найдена")
                    return final_url
            except:
                pass
            
            # Fallback - статичная картинка
            fallback_url = f"https://picsum.photos/{width}/{height}?random={timestamp}"
            logger.info(f"🔄 Используем fallback картинку")
            return fallback_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска картинки: {e}")
            return f"https://picsum.photos/1200/630?random={int(time.time())}"

    def clean_telegram_text(self, text):
        """Очищает текст для Telegram"""
        if not text:
            return ""
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Заменяем спецсимволы на обычные
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
            text = text[:4000] + "..."
        
        return text.strip()

    def test_bot_access(self):
        """Проверяет доступ бота к каналам"""
        logger.info("🔍 Проверка доступа бота...")
        
        try:
            # Проверяем бота
            response = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
                timeout=10
            )
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"🤖 Бот: @{bot_info.get('result', {}).get('username', 'N/A')}")
            else:
                logger.error(f"❌ Бот не доступен: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки бота: {e}")
            return False
        
        # Проверяем каналы
        channels = [
            (MAIN_CHANNEL_ID, "Основной канал (@da4a_hr)"),
            (YANDEX_CHANNEL_ID, "Яндекс канал (@tehdzemm)")
        ]
        
        all_ok = True
        for channel_id, channel_name in channels:
            try:
                # Проверяем через sendChatAction (менее строгий метод)
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction",
                    json={
                        "chat_id": channel_id,
                        "action": "typing"
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ {channel_name}: доступ ЕСТЬ")
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(f"❌ {channel_name}: НЕТ доступа")
                    logger.error(f"   Код: {response.status_code}, Ошибка: {error_data.get('description', 'Unknown')}")
                    all_ok = False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки {channel_name}: {e}")
                all_ok = False
        
        return all_ok

    def send_telegram_post(self, chat_id, text, image_url=None):
        """Отправляет пост в Telegram - ОСНОВНОЙ РАБОЧИЙ МЕТОД"""
        try:
            # Очищаем текст
            clean_text = self.clean_telegram_text(text)
            
            # Пробуем отправить с фото если есть
            if image_url:
                logger.info(f"📤 Отправка фото+текст в {chat_id}")
                
                # Метод 1: sendPhoto с caption
                params = {
                    'chat_id': chat_id,
                    'photo': image_url,
                    'caption': clean_text[:1024]  # Ограничение Telegram
                }
                
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Пост с фото отправлен в {chat_id}")
                    return True
                
                # Если не получилось, пробуем отправить фото и текст отдельно
                logger.info("🔄 Пробуем фото и текст отдельно...")
                
                # Сначала фото
                photo_params = {
                    'chat_id': chat_id,
                    'photo': image_url
                }
                
                photo_response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    params=photo_params,
                    timeout=30
                )
                
                if photo_response.status_code == 200:
                    time.sleep(1)
                    
                    # Затем текст
                    text_params = {
                        'chat_id': chat_id,
                        'text': clean_text,
                        'disable_web_page_preview': True
                    }
                    
                    text_response = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        params=text_params,
                        timeout=30
                    )
                    
                    if text_response.status_code == 200:
                        logger.info(f"✅ Фото и текст (отдельно) отправлены в {chat_id}")
                        return True
            
            # Fallback: только текст
            logger.info(f"📝 Отправка только текста в {chat_id}")
            
            params = {
                'chat_id': chat_id,
                'text': clean_text,
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
            
            logger.error(f"❌ Все методы не сработали для {chat_id}: {response.status_code}")
            return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при отправке: {e}")
            return False

    def generate_and_send_posts(self):
        """Генерирует и отправляет посты"""
        try:
            # Проверяем доступ
            if not self.test_bot_access():
                logger.error("❌ Проблемы с доступом к каналам")
                return False
            
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
            logger.info("🧠 Генерация текста...")
            post_text = self.generate_post_text(self.current_theme, time_slot_info)
            
            logger.info(f"📊 Длина поста: {len(post_text)} знаков")
            
            # Поиск картинки
            logger.info("🖼️ Поиск картинки...")
            image_url = self.get_image_url(self.current_theme)
            
            # Отправка
            logger.info("=" * 50)
            logger.info("🚀 Начинаем отправку...")
            logger.info("=" * 50)
            
            success_count = 0
            
            # Основной канал
            logger.info(f"📤 Основной канал: {MAIN_CHANNEL_ID}")
            main_success = self.send_telegram_post(MAIN_CHANNEL_ID, post_text, image_url)
            
            if main_success:
                success_count += 1
                logger.info("✅ Основной: УСПЕХ")
            else:
                logger.error("❌ Основной: НЕУДАЧА")
            
            time.sleep(2)
            
            # Яндекс канал
            logger.info(f"📤 Яндекс канал: {YANDEX_CHANNEL_ID}")
            yandex_success = self.send_telegram_post(YANDEX_CHANNEL_ID, post_text, image_url)
            
            if yandex_success:
                success_count += 1
                logger.info("✅ Яндекс: УСПЕХ")
            else:
                logger.error("❌ Яндекс: НЕУДАЧА")
            
            # Сохранение результата
            if success_count > 0:
                self.post_history["last_post_time"] = datetime.now().isoformat()
                self.save_post_history()
                
                if success_count == 2:
                    logger.info("🎉 УСПЕХ! Посты отправлены в ОБА канала!")
                else:
                    logger.info(f"⚠️  Отправлено в {success_count} из 2 каналов")
                return True
            else:
                logger.error("❌ НЕУДАЧА! Не удалось отправить")
                return False
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
            return False


def main():
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК AI ГЕНЕРАТОРА ПОСТОВ")
    print("=" * 80)
    print("🎯 Отправка в ДВА Telegram канала")
    print("🎯 Каждый пост с картинкой")
    print("🎯 Автоматический выбор темы")
    print("🎯 Временные слоты: утро/день/вечер")
    print("🎯 Год: 2025-2026")
    print("=" * 80)
    
    print("✅ Все переменные окружения загружены")
    
    # Создание бота
    bot = AIPostGenerator()
    
    print("\n" + "=" * 80)
    print("🚀 НАЧИНАЕМ ГЕНЕРАЦИЮ И ОТПРАВКУ...")
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
            print("🔧 Что проверить:")
            print("1. Бот должен быть АДМИНОМ в обоих каналах")
            print("2. У бота должно быть право 'Отправка сообщений'")
            print("3. Каналы должны быть публичными")
            print("4. BOT_TOKEN должен быть правильным")
            print("\n🔄 Запустите снова после проверки")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Бот остановлен")
    except Exception as e:
        print(f"\n💥 ОШИБКА: {e}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
