import requests
import os
import time

# File to store the ID of the last processed update
LAST_UPDATE_ID_FILE = 'last_update_id.txt'

def get_last_update_id():
    """Reads the last update ID from its file."""
    if not os.path.exists(LAST_UPDATE_ID_FILE):
        return None
    with open(LAST_UPDATE_ID_FILE, 'r') as f:
        try:
            return int(f.read().strip())
        except (ValueError, TypeError):
            return None

def save_last_update_id(update_id):
    """Saves the last update ID to its file."""
    with open(LAST_UPDATE_ID_FILE, 'w') as f:
        f.write(str(update_id))

def send_message_to_all_users(bot_token: str, user_ids: list[int], message: str):
    """
    Sends a text message to a list of Telegram user IDs using a bot token.

    Args:
        bot_token (str): The token for your Telegram bot.
        user_ids (list[int]): A list of integer user IDs to send the message to.
        message (str): The text message to send.
    """
    print(f"Attempting to send a message to {len(user_ids)} user(s)...")
    for user_id in user_ids:
        send_single_message(bot_token, user_id, message)


def send_single_message(bot_token: str, user_id: int, message: str):
    """Sends a single message to a specific user."""
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': user_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(base_url, data=payload)
        response.raise_for_status()
        print(f"Successfully sent message to user ID: {user_id}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message to user ID: {user_id}. Error: {e}")

def get_trading_coin():
    """Reads the trading coin from the config file, with a default."""
    try:
        with open('coin_config.txt', 'r') as f:
            coin = f.read().strip()
            if not coin:
                return 'SOL-USDT'
            return coin
    except FileNotFoundError:
        set_trading_coin('SOL-USDT')
        return 'SOL-USDT'

def set_trading_coin(new_coin: str):
    """Saves the new trading coin to the config file."""
    with open('coin_config.txt', 'w') as f:
        f.write(new_coin.upper())
    print(f"Trading coin has been updated to: {new_coin.upper()}")

def handle_telegram_command(bot_token: str, message: dict):
    """Handles incoming commands and messages from users."""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()

    if text.lower().startswith('/setcoin'):
        parts = text.split()
        if len(parts) == 2:
            new_coin = parts[1]
            set_trading_coin(new_coin)
            reply_message = f"Trading coin has been set to `{new_coin.upper()}`."
        else:
            reply_message = "Invalid format. Use `/setcoin COIN-PAIR` (e.g., `/setcoin ETH-USDT`)."
        send_single_message(bot_token, chat_id, reply_message)

    elif text.lower() == '/getcoin':
        current_coin = get_trading_coin()
        reply_message = f"The current trading coin is `{current_coin}`."
        send_single_message(bot_token, chat_id, reply_message)

    elif text.lower() == '/help':
        reply_message = (
            "Available commands:\n"
            "`/setcoin COIN-PAIR` - Set the coin to trade.\n"
            "`/getcoin` - See the currently traded coin."
        )
        send_single_message(bot_token, chat_id, reply_message)
    else:
        reply_message = "Unknown command. Try `/help` for a list of commands."
        send_single_message(bot_token, chat_id, reply_message)


def poll_telegram_updates(bot_token: str):
    """
    Continuously polls Telegram for new messages and handles them.
    This function is designed to be run in a separate thread.
    """
    print("Telegram message listener started...")
    last_update_id = get_last_update_id()

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    while True:
        offset = last_update_id + 1 if last_update_id else None
        params = {'timeout': 100, 'offset': offset}

        try:
            response = requests.get(url, params=params, timeout=110)
            response.raise_for_status()
            updates = response.json().get('result', [])

            if updates:
                for update in updates:
                    if 'message' in update and 'text' in update['message']:
                        handle_telegram_command(bot_token, update['message'])

                    last_update_id = update['update_id']
                    save_last_update_id(last_update_id)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching Telegram updates: {e}")
            time.sleep(15)
        except Exception as e:
            print(f"An unexpected error occurred in the Telegram poller: {e}")
            time.sleep(15)
