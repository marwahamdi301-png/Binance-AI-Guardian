import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ai_engine import (
    build_radar_table,
    compute_indicators,
    generate_signal,
    recommended_position_size,
)
from binance_api import BinanceClient, account_balances_df, estimate_wallet_value_usdt
from utils import badge_html, fmt_money, fmt_pct, inject_global_css


st.set_page_config(
    page_title="Binance AI Guardian X",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()

# =========================
# SESSION STATE
# =========================
DEFAULTS = {
    "bot_running": True,
    "paper_mode": True,
    "trade_log": [],
    "demo_wallet": 15000.0,
    "selected_symbol": "BTCUSDT",
    "selected_interval": "1h",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================
# HELPERS
# =========================
def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


def log_trade(action, symbol, mode, details):
    st.session_state.trade_log.insert(
        0,
        {
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": action,
            "Symbol": symbol,
            "Mode": mode,
            "Details": details,
        },
    )


def build_candles_chart(df: pd.DataFrame, symbol: str):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
    )

    fig.add_trace(
        go.Candlestick(
            x=df["open_time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol,
        ),
        row=1,
        col=1,
    )

    colors = ["#0ecb81" if c >= o else "#f6465d" for o, c in zip(df["open"], df["close"])]

    fig.add_trace(
        go.Bar(
            x=df["open_time"],
            y=df["volume"],
            marker_color=colors,
            name="Volume",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        height=650,
        margin=dict(l=10, r=10, t=25, b=10),
        paper_bgcolor="#12171f",
        plot_bgcolor="#12171f",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0.01),
    )

    return fig


# =========================
# SECRETS / CLIENTS
# =========================
api_key = get_secret("BINANCE_API_KEY", "")
api_secret = get_secret("BINANCE_API_SECRET", "")
default_testnet = bool(get_secret("BINANCE_TESTNET", False))

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚙️ Control Center")

paper_mode = st.sidebar.toggle("Paper Trading", value=st.session_state.paper_mode)
st.session_state.paper_mode = paper_mode

testnet = st.sidebar.toggle("Use Testnet", value=default_testnet)

symbol = st.sidebar.selectbox(
    "Trading Pair",
    ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"],
    index=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"].index(
        st.session_state.selected_symbol
    ),
)

interval = st.sidebar.selectbox(
    "Timeframe",
    ["15m", "1h", "4h", "1d"],
    index=["15m", "1h", "4h", "1d"].index(st.session_state.selected_interval),
)

scan_count = st.sidebar.slider("Radar Scan Depth", 5, 30, 12)
risk_pct = st.sidebar.slider("Risk per Trade %", 0.5, 5.0, 1.0, 0.5)
stop_loss_pct = st.sidebar.slider("Stop Loss %", 1.0, 15.0, 4.0, 0.5)
take_profit_pct = st.sidebar.slider("Take Profit %", 2.0, 30.0, 10.0, 0.5)
auto_refresh = st.sidebar.checkbox("Auto Refresh 30s", value=False)

st.session_state.selected_symbol = symbol
st.session_state.selected_interval = interval

st.sidebar.markdown("---")

if st.session_state.bot_running:
    st.sidebar.markdown(
        badge_html("✅ Bot actif", "success"),
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        badge_html("🛑 Bot stoppé", "danger"),
        unsafe_allow_html=True,
    )

col_sb1, col_sb2 = st.sidebar.columns(2)

with col_sb1:
    if st.button("🚨 Kill Switch", use_container_width=True):
        st.session_state.bot_running = False
        log_trade("KILL_SWITCH", symbol, "SYSTEM", "Bot arrêté manuellement")

with col_sb2:
    if st.button("▶ Restart", use_container_width=True):
        st.session_state.bot_running = True
        log_trade("RESTART", symbol, "SYSTEM", "Bot redémarré")

st.sidebar.markdown("---")

if not paper_mode and (not api_key or not api_secret):
    st.sidebar.error("Clés API manquantes. Passage conseillé en Paper Trading.")

mode_label = "PAPER" if paper_mode else "LIVE"
st.sidebar.caption(f"Mode: {mode_label}")
st.sidebar.caption("Binance AI Guardian X")


# =========================
# CLIENT INIT
# =========================
public_client = BinanceClient(testnet=testnet)
private_client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)

