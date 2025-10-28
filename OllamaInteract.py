import ollama
from Bot_config import MODEL_NAME, OLLAMA_HOST

class OllamaBot:
    def __init__(self, model=MODEL_NAME, host=OLLAMA_HOST):
        self.model = model
        self.client = ollama.Client(host=host)
        self.message_parts = []

    def add_to_message(self, text: str):
        self.message_parts.append(text)
        print(f"Added to message: '{text}'")

    def _build_message(self):
        return " ".join(self.message_parts)

    def send_message(self):
        full_message = self._build_message()
        if not full_message:
            return "Message is empty. Nothing to send"

        print(f"\nОтправка сообщения: '{full_message}'")
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': full_message}]
            )
            return response['message']['content']
        except Exception as e:
            return f"An error occured: {e}"

    def reset_message(self):
        self.message_parts = []
        print("Message is reset.")

    def send_and_reset_message(self):
        response = self.send_message()
        self.reset_message()
        return response
