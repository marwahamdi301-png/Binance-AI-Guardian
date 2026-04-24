import hashlib
import hmac
import time
from urllib.parse import urlencode

import pandas as pd
import requests


class BinanceClient:
    def __init__(self, api_key="", api_secret="", testnet=False, timeout=15):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.timeout = timeout
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"

    def _headers(self):
        headers = {}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    def _request(self, method, path, params=None, signed=False):
        params = params or {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            query_string = urlencode(params, doseq=True)
            signature = hmac.new(
                self.api_secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            params["signature"] = signature

        url = f"{self.base_url}{path}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, headers=self._headers(), timeout=self.timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, params=params, headers=self._headers(), timeout=self.timeout)
            else:
                raise ValueError("HTTP method non supportée")

            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    # =====================
    # PUBLIC ENDPOINTS
    # =====================
    def get_ticker_24h(self, symbol):
        return self._request("GET", "/api/v3/ticker/24hr", {"symbol": symbol})

    def get_all_24h(self):
        return self._request("GET", "/api/v3/ticker/24hr")

    def get_market_overview(self):
        data = self.get_all_24h()
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        cols = ["symbol", "lastPrice", "priceChangePercent", "quoteVolume", "volume"]
        df = df[cols].copy()

        for col in ["lastPrice", "priceChangePercent", "quoteVolume", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df[df["symbol"].str.endswith("USDT", na=False)].copy()
        df = df.sort_values("quoteVolume", ascending=False)
        return df.reset_index(drop=True)

    def get_price_map(self):
        data = self.get_all_24h()
        if not data:
            return {}
        return {item["symbol"]: float(item["lastPrice"]) for item in data if "symbol" in item and "lastPrice" in item}

    def get_klines_df(self, symbol, interval="1h", limit=200):
        data = self._request(
            "GET",
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
        )

        if not data:
            return pd.DataFrame()

        cols = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ]

        df = pd.DataFrame(data, columns=cols)
        for col in ["open", "high", "low", "close", "volume", "quote_asset_volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        return df

    # =====================
    # PRIVATE ENDPOINTS
    # =====================
    def get_account_info(self):
        if not self.api_key or not self.api_secret:
            return None
        return self._request("GET", "/api/v3/account", signed=True)

    def get_open_orders(self, symbol=None):
        if not self.api_key or not self.api_secret:
            return None
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/api/v3/openOrders", params=params, signed=True)

    def place_market_order(self, symbol, side, quantity=None, quote_qty=None, live=False):
        if not live:
            return {
                "paper": True,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "quoteOrderQty": quote_qty,
            }

        if not self.api_key or not self.api_secret:
            return None

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
        }

        if quote_qty is not None and side.upper() == "BUY":
            params["quoteOrderQty"] = quote_qty
        elif quantity is not None:
            params["quantity"] = quantity
        else:
            return None

        return self._request("POST", "/api/v3/order", params=params, signed=True)


def account_balances_df(account_info):
    if not account_info or "balances" not in account_info:
        return pd.DataFrame()

    rows = []
    for item in account_info["balances"]:
        free = float(item["free"])
        locked = float(item["locked"])
        total = free + locked
        if total > 0:
            rows.append(
                {
                    "asset": item["asset"],
                    "free": free,
                    "locked": locked,
                    "total": total,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    return df.sort_values("total", ascending=False).reset_index(drop=True)


def estimate_wallet_value_usdt(balances_df, price_map):
    if balances_df is None or balances_df.empty:
        return 0.0

    total_value = 0.0

    for _, row in balances_df.iterrows():
        asset = row["asset"]
        qty = float(row["total"])

        if asset == "USDT":
            total_value += qty
            continue

        pair_usdt = f"{asset}USDT"
        pair_btc = f"{asset}BTC"

        if pair_usdt in price_map:
            total_value += qty * price_map[pair_usdt]
        elif asset == "BTC" and "BTCUSDT" in price_map:
            total_value += qty * price_map["BTCUSDT"]
        elif pair_btc in price_map and "BTCUSDT" in price_map:
            total_value += qty * price_map[pair_btc] * price_map["BTCUSDT"]

    return round(total_value, 2)
