# Massive API Reference (formerly Polygon.io)

Polygon.io rebranded to **Massive** on October 30, 2025. Both domains work — this project uses `api.massive.com` as the primary base URL.

## Authentication

Two methods supported:

```
# Query parameter
GET https://api.massive.com/v2/...?apiKey=YOUR_KEY

# Authorization header (preferred)
Authorization: Bearer YOUR_API_KEY
```

## Rate Limits

| Tier | Limit | Notes |
|------|-------|-------|
| Free | 5 requests/minute | End-of-day and delayed data only |
| Paid (all tiers) | Unlimited | Stay under ~100 req/sec to avoid throttling |

**For this project:** Free tier → poll every 15 seconds. Paid tier → poll every 2–5 seconds.

---

## Endpoints We Use

### 1. Snapshot — Multiple Tickers (Primary Endpoint)

**This is the main endpoint for our live price polling.** One call returns the latest price data for all watchlist tickers.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `tickers` | string | No | Comma-separated ticker symbols (omit = all tickers) |
| `include_otc` | boolean | No | Include OTC securities (default: false) |

**Response:**

```json
{
  "count": 3,
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "day": {
        "o": 189.33,
        "h": 191.56,
        "l": 188.90,
        "c": 191.24,
        "v": 54032150,
        "vw": 190.45
      },
      "min": {
        "t": 1702483200000,
        "o": 191.20,
        "h": 191.30,
        "l": 191.10,
        "c": 191.24,
        "v": 120345,
        "n": 892,
        "av": 54032150
      },
      "prevDay": {
        "o": 188.50,
        "h": 189.99,
        "l": 187.80,
        "c": 189.33,
        "v": 42000000,
        "vw": 189.10
      },
      "lastTrade": {
        "p": 191.24,
        "s": 100,
        "t": 1702483260000,
        "x": 11
      },
      "lastQuote": {
        "p": 191.23,
        "s": 200,
        "P": 191.25,
        "S": 300,
        "t": 1702483260000
      },
      "todaysChange": 1.91,
      "todaysChangePerc": 1.009,
      "updated": 1702483260000000000
    }
  ]
}
```

**Key fields we extract:**

| Field | Path | Use |
|-------|------|-----|
| Current price | `lastTrade.p` | The most recent trade price — our "current price" |
| Previous price | `prevDay.c` | Previous day close — for daily change calculation |
| Today's change | `todaysChange` | Absolute price change since previous close |
| Today's change % | `todaysChangePerc` | Percentage change since previous close |
| Last updated | `updated` | Nanosecond timestamp of last update |
| Day high | `day.h` | Current session high |
| Day low | `day.l` | Current session low |
| Volume | `day.v` | Current session volume |

### 2. Previous Close

End-of-day OHLCV for the prior trading day. Useful for seeding prices or getting a baseline.

```
GET /v2/aggs/ticker/{ticker}/prev
```

**Response:**

```json
{
  "ticker": "AAPL",
  "adjusted": true,
  "queryCount": 1,
  "resultsCount": 1,
  "status": "OK",
  "results": [
    {
      "T": "AAPL",
      "c": 191.24,
      "h": 191.56,
      "l": 188.90,
      "o": 189.33,
      "v": 54032150,
      "vw": 190.45,
      "n": 432156,
      "t": 1702425600000
    }
  ]
}
```

**Fields:** `T`=ticker, `o`=open, `h`=high, `l`=low, `c`=close, `v`=volume, `vw`=VWAP, `n`=transactions, `t`=timestamp (ms).

### 3. Aggregates / Bars (Historical OHLCV)

For chart data or historical context (not used for live pricing).

```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `ticker` | string | Case-sensitive ticker symbol |
| `multiplier` | int | Timespan multiplier (e.g., `5` for 5-minute bars) |
| `timespan` | string | `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year` |
| `from` | string | Start date `YYYY-MM-DD` or millisecond timestamp |
| `to` | string | End date `YYYY-MM-DD` or millisecond timestamp |

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `adjusted` | boolean | true | Adjust for splits |
| `sort` | string | asc | `asc` or `desc` |
| `limit` | int | 5000 | Max 50,000 |

**Response:**

```json
{
  "ticker": "AAPL",
  "adjusted": true,
  "queryCount": 100,
  "resultsCount": 100,
  "status": "OK",
  "results": [
    {
      "o": 189.33,
      "h": 189.50,
      "l": 189.20,
      "c": 189.45,
      "v": 12345,
      "vw": 189.38,
      "n": 89,
      "t": 1702468800000
    }
  ],
  "next_url": "https://api.massive.com/v2/aggs/ticker/AAPL/range/1/minute/..."
}
```

### 4. Grouped Daily Bars (All Tickers, One Date)

Returns end-of-day data for every traded stock on a given date. Useful for bulk seeding.

```
GET /v2/aggs/grouped/locale/us/market/stocks/{date}
```

**Response:** Same structure as aggregates, but each result includes a `T` (ticker) field. Returns ~9000+ results (all traded stocks for the date).

---

## Python Code Examples

### Setup

```python
import httpx

