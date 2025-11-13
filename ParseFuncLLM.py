import json
import re
from OKXinteract import OKXTrader
from Get_market import get_okx_current_price
from Config import *
from TelegramInteract import get_slippage_config

def parse_and_execute_commands(trader, instrument_id, llm_response: str):
    """
    Parses a complex LLM response to find and execute trading commands.

    Returns:
        tuple[str, int | None]: A tuple containing the string of execution results
                                and an integer for the wait time in seconds, or None.
    """
    print(f"\n--- Processing LLM Response ---")
    results = []
    commands_to_parse = []
    wait_seconds = None # Initialize wait time as None
    cleaned_text = llm_response.strip()

    try:
        json_start = cleaned_text.find('{')
        json_end = cleaned_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = cleaned_text[json_start : json_end + 1]
            data = json.loads(json_str)
            if 'actions' in data and isinstance(data['actions'], list):
                commands_to_parse = data['actions']
            elif 'action' in data:
                commands_to_parse.append(data['action'])
            else:
                return "❌ Action: UNKNOWN. JSON is missing 'actions' or 'action' key.", None
        else:
            return "❌ Action: UNKNOWN. No valid JSON block found.", None
    except json.JSONDecodeError:
        return "❌ Action: UNKNOWN. Malformed JSON detected.", None

    print(f"Found commands to parse: {commands_to_parse}")

    if not commands_to_parse:
        return "❌ Action: UNKNOWN. No commands found in JSON.", None

    slippage_config = get_slippage_config()
    buy_slippage_multiplier = 1 - (slippage_config.get('buy_slippage', 0.1) / 100.0)
    sell_slippage_multiplier = 1 + (slippage_config.get('sell_slippage', 0.1) / 100.0)

    for command_str in commands_to_parse:
        command = command_str.strip().upper()
        open_pos_pattern = r'^(LONG_TP_SL|SHORT_TP_SL)\[([\d.]+)\]\[([\d.]+)\]\[([\d.]+)\]\[([\d.]+)\]$'
        trade_pattern = r'^(BUY|SELL)\[([\d.]+)\]\[([\d.]+)\]$'
        cancel_pattern = r'^CANCEL\[(\w+)\]$'
        wait_pattern = r'^WAIT\[(\d+)\]$'
        close_all_pattern = r'^CLOSE_ALL$'

        open_pos_match = re.match(open_pos_pattern, command)
        trade_match = re.match(trade_pattern, command)
        cancel_match = re.match(cancel_pattern, command)
        wait_match = re.match(wait_pattern, command)

        if open_pos_match:
            action, price_str, tp_price_str, sl_price_str, quantity_str = open_pos_match.groups()
            #max_quantity, min_quantity = trader.get_max_order_limits_quantity(instrument_id)
            #max_quantity = float(max_quantity)
            #min_quantity = float(min_quantity)
            tp_price = float(tp_price_str)
            sl_price = float(sl_price_str)
            cur_price = float(get_okx_current_price(instrument_id))
            price = float(price_str)
            quantity = float(quantity_str)
            if action == 'LONG_TP_SL':
                side = 'buy'
            else:
                side = 'sell'
            result = trader.place_limit_order_with_tp_sl(
                instrument_id=instrument_id,
                side=side,
                size=quantity,
                price=price,
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )
            results.append(result)

        if trade_match:
            action, price_str, quantity_str = trade_match.groups()
            max_quantity, min_quantity = trader.get_max_order_limits_quantity(instrument_id)
            max_quantity = float(max_quantity)
            min_quantity = float(min_quantity)
            cur_price = float(get_okx_current_price(instrument_id))
            price = float(price_str)
            quantity = float(quantity_str)
            if action == 'BUY':
                side = 'buy'
                if cur_price <= price: price = cur_price * buy_slippage_multiplier
                if quantity >= max_quantity: quantity = max_quantity * 0.9
            else:
                side = 'sell'
                if cur_price >= price: price = cur_price * sell_slippage_multiplier
                if quantity >= min_quantity: quantity = min_quantity * 0.9
            result = trader.place_limit_order_with_leverage(instrument_id, side, quantity, price)
            results.append(result)

        elif cancel_match:
            order_id = cancel_match.groups()
            result = trader.cancel_order(instrument_id, order_id)
            results.append(result)

        elif wait_match:
            time_to_wait = int(wait_match.groups()[0])
            wait_seconds = time_to_wait
            results.append(f"✅ Action: WAIT. Will pause for {time_to_wait} seconds after this cycle.")

        elif close_all_pattern:
            result = trader.close_all_orders_and_positions()
            results.append(result)

        elif command == 'HOLD':
            results.append("✅ Action: HOLD. No trade was executed.")

        else:
            results.append(f"❌ Action: UNKNOWN. Command '{command_str}' has an invalid format.")

    return "\n".join(results), wait_seconds

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
