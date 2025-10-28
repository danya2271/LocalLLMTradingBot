import requests
import pandas as pd

def get_okx_market_data(instId='BTC-USDT'):
    """
    Fetches candlestick data for a given instrument ID from the OKX API.

    Args:
        instId (str): The instrument ID (e.g., 'BTC-USDT').

    Returns:
        dict: A dictionary where keys are timeframes and values are pandas DataFrames
              containing the latest candlestick data.
    """
    print("Info for",instId)
    intervals = ['1m', '5m', '15m', '1H']
    market_data = {}
    for interval in intervals:
        url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={interval}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()['data']

            # CORRECTED: Added column names for all 9 fields returned by the API.
            columns = [
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_currency_quote', 'confirm'
            ]

            df = pd.DataFrame(data, columns=columns)

            df['timestamp'] = pd.to_numeric(df['timestamp'])

            # Convert timestamp to a readable datetime format
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Set timestamp as the index for easier plotting and analysis
            df.set_index('timestamp', inplace=True)

            # Define the columns to format
            volume_cols = ['volume', 'volume_currency', 'volume_currency_quote']

            # Convert columns to numeric type and round to 2 decimal places
            for col in volume_cols:
                df[col] = pd.to_numeric(df[col]).round(0).astype(int)

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
