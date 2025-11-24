import okx.Account as Account
import okx.Trade as Trade
import okx.PublicData as Public
from decimal import Decimal, ROUND_DOWN
import time
import re
import uuid
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

    def get_max_order_limits_quantity(self, instrument_id):
        try:
            result = self.account_api.get_max_order_size(instId=instrument_id, tdMode='cross', ccy='USDT')
            if result.get('code') == '0':
                data = result['data'][0]
                max_buy, max_sell = data.get('maxBuy'), data.get('maxSell')
                return max_buy, max_sell
            else:
                return 0, 0
        except Exception as e:
            return 0, 0

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



    def place_limit_order_with_tp_sl(self, instrument_id, side, size, price, take_profit_price, stop_loss_price):
        print(f"\n-> Placing {side.upper()} limit order with ATTACHED TP/SL for {instrument_id}...")
        print(f"   Main Order: {size} at {price}")
        print(f"   Take Profit will be attached at: {take_profit_price}")
        print(f"   Stop Loss will be attached at: {stop_loss_price}")

        main_order_params = {
            'instId': instrument_id,
            'tdMode': 'cross',
            'side': side,
            'ordType': 'limit',
            'sz': str(size),
            'px': str(price),
            'ccy': 'USDT'
        }

        closing_side = 'sell' if side == 'buy' else 'buy'
        pos_side = 'long' if side == 'buy' else 'short'

        attached_oco_params = {
            "algoClOrdId": f"oco-{instrument_id}-{int(time.time() * 1000)}",
            "ordType": "oco",
            "sz": str(size),
            "side": closing_side,
            "posSide": pos_side,
            "tpTriggerPx": str(take_profit_price),
            "tpOrdPx": str(take_profit_price),
            "slTriggerPx": str(stop_loss_price),
            "slOrdPx": str(stop_loss_price),
        }

        main_order_params['attachAlgoOrds'] = [attached_oco_params]

        try:
            result = self.trade_api._request_with_params('POST', '/api/v5/trade/order', main_order_params)

            if str(result.get('code')) == '0':
                order_id = result['data'][0].get('ordId')
                return f"✅ Limit order with attached TP/SL placed successfully! Main Order ID: {order_id}"
            else:
                error_msg = result.get('msg', '')
                try:
                    detailed_msg = result['data'][0].get('sMsg', '')
                    if detailed_msg:
                        error_msg = detailed_msg
                except (IndexError, KeyError, TypeError):
                    pass

                error_code = result.get('code', 'N/A')
                return f"❌ Error placing order: {error_msg} (Code: {error_code})"
        except Exception as e:
            return f"❌ A critical error occurred during the API call: {e}"





    def cancel_order(self, instrument_id, order_id):
        print(f"\n-> Attempting to cancel ID: {order_id} for {instrument_id}...")

        try:
            result = self.trade_api.cancel_order(instId=instrument_id, ordId=order_id)

            if result.get('code') == '0':
                return f"✅ Standard Order {order_id} canceled."

            print(f"   (Standard cancel failed: {result.get('msg')}. Trying Algo cancel...)")

        except Exception as e:
            print(f"   (Standard cancel exception: {e}. Trying Algo cancel...)")

        try:
            params = [{'instId': instrument_id, 'algoId': order_id}]
            result_algo = self.trade_api.cancel_algo_order(params)

            if result_algo.get('code') == '0':
                return f"✅ Algo Order {order_id} canceled successfully."
            else:
                return f"❌ Failed to cancel {order_id}. Algo Error: {result_algo.get('msg')}"

        except Exception as e:
            return f"❌ Critical error during Algo cancel: {e}"



    def get_open_orders(self, instrument_id=None):
        print(f"\n-> Requesting open orders{' for ' + instrument_id if instrument_id else ''}...")
        output_lines = []

        # --- 1. Fetch Standard Orders (Limit/Market) ---
        try:
            result = self.trade_api.get_order_list(instType='MARGIN', instId=instrument_id)
            if result.get('code') == '0':
                orders = result.get('data', [])
                if orders:
                    output_lines.append(f"--- Standard Orders ({len(orders)}) ---")
                    for order in orders:
                        output_lines.append(f"  [STD] ID: {order['ordId']}, Type: {order['ordType']}, Side: {order['side']}, Price: {order['px']}, Size: {order['sz']}")
                else:
                    output_lines.append("No standard open orders found.")
            else:
                output_lines.append(f"❌ Error getting standard list: {result.get('msg')}")
        except Exception as e:
            output_lines.append(f"❌ Critical error fetching standard orders: {e}")

        # --- 2. Fetch Algo Orders (Looping through specific types) ---
        # We must request 'oco' and 'trigger' separately because the API rejects combined strings.
        target_algo_types = ['oco', 'trigger']

        found_algos = False
        for a_type in target_algo_types:
            try:
                # Request specific type
                result_algo = self.trade_api.order_algos_list(instType='MARGIN', instId=instrument_id, ordType=a_type)

                if result_algo.get('code') == '0':
                    algos = result_algo.get('data', [])
                    if algos:
                        if not found_algos:
                            output_lines.append(f"\n--- Algo/TP/SL Orders ---")
                            found_algos = True

                        for algo in algos:
                            output_lines.append(f"  [{a_type.upper()}] ID: {algo['algoId']}, Side: {algo['side']}, Size: {algo['sz']}, SL: {algo.get('slOrdPx', 'N/A')}, TP: {algo.get('tpOrdPx', 'N/A')}")
                else:
                    # Ignore "code 0" with empty data, but log errors
                    if result_algo.get('code') != '0':
                         output_lines.append(f"❌ Error getting {a_type} list: {result_algo.get('msg')}")

            except Exception as e:
                output_lines.append(f"❌ Critical error fetching {a_type} orders: {e}")

        if not found_algos:
            output_lines.append("No Algo (TP/SL) orders found.")

        return "\n".join(output_lines)


    def get_open_positions(self, instrument_id=None):
        """
        Retrieves and formats open MARGIN positions.
        This function is robustly designed for CROSS MARGIN, which always returns 'posSide: "net"'.
        It uses a fallback P/L analysis to correctly deduce the long/short direction.
        """
        instrument_type = 'MARGIN'

        print(f"\n-> Requesting open positions for {instrument_type}{' on ' + instrument_id if instrument_id else ''}...")
        output_lines = []
        try:
            result = self.account_api.get_positions(instType=instrument_type, instId=instrument_id)

            if result.get('code') == '0':
                positions = result.get('data', [])
                active_positions = [p for p in positions if p.get('pos') and float(p.get('pos')) != 0]

                if active_positions:
                    output_lines.append(f"Found {len(active_positions)} open position(s):")
                    for pos in active_positions:
                        pos_side_from_api = pos.get('posSide')
                        mgn_mode = pos.get('mgnMode')
                        display_side = "UNKNOWN"

                        if pos_side_from_api == 'net':
                            try:
                                avg_px = float(pos.get('avgPx'))
                                mark_px = float(pos.get('markPx'))
                                upl = float(pos.get('upl'))

                                if upl == 0 or avg_px == mark_px:
                                    display_side = 'NEUTRAL (from net)'
                                else:
                                    price_delta = mark_px - avg_px
                                    if (price_delta * upl) > 0:
                                        display_side = 'LONG (from net)'
                                    elif (price_delta * upl) < 0:
                                        display_side = 'SHORT (from net)'
                            except (ValueError, TypeError, ZeroDivisionError):
                                display_side = 'INSUFFICIENT_DATA (from net)'

                        elif pos_side_from_api in ['long', 'short']:
                            display_side = pos_side_from_api.upper()

                        if display_side == 'SHORT (from net)':
                            total_size = float(pos.get('pos')) / float(pos.get('avgPx'))
                        else:
                            total_size = pos.get('pos')

                        output_lines.append(
                            f"  - Instrument: {pos.get('instId')}, "
                            f"Mode: {mgn_mode}, "
                            f"Side: {display_side}, "
                            f"Size: {total_size} SOL, "
                            f"Avg Price: {pos.get('avgPx')}, "
                            f"Unrealized P/L: {pos.get('upl')}"
                        )
                else:
                    output_lines.append(f"No open positions found for {instrument_type}.")
            else:
                output_lines.append(f"❌ Error getting positions: {result.get('msg')}")
        except Exception as e:
            output_lines.append(f"❌ A critical error occurred during the API call: {e}")

        return "\n".join(output_lines)

    def close_all_orders_and_positions(self):
        """
        Closes all open orders, close all open positions using the dedicated endpoint.
        """
        print(f"\n🚨 Initiating full closure of all open orders and positions...")

        # Cancel all open orders
        print("\n-> Step 1: Canceling all open orders...")
        try:
            open_orders_result = self.trade_api.get_order_list()
            if open_orders_result.get('code') == '0':
                orders_to_cancel = open_orders_result.get('data', [])
                if not orders_to_cancel:
                    print("✅ No open orders to cancel.")
                else:
                    for order in orders_to_cancel:
                        print(f"   - Canceling order {order['ordId']} for {order['instId']}...")
                        self.trade_api.cancel_order(instId=order['instId'], ordId=order['ordId'])
            else:
                print(f"❌ Error fetching open orders: {open_orders_result.get('msg')}")
        except Exception as e:
            print(f"❌ A critical error occurred during order cancellation: {e}")

        # Cancel all open algo orders
        print("\n-> Step 2: Canceling all Algo orders (TP/SL/OCO)...")
        target_algo_types = ['oco', 'trigger']

        for a_type in target_algo_types:
            try:
                algo_result = self.trade_api.order_algos_list(instType='MARGIN', state='live', ordType=a_type)

                if algo_result.get('code') == '0':
                    algos_to_cancel = algo_result.get('data', [])
                    if algos_to_cancel:
                        algo_cancel_list = []
                        for algo in algos_to_cancel:
                            print(f"   - Found {a_type.upper()} ID: {algo['algoId']}")
                            algo_cancel_list.append({'algoId': algo['algoId'], 'instId': algo['instId']})

                        if algo_cancel_list:
                            cancel_resp = self.trade_api.cancel_algo_order(algo_cancel_list)
                            if cancel_resp.get('code') == '0':
                                 print(f"   ✅ {a_type.upper()} orders canceled.")
                            else:
                                 print(f"   ❌ Error canceling {a_type}: {cancel_resp.get('msg')}")
                    else:
                        print(f"   - No active {a_type.upper()} orders.")
            except Exception as e:
                print(f"   ❌ Critical error handling {a_type}: {e}")

        time.sleep(1)

        # Close all open positions using the dedicated endpoint
        print("\n-> Step 2: Canceling all Algo orders (TP/SL/OCO)...")

        target_algo_types = ['oco', 'trigger']

        for a_type in target_algo_types:
            try:
                algo_result = self.trade_api.order_algos_list(instType='MARGIN', ordType=a_type)

                if algo_result.get('code') == '0':
                    algos_to_cancel = algo_result.get('data', [])
                    if algos_to_cancel:
                        algo_cancel_list = []
                        for algo in algos_to_cancel:
                            print(f"   - Found {a_type.upper()} ID: {algo['algoId']}")
                            algo_cancel_list.append({'algoId': algo['algoId'], 'instId': algo['instId']})

                        if algo_cancel_list:
                            cancel_resp = self.trade_api.cancel_algo_order(algo_cancel_list)
                            if cancel_resp.get('code') == '0':
                                 print(f"   ✅ {a_type.upper()} orders canceled.")
                            else:
                                 print(f"   ❌ Error canceling {a_type}: {cancel_resp.get('msg')}")
                    else:
                        print(f"   - No active {a_type.upper()} orders.")
                else:
                    # OKX often returns code 0 with empty data, but if code is non-zero, log it
                    if algo_result.get('code') != '0':
                        print(f"   ❌ Error fetching {a_type}: {algo_result.get('msg')}")
            except Exception as e:
                print(f"   ❌ Critical error handling {a_type}: {e}")


# --- USAGE EXAMPLE ---
if __name__ == "__main__":
    trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
    instrument_sol = 'SOL-USDT'

    entry_price = 143.0
    trade_size = 0.06
    tp_price = round(entry_price * 1.030, 2)
    sl_price = round(entry_price * 0.99, 2)

    print(trader.get_open_positions(instrument_sol))
    print (trader.get_open_orders(instrument_sol))
