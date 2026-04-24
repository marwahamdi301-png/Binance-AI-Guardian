import pandas as pd


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()

    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
    rs = avg_gain / avg_loss
    out["rsi"] = 100 - (100 / (1 + rs))

    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    tr1 = out["high"] - out["low"]
    tr2 = (out["high"] - out["close"].shift()).abs()
    tr3 = (out["low"] - out["close"].shift()).abs()
    out["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr"] = out["tr"].rolling(14).mean()

    return out


def generate_signal(df: pd.DataFrame, change_pct_24h: float):
    last = df.iloc[-1]

    score = 0
    reasons = []

    if last["ema20"] > last["ema50"]:
        score += 1
        reasons.append("EMA20 > EMA50")

    if last["macd"] > last["macd_signal"]:
        score += 1
        reasons.append("MACD bullish")

    if pd.notna(last["rsi"]) and 45 <= last["rsi"] <= 68:
        score += 1
        reasons.append("RSI healthy")

    if change_pct_24h > 1.0:
        score += 1
        reasons.append("24h momentum positive")

    if pd.notna(last["atr"]) and last["atr"] / last["close"] < 0.04:
        score += 1
        reasons.append("Volatility acceptable")

    if score >= 5:
        signal = "Strong Buy"
        confidence = "Very High"
        bias = "Bullish"
    elif score == 4:
        signal = "Buy"
        confidence = "High"
        bias = "Bullish"
    elif score == 3:
        signal = "Hold"
        confidence = "Moderate"
        bias = "Neutral-Bullish"
    elif pd.notna(last["rsi"]) and last["rsi"] > 75:
        signal = "Take Profit"
        confidence = "High"
        bias = "Overheated"
    else:
        signal = "Watch"
        confidence = "Low"
        bias = "Neutral"

    return {
        "signal": signal,
        "confidence": confidence,
        "market_bias": bias,
        "score": score,
        "reasons": reasons,
    }


def recommended_position_size(
    portfolio_value: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    entry_price: float,
    max_portfolio_allocation: float = 0.25,
):
    risk_amount = portfolio_value * risk_per_trade
    stop_distance = entry_price * stop_loss_pct if entry_price > 0 else 0

    quantity = risk_amount / stop_distance if stop_distance > 0 else 0.0
    notional = quantity * entry_price

    max_notional = portfolio_value * max_portfolio_allocation
    if notional > max_notional and entry_price > 0:
        notional = max_notional
        quantity = notional / entry_price

    return {
        "risk_amount": round(risk_amount, 2),
        "quantity": quantity,
        "notional": round(notional, 2),
    }


def build_radar_table(client, symbols, interval="1h", limit=180):
    rows = []

    for sym in symbols:
        df = client.get_klines_df(sym, interval=interval, limit=limit)
        ticker = client.get_ticker_24h(sym)

        if df.empty or not ticker:
            continue

        df = compute_indicators(df)
        sig = generate_signal(df, float(ticker.get("priceChangePercent", 0.0)))
        last = df.iloc[-1]

        rows.append(
            {
                "Pair": sym.replace("USDT", "/USDT"),
                "Price": round(float(last["close"]), 6),
                "RSI": round(float(last["rsi"]), 2) if pd.notna(last["rsi"]) else None,
                "ATR": round(float(last["atr"]), 6) if pd.notna(last["atr"]) else None,
                "24h Change %": round(float(ticker.get("priceChangePercent", 0.0)), 2),
                "AI Signal": sig["signal"],
                "Confidence": sig["confidence"],
                "Bias": sig["market_bias"],
            }
        )

    if not rows:
        return pd.DataFrame()

    radar_df = pd.DataFrame(rows)

    priority = {
        "Strong Buy": 1,
        "Buy": 2,
        "Hold": 3,
        "Watch": 4,
        "Take Profit": 5,
    }

    radar_df["priority"] = radar_df["AI Signal"].map(priority).fillna(99)
    radar_df = radar_df.sort_values(["priority", "24h Change %"], ascending=[True, False])
    radar_df = radar_df.drop(columns=["priority"]).reset_index(drop=True)

    return radar_df
