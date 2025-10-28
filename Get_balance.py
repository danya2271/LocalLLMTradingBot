from okx import OkxRestClient
from Logging import log_message
from Config import *

def GetBal():
    output_lines = []

    try:
        # The client handles different API sections as attributes (e.g., .account, .public, .trade)
        client = OkxRestClient(api_key, secret_key, passphrase)

        # Fetch the account balance
        # The result object is directly the response data
        result = client.account.get_balance()

        # Check if the API call was successful by inspecting the 'code' key
        if result and result.get('code') == '0':
            output_lines.append("Successfully connected to the OKX API.")
            output_lines.append("Account Balance:")
            # The balance details are in the 'data' field, which is a list
            for balance in result['data'][0]['details']:
                output_lines.append(f"  Currency: {balance['ccy']}")
                output_lines.append(f"  Available Balance: {balance['availBal']}")
                output_lines.append(f"  Frozen Balance: {balance['frozenBal']}")
                output_lines.append("-" * 20)
        else:
            output_lines.append("Failed to retrieve account balance.")
            error_msg = result.get('msg') if result else "No response from API."
            output_lines.append(f"Error details: {error_msg}")

        log_message("\n".join(output_lines))
        return "\n".join(output_lines)

    except Exception as e:
        output_lines.append(f"An error occurred: {e}")
