import json
import re
from OKXinteract import OKXTrader
from Config import *

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

            # Prefer the 'actions' key for multiple commands
            if 'actions' in data and isinstance(data['actions'], list):
                commands_to_parse = data['actions']
            # Fallback for a single 'action'
            elif 'action' in data:
                commands_to_parse.append(data['action'])
            else:
                return "❌ Action: UNKNOWN. Found JSON but it is missing the 'actions' or 'action' key."
        else:
            return "❌ Action: UNKNOWN. No valid JSON block found in the response."

    except json.JSONDecodeError:
        return "❌ Action: UNKNOWN. Malformed JSON detected in the response."

    print(f"Found commands to parse: {commands_to_parse}")

    # --- Step 2: Parse and execute each extracted command ---
    if not commands_to_parse:
        return "❌ Action: UNKNOWN. The JSON did not contain any commands to execute."

    for command_str in commands_to_parse:
        command = command_str.strip().upper()

        trade_pattern = r'^(BUY|SELL)\[([\d.]+)\]\[([\d.]+)\]\[([A-Z-]+)\]$'
        cancel_pattern = r'^CANCEL\[(\w+)\]\[([A-Z-]+)\]$'

        trade_match = re.match(trade_pattern, command)
        cancel_match = re.match(cancel_pattern, command)

        if trade_match:
            action, price_str, quantity_str, instrument_id = trade_match.groups()
            try:
                price = float(price_str)
                quantity = float(quantity_str)
                side = 'buy' if action == 'BUY' else 'sell'
                result = trader.place_limit_order_with_leverage(instrument_id, side, quantity, price)
                results.append(result)
            except ValueError:
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

# --- USAGE EXAMPLE ---
if __name__ == "__main__":

    trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)

    parse_and_execute_command(trader, """Okay, let's analyze the data and formulate a trading decision.

**Analysis:**

1.  **Overall Trend:** Both the 1m and 5m data suggest a period of consolidation followed by a slight upward trend. The 5m data shows a similar pattern with some volatility.
2.  **Volume:** Volume has been fluctuating, but relatively high on the 5m timeframe.
3.  **Price Action:** The price is currently around 111530. The recent price action shows some sideways movement. The 5m data suggests a potential reversal from lower levels.
4.  **Risk Tolerance:** Given the moderate volatility and the account balance, a conservative approach is warranted. I will target a small buy order to test the waters.

**Decision:**

Based on the analysis, I will place a small buy order.


```json
{
    "actions": [
    "BUY[0.00015][BTC-USDT]",
    "SELL[0.00015][BTC-USDT]",
    "CANCEL[98765XYZ][BTC-USDT]"
    ]
}
    ```""")
