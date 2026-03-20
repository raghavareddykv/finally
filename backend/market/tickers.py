"""Supported ticker universe with seed prices.

This is the single source of truth for:
- Valid ticker symbols (API validation, watchlist, trade requests)
- Seed prices (simulator starting values)
- Ticker universe for the Massive poller
"""

SUPPORTED_TICKERS: dict[str, float] = {
    # Tech
    "AAPL": 190.0,
    "GOOGL": 175.0,
    "MSFT": 420.0,
    "AMZN": 185.0,
    "TSLA": 250.0,
    "NVDA": 880.0,
    "META": 500.0,
    "NFLX": 620.0,
    "AMD": 160.0,
    "INTC": 45.0,
    "CRM": 280.0,
    "ORCL": 125.0,
    "ADBE": 560.0,
    "CSCO": 50.0,
    "QCOM": 170.0,
    "AVGO": 1350.0,
    "UBER": 75.0,
    "SQ": 80.0,
    "SHOP": 75.0,
    "PYPL": 65.0,
    # Finance
    "JPM": 195.0,
    "V": 280.0,
    "MA": 460.0,
    "BAC": 35.0,
    "GS": 410.0,
    "MS": 95.0,
    "BLK": 810.0,
    "AXP": 220.0,
    # Healthcare
    "JNJ": 155.0,
    "PFE": 28.0,
    "UNH": 520.0,
    "MRK": 125.0,
    "ABBV": 170.0,
    "LLY": 750.0,
    # Consumer
    "KO": 60.0,
    "PEP": 170.0,
    "WMT": 165.0,
    "COST": 720.0,
    "MCD": 290.0,
    "NKE": 105.0,
    "SBUX": 95.0,
    "DIS": 115.0,
    # Industrial / Energy / Other
    "BA": 190.0,
    "CAT": 330.0,
    "XOM": 105.0,
    "CVX": 155.0,
    "GE": 160.0,
    "UPS": 145.0,
    "HD": 370.0,
    "LMT": 450.0,
}
