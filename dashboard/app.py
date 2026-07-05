"""
AI Intelligent Trader Dashboard — Password-protected, 5 scenarios with risk selection.
Multi-user accounts with registration. Designed for anyone to understand.
Self-learning AI that improves from every trade.
Admin panel for user management on sidebar.
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
    .admin-card { background: rgba(255,152,0,0.08); border: 1px solid rgba(255,152,0,0.25); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ==================== INLINE AUTH SYSTEM ====================

class AuthSystem:
    def __init__(self):
        self.users_file = "users.json"
        self.users = []
        if os.path.exists(self.users_file):
            with open(self.users_file) as f:
                self.users = json.load(f).get("users", [])

    def _save(self):
        with open(self.users_file, "w") as f:
            json.dump({"users": self.users}, f, indent=2)

    def login(self, username, password):
        for u in self.users:
            if u["id"] == username and u["password"] == password:
                return u
        return None

    def register(self, username, password, name=""):
        for u in self.users:
            if u["id"] == username:
                return None
        new_user = {
            "id": username, "password": password,
            "name": name or username, "role": "user",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "scenarios": [
                {"id": f"{username}_500", "name": "Starter $500", "starting_capital_cad": 500, "monthly_deposit_cad": 0, "risk_profile": "conservative"},
                {"id": f"{username}_1k", "name": "Basic $1,000", "starting_capital_cad": 1000, "monthly_deposit_cad": 100, "risk_profile": "balanced"},
                {"id": f"{username}_5k", "name": "Growth $5,000", "starting_capital_cad": 5000, "monthly_deposit_cad": 250, "risk_profile": "balanced"}
            ]
        }
        self.users.append(new_user)
        self._save()
        return new_user

    def list_users(self):
        return [{"id": u["id"], "name": u["name"], "role": u["role"], "created": u["created"]} for u in self.users]

    def delete_user(self, username):
        for i, u in enumerate(self.users):
            if u["id"] == username:
                self.users.pop(i)
                self._save()
                return True
        return False

# ==================== AUTHENTICATION ====================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

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
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("🔓 Unlock Dashboard", use_container_width=True, key="login_btn"):
                auth = AuthSystem()
                user = auth.login(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

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
user = st.session_state.get("user", {})
is_admin = user.get("role") == "admin"

# ==================== SIDEBAR ====================

with st.sidebar:
    st.markdown(f"### 🤖 Welcome, {user.get('name', 'Trader')}!")
    st.caption(f"@{user.get('id', 'unknown')} · {user.get('role', 'user').title()}")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    st.divider()

    # ==================== ADMIN PANEL ====================
    if is_admin:
        with st.expander("🔧 Admin Panel", expanded=False):
            st.markdown("**Create New User**")
            admin_new_user = st.text_input("Username", key="admin_new_user")
            admin_new_pass = st.text_input("Password", type="password", key="admin_new_pass")
            admin_new_name = st.text_input("Name", key="admin_new_name")
            if st.button("➕ Create User", use_container_width=True):
                if len(admin_new_user) >= 3 and len(admin_new_pass) >= 4:
                    auth = AuthSystem()
                    new_u = auth.register(admin_new_user, admin_new_pass, admin_new_name)
                    if new_u:
                        st.success(f"User '{admin_new_user}' created!")
                    else:
                        st.error("Username taken.")
                else:
                    st.error("Username 3+ chars, password 4+ chars.")

            st.divider()
            st.markdown("**Existing Users**")
            auth = AuthSystem()
            all_users = auth.list_users()
            for u in all_users:
                col_u, col_d = st.columns([4, 1])
                with col_u:
                    st.caption(f"• {u['name']} (@{u['id']}) — {u['role']}")
                with col_d:
                    if u['id'] != 'renzochiara':
                        if st.button("🗑️", key=f"del_{u['id']}"):
                            auth.delete_user(u['id'])
                            st.rerun()

        st.divider()

    st.markdown("**📖 How to read this page**")
    st.write(
        "- 🧪 **Top cards** = your test accounts\n"
        "- 💰 **Numbers** = how much money\n"
        "- 📈 **Percentage** = profit or loss\n"
        "- 📋 **Activity** = every trade explained\n"
        "- 📊 **Charts page** = visual analytics\n"
        "- 🧠 **Letta AI** = learns from every trade"
    )

    st.divider()

    st.markdown("**🛡️ Risk Levels**")
    st.write(
        "**🛡️ Conservative:**\n2-7 trades/week, 20% cash, TSX/crypto only\n\n"
        "**⚖️ Balanced:**\n10-20 trades/week, 10% cash, all markets\n\n"
        "**🚀 Aggressive:**\nUnlimited trades, 5% cash, 5/10 rule only"
    )

    st.divider()

    st.markdown("**⏰ Market Hours**")
    st.write("Mon-Fri · 9:30 AM - 4:00 PM EST · Checks every 15 min")

    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. No real money. Not financial advice.</div>', unsafe_allow_html=True)

# ==================== MAIN CONTENT ====================

if not scenarios and not snapshots:
    st.title("🤖 AI Intelligent Trader")
    st.info("""
    ### Your AI Trading Assistant is setting up...

    Soon you'll see:
    - 🧪 **Your test accounts** running
    - 💰 **Real-time equity** for each
    - 📋 **Every trade explained**
    - 🧠 **Letta AI** learning from outcomes

    *Check back after the first trading cycle.*
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

