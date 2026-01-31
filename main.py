
import pandas as pd
import time
import threading
from Get_market import get_okx_market_data, get_okx_current_price
from Get_balance import GetBal
from Logging import log_message
from OllamaInteract import OllamaBot #TODO shift to llama.cpp
from GeminiInteract import GeminiBot
from OKXinteract import OKXTrader
from ParseFuncLLM import parse_and_execute_commands
from Config import *
from TelegramConfig import *
from TelegramInteract import (
    send_message_to_all_users, get_trading_coin, poll_telegram_updates,
    get_data_config, get_wait_config
)

trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
#bot = OllamaBot()
bot = GeminiBot()

def HInfoSend(risk, coin):
    data_config = get_data_config()
    Bal = GetBal(coin)
    current_price = float(get_okx_current_price(coin))
    btc_market_data = get_okx_market_data(coin)

    # Берем данные с самого короткого таймфрейма для торговли (например, 15m)
    df = btc_market_data.get('15m')

    if not isinstance(df, pd.DataFrame):
        print("Error getting data")
        return 60

    # Извлекаем последние значения
    last_row = df.iloc[-1]
    rsi = last_row['RSI']
    atr = last_row['ATR']
    ema_50 = last_row['EMA_50']
    price = last_row['close']

    # Определяем тренд жесткой логикой Python (точнее чем LLM)
    trend = "BULLISH" if price > ema_50 else "BEARISH"
    rsi_status = "OVERBOUGHT" if rsi > 70 else ("OVERSOLD" if rsi < 30 else "NEUTRAL")

    # Формируем промпт. ЗАМЕТЬТЕ: Мы не просим модель считать цифры!
    # Мы просим только ACTION.
    prompt = f"""
    ROLE: You are a professional crypto quant trader.

    MARKET STATE for {coin}:
    1. Current Price: {price}
    2. Trend (EMA 50): {trend}
    3. Momentum (RSI 14): {rsi:.2f} ({rsi_status})
    4. Volatility (ATR): {atr:.2f}

    YOUR STRATEGY RULES:
    - BUY only if Trend is BULLISH and RSI is not OVERBOUGHT (>70).
    - SELL only if Trend is BEARISH and RSI is not OVERSOLD (<30).
    - If market is flat or conflicting signals -> WAIT.

    OUTPUT FORMAT:
    Return a JSON object with your decision. Do NOT calculate prices, I will calculate TP/SL based on ATR automatically.

    {{
        "reasoning": "Explain why in 1 sentence based on RSI and Trend",
        "action": "BUY" or "SELL" or "WAIT",
        "confidence": "HIGH" or "LOW"
    }}
    """

    bot.add_to_message(prompt)
    llm_answ = bot.send_and_reset_message()
    print(f"LLM Reasoning: {llm_answ}")

    # Передаем ATR в функцию исполнения, чтобы Python сам посчитал стопы
    execution_results, llm_wait_time = parse_and_execute_commands(trader, coin, llm_answ, current_price, atr)

    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, llm_answ)
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