# =========================
# HEADER
# =========================
st.title("🛡️ Binance AI Guardian X")
st.markdown(
    f"""
<div class="hero-card">
    <div>
        <h3 style="margin-bottom:8px;">Trading Command Center</h3>
        <p style="margin:0;color:#9aa4af;">
            Dashboard intelligent Binance Spot avec radar, exécution, portefeuille et moteur de signaux.
        </p>
    </div>
    <div style="text-align:right;">
        <div style="font-size:0.9rem;color:#9aa4af;">Dernière mise à jour</div>
        <div style="font-weight:700;color:#f0b90b;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# =========================
# FETCH MARKET DATA
# =========================
ticker = public_client.get_ticker_24h(symbol)
klines = public_client.get_klines_df(symbol, interval=interval, limit=220)

if klines.empty or not ticker:
    st.error("Impossible de charger les données Binance pour le moment.")
    st.stop()

ind_df = compute_indicators(klines)
signal_data = generate_signal(ind_df, float(ticker.get("priceChangePercent", 0.0)))

last_close = float(ind_df["close"].iloc[-1])
rsi = float(ind_df["rsi"].iloc[-1]) if pd.notna(ind_df["rsi"].iloc[-1]) else None
macd = float(ind_df["macd"].iloc[-1]) if pd.notna(ind_df["macd"].iloc[-1]) else None
macd_signal = float(ind_df["macd_signal"].iloc[-1]) if pd.notna(ind_df["macd_signal"].iloc[-1]) else None
atr = float(ind_df["atr"].iloc[-1]) if pd.notna(ind_df["atr"].iloc[-1]) else None
change_pct = float(ticker.get("priceChangePercent", 0.0))
quote_volume = float(ticker.get("quoteVolume", 0.0))
high_24h = float(ticker.get("highPrice", 0.0))
low_24h = float(ticker.get("lowPrice", 0.0))

# =========================
# ACCOUNT / PORTFOLIO
# =========================
balances_df = pd.DataFrame()
wallet_value = st.session_state.demo_wallet
account_connected = False

if api_key and api_secret:
    account_info = private_client.get_account_info()
    if account_info and "balances" in account_info:
        balances_df = account_balances_df(account_info)
        price_map = public_client.get_price_map()
        wallet_value = estimate_wallet_value_usdt(balances_df, price_map)
        account_connected = True

# =========================
# TOP METRICS
# =========================
m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric("Wallet Value", fmt_money(wallet_value), fmt_pct(2.85))

with m2:
    st.metric("Selected Pair", symbol.replace("USDT", "/USDT"), fmt_pct(change_pct))

with m3:
    st.metric("AI Signal", signal_data["signal"], signal_data["confidence"])

with m4:
    st.metric("RSI(14)", f"{rsi:.2f}" if rsi is not None else "N/A", signal_data["market_bias"])

with m5:
    st.metric("ATR", f"{atr:.4f}" if atr is not None else "N/A", f"Vol ${quote_volume:,.0f}")

tabs = st.tabs(["📊 Dashboard", "🚀 Radar", "💼 Portfolio", "⚡ Execution", "🧾 Logs"])

# =========================
# TAB 1 DASHBOARD
# =========================
with tabs[0]:
    left, right = st.columns([2.2, 1])

    with left:
        st.subheader(f"Prix en direct — {symbol.replace('USDT', '/USDT')}")
        st.plotly_chart(build_candles_chart(ind_df, symbol), use_container_width=True)

    with right:
        st.subheader("AI Decision Engine")

        st.markdown(
            f"""
<div class="glass-card">
    <h4>Market Snapshot</h4>
    <p><strong>Prix actuel:</strong> {fmt_money(last_close)}</p>
    <p><strong>24h High:</strong> {fmt_money(high_24h)}</p>
    <p><strong>24h Low:</strong> {fmt_money(low_24h)}</p>
    <p><strong>Variation 24h:</strong> {fmt_pct(change_pct)}</p>
    <p><strong>Quote Volume:</strong> ${quote_volume:,.0f}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
<div class="glass-card">
    <h4>Technical State</h4>
    <p><strong>Signal:</strong> {signal_data["signal"]}</p>
    <p><strong>Confiance:</strong> {signal_data["confidence"]}</p>
    <p><strong>Bias:</strong> {signal_data["market_bias"]}</p>
    <p><strong>RSI:</strong> {rsi:.2f if rsi is not None else 0}</p>
    <p><strong>MACD:</strong> {macd:.4f if macd is not None else 0}</p>
    <p><strong>MACD Signal:</strong> {macd_signal:.4f if macd_signal is not None else 0}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        status_box = (
            badge_html("Trading autorisé", "success")
            if st.session_state.bot_running
            else badge_html("Trading désactivé", "danger")
        )
        st.markdown(status_box, unsafe_allow_html=True)

# =========================
# TAB 2 RADAR
# =========================
with tabs[1]:
    st.subheader("Investment Opportunity Radar")

    market_df = public_client.get_market_overview()
    if market_df.empty:
        st.warning("Aucune donnée marché disponible.")
    else:
        candidates = market_df.head(40)["symbol"].tolist()
        radar_symbols = candidates[:scan_count]

        with st.spinner("Scan intelligent des paires en cours..."):
            radar_df = build_radar_table(public_client, radar_symbols, interval="1h", limit=180)

        if radar_df.empty:
            st.info("Aucune opportunité intéressante détectée.")
        else:
            st.dataframe(radar_df, use_container_width=True, hide_index=True)

            best = radar_df.iloc[0]
            st.markdown(
                f"""
<div class="glass-card">
    <h4>Top Pick du moment</h4>
    <p><strong>Pair:</strong> {best['Pair']}</p>
    <p><strong>Signal:</strong> {best['AI Signal']}</p>
    <p><strong>Confiance:</strong> {best['Confidence']}</p>
    <p><strong>RSI:</strong> {best['RSI']}</p>
    <p><strong>24h %:</strong> {best['24h Change %']}</p>
</div>
""",
                unsafe_allow_html=True,
            )

# =========================
# TAB 3 PORTFOLIO
# =========================
with tabs[2]:
    st.subheader("Portfolio & Account State")

    p1, p2 = st.columns([1.2, 1])

    with p1:
        st.markdown(
            f"""
<div class="glass-card">
    <h4>Connexion Binance</h4>
    <p><strong>État:</strong> {"Connecté" if account_connected else "Démo / non connecté"}</p>
    <p><strong>Mode:</strong> {mode_label}</p>
    <p><strong>Wallet estimé:</strong> {fmt_money(wallet_value)}</p>
    <p><strong>Bot:</strong> {"Actif" if st.session_state.bot_running else "Stoppé"}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        if not account_connected:
            st.info(
                "Aucune clé API détectée. Le dashboard fonctionne en mode démonstration pour le portefeuille."
            )

    with p2:
        if account_connected and not balances_df.empty:
            st.markdown(
                f"""
<div class="glass-card">
    <h4>Résumé portefeuille</h4>
    <p><strong>Actifs détenus:</strong> {len(balances_df)}</p>
    <p><strong>Exposition estimée:</strong> {fmt_money(wallet_value)}</p>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div class="glass-card">
    <h4>Mode démo</h4>
    <p>Le wallet affiché est simulé tant que les clés API Spot Binance ne sont pas configurées.</p>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("### Balances")
    if account_connected and not balances_df.empty:
        st.dataframe(balances_df, use_container_width=True, hide_index=True)
    else:
        demo_balances = pd.DataFrame(
            [
                {"asset": "USDT", "free": 8500.00, "locked": 0.00, "total": 8500.00},
                {"asset": "BTC", "free": 0.0820, "locked": 0.0000, "total": 0.0820},
                {"asset": "ETH", "free": 1.5400, "locked": 0.0000, "total": 1.5400},
            ]
        )
        st.dataframe(demo_balances, use_container_width=True, hide_index=True)

# =========================
# TAB 4 EXECUTION
# =========================
with tabs[3]:
    st.subheader("Execution Console")

    ex1, ex2 = st.columns([1.2, 1])

    with ex1:
        spend_usdt = st.number_input("Capital à engager (USDT)", min_value=10.0, value=250.0, step=10.0)
        base_qty = spend_usdt / last_close if last_close > 0 else 0.0

        sizing = recommended_position_size(
            portfolio_value=wallet_value,
            risk_per_trade=risk_pct / 100.0,
            stop_loss_pct=stop_loss_pct / 100.0,
            entry_price=last_close,
            max_portfolio_allocation=0.25,
        )

        st.markdown(
            f"""
<div class="glass-card">
    <h4>Risk Engine</h4>
    <p><strong>Position théorique:</strong> {sizing['quantity']:.6f} {symbol.replace('USDT', '')}</p>
    <p><strong>Notional théorique:</strong> {fmt_money(sizing['notional'])}</p>
    <p><strong>Risque max/trade:</strong> {fmt_money(sizing['risk_amount'])}</p>
    <p><strong>Stop Loss:</strong> {stop_loss_pct:.2f}%</p>
    <p><strong>Take Profit:</strong> {take_profit_pct:.2f}%</p>
</div>
""",
            unsafe_allow_html=True,
        )

        st.caption(f"Montant simulé au prix actuel: ~ {base_qty:.6f} {symbol.replace('USDT','')}")

    with ex2:
        st.markdown(
            f"""
<div class="glass-card">
    <h4>Order Guard</h4>
    <p><strong>Mode:</strong> {mode_label}</p>
    <p><strong>Pair:</strong> {symbol}</p>
    <p><strong>Signal actuel:</strong> {signal_data['signal']}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        live_ack = st.checkbox("Je confirme comprendre les risques du mode LIVE")

        cta1, cta2 = st.columns(2)

        with cta1:
            if st.button("🟢 BUY", use_container_width=True):
                if not st.session_state.bot_running:
                    st.error("Le bot est arrêté. Redémarre-le avant exécution.")
                elif paper_mode or not api_key or not api_secret:
                    log_trade(
                        "BUY",
                        symbol,
                        "PAPER",
                        f"Achat simulé — {spend_usdt:.2f} USDT (~{base_qty:.6f})",
                    )
                    st.success("Ordre BUY simulé ajouté au journal.")
                else:
                    if not live_ack:
                        st.error("Confirmation LIVE requise.")
                    else:
                        result = private_client.place_market_order(
                            symbol=symbol,
                            side="BUY",
                            quote_qty=spend_usdt,
                            live=True,
                        )
                        if result and "orderId" in result:
                            log_trade("BUY", symbol, "LIVE", f"OrderID {result['orderId']}")
                            st.success(f"Ordre LIVE BUY exécuté. ID: {result['orderId']}")
                        else:
                            st.error("Échec de l'ordre BUY LIVE.")

        with cta2:
            if st.button("🔴 SELL", use_container_width=True):
                if not st.session_state.bot_running:
                    st.error("Le bot est arrêté. Redémarre-le avant exécution.")
                elif paper_mode or not api_key or not api_secret:
                    log_trade(
                        "SELL",
                        symbol,
                        "PAPER",
                        f"Vente simulée — {base_qty:.6f} {symbol.replace('USDT','')}",
                    )
                    st.success("Ordre SELL simulé ajouté au journal.")
                else:
                    if not live_ack:
                        st.error("Confirmation LIVE requise.")
                    else:
                        result = private_client.place_market_order(
                            symbol=symbol,
                            side="SELL",
                            quantity=round(base_qty, 6),
                            live=True,
                        )
                        if result and "orderId" in result:
                            log_trade("SELL", symbol, "LIVE", f"OrderID {result['orderId']}")
                            st.success(f"Ordre LIVE SELL exécuté. ID: {result['orderId']}")
                        else:
                            st.error("Échec de l'ordre SELL LIVE.")

# =========================
# TAB 5 LOGS
# =========================
with tabs[4]:
    st.subheader("Trade / Bot Logs")

    if st.session_state.trade_log:
        logs_df = pd.DataFrame(st.session_state.trade_log)
        st.dataframe(logs_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun log pour le moment.")

st.markdown("---")
st.caption(
    "Version X — architecture modulaire prête pour enrichissements: WebSocket, trailing stop, alertes Telegram, backtesting, stratégies multi-signaux."
)

if auto_refresh:
    time.sleep(30)
    st.rerun()
