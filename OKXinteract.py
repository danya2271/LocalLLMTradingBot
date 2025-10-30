import okx.Account as Account
import okx.Trade as Trade
import okx.PublicData as Public
from decimal import Decimal, ROUND_DOWN
import time
import re
from Config import *

class OKXTrader:
    def __init__(self, api_key, secret_key, passphrase, is_demo=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        flag = '1' if is_demo else '0'

        self.account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, flag)
        self.trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
        self.public_api = Public.PublicAPI(debug=False, flag=flag)

        print(f"Trader initialized in {'DEMO' if is_demo else 'LIVE'} mode.")

    # ... (all other methods like get_max_order_limits, place_limit_order_with_leverage, etc., remain unchanged) ...
    def get_max_order_limits(self, instrument_id):
        print(f"\n-> Requesting max order limits for {instrument_id}...")
        try:
            result = self.account_api.get_max_order_size(instId=instrument_id, tdMode='cross', ccy='USDT')
            if result.get('code') == '0':
                data = result['data'][0]
                max_buy, max_sell = data.get('maxBuy'), data.get('maxSell')
                currency = instrument_id.split('-')[0]
                return f"✅ Max limits received: Max buy: {max_buy} {currency}, Max sell: {max_sell} {currency}"
            else:
                return f"❌ Error getting limits: {result.get('msg')}"
        except Exception as e:
            return f"❌ A critical error occurred during the API call: {e}"

    def place_limit_order_with_leverage(self, instrument_id, side, size, price):
        print(f"\n-> Placing {side.upper()} limit order: {size} {instrument_id} at price {price}...")
        try:
            result = self.trade_api.place_order(instId=instrument_id, tdMode='cross', side=side, ordType='limit', sz=f'{size:.8f}', px=str(price), ccy='USDT')
            if result.get('code') == '0':
                return f"✅ Order placed successfully! Order ID: {result['data'][0].get('ordId')}"
            else:
                return f"❌ Error placing order: {result.get('msg')}"
        except Exception as e:
            return f"❌ A critical error occurred during the API call: {e}"

    def cancel_order(self, instrument_id, order_id):
        print(f"\n-> Canceling order ID: {order_id} for {instrument_id}...")
        try:
            result = self.trade_api.cancel_order(instId=instrument_id, ordId=order_id)
            if result.get('code') == '0':
                return f"✅ Order {result['data'][0].get('ordId')} successfully canceled."
            else:
                return f"❌ Error canceling order: {result.get('msg')}"
        except Exception as e:
            return f"❌ A critical error occurred during the API call: {e}"

    def get_open_orders(self, instrument_id=None):
        print(f"\n-> Requesting open orders{' for ' + instrument_id if instrument_id else ''}...")
        output_lines = []
        try:
            result = self.trade_api.get_order_list(instType='MARGIN', instId=instrument_id)
            if result.get('code') == '0':
                orders = result.get('data', [])
                if orders:
                    output_lines.append(f"Found {len(orders)} open orders:")
                    for order in orders:
                        output_lines.append(f"  - ID: {order['ordId']}, Instrument: {order['instId']}, Side: {order['side']}, Price: {order['px']}, Size: {order['sz']}")
                else:
                    output_lines.append("No open orders found.")
            else:
                output_lines.append(f"❌ Error getting order list: {result.get('msg')}")
        except Exception as e:
            output_lines.append(f"❌ A critical error occurred during the API call: {e}")

        return "\n".join(output_lines)


    def get_open_positions(self, instrument_id=None):
        """
        Retrieves and formats a list of all open positions.
        *** FIX 2: Uses P/L and price data to correctly determine LONG/SHORT for 'net' positions. ***
        """
        print(f"\n-> Requesting open positions{' for ' + instrument_id if instrument_id else ''}...")
        output_lines = []
        try:
            result = self.account_api.get_positions(instType='MARGIN', instId=instrument_id)
            if result.get('code') == '0':
                positions = result.get('data', [])
                active_positions = [p for p in positions if p.get('pos') and float(p.get('pos')) != 0]

                if active_positions:
                    output_lines.append(f"Found {len(active_positions)} open position(s):")
                    for pos in active_positions:
                        pos_side_from_api = pos.get('posSide')
                        display_side = "UNKNOWN"

                        # --- START OF NEW LOGIC ---
                        if pos_side_from_api in ['long', 'short']:
                            display_side = pos_side_from_api.upper()
                        elif pos_side_from_api == 'net':
                            try:
                                # Use price and P/L to determine the true side
                                avg_px = float(pos.get('avgPx'))
                                mark_px = float(pos.get('markPx'))
                                upl = float(pos.get('upl'))

                                if mark_px > avg_px:
                                    # Price went up. If P/L is positive, it's a LONG. If negative, it's a SHORT.
                                    display_side = 'LONG' if upl >= 0 else 'SHORT'
                                elif mark_px < avg_px:
                                    # Price went down. If P/L is positive, it's a SHORT. If negative, it's a LONG.
                                    display_side = 'SHORT' if upl >= 0 else 'LONG'
                                else:
                                    # Prices are equal, side is neutral until there's P/L
                                    display_side = 'NEUTRAL'

                            except (ValueError, TypeError):
                                display_side = 'INSUFFICIENT_DATA'
                        # --- END OF NEW LOGIC ---

                        output_lines.append(
                            f"  - Instrument: {pos.get('instId')}, "
                            f"Side: {display_side}, "
                            # NOTE: The 'Size' field from the API remains ambiguous.
                            # For now, we report what the API gives us but acknowledge it can be misleading.
                            f"Size (from API): {pos.get('pos')}, "
                            f"Avg Price: {pos.get('avgPx')}, "
                            f"Unrealized P/L: {pos.get('upl')}"
                        )
                else:
                    output_lines.append("No open positions found.")
            else:
                output_lines.append(f"❌ Error getting positions: {result.get('msg')}")
        except Exception as e:
            output_lines.append(f"❌ A critical error occurred during the API call: {e}")
        return "\n".join(output_lines)

# --- USAGE EXAMPLE ---
if __name__ == "__main__":
    trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
    instrument = 'BTC-USDT'

    limits_info_string = trader.get_max_order_limits(instrument)
    print(limits_info_string)

    test_price = 10000
    test_size = 0.0001

    place_order_result_string = trader.place_limit_order_with_leverage(
        instrument, 'buy', test_size, test_price
    )
    print(place_order_result_string)
    if "successfully" in place_order_result_string:
        match = re.search(r'Order ID: (\d+)', place_order_result_string)
        if match:
            order_id_to_cancel = match.group(1)
            print(f"\nExtracted Order ID to cancel: {order_id_to_cancel}")

            print("\n--- Waiting 2 seconds for the order to appear in the system ---")
            time.sleep(2)

            open_orders_string = trader.get_open_orders(instrument)
            print(open_orders_string)

            cancel_result_string = trader.cancel_order(instrument, order_id_to_cancel)
            print(cancel_result_string)

            print("\n--- Waiting 2 seconds for the cancellation to process ---")
            time.sleep(2)

            final_orders_string = trader.get_open_orders(instrument)
            print(final_orders_string)

        else:
            print("\nCould not find Order ID in the response message.")
    else:
        print("\nOrder placement failed, skipping cancellation test.")
