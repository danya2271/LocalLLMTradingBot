import requests
import pandas as pd
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
    """
    Fetches and formats candlestick data from the OKX API.

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        dict: A dictionary of pandas DataFrames containing the requested market data.
    """
    print("Fetching candlestick info for", instId)
    intervals = ['1m', '5m', '1H']
    market_data = {}

    for interval in intervals:
        # This is the most reliable way to get the latest 100 candles from the API.
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}"

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get('data')
            if not data:
                market_data[interval] = f"No data returned from API for {interval}. The endpoint may be temporarily unavailable or the pair is not traded."
                continue

            # Full list of columns returned by the API
            columns = [
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_currency_quote', 'confirm'
            ]

            df = pd.DataFrame(data, columns=columns)

            # Select only the required columns
            df = df[['timestamp', 'high', 'low', 'close', 'volume', 'confirm']]

            # Convert timestamp to a readable format
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%H:%M')

            # Convert data columns to numeric types
            numeric_cols = ['high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col])

            # Set timestamp as the index
            df.set_index('timestamp', inplace=True)

            # The API returns the latest data first, so we reverse it to have time ascend.
            df = df.iloc[::-1]

            # Format only the 'volume' column
            df['volume'] = df['volume'].apply(human_format)

            market_data[interval] = df
        else:
            market_data[interval] = f"Error fetching data for {interval}: Status {response.status_code} - {response.text}"

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
