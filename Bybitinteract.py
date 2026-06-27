import time
import hmac
import hashlib
import json
import requests
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from urllib.parse import urlencode
from bybit_config import (
    BYBIT_API_KEY, BYBIT_SECRET_KEY, BYBIT_IS_DEMO,
    HTTP_TIMEOUT, MIN_NOTIONAL_USDT,
)

class BybitTrader:
    def __init__(self, api_key, secret_key, is_demo=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.is_demo = is_demo

        # Base URL setup
        self.base_url = "https://api-testnet.bybit.com" if is_demo else "https://api.bybit.com"
        self.recv_window = "5000"
        # Cache of per-symbol instrument filters (tickSize/qtyStep/minOrderQty/minNotional)
        self._filters_cache = {}
        print(f"BybitTrader initialized in {'DEMO (Testnet)' if is_demo else 'LIVE (Mainnet)'} mode.")

    def _set_trading_stop(self, symbol, stop_loss_price_str):
        """ Устанавливает новый StopLoss для активной позиции (Безубыток) """
        params = {
            "category": "linear",
            "symbol": symbol,
            "stopLoss": stop_loss_price_str, # Передаем как строку
            "positionIdx": 0 # 0 для One-Way Mode
        }

        result = self._request("POST", "/v5/position/trading-stop", params)

        if str(result.get("retCode")) == "0":
            print(f"   ✅ [Bybit] Stop Loss successfully updated to {stop_loss_price_str} (Breakeven)")
        # Ошибка 34040 означает, что стоп уже стоит на этой цене (Not modified)
        elif str(result.get("retCode")) != "34040":
            print(f"   ❌ [Bybit] Failed to update SL: {result.get('retMsg')}")


    def update_stop_loss_to_breakeven(self, instrument_id, atr_value):
        """
        Переводит сделку в безубыток.
        Если профит достигает 1.5 ATR (половина пути до TP = 3.0 ATR),
        SL передвигается на среднюю цену входа (avgPrice).
        """
        symbol = self._format_symbol(instrument_id)
        params = {"category": "linear", "symbol": symbol, "settleCoin": "USDT"}

        # Получаем список активных позиций
        result = self._request("GET", "/v5/position/list", params)

        if str(result.get("retCode")) == "0":
            positions = result.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get("size", "0")) > 0]

            for pos in active_positions:
                side = pos.get('side')
                avg_price_str = pos.get('avgPrice') # Строка с точной ценой входа от биржи

                avg_price = float(avg_price_str)
                mark_price = float(pos.get('markPrice', '0'))

                sl_str = pos.get('stopLoss', '0')
                current_sl = float(sl_str) if sl_str else 0.0

                threshold = 1.5 * atr_value # Порог срабатывания

                # 1. Логика для LONG
                if side == "Buy":
                    profit_distance = mark_price - avg_price
                    # Профит больше порога И текущий стоп все еще ниже цены входа
                    if profit_distance >= threshold and current_sl < avg_price:
                        print(f"\n🛡️ Breakeven triggered! Profit > 1.5 ATR. Moving SL to {avg_price_str} for LONG {symbol}")
                        self._set_trading_stop(symbol, avg_price_str)

                # 2. Логика для SHORT
                elif side == "Sell":
                    profit_distance = avg_price - mark_price
                    # Профит больше порога И текущий стоп все еще выше цены входа (или равен 0)
                    if profit_distance >= threshold and (current_sl > avg_price or current_sl == 0):
                        print(f"\n🛡️ Breakeven triggered! Profit > 1.5 ATR. Moving SL to {avg_price_str} for SHORT {symbol}")
                        self._set_trading_stop(symbol, avg_price_str)

    def _format_symbol(self, instrument_id):
        """ Converts OKX style 'SOL-USDT' to Bybit style 'SOLUSDT' """
        if instrument_id:
            return instrument_id.replace("-", "").upper()
        return None

    def get_instrument_filters(self, instrument_id):
        """
        Fetches and caches per-symbol trading filters from Bybit:
        tickSize, qtyStep, minOrderQty, maxOrderQty, minNotional.
        Returns a dict, or None if it cannot be fetched.
        """
        symbol = self._format_symbol(instrument_id)
        if not symbol:
            return None
        if symbol in self._filters_cache:
            return self._filters_cache[symbol]

        result = self._request(
            "GET", "/v5/market/instruments-info",
            {"category": "linear", "symbol": symbol},
        )
        if str(result.get("retCode")) != "0":
            print(f"   ❌ [Bybit] Could not fetch instrument filters for {symbol}: {result.get('retMsg')}")
            return None

        lst = result.get("result", {}).get("list", [])
        if not lst:
            print(f"   ❌ [Bybit] No instrument info returned for {symbol}.")
            return None

        info = lst[0]
        price_f = info.get("priceFilter", {})
        lot_f = info.get("lotSizeFilter", {})
        try:
            filters = {
                "tickSize": Decimal(str(price_f.get("tickSize", "0.0001"))),
                "qtyStep": Decimal(str(lot_f.get("qtyStep", "0.001"))),
                "minOrderQty": Decimal(str(lot_f.get("minOrderQty", "0"))),
                "maxOrderQty": Decimal(str(lot_f.get("maxOrderQty", "0")) or "0"),
                "minNotional": Decimal(str(lot_f.get("minNotionalValue", MIN_NOTIONAL_USDT))),
            }
        except Exception as e:
            print(f"   ❌ [Bybit] Failed to parse filters for {symbol}: {e}")
            return None

        self._filters_cache[symbol] = filters
        return filters

    @staticmethod
    def _quantize_down(value, step):
        """ Rounds value DOWN to the nearest multiple of step (Decimal), preserving step precision. """
        v = Decimal(str(value))
        s = Decimal(str(step))
        if s <= 0:
            return v
        return (v / s).to_integral_value(rounding=ROUND_DOWN) * s

    @staticmethod
    def _quantize_nearest(value, step):
        """ Rounds value to the NEAREST multiple of step (Decimal), preserving step precision. """
        v = Decimal(str(value))
        s = Decimal(str(step))
        if s <= 0:
            return v
        return (v / s).to_integral_value(rounding=ROUND_HALF_UP) * s

    def round_qty(self, instrument_id, raw_qty):
        """ Floor qty to the symbol's qtyStep. Returns Decimal, or None if filters unavailable. """
        filters = self.get_instrument_filters(instrument_id)
        if not filters:
            return None
        return self._quantize_down(raw_qty, filters["qtyStep"])

    def round_price(self, instrument_id, raw_price):
        """ Round price to the symbol's tickSize. Returns Decimal, or None if filters unavailable. """
        filters = self.get_instrument_filters(instrument_id)
        if not filters:
            return None
        return self._quantize_nearest(raw_price, filters["tickSize"])

    def set_leverage(self, instrument_id, leverage):
        """ Sets buy/sell leverage for a symbol. Idempotent (tolerates 'not modified'). """
        symbol = self._format_symbol(instrument_id)
        params = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }
        result = self._request("POST", "/v5/position/set-leverage", params)
        code = str(result.get("retCode"))
        # 110043 = leverage not modified (already set) -> treat as success
        if code == "0" or code == "110043":
            return True
        print(f"   ❌ [Bybit] Failed to set leverage for {symbol}: {result.get('retMsg')} (Code: {code})")
        return False

    def has_open_position(self, instrument_id):
        """ Returns True if there is an active (size > 0) position on the symbol. """
        symbol = self._format_symbol(instrument_id)
        result = self._request(
            "GET", "/v5/position/list",
            {"category": "linear", "symbol": symbol, "settleCoin": "USDT"},
        )
        if str(result.get("retCode")) != "0":
            # Fail safe: if we cannot confirm, assume a position may exist to avoid stacking.
            print(f"   ⚠️ [Bybit] Could not verify positions for {symbol}; assuming one exists.")
            return True
        positions = result.get("result", {}).get("list", [])
        return any(float(p.get("size", 0) or 0) > 0 for p in positions)

    def has_open_order(self, instrument_id):
        """ Returns True if there is a resting open order on the symbol. """
        symbol = self._format_symbol(instrument_id)
        result = self._request(
            "GET", "/v5/order/realtime",
            {"category": "linear", "symbol": symbol},
        )
        if str(result.get("retCode")) != "0":
            print(f"   ⚠️ [Bybit] Could not verify open orders for {symbol}; assuming one exists.")
            return True
        orders = result.get("result", {}).get("list", [])
        return len(orders) > 0

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
                response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
            else:
                response = requests.post(url, headers=headers, data=payload, timeout=HTTP_TIMEOUT)

            return response.json()
        except Exception as e:
            return {"retCode": -1, "retMsg": str(e)}

    def place_limit_order_with_tp_sl(self, instrument_id, side, size, price, take_profit_price, stop_loss_price):
        """
        Places a limit order with TP/SL attached natively (Bybit supports this in a single call).

        Quantizes qty/price/TP/SL to the symbol's exchange filters and validates the order
        before sending. Returns a structured dict:
            {'ok': bool, 'orderId': str|None, 'retCode': int|str, 'retMsg': str}
        """
        symbol = self._format_symbol(instrument_id)
        side_capitalized = "Buy" if side.lower() == "buy" else "Sell"

        filters = self.get_instrument_filters(instrument_id)
        if not filters:
            return {"ok": False, "orderId": None, "retCode": -2,
                    "retMsg": f"Could not fetch instrument filters for {symbol}; order not sent."}

        # Quantize quantity DOWN to the step so notional never exceeds the intended budget.
        qty_d = self._quantize_down(size, filters["qtyStep"])
        min_qty = filters["minOrderQty"]
        max_qty = filters["maxOrderQty"]
        if qty_d <= 0 or (min_qty > 0 and qty_d < min_qty):
            return {"ok": False, "orderId": None, "retCode": -3,
                    "retMsg": f"Qty {qty_d} below minOrderQty {min_qty} for {symbol}; skipped."}
        if max_qty > 0 and qty_d > max_qty:
            qty_d = max_qty

        # Quantize prices to the tick.
        entry_d = self._quantize_nearest(price, filters["tickSize"])
        tp_d = self._quantize_nearest(take_profit_price, filters["tickSize"])
        sl_d = self._quantize_nearest(stop_loss_price, filters["tickSize"])

        if entry_d <= 0:
            return {"ok": False, "orderId": None, "retCode": -4,
                    "retMsg": f"Invalid entry price {entry_d} for {symbol}; skipped."}

        # Direction-coherence check: TP/SL must be on the correct side of entry.
        if side_capitalized == "Buy":
            if not (sl_d < entry_d < tp_d):
                return {"ok": False, "orderId": None, "retCode": -5,
                        "retMsg": f"Incoherent LONG levels SL={sl_d} entry={entry_d} TP={tp_d}; skipped."}
        else:
            if not (tp_d < entry_d < sl_d):
                return {"ok": False, "orderId": None, "retCode": -5,
                        "retMsg": f"Incoherent SHORT levels TP={tp_d} entry={entry_d} SL={sl_d}; skipped."}

        # Minimum notional guard.
        notional = qty_d * entry_d
        if notional < filters["minNotional"]:
            return {"ok": False, "orderId": None, "retCode": -6,
                    "retMsg": f"Notional {notional} below minNotional {filters['minNotional']} for {symbol}; skipped."}

        qty_s, price_s = str(qty_d), str(entry_d)
        tp_s, sl_s = str(tp_d), str(sl_d)

        print(f"\n-> Placing {side.upper()} limit order with ATTACHED TP/SL for {symbol}...")
        print(f"   Main Order: {qty_s} at {price_s}")
        print(f"   Take Profit will be attached at: {tp_s}")
        print(f"   Stop Loss will be attached at: {sl_s}")

        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side_capitalized,
            "orderType": "Limit",
            "qty": qty_s,
            "price": price_s,
            "takeProfit": tp_s,
            "stopLoss": sl_s,
            "tpslMode": "Full",  # Apply TP/SL to the entire order
            "timeInForce": "GTC"
        }

        result = self._request("POST", "/v5/order/create", params)
        ret_code = str(result.get("retCode"))

        if ret_code == "0":
            order_id = result.get("result", {}).get("orderId", "UNKNOWN")
            print(f"   ✅ Limit order with TP/SL placed successfully! Order ID: {order_id}")
            return {"ok": True, "orderId": order_id, "retCode": 0,
                    "retMsg": f"OK (Entry: {price_s}, SL: {sl_s}, TP: {tp_s})"}
        else:
            ret_msg = result.get("retMsg")
            print(f"   ❌ Error placing order: {ret_msg} (Code: {ret_code})")
            return {"ok": False, "orderId": None, "retCode": ret_code, "retMsg": str(ret_msg)}

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

    def get_available_balance(self, coin_pair):
        """
        Returns available (free) Quote Currency margin as a float from Bybit.

        Returns None when the balance cannot be determined (API/network error) so callers
        can distinguish a real zero balance from a transient failure and avoid acting on it.
        """
        try:
            # Handle invalid/null inputs gracefully
            if not coin_pair or coin_pair.lower() == "null":
                return 0.0

            # Extract quote currency (e.g., SOL-USDT -> USDT, or SOLUSDT -> USDT)
            if '-' in coin_pair:
                quote_currency = coin_pair.split('-')[1]
            elif coin_pair.endswith('USDT'):
                quote_currency = 'USDT'
            elif coin_pair.endswith('USDC'):
                quote_currency = 'USDC'
            else:
                quote_currency = coin_pair

            print(f"\n-> Fetching balance for {quote_currency}...")

            # First try Unified Trading Account (UTA)
            params = {
                "accountType": "UNIFIED",
                "coin": quote_currency
            }
            result = self._request("GET", "/v5/account/wallet-balance", params)

            # ONLY fallback to CONTRACT if the API explicitly returns an error for UNIFIED
            # (Do not fallback if the request succeeds but the balance is simply 0)
            if str(result.get("retCode")) != "0":
                params["accountType"] = "CONTRACT"
                result = self._request("GET", "/v5/account/wallet-balance", params)

            # Process the response
            if str(result.get("retCode")) == "0":
                list_data = result.get("result", {}).get("list", [])

                # If list_data is empty, the account exists but has 0 balance
                if not list_data:
                    return 0.0

                account = list_data[0]
                coins = account.get("coin", [])
                # If coins array is empty, the specific coin has 0 balance
                if not coins:
                    return 0.0

                # Find the specific coin and return its FREE balance (not total equity).
                for c in coins:
                    if c.get("coin") == quote_currency:
                        # Prefer genuinely available margin; fall back through sensible fields.
                        for field in ("availableToWithdraw", "availableBalance", "free"):
                            val = c.get(field)
                            if val not in (None, ""):
                                return float(val)
                        # Account-level free balance for cross-margin UNIFIED accounts.
                        acct_avail = account.get("totalAvailableBalance")
                        if acct_avail not in (None, ""):
                            return float(acct_avail)
                        # Last resort: total wallet equity (overstates free funds).
                        return float(c.get("walletBalance", 0.0))

                # If loop finishes and coin isn't found, balance is 0
                return 0.0

            # Could not determine balance -> signal failure rather than a misleading 0.0
            print(f"❌ Error getting balance: {result.get('retMsg', result)}")
            return None

        except Exception as e:
            print(f"Exception inside get_available_balance: {e}")
            return None

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
