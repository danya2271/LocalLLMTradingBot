import json
import re
from OKXinteract import OKXTrader
from Get_market import get_okx_current_price
from Config import *
from TelegramInteract import get_slippage_config

def parse_and_execute_commands(trader, llm_response: str):
    """
    Parses a complex LLM response to find and execute one or more trading commands.
    It looks for a JSON block containing an "actions" list (for multiple commands)
    or an "action" string (for a single command).
    """
    print(f"\n--- Processing LLM Response ---")
    results = []
    commands_to_parse = []
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
                return "❌ Action: UNKNOWN. Found JSON but it is missing the 'actions' or 'action' key."
        else:
            return "❌ Action: UNKNOWN. No valid JSON block found in the response."
    except json.JSONDecodeError:
        return "❌ Action: UNKNOWN. Malformed JSON detected in the response."

    print(f"Found commands to parse: {commands_to_parse}")

    if not commands_to_parse:
        return "❌ Action: UNKNOWN. The JSON did not contain any commands to execute."

    slippage_config = get_slippage_config()
    buy_slippage_multiplier = 1 - (slippage_config.get('buy_slippage', 0.1) / 100.0)
    sell_slippage_multiplier = 1 + (slippage_config.get('sell_slippage', 0.1) / 100.0)

    for command_str in commands_to_parse:
        command = command_str.strip().upper()
        trade_pattern = r'^(BUY|SELL)\[([\d.]+)\]\[([\d.]+)\]\[([A-Z-]+)\]$'
        cancel_pattern = r'^CANCEL\[(\w+)\]\[([A-Z-]+)\]$'
        trade_match = re.match(trade_pattern, command)
        cancel_match = re.match(cancel_pattern, command)

        if trade_match:
            action, price_str, quantity_str, instrument_id = trade_match.groups()
            try:
                cur_price = float(get_okx_current_price(instrument_id))
                price = float(price_str)
                quantity = float(quantity_str)
                if action == 'BUY':
                    side = 'buy'
                    if cur_price <= price:
                        price *= buy_slippage_multiplier
                else:
                    side = 'sell'
                    if cur_price >= price:
                        price *= sell_slippage_multiplier
                result = trader.place_limit_order_with_leverage(instrument_id, side, quantity, price)
                results.append(result)
            except (ValueError, TypeError):
                results.append(f"❌ Action: UNKNOWN. Invalid number format in command: '{command}'")
        elif cancel_match:
            order_id, instrument_id = cancel_match.groups()
            result = trader.cancel_order(instrument_id, order_id)
            results.append(result)
        elif command == 'HOLD':
            results.append("✅ Action: HOLD. No trade was executed.")
        else:
            results.append(f"❌ Action: UNKNOWN. The command '{command_str}' does not match any known format.")

    return "\n".join(results)

if __name__ == "__main__":
    trader = OKXTrader(api_key, secret_key, passphrase, is_demo=True)
    test_response = """
    This is some text from the LLM.
    ```json
    {
        "reasoning": "The market is showing signs of an uptrend, so I will place a buy order.",
        "actions": [
            "BUY[110000.0][0.01][BTC-USDT]",
            "SELL[120000.0][0.01][BTC-USDT]",
            "CANCEL[98765XYZ][BTC-USDT]"
        ]
    }
    ```
    """
    execution_results = parse_and_execute_commands(trader, test_response)
    print("\n--- Execution Results ---")
    print(execution_results)
