import requests

class llamacppBot:
    def __init__(self, api_key, host):
        self.api_key = api_key

        # 1. Clean up the host URL (removes trailing slashes and Web UI fragments like /#)
        self.host = host.split('/#')[0].rstrip('/')

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.message = None # Initialize to prevent AttributeError

    def add_to_message(self, text: str):
        self.message = text
        print(f"Added to message: '{text}'")

    def _build_message(self):
        return self.message

    def send_message(self):
        full_message = self._build_message()
        if not full_message:
            return "Message is empty. Nothing to send"

        print(f"\nОтправка сообщения: '{full_message}'")
        try:
            # 2. Use the standard OpenAI-compatible endpoint built into llama.cpp
            endpoint = f"{self.host}/v1/chat/completions"

            # 3. Correctly structure the JSON payload
            payload = {
                "messages": [
                    {"role": "user", "content": full_message}
                ]
            }

            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload # requests handles json.dumps automatically here
            )
            response.raise_for_status()

            # 4. Correctly parse the standard response structure
            return response.json()['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            return f"An error occured: {e}"

    def reset_message(self):
        self.message = None
        print("Message is reset.")

    def send_and_reset_message(self):
        response = self.send_message()
        self.reset_message()
        return response

# Make sure your LLM_HOST in llamacpp_config is set to just the base URL,
# e.g., "http://91.218.xxx.xxx:8080"
from llamacpp_config import LLM_API_KEY, LLM_HOST
bot = llamacppBot(LLM_API_KEY, host=LLM_HOST)

# Example usage:
# bot.add_to_message("Hello, how are you?")
# print(bot.send_and_reset_message())
