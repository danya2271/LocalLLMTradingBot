
import pandas as pd
import time
import threading
from Get_market import get_okx_market_data
from Get_balance import GetBal
from Logging import log_message
from OllamaInteract import OllamaBot
from OKXinteract import OKXTrader
from ParseFuncLLM import parse_and_execute_commands
from Config import *
from TelegramConfig import *
from TelegramInteract import send_message_to_all_users, get_trading_coin, poll_telegram_updates

trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
bot = OllamaBot()

def HInfoSend(risk,coin):
    Bal = GetBal(coin)
    open_orders_info = trader.get_open_orders(coin)
    open_positions_info = trader.get_open_positions(coin)
    max_order_limits = trader.get_max_order_limits(coin)
    print(Bal)
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        bot.add_to_message(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            if timeframe == '1m':
                out = data.tail(40)
            if timeframe == '5m':
                out = data.tail(20)
            if timeframe == '15m':
                out = data.tail(15)
            if timeframe == '1H':
                out = data.tail(0)
            # Sort by timestamp to ensure the latest data is last
            print(out)
            log_message(out)
            bot.add_to_message(out.to_string())
        else:
            print(data)
            log_message(data)
            bot.add_to_message(data.to_string())
    bot.add_to_message(F"""
You are an autonomous trading analyst AI. Your primary objective is to maximize the USDT balance of the account by trading the {coin} pair. You must operate under the following rules:

1.  **Analyze the Data**: You will be given the current account balance and recent candlestick data for {coin}.
2.  **Make a Decision**: Based on your analysis, you must define a list of actions to be executed.
3.  **Risk Management**:
    *   When issuing `BUY` orders, the total quantity must not exceed 100% of the available USDT balance.
    *   When issuing `SELL` orders, the total quantity must not exceed 100% of the available BTC balance.
4.  **Logical Reasoning**: Before your final decision, provide a brief, step-by-step analysis of the market data.
5.  **Strict Output Format**: Your final response MUST be a JSON object with a single key, `"actions"`. The value of this key MUST be a list of STRINGS. No other text or explanation should come after the JSON object. Each string must strictly conform to one of the following formats:
    *   `BUY[PRICE][QUANTITY][{coin}]`
    *   `SELL[PRICE][QUANTITY][{coin}]`
    *   `CANCEL[ORDER_ID][{coin}]`
    *   `HOLD`

---
**CORRECT FORMAT EXAMPLE (A list of strings):**
```json
{{
  "actions": [
    "SELL[PRICE][BTC-USDT]",
    "CANCEL[ORDER_ID][BTC-USDT]"
  ]
}}
```
""")
    bot.add_to_message(Bal)
    bot.add_to_message(open_orders_info)
    bot.add_to_message(max_order_limits)
    bot.add_to_message(open_positions_info)
    llm_answ = bot.send_and_reset_message()
    print(llm_answ)
    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, llm_answ)
    parse_and_execute_commands(trader, llm_answ)

if __name__ == '__main__':
    # Start the Telegram listener in a background thread
    telegram_thread = threading.Thread(target=poll_telegram_updates, args=(TELEGRAM_BOT_TOKEN,), daemon=True)
    telegram_thread.start()

    interval_seconds = 150

    try:
        print("Starting the main trading loop. Press Ctrl+C to stop.")
        while True:
            # Get the current coin to trade from the config file
            current_coin = get_trading_coin()
            print(f"\n--- Running analysis for {current_coin} ---")

            # Run the main trading logic
            HInfoSend(0, current_coin)

            print(f"--- Waiting for {interval_seconds / 60:.1f} minutes before next run... ---")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")

