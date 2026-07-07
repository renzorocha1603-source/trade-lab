"""
AI Intelligent Trader Dashboard v2.9 — Phase 2 Complete
Stocks · Crypto · Fiat · Ask Letta · Training Mode
Claude-polished UI — designed for anyone to understand.
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
    .crypto-card { background: rgba(255,152,0,0.08); border: 1px solid rgba(255,152,0,0.25); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .fiat-card { background: rgba(0,150,136,0.08); border: 1px solid rgba(0,150,136,0.25); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .status-pill-green { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(0,200,83,0.15); color: #00c853; }
    .disclaimer-box { background: rgba(255,193,7,0.08); border: 1px solid rgba(255,193,7,0.35); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #b58a00; margin-top: 6px; }
    .scenario-card { background: rgba(127,127,127,0.04); border: 1px solid rgba(127,127,127,0.1); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .login-card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 16px; padding: 40px 32px; text-align: center; margin-top: 80px; }
    .letta-answer { background: rgba(124,77,255,0.06); border: 1px solid rgba(124,77,255,0.2); border-radius: 10px; padding: 12px 16px; margin-top: 8px; font-size: 14px; }
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
        st.markdown(f"""<div class="login-card"><div style="font-size:56px;">🤖</div><div style="font-size:24px;font-weight:700;">AI Intelligent Trader</div><div style="font-size:14px;color:#9aa0a6;margin-bottom:6px;">Self-Learning Trading Assistant</div><div style="font-size:12px;color:#7c4dff;margin-bottom:28px;">🧠 DeepSeek · Claude · Letta Memory</div></div>""", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Login", "Create Account"])
        with tab1:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("🔓 Unlock Dashboard", use_container_width=True):
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
                        if u["id"] == new_username: st.error("Username taken."); st.stop()
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
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False; st.session_state.user = None; st.rerun()
    st.divider()

    # ==================== ASK LETTA ====================
    st.markdown("### 🧠 Ask Letta")
    st.caption("Ask about any symbol Letta has traded")
    ask_symbol = st.text_input("Symbol", placeholder="e.g., NVDA, BTC-USD, XLM-USD", key="ask_letta")
    if st.button("🔍 Ask Letta", use_container_width=True) and ask_symbol:
        relevant_trades = [t for t in trades if t.get("symbol", "").upper() == ask_symbol.upper()]
        checked = [t for t in relevant_trades if t.get("outcome_checked")]
        wins = sum(1 for t in checked if t.get("outcome_success"))
        total = len(checked)
        win_rate = round(wins / max(total, 1) * 100, 1)
        
        st.markdown(f"""<div class="letta-answer">
        <b>📊 {ask_symbol.upper()}</b><br>
        • Trades tracked: {len(relevant_trades)} total<br>
        • Analyzed: {total} (need 24h to evaluate)<br>
        • Win rate: {win_rate}% ({wins}/{total})<br>
        • Rules learned: {len([r for r in learned_rules if ask_symbol.upper() in r.get('description', '').upper()])}
        </div>""", unsafe_allow_html=True)
        
        if total == 0:
            st.caption("No analyzed trades yet — Letta needs 24h to evaluate outcomes.")
    
    st.divider()

    # ==================== LETTA STATS ====================
    st.markdown("### 📈 Letta's Brain")
    active_rules = [r for r in learned_rules if r.get("confidence", 0) >= 0.5]
    checked_trades = [t for t in trades if t.get("outcome_checked")]
    win_rate_all = round(sum(1 for t in checked_trades if t.get("outcome_success")) / max(len(checked_trades), 1) * 100, 1)
    
    st.metric("🧠 Rules Learned", len(active_rules))
    st.metric("🎯 Win Rate", f"{win_rate_all}%" if checked_trades else "Learning...")
    st.metric("📊 Trades Analyzed", len(checked_trades))
    st.metric("💪 Total Trades", len(trades))
    
    if active_rules:
        with st.expander("🧠 Top 5 Rules"):
            for rule in sorted(active_rules, key=lambda r: r["confidence"], reverse=True)[:5]:
                conf = rule.get("confidence", 0)
                c = "green" if conf > 0.7 else "orange" if conf > 0.5 else "red"
                st.markdown(f"• <span style='color:{c}'>{conf:.0%}</span> {rule.get('description', '')[:80]}", unsafe_allow_html=True)
    
    st.divider()
    st.markdown("**⏰ Training Mode Active**")
    st.write("• Trades every 10 minutes\n• 24/7 operation\n• Auto-reload at $50\n• Stocks + Crypto + Fiat")
    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. No real money. Not financial advice.</div>', unsafe_allow_html=True)

# ==================== HEADER ====================
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🤖 AI Intelligent Trader")
    st.caption("Training Mode — Letta learns from every trade. Stocks · Crypto · Fiat.")
with col2:
    st.markdown('<span class="status-pill-green">🟢 Live</span>', unsafe_allow_html=True)
    st.caption(f"Updated: {datetime.now().strftime('%b %d, %I:%M %p')}")
st.divider()

# ==================== SCENARIOS ====================
latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

stock_configs = [s for s in scenarios_config if s.get("type") == "stocks"]
crypto_configs = [s for s in scenarios_config if s.get("type") == "crypto"]
fiat_configs = [s for s in scenarios_config if s.get("type") == "fiat"]

# STOCKS
if stock_configs:
    st.markdown('<p class="section-title">📈 Stock Accounts</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Z-Score entries · Kelly sizing · Forced training mode</p>', unsafe_allow_html=True)
    cols = st.columns(len(stock_configs))
    for i, sc in enumerate(stock_configs):
        sid = sc["id"]
        with cols[i]:
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="scenario-card"><b>{sc['name']}</b><br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 📦 {data.get('positions', 0)} holdings</small></div>""", unsafe_allow_html=True)

