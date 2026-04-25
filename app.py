# ═══════════════════════════════════════════════════════════════════
#                  BAYA EMPIRE - واجهة Streamlit
#                      Trading Dashboard UI
# ═══════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
from datetime import date
from baya_database import BayaDatabase

st.set_page_config(page_title="Baya Empire", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #1a1a2e, #16213e);
        border-radius: 10px;
        color: white;
    }
    .metric-card {
        background: #16213e;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<div class="main-header">🛡️ Baya Empire - AI Trading Guardian</div>', unsafe_allow_html=True)

    page = st.sidebar.radio("القائمة", ["📊 لوحة التحكم", "📈 التحليلات", "💼 المحفظة", "⚙️ الإعدادات"])

    if page == "📊 لوحة التحكم":
        dashboard()
    elif page == "📈 التحليلات":
        analytics()
    elif page == "💼 المحفظة":
        portfolio()
    elif page == "⚙️ الإعدادات":
        settings()

def dashboard():
    st.markdown("## 📊 لوحة التحكم")

    db = BayaDatabase.get_instance()
    stats = db.get_performance_stats()
    open_trades = db.get_open_trades()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("نسبة الفوز", f"{stats['win_rate']}%")
    with col2:
        st.metric("إجمالي الربح", f"${stats['total_profit']}")
    with col3:
        st.metric("عدد الصفقات", stats['trade_count'])
    with col4:
        st.metric("الصفقات المفتوحة", len(open_trades))

    st.markdown("### 📋 الصفقات المفتوحة")
    if not open_trades.empty:
        st.dataframe(open_trades, use_container_width=True)
    else:
        st.info("لا توجد صفقات مفتوحة")

    st.markdown("### 🔒 إغلاق صفقة")
    if not open_trades.empty:
        trade_list = [f"#{row['id']} - {row['symbol']}" for _, row in open_trades.iterrows()]
        selected = st.selectbox("اختر الصفقة", trade_list)
        trade_id = int(selected.split("#")[1].split(" - ")[0])

        col1, col2 = st.columns(2)
        with col1:
            exit_price = st.number_input("سعر الخروج", min_value=0.0, step=100.0)
        with col2:
            profit = st.number_input("الربح/الخسارة", step=1.0)

        if st.button("🔒 إغلاق الصفقة"):
            db.close_trade(trade_id, exit_price, profit)
            st.success("✅ تم إغلاق الصفقة!")
            st.rerun()

def analytics():
    st.markdown("## 📈 التحليلات المتقدمة")

    db = BayaDatabase.get_instance()
    stats = db.get_performance_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sharpe Ratio", stats['sharpe_ratio'])
    with col2:
        st.metric("Max Drawdown", f"${stats['max_drawdown']}")
    with col3:
        st.metric("Profit Factor", stats['profit_factor'])
    with col4:
        st.metric("الفائزين", stats['winners'])

    st.markdown("### 📊 الأرباح اليومية")
    daily_pnl = db.get_daily_pnl()
    if not daily_pnl.empty:
        st.bar_chart(daily_pnl.set_index('date'))

    st.markdown("### 📋 سجل الصفقات")
    history = db.get_trade_history()
    st.dataframe(history, use_container_width=True)

def portfolio():
    st.markdown("## 💼 إدارة المحفظة")

    st.markdown("### 📝 تسجيل صفقة جديدة")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("الرمز", value="BTCUSDT")
        side = st.selectbox("الاتجاه", ["LONG", "SHORT"])
    with col2:
        price = st.number_input("سعر الدخول", min_value=0.0, step=100.0)
        amount = st.number_input("الكمية", min_value=0.0, step=0.001)

    strategy = st.selectbox("الاستراتيجية", ["Breakout", "Mean Reversion", "Trend", "Manual"])
    notes = st.text_area("ملاحظات")

    if st.button("📝 تسجيل الصفقة"):
        db = BayaDatabase.get_instance()
        trade_id = db.log_trade(symbol, side, price, amount, strategy, notes)
        st.success(f"✅ تم تسجيل الصفقة #{trade_id}")

def settings():
    st.markdown("## ⚙️ الإعدادات")

    st.markdown("### 🔧 إعدادات API")
    api_key = st.text_input("Binance API Key", type="password")
    api_secret = st.text_input("Binance API Secret", type="password")

    st.markdown("### 🔔 إعدادات الإشعارات")
    telegram_token = st.text_input("Telegram Bot Token", type="password")
    telegram_chat = st.text_input("Telegram Chat ID")
    discord_webhook = st.text_input("Discord Webhook URL")

    if st.button("💾 حفظ الإعدادات"):
        st.success("✅ تم الحفظ!")

    st.markdown("### 💾 النسخ الاحتياطية")
    if st.button("📦 إنشاء نسخة احتياطية"):
        db = BayaDatabase.get_instance()
        backup_path = db.create_backup()
        st.success(f"💾 تم إنشاء النسخة: {backup_path}")

if __name__ == "__main__":
    main()
