from selenium import webdriver
import time
import os
from dotenv import load_dotenv

# 1. Грузим данные из .env файла
load_dotenv()

# 2. Берем логин/пароль из .env
login = os.getenv("YANDEX_LOGIN")
password = os.getenv("YANDEX_PASSWORD")

print("🔧 Запускаем тест...")
print(f"Логин: {login}")  # Проверим что загрузилось

# 1. Открываем браузер
driver = webdriver.Chrome()
print("✅ Браузер открыт")

# 2. Идем на страницу входа
driver.get("https://passport.yandex.ru/auth/")
time.sleep(2)

# 3. Вводим логин
login_field = driver.find_element("id", "passp-field-login")
login_field.send_keys(login)
print("✅ Логин введен")

# 4. Нажимаем "Войти"
login_btn = driver.find_element("id", "passp:sign-in")
login_btn.click()
time.sleep(2)

# 5. Вводим пароль
password_field = driver.find_element("id", "passp-field-passwd")
password_field.send_keys(password)
print("✅ Пароль введен")

# 6. Нажимаем "Войти"
password_btn = driver.find_element("id", "passp:sign-in")
password_btn.click()
time.sleep(5)

print("🎉 Если видите страницу Яндекса - ВСЁ РАБОТАЕТ!")
print("Теперь можем публиковать посты в Дзен!")

input("Нажмите Enter чтобы закрыть браузер...")
driver.quit()
