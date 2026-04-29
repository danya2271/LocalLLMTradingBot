import time
import hmac
import hashlib
import json
import requests
from urllib.parse import urlencode
from bybit_config import BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO

class BybitTrader:
    def __init__(self, api_key, secret_key, is_demo=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.is_demo = is_demo

        # Base URL setup
        self.base_url = "https://api-testnet.bybit.com" if is_demo else "https://api.bybit.com"
        self.recv_window = "5000"
        print(f"BybitTrader initialized in {'DEMO (Testnet)' if is_demo else 'LIVE (Mainnet)'} mode.")

    def _format_symbol(self, instrument_id):
        """ Converts OKX style 'SOL-USDT' to Bybit style 'SOLUSDT' """
        if instrument_id:
            return instrument_id.replace("-", "").upper()
        return None

    def _request(self, method, endpoint, params=None):
        """ Handles authentication and sends request to Bybit V5 API """
        timestamp = str(int(time.time() * 1000))
        payload = ""

        if method == "GET":
            if params:
                payload = urlencode(params)
                endpoint = f"{endpoint}?{payload}"
        else:
            if params:
                # Bybit requires compact JSON (no spaces) for the signature
                payload = json.dumps(params, separators=(',', ':'))

        # Create the signature string
        param_str = timestamp + self.api_key + self.recv_window + payload
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            bytes(param_str, "utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "Content-Type": "application/json",
            "User-Agent": "bybit-bot/1.0"
        }

        url = self.base_url + endpoint

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            else:
                response = requests.post(url, headers=headers, data=payload)

            return response.json()
        except Exception as e:
            return {"retCode": -1, "retMsg": str(e)}

    def place_limit_order_with_tp_sl(self, instrument_id, side, size, price, take_profit_price, stop_loss_price):
        """ Places a limit order with TP/SL attached natively (Bybit supports this in a single call) """
        symbol = self._format_symbol(instrument_id)
        side_capitalized = "Buy" if side.lower() == "buy" else "Sell"

        print(f"\n-> Placing {side.upper()} limit order with ATTACHED TP/SL for {symbol}...")
        print(f"   Main Order: {size} at {price}")
        print(f"   Take Profit will be attached at: {take_profit_price}")
        print(f"   Stop Loss will be attached at: {stop_loss_price}")

        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side_capitalized,
            "orderType": "Limit",
            "qty": str(size),
            "price": str(price),
            "takeProfit": str(take_profit_price),
            "stopLoss": str(stop_loss_price),
            "tpslMode": "Full",  # Apply TP/SL to the entire order
            "timeInForce": "GTC"
        }

        result = self._request("POST", "/v5/order/create", params)

        if str(result.get("retCode")) == "0":
            order_id = result.get("result", {}).get("orderId", "UNKNOWN")
            return f"✅ Limit order with TP/SL placed successfully! Order ID: {order_id}"
        else:
            return f"❌ Error placing order: {result.get('retMsg')} (Code: {result.get('retCode')})"

    def cancel_order(self, instrument_id, order_id):
        """ Cancels a specific order """
        symbol = self._format_symbol(instrument_id)
        print(f"\n-> Attempting to cancel ID: {order_id} for {symbol}...")

        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id
        }

        result = self._request("POST", "/v5/order/cancel", params)
        if str(result.get("retCode")) == "0":
            return f"✅ Order {order_id} canceled successfully."
        else:
            return f"❌ Failed to cancel {order_id}. Error: {result.get('retMsg')}"

    def get_open_orders(self, instrument_id=None):
        """ Fetches open orders (Limit, TP/SL, etc.) """
        symbol = self._format_symbol(instrument_id)
        print(f"\n-> Requesting open orders{' for ' + symbol if symbol else ''}...")

        params = {"category": "linear"}
        if symbol:
            params["symbol"] = symbol

        result = self._request("GET", "/v5/order/realtime", params)
        output_lines = []

        if str(result.get("retCode")) == "0":
            orders = result.get("result", {}).get("list", [])
            if orders:
                output_lines.append(f"--- Open Orders ({len(orders)}) ---")
                for order in orders:
                    output_lines.append(
                        f"  ID: {order.get('orderId')}, Type: {order.get('orderType')}, "
                        f"Side: {order.get('side')}, Price: {order.get('price')}, "
                        f"Size: {order.get('qty')}, TP: {order.get('takeProfit', 'N/A')}, "
                        f"SL: {order.get('stopLoss', 'N/A')}"
                    )
            else:
                output_lines.append("No open orders found.")
        else:
            output_lines.append(f"❌ Error getting open orders: {result.get('retMsg')}")

        return "\n".join(output_lines)

    def get_open_positions(self, instrument_id=None):
        """ Fetches currently active positions """
        symbol = self._format_symbol(instrument_id)
        print(f"\n-> Requesting open positions{' for ' + symbol if symbol else ''}...")

        params = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            params["symbol"] = symbol

        result = self._request("GET", "/v5/position/list", params)
        output_lines = []

        if str(result.get("retCode")) == "0":
            positions = result.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]

            if active_positions:
                output_lines.append(f"Found {len(active_positions)} open position(s):")
                for pos in active_positions:
                    output_lines.append(
                        f"  - Instrument: {pos.get('symbol')}, "
                        f"Side: {pos.get('side')}, "
                        f"Size: {pos.get('size')}, "
                        f"Avg Price: {pos.get('avgPrice')}, "
                        f"Unrealized P/L: {pos.get('unrealisedPnl')}"
                    )
            else:
                output_lines.append("No open positions found.")
        else:
            output_lines.append(f"❌ Error getting positions: {result.get('retMsg')}")

        return "\n".join(output_lines)

    def close_all_orders_and_positions(self):
        """ Cancels all open orders and closes all active positions via market orders """
        print(f"\n🚨 Initiating full closure of all open orders and positions on Bybit...")

        # 1. Cancel all active orders
        print("\n-> Step 1: Canceling all open orders...")
        cancel_result = self._request("POST", "/v5/order/cancel-all", {"category": "linear", "settleCoin": "USDT"})
        if str(cancel_result.get("retCode")) == "0":
            print("   ✅ All open orders canceled successfully.")
        else:
            print(f"   ❌ Error canceling orders: {cancel_result.get('retMsg')}")

        time.sleep(1)

        # 2. Close all positions
        print("\n-> Step 2: Closing all open positions...")
        pos_result = self._request("GET", "/v5/position/list", {"category": "linear", "settleCoin": "USDT"})

        if str(pos_result.get("retCode")) == "0":
            positions = pos_result.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]

            if not active_positions:
                print("   ✅ No active positions to close.")
            else:
                for pos in active_positions:
                    symbol = pos.get('symbol')
                    current_side = pos.get('side')
                    size = pos.get('size')

                    # Determine opposite side to close
                    close_side = "Sell" if current_side == "Buy" else "Buy"

                    print(f"   - Closing {size} {symbol} ({current_side} position)...")

                    close_params = {
                        "category": "linear",
                        "symbol": symbol,
                        "side": close_side,
                        "orderType": "Market",
                        "qty": size,
                        "reduceOnly": True # Critical: Ensures we only close the position, not open a new one
                    }

                    close_req = self._request("POST", "/v5/order/create", close_params)
                    if str(close_req.get("retCode")) == "0":
                        print(f"   ✅ Successfully closed {symbol}.")
                    else:
                        print(f"   ❌ Failed to close {symbol}: {close_req.get('retMsg')}")
        else:
            print(f"   ❌ Error fetching positions to close: {pos_result.get('retMsg')}")

# --- USAGE EXAMPLE / TEST ---
if __name__ == "__main__":
    trader = BybitTrader(BYBIT_API_KEY, BYBIT_SECRET_KEY, is_demo=BYBIT_IS_DEMO)
    instrument_sol = 'SOL-USDT' # Will be automatically converted to 'SOLUSDT'

    print(trader.get_open_positions(instrument_sol))
    print(trader.get_open_orders(instrument_sol))
