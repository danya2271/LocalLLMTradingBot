import requests
import os
import time
import json

LAST_UPDATE_ID_FILE = 'last_update_id.txt'
SLIPPAGE_CONFIG_FILE = 'slippage_config.json'
DATA_CONFIG_FILE = 'data_config.json'

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

# --- Slippage Configuration Functions ---
def get_slippage_config():
    """Reads the slippage configuration from a JSON file."""
    try:
        with open(SLIPPAGE_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_config = {'buy_slippage': 0.1, 'sell_slippage': 0.1}
        set_slippage_config(default_config['buy_slippage'], default_config['sell_slippage'])
        return default_config

def set_slippage_config(buy_slippage: float, sell_slippage: float):
    """Saves the slippage configuration to a JSON file."""
    config = {'buy_slippage': buy_slippage, 'sell_slippage': sell_slippage}
    with open(SLIPPAGE_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Slippage config updated: Buy={buy_slippage}%, Sell={sell_slippage}%")

# --- Data Fetch Configuration Functions ---
def get_data_config():
    """Reads the data fetch configuration from a JSON file."""
    try:
        with open(DATA_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_config = {'1m': 80, '5m': 20, '15m': 15, '1H': 18}
        set_data_config(default_config)
        return default_config

def set_data_config(config: dict):
    """Saves the data fetch configuration to a JSON file."""
    with open(DATA_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"Data fetch config updated: {config}")

def get_trading_coin():
    """Reads the trading coin from the config file, with a default."""
    try:
        with open('coin_config.txt', 'r') as f:
            coin = f.read().strip()
            return coin if coin else 'SOL-USDT'
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
    command = text.lower().split()[0] if text else ""

    if command == '/setcoin':
        parts = text.split()
        if len(parts) == 2:
            new_coin = parts[1]
            set_trading_coin(new_coin)
            reply_message = f"Trading coin has been set to `{new_coin.upper()}`."
        else:
            reply_message = "Invalid format. Use `/setcoin COIN-PAIR` (e.g., `/setcoin ETH-USDT`)."
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/getcoin':
        current_coin = get_trading_coin()
        reply_message = f"The current trading coin is `{current_coin}`."
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/setslippage':
        parts = text.split()
        if len(parts) == 3:
            try:
                buy_slip = float(parts[1])
                sell_slip = float(parts[2])
                set_slippage_config(buy_slip, sell_slip)
                reply_message = (f"✅ Slippage updated.\n"
                                 f"- Buy orders will be placed `{buy_slip}%` below the target price.\n"
                                 f"- Sell orders will be placed `{sell_slip}%` above the target price.")
            except ValueError:
                reply_message = "Invalid format. Please use numbers for slippage values."
        else:
            reply_message = "Invalid format. Use `/setslippage <buy_%> <sell_%>` (e.g., `/setslippage 0.1 0.1`)."
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/getslippage':
        config = get_slippage_config()
        reply_message = (f"Current slippage settings:\n"
                         f"- Buy Price Slippage: `{config['buy_slippage']}%`\n"
                         f"- Sell Price Slippage: `{config['sell_slippage']}%`")
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/setdata':
        parts = text.split()
        if len(parts) == 5:
            try:
                config = {'1m': int(parts[1]), '5m': int(parts[2]), '15m': int(parts[3]), '1H': int(parts[4])}
                set_data_config(config)
                reply_message = f"✅ Data fetch rows updated:\n" + "\n".join([f"- {k}: `{v}` rows" for k, v in config.items()])
            except ValueError:
                reply_message = "Invalid format. Please use integers for row counts."
        else:
            reply_message = "Invalid format. Use `/setdata <1m> <5m> <15m> <1H>` (e.g., `/setdata 80 20 15 18`)."
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/getdata':
        config = get_data_config()
        reply_message = "Current data fetch settings (rows per timeframe):\n" + "\n".join([f"- {k}: `{v}`" for k, v in config.items()])
        send_single_message(bot_token, chat_id, reply_message)

    elif command == '/help':
        reply_message = (
            "Available commands:\n"
            "`/setcoin COIN-PAIR` - Set the coin to trade.\n"
            "`/getcoin` - See the currently traded coin.\n"
            "`/setslippage <buy_%> <sell_%>` - Set price slippage for orders.\n"
            "`/getslippage` - View current slippage settings.\n"
            "`/setdata <1m> <5m> <15m> <1H>` - Set rows to fetch for market data.\n"
            "`/getdata` - View current data fetch settings."
        )
        send_single_message(bot_token, chat_id, reply_message)

    elif text.startswith('/'):
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
