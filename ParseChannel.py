import os
import asyncio
from telethon import TelegramClient

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

async def parse_last_messages(channel_id):
    """
    Connects to Telegram, retrieves the last 30 messages from a channel ID or username,
    prints the message text, and downloads images using the custom name format.
    """
    # 1. Automatic Formatting for Channel IDs
    # If the user passed a positive integer, automatically format it into a marked channel ID
    if isinstance(channel_id, int) and channel_id > 0:
        formatted_id = int(f"-100{channel_id}")
        print(f"Auto-formatting ID {channel_id} to marked channel ID: {formatted_id}")
        channel_id = formatted_id

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        await client.start()
        print(f"Connected to Telegram. Fetching messages...")

        # Resolve the entity
        entity = await client.get_input_entity(channel_id)

        count = 0
        async for message in client.iter_messages(entity, limit=5):
            count += 1
            text_preview = (message.text[:50].replace("\n", " ") + "...") if message.text else "[No Text]"
            print(f"\n[{count}/30] Msg ID: {message.id} | Date: {message.date} | Text: {text_preview}")

            # Check for images (regular photos or files with image MIME-types)
            is_image = False
            if message.photo:
                is_image = True
            elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
                is_image = True

            if is_image:
                extension = message.file.ext if (message.file and message.file.ext) else '.jpg'

                # Format: channel-id_message-id_indexofmedia.format
                # Standard channel IDs are negative, so we strip the minus sign for a cleaner file name
                clean_channel_id = str(channel_id).replace("-", "")
                filename = f"{clean_channel_id}_{message.id}_0{extension}"
                target_path = os.path.join(DOWNLOAD_DIR, filename)

                if os.path.exists(target_path):
                    print(f"  -> Image already downloaded: {filename} (Skipping)")
                else:
                    print(f"  -> New image found. Downloading: {filename}...")
                    await client.download_media(message, file=target_path)
                    print(f"  -> Download complete.")
            else:
                print("  -> No image attached.")

    except ValueError as e:
        print(f"\nError: {e}")
        print("\nSuggestions to resolve this:")
        print("1. Ensure your account is actually a member of or has viewed this channel before.")
        print("2. If it's a public channel, try using its string username (e.g., '@public_channel_name') instead of the number.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        await client.disconnect()
        print("\nDisconnected.")

if __name__ == '__main__':
    # Enter your channel ID
    TARGET_CHANNEL_ID = 2432930513

    # Run the asynchronous function
    asyncio.run(parse_last_messages(TARGET_CHANNEL_ID))
