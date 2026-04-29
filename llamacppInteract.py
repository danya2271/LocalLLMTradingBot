import requests
import json

class llamacppBot:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://localhost:8000"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def add_to_message(self, text: str):
        # For llama.cpp, we can just append text to a single message
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
            response = requests.post(
                f"{self.base_url}/chat",
                headers=self.headers,
                data=json.dumps([{'role': 'user', 'content': full_message}])
            )
            response.raise_for_status()
            return response.json()['message']['content']
        except requests.exceptions.RequestException as e:
            return f"An error occured: {e}"

    def reset_message(self):
        self.message = None
        print("Message is reset.")

    def send_and_reset_message(self):
        response = self.send_message()
        self.reset_message()
        return response
