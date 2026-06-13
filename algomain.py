import pandas as pd
import time
import threading
import asyncio
import json
from datetime import datetime, timezone
from Database import init_db, timeout_old_orders, get_ready_orders, mark_order_placed
from ParseChannel import parse_last_messages, recognize_text_from_message
from Get_market import get_okx_market_data, get_okx_current_price
from Logging import log_message
from llamacppInteract import llamacppBot
from ParseFuncLLM import parse_and_execute_commands
from Bybitinteract import BybitTrader
from bybit_config import BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO
from Config import *
from llamacpp_config import LLM_API_KEY, LLM_HOST
from TelegramConfig import *
from TelegramInteract import (
    send_message_to_all_users, get_trading_coin, poll_telegram_updates,
    get_data_config, get_wait_config
)

print("Initializing BybitTrader...")
trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)

print("Initializing LLM Bot...")
# IT IS VERY LIKELY STUCK ON THE NEXT LINE:
bot = llamacppBot(LLM_API_KEY, host=LLM_HOST)
print("LLM Bot initialized successfully!")

def HInfoSend(risk, coin):
    data_config = get_data_config()
    Bal = trader.get_available_balance(coin)
    print(f"Available Balance for trading: {Bal} USDT")
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
    ema_10 = last_row['EMA_10']
    price = last_row['close']
    volume = last_row['volume']
    vol_sma = last_row['Vol_SMA_20']

    trader.update_stop_loss_to_breakeven(coin, atr)

    # Вычисляем отклонение (Overextension) и аномалии объема (Volume Spike)
    extension_pct = ((price - ema_10) / ema_10) * 100
    vol_ratio = volume / vol_sma if vol_sma > 0 else 1.0

    # БАЗОВОЕ ОПРЕДЕЛЕНИЕ ТРЕНДА (Добавлено)
    if price > ema_50:
        trend = "BULLISH"
    else:
        trend = "BEARISH"

    # Определяем тренд и опасные состояния жесткой логикой Python
    rsi_status = "OVERBOUGHT" if rsi >= 70 else ("OVERSOLD" if rsi <= 30 else "NEUTRAL")

    is_dangerously_overextended = extension_pct > 1.5  # Цена выше быстрой скользящей более чем на 1.5%
    is_buying_climax = vol_ratio > 3.0 and trend == "BULLISH" # Объем в 3 раза выше нормы на росте

    if is_dangerously_overextended or is_buying_climax:
        trend = "PARABOLIC_DANGER_DO_NOT_BUY"

    # Формируем промпт.
    prompt = f"""
    ROLE: You are a professional crypto quant trader.

    MARKET STATE for {coin}:
    1. Current Price: {price}
    2. Trend (EMA 50): {trend}
    3. Momentum (RSI 14): {rsi:.2f} ({rsi_status})
    4. Volatility (ATR): {atr:.2f}
    5. Extension from fast EMA10: {extension_pct:.2f}%
    6. Volume Spike Ratio: {vol_ratio:.1f}x average

    YOUR STRATEGY RULES:
    - BUY only if Trend is BULLISH, RSI is < 70, AND Extension is < 1.0%.
    - DO NOT BUY if Trend is PARABOLIC_DANGER_DO_NOT_BUY (market is overextended or buying climax).
    - SELL only if Trend is BEARISH and RSI is not OVERSOLD (<30).
    - If market is flat, overextended, or conflicting signals -> WAIT.

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

    # --- PYTHON GUARDRAILS (ЖЕСТКАЯ БЛОКИРОВКА ГАЛЛЮЦИНАЦИЙ LLM) ---
    try:
        # Извлекаем JSON из ответа LLM
        start_idx = llm_answ.find('{')
        end_idx = llm_answ.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            parsed_json = json.loads(llm_answ[start_idx:end_idx])
            action = parsed_json.get("action", "").upper()

            # Если LLM сказала BUY, но математика запрещает -> Отменяем
            if action == "BUY" and (extension_pct >= 1.0 or rsi >= 70 or "PARABOLIC" in trend):
                print(f"❌ PYTHON GUARDRAIL ACTIVATED: LLM hallucinated! Blocked BUY (RSI: {rsi:.2f}, Ext: {extension_pct:.2f}%)")
                # Принудительно перезаписываем ответ перед отправкой на исполнение
                llm_answ = '{\n    "reasoning": "Python Guardrails blocked LLM decision due to overbought metrics.",\n    "action": "WAIT",\n    "confidence": "HIGH"\n}'
    except Exception as e:
        print(f"Guardrail check error: {e}")
    # -------------------------------------------------------------

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
