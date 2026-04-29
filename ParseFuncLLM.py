import json
import re
from OKXinteract import OKXTrader
from Get_market import get_okx_current_price
from Config import *
from TelegramInteract import get_slippage_config
from Bybitinteract import BybitTrader
from bybit_config import BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO
import math

trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)

def parse_and_execute_commands(trader, instrument_id, llm_response, current_price, atr):
    """
    ATR-based execution logic.
    """
    print(f"\n--- Processing Strategy ---")

    try:
        # Пытаемся найти JSON
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            return "❌ No JSON found", 60

        action = data.get('action', 'WAIT').upper()
        reasoning = data.get('reasoning', '')

        print(f"Decision: {action} | Reason: {reasoning}")

        if action == 'WAIT':
            return f"Bot decided to WAIT: {reasoning}", 60

        # --- МАТЕМАТИКА НА PYTHON (НЕ НА LLM) ---
        # Настройки риск-менеджмента
        sl_multiplier = 2.0  # Стоп-лосс = 2 * ATR
        tp_multiplier = 3.0  # Тейк-профит = 3 * ATR (Риск/Прибыль 1:1.5)

        if action == 'BUY':
            # 1. ROUND PRICES FOR BYBIT (Max 3-4 decimal places for SOL)
            entry_price = round(current_price, 3)
            sl_price = round(entry_price - (atr * sl_multiplier), 3)
            tp_price = round(entry_price + (atr * tp_multiplier), 3)

            available_usdt = trader.get_available_balance(instrument_id)

            # NOTE: 2.50 means you are trying to use 250% of your balance (Leverage)
            pct_per_trade = 2.50
            trade_amount_usdt = available_usdt * pct_per_trade

            if trade_amount_usdt < 2.0:
                return f"❌ Skip: Balance too low ({trade_amount_usdt:.2f} USDT)", 60

            print(f"Calculated Trade Amount: {trade_amount_usdt:.2f} USDT based on balance {available_usdt}")

            raw_qty = trade_amount_usdt / entry_price

            # 2. ROUND QUANTITY (Bybit requires 1 or 2 decimal places for SOL)
            qty = round(raw_qty, 1)

            # 3. CAPTURE AND RETURN THE REAL RESULT
            result = trader.place_limit_order_with_tp_sl(
                instrument_id=instrument_id,
                side='buy',
                size=qty,
                price=entry_price,
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )
            return f"{result} | Entry: {entry_price}, SL: {sl_price}, TP: {tp_price}", 300

        elif action == 'SELL':
            # 1. ROUND PRICES FOR BYBIT
            entry_price = round(current_price, 3)
            sl_price = round(entry_price + (atr * sl_multiplier), 3)
            tp_price = round(entry_price - (atr * tp_multiplier), 3)

            available_usdt = trader.get_available_balance(instrument_id)

            pct_per_trade = 2.50
            trade_amount_usdt = available_usdt * pct_per_trade

            if trade_amount_usdt < 2.0:
                return f"❌ Skip: Balance too low ({trade_amount_usdt:.2f} USDT)", 60

            print(f"Calculated Trade Amount: {trade_amount_usdt:.2f} USDT based on balance {available_usdt}")

            raw_qty = trade_amount_usdt / entry_price

            # 2. ROUND QUANTITY
            qty = round(raw_qty, 1)

            # 3. CAPTURE AND RETURN THE REAL RESULT
            result = trader.place_limit_order_with_tp_sl(
                instrument_id=instrument_id,
                side='sell',
                size=qty,
                price=entry_price,
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )
            return f"{result} | Entry: {entry_price}, SL: {sl_price}, TP: {tp_price}", 300

    except Exception as e:
        return f"Error executing: {e}", 60

    return "No action taken", 60

if __name__ == "__main__":
    trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
    test_response = """
    ```json
    {
        "reasoning": "Market is volatile, will place orders and wait longer.",
        "actions": [
            "BUY[168.06][0.1305][SOL-USDT]",
            "WAIT[900]"
        ]
    }
    ```
    """
    execution_results, llm_wait_time = parse_and_execute_commands(trader, test_response)
    print("\n--- Execution Results ---")
    print(execution_results)
    print(f"\n--- Recommended Wait Time ---")
    print(f"{llm_wait_time} seconds")
