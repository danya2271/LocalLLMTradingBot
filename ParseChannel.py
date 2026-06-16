import os
import re
import asyncio
from telethon import TelegramClient
import json
from datetime import datetime, timezone, timedelta
from Database import is_message_checked, mark_message_checked, process_extracted_data
from llamacppInteract import llamacppBot
from llamacpp_config import LLM_API_KEY, LLM_HOST

try:
    import easyocr
except ImportError:
    easyocr = None

# Import your configurations
try:
    from TelegramReaderConfig import API_ID, API_HASH, SESSION_NAME
except ImportError:
    print("Error: Could not find TelegramReaderConfig.py in the same directory.")
    print("Please make sure TelegramReaderConfig.py exists and is correctly configured.")
    exit(1)

# Directory to save the downloaded images
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

OCR_READER = None
def get_ocr_reader():
    global OCR_READER
    if OCR_READER is None and easyocr is not None:
        print("Initializing OCR Engine (loading models)...")
        # Support both Russian and English
        OCR_READER = easyocr.Reader(['ru', 'en'], gpu=False)
    return OCR_READER

def clean_and_normalize_text(lines):
    """
    Cleans up common OCR character substitutions and filters out background noise.
    """
    cleaned_lines = []

    # Map of common Cyrillic characters to their Latin/Numeric lookalikes for code blocks
    cyrillic_to_latin = {
        'Х': 'X', 'З': '3', 'О': '0', 'А': 'A', 'В': 'B', 'Е': 'E',
        'К': 'K', 'М': 'M', 'Н': 'H', 'Р': 'P', 'С': 'C', 'Т': 'T', 'У': 'Y',
        'х': 'x', 'з': '3', 'о': '0', 'а': 'a', 'в': 'b', 'е': 'e'
    }

    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        # --- FIX APPLIED HERE ---
        # 1. Fix common punctuation errors in percentages (e.g., -].14% or -I.14% -> -1.14%)
        cleaned = re.sub(r'([-\+])?[\]\[I|l!1sS](\.\d+%)', r'\g<1>1\g<2>', cleaned)
        # Handle cases where the '1' in -1.14% was read as a bracket/slash
        cleaned = re.sub(r'([-\+])[\]\[I|l!](\d+\.\d+%)', r'\g<1>1\g<2>', cleaned)
        # ------------------------

        # 2. Fix lookalike characters in potential uppercase alphanumeric codes (like X3LNUR)
        if re.match(r'^[A-Z0-9\u0410-\u042f]{5,10}$', cleaned):
            normalized = "".join(cyrillic_to_latin.get(char, char) for char in cleaned)
            cleaned = normalized

        # 3. Filter out highly likely noise (1-2 characters that are just stray symbols/letters)
        if len(cleaned) <= 2 and not cleaned.isdigit() and cleaned not in ['+', '-']:
            continue

        cleaned_lines.append(cleaned)

    return cleaned_lines

def parse_trading_card(lines):
    """
    Parses the cleaned text lines to extract structured trading parameters.
    """
    data = {
        "Symbol": None,
        "Direction": None,
        "Entry_Price": None,
    }

    full_text = "\n".join(lines)

    for i, line in enumerate(lines):
        # Detect Trading Pair (standard format like NIGHTUSDT)
        if "USDT" in line:
            data["Symbol"] = line

        # Detect Direction
        if "лонг" in line.lower() or "long" in line.lower():
            data["Direction"] = "Long"
        elif "шорт" in line.lower() or "short" in line.lower():
            data["Direction"] = "Short"

        # Detect Entry and Last/Mark Prices
        if "цена" in line.lower() or "price" in line.lower():
            # Check the next line for the corresponding numerical value
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                price_match = re.search(r'\b\d+[\.,]\d+\b', next_line)
                if price_match:
                    price_val = price_match.group(0).replace(',', '.')
                    if "вход" in line.lower() or "entry" in line.lower():
                        data["Entry_Price"] = price_val

    return data


