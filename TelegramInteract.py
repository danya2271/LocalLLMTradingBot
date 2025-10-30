import requests

def send_message_to_all_users(bot_token: str, user_ids: list[int], message: str):
    """
    Sends a text message to a list of Telegram user IDs using a bot token.

    Args:
        bot_token (str): The token for your Telegram bot.
        user_ids (list[int]): A list of integer user IDs to send the message to.
        message (str): The text message to send.
    """
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    print(f"Attempting to send a message to {len(user_ids)} user(s)...")

    for user_id in user_ids:
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
            #     print(f"Response Body: {e.response.text}")
