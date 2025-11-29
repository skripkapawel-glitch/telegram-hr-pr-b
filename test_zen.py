from selenium import webdriver
import time
import pickle
import os

def test_zen_with_cookies():
    print("🔐 Тест входа в Яндекс с сохранением сессии")
    
    # Пробуем зайти по сохраненным кукам
    if os.path.exists("yandex_cookies.pkl"):
        print("🔄 Пробуем автоматический вход...")
        driver = webdriver.Chrome()
        driver.get("https://zen.yandex.ru")
        
        # Загружаем куки
        with open("yandex_cookies.pkl", "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        driver.refresh()
        time.sleep(3)
        
        # Проверяем успешность входа
        if "auth" not in driver.current_url:
            print("✅ Автоматический вход успешен!")
            return driver
        else:
            print("❌ Куки устарели, нужен повторный вход")
            driver.quit()
    
    # Если куков нет или они не работают - обычный вход
    print("🔑 Требуется ручной вход")
    login = input("Введите логин Яндекс: ")
    password = input("Введите пароль Яндекс: ")
    
    driver = webdriver.Chrome()
    
    # Процесс входа
    driver.get("https://passport.yandex.ru/auth/")
    time.sleep(2)
    
    # Ввод логина
    login_field = driver.find_element("id", "passp-field-login")
    login_field.send_keys(login)
    login_btn = driver.find_element("id", "passp:sign-in")
    login_btn.click()
    time.sleep(2)
    
    # Ввод пароля
    password_field = driver.find_element("id", "passp-field-passwd")
    password_field.send_keys(password)
    password_btn = driver.find_element("id", "passp:sign-in")
    password_btn.click()
    time.sleep(5)
    
    print("✅ Вход выполнен! Сохраняем куки...")
    
    # Сохраняем куки для след. разов
    with open("yandex_cookies.pkl", "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print("💾 Куки сохранены в yandex_cookies.pkl")
    
    return driver

# Запускаем тест
driver = test_zen_with_cookies()

print("🎉 Готово! Теперь можно публиковать посты.")
print("Следующий запуск будет автоматическим!")

input("Нажмите Enter чтобы закрыть...")
driver.quit()
