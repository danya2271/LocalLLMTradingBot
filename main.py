
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
You are an elite Quantitative Trading AI specialized in the {coin} pair. Your objective is to grow the USDT balance by executing high-probability trades while strictly preserving capital. You operate on a "Risk First, Profit Second" philosophy.

### INPUT DATA ANALYSIS PROTOCOL ###
Before generating actions, you must mentally process the provided data in this order:
1.  **Market Regime**: Is the market Trending (Higher Highs/Lower Lows) or Ranging (Choppy/Sideways)?
2.  **Key Levels**: Identify the nearest Support and Resistance levels based on the provided candlestick data.
3.  **Volatility State**: Is volume expanding (breakout imminent) or contracting (consolidation)?

### STRATEGIC EXECUTION RULES ###

1.  **Entry Logic (Sniper Approach)**:
    *   **Trending**: Enter on pullbacks to support (Long) or rejections from resistance (Short).
    *   **Ranging**: Buy support, Sell resistance. Avoid trading in the middle of the range.
    *   *Constraint*: Do not open a new position if the spread between Entry and Stop Loss is too tight (<0.2%) or too wide (>5%) unless volatility justifies it.

2.  **Position Sizing (Dynamic)**:
    *   **High Confidence**: If trend and volume align, use 60%-90% of `max_buy/sell_limit`.
    *   **Low Confidence/Counter-Trend**: Use 30%-50% of `max_buy/sell_limit` to test the water.

3.  **Active Position Management**:
    *   **Winning Positions**: If PNL > 1.5%, consider cancelling the old TP and setting a new `LONG/SHORT_TP_SL` with a higher Stop Loss (Trailing Stop) to lock in profits.
    *   **Losing Positions (CRITICAL)**:
        *   If the price breaks market structure (e.g., a Long's support level is smashed with volume), **YOU MUST CUT THE LOSS**. Do not hold "hope" trades.
        *   If the price is merely chopping but structure holds, you may `HOLD` or adjust the TP closer to entry to exit at Break Even.

4.  **Order Hygiene**:
    *   If an open Limit Order has not been filled and price has moved away by >2%, `CANCEL` it. It is now "stale liquidity."

5.  **Tempo Control (WAIT)**:
    *   **High Volatility**: If candles are erratic, `WAIT[120]` to let dust settle.
    *   **Normal Operation**: `WAIT[30]` or `WAIT[60]` is standard.

### RESPONSE FORMAT (Strictly Enforced) ###
Your output must be a **SINGLE RAW JSON OBJECT**. No markdown, no conversational text.

**JSON Structure:**
{{
  "reasoning": "A concise chain-of-thought: 1. Market Regime. 2. Key Levels. 3. Action justification. 4. Risk management logic.",
  "actions": [
    "ACTION_STRING_1",
    "ACTION_STRING_2"
  ]
}}

**Valid Action Strings:**
*   `LONG_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]` -> All prices/qtys must be floats.
*   `SHORT_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]`
*   `CANCEL[ORDER_ID]`
*   `CLOSE_ALL` -> Panic button. Use only if market data is erratic or extreme risk detected.
*   `WAIT[SECONDS]` -> Integer only.
*   `HOLD` -> Use when no action is required.

### CRITICAL REMINDERS ###
1.  **Math Precision**: Ensure `SL_PRICE` is *below* entry for Longs and *above* entry for Shorts.
2.  **Self-Correction**: If you have a winning position, do not open a *competing* opposite order.
3.  **Data Reliance**: Do not hallucinate prices. Use the exact `current_price` provided in inputs.

---
### EXAMPLE OUTPUT ###
{{
  "reasoning": "Analysis: The 1m chart shows high volatility. I will place a LONG order slightly below the current price to catch a potential dip and will then wait for 90 seconds to let the market stabilize before re-evaluating.",
  "actions": [
    "LONG_TP_SL[{float(current_price) * 0.999:.2f}][{float(current_price) * 1.01:.2f}][{float(current_price) * 0.99:.2f}][0.5]",
    "WAIT[90]"
  ]
}}
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

