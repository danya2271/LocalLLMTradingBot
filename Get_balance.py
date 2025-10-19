from okx import OkxRestClient

from Config import *

# Initialize the Account API client
try:
    # The client handles different API sections as attributes (e.g., .account, .public, .trade)
    client = OkxRestClient(api_key, secret_key, passphrase)

    # Fetch the account balance
    # The result object is directly the response data
    result = client.account.get_balance()

    # Check if the API call was successful by inspecting the 'code' key
    if result and result.get('code') == '0':
        print("Successfully connected to the OKX API.")
        print("Account Balance:")
        # The balance details are in the 'data' field, which is a list
        for balance in result['data'][0]['details']:
            print(f"  Currency: {balance['ccy']}")
            print(f"  Available Balance: {balance['availBal']}")
            print(f"  Frozen Balance: {balance['frozenBal']}")
            print("-" * 20)
    else:
        print("Failed to retrieve account balance.")
        print(f"Error details: {result.get('msg')}")

except Exception as e:
    print(f"An error occurred: {e}")
