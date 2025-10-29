import okx.Account as Account
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
        account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, '0') # '0' for live trading

        result = account_api.get_account_balance()

        if result and result.get('code') == '0':
            output_lines.append("Account Balance:")

            for balance in result['data'][0]['details']:
                ccy = balance.get('ccy', 'N/A')
                if ccy == base_currency or ccy == quote_currency:
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
                    output_lines.append(f"  Net Equity: {equity}")
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
