from Get_market import get_okx_market_data
from Get_balance import GetBal
import pandas as pd
import time
from Logging import log_message
from OllamaInteract import OllamaBot

bot = OllamaBot()

def HInfoSend(risk,coin):
    Bal = GetBal()
    print(Bal)
    bot.add_to_message(Bal)
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            # Sort by timestamp to ensure the latest data is last
            print(data.sort_index().tail(50))
            log_message(data.sort_index().tail(50))
            bot.add_to_message(data.sort_index().tail(50))
            bot.send_and_reset_message()
        else:
            print(data)
            log_message(data)
            bot.add_to_message(data)
            bot.send_and_reset_message()

if __name__ == '__main__':
    interval_seconds = 300

    try:
        print("Starting the loop. Press Ctrl+C to stop.")
        while True:
            HInfoSend(0,'BTC-USDT')
            print(f"--- Waiting for {interval_seconds / 60:.0f} minutes before next run... ---")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")
