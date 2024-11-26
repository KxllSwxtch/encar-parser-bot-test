import time
import re
import requests
import locale

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from twocaptcha import TwoCaptcha
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Set locale for number formatting
try:
    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_ALL, "C")  # Использует стандартную локаль

# Токен вашего бота
bot_token = "8122197139:AAESd2hmle6YJ8Qdvwbj2rAU1AHZI0tR-hA"

# Создание экземпляра 2Captcha
solver = TwoCaptcha("89a8f41a0641f085c8ca6e861e0fa571")


# Форматирование больших значений
def format_number(number):
    return locale.format_string("%d", number, grouping=True)


# Функция для настройки Selenium с прокси
def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--enable-logging")
    chrome_options.add_argument("--v=1")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36"
    )

    # Запуск браузера
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def extract_sitekey(driver, url):
    driver.get(url)

    iframe = driver.find_element(By.TAG_NAME, "iframe")
    iframe_src = iframe.get_attribute("src")
    match = re.search(r"k=([A-Za-z0-9_-]+)", iframe_src)

    if match:
        sitekey = match.group(1)
        return sitekey
    else:
        return None


def send_recaptcha_token(token):
    data = {"token": token, "action": "/dc/dc_cardetailview.do"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.encar.com/",
    }

    url = "https://www.encar.com/validation_recaptcha.do?method=v3"
    # Отправляем POST-запрос с токеном
    response = requests.post(url, data=data, headers=headers)

    # Выводим ответ для отладки
    print("\n\nОтвет от сервера:")
    print(f"Статус код: {response.status_code}")
    print(f"Тело ответа: {response.text}\n\n")

    try:
        result = response.json()

        if result[0]["success"]:
            print("reCAPTCHA успешно пройдена!")
            return True
        else:
            print("Ошибка проверки reCAPTCHA.")
            return False
    except requests.exceptions.JSONDecodeError:
        print("Ошибка: Ответ от сервера не является валидным JSON.")
        return False
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return False


def get_ip():
    response = requests.get("https://api.ipify.org?format=json")
    ip = response.json()["ip"]
    print(f"Current IP address: {ip}")
    return ip


print(get_ip())


# Запуск браузера и получение токена reCAPTCHA
def get_car_info(url):
    global car_id_external

    try:
        driver = create_driver()
        solver = TwoCaptcha("89a8f41a0641f085c8ca6e861e0fa571")

        is_recaptcha_solved = True

        driver.get(url)

        print(driver.page_source)

        if "reCAPTCHA" in driver.page_source:
            print("Обнаружена reCAPTCHA, решаем...")

            sitekey = extract_sitekey(driver, url)
            print(f"Sitekey: {sitekey}")

            result = solver.recaptcha(sitekey, url)
            print(f'reCAPTCHA result: {result["code"][0:50]}...')

            is_recaptcha_solved = send_recaptcha_token(result["code"])

        if is_recaptcha_solved:
            # Достаём данные об авто после решения капчи
            car_date, car_price, car_engine_displacement, car_title = "", "", "", ""
            meta_elements = driver.find_elements(By.CSS_SELECTOR, "meta[name^='WT.']")

            meta_data = {}
            for meta in meta_elements:
                name = meta.get_attribute("name")
                content = meta.get_attribute("content")
                meta_data[name] = content

            car_date = f'01{meta_data["WT.z_month"]}{meta_data["WT.z_year"][-2:]}'
            car_price = meta_data["WT.z_price"]
            car_title = f'{meta_data["WT.z_model_name"]} {meta_data["WT.z_model"]}'

            # Предполагается, что драйвер Selenium уже инициализирован
            try:
                # Найти элемент с id "dsp"
                dsp_element = driver.find_element(By.ID, "dsp")
                # Получить значение из атрибута "value"
                car_engine_displacement = dsp_element.get_attribute("value")
            except Exception as e:
                print(f"Ошибка при получении объема двигателя: {e}")

            print(car_date, car_price, car_engine_displacement)
            driver.quit()
    except WebDriverException as e:
        print(f"Ошибка Selenium: {e}")
        driver.quit()

    return f"<b>{car_title}</b>\n\n Дата регистрации: {meta_data['WT.z_year']}/{meta_data['WT.z_month']}\nЦена: {format_number(int(car_price)*10000)} KRW\nОбъем двигателя: {format_number(int(car_engine_displacement))} cc"


# Обработчик команды /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Отправьте ссылку на автомобиль с сайта encar")


# Обработчик для ссылок на автомобиль
async def car_info(update: Update, context: CallbackContext):
    url = update.message.text  # Получаем ссылку на автомобиль

    # Сообщение о том, что данные переданы в обработку
    await update.message.reply_text(
        "Данные переданы в обработку. Пожалуйста, подождите..."
    )

    # Ваш код для обработки ссылки и получения информации об авто
    result = get_car_info(url)

    # Отправка результата пользователю
    await update.message.reply_text(result, parse_mode="HTML")


def main():
    # Ваш токен
    bot_token = "8122197139:AAESd2hmle6YJ8Qdvwbj2rAU1AHZI0tR-hA"

    # Создание экземпляра Application
    application = Application.builder().token(bot_token).build()

    # Добавление обработчика команды /start
    application.add_handler(CommandHandler("start", start))

    # Добавление обработчика для всех текстовых сообщений (ссылка на авто)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, car_info))

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()
