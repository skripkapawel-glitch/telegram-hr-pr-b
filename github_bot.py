# github_bot.py - Telegram бот для автоматической публикации постов
import os
import requests
import random
import json
import time
import logging
import re
import sys
import argparse
from datetime import datetime, timedelta
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
MAIN_CHANNEL_ID = os.environ.get("CHANNEL_ID", "@da4a_hr")
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# Проверка критических переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)
if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY не установлен!")
    sys.exit(1)
if not PEXELS_API_KEY:
    logger.error("❌ PEXELS_API_KEY не установлен! Обязательно получи ключ на pexels.com/api")
    sys.exit(1)

# Используем стабильную модель Gemini
GEMINI_MODEL = "gemini-1.5-pro-latest"

# Система согласования отключена - прямая публикация в каналы
logger.info("📤 Режим: прямая публикация в каналы")

# Настройка сессии
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
})

print("=" * 80)
print("🚀 ТЕЛЕГРАМ БОТ: АВТОПИЛОТ С ПРЯМОЙ ПУБЛИКАЦИЕЙ")
print("=" * 80)
print(f"✅ BOT_TOKEN: Установен")
print(f"✅ GEMINI_API_KEY: Установен")
print(f"✅ PEXELS_API_KEY: Установен")
print(f"🤖 Используется модель: {GEMINI_MODEL}")
print(f"📢 Основной канал: {MAIN_CHANNEL_ID}")
print(f"📢 Канал для Дзен: {ZEN_CHANNEL_ID}")
print(f"📋 Режим: 📤 ПРЯМАЯ ПУБЛИКАЦИЯ В КАНАЛЫ")
if ADMIN_CHAT_ID:
    print(f"👨‍💼 Уведомления для: {ADMIN_CHAT_ID}")
print("\n⏰ РАСПИСАНИЕ ПУБЛИКАЦИЙ (МСК):")
print("   • 09:00 - Утренний пост (TG: 400-600, Дзен: 600-700)")
print("   • 14:00 - Дневной пост (TG: 700-900, Дзен: 700-900)")
print("   • 19:00 - Вечерний пост (TG: 600-900, Дзен: 700-800)")
print("=" * 80)

