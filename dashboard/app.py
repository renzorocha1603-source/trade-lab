"""
Trade Lab Dashboard v2.2 — Password-protected, 5 scenarios with risk selection.
Each scenario can choose Conservative, Balanced, or Aggressive.
Designed for anyone to understand — no finance degree needed.
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
    .tip-box { background: rgba(66,133,244,0.08); border: 1px solid rgba(66,133,244,0.2); border-radius: 8px; padding: 10px 14px; font-size: 13px; margin: 8px 0; }
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
    except:
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

# ==================== SIDEBAR — Everything Explained ====================

with st.sidebar:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.markdown("### 🤖 Trade Lab")
    st.caption("Your AI-powered trading assistant")
    st.divider()

    st.markdown("**📖 How to read this page**")
    st.write(
        "- 🧪 **Top cards** = 5 test accounts running at the same time\n"
        "- 💰 **Green number** = how much money is in each account\n"
        "- 📈 **Percentage** = how much you've made (or lost) so far\n"
        "- 📋 **Activity** = every buy and sell, explained in simple words"
    )

    st.divider()

    st.markdown("**🛡️ What the risk levels mean**")
    st.write(
        "**🛡️ Conservative (Safest):**\n"
        "- Makes 2-7 trades per week\n"
        "- Very picky about what to buy\n"
        "- Keeps 20% cash just in case\n"
        "- Only buys Canadian stocks & crypto\n"
        "- Best for: $500 account\n\n"
        "**⚖️ Balanced (Middle ground):**\n"
        "- Makes 10-20 trades per week\n"
        "- Uses smart filters to avoid bad buys\n"
        "- Keeps 10% cash in reserve\n"
        "- Buys US, Canadian, and crypto\n"
        "- Best for: $1,000 - $5,000 accounts\n\n"
        "**🚀 Aggressive (Most active):**\n"
        "- Trades whenever there's an opportunity\n"
        "- Uses only the basic 5/10 rule\n"
        "- Keeps 5% cash\n"
        "- Buys everything\n"
        "- Best for: $10,000 account"
    )

    st.divider()

    st.markdown("**⏰ When does it trade?**")
    st.write(
        "- Monday to Friday only\n"
        "- 9:30 AM to 4:00 PM (New York time)\n"
        "- Checks prices every 15 minutes\n"
        "- Weekends: watches news but doesn't trade"
    )

    st.divider()

    st.markdown("**💡 Tips**")
    st.write(
        "- The AI explains WHY it made each trade — click the arrow to read it\n"
        "- You can change any account's risk level anytime — it updates within 15 minutes\n"
        "- Download your trade history as a spreadsheet anytime\n"
        "- This is fake money for testing — no real dollars are used"
    )

    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ This is a paper trading simulation. No real money is used. Nothing here is financial advice. Past results do not guarantee future performance.</div>', unsafe_allow_html=True)

# ==================== NO DATA YET ====================

if not scenarios and not snapshots:
    st.title("🤖 Trade Lab")
    st.info("""
    ### Your AI Trading Assistant is setting up...

    Soon you'll see:
    - 🧪 **5 test accounts** running side by side
    - 💰 **How much each one has** in real time
    - 📋 **Every trade explained** in plain English

    *Check back after the first trading cycle — usually within 15 minutes during market hours.*
    """)
    st.stop()

# ==================== HEADER ====================

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🤖 Trade Lab")
    st.caption("5 accounts. 3 risk levels. 1 AI running them all.")
with col2:
    st.markdown('<span class="status-pill-green">🟢 Live</span>', unsafe_allow_html=True)
    st.caption(f"Updated: {datetime.now().strftime('%b %d, %I:%M %p')}")

# ==================== WHAT IS THIS? ====================

with st.expander("🤔 What am I looking at?", expanded=False):
    st.markdown("""
    ### Welcome to your AI Trading Lab!
    
    **In plain English, here's what's happening:**
    
    - You have **5 virtual accounts** with different amounts of play money ($500, $1,000, $2,500, $5,000, $10,000)
    - An **AI brain** watches the stock market 24/7 and decides when to buy and sell
    - Each account has a **risk level** you can change (Conservative = careful, Balanced = middle, Aggressive = bold)
    - Every trade is **explained in simple words** — click any trade to see why the AI did it
    - This is **practice money only** — great for testing before using real dollars
    
    **The goal:** Find which combination of account size and risk level works best!
    """)

st.divider()

# ==================== SCENARIO SIMULATOR WITH RISK SELECTION ====================

st.markdown('<p class="section-title">🧪 Your 5 Test Accounts</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Each account runs independently with its own risk level. Change the risk anytime — it updates within 15 minutes.</p>', unsafe_allow_html=True)

# Build latest scenario data
latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

risk_options = ["conservative", "balanced", "aggressive"]
risk_emoji = {"conservative": "🛡️", "balanced": "⚖️", "aggressive": "🚀"}
risk_explanations = {
    "conservative": "Safest — few trades, strict filters",
    "balanced": "Middle — regular trades, smart filters",
    "aggressive": "Bold — many trades, basic rules only"
}

config_map = {}
for sc in scenarios_config:
    config_map[sc["id"]] = sc

if scenarios_config:
    cols = st.columns(len(scenarios_config))
    for i, sc in enumerate(scenarios_config):
        sid = sc["id"]
        with cols[i]:
            current_risk = sc.get("risk_profile", "balanced")
            
            # Risk selector with label
            st.caption(f"**{sc['name']}**")
            new_risk = st.selectbox(
                "Risk level",
                risk_options,
                index=risk_options.index(current_risk) if current_risk in risk_options else 1,
                key=f"risk_{sid}",
                format_func=lambda x: f"{risk_emoji.get(x, '')} {x.title()}",
                help=risk_explanations.get(current_risk, "")
            )

            if new_risk != current_risk:
                sc["risk_profile"] = new_risk
                if save_scenarios_to_github(scenarios_config):
                    st.success(f"✅ Changed to {new_risk}!")
                    st.rerun()

            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"

            st.markdown(f"""
            <div class="scenario-card">
                <b>{fmt_money(capital)}</b> starting<br>
                <h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3>
                <small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br>
                <small>📊 {data.get('trades', 0)} trades | 📦 {data.get('positions', 0)} holdings</small><br>
                <small style="color:#888;">{risk_emoji.get(current_risk, '')} {current_risk.title()}</small>
            </div>
            """, unsafe_allow_html=True)

    st.caption("💡 **Tip:** Click the dropdown above any account to change its risk level. The change takes effect on the next trading cycle (within 15 minutes during market hours).")

else:
    st.info("Loading account configurations...")

st.divider()

# ==================== RECENT TRADES ====================

st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Every trade the AI made, explained in plain English. Click any trade to see why it happened.</p>', unsafe_allow_html=True)

if trades:
    df_t = pd.DataFrame(trades)
    if 'timestamp' in df_t.columns:
        df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
        df_t = df_t.sort_values('timestamp', ascending=False)
        
        filt = st.radio("Show:", ["All trades", "Buys only 📈", "Sells only 📉"], horizontal=True, label_visibility="collapsed")
        if "Buys" in filt: df_t = df_t[df_t['action'] == "BUY"]
        elif "Sells" in filt: df_t = df_t[df_t['action'] == "SELL"]
        
        for _, r in df_t.head(30).iterrows():
            action = r.get('action', '')
            symbol = r.get('symbol', '')
            qty = r.get('quantity', 0)
            price = r.get('price_usd', 0)
            ai = r.get('ai_modified', False)
            reason = r.get('reason', '')
            fees = r.get('fees_cad', 0)
            ts = r.get('timestamp', '')
            
            emoji = "🟢 Bought" if action == "BUY" else "🔴 Sold"
            ai_tag = " (AI helped decide)" if ai else ""
            
            with st.expander(f"{emoji} {qty:.4f} shares of {symbol} at ${price:.2f} USD{ai_tag}"):
                st.write(f"**When:** {ts} ({time_ago(ts)})")
                if reason:
                    st.write(f"**Why the AI did this:** {reason[:500]}")
                else:
                    st.write("**Why:** The 5/10 rule triggered — the stock moved enough to warrant a trade.")
                if fees > 0:
                    st.write(f"**Fee charged:** ${fees:.2f} CAD (This is Wealthsimple's 1.5% fee for converting Canadian to US dollars)")
        
        # Download button
        csv = df_t.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download all trades (Spreadsheet)",
            data=csv,
            file_name="my_trades.csv",
            mime="text/csv",
            help="Opens in Excel or Google Sheets — perfect for your own records."
        )
else:
    st.info("No trades have happened yet. The AI is watching the market and waiting for the right moment. Trades will appear here automatically when the market opens.")
    st.write("**What to expect:** When the AI finds a good opportunity, you'll see green (buy) or red (sell) entries here with explanations of why.")

st.divider()

# ==================== HOW IT WORKS ====================

st.markdown('<p class="section-title">🧠 How the AI Makes Decisions</p>', unsafe_allow_html=True)

col_how1, col_how2 = st.columns(2)

with col_how1:
    st.markdown("""
    <div class="card">
    <b>📊 Step 1: Watch the Market</b><br><br>
    The system monitors 31 different investments — US stocks, Canadian stocks, ETFs, and crypto — using 4 different data sources to get the most accurate prices and news.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
    <b>🧮 Step 2: Do the Math</b><br><br>
    The 5/10 Rule looks at the last 2 weeks. If something dropped more than 3%, it considers buying. If something rose more than 5%, it considers selling. Extra filters (RSI, ATR) make sure it's not catching a "falling knife" — buying something that keeps dropping.
    </div>
    """, unsafe_allow_html=True)

with col_how2:
    st.markdown("""
    <div class="card">
    <b>🧠 Step 3: Ask the AI</b><br><br>
    DeepSeek AI reads the news and analyzes the numbers — like a tireless research analyst. For really big events, Claude AI double-checks as a second opinion. But the AI only advises — math rules make the final call.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
    <b>✅ Step 4: Execute (or Don't)</b><br><br>
    If all filters pass, the trade happens automatically. If any filter says no, the trade is skipped. This prevents impulse decisions and keeps the system disciplined.
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.caption(f"Trade Lab v2.2 · Running 24/7 on Railway · {len(scenarios)} scenario snapshots · {len(trades)} trades recorded · Paper trading simulation only")