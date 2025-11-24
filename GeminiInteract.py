import google.generativeai as genai
import os
from Gemini_config import API_KEY, GEMINI_MODEL
from google.generativeai.types import HarmCategory, HarmBlockThreshold

class GeminiBot:
    def __init__(self):
        # Replace with your actual key or load from Config
        # It's better to put this in your Config.py file
        self.api_key = API_KEY

        genai.configure(api_key=self.api_key)

        # Configuration to force JSON response
        generation_config = {
            "temperature": 0.2, # Low temperature for more deterministic trading logic
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }

        # Disable safety filters so trading terms don't trigger blocks
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # Use Gemini 1.5 Pro
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        self.message_buffer = []

    def add_to_message(self, content):
        """Accumulates text to send in one go."""
        self.message_buffer.append(str(content))

    def send_and_reset_message(self):
        """Sends the accumulated buffer to Gemini and returns the text."""
        try:
            full_prompt = "\n\n".join(self.message_buffer)

            # Generate content
            chat_session = self.model.start_chat(history=[])
            response = chat_session.send_message(full_prompt)

            # Clear buffer for next loop
            self.message_buffer = []

            # Return the clean text (which will be JSON)
            return response.text

        except Exception as e:
            print(f"Error communicating with Gemini: {e}")
            self.message_buffer = []
            # Return a safe fallback or empty JSON string
            return '{"reasoning": "API Error", "actions": ["WAIT[60]"]}'