class TelegramBot:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        self.history_file = "post_history.json"
        self.post_history = self.load_history()
        self.image_history_file = "image_history.json"
        self.image_history = self.load_image_history()
        
        # 19 форматов подачи текста
        self.text_formats = [
            "разбор ситуации", "микро-исследование", "аналитическое наблюдение",
            "разбор ошибки", "мини-история", "взгляд автора",
            "объяснение простым языком", "сторителлинг", "структурированные советы",
            "аналогия", "демонстрация пользы", "анализ поведения аудитории",
            "причинно-следственные связи", "цепочка «факт → пример → вывод»",
            "список шагов", "инсайт", "тихая эмоциональная подача",
            "сравнение подходов", "мини-обобщение опыта"
        ]
        
        # Хэштеги по темам
        self.hashtags_by_theme = {
            "HR и управление персоналом": [
                "#HR", "#управлениеперсоналом", "#рекрутинг", "#кадры",
                "#команда", "#лидерство", "#мотивация", "#развитиеперсонала",
                "#бизнес", "#управление", "#работа", "#карьера"
            ],
            "PR и коммуникации": [
                "#PR", "#коммуникации", "#маркетинг", "#продвижение",
                "#брендинг", "#соцсети", "#медиа", "#пиар",
                "#общение", "#публичность", "#репутация", "#инфоповод"
            ],
            "ремонт и строительство": [
                "#ремонт", "#строительство", "#дизайн", "#интерьер",
                "#ремонтквартир", "#строитель", "#отделка", "#ремонтдома",
                "#стройматериалы", "#проект", "#ремонтподключ", "#евроремонт"
            ]
        }
        
        # Стили по времени публикации
        self.time_styles = {
            "09:00": {
                "name": "Утренний пост", "type": "morning", "emoji": "🌅",
                "style": "мотивация, фокус, энерго-старт",
                "allowed_formats": ["советы", "объяснение простым языком", "демонстрация пользы", "сравнение подходов", "тихая эмоциональная подача", "цепочка «факт → пример → вывод»"],
                "tg_chars": (400, 600), "zen_chars": (600, 700)
            },
            "14:00": {
                "name": "Дневной пост", "type": "day", "emoji": "🌞",
                "style": "аналитика, рациональность, польза",
                "allowed_formats": ["аналитическое наблюдение", "микро-исследование", "разбор ошибки", "анализ поведения аудитории", "причинно-следственные связи", "список шагов", "инсайт"],
                "tg_chars": (700, 900), "zen_chars": (700, 900)
            },
            "19:00": {
                "name": "Вечерний пост", "type": "evening", "emoji": "🌙",
                "style": "истории, личные выводы, рефлексия",
                "allowed_formats": ["мини-история", "взгляд автора", "сторителлинг", "аналогия", "проживание опыта", "глубокая тема"],
                "tg_chars": (600, 900), "zen_chars": (700, 800)
            }
        }
        
        # Мягкие финалы
        self.soft_finals = [
            "А как вы считаете?", "Было ли у вас так?", "Что думаете?",
            "Согласны с этим?", "Какой у вас опыт?", "Как бы вы поступили?",
            "Есть что добавить?"
        ]
        
        self.current_theme = None
        self.current_format = None
        self.current_style = None

    # ... [Здесь остаются все вспомогательные методы из предыдущего кода без изменений:
    # load_history, save_history, get_moscow_time, was_slot_sent_today,
    # mark_slot_as_sent, get_smart_theme, get_smart_format, get_relevant_hashtags,
    # get_soft_final, create_master_prompt, clean_generated_text,
    # _force_cut_text, parse_generated_texts, get_post_image_and_description,
    # format_telegram_text, format_zen_text, publish_directly,
    # send_admin_notification, send_telegram_post, run_once_mode, run_test_mode]
    # Опускаем для краткости, но в рабочем коде они должны быть.

    def generate_with_gemini(self, prompt, max_attempts=3):
        """Генерация текста через Gemini API с правильным форматом запроса"""
        for attempt in range(max_attempts):
            try:
                logger.info(f"🤖 Попытка {attempt+1}/{max_attempts} к Gemini API")
                
                # АКТУАЛЬНЫЙ URL и структура запроса для Gemini API
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                
                # ПРАВИЛЬНЫЙ JSON для Gemini API
                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topP": 0.8,
                        "topK": 40,
                        "maxOutputTokens": 2048,
                    }
                }
                
                headers = {
                    'Content-Type': 'application/json'
                }
                
                response = session.post(url, json=data, headers=headers, timeout=60)
                
                # ДЕТАЛЬНАЯ ОБРАБОТКА ОТВЕТА
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Gemini API вернул успешный ответ")
                    
                    # Извлекаем текст из ответа API
                    if 'candidates' in result and result['candidates']:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            generated_text = candidate['content']['parts'][0]['text']
                            logger.info(f"📝 Текст успешно извлечен, длина: {len(generated_text)} символов")
                            return generated_text.strip()
                        else:
                            logger.warning(f"⚠️ Неожиданная структура 'content' в ответе: {result}")
                    else:
                        logger.warning(f"⚠️ Нет candidates в ответе API: {result}")
                
                # Логирование ошибок API
                else:
                    logger.error(f"❌ Ошибка Gemini API: {response.status_code}")
                    logger.error(f"Ответ сервера: {response.text[:200]}")
                    
                    if response.status_code == 429:
                        logger.warning("⏸️ Слишком много запросов, жду 10 секунд...")
                        time.sleep(10)
                        continue
                    elif response.status_code == 400:
                        logger.error("🔧 Неверный запрос к API. Проверьте параметры.")
                        break
                
            except requests.exceptions.Timeout:
                logger.error(f"⏱️ Таймаут при попытке {attempt+1}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
            except requests.exceptions.ConnectionError:
                logger.error(f"🌐 Ошибка соединения при попытке {attempt+1}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
            except Exception as e:
                logger.error(f"💥 Неожиданная ошибка при генерации: {e}")
                import traceback
                logger.error(traceback.format_exc())
                if attempt < max_attempts - 1:
                    time.sleep(2)
        
        logger.error("❌ Все попытки генерации через Gemini провалились")
        return None

    def generate_with_retry(self, prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=3):
        """Генерация постов с повторными попытками - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        for attempt in range(max_attempts):
            try:
                logger.info(f"🔄 Попытка {attempt+1}/{max_attempts}: генерация обоих постов")
                
                # Генерация через Gemini
                generated_text = self.generate_with_gemini(prompt)
                
                if not generated_text:
                    logger.warning("⚠️ Gemini не вернул текст, пробуем снова...")
                    continue
                
                # Парсим оба текста
                tg_text, zen_text = self.parse_generated_texts(generated_text, tg_min, tg_max, zen_min, zen_max)
                
                if tg_text and zen_text:
                    # Проверяем финальную длину
                    tg_final_len = len(tg_text)
                    zen_final_len = len(zen_text)
                    
                    if tg_min <= tg_final_len <= tg_max and zen_min <= zen_final_len <= zen_max:
                        logger.info(f"✅ Оба поста соответствуют длине")
                        logger.info(f"   Telegram: {tg_final_len} символов ({tg_min}-{tg_max} ✅)")
                        logger.info(f"   Дзен: {zen_final_len} символов ({zen_min}-{zen_max} ✅)")
                        return tg_text, zen_text
                    else:
                        logger.warning(f"⚠️ Длины не соответствуют: TG={tg_final_len}, Дзен={zen_final_len}")
                
                # Пауза перед следующей попыткой
                if attempt < max_attempts - 1:
                    wait_time = 2 * (attempt + 1)
                    logger.info(f"⏸️ Жду {wait_time} секунд перед следующей попыткой...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в generate_with_retry: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(3)
        
        # АВАРИЙНЫЙ РЕЖИМ: создаем минимальные посты
        logger.warning("🆘 Переходим в аварийный режим - создаем минимальные посты")
        
        theme = self.current_theme or "HR и управление персоналом"
        hashtags = self.get_relevant_hashtags(theme, 3)
        hashtags_str = ' '.join(hashtags)
        soft_final = self.get_soft_final()
        
        # Минимальный Telegram пост
        tg_emergency = f"🌙 {theme}\n\nПоговорим сегодня на важную тему. Актуально для каждого.\n\nПрактические советы всегда помогают.\n\n{soft_final}\n\n{hashtags_str}"
        
        # Минимальный Дзен пост
        zen_emergency = f"{theme}\n\nЭта тема заслуживает внимания. Многие сталкиваются с подобными вопросами.\n\nПонимание процессов дает преимущество. Реальные кейсы показывают эффективность.\n\nПравильный подход меняет результат.\n\n{soft_final}\n\n{hashtags_str}"
        
        # Подгоняем длину
        if len(tg_emergency) > tg_max:
            tg_emergency = self._force_cut_text(tg_emergency, tg_max)
        if len(zen_emergency) > zen_max:
            zen_emergency = self._force_cut_text(zen_emergency, zen_max)
        
        logger.info(f"🆘 Используем аварийные посты: TG={len(tg_emergency)} симв, Дзен={len(zen_emergency)} симв")
        return tg_emergency, zen_emergency

    def create_and_send_posts(self, slot_time, slot_style, is_test=False, force_send=False):
        """Генерирует и отправляет посты - ОСНОВНАЯ ФУНКЦИЯ"""
        try:
            logger.info(f"\n🎬 Начинаем создание поста для {slot_time} - {slot_style['name']}")
            logger.info(f"🎨 Стиль: {slot_style['style']}")
            logger.info(f"📏 Лимиты: Telegram {slot_style['tg_chars'][0]}-{slot_style['tg_chars'][1]}, Дзен {slot_style['zen_chars'][0]}-{slot_style['zen_chars'][1]}")
            
            if not force_send and not is_test and self.was_slot_sent_today(slot_time):
                logger.info(f"⏭️ Слот {slot_time} уже был отправлен сегодня, пропускаем")
                return True
            
            theme = self.get_smart_theme()
            text_format = self.get_smart_format(slot_style)
            self.current_style = slot_style
            
            logger.info(f"🎯 Тема: {theme}")
            logger.info(f"📝 Формат подачи: {text_format}")
            
            tg_min, tg_max = slot_style['tg_chars']
            zen_min, zen_max = slot_style['zen_chars']
            
            logger.info("🖼️ Подбираем картинку...")
            image_url, image_description = self.get_post_image_and_description(theme)
            
            logger.info("\n📝 СОЗДАНИЕ МАСТЕР-ПРОМПТА")
            master_prompt = self.create_master_prompt(theme, slot_style, text_format, image_description)
            
            # Логируем промпт для отладки (первые 500 символов)
            logger.debug(f"Промпт для Gemini:\n{master_prompt[:500]}...")
            
            logger.info("\n🤖 ГЕНЕРАЦИЯ ОБОИХ ПОСТОВ ЧЕРЕЗ GEMINI API")
            tg_text, zen_text = self.generate_with_retry(master_prompt, tg_min, tg_max, zen_min, zen_max, max_attempts=3)
            
            if not tg_text or not zen_text:
                logger.error("❌ Критическая ошибка: не удалось получить тексты постов")
                return False
            
            tg_formatted = self.format_telegram_text(tg_text, slot_style)
            zen_formatted = self.format_zen_text(zen_text, slot_style)
            
            if not tg_formatted or not zen_formatted:
                logger.error("❌ Один из текстов не прошел проверку формата")
                return False
            
            tg_length = len(tg_formatted)
            zen_length = len(zen_formatted)
            
            # ФИНАЛЬНАЯ ПРОВЕРКА
            logger.info(f"\n🔴 ФИНАЛЬНАЯ ПРОВЕРКА:")
            
            tg_ok = tg_min <= tg_length <= tg_max
            zen_ok = zen_min <= zen_length <= zen_max
            
            logger.info(f"   Telegram: {tg_length} символов ({tg_min}-{tg_max}) {'✅' if tg_ok else '❌'}")
            logger.info(f"   Дзен: {zen_length} символов ({zen_min}-{zen_max}) {'✅' if zen_ok else '❌'}")
            
            if not tg_ok or not zen_ok:
                logger.error("❌ Тексты не соответствуют лимитам")
                return False
            
            if not is_test:
                logger.info("📤 ПУБЛИКУЮ ПОСТЫ НАПРЯМУЮ В КАНАЛЫ")
                success_count = self.publish_directly(slot_time, tg_formatted, zen_formatted, image_url, theme)
            else:
                logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ - публикация пропущена")
                success_count = 1
            
            if success_count >= 1 and not is_test:
                self.mark_slot_as_sent(slot_time)
                logger.info(f"📝 Информация сохранена в историю")
            
            if success_count >= 1:
                logger.info(f"\n🎉 УСПЕХ! Отправлено постов: {success_count}/2")
                logger.info(f"   🕒 Время: {slot_time} МСК")
                logger.info(f"   🎨 Стиль: {slot_style['style']}")
                logger.info(f"   🎯 Тема: {theme} (ротация активна)")
                logger.info(f"   📝 Формат: {text_format}")
                logger.info(f"   📏 Telegram: {tg_length} символов ({tg_min}-{tg_max} ✅)")
                logger.info(f"   📏 Дзен: {zen_length} символов ({zen_min}-{zen_max} ✅)")
                logger.info(f"   🤖 Модель: {GEMINI_MODEL}")
                logger.info(f"   🖼️ Картинка: {image_description[:80]}...")
                return True
            else:
                logger.error(f"❌ Не удалось отправить ни одного поста")
                return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка в create_and_send_posts: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """Главная функция запуска"""
    
    parser = argparse.ArgumentParser(description='Телеграм бот для автоматической публикации постов')
    parser.add_argument('--test', '-t', action='store_true', help='Тестовый режим')
    parser.add_argument('--once', '-o', action='store_true', help='Однократный запуск (для GitHub Actions)')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕЛЕГРАМ БОТА")
    print("=" * 80)
    
    bot = TelegramBot()
    
    if args.once:
        print("📝 РЕЖИМ: Однократный запуск (GitHub Actions)")
        bot.run_once_mode()
    elif args.test:
        print("📝 РЕЖИМ: Тестирование")
        bot.run_test_mode()
    else:
        print("\nСПОСОБЫ ЗАПУСКА:")
        print("python github_bot.py --once   # Для GitHub Actions")
        print("python github_bot.py --test   # Тестирование")
        print(f"🤖 Используемая модель: {GEMINI_MODEL}")
        print("\nДЛЯ GITHUB ACTIONS: python github_bot.py --once")
        print("=" * 80)
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("🏁 РАБОТА ЗАВЕРШЕНА")
    print("=" * 80)

if __name__ == "__main__":
    main()
