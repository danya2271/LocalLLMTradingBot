
import pandas as pd
import time
import threading
from Get_market import get_okx_market_data, get_okx_current_price
from Get_balance import GetBal
from Logging import log_message
from OllamaInteract import OllamaBot #TODO shift to llama.cpp
from OKXinteract import OKXTrader
from ParseFuncLLM import parse_and_execute_commands
from Config import *
from TelegramConfig import *
from TelegramInteract import send_message_to_all_users, get_trading_coin, poll_telegram_updates, get_data_config

trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
bot = OllamaBot()

def HInfoSend(risk,coin):
    data_config = get_data_config()
    Bal = GetBal(coin)
    open_orders_info = trader.get_open_orders(coin)
    open_positions_info = trader.get_open_positions(coin)
    max_order_limits = trader.get_max_order_limits(coin)
    current_price = get_okx_current_price(coin)
    print(Bal)
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        bot.add_to_message(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            rows_to_fetch = data_config.get(timeframe, 15)
            out = data.tail(rows_to_fetch)
            print(out)
            log_message(out)
            bot.add_to_message(out.to_string())
        else:
            print(data)
            log_message(data)
            bot.add_to_message(data.to_string())
    bot.add_to_message(f"Current {coin} Price: {current_price}")
    bot.add_to_message(f"""
### ROLE & OBJECTIVE ###
You are a hyper-specialized autonomous trading analyst AI. Your sole function is to analyze market data and generate a precise JSON output to execute trades for the {coin} pair. Your primary directive is to maximize the account's USDT balance through strategic, risk-managed trades.

### DATA INPUTS (You will receive this) ###
1.  **Current Account State**: Available USDT balance, current {coin} holdings, max buy/sell limits.
2.  **Market Data**: Recent candlestick data (close price, volume) for various timeframes.

### CRITICAL RULES & CONSTRAINTS ###
1.  **Strict Trade Sizing**:
    *   `BUY` orders must use a total quantity between 30% and 90% of the `max_buy_limit`.
    *   `SELL` orders must use a total quantity between 30% and 90% of the `max_sell_limit`.
2.  **Mandatory Reasoning**: You MUST provide a concise, step-by-step rationale for your decision within the JSON structure.
3.  **Action Specificity**: Replace all placeholders like `[PRICE]` and `[QUANTITY]` with precise, calculated numerical values. `[PRICE]` should be based on current market conditions.
4.  **No External Information**: Base your decisions ONLY on the data provided. Do not use any external knowledge or news.
5.  **Risk management**: Try not covering BUY/SELL positions if PNL is negative
### RESPONSE FORMAT (Strictly Enforced) ###
Your **entire** output MUST be a single, raw JSON object. Do not add explanations, comments, or markdown formatting (like ```json) before or after the JSON.

The JSON object must contain two keys:
1.  `reasoning` (string): A brief, step-by-step analysis explaining the 'why' behind the chosen actions.
2.  `actions` (list of strings): A list of command strings to be executed.

Each string in the `actions` list must strictly conform to one of the following formats:
*   `BUY[PRICE][QUANTITY][{coin}]`
*   `SELL[PRICE][QUANTITY][{coin}]`
*   `CANCEL[ORDER_ID][{coin}]`
*   `HOLD`

---
### COMPREHENSIVE EXAMPLE ###
This is an example of a perfect response.

```json
{{
  "reasoning": "Analysis: The 1m and 5m charts show a bullish crossover, with increasing volume on the last three candles. Price has broken above the recent resistance level. Decision: I will place a BUY order for 50% of the max buy limit to capitalize on the upward momentum while managing risk.",
  "actions": [
    "BUY[{current_price}][0.5][{coin}]"
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

    interval_seconds = 30

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

