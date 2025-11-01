import requests
import pandas as pd
import time
pd.set_option("display.max_rows", None)

def human_format(num):
    """
    A helper function to format large numbers into a human-readable string (e.g., 1000 -> 1K).
    This is a placeholder for the function used in your original code.
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
    """
    Fetches and formats candlestick data from the OKX API for concise display.
    *** MODIFIED: Now only processes 'close' and volume columns. ***

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        dict: A dictionary of pandas DataFrames with formatted timestamps, close prices, and volumes.
    """
    print("Fetching candlestick info for", instId)
    intervals = ['1m', '5m', '1H']
    market_data = {}

    end_timestamp = int(time.time() * 1000)

    for interval in intervals:
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}&after={end_timestamp}"

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get('data')
            if not data:
                market_data[interval] = "No data returned from API for this timeframe."
                continue

            columns = [
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_currency_quote', 'confirm'
            ]

            df = pd.DataFrame(data, columns=columns)

            # Select only the columns we need
            df = df[['timestamp', 'close', 'volume', 'volume_currency']]

            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%H:%M')

            df.set_index('timestamp', inplace=True)
            # Reverse the DataFrame so the latest data is at the bottom
            df = df.iloc[::-1]

            # Format volume columns
            for col in ['volume', 'volume_currency']:
                df[col] = pd.to_numeric(df[col])
                df[col] = df[col].apply(human_format)

            market_data[interval] = df
        else:
            market_data[interval] = f"Error fetching data for {interval}: {response.text}"

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
        print(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            print(data.tail(70))
        else:
            print(data)

    print("\n" + "="*30 + "\n")

    # Get and display the current price
    current_price = get_okx_current_price('BTC-USDT')
    print(f"Current BTC-USDT Price: {current_price}")

