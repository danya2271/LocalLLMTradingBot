import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_IDS = [int(user_id) for user_id in os.getenv("TELEGRAM_USER_IDS", "123456789").split(",")]