# CRYPTO
if crypto_configs:
    st.markdown('<p class="section-title">🪙 Crypto Account</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Pennies Strategy · 20 coins · 24/7 · DIP/MOMENTUM/BREAKOUT</p>', unsafe_allow_html=True)
    cols = st.columns(len(crypto_configs))
    for i, sc in enumerate(crypto_configs):
        sid = sc["id"]
        with cols[i]:
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="crypto-card"><b>{sc['name']}</b><br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 🎯 Target: +1.5-3% | 🛑 Stop: ATR</small><br><small>🪙 Pennies · 20 coins · 24/7</small></div>""", unsafe_allow_html=True)

# FIAT
if fiat_configs:
    st.markdown('<p class="section-title">💱 Fiat Account</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Pennies Strategy · 5 forex pairs · Tighter spreads · 24/7</p>', unsafe_allow_html=True)
    cols = st.columns(len(fiat_configs))
    for i, sc in enumerate(fiat_configs):
        sid = sc["id"]
        with cols[i]:
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="fiat-card"><b>{sc['name']}</b><br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 🎯 Target: ATR×2.0 | 🛑 Stop: ATR×0.8</small><br><small>💱 5 pairs · 24/7</small></div>""", unsafe_allow_html=True)

st.divider()

# ==================== RECENT TRADES ====================
st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Every trade explained. Click any trade to see why it happened.</p>', unsafe_allow_html=True)

if trades:
    df_t = pd.DataFrame(trades)
    if 'timestamp' in df_t.columns:
        df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
        df_t = df_t.sort_values('timestamp', ascending=False)
        filt = st.radio("Show", ["All", "Stocks 📈", "Crypto 🪙", "Fiat 💱"], horizontal=True, label_visibility="collapsed")
        if "Stocks" in filt: 
            df_t = df_t[~df_t['symbol'].str.contains('-USD', na=False) & ~df_t['symbol'].str.contains('=X', na=False)]
        elif "Crypto" in filt: 
            df_t = df_t[df_t['symbol'].str.contains('-USD', na=False)]
        elif "Fiat" in filt: 
            df_t = df_t[df_t['symbol'].str.contains('=X', na=False)]
        for _, r in df_t.head(30).iterrows():
            action = r.get('action', '')
            symbol = r.get('symbol', '')
            qty = r.get('quantity', 0)
            price = r.get('price_usd', 0)
            reason = r.get('reason', '')
            fees = r.get('fees_cad', 0)
            ts = r.get('timestamp', '')
            is_crypto = "-USD" in str(symbol)
            is_fiat = "=X" in str(symbol)
            emoji = "🟢" if action == "BUY" else "🔴"
            tag = " 🪙" if is_crypto else " 💱" if is_fiat else ""
            with st.expander(f"{emoji} {action} {qty:.4f} {symbol} @ ${price:.2f}{tag}"):
                st.write(f"**When:** {ts} ({time_ago(ts)})")
                st.write(f"**Why:** {reason[:300] if reason else 'Forced training entry'}")
                if fees > 0: st.write(f"**Fee:** ${fees:.2f} CAD")
        st.download_button("⬇️ Download CSV", df_t.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
else:
    st.info("No trades yet. Forced training mode will enter positions every 10 minutes.")

st.divider()

# ==================== HOW IT WORKS ====================
st.markdown('<p class="section-title">🧠 How Letta Learns</p>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown("""<div class="card"><b>📝 Step 1: Trade</b><br><br>Every 10 minutes, the bot enters positions on stocks, crypto, and fiat — forced training ensures maximum data for learning.<br><br><i>Hundreds of trades per day.</i></div>""", unsafe_allow_html=True)
c2.markdown("""<div class="card"><b>🔍 Step 2: Analyze</b><br><br>After 24 hours, Letta checks every trade outcome and extracts patterns from wins AND losses across all 3 asset classes.<br><br><i>Thousands of data points.</i></div>""", unsafe_allow_html=True)
c3.markdown("""<div class="card"><b>💡 Step 3: Learn</b><br><br>Letta creates rules: "When VIX > 30 and RSI < 35, buying tech stocks works 85% of the time." These rules apply across ALL scenarios.<br><br><i>Smarter every single cycle.</i></div>""", unsafe_allow_html=True)

st.divider()
st.markdown("""
<div style="text-align:center; padding: 20px;">
    <hr style="border-color: rgba(127,127,127,0.2);">
    <p style="color: #666; font-size: 12px;">© 2026 <b>OnlySolutions Inc.</b> — All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
st.caption(f"AI Intelligent Trader v2.9 · Phase 2 Complete · {len(trades)} trades · {len(active_rules) if 'active_rules' in dir() else 0} rules · Paper trading only")