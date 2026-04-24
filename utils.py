import streamlit as st


def fmt_money(value):
    return f"${value:,.2f}"


def fmt_pct(value):
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def badge_html(text, kind="neutral"):
    styles = {
        "success": "background:rgba(14,203,129,.12);border:1px solid rgba(14,203,129,.35);color:#0ecb81;",
        "danger": "background:rgba(246,70,93,.12);border:1px solid rgba(246,70,93,.35);color:#f6465d;",
        "neutral": "background:rgba(240,185,11,.12);border:1px solid rgba(240,185,11,.35);color:#f0b90b;",
    }
    style = styles.get(kind, styles["neutral"])
    return f"""
    <div style="{style}padding:12px 16px;border-radius:14px;font-weight:700;margin-bottom:10px;">
        {text}
    </div>
    """


def inject_global_css():
    st.markdown(
        """
<style>
    .stApp {
        background: linear-gradient(180deg, #0b0e11 0%, #12171f 100%);
        color: #eaecef;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
        max-width: 1600px;
    }

    h1, h2, h3, h4 {
        color: #f0b90b !important;
        letter-spacing: 0.2px;
    }

    div[data-testid="stSidebar"] {
        background: #0f131a;
        border-right: 1px solid rgba(240,185,11,0.10);
    }

    div[data-testid="stMetric"] {
        background: #161b22;
        border: 1px solid rgba(240,185,11,0.18);
        border-radius: 18px;
        padding: 14px;
        box-shadow: 0 0 18px rgba(240,185,11,0.07);
    }

    .glass-card {
        background: #161b22;
        border: 1px solid rgba(240,185,11,0.16);
        border-radius: 18px;
        padding: 18px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,.22);
    }

    .hero-card {
        background: linear-gradient(135deg, rgba(240,185,11,0.10), rgba(255,255,255,0.02));
        border: 1px solid rgba(240,185,11,0.20);
        border-radius: 22px;
        padding: 22px;
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom: 16px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #161b22;
        border-radius: 12px;
        border: 1px solid rgba(240,185,11,0.12);
        padding: 10px 14px;
    }

    .stButton > button {
        border-radius: 12px !important;
        border: 1px solid rgba(240,185,11,0.25) !important;
        background: #1a2028 !important;
        color: #eaecef !important;
        font-weight: 700 !important;
    }

    .stButton > button:hover {
        border-color: #f0b90b !important;
        color: #f0b90b !important;
    }
</style>
""",
        unsafe_allow_html=True,
    )
