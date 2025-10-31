import requests
import pandas as pd
import time

def human_format(num):
    """Formats a number into a human-readable string with a 'k' for thousands."""
    num = float(f'{num:.2g}')
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return f'{int(num)}{["", "k", "M", "B", "T"][magnitude]}'


def get_okx_market_data(instId='BTC-USDT'):
    """
    Fetches and formats candlestick data from the OKX API for concise display.
    *** FIX: Uses 'after' parameter to correctly fetch data before the current time. ***

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        dict: A dictionary of pandas DataFrames with formatted timestamps and volumes.
    """
    print("Info for", instId)
    intervals = ['1m', '5m', '1H']
    market_data = {}

    # Get a single timestamp to synchronize all API calls.
    end_timestamp = int(time.time() * 1000)

    for interval in intervals:
        # --- FIX: Changed 'before' to 'after' ---
        # Per OKX's confusing documentation, 'after' is used to get data OLDER than the timestamp.
        # This now correctly asks for the most recent candles leading up to the current time.
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}&after={end_timestamp}"

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()['data']
            if not data:
                market_data[interval] = "No data returned from API for this timeframe."
                continue

            columns = [
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_currency_quote', 'confirm'
            ]

            df = pd.DataFrame(data, columns=columns)
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%H:%M')

            df.set_index('timestamp', inplace=True)
            # Reverse the DataFrame so the latest data is at the bottom
            df = df.iloc[::-1]

            volume_cols = ['volume', 'volume_currency', 'volume_currency_quote']

            for col in volume_cols:
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
        data = response.json()['data']
        if data:
            return data[0]['last']
        else:
            return "No data returned from API for this instrument."
    else:
        return f"Error fetching current price: {response.text}"


# Example usage:
if __name__ == '__main__':
    # Get and display candlestick data
    btc_market_data = get_okx_market_data('BTC-USDT')
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            print(data.tail(10))
        else:
            print(data)

    print("\n" + "="*30 + "\n")

    # Get and display the current price
    current_price = get_okx_current_price('BTC-USDT')
    print(f"Current BTC-USDT Price: {current_price}")
