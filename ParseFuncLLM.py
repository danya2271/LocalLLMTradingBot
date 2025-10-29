import json
import re
from OKXinteract import OKXTrader
from Config import *

def parse_and_execute_command(trader, llm_response: str):
    """
    Parses a complex LLM response to find and execute a trading command.
    It first looks for a JSON block, then parses the command within it.
    If no JSON is found, it falls back to parsing the entire string.
    """
    print(f"\n--- Processing LLM Response ---")

    # --- Step 1: Extract the core command string from the messy response ---
    command_to_parse = ""
    cleaned_text = llm_response.strip()

    # Try to find a JSON block first
    try:
        json_start = cleaned_text.find('{')
        json_end = cleaned_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_str = cleaned_text[json_start : json_end + 1]
            data = json.loads(json_str)
            # The command is the VALUE of the "action" key
            if 'action' in data:
                command_to_parse = data['action']
            else:
                 return "❌ Action: UNKNOWN. Found JSON but it is missing the 'action' key."
        else:
            # No JSON found, assume the whole response is the command
            command_to_parse = cleaned_text
    except (json.JSONDecodeError, AttributeError):
        # JSON was malformed, assume the whole response is the command
        command_to_parse = cleaned_text

    print(f"Found command to parse: '{command_to_parse}'")

    # --- Step 2: Parse and execute the extracted command string ---
    command = command_to_parse.strip().upper()

    # Regex for BUY[PRICE][QUANTITY][INSTRUMENT-ID] or SELL[...]
    trade_pattern = r'^(BUY|SELL)\[([\d.]+)\]\[([\d.]+)\]\[([A-Z-]+)\]$'
    # Regex for CANCEL[ORDER_ID][INSTRUMENT-ID]
    cancel_pattern = r'^CANCEL\[(\w+)\]\[([A-Z-]+)\]$'

    # Check for BUY or SELL
    trade_match = re.match(trade_pattern, command)
    if trade_match:
        action, price_str, quantity_str, instrument_id = trade_match.groups()
        try:
            price = float(price_str)
            quantity = float(quantity_str)
            side = 'buy' if action == 'BUY' else 'sell'
            return trader.place_limit_order_with_leverage(instrument_id, side, quantity, price)
        except ValueError:
            return f"❌ Action: UNKNOWN. Invalid number format in command: '{command}'"

    # Check for CANCEL
    cancel_match = re.match(cancel_pattern, command)
    if cancel_match:
        order_id, instrument_id = cancel_match.groups()
        return trader.cancel_order(instrument_id, order_id)

    # Check for HOLD
    if command == 'HOLD':
        return "✅ Action: HOLD. No trade was executed."

    # If no patterns match the extracted command
    return f"❌ Action: UNKNOWN. The extracted command '{command_to_parse}' does not match any known format."


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
  "action": "BUY[111535][0.00006382][BTC-USDT]"
}
```""")