async def recognize_text_from_message(channel_id, message_id):
    reader = get_ocr_reader()
    if not reader:
        print("Error: OCR Engine is not initialized.")
        return

    if isinstance(channel_id, int) and channel_id > 0:
        channel_id = int(f"-100{channel_id}")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        await client.start()
        entity = await client.get_input_entity(channel_id)
        message = await client.get_messages(entity, ids=message_id)

        print("\n--- Original Telegram Message Text ---")
        if message.text:
            print(message.text)
        else:
            print("[No text/caption in the Telegram message]")
        print("-" * 40)

        if not message:
            print(f"Could not find message ID {message_id}.")
            return

        # Album handling
        messages_to_process = []
        if message.grouped_id:
            async for msg in client.iter_messages(entity, min_id=max(1, message_id - 15), max_id=message_id + 15):
                if msg.grouped_id == message.grouped_id:
                    messages_to_process.append(msg)
            messages_to_process.sort(key=lambda m: m.id)
        else:
            messages_to_process = [message]

        # Download media
        image_paths = []
        for index, msg in enumerate(messages_to_process):
            is_image = msg.photo or (msg.document and msg.document.mime_type and msg.document.mime_type.startswith('image/'))
            if is_image:
                extension = msg.file.ext if (msg.file and msg.file.ext) else '.jpg'
                clean_channel = str(channel_id).replace("-", "")
                filename = f"{clean_channel}_{msg.id}_{index}{extension}"
                target_path = os.path.join(DOWNLOAD_DIR, filename)

                if not os.path.exists(target_path):
                    await client.download_media(msg, file=target_path)
                image_paths.append(target_path)

        # Process OCR on each image
        for path in image_paths:
            print(f"\nProcessing: {os.path.basename(path)}")

            # 1. Raw Extraction
            raw_results = reader.readtext(path)
            raw_lines = [box[1] for box in raw_results]

            # 2. Cleanup and Normalization
            cleaned_lines = clean_and_normalize_text(raw_lines)

            # 3. Structured Data Extraction
            structured_data = parse_trading_card(cleaned_lines)

            # Print Raw text for debug
            # print("\n--- Cleaned Text Output ---")
            # print("\n".join(cleaned_lines))

            # Print parsed parameters
            print("\n--- Extracted Structured Data ---")
            for key, val in structured_data.items():
                print(f"{key:15}: {val}")
            print("=" * 40)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()

bot = llamacppBot(LLM_API_KEY, host=LLM_HOST)

def ask_llm_for_json(text_content):
    """Sends the combined OCR + text to the LLM to extract JSON data."""
    prompt = f"""
    ROLE: You are an expert at extracting crypto trading signals from Telegram messages.
    Extract the following information from the text into a JSON object.

    RULES:
    1. "symbol": The trading pair (e.g., "ATOMUSDT"). Return null if not found.
    2. "direction": 1 if the signal says LONG or BUY. 0 if it says SHORT or SELL. Return null if not found.
    3. "entry_price": The numerical entry price. Return null if not found.
    4. "take_profit": The LOWEST take profit target if multiple are given (e.g., if TP1=1.825 and TP2=1.9, return 1.825). Return null if not found.
    5. "stop_loss": The numerical stop loss price. Return null if not found.
    6. Only return valid JSON. Do not include any explanations.

    TEXT TO PARSE:
    "{text_content}"

    OUTPUT FORMAT:
    {{
        "symbol": "null",
        "direction": null,
        "entry_price": null,
        "take_profit": null,
        "stop_loss": null
    }}
    """
    bot.add_to_message(prompt)
    response = bot.send_and_reset_message()

    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"Failed to parse JSON from LLM: {e}")

    return {"symbol": None, "direction": None, "entry_price": None, "take_profit": None, "stop_loss": None}

async def parse_last_messages(channel_id):
    if isinstance(channel_id, int) and channel_id > 0:
        channel_id = int(f"-100{channel_id}")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        await client.start()
        entity = await client.get_input_entity(channel_id)

        now_utc = datetime.now(timezone.utc)

        async for message in client.iter_messages(entity, limit=10):
            # CONDITION 2: Message is relevant (posted less than 10 min ago)
            if (now_utc - message.date) > timedelta(minutes=10):
                continue

            # CONDITION 1: Message is checked?
            if is_message_checked(message.id):
                continue

            print(f"\n[NEW] Processing Message ID: {message.id}")
            mark_message_checked(message.id)

            full_extracted_text = message.text or ""

            # Check for images and do OCR if needed
            is_image = message.photo or (message.document and message.document.mime_type and message.document.mime_type.startswith('image/'))
            if is_image:
                # Note: Assumes you have your target_path logic from your original code here
                target_path = os.path.join(DOWNLOAD_DIR, f"temp_{message.id}.jpg")
                await client.download_media(message, file=target_path)

                reader = get_ocr_reader()
                if reader:
                    raw_results = reader.readtext(target_path)
                    ocr_text = " ".join([box[1] for box in raw_results])
                    full_extracted_text += "\n" + ocr_text

            if not full_extracted_text.strip():
                continue

            # CONDITION 3: Message is useful (Checked by LLM)
            extracted_json = ask_llm_for_json(full_extracted_text)
            print(f"LLM Extracted: {extracted_json}")

            # Save/Merge to Database
            is_useful = process_extracted_data(extracted_json)
            if is_useful:
                print("Message contained useful data. Database updated.")
            else:
                print("Message did not contain useful trading data.")

    except Exception as e:
        print(f"Error in parse_last_messages: {e}")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    # Enter your channel ID
    TARGET_CHANNEL_ID = 2432930513
    TARGET_MESSAGE_ID = 4244

    # Run the asynchronous function
    asyncio.run(parse_last_messages(TARGET_CHANNEL_ID))
    asyncio.run(recognize_text_from_message(TARGET_CHANNEL_ID, TARGET_MESSAGE_ID))
