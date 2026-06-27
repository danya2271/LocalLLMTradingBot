import time
import threading
import asyncio
from datetime import datetime, timezone
from Database import init_db, timeout_old_orders, get_ready_orders, mark_order_placed, mark_order_failed
from ParseChannel import parse_last_messages
from Logging import log_message
from Bybitinteract import BybitTrader
from bybit_config import (
    BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO,
    LEVERAGE, RISK_FRACTION, MAX_MARGIN_FRACTION,
)
from Config import *
from TelegramConfig import *
from TelegramInteract import (
    send_message_to_all_users, poll_telegram_updates,
)

print("Initializing BybitTrader...")
trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)

if __name__ == '__main__':
    print("Initializing Database...")
    init_db()
    print("Database initialized successfully!")

def _coerce_price(value):
    """ Parse a price/qty field that may be a number, a comma-decimal string, or junk. """
    if value is None:
        return None
    try:
        s = str(value).strip().replace(',', '.')
        f = float(s)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def place_ready_order(order, remaining_margin):
    """
    Attempts to place one READY_TO_PLACE order.
    Returns (status, margin_used) where status is one of
    'placed' | 'skip_retry' | 'invalid', and margin_used is float committed.
    """
    symbol = order['symbol']
    direction = order['direction']
    action = "BUY" if direction == 1 else "SELL"

    entry_price = _coerce_price(order['entry_price'])
    take_profit = _coerce_price(order['take_profit'])
    stop_loss = _coerce_price(order['stop_loss'])

    # Reject structurally invalid signals (bad numbers / incoherent direction).
    if not symbol or entry_price is None or take_profit is None or stop_loss is None:
        print(f"❌ Invalid order #{order['id']}: non-numeric price fields.")
        return 'invalid', 0.0
    if direction == 1 and not (stop_loss < entry_price < take_profit):
        print(f"❌ Invalid LONG #{order['id']}: need SL<entry<TP "
              f"({stop_loss} < {entry_price} < {take_profit}).")
        return 'invalid', 0.0
    if direction == 0 and not (take_profit < entry_price < stop_loss):
        print(f"❌ Invalid SHORT #{order['id']}: need TP<entry<SL "
              f"({take_profit} < {entry_price} < {stop_loss}).")
        return 'invalid', 0.0

    # Do not stack onto an existing position or resting order for this symbol.
    if trader.has_open_position(symbol) or trader.has_open_order(symbol):
        print(f"⏭️ Skip #{order['id']}: existing position/order on {symbol}.")
        return 'skip_retry', 0.0

    if remaining_margin is None or remaining_margin <= 0:
        print(f"⏭️ Skip #{order['id']}: no free margin this cycle (will retry).")
        return 'skip_retry', 0.0

    # Size from the remaining free margin, scaled by leverage.
    margin_to_use = min(remaining_margin * RISK_FRACTION, remaining_margin * MAX_MARGIN_FRACTION)
    notional = margin_to_use * LEVERAGE
    raw_qty = notional / entry_price

    # Set leverage explicitly (idempotent) so the order is not rejected/oversized.
    trader.set_leverage(symbol, LEVERAGE)

    result = trader.place_limit_order_with_tp_sl(
        instrument_id=symbol,
        side=action,
        size=raw_qty,
        price=entry_price,
        take_profit_price=take_profit,
        stop_loss_price=stop_loss,
    )
    print(f"Execution Result: {result.get('retMsg')}")

    if result.get('ok'):
        return 'placed', margin_to_use

    # Distinguish permanent rejects (bad params) from transient ones worth retrying.
    permanent_codes = {-3, -4, -5, -6, '110007', '110017', '170137', '110045'}
    if result.get('retCode') in permanent_codes:
        return 'invalid', 0.0
    return 'skip_retry', 0.0


if __name__ == '__main__':
    print("Initializing Database...")
    init_db()
    print("Database initialized successfully!")

    telegram_thread = threading.Thread(target=poll_telegram_updates, args=(TELEGRAM_BOT_TOKEN,), daemon=True)
    telegram_thread.start()

    try:
        print("Starting the main trading loop. Press Ctrl+C to stop.")
        while True:
            channel_id = 2432930513
            target_sleep = 30
            try:
                current_time_gmt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
                print(f"\n[{current_time_gmt}] --- Tracking telegram channel {channel_id} ---")

                # Close old incomplete orders gracefully
                timeout_old_orders()

                # Parse new Telegram messages and merge into DB
                asyncio.run(parse_last_messages(channel_id))

                # Fetch orders where the database says 'READY_TO_PLACE'
                ready_orders = get_ready_orders()

                # Snapshot free margin once and decrement as we place, so concurrent
                # READY orders cannot each size against the full balance.
                remaining_margin = trader.get_available_balance('USDT')

                for order in ready_orders:
                    print(f"\n🚀 --- READY TO EXECUTE ORDER --- 🚀")
                    print(f"ID: {order['id']} | Pair: {order['symbol']} | "
                          f"Dir: {'LONG' if order['direction'] == 1 else 'SHORT'}")
                    print(f"Entry: {order['entry_price']} | TP: {order['take_profit']} | SL: {order['stop_loss']}")

                    try:
                        status, margin_used = place_ready_order(order, remaining_margin)
                    except Exception as e:
                        # One bad order must not kill the loop or be silently dropped.
                        print(f"❌ Error placing order #{order['id']}: {e}")
                        log_message(f"Order #{order['id']} placement error: {e}")
                        continue

                    if status == 'placed':
                        if remaining_margin is not None:
                            remaining_margin -= margin_used
                        mark_order_placed(order['id'])
                    elif status == 'invalid':
                        mark_order_failed(order['id'])  # terminal; won't be retried forever
                    # 'skip_retry' -> leave as READY_TO_PLACE for the next cycle
            except KeyboardInterrupt:
                raise
            except Exception as e:
                err = f"⚠️ Copier loop error: {e}"
                print(err)
                log_message(err)
                try:
                    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, err)
                except Exception:
                    pass

            current_time_gmt = datetime.now(timezone.utc).strftime("%H:%M:%S GMT")
            print(f"[{current_time_gmt}] --- Waiting for {target_sleep / 60:.1f} minutes before next run... ---")
            time.sleep(target_sleep)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")

