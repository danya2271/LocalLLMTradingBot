import json
import re
from OKXinteract import OKXTrader
from Get_market import get_okx_current_price
from Config import *
from TelegramInteract import get_slippage_config
from Get_balance import GetBal
import math

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
            entry_price = current_price
            sl_price = entry_price - (atr * sl_multiplier)
            tp_price = entry_price + (atr * tp_multiplier)

            available_usdt = GetBal(instrument_id)

            pct_per_trade = 2.50 # coeff of trading
            trade_amount_usdt = available_usdt * pct_per_trade

            if trade_amount_usdt < 2.0:
                return f"❌ Skip: Balance too low ({trade_amount_usdt:.2f} USDT)", 60

            print(f"Calculated Trade Amount: {trade_amount_usdt:.2f} USDT based on balance {available_usdt}")

            raw_qty = trade_amount_usdt / entry_price

            qty = math.floor(raw_qty * 100) / 100.0

            result = trader.place_limit_order_with_tp_sl(
                instrument_id=instrument_id,
                side='buy',
                size=qty,
                price=entry_price,
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )
            return f"✅ BUY Executed. Entry: {entry_price}, SL: {sl_price}, TP: {tp_price}", 300

        elif action == 'SELL':
            entry_price = current_price
            sl_price = entry_price + (atr * sl_multiplier)
            tp_price = entry_price - (atr * tp_multiplier)

            available_usdt = GetBal(instrument_id)

            pct_per_trade = 2.50 # coeff of trading
            trade_amount_usdt = available_usdt * pct_per_trade

            if trade_amount_usdt < 2.0:
                return f"❌ Skip: Balance too low ({trade_amount_usdt:.2f} USDT)", 60

            print(f"Calculated Trade Amount: {trade_amount_usdt:.2f} USDT based on balance {available_usdt}")

            raw_qty = trade_amount_usdt / entry_price

            qty = math.floor(raw_qty * 100) / 100.0

            result = trader.place_limit_order_with_tp_sl(
                instrument_id=instrument_id,
                side='sell',
                size=qty,
                price=entry_price,
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )
            return f"✅ SELL Executed. Entry: {entry_price}, SL: {sl_price}, TP: {tp_price}", 300

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
