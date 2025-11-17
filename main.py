
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
from TelegramInteract import (
    send_message_to_all_users, get_trading_coin, poll_telegram_updates,
    get_data_config, get_wait_config
)

trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
bot = OllamaBot()

def HInfoSend(risk,coin):
    data_config = get_data_config()
    Bal = GetBal(coin)
    open_orders_info = trader.get_open_orders(coin)
    open_positions_info = trader.get_open_positions(coin)
    max_order_limits = trader.get_max_order_limits(coin)
    current_price = get_okx_current_price(coin)
    #print(Bal)
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        #print(f"--- {timeframe} Data ---")
        bot.add_to_message(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            rows_to_fetch = data_config.get(timeframe, 15)
            out = data.tail(rows_to_fetch)
            #print(out)
            log_message(out)
            bot.add_to_message(out.to_string())
        else:
            #print(data)
            log_message(data)
            bot.add_to_message(data.to_string())
    bot.add_to_message(f"Current {coin} Price: {current_price}")
    prompt = f"""
### ROLE & OBJECTIVE ###
You are a hyper-specialized autonomous trading analyst AI. Your sole function is to analyze market data and generate a precise JSON output to execute trades and control your own operational tempo for the {coin} pair. Your primary directive is to maximize the account's USDT balance by intelligently managing entries, exits, and existing positions.

### DATA INPUTS ###
1.  **Current Account State**: Available USDT balance, {coin} holdings, details of any open positions (entry price, PNL), and any open orders (order ID, price, quantity).
2.  **Market Data**: Recent candlestick data for various timeframes, including key indicators and volume.

### POSITION & ORDER MANAGEMENT ###
1.  **Losing Positions**: DO NOT close a position if its PNL is negative. Instead, analyze the chart for reversal signals.
    *   If a reversal is likely, consider moving the take-profit order to a more conservative, achievable price to increase the probability of a successful exit.
    *   If the trend remains strongly against the position, HOLD and wait for a more favorable exit opportunity.
2.  **Open Orders**: Continuously evaluate if your open limit orders are still valid based on the most recent price action. If a take-profit or stop-loss is unlikely to be hit due to a significant change in market structure, you MUST `CANCEL` the order and re-evaluate your strategy.

### CRITICAL RULES & CONSTRAINTS ###
1.  **Strict Trade Sizing**: New `LONG_TP_SL` and `SHORT_TP_SL` orders must use a quantity between 30% and 90% of the `max_buy_limit` or `max_sell_limit`. When managing an existing position, use the position's original quantity.
2.  **Mandatory Reasoning**: You MUST provide a concise, step-by-step rationale for your decision, referencing market data and your management rules.
3.  **Action Specificity**: Replace `[ENTRY_PRICE]`, `[TP_PRICE]`, `[SL_PRICE]`, `[QUANTITY]`, and `[ORDER_ID]` with precise numerical values derived from the input data.
4.  **No External Information**: Base decisions ONLY on the data provided.

### RESPONSE FORMAT (Strictly Enforced) ###
Your **entire** output MUST be a single, raw JSON object.

The JSON object must contain two keys:
1.  `reasoning` (string): A brief analysis explaining your actions.
2.  `actions` (list of strings): A list of commands to be executed.

Each string in the `actions` list must strictly conform to one of the following formats:
*   `LONG_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]`
*   `SHORT_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]`
*   `CANCEL[ORDER_ID]`
*   `CLOSE_ALL` - closes all orders and positions
*   `WAIT[SECONDS]` - Pause the bot for a specific number of seconds before the next cycle.
*   `HOLD`

---
### COMPREHENSIVE EXAMPLE ###
This is an example of a perfect response.

```json
{{
  "reasoning": "Analysis: The 1m chart shows high volatility. I will place a LONG order slightly below the current price to catch a potential dip and will then wait for 90 seconds to let the market stabilize before re-evaluating.",
  "actions": [
    "LONG_TP_SL[{float(current_price) * 0.999:.2f}][{float(current_price) * 1.01:.2f}][{float(current_price) * 0.99:.2f}][0.5]",
    "WAIT[90]"
  ]
}}
```
"""
    bot.add_to_message(prompt)
    #bot.add_to_message(Bal)
    bot.add_to_message(open_orders_info)
    bot.add_to_message(max_order_limits)
    bot.add_to_message(open_positions_info)
    llm_answ = bot.send_and_reset_message()
    print(llm_answ)
    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, llm_answ)
    execution_results, llm_wait_time = parse_and_execute_commands(trader, coin, llm_answ)
    print(execution_results)
    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, f"--- Execution Results ---\n{execution_results}")

    return llm_wait_time

if __name__ == '__main__':
    # Start the Telegram listener in a background thread
    telegram_thread = threading.Thread(target=poll_telegram_updates, args=(TELEGRAM_BOT_TOKEN,), daemon=True)
    telegram_thread.start()

    try:
        print("Starting the main trading loop. Press Ctrl+C to stop.")
        while True:
            current_coin = get_trading_coin()
            print(f"\n--- Running analysis for {current_coin} ---")

            llm_specified_wait_time = HInfoSend(0, current_coin)

            if llm_specified_wait_time is not None:
                interval_seconds = llm_specified_wait_time
                print(f"LLM decided to wait for {interval_seconds} seconds.")
            else:
                interval_seconds = get_wait_config() # Fallback to default
                print(f"LLM did not specify wait time. Using default: {interval_seconds} seconds.")

            print(f"--- Waiting for {interval_seconds / 60:.1f} minutes before next run... ---")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")

