"""
Trade Lab Dashboard v2.2 — Password-protected, 5 scenarios with risk selection.
Each scenario can choose Conservative, Balanced, or Aggressive.
"""

import streamlit as st
import pandas as pd
import json
import os
import subprocess
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Trade Lab", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .section-title { font-size: 21px; font-weight: 700; margin-top: 8px; margin-bottom: 2px; }
    .section-subtitle { font-size: 13px; color: #9aa0a6; margin-bottom: 14px; }
    .explanation { font-size: 13px; color: #888; font-style: italic; }
    .card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 12px; padding: 16px 18px; margin-bottom: 14px; }
    .status-pill-green { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(0,200,83,0.15); color: #00c853; }
    .disclaimer-box { background: rgba(255,193,7,0.08); border: 1px solid rgba(255,193,7,0.35); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #b58a00; margin-top: 6px; }
    .scenario-card { background: rgba(127,127,127,0.04); border: 1px solid rgba(127,127,127,0.1); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .login-card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 16px; padding: 40px 32px; text-align: center; margin-top: 80px; }
</style>
""", unsafe_allow_html=True)

# ==================== AUTHENTICATION ====================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f"""
        <div class="login-card">
            <div style="font-size:56px;">🤖</div>
            <div style="font-size:24px;font-weight:700;">Trade Lab</div>
            <div style="font-size:14px;color:#9aa0a6;margin-bottom:28px;">Your AI-Powered Trading Assistant</div>
        </div>
        """, unsafe_allow_html=True)
        password = st.text_input("Enter password to continue", type="password", placeholder="••••••••••••")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            if st.button("🔓 Unlock Dashboard", use_container_width=True):
                if password == "Angelorea1$":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password. Please try again.")
        st.divider()
        st.caption("🔒 This dashboard contains private trading data.")
        st.caption("Authorized access only.")
    st.stop()

# ==================== HELPERS ====================

def safe_pct(num, den):
    return round(num / den * 100, 2) if den else 0.0

def fmt_money(x):
    try: return f"${x:,.2f} CAD"
    except: return "$0.00 CAD"

def time_ago(ts_str):
    try:
        ts = pd.to_datetime(ts_str)
        secs = (datetime.now() - ts.to_pydatetime().replace(tzinfo=None)).total_seconds()
        if secs < 60: return "just now"
        if secs < 3600: return f"{int(secs//60)} min ago"
        if secs < 86400: return f"{int(secs//3600)} hr ago"
        return f"{int(secs//86400)} day(s) ago"
    except: return ""

def save_scenarios_to_github(scenarios_data):
    """Save updated scenarios.json and push to GitHub"""
    try:
        with open("scenarios.json", "w") as f:
            json.dump({"scenarios": scenarios_data}, f, indent=2)
        subprocess.run(["git", "add", "scenarios.json"], capture_output=True, timeout=5)
        subprocess.run(["git", "commit", "-m", "Update risk profiles from dashboard"], capture_output=True, timeout=5)
        subprocess.run(["git", "push"], capture_output=True, timeout=10)
        return True
    except Exception as e:
        return False

@st.cache_data(ttl=60)
def load_data():
    try: subprocess.run(["git", "pull", "origin", "main"], capture_output=True, timeout=10)
    except: pass

    snapshots, trades, accuracy, scenarios = [], [], {"accuracy": 0, "total_checked": 0}, []
    scenarios_config = []

    if os.path.exists("logs/portfolio_snapshots.json"):
        with open("logs/portfolio_snapshots.json") as f: snapshots = json.load(f)
    if os.path.exists("logs/trades.json"):
        with open("logs/trades.json") as f: trades = json.load(f)
    if os.path.exists("logs/accuracy_log.json"):
        with open("logs/accuracy_log.json") as f:
            preds = json.load(f)
            checked = [p for p in preds if p.get("outcome_checked")]
            if checked:
                accuracy["total_checked"] = len(checked)
                accuracy["accuracy"] = round(sum(1 for p in checked if p.get("outcome_correct")) / len(checked) * 100, 1)
    if os.path.exists("logs/scenario_snapshots.json"):
        with open("logs/scenario_snapshots.json") as f: scenarios = json.load(f)
    if os.path.exists("scenarios.json"):
        with open("scenarios.json") as f:
            data = json.load(f)
            scenarios_config = data.get("scenarios", [])

    return snapshots, trades, accuracy, scenarios, scenarios_config

snapshots, trades, accuracy, scenarios, scenarios_config = load_data()

# ==================== SIDEBAR ====================

with st.sidebar:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.markdown("### 🤖 Trade Lab")
    st.caption("Your AI-powered trading assistant")
    st.divider()

    st.markdown("**Risk Profiles**")
    st.write("- 🛡️ **Conservative**: 2-7 trades/week, low risk")
    st.write("- ⚖️ **Balanced**: 10-20 trades/week, medium risk")
    st.write("- 🚀 **Aggressive**: Daily trades, 5/10 rule only")

    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. Not financial advice.</div>', unsafe_allow_html=True)

# ==================== NO DATA YET ====================

if not scenarios and not snapshots:
    st.title("🤖 Trade Lab")
    st.info("""
    ### Your AI Trading Assistant is setting up...

    This dashboard will show:
    - 🧪 **5 scenarios** with different risk levels
    - 💰 **Real-time equity** for each account size
    - 📊 **Every trade** and why it was made

    *Check back after the first trading cycle completes.*
    """)
    st.stop()

# ==================== HEADER ====================

st.title("🤖 Trade Lab")
st.caption("Multi-Scenario AI Trading — Conservative · Balanced · Aggressive")

st.divider()

# ==================== SCENARIO SIMULATOR WITH RISK SELECTION ====================

st.markdown('<p class="section-title">🧪 Scenario Simulator</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Each scenario runs independently with its own risk profile. Change the risk level anytime — it updates on the next trading cycle.</p>', unsafe_allow_html=True)

# Build scenario cards
latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

# Risk profile options
risk_options = ["conservative", "balanced", "aggressive"]
risk_emoji = {"conservative": "🛡️", "balanced": "⚖️", "aggressive": "🚀"}

# Get scenario configs for risk selection
config_map = {}
for sc in scenarios_config:
    config_map[sc["id"]] = sc

# Display scenario cards in a row
if scenarios_config:
    cols = st.columns(len(scenarios_config))
    for i, sc in enumerate(scenarios_config):
        sid = sc["id"]
        with cols[i]:
            # Risk profile selector
            current_risk = sc.get("risk_profile", "balanced")
            new_risk = st.selectbox(
                f"{risk_emoji.get(current_risk, '')} Risk",
                risk_options,
                index=risk_options.index(current_risk) if current_risk in risk_options else 1,
                key=f"risk_{sid}",
                label_visibility="collapsed"
            )

            # If changed, update scenarios.json
            if new_risk != current_risk:
                sc["risk_profile"] = new_risk
                if save_scenarios_to_github(scenarios_config):
                    st.success(f"Updated to {new_risk}!")
                    st.rerun()

            # Show equity
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"

            st.markdown(f"""
            <div class="scenario-card">
                <b>{sc['name']}</b><br>
                <small style="color:#888;">{risk_emoji.get(current_risk, '')} {current_risk.title()}</small>
                <h4 style="color:{c};margin:4px 0;">{fmt_money(equity)}</h4>
                <small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br>
                <small>Trades: {data.get('trades', 0)} | Pos: {data.get('positions', 0)}</small>
            </div>
            """, unsafe_allow_html=True)

    st.caption("💡 Change any scenario's risk level above — the bot updates on the next cycle (~15 min during market hours).")
else:
    st.info("Scenario configuration loading...")

st.divider()

# ==================== RECENT TRADES ====================

st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)

if trades:
    df_t = pd.DataFrame(trades)
    if 'timestamp' in df_t.columns:
        df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
        df_t = df_t.sort_values('timestamp', ascending=False)
        filt = st.radio("Show", ["All", "Buys", "Sells"], horizontal=True, label_visibility="collapsed")
        if filt == "Buys": df_t = df_t[df_t['action'] == "BUY"]
        elif filt == "Sells": df_t = df_t[df_t['action'] == "SELL"]
        for _, r in df_t.head(20).iterrows():
            emoji = "🟢" if r.get('action') == "BUY" else "🔴"
            ai = " 🤖 AI" if r.get('ai_modified') else ""
            with st.expander(f"{emoji} {r.get('action')} {r.get('quantity', 0):.4f} {r.get('symbol')} @ ${r.get('price_usd', 0):.2f}{ai}"):
                st.write(f"**When:** {r.get('timestamp')} ({time_ago(r.get('timestamp'))})")
                st.write(f"**Why:** {r.get('reason', 'No reason logged')[:300]}")
                if r.get('fees_cad', 0) > 0: st.write(f"**Fee:** ${r['fees_cad']:.2f} CAD")
else:
    st.info("No trades yet. Trades will appear when the market opens.")

st.divider()

# ==================== ABOUT ====================

st.markdown('<p class="section-title">🧠 About The AI</p>', unsafe_allow_html=True)
st.markdown("""
<div class="card">
<b>How decisions are made:</b><br><br>
1️⃣ <b>DeepSeek AI</b> scans news + technicals 24/7<br>
2️⃣ <b>Claude AI</b> steps in for extreme events only<br>
3️⃣ <b>5/10 Rule</b> — buy small on dips, sell on rallies<br>
4️⃣ <b>Risk Profiles</b> — each scenario uses its own filters<br><br>
<b>Conservative:</b> RSI + ATR + Sector Limits + 20% cash reserve<br>
<b>Balanced:</b> RSI + Sector Limits + 10% cash reserve<br>
<b>Aggressive:</b> 5/10 Rule only, 5% cash reserve<br><br>
<i>Math rules make the final call. No impulsive decisions.</i>
</div>
""", unsafe_allow_html=True)

st.divider()
st.caption(f"Trade Lab v2.2 · 24/7 on Railway · {len(scenarios)} scenario snapshots · {len(trades)} trades · Paper trading only")