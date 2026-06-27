# Your Bybit API Keys
BYBIT_API_KEY = "your_bybit_api_key_here"
BYBIT_SECRET_KEY = "your_bybit_secret_key_here"

# Set to True to use Testnet (paper trading), False for Mainnet (real money)
BYBIT_IS_DEMO = True

# If you need to specify a subaccount (optional, Bybit usually handles this automatically via the API key)
BYBIT_SUBACCOUNT = ""

# --- Risk / Sizing configuration ---
# Leverage applied to every position. Set explicitly so notional is predictable and
# orders are not silently rejected by the exchange's default leverage.
LEVERAGE = 2

# Fraction of *free* margin committed as margin per trade (0.0 - 1.0).
# Notional = free_margin * RISK_FRACTION * LEVERAGE.
RISK_FRACTION = 0.5

# Fee/slippage safety buffer: never deploy more than this fraction of free margin as margin.
MAX_MARGIN_FRACTION = 0.90

# Fallback minimum notional (USDT) used only when the exchange's per-symbol
# minNotionalValue cannot be fetched.
MIN_NOTIONAL_USDT = 5.0

# Network timeouts (connect, read) in seconds for Bybit HTTP calls.
HTTP_TIMEOUT = (5, 15)
