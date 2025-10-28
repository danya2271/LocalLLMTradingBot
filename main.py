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
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        bot.add_to_message(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            if timeframe == '1m':
                out = data.sort_index().tail(30)
            if timeframe == '5m':
                out = data.sort_index().tail(20)
            if timeframe == '15m':
                out = data.sort_index().tail(15)
            if timeframe == '1H':
                out = data.sort_index().tail(10)
            # Sort by timestamp to ensure the latest data is last
            print(out)
            log_message(out)
            bot.add_to_message(out.to_string())
        else:
            print(data)
            log_message(data)
            bot.add_to_message(data.to_string())
    bot.add_to_message("""
You are an autonomous trading analyst AI. Your primary objective is to maximize the USDT balance of the account by trading the BTC/USDT pair. You must operate under the following rules:

1.  **Analyze the Data**: You will be given the current account balance and recent candlestick data for BTC/USDT across multiple timeframes (1-hour, 15-minute, 5-minute, and 1-minute).
2.  **Make a Single Decision**: Based on your analysis, you must choose one of three actions: `BUY`, `SELL`, or `HOLD`.
3.  **Risk Management**:
    *   When issuing a `BUY` order, you can only use up to 100% of the available USDT balance.
    *   When issuing a `SELL` order, you can only sell up to 100% of the available BTC balance.
4.  **Logical Reasoning**: Before stating your final decision, you must provide a brief, step-by-step analysis of the market data. Consider the trends, volume, and any potential patterns across the different timeframes.
5.  **Strict Output Format**: Your final response must be a JSON object. No other text or explanation should come after the JSON object.
**Current Account and Market Data:**""")
    bot.add_to_message(Bal)
    print(bot.send_and_reset_message())

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
