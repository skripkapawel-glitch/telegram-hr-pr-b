import os
import requests
import random
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_CHANNEL_ID = "@da4a_hr"
ZEN_CHANNEL_ID = "@tehdzenm"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 80)
print("🚀 УМНЫЙ БОТ: AI-ГЕНЕРАЦИЯ С ПРОВЕРКОЙ УНИКАЛЬНОСТИ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        self.current_theme = None
        
        # Расширенные коллекции изображений для каждой темы
        self.theme_images = {
            "HR и управление персоналом": [
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1573164713714-d95e436ab290?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1551836026-d5c2e0c49b61?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1556761175-b413da4baf72?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "PR и коммуникации": [
                "https://images.unsplash.com/photo-1432888622747-4eb9a8efeb07?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1551836026-d5c2e0c49b61?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "ремонт и строительство": [
                "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1541976590-713941681591?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1541976590-713941681591?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1541976590-713941681591?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1541976590-713941681591?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ]
        }
        
        self.fallback_images = [
            "https://picsum.photos/1200/630",
            "https://placekitten.com/1200/630",
        ]

    def load_post_history(self):
        """Загружает историю постов и использованных изображений"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Инициализируем структуру для изображений если её нет
                    if "used_images" not in data:
                        data["used_images"] = {}
                    return data
            return {"posts": {}, "themes": {}, "used_images": {}}
        except:
            return {"posts": {}, "themes": {}, "used_images": {}}
    
    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")
    
    def get_last_themes(self, channel_id, count=3):
        channel_key = str(channel_id)
        themes = self.post_history.get("themes", {}).get(channel_key, [])
        return themes[-count:] if len(themes) >= count else themes
    
    def add_theme_to_history(self, channel_id, theme):
        channel_key = str(channel_id)
        
        if "themes" not in self.post_history:
            self.post_history["themes"] = {}
        if channel_key not in self.post_history["themes"]:
            self.post_history["themes"][channel_key] = []
        
        self.post_history["themes"][channel_key].append(theme)
        if len(self.post_history["themes"][channel_key]) > 10:
            self.post_history["themes"][channel_key] = self.post_history["themes"][channel_key][-10:]
        
        self.save_post_history()

    def get_unique_image(self, theme):
        """Возвращает уникальное изображение для темы, которое не использовалось недавно"""
        available_images = self.theme_images.get(theme, []) + self.fallback_images
        
        if not available_images:
            return random.choice(self.fallback_images)
        
        # Получаем историю использованных изображений для темы
        theme_key = theme
        if "used_images" not in self.post_history:
            self.post_history["used_images"] = {}
        if theme_key not in self.post_history["used_images"]:
            self.post_history["used_images"][theme_key] = []
        
        used_images = self.post_history["used_images"][theme_key]
        
        # Фильтруем изображения, которые не использовались в последних 10 постах
        recent_used = used_images[-10:] if len(used_images) >= 10 else used_images
        available_images = [img for img in available_images if img not in recent_used]
        
        # Если все изображения использовались, сбрасываем историю для этой темы
        if not available_images:
            print(f"🔄 Все изображения для темы '{theme}' использовались, сбрасываем историю")
            available_images = self.theme_images.get(theme, []) + self.fallback_images
            self.post_history["used_images"][theme_key] = []
        
        selected_image = random.choice(available_images)
        
        # Добавляем выбранное изображение в историю
        self.post_history["used_images"][theme_key].append(selected_image)
        if len(self.post_history["used_images"][theme_key]) > 20:  # Ограничиваем историю
            self.post_history["used_images"][theme_key] = self.post_history["used_images"][theme_key][-10:]
        
        self.save_post_history()
        print(f"🖼️ Выбрано уникальное изображение: {selected_image}")
        return selected_image
    
    def get_smart_theme(self, channel_id):
        last_themes = self.get_last_themes(channel_id, 2)
        
        available_themes = self.themes.copy()
        
        if last_themes:
            last_theme = last_themes[-1]
            if last_theme in available_themes:
                available_themes.remove(last_theme)
                print(f"🎯 Исключили последнюю тему: {last_theme}")
        
        if not available_themes:
            available_themes = self.themes.copy()
        
        theme = random.choice(available_themes)
        print(f"🎯 Выбрана тема: {theme} (история: {last_themes})")
        return theme

    def generate_with_gemini(self, prompt):
        try:
            print("🧠 Запрос к Gemini API...")
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            response = requests.post(
                url,
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "maxOutputTokens": 800,
                        "temperature": 0.9,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                generated_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print("✅ Текст сгенерирован")
                return generated_text
            else:
                print(f"❌ Ошибка Gemini: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            return None

    def generate_tg_post(self, theme):
        prompt = f"""
        Напиши пост для Telegram на тему "{theme}" за 2024-2025 год.

        Требования:
        - Пиши как настоящий человек
        - Будь профессионален, но естественен
        - Избегай клише и корпоративного жаргона
        - Используй символ • для разделения пунктов
        - Каждый пункт с новой строки
        - Пост должен содержать:
          1. Цепляющий заголовок
          2. 2-3 актуальных факта или тренда (через •)
          3. Раздел "Что работает сейчас:" с 3 пунктами
          4. Вопрос для вовлечения аудитории
        - Длина: 400-600 символов
        - Говори о реальных кейсах

        Тема: {theme}
        """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            formatted_text = self.format_tg_post(generated_text)
            hashtags = self.add_tg_hashtags(theme)
            return f"{formatted_text}\n\n{hashtags}"
        else:
            return self.generate_fallback_tg_post(theme)

    def format_tg_post(self, text):
        """Форматирует пост для Telegram с правильными отступами как в Word"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Добавляем отступ как в Word (4 пробела) для пунктов с •
                if line.startswith('•'):
                    line = f"    {line}"  # 4 пробела - аналог Tab в Word
                # Добавляем пустую строку перед разделами
                elif any(keyword in line.lower() for keyword in ['что работает', 'советы:', 'рекомендации:']):
                    if formatted_lines:  # Добавляем отступ только если уже есть контент
                        formatted_lines.append('')
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_zen_post(self, theme):
        prompt = f"""
        Напиши структурированный пост для Яндекс.Дзен на тему "{theme}" за 2024-2025 год.

        Требования:
        - Стиль: профессиональная аналитика, но человеческим языком
        - Четкая структура с подзаголовками
        - Без корпоративного жаргона
        - Конкретные примеры и цифры
        - Без эмодзи и хештегов
        - Используй символ • для визуального разделения пунктов
        - Каждый пункт должен быть законченным предложением с точкой
        - Пост должен содержать:
          1. Заголовок
          2. Введение с актуальными данными
          3. Раздел "Ключевые направления:" 
          4. 3 пункта с символом • и конкретными рекомендациями
        - Длина: 600-900 символов

        Тема: {theme}
        """
        
        generated_text = self.generate_with_gemini(prompt)
        
        if generated_text:
            return self.format_zen_post(generated_text)
        else:
            return self.generate_fallback_zen_post(theme)

    def format_zen_post(self, text):
        """Форматирует пост для Дзена с правильными отступами"""
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                # Добавляем отступ как в Word (4 пробела) для пунктов с •
                if line.startswith('•'):
                    line = f"    {line}"  # 4 пробела - аналог Tab в Word
                # Добавляем пустую строку перед ключевыми разделами
                elif any(keyword in line.lower() for keyword in ['ключевые направления', 'основные тренды', 'рекомендации:']):
                    if formatted_lines:  # Добавляем отступ только если уже есть контент
                        formatted_lines.append('')
                
                # Добавляем точку в конец предложения если нужно
                if not line.endswith(('.', '!', '?')) and len(line.split()) > 3:
                    line = line + '.'
                    
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def generate_fallback_tg_post(self, theme):
        """Резервные посты для Telegram с улучшенным форматированием"""
        fallbacks = {
            "HR и управление персоналом": [
                """HR в 2024: нанимают не навыки, а mindset

    • 78% компаний ищут кандидатов с эмоциональным интеллектом
    • AI обрабатывает 65% резюме

Что работает сейчас:

    • Смотрите на soft skills — технике научить проще
    • Внедрите пробный день вместо собеседований  
    • Давайте фидбек даже отказанным кандидатам

Что сработало в вашей практике?

#HR #управление #команда""",
                
                """Как удерживать команду в 2024

    • 68% сотрудников ценят обучение выше зарплаты
    • Гибкий график стал стандартом

Что работает сейчас:

    • Создайте карту развития для каждой позиции
    • Разрешите работать над личными проектами
    • Проводите встречи о целях, а не задачах

Как мотивируете команду?

#HR #управление #развитие"""
            ],
            
            "PR и коммуникации": [
                """PR в 2024: что реально работает

    • LinkedIn стал главной B2B-площадкой
    • Короткие видео +300% к вовлеченности

Что работает сейчас:

    • Делайте личный бренд руководителей
    • Снимите 30-секундное видео вместо пресс-релиза
    • Дайте эксперту пообщаться в комментариях

Какие тренды пробовали?

#PR #коммуникации #LinkedIn""",
                
                """Коммуникации, которые доходят до людей

    • 45% используют AI для материалов
    • Микро-инфлюенсерам доверяют больше

Что работает сейчас:

    • Говорите на языке клиента
    • Показывайте закулисье проектов
    • Отвечайте на комментарии лично

Что лучше сработало у вас?

#PR #коммуникации #бренд"""
            ],
            
            "ремонт и строительство": [
                """Ремонт в 2024: тренды, которые останутся

    • 72% выбирают натуральные материалы
    • Умный дом стал must-have

Что работает сейчас:

    • Используйте локальные материалы
    • Заложите умные системы заранее
    • Сделайте универсальную базу

Что из этого пробовали?

#ремонт #стройка #дизайн""",
                
                """Строительство без стресса в 2024 2024

    • Модульные конструкции эконом

    • Модульные конструкции экономят 40% временият 40% времени
    • Дроны экономят
    • Дроны экономят 25% бюджета

Что работает сейчас:

    • Создайте циф 25% бюджета

Что работает сейчас:

    • Создайте цифровойровой двойник объекта
 двойник объекта
    • Используйте BIM-м    • Используйте BIM-моделирование
    •оделирование
    • Ведите онлайн-днев Ведите онлайн-дневник стройки

Какник стройки

Как оптими оптимизируетезируете процессы?

#рем процессы?

#ремонт #онт #стройка #стройка #технологиитехнологии"""
            ]
        }
"""
            ]
        }
        return        return random.choice(fall random.choice(fallbacks.getbacks.get(theme, ["(theme, ["АкАктуальные трентуальные тренды 202ды 20244-2025. #трен-2025. #тренды"])ды"]))

    def generate)

    def generate_fallback_fallback_zen_post(self_zen_post(self, theme, theme):
        """):
        """РезервРезервные посты дляные посты для Дз Дзена с улучшенена с улучшенным форным форматированием"""
матированием"""
        fall        fallbacks = {
            "backs = {
            "HRHR и управление персоналом": и управление персоналом": [
                """Современ [
                """Современные подходы к управлениюные подходы к управлению персоналом

68% сотруд персоналом

68% сотрудниковников остаются там, где остаются там, где есть есть возможности для развития возможности для развития. Г. Гибкий график работыибкий график работы стал стал новым стандартом в новым стандартом в ин индустрии.

дустрии.

КлюКлючевые направления:

    •чевые направления:

    • Развитие вместо денежных Развитие вместо денежных стимулов. Соз стимулов. Создавайте индивидуальныедавайте индивидуальные карты профессионального роста для карты профессионального роста для каждого сотрудника.

    • Баланс каждого сотрудника.

    • Баланс работы работы и личных интере и личных интересов.сов. Возможность работать Возможность работать над персональ над персональными проекными проектами значительно снижаеттами значительно снижает риски вы риски выгораниягорания.

   .

    • Открытая • Открытая коммуникация. коммуникация. Регу Регулярные встрелярные встречи должны фчи должны фокусироваться наокусироваться на стратегических це стратегических целях илях и текущем состоянии коман текущем состоянии команды.""",
                
                """Как изды.""",
                
                """Как изменился HR в менился HR в 2024: новые правила2024: новые правила найма

78% найма

78% компаний активно ищут кандидатов компаний активно ищут кандидатов с развитым эмо с развитым эмоциональным интеллекциональным интеллектом.том. Искусственный Искусственный интел интеллект обрабатылект обрабатывает вает 65% всех поступа65% всех поступающих резющих резюме.

Клююме.

Ключевыечевые направления:

    направления:

    • М • Мягкие навыягкие навыки вместо жестки вместо жестких требованийких требований. Те. Техническим навыхническим навыкам можнокам можно научить относительно быстро научить относительно быстро, тогда, тогда как мышление меня как мышление меняется значительноется значительно дольше.

 дольше.

    •    • Прозрачность Прозрачность процесса найма. процесса найма. Внедрение Внедрение пробного рабочего пробного рабочего дня дня заменяет много заменяет многоэтаэтапные собеседпные собеседованияования.

    • Постоян.

    • Постоянная обраная обратная связь.тная связь. Профе Профессиональный фиссиональный фидбдбек следует даватьек следует давать даже тем даже тем кандидатам кандидатам, которых не приняли на позицию."""
            ],
            
            "PR и коммуникации":, которых не приняли на позицию."""
            ],
            
            "PR и коммуникации": [
                """Трансформа [
                """Трансформация PR-коммуция PR-коммуникацийникаций

45% компа

45% компаний ужений уже используют искусственный инте используют искусственный интеллекллект для создания материаловт для создания материалов. Сов. Современная аудиременная аудитория большетория больше доверяет доверяет микроин микроинфлюенсефлюенсерам,рам, чем крупным б чем крупным блогерам.

Ключевые направления:

    • Простота и ясность сообщений.логерам.

Ключевые направления:

    • Простота и ясность сообщений. Необходи Необходимо говорить на языкемо говорить на языке целевой аудитории, целевой аудитории, избегая профессионального ж избегая профессионального жаргона.

    •аргона.

    • Прозрачность и а Прозрачность и аутентиутентичность контента.чность контента. Д Демонстрация рабоемонстрация рабочего процессачего процесса создает создает устойчи устойчивое доверие у подписчиковвое доверие у подписчиков.

   .

    • Формирование активного сообщества. Ре • Формирование активного сообщества. Регулярные ответы на комментариигулярные ответы на комментарии превращают превращают пассивную аудиторию в активных участ пассивную аудиторию в активных участников.""ников.""",
                
                """PR",
                
                """PR в в 2024: комму 2024: коммуниканикации, которые работают

ции, которые работают

LinkedIn утвердился вLinkedIn утвердился в качестве главной B2B качестве главной B2B-площадки для профессиональ-площадки для профессионального общения. Корного общения. Короткие видеоформаты демоноткие видеоформаты демонстрируют рост вовлеченстрируют рост вовлеченности на 300ности на 300%.

Ключевые%.

Ключевые направления направления:

    • Личный бренд:

    • Личный бренд вместо вместо корпоративного. И корпоративного. Исссследования показывают, чтоледования показывают, что люди ск люди склонлонны доверять конкретнымны доверять конкретным людям людям, а не аб, а не абстрактстрактным компаным компаниям.

    • Видениям.

    • Видеоконоконтент вместо текстового.тент вместо текстового. Короткие Короткие видео собирают в видео собирают в три раза больше три раза больше просмотров по сравнению просмотров по сравнению с тради с традиционными текстовыми публикационными текстовыми публикациямициями.

    • Диал.

    • Диалог с аудиог с аудиториейторией вместо монолога вместо монолога. В. В современных условиях комментарии современных условиях комментарии под пост под постом часто становятся важом часто становятся важнее самогонее самого контента."""
 контента."""
                       ]
        }
        return random ]
        }
        return random.choice(f.choice(fallbacks.get(allbacks.get(theme,theme, ["Актуаль ["Актуальные тенные тенденции 202денции 2024-4-2025 года."2025 года."]))

   ]))

    def add def add_tg_hashtags_tg_hashtags(self(self, theme):
        hasht, theme):
        hashtags = {
            "HRags = {
            " и управление персоналом": "#HR #управление #комHR и управление персоналом": "#HR #управление #командаанда",
            "PR",
            "PR и коммуника и коммуникации": "#ции": "#PR #коммуPR #коммуниканикацииции #маркетинг", 
 #маркетинг", 
            "ремонт и            "ремонт и строительство": "#ремонт # строительство": "#ремонт #стройка #дистройка #дизайнзайн"
        }
       "
        }
        return hasht return hashtags.get(themeags.get(theme, "")
    
, "")
    
    def send    def send_to_telegram_to_telegram(self,(self, chat_id, text chat_id, text, image, image_url=None):
_url=None):
        print(f"        print(f"📤 Отправка в {chat_id📤 Отправка в {chat_id}...")
        
        if}...")
        
        if image_url image_url:
            url:
            url = = f"https://api f"https://api.tele.telegram.org/bot{Bgram.org/bot{BOT_TOKENOT_TOKEN}/sendPhoto"
}/sendPhoto"
            payload            payload = {
                " = {
                "chat_idchat_id": chat_id,
": chat_id,
                "                "photo": image_urlphoto": image_url,
                ",
                "caption": text,
                "parse_mode":caption": text,
                "parse_mode": "HTML"
            "HTML"
            }
 }
            
            try            
            try:
                response =:
                response = requests.post(url, json= requests.post(url, json=payload, timeout=30)
               payload, timeout=30)
                if response.status_code == if response.status_code == 200:
                    200:
                    self.add self.add_to_history(text,_to_history(text, chat_id chat_id)
                    if self)
                    if self.current_.current_theme:
