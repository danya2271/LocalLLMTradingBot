from okx import OkxRestClient
from Logging import log_message
from Config import *


def GetBal(coin):
    """
    Fetches and displays the full account balance from OKX,
    including liabilities to correctly show negative balances (equity).
    """
    output_lines = []

    base_currency, quote_currency = coin.split('-')

    try:
        # The client handles different API sections as attributes (e.g., .account, .public, .trade)
        client = OkxRestClient(api_key, secret_key, passphrase)

        # Fetch the account balance
        # The result object is directly the response data
        result = client.account.get_balance()

        # Check if the API call was successful by inspecting the 'code' key
        if result and result.get('code') == '0':
            # output_lines.append("Successfully connected to the OKX API.")
            output_lines.append("Account Balance:")

            # The balance details are in the 'data' field, which is a list
            for balance in result['data'][0]['details']:
                # Use .get() with a default value '0' for robustness
                ccy = balance.get('ccy', 'N/A')
                if ccy==base_currency or ccy==quote_currency:
                    avail_bal = balance.get('availBal', '0')
                    frozen_bal = balance.get('frozenBal', '0')

                    equity = balance.get('eq', '0')
                    liabilities = balance.get('liab', '0')
                    interest = balance.get('interest', '0')

                    output_lines.append(f"  Currency: {ccy}")
                    output_lines.append(f"  Available Balance: {avail_bal}")
                    output_lines.append(f"  Frozen Balance: {frozen_bal}")

                    output_lines.append(f"  Liabilities (Debt): {liabilities}")
                    output_lines.append(f"  Accrued Interest: {interest}")
                    output_lines.append(f"  Net Equity: {equity}") # This is the value that can be negative

                    output_lines.append("-" * 20)
        else:
            output_lines.append("Failed to retrieve account balance.")
            error_msg = result.get('msg') if result else "No response from API."
            output_lines.append(f"Error details: {error_msg}")

        final_output = "\n".join(output_lines)
        log_message(final_output)
        return final_output

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        output_lines.append(f"An unexpected error occurred: {e}")
        output_lines.append(error_details)

        final_output = "\n".join(output_lines)
        log_message(final_output)
        return final_output
