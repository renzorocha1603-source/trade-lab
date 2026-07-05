"""
AI Intelligent Trader Dashboard — Password-protected, 5 scenarios with risk selection.
Multi-user accounts with registration. Designed for anyone to understand.
Self-learning AI that improves from every trade.
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
    .status-pill-green { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(0,200,83,0.15); color: #00c853; }
    .disclaimer-box { background: rgba(255,193,7,0.08); border: 1px solid rgba(255,193,7,0.35); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #b58a00; margin-top: 6px; }
    .scenario-card { background: rgba(127,127,127,0.04); border: 1px solid rgba(127,127,127,0.1); border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 8px; }
    .login-card { background: rgba(127,127,127,0.06); border: 1px solid rgba(127,127,127,0.15); border-radius: 16px; padding: 40px 32px; text-align: center; margin-top: 80px; }
    .learning-badge { display: inline-block; background: linear-gradient(135deg, #7c4dff, #448aff); color: white; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; margin-left: 6px; }
</style>
""", unsafe_allow_html=True)

# ==================== AUTHENTICATION ====================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f"""
        <div class="login-card">
            <div style="font-size:56px;">🤖</div>
            <div style="font-size:24px;font-weight:700;">AI Intelligent Trader</div>
            <div style="font-size:14px;color:#9aa0a6;margin-bottom:6px;">Self-Learning Trading Assistant</div>
            <div style="font-size:12px;color:#7c4dff;margin-bottom:28px;">🧠 Powered by DeepSeek · Claude · Letta Memory</div>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Create Account"])

        with tab1:
            password = st.text_input("Enter password", type="password", placeholder="••••••••••••", key="login_pass")
            if st.button("🔓 Unlock Dashboard", use_container_width=True, key="login_btn"):
                from auth import AuthSystem
                auth = AuthSystem()
                user = auth.login("renzochiara", password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Incorrect password. Please try again.")

        with tab2:
            new_username = st.text_input("Choose a username", key="reg_user")
            new_password = st.text_input("Choose a password", type="password", key="reg_pass")
            new_name = st.text_input("Your name (optional)", key="reg_name")
            if st.button("✨ Create My Account", use_container_width=True, key="reg_btn"):
                if len(new_username) < 3:
                    st.error("Username must be at least 3 characters.")
                elif len(new_password) < 4:
                    st.error("Password must be at least 4 characters.")
                else:
                    from auth import AuthSystem
                    auth = AuthSystem()
                    user = auth.register(new_username, new_password, new_name)
                    if user:
                        st.success(f"Account created! Welcome, {new_name or new_username}!")
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Username already taken. Try a different one.")

        st.divider()
        st.caption("🔒 Authorized access only.")
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
    learned_rules = []

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
    if os.path.exists("logs/learned_rules.json"):
        with open("logs/learned_rules.json") as f:
            learned_rules = json.load(f)

    return snapshots, trades, accuracy, scenarios, scenarios_config, learned_rules

snapshots, trades, accuracy, scenarios, scenarios_config, learned_rules = load_data()

# ==================== SIDEBAR ====================

with st.sidebar:
    user = st.session_state.get("user", {})
    st.markdown(f"### 🤖 Welcome, {user.get('name', 'Trader')}!")
    st.caption(f"@{user.get('id', 'unknown')} · {user.get('role', 'user').title()}")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    st.divider()

    st.markdown("**📖 How to read this page**")
    st.write(
        "- 🧪 **Top cards** = your test accounts\n"
        "- 💰 **Numbers** = how much money in each\n"
        "- 📈 **Percentage** = your profit or loss\n"
        "- 📋 **Activity** = every trade explained\n"
        "- 📊 **Charts page** = visual analytics\n"
        "- 🧠 **Letta AI** = learns from every trade"
    )

    st.divider()

    st.markdown("**🛡️ Risk Levels Explained**")
    st.write(
        "**🛡️ Conservative (Safest):**\n"
        "- 2-7 trades per week\n"
        "- Very picky about what to buy\n"
        "- Keeps 20% cash as safety net\n"
        "- Only Canadian stocks & crypto\n"
        "- Best for: small accounts\n\n"
        "**⚖️ Balanced (Middle):**\n"
        "- 10-20 trades per week\n"
        "- Smart filters avoid bad buys\n"
        "- Keeps 10% cash in reserve\n"
        "- All markets available\n"
        "- Best for: medium accounts\n\n"
        "**🚀 Aggressive (Bold):**\n"
        "- Trades at every opportunity\n"
        "- Uses only the 5/10 rule\n"
        "- Keeps 5% cash\n"
        "- Maximum activity\n"
        "- Best for: large accounts"
    )

    st.divider()

    st.markdown("**⏰ When does it trade?**")
    st.write(
        "- Monday to Friday only\n"
        "- 9:30 AM to 4:00 PM (New York)\n"
        "- Checks prices every 15 minutes\n"
        "- Watches news 24/7"
    )

    st.divider()

    st.markdown("**💡 Pro Tips**")
    st.write(
        "- The AI explains WHY for every trade — click the arrow\n"
        "- Change risk level anytime — updates within 15 min\n"
        "- Download trade history as a spreadsheet\n"
        "- Check the Charts page for visual insights\n"
        "- This is practice money — perfect for learning"
    )

    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. No real money is used. Nothing here is financial advice. Past results do not guarantee future performance.</div>', unsafe_allow_html=True)

# ==================== NO DATA YET ====================

if not scenarios and not snapshots:
    st.title("🤖 AI Intelligent Trader")
    st.info("""
    ### Your AI Trading Assistant is setting up...

    Soon you'll see:
    - 🧪 **Your test accounts** running side by side
    - 💰 **Real-time equity** for each account
    - 📋 **Every trade explained** in plain English
    - 🧠 **Letta AI** learning from every outcome

    *Check back after the first trading cycle — usually within 15 minutes during market hours.*
    """)
    st.stop()

# ==================== HEADER ====================

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🤖 AI Intelligent Trader")
    st.caption("Self-learning AI that gets smarter with every trade.")
with col2:
    st.markdown('<span class="status-pill-green">🟢 Live</span>', unsafe_allow_html=True)
    st.caption(f"Updated: {datetime.now().strftime('%b %d, %I:%M %p')}")

# ==================== WHAT IS THIS? ====================

with st.expander("🤔 What am I looking at? (Click to learn more)", expanded=False):
    st.markdown("""
    ### Welcome to your AI Intelligent Trader!
    
    **In plain English, here's what's happening behind the scenes:**
    
    - You have **virtual accounts** with different amounts of play money — like having multiple practice portfolios
    - An **AI brain** watches the stock market 24/7, reading news and analyzing numbers faster than any human could
    - Each account has a **risk level** you can change — Conservative plays it safe, Aggressive goes for maximum action
    - Every single trade is **explained in simple words** — click any trade to see exactly why the AI made that decision
    - And here's the really cool part: **the AI learns from its own results.** Every time a trade works or doesn't work, the Letta Memory system remembers it and adjusts future decisions
    
    **Think of it like this:** The AI is a student. Every trade is a lesson. Over time, it gets better and better at knowing when to buy and sell.
    
    **The goal:** Find the perfect combination of account size and risk level that works best for you — all with zero real money at risk.
    """)

st.divider()

# ==================== THE LEARNING AI EXPLAINED ====================

st.markdown('<p class="section-title">🧠 The Self-Learning AI — How It Gets Smarter</p>', unsafe_allow_html=True)

col_learn1, col_learn2, col_learn3 = st.columns(3)

with col_learn1:
    st.markdown("""
    <div class="highlight-card">
    <b>📝 Step 1: Remember</b><br><br>
    Every time the AI makes a trade, it records everything — the price, the market conditions, the news, even the "fear level" (VIX).<br><br>
    <i>Like a trader keeping a detailed journal of every decision.</i>
    </div>
    """, unsafe_allow_html=True)

with col_learn2:
    st.markdown("""
    <div class="highlight-card">
    <b>🔍 Step 2: Analyze</b><br><br>
    After 24 hours, the AI checks: "Was that a good trade? Did I make money or lose money?" It looks for patterns.<br><br>
    <i>Like reviewing your homework to see what you got right and wrong.</i>
    </div>
    """, unsafe_allow_html=True)

with col_learn3:
    st.markdown("""
    <div class="highlight-card">
    <b>💡 Step 3: Learn</b><br><br>
    The AI creates new rules from what it learned. "Last time VIX was high and RSI was low, buying worked. Let's do that again!"<br><br>
    <i>Like getting smarter every single day, automatically.</i>
    </div>
    """, unsafe_allow_html=True)

# Show learning progress
rules_count = len(learned_rules)
trades_remembered = len([t for t in trades]) if trades else 0

col_rules, col_trades, col_accuracy = st.columns(3)
with col_rules:
    st.metric("🧠 Learned Rules", rules_count, help="Rules the AI created from its own trading experience. More rules = smarter AI.")
with col_trades:
    st.metric("📝 Trades Remembered", trades_remembered, help="Every trade is stored in the AI's memory for future learning.")
with col_accuracy:
    acc_val = accuracy.get('accuracy', 0)
    total_checked = accuracy.get('total_checked', 0)
    st.metric("🎯 Prediction Accuracy", f"{acc_val}%" if total_checked else "Learning...", help=f"Based on {total_checked} predictions. Above 50% means the AI is better than random chance.")

if learned_rules:
    with st.expander("🧠 See what the AI has learned so far"):
        for rule in learned_rules[:10]:
            conf = rule.get("confidence", 0)
            conf_color = "green" if conf > 0.7 else "orange" if conf > 0.5 else "red"
            st.markdown(f"• **{rule.get('description', '')}** — <span style='color:{conf_color}'>{conf:.0%} confidence</span> (seen {rule.get('times_seen', 0)} times, worked {rule.get('times_worked', 0)} times)", unsafe_allow_html=True)

st.divider()

# ==================== SCENARIO SIMULATOR ====================

st.markdown('<p class="section-title">🧪 Your Test Accounts</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Each account runs independently with its own risk level. Change the risk anytime — it updates within 15 minutes.</p>', unsafe_allow_html=True)

latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

risk_options = ["conservative", "balanced", "aggressive"]
risk_emoji = {"conservative": "🛡️", "balanced": "⚖️", "aggressive": "🚀"}
risk_explanations = {
    "conservative": "Safest — few trades, strict filters, 20% cash reserve",
    "balanced": "Middle ground — regular trades, smart filters, 10% cash",
    "aggressive": "Maximum action — trades at every opportunity, 5% cash"
}

if scenarios_config:
    cols = st.columns(len(scenarios_config))
    for i, sc in enumerate(scenarios_config):
        sid = sc["id"]
        with cols[i]:
            current_risk = sc.get("risk_profile", "balanced")
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

    st.caption("💡 **Tip:** Click any dropdown above to change the risk level. The change takes effect on the next trading cycle (within 15 minutes during market hours). Try different combinations!")
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
                    st.write(f"**Fee charged:** ${fees:.2f} CAD (This is the 1.5% fee for converting Canadian dollars to US dollars when trading US stocks)")
        
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
    st.write("**What to expect:** When the AI finds a good opportunity, you'll see green (buy) or red (sell) entries here with clear explanations of why each trade was made.")

st.divider()

# ==================== HOW THE AI WORKS ====================

st.markdown('<p class="section-title">🧠 How the AI Makes Decisions</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">A behind-the-scenes look at the four-step process that runs 24/7.</p>', unsafe_allow_html=True)

col_how1, col_how2 = st.columns(2)

with col_how1:
    st.markdown("""
    <div class="card">
    <b>📊 Step 1: Watch the Market</b><br><br>
    The system monitors 31 different investments — US stocks, Canadian stocks, ETFs, and crypto — using 4 different data sources (Finnhub, Alpha Vantage, Coinbase, and Yahoo Finance) to get the most accurate prices and breaking news in real time.<br><br>
    <i>Like having a team of analysts watching the market 24/7 without sleep.</i>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
    <b>🧮 Step 2: Do the Math</b><br><br>
    The 5/10 Rule looks at the last 2 weeks of price data. If something dropped more than 3%, it considers buying (a "dip"). If something rose more than 5%, it considers selling (taking profit). Extra filters like RSI and ATR make sure it's not catching a "falling knife" — buying something that keeps dropping.<br><br>
    <i>Math keeps emotions out of the decision. No panic selling. No FOMO buying.</i>
    </div>
    """, unsafe_allow_html=True)

with col_how2:
    st.markdown("""
    <div class="card">
    <b>🧠 Step 3: Ask the AI</b><br><br>
    <b>DeepSeek AI</b> reads the news and analyzes the numbers — like a tireless research analyst who never misses a detail. For really big events (like a market crash), <b>Claude AI</b> double-checks as a second opinion. Then <b>Letta Memory</b> checks: "Have we seen this situation before? What happened last time?"<br><br>
    <i>Three AI systems working together, each with a different specialty — but math always has the final say.</i>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
    <b>✅ Step 4: Execute (or Don't)</b><br><br>
    If all filters pass, the trade happens automatically. If any filter says no, the trade is skipped. Then, after 24 hours, the AI checks the result and <b>learns from the outcome</b>. Over time, it creates its own rules — "When VIX is high and RSI is low, buying usually works" — and applies them to future decisions.<br><br>
    <i>Every trade is a lesson. The system gets smarter every single day.</i>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ==================== THE AI TEAM ====================

st.markdown('<p class="section-title">🤖 Meet the AI Team</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Three specialized AI systems working together to make smarter trading decisions.</p>', unsafe_allow_html=True)

col_team1, col_team2, col_team3 = st.columns(3)

with col_team1:
    st.markdown("""
    <div class="card">
    <b>🔬 DeepSeek AI</b><br>
    <i>The Research Analyst</i><br><br>
    • Reads financial news 24/7<br>
    • Analyzes price patterns<br>
    • Calculates statistical significance<br>
    • Spots trends before humans do<br><br>
    <i>"The numbers say this dip is temporary — the company just had a great earnings report."</i>
    </div>
    """, unsafe_allow_html=True)

with col_team2:
    st.markdown("""
    <div class="card">
    <b>🧠 Claude AI</b><br>
    <i>The Senior Advisor</i><br><br>
    • Only called for big events<br>
    • Analyzes crowd psychology<br>
    • Detects panic and euphoria<br>
    • Provides second opinion<br><br>
    <i>"The crowd is panicking. This looks like capitulation. Wait before buying."</i>
    </div>
    """, unsafe_allow_html=True)

with col_team3:
    st.markdown("""
    <div class="card">
    <b>💡 Letta Memory</b><br>
    <i>The Learning Engine</i><br><br>
    • Remembers every trade<br>
    • Learns from wins AND losses<br>
    • Creates its own rules<br>
    • Gets smarter every cycle<br><br>
    <i>"Last 3 times VIX was above 30 and RSI was below 30, buying worked. Let's do it again."</i>
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.markdown("""
<div style="text-align:center; padding: 20px; margin-top: 10px;">
    <hr style="border-color: rgba(127,127,127,0.2);">
    <p style="color: #666; font-size: 12px;">© 2026 <b>OnlySolutions Inc.</b> — All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
st.caption(f"AI Intelligent Trader v2.3 · Running 24/7 on Railway · {len(snapshots)} snapshots · {len(trades)} trades · {rules_count} learned rules · Paper trading simulation only · Not financial advice")