theme:
                        self.add                        self.add_theme_to_theme_to_history(chat_history(chat_id, self_id, self.current_theme)
.current_theme)
                    print(f                    print(f"✅ По"✅ Пост отправст отправленлен в {chat_id}")
 в {chat_id}")
                    return                    return True
                else True
                else:
                   :
                    print(f" print(f"❌ О❌ Ошибка: {шибка: {response.text}")
response.text}")
                    return self.send_text                    return self.send_text_to_to_telegram(chat_telegram(chat_id_id, text)
, text)
            except Exception as e:
                print            except Exception as e:
                print(f"❌(f"❌ Ошибка: {e}")
                Ошибка: {e}")
                return self return self.send_text_to_.send_text_to_telegramtelegram(chat_id,(chat_id, text)
 text)
        else        else:
            return self.send_text_to:
            return self.send_text_to_telegram(chat_id, text)
_telegram(chat_id, text)
    
    def send_text_to    
    def send_text_to__teletelegram(self,gram(self, chat_id, text):
        url = f chat_id, text):
        url = f"https://api."https://api.telegram.org/bottelegram.org/bot{BOT{BOT_TOKEN}/sendMessage_TOKEN}/sendMessage"
       "
        payload = {
            payload = {
            "chat "chat_id": chat_id_id": chat_id,
            ",
            "text": texttext": text,
           ,
            "parse_mode": " "parse_mode": "HTML"
       HTML"
        }
        
        try }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
               :
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                self.add_to self.add_to_history(text, chat_history(text, chat_id)
               _id)
                if self.current if self.current_theme:
                    self_theme:
                    self.add_.add_theme_to_history(theme_to_history(chat_idchat_id, self.current_, self.current_theme)
theme)
                print(f"                print(f"✅ Т✅ Текстовый постекстовый пост отправлен отправлен в {chat_id в {chat_id}")
               }")
                return True
            return True
            else:
                print(f" else:
                print(f"❌❌ Ошиб Ошибка: {responseка: {response.text}")
.text}")
                return False
                return False
        except        except Exception as e:
 Exception as e:
            print(f            print(f"❌"❌ Ошибка Ошибка: {e}")
: {e}")
            return False            return False
    
   
    
    def generate_post_hash(self, text def generate_post_hash(self, text):
        return hashl):
        return hashlib.md5(text.encode('utf-ib.md5(text.encode('utf-8')).hexdig8')).hexdigest()
    
    def is_post_uniqueest()
    
    def is_post_unique(self,(self, post_text, channel post_text, channel_id):
_id):
        post_hash = self        post_hash = self.generate.generate_post_hash(post_text)
       _post_hash(post_text)
        channel_key = str(channel channel_key = str(channel_id_id)
        
        if ")
        
        if "posts"posts" not in self.post not in self.post_history:
_history:
            self.post_history            self.post_history["posts"] = {}
        if channel["_key not in self.post_historyposts"] = {}
        if channel_key not in self.post_history["posts["posts"]:
            self"]:
            self.post_history["posts.post_history["posts""][channel_key] =][channel_key] = []
        
 []
        
        recent_posts        recent_posts = self = self.post_history["posts.post_history["posts""][channel_key][-50][channel_key][-50:]
:]
               return post return post_hash not in recent_posts
    
    def_hash not in recent_posts
    
    def add_to_history(self add_to_history(self, post_text, channel_id):
       , post_text, channel_id):
        post_hash post_hash = self.generate_post = self.generate_post_hash(post_hash(post_text)
        channel_key =_text)
        channel_key = str(channel_id)
        
 str(channel_id)
        
        if "posts"        if "posts" not in not in self.post_history:
            self.post_history:
            self.post self.post_history["posts"]_history["posts"] = {}
 = {}
        if channel_key        if channel_key not in not in self.post_history["posts self.post_history["posts"]"]:
            self.post_history[":
            self.post_history["posts"][channel_key] =posts"][channel_key] = []
        
        self.post_history["posts"][channel_key].append(post_hash []
        
        self.post_history["posts"][channel_key].append(post_hash)
)
        if len(self.post        if len(self.post_history_history["posts"][channel["posts"][channel_key]) >_key]) > 100:
            100:
            self.post self.post_history["posts"_history["posts"][channel][channel_key] = self.post_history_key] = self.post_history["posts"][channel_key["posts"][channel_key][-50:]
        
       ][-50:]
        
        self.save_post_history()
    
 self.save_post_history()
    
    def send_dual_posts    def send_dual_posts(self):
        self.current(self):
        self.current_theme_theme = self.get_smart = self.get_smart__theme(MAIN_CHANNtheme(MAIN_CHANNEL_ID)
        
        printEL_ID)
        
        print(f"🎯 Ум(f"🎯 Умный выбор темы: {ный выбор темы: {selfself.current_theme}")
        
.current_theme}")
        
        # Используем        # Используем уникальное уникальное изображение для изображение для темы темы
        theme_image
        theme_image = self.get_unique_image(self.current_theme = self.get_unique_image(self.current_theme)
        
        print(")
        
        print("🧠🧠 Генерация по Генерация постовстов...")
        tg_post = self.generate_t...")
        tg_post = self.generate_tg_postg_post(self.current_theme)
        zen_post = self.generate(self.current_theme)
        zen_post = self.generate_zen_zen_post(self.current_theme)
_post(self.current_theme)
        
        print(f"        
        print(f"📝 ТГ-пост: {len(tg_post)} символов")
📝 ТГ-пост: {len(tg_post)} символов")
        print(f"📝        print(f"📝 Дзен-пост Дзен-пост:: {len( {len(zen_post)} симвzen_post)} символов")
        
        if not self.is_post_uniqueолов")
        
        if not self.is_post_unique(tg(tg_post, MAIN_CH_post, MAIN_CHANNELANNEL_ID):
_ID):
            print("⚠️ Пост для            print("⚠️ Пост ТГ не уникален, генерируем заново для ТГ не уникален, генерируем заново...")
            return self.send_dual...")
            return self.send_dual_posts()
            
       _posts()
            
        if if not self.is_post_unique( not self.is_post_unique(zen_post, ZEN_CHzen_post, ZEN_CHANNEL_ID):
            printANNEL_ID):
            print("⚠️ По("⚠️ Пост для Дзена нест для Дзена не уникален, генериру уникален, генерируем заново...")  
ем заново...")  
            return self.send_dual            return self.send_dual_posts()
        
_posts()
        
        print("📤 Отправка в @        print("📤 Отправка в @da4a_hrda4a_hr......")
        tg_success =")
        tg_success = self self.send_to_telegram.send_to_telegram((MAIN_CHANNELMAIN_CHANNEL_ID,_ID, tg_post tg_post, theme, theme_image)
        
        print_image)
        
        print("("📤 Отправка в📤 Отправка в @tehdzen @tehdzenm...")
        zen_success =m...")
        zen_success = self.send_to_telegram self.send_to_telegram(ZEN_CHANNEL_ID(ZEN_CHANNEL_ID, zen_post, theme_image)
        
, zen_post, theme_image)
        
        if tg_success        if tg_success and and zen_success:
            zen_success:
            print print("✅ ПОСТ("✅ ПОСТЫ УСПЕШЫ УСПЕШНО ОТПРАВНО ОТПРАВЛЕНЫ!")
ЛЕНЫ!")
            return True
        else            return True
        else:
            print(f"⚠️ Есть ошиб:
            print(f"⚠️ Есть ошибкики: ТГ={tg_success}, Д: ТГ={tg_success}, Дзензен={zen_success}")
            return tg_success={zen_success}")
            return tg_success or zen_success or zen_success

def main():
    print

def main():
    print("\n🚀("\n🚀 ЗАПУСК УМНО ЗАПУСК УМНОГО ГЕНЕГО ГЕНЕРАТОРАТОРА")
   РА")
    print print("🎯("🎯 Проверка Проверка истории перед генерацией")
    print(" истории перед генерацией")
    print("🎯 Исклю🎯 Исключение повторяющихся тем")
чение повторяющихся тем")
       print("🖼 print("🖼️ Си️ Системастема уникальных уникальных изображений изображений")
   ")
    print("=" * print("=" * 80 80)
    
   )
    
    bot = bot = SmartPostGenerator()
    SmartPostGenerator()
    success success = bot.send_dual = bot.send_dual_posts_posts()
    
()
    
    if success:
    if success:
        print        print("\n🎉("\n🎉 УСПЕ УСПЕХ!Х! Посты отправлены Посты отправлены!")
   !")
    else:
        else:
        print print("\n💥 ЕСТ("\n💥 ЕСТЬ ОШИБКИ ОТПРАВКИ!")
    
    printЬ ОШИБКИ О("=" * 80)

ТПРАВКИ!")
    
    print("=" * 80)

if __name__ == "__if __name__ == "__main__":
main__":
    main    main()
