import json
import re
from Get_market import get_okx_current_price
from Config import *
from Bybitinteract import BybitTrader
from bybit_config import (
    BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO,
    LEVERAGE, RISK_FRACTION, MAX_MARGIN_FRACTION,
)

trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)

# Risk-management parameters (ATR-based)
SL_MULTIPLIER = 2.0  # Stop-loss = 2 * ATR
TP_MULTIPLIER = 3.0  # Take-profit = 3 * ATR (Risk/Reward 1:1.5)
LONG_ENTRY_MULTIPLIER = 0.996   # Place long limit ~0.4% below market (maker side)
SHORT_ENTRY_MULTIPLIER = 1.004  # Place short limit ~0.4% above market (maker side)


def _compute_sizing(trader, instrument_id, entry_price):
    """
    Returns (qty, info_str) sizing notional from FREE margin, leverage and risk fraction.
    Returns (None, reason) when the trade should be skipped.
    """
    available_usdt = trader.get_available_balance(instrument_id)
    if available_usdt is None:
        return None, "Balance unavailable (API/network error); skipping cycle"
    if available_usdt <= 0:
        return None, f"No free margin available ({available_usdt})"

    # Cap the margin actually committed, then scale to notional by leverage.
    margin_fraction = min(RISK_FRACTION, MAX_MARGIN_FRACTION)
    margin_to_use = available_usdt * margin_fraction
    notional = margin_to_use * LEVERAGE

    if entry_price <= 0:
        return None, f"Invalid entry price ({entry_price})"

    raw_qty = notional / entry_price
    info = (f"free={available_usdt:.2f} USDT, margin={margin_to_use:.2f}, "
            f"lev={LEVERAGE}x, notional={notional:.2f}")
    return raw_qty, info


def parse_and_execute_commands(trader, instrument_id, llm_response, current_price, atr):
    """
    ATR-based execution logic. Returns (result_message, wait_seconds).
    """
    print(f"\n--- Processing Strategy ---")

    # Only the JSON extraction is wrapped defensively; execution errors must surface distinctly.
    try:
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            return "❌ No JSON found", 60
        data = json.loads(json_match.group(0))
    except Exception as e:
        return f"❌ Failed to parse LLM JSON: {e}", 60

    action = data.get('action', 'WAIT').upper()
    reasoning = data.get('reasoning', '')
    print(f"Decision: {action} | Reason: {reasoning}")

    if action not in ('BUY', 'SELL'):
        return f"Bot decided to WAIT: {reasoning}", 60

    if current_price is None or current_price <= 0:
        return "❌ EXECUTION_ERROR: invalid current price; not trading", 60

    # Guard: never stack onto an existing position or resting order for this symbol.
    try:
        if trader.has_open_position(instrument_id) or trader.has_open_order(instrument_id):
            return f"Skip {action}: existing position/order on {instrument_id}", 300
    except Exception as e:
        return f"❌ EXECUTION_ERROR: could not verify existing exposure: {e}", 60

    # Set leverage explicitly so sizing is predictable (idempotent).
    try:
        trader.set_leverage(instrument_id, LEVERAGE)
    except Exception as e:
        print(f"   ⚠️ set_leverage failed (continuing): {e}")

    side = 'buy' if action == 'BUY' else 'sell'
    if action == 'BUY':
        entry_price = current_price * LONG_ENTRY_MULTIPLIER
        sl_price = entry_price - (atr * SL_MULTIPLIER)
        tp_price = entry_price + (atr * TP_MULTIPLIER)
    else:
        entry_price = current_price * SHORT_ENTRY_MULTIPLIER
        sl_price = entry_price + (atr * SL_MULTIPLIER)
        tp_price = entry_price - (atr * TP_MULTIPLIER)

    raw_qty, info = _compute_sizing(trader, instrument_id, entry_price)
    if raw_qty is None:
        return f"❌ Skip {action}: {info}", 60
    print(f"Sizing: {info}")

    # The trader quantizes qty/price to exchange filters and validates before sending.
    try:
        result = trader.place_limit_order_with_tp_sl(
            instrument_id=instrument_id,
            side=side,
            size=raw_qty,
            price=entry_price,
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
        )
    except Exception as e:
        return f"❌ EXECUTION_ERROR placing {action}: {e}", 60

    if result.get("ok"):
        return (f"✅ {action} placed (Order {result.get('orderId')}) | {result.get('retMsg')}", 300)
    return (f"❌ EXECUTION_ERROR: {action} not placed: {result.get('retMsg')} "
            f"(Code: {result.get('retCode')})", 60)


if __name__ == "__main__":
    trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)
    test_response = '{"reasoning": "test", "action": "WAIT", "confidence": "LOW"}'
    test_price = float(get_okx_current_price('SOL-USDT') or 0.0)
    execution_results, llm_wait_time = parse_and_execute_commands(
        trader, 'SOL-USDT', test_response, test_price, atr=1.0
    )
    print("\n--- Execution Results ---")
    print(execution_results)
    print(f"\n--- Recommended Wait Time ---")
    print(f"{llm_wait_time} seconds")
