import pandas as pd
import time
import threading
import asyncio
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
            current_time_gmt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")

            print(f"\n[{current_time_gmt}] --- Tracking telegram channel {channel_id} ---")

            # Close old incomplete orders gracefully
            timeout_old_orders()

            # Parse new Telegram messages and merge into DB
            asyncio.run(parse_last_messages(channel_id))

            # Fetch orders where the database says 'READY_TO_PLACE'
            ready_orders = get_ready_orders()
            for order in ready_orders:
                print(f"\n🚀 --- READY TO EXECUTE ORDER --- 🚀")
                print(f"ID: {order['id']} | Pair: {order['symbol']} | Dir: {'LONG' if order['direction'] == 1 else 'SHORT'}")
                print(f"Entry: {order['entry_price']} | TP: {order['take_profit']} | SL: {order['stop_loss']}")

                # Setup parameters
                symbol = order['symbol']
                action = "BUY" if order['direction'] == 1 else "SELL"
                entry_price = float(order['entry_price'])

                # Fetch balance and calculate size (Adjust percentage as needed, e.g., 5% of balance)
                available_usdt = trader.get_available_balance(symbol)
                pct_per_trade = 0.85 # 85% of your available USDT
                trade_amount_usdt = available_usdt * pct_per_trade

                if trade_amount_usdt < 2.0:
                    print(f"❌ Skip: Balance too low ({trade_amount_usdt:.2f} USDT available for trade)")
                    mark_order_placed(order['id']) # Mark placed so we don't spam errors
                    continue

                # Calculate quantity to buy/sell (rounding to 1 decimal place. You might need logic to adjust decimal places per coin)
                raw_qty = trade_amount_usdt / entry_price
                qty = round(raw_qty, 1)

                # Call the actual Bybit logic
                result = trader.place_limit_order_with_tp_sl(
                    instrument_id=symbol,
                    side=action,
                    size=qty,
                    price=entry_price,
                    take_profit_price=float(order['take_profit']),
                    stop_loss_price=float(order['stop_loss'])
                )

                print(f"Execution Result: {result}")

                # Once traded (or attempted), flag DB so it doesn't try again
                mark_order_placed(order['id'])

            current_time_gmt = datetime.now(timezone.utc).strftime("%H:%M:%S GMT")
            print(f"[{current_time_gmt}] --- Waiting for {target_sleep / 60:.1f} minutes before next run... ---")
            time.sleep(target_sleep)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")

