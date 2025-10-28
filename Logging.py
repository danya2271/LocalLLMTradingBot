import os
from datetime import datetime
import sys

def log_message(message):
    """
    Appends a timestamped message to a log file inside a 'data' subdirectory.
    The 'data' folder is created in the same directory as the script.
    """
    try:
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        else:
            script_dir = os.path.dirname(os.path.realpath(__file__))
        data_directory = os.path.join(script_dir, "data")
        os.makedirs(data_directory, exist_ok=True)

        log_file_path = os.path.join(data_directory, 'trading_bot.log')

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file_path, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")

    except Exception as e:
        print(f"Error: Could not write to log file. {e}")
