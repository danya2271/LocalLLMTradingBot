import requests
import pandas as pd

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

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        dict: A dictionary of pandas DataFrames with formatted timestamps and volumes.
    """
    print("Info for",instId)
    intervals = ['1m', '5m', '1H'] # Reduced intervals for brevity
    market_data = {}
    for interval in intervals:
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()['data']
            columns = [
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_currency_quote', 'confirm'
            ]

            df = pd.DataFrame(data, columns=columns)
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%H:%M:%S')

            df.set_index('timestamp', inplace=True)

            volume_cols = ['volume', 'volume_currency', 'volume_currency_quote']

            # First, ensure columns are numeric for processing
            for col in volume_cols:
                df[col] = pd.to_numeric(df[col])

            # MODIFIED: Apply the human-readable formatting for display
            for col in volume_cols:
                df[col] = df[col].apply(human_format)

            market_data[interval] = df
        else:
            market_data[interval] = f"Error fetching data for {interval}: {response.text}"

    return market_data

# Example usage:
if __name__ == '__main__':
    btc_market_data = get_okx_market_data('BTC-USDT')
    for timeframe, data in btc_market_data.items():
        print(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            # Sort by timestamp to ensure the latest data is last
            print(data.sort_index().tail(50))
        else:
            print(data)
