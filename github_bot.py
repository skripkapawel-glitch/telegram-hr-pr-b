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
print("🚀 УМНЫЙ БОТ: ПРОФЕССИОНАЛЬНЫЕ ПОСТЫ")
print("=" * 80)

class SmartPostGenerator:
    def __init__(self):
        self.themes = ["HR и управление персоналом", "PR и коммуникации", "ремонт и строительство"]
        
        self.history_file = "post_history.json"
        self.post_history = self.load_post_history()
        
        # Надежные изображения
        self.theme_images = {
            "HR и управление персоналом": [
                "https://images.unsplash.com/photo-1552664730-d307ca884978?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ],
            "PR и коммуникации": [
                "https://images.unsplash.com/photo-1432888622747-4eb9a8efeb07?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?ixlib=rb-4.0.3&w=1200&h=630&fit=crop", 
            ],
            "ремонт и строительство": [
                "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
                "https://images.unsplash.com/photo-1504307651254-35680f356dfd?ixlib=rb-4.0.3&w=1200&h=630&fit=crop",
            ]
        }
        
        self.fallback_images = [
            "https://picsum.photos/1200/630",
            "https://placekitten.com/1200/630",
        ]
        
        # База знаний с качественным контентом
        self.knowledge_base = {
            "HR и управление персоналом": [
                {
                    "title": "HR в 2024: нанимают не навыки, а mindset",
                    "facts": [
                        "78% компаний ищут кандидатов с развитым эмоциональным интеллектом",
                        "AI уже обрабатывает 65% резюме на первичном этапе"
                    ],
                    "tg_tips": [
                        "Смотрите на soft skills — техническим навыкам можно научить, а мышление меняется долго",
                        "Внедрите пробный день вместо пятиэтапного собеседования — так понятнее и кандидату, и вам",
                        "Давайте обратную связь даже тем, кого не взяли — это формирует лояльность к бренду работодателя"
                    ],
                    "zen_structure": [
                        "Мягкие навыки вместо жестких требований",
                        "Прозрачность процесса найма", 
                        "Постоянная обратная связь"
                    ]
                },
                {
                    "title": "Как удерживать команду в 2024",
                    "facts": [
                        "Сотрудники остаются там, где есть развитие — 68% ценят обучение выше зарплаты",
                        "Гибкий график стал стандартом ожидания, а не преимуществом"
                    ],
                    "tg_tips": [
                        "Создайте карту развития для каждой позиции — люди должны видеть свой рост",
                        "Разрешите работать над личными проектами 10% времени — это снижает выгорание",
                        "Проводите регулярные one-to-one встречи не о задачах, а о целях и настроении"
                    ],
                    "zen_structure": [
                        "Карьерный рост вместо денежных бонусов",
                        "Баланс работы и личных интересов",
                        "Открытый диалог с руководством"
                    ]
                }
            ],
            "PR и коммуникации": [
                {
                    "title": "PR в 2024: что реально работает",
                    "facts": [
                        "LinkedIn стал главной B2B-площадкой — 85% компаний ведут там PR",
                        "Короткие видео дают +300% к вовлеченности compared с текстом"
                    ],
                    "tg_tips": [
                        "Делайте личный бренд руководителей в LinkedIn — люди доверяют людям, а не компаниям",
                        "Снимите 30-секундное видео о проекте вместо пресс-релиза — его досмотрят до конца", 
                        "Дайте эксперту из команды пообщаться в комментариях — это живая коммуникация, а не монолог"
                    ],
                    "zen_structure": [
                        "Личный бренд вместо корпоративного",
                        "Видеоконтент вместо текстового",
                        "Диалог с аудиторией вместо монолога"
                    ]
                },
                {
                    "title": "Коммуникации, которые действительно доходят до людей",
                    "facts": [
                        "45% PR-специалистов используют AI для подготовки материалов",
                        "Аудитория в 3 раза чаще доверяет микро-инфлюенсерам, чем знаменитостям"
                    ],
                    "tg_tips": [
                        "Говорите на языке клиента, а не на корпоративном жаргоне — проверьте, поймет ли ваша бабушка",
                        "Показывайте закулисье проектов — прозрачность builds trust быстрее, чем идеальная картинка",
                        "Отвечайте на комментарии лично — это превращает пассивную аудиторию в сообщество"
                    ],
                    "zen_structure": [
                        "Простой язык вместо профессионального жаргона",
                        "Прозрачность процессов и решений", 
                        "Сообщество вместо аудитории"
                    ]
                }
            ],
            "ремонт и строительство": [
                {
                    "title": "Ремонт в 2024: тренды, которые останутся",
                    "facts": [
                        "Натуральные материалы выбирают 72% клиентов — даже если дороже",
                        "Умный дом стал must-have для 60% новостроек"
                    ],
                    "tg_tips": [
                        "Используйте локальные материалы — это экологичнее и поддерживает местных производителей", 
                        "Заложите умные системы на этапе черновой отделки — переделывать будет дороже",
                        "Сделайте универсальную базу — сменный декор обойдется дешевле, чем новый ремонт"
                    ],
                    "zen_structure": [
                        "Натуральные и локальные материалы",
                        "Технологии как основа, а не дополнение",
                        "Гибкость и адаптивность пространства"
                    ]
                },
                {
                    "title": "Строительство без стресса: как сейчас работают",
                    "facts": [
                        "Модульные конструкции сокращают сроки на 40% без потери качества",
                        "Дроны и и адаптивность пространства"
                    ]
                },
                {
                    "title": "Строительство без стресса: как сейчас работают",
                    "facts": [
                        "Модульные конструкции сокращают сроки на 40% без потери качества",
                        "Дроны и 3D 3D-сканирование экономят до 25% бюджета на измерениях"
                    ],
                    "tg_tips": [
                        "Создайте цифровой двойник объекта — это поможет избежать 80% ошибок на стройке",
                        "Используйте BIM-моделирование — видите clashes до начала работ, а не в процессе",
                        "Ведите онлайн-дневник стройки — клиент в курсе прогресса, вы меньше отвлекаетесь на отчеты"
-сканирование экономят до 25% бюджета на измерениях"
                    ],
                    "tg_tips": [
                        "Создайте цифровой двойник объекта — это поможет избежать 80% ошибок на стройке",
                        "Используйте BIM-моделирование — видите clashes до начала работ, а не в процессе",
                        "Ведите онлайн-дневник стройки — клиент в курсе прогресса, вы меньше отвлекаетесь на отчеты"
                                       ],
                    "zen_structure ],
                    "zen_structure": [
": [
                        "Ци                        "Цифровое проектирование ифровое проектирование и контроль контроль",
                        "П",
                        "Прозрачность для заказчикарозрачность для заказчика",
                        "Оптими",
                        "Оптимизация процессов через технологии"
                    ]
                }
            ]
        }

    def load_post_history(selfзация процессов через технологии"
                    ]
                }
            ]
        }

    def load_post_history(self):
        try:
            if os.path.exists(self.history):
        try:
            if os.path.exists(self_file):
                with open(self.history_file):
                with open(self.history_file.history_file, 'r',, 'r', encoding='utf encoding='utf-8-8') as') as f:
                    return f:
                    return json.load json.load(f)
           (f)
            return {}
        return {}
        except:
            return except:
            return {}
    
 {}
    
    def save    def save_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.d_post_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.post_history, f, ensure_ascii=False,ump(self.post_history, f, ensure_ascii=False, indent=2)
        except indent=2)
        except Exception Exception as e:
            print(f as e:
            print(f"⚠️ Ошибка"⚠️ Ошибка сохранения истории: сохранения истории: {e}")
    
    def get_reliable {e}")
    
    def get_reliable_image(self, theme):
       _image(self, theme):
        try:
            theme try:
            theme_image = random.choice(self.theme_images_image = random.choice(self.theme_images.get(theme, self.the.get(theme, self.theme_images["HR и управme_images["HR и управление персоналом"]))
           ление персоналом"]))
            print(f"🖼 print(f"🖼️️ Используем изображение Используем изображение: {: {theme_image}")
           theme_image}")
            return theme return theme_image
        except:
           _image
        except:
            fallback = random.choice(self fallback = random.choice(self.fallback_images)
            print(f.fallback_images)
            print(f"🖼️"🖼️ Использу Используем fallback:ем fallback: {fallback}")
 {fallback}")
            return            return fallback
    
    def generate fallback
    
    def generate_tg_tg_post(self, theme_post(self, theme_data):
_data):
        """        """ГГенериенерирует пострует пост для Telegram в человеческом сти для Telegram в человеческом стиле"""
        theme =ле"""
        theme = theme_data["theme"]
        theme_data["theme"]
        content = content = theme_data[" theme_data["content"]
        
        # Сcontent"]
        
        # Собираем пост для Тобираем пост для ТГ
        post_parts =Г
        post_parts = []
        
 []
        
        # Заг        # Заголовок
оловок
        post_parts        post_parts.append(f"{.append(f"{content['title']content['title']}\}\n")
        
       n")
        
        # Факты в естественной форме
        facts_text = " # Факты в естественной форме
        facts_text = " • ". •join(content['facts'])
        post_parts.append(f"{facts_text}\n")
        
        # Советы ".join(content['facts'])
        post
_parts.append(f"{facts_text}\n")
        
        # Советы
        post_parts        post_parts.append("Что работает прямо.append("Что работает прямо сейчас сейчас:")
        for i,:")
        for i, tip tip in enumerate(content['tg in enumerate(content['tg_tips_tips'], '], 1):
1):
            post_parts.append            post_parts.append(f(f"\n{tip}")
"\n{tip}")
        
        # Вопрос для        
        # Вопрос для вов вовлечения
        postлечения
        post_parts_parts.append(f"\n.append(f"\n\nА в вашей\nА в вашей практике практике что сработало что сработало?")
?")
        
        return "\        
        return "\n".n".join(post_parts)
    
join(post_parts)
    
    def generate_    def generate_zenzen_post(self, theme_data):
       _post(self, theme_data):
        """Генерирует пост """Генерирует пост для Дзена в анали для Дзена в аналитическомтическом стиле"""
        стиле"""
        theme = theme = theme_data["theme theme_data["theme"]
       "]
        content = theme_data content = theme_data["content["content"]
        
        # Соби"]
        
        # Собираем пост для Драем пост для Дзеназена
        post_p
        post_parts =arts = []
        
        # []
        
        # Заг Заголовоколовок
       
        post_parts.append(f post_parts.append(f"{content"{content['title']}\n['title']}\n")
        
")
        
        # Введение        # Введение с с фактами
        фактами
        intro = f"{ intro = f"{content['content['facts'][0]} {facts'][0]} {content['factscontent['facts'][1]}'][1]}"
"
        post        post_parts.append(f"{intro}\n")
        
        # Структур_parts.append(f"{intro}\n")
        
        # Структурный анализ
        post_pный анализ
        post_parts.append("Кarts.append("Ключелючевые направления:\n")
вые направления:\n")
        
        
        for i, point        for i, point in enumerate in enumerate(content['(content['zen_stzen_structure'], 1):
ructure'], 1):
                       post_parts.append(f"{ post_parts.append(f"{point}")
point}")
            #            # Добавляем пояс Добавляем пояснение кнение к каждому пунк каждому пункту
           ту
            if i ==  if i == 1:
                post1:
                post_parts.append(f_parts.append(f"{content"{content['tg['tg_tips'][0_tips'][0]}\n")
]}\n")
            elif i ==            elif i == 2:
                2:
                post_p post_parts.append(f"{arts.append(f"{content['content['tg_ttg_tips'][1]}\n")
            else:
                post_parts.append(f"{contentips'][1]}\n")
            else:
                post_parts.append(f"{content['tg_tips['tg_tips'][2]}\n")
        
'][2]}\n")
        
        # Заключение
        # Заключение
        post_parts.append("        post_parts.append("ПрофессионалыПрофессионалы теперь должны совмещать теперь должны совмещать экспертизу в своей экспертизу в своей области с понима области с пониманием современных инструнием современных инструментов и запросовментов и запросов аудитории. Успех при аудитории. Успех приходит к тем, кто говоритходит к тем, кто говорит с с людьми на их людьми на их языке.")
 языке.")
        
        return "\        
        return "\n".join(postn".join(post_parts_parts)
    
    def)
    
    def add_t add_tg_hashtg_hashtags(self, themeags(self, theme):
):
        hashtags = {
                   hashtags = {
            " "HR и управление персоналомHR и управление персоналом": "#HR #управ": "#HR #управление #команда #ление #команда #карьера #карьера #работа",
            "PR иработа",
            "PR и коммуникации": "#PR #ком коммуникации": "#PR #коммуникации #LinkedIn #маркетинг #муникации #LinkedIn #маркетинг #бренд",бренд", 
 
                       "ремонт и строи "ремонт и строительство": "#ремонт #стройтельство": "#ремонт #стройка #дизайн #интерьер #кварка #дизайн #интерьер #квартира"
        }
       тира"
        }
        return hashtags.get return hashtags.get(theme,(theme, "")
    
    def send "")
    
    def send_to__to_telegramtelegram(self, chat(self, chat_id, text,_id, text, image image_url=None):
        """От_url=None):
        """Отправляет пост в Telegram"""
правляет пост в Telegram"""
        print(f"📤        print(f"📤 Отправка в {chat Отправка в {chat_id}...")
        
        if image_url:
            url = f_id}...")
        
        if image_url:
            url = f"https://api.telegram.org"https://api.telegram.org/bot{BOT_TOKEN}//bot{BOT_TOKEN}/sendPhoto"
            payload =sendPhoto"
            payload = {
                "chat_id": {
                "chat_id": chat_id,
                chat_id,
                "photo": image_url,
                "caption "photo": image_url,
                "caption":": text,
                "parse_mode text,
                "parse_mode": "HTML"
            }
": "HTML"
            }
            
            try:
                response            
            try:
                response = requests.post(url, json= = requests.post(url, jsonpayload, timeout=30)
               =payload, timeout=30)
 if response.status_code ==                 if response.status_code == 200:
                    self200:
                    self.add.add_to_history(text, chat_to_history(text, chat_id)
                    print(f"✅ По_id)
                    print(f"✅ Пост отправлен вст отправлен в {chat_id}")
                    return True
                else:
                    print {chat_id}")
                    return True
                else:
                    print(f"(f"❌ О❌ Ошибка: {response.textшибка: {response.text}")
                   }")
                    return self.send_text return self.send_text_to__to_telegram(chat_idtelegram(chat_id,, text)
            except text)
            except Exception as Exception as e:
                print e:
                print(f(f"❌ Ошиб"❌ Ошибка:ка: {e}")
                {e}")
                return self return self.send_text_to_telegram(chat_id, text)
        else:
           .send_text_to_telegram(chat_id, text)
        else:
            return self return self.send_text_to_tele.send_text_to_telegram(chatgram(chat_id, text)
_id, text)
    
       
    def send_text_to_telegram(self def send_text_to_telegram(self, chat_id,, chat_id, text):
        """Отправляет text):
        """Отправляет текстовый пост"""
        текстовый пост"""
        url = f"https url = f"https://api://api.telegram.org/bot{BOT_TOKEN}/.telegram.org/bot{BOT_TOKENsendMessage"
        payload = {
           }/sendMessage"
        payload = {
            "chat_id": chat_id "chat_id": chat_id,
            "text": text,
            "text": text,
            "parse_mode": "HTML,
            "parse_mode": ""
        }
HTML"
        }
        
        
        try:
            response =        try:
            response = requests.post(url, json= requests.post(url, json=payloadpayload, timeout=30)
, timeout=30)
            if            if response.status_code == 200:
                self response.status_code == 200:
                self.add_to_history(text, chat_id)
               .add_to_history(text, chat_id)
                print(f"✅ Тек print(f"✅ Текстовый пост отправлен в {стовый пост отправлен в {chatchat_id}")
                return True
_id}")
                return True
            else            else:
               :
                print(f print(f"❌ О"❌ Ошибкашибка: {response.text: {response.text}")
                return False
       }")
                return False
        except Exception except Exception as e:
            print(f"❌ О as e:
            print(f"❌ Ошибшибка: {e}")
ка: {e}")
            return False
    
    def generate_post            return False
    
    def generate_post_hash(self, text):
       _hash(self, text):
        return hashlib.md5(text.encode('utf return hashlib.md5(text.encode('utf-8-8')).hex')).hexdigest()
    
    defdigest()
    
    def is_post is_post_unique(self, post_unique(self, post_text,_text, channel_id):
        channel_id):
        post_hash post_hash = self.generate_post = self.generate_post_hash(post_hash(post_text)
        channel_text)
        channel_key =_key = str(channel_id str(channel_id)
        
        if)
        
        if channel_key not channel_key not in self.post in self.post_history:
            self_history:
            self.post_history.post_history[channel_key][channel_key] = []
        
        = []
        
        recent_p recent_posts = self.postosts = self.post_history_history[channel_key[channel_key][-50:]
][-50:]
        return post        return post_hash not in recent_hash not in recent_posts
    
_posts
    
    def    def add_to add_to_history(self, post_text, channel_id_history(self, post_text, channel_id):
        post):
        post_hash = self_hash = self.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
.generate_post_hash(post_text)
        channel_key = str(channel_id)
        
        if        if channel_key not in self.post channel_key not in self.post_history:
_history:
            self.post_history            self.post_history[channel[channel_key] = []
_key] = []
        
        self        
        self.post_history.post_history[channel_key].append[channel_key].append(post_hash)
        if len(self.post(post_hash)
        if len(self.post_history_history[channel_key])[channel_key]) > 100 > 100:
            self.post:
            self.post_history_history[channel_key] = self[channel_key] = self.post.post_history_history[channel_key][[channel_key][-50:]
        
        self.save-50:]
        
        self.save_post_history_post_history()
    
    def()
    
    def send_ send_dual_posts(selfdual_posts(self):
       ):
        # Выбираем # Выбираем тему и тему и конкретный кон конкретный контенттент
        theme =
        theme = random.choice random.choice(self.themes)
       (self.themes)
        content content = random.choice(self.knowledge_base = random.choice(self.know[theme])
        
        theme_data = {
            "theme": theme,
            "contentledge_base[theme])
        
        theme_data = {
            "theme": theme,
            "content": content": content
       
        }
        
        print }
        
        print(f"🎯(f"🎯 Т Тема: {themeема: {theme}")}")
        print(f
        print(f""📄 Конт📄 Контентент: {content['title']: {content['title']}")
        
        # Получа}")
        
        # Получаемем изображение
        theme изображение
        theme_image =_image = self.get_reliable_image self.get_reliable_image((theme)
        
        # Гtheme)
        
        # Генерируем постыенерируем посты

        print("🧠        print("🧠 Ген Генерация постоверация постов...")
        tg_post =...")
        tg_post = self.generate self.generate_tg_post(theme_data)
        zen_post_tg_post(theme_data)
        zen_post = = self.generate_zen_post( self.generate_zen_post(themetheme_data)
        
_data)
        
               # Добавляем хе # Добавляем хештеги только для ТГ
       штеги только для ТГ
        tg tg_full_post = f"{tg_full_post = f"{tg_post_post}\n\n{self.add}\n\n{self.add_tg_hashtags_tg_hashtags(theme(theme)}"
        
       )}"
        
        print(f" print(f"📝 ТГ📝 ТГ-пост:-пост: {len(t {len(tg_fullg_full_post)} символов_post)} символов")
       ")
        print(f" print(f"📝 Дзен📝 Дзен-по-пост:ст: {len(zen_post {len(zen_post)} символов)} символов")
        
        #")
        
        # Пров Проверяем уникаеряем уникальностьльность

        if not self.is        if not self.is_post_post_unique(tg_full_post, MAIN_CHANNEL_ID):
            print("⚠️_unique(tg_full_post, MAIN_CHANNEL_ID):
            print("⚠️ Пост для ТГ не уникален, г Пост для ТГ не уникален, генерируем зановенерируем заново...")
            return self.send_о...")
            return self.senddual_posts()
            
       _dual_posts()
            
        if not self.is_post_unique if not self.is_post_unique(zen_post, ZEN(zen_post, Z_CHANNEL_ID):
            print("⚠️ Пост для ДEN_CHANNEL_ID):
            print("⚠️ Пост для Дзена не уникален, генерируем зановозена не уникален, генерируем заново...")  
           ...")  
            return self.send_dual_p return self.send_dual_posts()
        
        # Отправляемosts()
        
        # Отправляем
       
        print("📤 print("📤 Отправка в @da4a Отправка в @da4a_hr_hr...")
        tg_s...")
        tg_success =uccess = self.send_to_tele self.send_to_telegram(gram(MAIN_CHANNMAIN_CHANNEL_IDEL_ID, tg, tg_full_post_full_post, theme_image)
, theme_image)
        
        print("        
        print("📤📤 Отправка в Отправка в @tehdzen @tehdzenm...m...")
        zen_success = self.send_to_telegram(ZEN")
        zen_success = self.send_to__CHANNEL_ID, zen_posttelegram(ZEN_CHANNEL_ID, zen_post,, theme_image)
        
        if tg_success and zen_success:
            print("✅ ПОСТЫ УСПЕШНО ОТП theme_image)
        
        if tg_success and zen_success:
            print("✅ ПОСТЫ УСПЕШНО ОТПРАВЛЕНЫРАВЛЕНЫ!")
            return True
        else!")
            return True
        else:
:
            print(f"⚠️            print(f"⚠️ Е Есть ошибкисть ошибки: ТГ={tg_s: ТГ={tg_success}, Дзен={uccess}, Дзен={zen_success}")
            returnzen_success}")
            return tg_success or zen_success

def main():
    tg_success or zen_success

def main():
    print("\n🚀 З print("\n🚀 ЗАПУСК ПРОАПУСК ПРОФЕССИОНАЛЬНОГО ГЕНЕРАТФЕССИОНАЛЬНОГО ГЕНЕРАТОРА")
   ОРА")
    print("🎯 print("🎯 Человеческий язык вместо корпора Человеческий язык вместо корпоративного")
   тивного")
    print print("("🎯 Практические советы вместо теории")
   🎯 Практические советы вместо теории")
    print(" print("=" * 80=" * 80)
    
)
    
    bot = Smart    bot = SmartPostGeneratorPostGenerator()
    success = bot.send()
    success = bot.send_dual_dual_posts()
    
    if_posts()
    
    if success:
        print success:
        print("\("\n🎉 УСn🎉 УСПЕХ! ПроПЕХ! Профессиональные постыфессиональные посты отправ отправлены!")
    else:
       лены!")
    else:
        print print("\n("\n💥 ЕСТЬ ОШИБКИ ОТПРАВКИ!")
    
    print("=" * 80)

if💥 ЕСТЬ ОШИБКИ ОТПРАВКИ __!")
    
    print("=" * 80)

if __name__ == "__main__":
name__ == "__main__":
    main    main()
