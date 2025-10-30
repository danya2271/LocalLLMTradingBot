from Get_market import get_okx_market_data
from Get_balance import GetBal
import pandas as pd
import time
from Logging import log_message
from OllamaInteract import OllamaBot
from OKXinteract import OKXTrader
from ParseFuncLLM import parse_and_execute_command
from Config import *

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
    bot.add_to_message(F"""
You are an autonomous trading analyst AI. Your primary objective is to maximize the USDT balance of the account by trading the {coin} pair. You must operate under the following rules:

1.  **Analyze the Data**: You will be given the current account balance and recent candlestick data for {coin} across multiple timeframes (1-hour, 15-minute, 5-minute, and 1-minute).
2.  **Make a Single Decision**: Based on your analysis, you must choose one of four actions: `BUY[PRICE][QUANTITY][{coin}]`, `SELL[PRICE][QUANTITY][{coin}]`, `CANCEL[ORDER_ID][{coin}]`, or `HOLD`.
3.  **Risk Management**:
    *   When issuing a `BUY` order, you can only use up to 75% of the available USDT balance.
    *   When issuing a `SELL` order, you can only sell up to 35% of the available BTC balance.
4.  **Logical Reasoning**: Before stating your final decision, you must provide a brief, step-by-step analysis of the market data. Consider the trends, volume, and any potential patterns across the different timeframes.
5.  **Strict Output Format**: Your final response must be a JSON object. No other text or explanation should come after the JSON object.
""")
    bot.add_to_message(Bal)
    bot.add_to_message(open_orders_info)
    bot.add_to_message(max_order_limits)
    bot.add_to_message(open_positions_info)
    llm_answ = bot.send_and_reset_message()
    print(llm_answ)
    parse_and_execute_command(trader, llm_answ)

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
