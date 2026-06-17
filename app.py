"""
Kvadro_Fun — backend (Flask)
=============================
Приймає заявки з форми на сайті, валідує дані та надсилає
повідомлення в Telegram-чат через Bot API.

Запуск:
    pip install flask requests
    python app.py

Перед запуском заповни змінні TELEGRAM_BOT_TOKEN та TELEGRAM_CHAT_ID нижче
(або встанови їх як змінні середовища).
"""

import os
import re
from datetime import datetime

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

# ---------------------------------------------------------------------------
# КОНФІГУРАЦІЯ TELEGRAM
# ---------------------------------------------------------------------------
# Отримати токен бота: напиши @BotFather в Telegram -> /newbot
# Отримати chat_id: напиши боту будь-яке повідомлення, потім відкрий
#   https://api.telegram.org/bot<TOKEN>/getUpdates
#   і знайди поле "chat":{"id": ...}
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ВСТАВ_СВІЙ_ТОКЕН_СЮДИ")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "ВСТАВ_ID_ЧАТУ_СЮДИ")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Дозволені значення для поля "service" (захист від довільних даних)
ALLOWED_SERVICES = {"Квадроцикли", "Велосипеди", "Тур на Маковицю"}

# Регулярка для українського номера у форматі +380 (XX) XXX-XX-XX
PHONE_RE = re.compile(r"^\+380\s?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$")


# ---------------------------------------------------------------------------
# СТАТИКА (index.html)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ---------------------------------------------------------------------------
# ВАЛІДАЦІЯ
# ---------------------------------------------------------------------------
def validate_payload(data: dict):
    """Повертає (is_valid: bool, error_message: str | None)."""

    if not isinstance(data, dict):
        return False, "Невірний формат даних."

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    service = (data.get("service") or "").strip()
    dt_raw = (data.get("datetime") or "").strip()

    if not name or len(name) < 2:
        return False, "Вкажіть, будь ласка, ваше ім'я (мінімум 2 символи)."

    if len(name) > 60:
        return False, "Ім'я занадто довге."

    if not PHONE_RE.match(phone):
        return False, "Невірний формат телефону. Приклад: +380 (99) 123-45-67"

    if service not in ALLOWED_SERVICES:
        return False, "Оберіть, будь ласка, послугу зі списку."

    if not dt_raw:
        return False, "Вкажіть дату та час."

    try:
        # datetime-local з браузера приходить у формі YYYY-MM-DDTHH:MM
        datetime.fromisoformat(dt_raw)
    except ValueError:
        return False, "Невірний формат дати/часу."

    return True, None


def format_datetime(dt_raw: str) -> str:
    """Перетворює ISO-рядок у читабельний формат ДД.МММ.РРРР ГГ:ХХ."""
    try:
        dt = datetime.fromisoformat(dt_raw)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return dt_raw


# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------
def send_telegram_message(name: str, phone: str, service: str, dt_formatted: str) -> bool:
    """Надсилає сформоване повідомлення в Telegram-чат. Повертає True/False."""

    text = (
        "🚨 НОВА ЗАЯВКА НА САЙТІ KVADRO_FUN!\n"
        f"👤 Ім'я: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🏍️ Що обрали: {service}\n"
        f"📅 Дата/Час: {dt_formatted}"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    try:
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        app.logger.error("Помилка надсилання в Telegram: %s", exc)
        return False


# ---------------------------------------------------------------------------
# API ENDPOINT
# ---------------------------------------------------------------------------
@app.route("/api/submit-request", methods=["POST"])
def submit_request():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify(success=False, error="Очікувався JSON у тілі запиту."), 400

    is_valid, error_message = validate_payload(data)
    if not is_valid:
        return jsonify(success=False, error=error_message), 400

    name = data["name"].strip()
    phone = data["phone"].strip()
    service = data["service"].strip()
    dt_formatted = format_datetime(data["datetime"].strip())

    telegram_ok = send_telegram_message(name, phone, service, dt_formatted)

    if not telegram_ok:
        # Дані валідні, але сповіщення не доставлено — повідомляємо клієнта,
        # щоб він міг зв'язатись напряму.
        return (
            jsonify(
                success=False,
                error="Заявку отримано, але не вдалося надіслати сповіщення. Зателефонуйте нам напряму.",
            ),
            502,
        )

    return jsonify(success=True, message="Заявку успішно надіслано!")


# ---------------------------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------------------------
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
