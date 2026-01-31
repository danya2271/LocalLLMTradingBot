import okx.Account as Account
from Config import *

def GetBal(coin_pair):
    """
    Returns available Quote Currency (usually USDT) as a float.
    """
    try:
        if '-' in coin_pair:
            quote_currency = coin_pair.split('-')[1]
        else:
            quote_currency = coin_pair

        account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, '0')

        result = account_api.get_account_balance(ccy=quote_currency)

        if result and result.get('code') == '0' and result.get('data'):
            details = result['data'][0]['details']
            for balance in details:
                if balance.get('ccy') == quote_currency:
                    return float(balance.get('availBal', 0.0))

        print(f"Error getting balance: {result}")
        return 0.0

    except Exception as e:
        print(f"Exception inside GetBal: {e}")
        return 0.0
if __name__ == "__main__":
    usdt_balance = get_available_balance("SOL-USDT")
    print(f"Доступно для торговли: {usdt_balance} USDT")
