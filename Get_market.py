import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time
pd.set_option("display.max_rows", None)

def human_format(num):
    """
    A helper function to format large numbers into a human-readable string (e.g., 1000 -> 1K).
    """
    if num is None:
        return 'N/A'
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def get_okx_market_data(instId='BTC-USDT'):
    print(f"Fetching candlestick info for {instId}...")
    intervals = ['15m']
    market_data = {}

    for interval in intervals:
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}"

        # --- RETRY ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Network error (Attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
                if attempt == max_retries - 1:
                    print(f"❌ Failed to get data for {instId} after retries.")
                    return {}
        # ---------------------------------------

        if response.status_code == 200:
            data = response.json().get('data')
            if not data:
                continue

            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm']
            df = pd.DataFrame(data, columns=columns)

            df = df[['timestamp', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            for col in ['high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])

            df.set_index('timestamp', inplace=True)
            df = df.iloc[::-1]

            # Индикаторы
            rsi_ind = RSIIndicator(close=df["close"], window=14)
            df["RSI"] = rsi_ind.rsi()

            ema_ind = EMAIndicator(close=df["close"], window=50)
            df["EMA_50"] = ema_ind.ema_indicator()

            atr_ind = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
            df["ATR"] = atr_ind.average_true_range()

            df.dropna(inplace=True)
            market_data[interval] = df.tail(50)

    return market_data


def get_okx_current_price(instId='BTC-USDT'):
    """
    Fetches the current price of a trading pair from the OKX API.

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        str: The last traded price as a string, or an error message.
    """
    url = f"https://www.okx.com/api/v5/market/ticker?instId={instId}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get('data')
        if data:
            return data[0]['last']
        else:
            return "No data returned from API for this instrument."
    else:
        return f"Error fetching current price: {response.text}"


# --- Example Usage ---
if __name__ == '__main__':
    # Get and display candlestick data
    btc_market_data = get_okx_market_data('BTC-USDT')
    for timeframe, data in btc_market_data.items():
        print(f"\n--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            # Display the last 70 rows to keep the output manageable
            print(data.tail(70))
        else:
            print(data)

    print("\n" + "="*30 + "\n")

    # Get and display the current price
    current_price = get_okx_current_price('BTC-USDT')
    print(f"Current BTC-USDT Price: {current_price}")