BASE_URL = "https://api.massive.com"

def make_client(api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10.0,
    )
```

### Fetch Latest Prices for Watchlist (Primary Use Case)

```python
async def fetch_snapshot(
    client: httpx.AsyncClient,
    tickers: list[str],
) -> dict[str, dict]:
    """Fetch latest prices for multiple tickers in a single API call.

    Returns dict mapping ticker -> price data.
    """
    resp = await client.get(
        "/v2/snapshot/locale/us/markets/stocks/tickers",
        params={"tickers": ",".join(tickers)},
    )
    resp.raise_for_status()
    data = resp.json()

    result = {}
    for t in data.get("tickers", []):
        last_trade = t.get("lastTrade", {})
        result[t["ticker"]] = {
            "price": last_trade.get("p", 0.0),
            "previous_close": t.get("prevDay", {}).get("c", 0.0),
            "change": t.get("todaysChange", 0.0),
            "change_percent": t.get("todaysChangePerc", 0.0),
            "day_high": t.get("day", {}).get("h", 0.0),
            "day_low": t.get("day", {}).get("l", 0.0),
            "volume": t.get("day", {}).get("v", 0),
            "timestamp": t.get("updated", 0),
        }
    return result
```

### Fetch Previous Close

```python
async def fetch_previous_close(
    client: httpx.AsyncClient,
    ticker: str,
) -> float | None:
    """Fetch previous day's closing price for a single ticker."""
    resp = await client.get(f"/v2/aggs/ticker/{ticker}/prev")
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if results:
        return results[0]["c"]
    return None
```

### Fetch Historical Bars

```python
async def fetch_bars(
    client: httpx.AsyncClient,
    ticker: str,
    timespan: str = "day",
    multiplier: int = 1,
    from_date: str = "2024-01-01",
    to_date: str = "2024-12-31",
) -> list[dict]:
    """Fetch OHLCV bars for a ticker over a date range."""
    resp = await client.get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
        params={"adjusted": "true", "sort": "asc", "limit": 50000},
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])
```

### Complete Polling Loop Example

```python
import asyncio

async def poll_prices(
    api_key: str,
    tickers: list[str],
    interval: float = 15.0,  # 15s for free tier
):
    """Poll the snapshot endpoint on a regular interval."""
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10.0,
    ) as client:
        while True:
            try:
                prices = await fetch_snapshot(client, tickers)
                for ticker, data in prices.items():
                    print(f"{ticker}: ${data['price']:.2f} ({data['change_percent']:+.2f}%)")
            except httpx.HTTPStatusError as e:
                print(f"API error: {e.response.status_code}")
            except httpx.RequestError as e:
                print(f"Request error: {e}")

            await asyncio.sleep(interval)
```

---

## Error Handling

The API returns standard HTTP status codes:

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 401 | Invalid API key | Check `MASSIVE_API_KEY` |
| 403 | Forbidden (plan doesn't include endpoint) | Snapshots require paid plan on free tier; fall back to previous-close |
| 429 | Rate limited | Back off; respect `Retry-After` header if present |
| 500+ | Server error | Retry with exponential backoff |

**Important:** The snapshot endpoint (`/v2/snapshot/...`) requires a **paid plan** for real-time data. Free tier users get delayed data or may receive 403 errors on this endpoint. For free tier, the previous-close endpoint (`/v2/aggs/ticker/{ticker}/prev`) is the reliable fallback for getting the latest available price.

---

## Official Python Client

An official client library exists (`pip install massive`, formerly `polygon-api-client`), but we use **direct `httpx` calls** instead because:

1. Better integration with FastAPI's async architecture
2. No extra dependency to manage
3. Full control over request timing and retry logic
4. We only need 1–2 endpoints