# ==================== WHAT IS THIS ====================

with st.expander("🤔 What am I looking at? (Click to learn more)", expanded=False):
    st.markdown("""
    ### Welcome to your AI Intelligent Trader!
    
    - You have **virtual accounts** with play money
    - An **AI brain** watches the market 24/7
    - Each account has a **risk level** you can change
    - Every trade is **explained in simple words**
    - **Letta Memory** learns from every trade outcome
    
    **The goal:** Find the best combination of account size and risk level — with zero real money at risk.
    """)

st.divider()

# ==================== THE LEARNING AI ====================

st.markdown('<p class="section-title">🧠 The Self-Learning AI — How It Gets Smarter</p>', unsafe_allow_html=True)

col_learn1, col_learn2, col_learn3 = st.columns(3)
with col_learn1:
    st.markdown("""<div class="highlight-card"><b>📝 Step 1: Remember</b><br><br>Every trade is recorded — price, market conditions, news, fear level (VIX).<br><br><i>Like a trader keeping a detailed journal.</i></div>""", unsafe_allow_html=True)
with col_learn2:
    st.markdown("""<div class="highlight-card"><b>🔍 Step 2: Analyze</b><br><br>After 24 hours: "Was that a good trade?" It looks for patterns.<br><br><i>Like reviewing homework to see what worked.</i></div>""", unsafe_allow_html=True)
with col_learn3:
    st.markdown("""<div class="highlight-card"><b>💡 Step 3: Learn</b><br><br>Creates new rules: "Last time VIX was high and RSI was low, buying worked."<br><br><i>Getting smarter every single day.</i></div>""", unsafe_allow_html=True)

rules_count = len(learned_rules)
trades_remembered = len(trades) if trades else 0
col_rules, col_trades, col_accuracy = st.columns(3)
col_rules.metric("🧠 Learned Rules", rules_count)
col_trades.metric("📝 Trades Remembered", trades_remembered)
acc_val = accuracy.get('accuracy', 0)
total_checked = accuracy.get('total_checked', 0)
col_accuracy.metric("🎯 AI Accuracy", f"{acc_val}%" if total_checked else "Learning...")

if learned_rules:
    with st.expander("🧠 See what the AI has learned so far"):
        for rule in learned_rules[:10]:
            conf = rule.get("confidence", 0)
            conf_color = "green" if conf > 0.7 else "orange" if conf > 0.5 else "red"
            st.markdown(f"• **{rule.get('description', '')}** — <span style='color:{conf_color}'>{conf:.0%} confidence</span> (seen {rule.get('times_seen', 0)}x, worked {rule.get('times_worked', 0)}x)", unsafe_allow_html=True)

st.divider()

# ==================== SCENARIOS ====================

st.markdown('<p class="section-title">🧪 Your Test Accounts</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Each account runs independently. Change risk anytime — updates within 15 minutes.</p>', unsafe_allow_html=True)

latest_scenarios = {}
for s in scenarios:
    sid = s.get("scenario_id", "unknown")
    if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
        latest_scenarios[sid] = s

risk_options = ["conservative", "balanced", "aggressive"]
risk_emoji = {"conservative": "🛡️", "balanced": "⚖️", "aggressive": "🚀"}

