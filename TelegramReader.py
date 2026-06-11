import asyncio
from TelegramReaderConfig import SESSION_NAME, API_ID, API_HASH
from telethon import TelegramClient

async def main():
    # Initialize the Telegram Client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    # Start the client. This will prompt you for your phone number
    # and login code in the terminal upon the first run.
    await client.start()
    print("Successfully connected to Telegram!")

    try:
        # Fetch the top 20 active chats/channels
        print("\nFetching your recent chats and channels...")
        dialogs = await client.get_dialogs(limit=20)

        # Display the list of dialogs
        print("\n--- Available Chats/Channels ---")
        for idx, dialog in enumerate(dialogs):
            chat_type = "Channel" if dialog.is_channel else ("Group" if dialog.is_group else "User")
            print(f"[{idx}] {dialog.name} (ID: {dialog.id}) - Type: {chat_type}")

        # Ask the user to select a chat
        choice_input = input("\nEnter the index number of the chat to read messages from: ")
        try:
            choice = int(choice_input)
            if 0 <= choice < len(dialogs):
                selected_chat = dialogs[choice]
                print(f"\n--- Fetching the last 10 messages from: {selected_chat.name} ---")

                # Fetch and print the 10 most recent messages
                async for message in client.iter_messages(selected_chat, limit=10):
                    # Get sender details if available
                    sender = await message.get_sender()
                    sender_name = getattr(sender, 'first_name', 'System/Channel') if sender else 'System/Channel'

                    # Handle empty/media messages gracefully
                    text = message.text if message.text else "[Media or Service Message]"

                    print(f"[{message.date.strftime('%Y-%m-%d %H:%M:%S')}] {sender_name}: {text}")
                    print("-" * 50)
            else:
                print("Invalid index selection.")
        except ValueError:
            print("Please enter a valid number.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Properly disconnect the client
        await client.disconnect()

if __name__ == '__main__':
    # Run the main async loop
    asyncio.run(main())
