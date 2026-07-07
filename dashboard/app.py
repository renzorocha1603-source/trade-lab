"""
AI Intelligent Trader Dashboard v2.6 — Stocks + Crypto sections.
Password-protected. Multi-user. Self-learning AI showcase.
Designed for anyone to understand — no finance degree needed.
"""

import streamlit as st
import pandas as pd
import json
import os
import subprocess
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="AI Intelligent Trader", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .section-title { font-size: 21px; font-weight: 700; margin-top: 8px; margin-bottom: 2px; }
    .section-subtitle { font-size: 13px; color: #9aa0a6; margin-bottom: 14px; }
    .explanation { font-size: 13px; color: #888; font-style: italic; }
    .card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 12px; padding: 16px 18px; margin-bottom: 14px; }
    .highlight-card { background: rgba(124,77,255,0.08); border: 1px solid rgba(124,77,255,0.25); border-radius: 12px; padding: 16px 18px; margin-bottom: 14px; }
    .crypto-card { background: rgba(255,152,0,0.08); border: 1px solid rgba(255,152,0,0.25); border-radius: 12px; padding: 16px 18px; margin-bottom: 14px; }
    .status-pill-green { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(0,200,83,0.15); color: #00c853; }
    .status-pill-orange { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(255,152,0,0.15); color: #ff9800; }
    .disclaimer-box { background: rgba(255,193,7,0.08); border: 1px solid rgba(255,193,7,0.35); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #b58a00; margin-top: 6px; }
    .scenario-card { background: rgba(127,127,127,0.04); border: 1px solid rgba(127,127,127,0.1); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .login-card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 16px; padding: 40px 32px; text-align: center; margin-top: 80px; }
</style>
""", unsafe_allow_html=True)

# ==================== AUTHENTICATION ====================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.authenticated:
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; }</style>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f"""
        <div class="login-card">
            <div style="font-size:56px;">🤖</div>
            <div style="font-size:24px;font-weight:700;">AI Intelligent Trader</div>
            <div style="font-size:14px;color:#9aa0a6;margin-bottom:6px;">Self-Learning Trading Assistant</div>
            <div style="font-size:12px;color:#7c4dff;margin-bottom:28px;">🧠 DeepSeek · Claude · Letta Memory</div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Create Account"])
        with tab1:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("🔓 Unlock Dashboard", use_container_width=True):
                # Inline auth
                auth_file = "users.json"
                if os.path.exists(auth_file):
                    with open(auth_file) as f:
                        users = json.load(f).get("users", [])
                    for u in users:
                        if u["id"] == username and u["password"] == password:
                            st.session_state.authenticated = True
                            st.session_state.user = u
                            st.rerun()
                st.error("Invalid username or password.")
        with tab2:
            new_username = st.text_input("Choose a username", key="reg_user")
            new_password = st.text_input("Choose a password", type="password", key="reg_pass")
            new_name = st.text_input("Your name (optional)", key="reg_name")
            if st.button("✨ Create My Account", use_container_width=True):
                if len(new_username) < 3: st.error("Username must be at least 3 characters.")
                elif len(new_password) < 4: st.error("Password must be at least 4 characters.")
                else:
                    auth_file = "users.json"
                    users_data = {"users": []}
                    if os.path.exists(auth_file):
                        with open(auth_file) as f: users_data = json.load(f)
                    for u in users_data["users"]:
                        if u["id"] == new_username:
                            st.error("Username taken."); st.stop()
                    new_user = {"id": new_username, "password": new_password, "name": new_name or new_username, "role": "user", "created": datetime.now().strftime("%Y-%m-%d")}
                    users_data["users"].append(new_user)
                    with open(auth_file, "w") as f: json.dump(users_data, f, indent=2)
                    st.success(f"Welcome, {new_name or new_username}!")
                    st.session_state.authenticated = True
                    st.session_state.user = new_user
                    st.rerun()
        st.divider()
        st.caption("🔒 Authorized access only.")
    st.stop()

# ==================== HELPERS ====================

def safe_pct(num, den): return round(num / den * 100, 2) if den else 0.0
def fmt_money(x): return f"${x:,.2f} CAD" if x else "$0.00 CAD"
def time_ago(ts_str):
    try:
        ts = pd.to_datetime(ts_str)
        secs = (datetime.now() - ts.to_pydatetime().replace(tzinfo=None)).total_seconds()
        if secs < 60: return "just now"
        if secs < 3600: return f"{int(secs//60)} min ago"
        if secs < 86400: return f"{int(secs//3600)} hr ago"
        return f"{int(secs//86400)} day(s) ago"
    except: return ""

@st.cache_data(ttl=60)
def load_data():
    try: subprocess.run(["git", "pull", "origin", "main"], capture_output=True, timeout=10)
    except: pass
    snapshots, trades, scenarios, learned_rules = [], [], [], []
    if os.path.exists("logs/portfolio_snapshots.json"):
        with open("logs/portfolio_snapshots.json") as f: snapshots = json.load(f)
    if os.path.exists("logs/trades.json"):
        with open("logs/trades.json") as f: trades = json.load(f)
    if os.path.exists("logs/scenario_snapshots.json"):
        with open("logs/scenario_snapshots.json") as f: scenarios = json.load(f)
    if os.path.exists("logs/learned_rules.json"):
        with open("logs/learned_rules.json") as f: learned_rules = json.load(f)
    scenarios_config = []
    if os.path.exists("scenarios.json"):
        with open("scenarios.json") as f: scenarios_config = json.load(f).get("scenarios", [])
    return snapshots, trades, scenarios, learned_rules, scenarios_config

snapshots, trades, scenarios, learned_rules, scenarios_config = load_data()
user = st.session_state.get("user", {})
is_admin = user.get("role") == "admin"

# ==================== SIDEBAR ====================

with st.sidebar:
    st.markdown(f"### 🤖 Welcome, {user.get('name', 'Trader')}!")
    st.caption(f"@{user.get('id', 'unknown')}")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False; st.session_state.user = None; st.rerun()
    st.divider()

    if is_admin:
        with st.expander("🔧 Admin Panel", expanded=False):
            st.markdown("**Create New User**")
            admin_user = st.text_input("Username", key="admin_user")
            admin_pass = st.text_input("Password", type="password", key="admin_pass")
            admin_name = st.text_input("Name", key="admin_name")
            if st.button("➕ Create User", use_container_width=True):
                if len(admin_user) >= 3 and len(admin_pass) >= 4:
                    auth_file = "users.json"
                    data = {"users": []}
                    if os.path.exists(auth_file):
                        with open(auth_file) as f: data = json.load(f)
                    if any(u["id"] == admin_user for u in data["users"]):
                        st.error("Username taken.")
                    else:
                        data["users"].append({"id": admin_user, "password": admin_pass, "name": admin_name or admin_user, "role": "user", "created": datetime.now().strftime("%Y-%m-%d")})
                        with open(auth_file, "w") as f: json.dump(data, f, indent=2)
                        st.success(f"User '{admin_user}' created!")
                else:
                    st.error("Username 3+ chars, password 4+ chars.")
        st.divider()

    st.markdown("**📖 How to read this page**")
    st.write("- 📈 **Stocks** = 4 test accounts\n- 🪙 **Crypto** = 1 Pennies account\n- 📋 **Activity** = every trade explained\n- 🧠 **Letta AI** = learns from outcomes")
    st.divider()
    st.markdown("**🛡️ Stock Risk Levels**")
    st.write("🛡️ Conservative | ⚖️ Balanced | 🚀 Aggressive")
    st.markdown("**🪙 Crypto Strategy**")
    st.write("💰 Pennies — Small wins, compound growth, 24/7")
    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. No real money. Not financial advice.</div>', unsafe_allow_html=True)

# ==================== NO DATA ====================

if not scenarios and not snapshots:
    st.title("🤖 AI Intelligent Trader")
    st.info("### Setting up...\n\nCheck back after the first trading cycle.")
    st.stop()

# ==================== HEADER ====================

st.title("🤖 AI Intelligent Trader")
st.caption("Self-learning AI — Z-Score + Kelly for stocks, Pennies for crypto, Letta for memory.")
st.divider()

# ==================== STOCKS SECTION ====================

st.markdown('<p class="section-title">📈 Stock Trading Accounts</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Z-Score entries · Kelly sizing · Sharpe quality filter</p>', unsafe_allow_html=True)

latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

risk_options = ["conservative", "balanced", "aggressive"]
risk_emoji = {"conservative": "🛡️", "balanced": "⚖️", "aggressive": "🚀", "pennies": "🪙"}

stock_configs = [s for s in scenarios_config if s.get("type") == "stocks"]
crypto_configs = [s for s in scenarios_config if s.get("type") == "crypto"]

if stock_configs:
    cols = st.columns(len(stock_configs))
    for i, sc in enumerate(stock_configs):
        sid = sc["id"]
        with cols[i]:
            current_risk = sc.get("risk_profile", "balanced")
            st.caption(f"**{sc['name']}**")
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="scenario-card"><b>{fmt_money(capital)}</b><br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 📦 {data.get('positions', 0)} holdings</small><br><small>{risk_emoji.get(current_risk, '')} {current_risk.title()}</small></div>""", unsafe_allow_html=True)

st.divider()

# ==================== CRYPTO SECTION ====================

st.markdown('<p class="section-title">🪙 Crypto Trading Account</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Pennies Strategy — VWAP Z-Score · ATR stops · Fee-aware · 24/7</p>', unsafe_allow_html=True)

if crypto_configs:
    cols = st.columns(len(crypto_configs))
    for i, sc in enumerate(crypto_configs):
        sid = sc["id"]
        with cols[i]:
            st.caption(f"**{sc['name']}**")
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="crypto-card"><b>{fmt_money(capital)}</b> starting<br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 🎯 Target: +1.5-3% | 🛑 Stop: ATR-based</small><br><small>🪙 Pennies Strategy · 24/7 Trading</small></div>""", unsafe_allow_html=True)
    st.caption("💡 Pennies Strategy: Small consistent wins (0.5-3%) compound into big returns. Trades 24/7 — never sleeps.")
else:
    st.info("🪙 Crypto account starting soon...")

st.divider()

# ==================== RECENT TRADES ====================

st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Every trade explained in plain English. Click any trade to see why it happened.</p>', unsafe_allow_html=True)

if trades:
    df_t = pd.DataFrame(trades)
    if 'timestamp' in df_t.columns:
        df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
        df_t = df_t.sort_values('timestamp', ascending=False)
        filt = st.radio("Show", ["All", "Buys 📈", "Sells 📉", "Crypto 🪙"], horizontal=True, label_visibility="collapsed")
        if "Buys" in filt: df_t = df_t[df_t['action'] == "BUY"]
        elif "Sells" in filt: df_t = df_t[df_t['action'] == "SELL"]
        elif "Crypto" in filt: df_t = df_t[df_t['symbol'].isin(["BTC-USD", "ETH-USD"])]
        for _, r in df_t.head(30).iterrows():
            action = r.get('action', '')
            symbol = r.get('symbol', '')
            qty = r.get('quantity', 0)
            price = r.get('price_usd', 0)
            ai = r.get('ai_modified', False)
            reason = r.get('reason', '')
            fees = r.get('fees_cad', 0)
            ts = r.get('timestamp', '')
            is_crypto = symbol in ["BTC-USD", "ETH-USD"]
            emoji = "🟢 Bought" if action == "BUY" else "🔴 Sold"
            tag = " 🪙" if is_crypto else " 🤖 AI" if ai else ""
            with st.expander(f"{emoji} {qty:.4f} {symbol} @ ${price:.2f} USD{tag}"):
                st.write(f"**When:** {ts} ({time_ago(ts)})")
                st.write(f"**Why:** {reason[:300] if reason else 'Strategy signal triggered'}")
                if fees > 0: st.write(f"**Fee:** ${fees:.2f} CAD")
        st.download_button("⬇️ Download CSV", df_t.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
else:
    st.info("No trades yet. The AI is watching the market 24/7.")

st.divider()

# ==================== LEARNED RULES ====================

st.markdown('<p class="section-title">🧠 Letta\'s Learned Rules</p>', unsafe_allow_html=True)
if learned_rules:
    active = [r for r in learned_rules if r.get("confidence", 0) >= 0.5]
    st.metric("Rules Learned", len(active))
    for rule in active[:5]:
        conf = rule.get("confidence", 0)
        conf_color = "green" if conf > 0.7 else "orange" if conf > 0.5 else "red"
        st.markdown(f"• **{rule.get('description', '')}** — <span style='color:{conf_color}'>{conf:.0%} confidence</span>", unsafe_allow_html=True)
else:
    st.info("Letta is waiting for trade outcomes to start learning...")

st.divider()

# ==================== HOW IT WORKS ====================

st.markdown('<p class="section-title">🧠 How the AI Works</p>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown("""<div class="card"><b>📈 Stocks</b><br><br>Z-Score finds statistically significant dips. Kelly sizes positions optimally. Sharpe filters noise.<br><br><i>Math-driven, emotion-free.</i></div>""", unsafe_allow_html=True)
c2.markdown("""<div class="card"><b>🪙 Crypto</b><br><br>VWAP Z-Score detects volume-weighted dips. ATR sets dynamic stops. Fees calculated into every trade.<br><br><i>Pennies compound into dollars.</i></div>""", unsafe_allow_html=True)
c3.markdown("""<div class="card"><b>🧠 Letta Memory</b><br><br>Remembers every trade. Learns from wins AND losses. Creates rules that improve over time.<br><br><i>Smarter every single day.</i></div>""", unsafe_allow_html=True)

st.divider()

st.markdown("""
<div style="text-align:center; padding: 20px;">
    <hr style="border-color: rgba(127,127,127,0.2);">
    <p style="color: #666; font-size: 12px;">© 2026 <b>OnlySolutions Inc.</b> — All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
st.caption(f"AI Intelligent Trader v2.6 · 24/7 on Railway · {len(scenarios)} snapshots · {len(trades)} trades · {len(learned_rules)} learned rules · Paper trading only")