if scenarios_config:
    cols = st.columns(len(scenarios_config))
    for i, sc in enumerate(scenarios_config):
        sid = sc["id"]
        with cols[i]:
            current_risk = sc.get("risk_profile", "balanced")
            st.caption(f"**{sc['name']}**")
            new_risk = st.selectbox("Risk", risk_options, index=risk_options.index(current_risk) if current_risk in risk_options else 1, key=f"risk_{sid}", format_func=lambda x: f"{risk_emoji.get(x, '')} {x.title()}")
            if new_risk != current_risk:
                sc["risk_profile"] = new_risk
                if save_scenarios_to_github(scenarios_config):
                    st.success(f"✅ {new_risk}!")
                    st.rerun()
            data = latest_scenarios.get(sid, {})
            equity = data.get("equity_cad", sc.get("starting_capital_cad", 0))
            capital = data.get("starting_capital", sc.get("starting_capital_cad", 0))
            pnl_s = equity - capital
            pnl_pct_s = safe_pct(pnl_s, capital)
            c = "green" if pnl_s >= 0 else "red"
            st.markdown(f"""<div class="scenario-card"><b>{fmt_money(capital)}</b><br><h3 style="color:{c};margin:6px 0;">{fmt_money(equity)}</h3><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>📊 {data.get('trades', 0)} trades | 📦 {data.get('positions', 0)} holdings</small><br><small>{risk_emoji.get(current_risk, '')} {current_risk.title()}</small></div>""", unsafe_allow_html=True)
    st.caption("💡 Change risk anytime — updates on next cycle.")
else:
    st.info("Loading...")

st.divider()

# ==================== RECENT TRADES ====================

st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Every trade explained in plain English.</p>', unsafe_allow_html=True)

if trades:
    df_t = pd.DataFrame(trades)
    if 'timestamp' in df_t.columns:
        df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
        df_t = df_t.sort_values('timestamp', ascending=False)
        filt = st.radio("Show", ["All", "Buys 📈", "Sells 📉"], horizontal=True, label_visibility="collapsed")
        if "Buys" in filt: df_t = df_t[df_t['action'] == "BUY"]
        elif "Sells" in filt: df_t = df_t[df_t['action'] == "SELL"]
        for _, r in df_t.head(30).iterrows():
            action = r.get('action', '')
            emoji = "🟢 Bought" if action == "BUY" else "🔴 Sold"
            ai_tag = " (AI)" if r.get('ai_modified') else ""
            with st.expander(f"{emoji} {r.get('quantity', 0):.4f} {r.get('symbol')} @ ${r.get('price_usd', 0):.2f}{ai_tag}"):
                st.write(f"**When:** {r.get('timestamp')} ({time_ago(r.get('timestamp'))})")
                st.write(f"**Why:** {r.get('reason', '5/10 rule triggered')[:300]}")
                if r.get('fees_cad', 0) > 0: st.write(f"**Fee:** ${r['fees_cad']:.2f} CAD")
        st.download_button("⬇️ Download CSV", df_t.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
else:
    st.info("No trades yet. The AI is watching the market.")

st.divider()

# ==================== HOW IT WORKS ====================

st.markdown('<p class="section-title">🧠 How the AI Makes Decisions</p>', unsafe_allow_html=True)

col_h1, col_h2 = st.columns(2)
with col_h1:
    st.markdown("""<div class="card"><b>📊 Step 1: Watch</b><br><br>Monitors 31 investments across 4 data sources — 24/7.</div>""", unsafe_allow_html=True)
    st.markdown("""<div class="card"><b>🧮 Step 2: Math</b><br><br>5/10 Rule + RSI + ATR filters — no emotions, just numbers.</div>""", unsafe_allow_html=True)
with col_h2:
    st.markdown("""<div class="card"><b>🧠 Step 3: AI Analysis</b><br><br>DeepSeek reads news, Claude checks big events, Letta checks past patterns.</div>""", unsafe_allow_html=True)
    st.markdown("""<div class="card"><b>✅ Step 4: Execute</b><br><br>All filters pass = trade. Any filter says no = skip. Learns from every outcome.</div>""", unsafe_allow_html=True)

st.divider()

# ==================== AI TEAM ====================

st.markdown('<p class="section-title">🤖 Meet the AI Team</p>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown("""<div class="card"><b>🔬 DeepSeek</b><br><i>Research Analyst</i><br><br>Reads news, analyzes patterns, calculates probabilities.</div>""", unsafe_allow_html=True)
c2.markdown("""<div class="card"><b>🧠 Claude</b><br><i>Senior Advisor</i><br><br>Called for big events. Detects panic and euphoria.</div>""", unsafe_allow_html=True)
c3.markdown("""<div class="card"><b>💡 Letta</b><br><i>Learning Engine</i><br><br>Remembers every trade. Creates rules. Gets smarter daily.</div>""", unsafe_allow_html=True)

st.divider()

# ==================== FOOTER ====================

st.markdown("""
<div style="text-align:center; padding: 20px; margin-top: 10px;">
    <hr style="border-color: rgba(127,127,127,0.2);">
    <p style="color: #666; font-size: 12px;">© 2026 <b>OnlySolutions Inc.</b> — All rights reserved.</p>
</div>
""", unsafe_allow_html=True)

st.caption(f"AI Intelligent Trader v2.3 · 24/7 on Railway · {len(snapshots)} snapshots · {len(trades)} trades · {rules_count} learned rules · Paper trading only · Not financial advice")