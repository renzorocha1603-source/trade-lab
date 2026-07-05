"""
Trade Lab Dashboard — Professional yet simple enough for anyone.
Password-protected. Shows: Portfolio, Scenarios, Activity, AI Accuracy, Positions, Fees.
Run: streamlit run dashboard/app.py
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
    .scenario-card { background: rgba(127,127,127,0.04); border: 1px solid rgba(127,127,127,0.1); border-radius: 12px; padding: 14px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ==================== AUTH ====================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("""<div class="card" style="text-align:center; padding:40px 32px; margin-top:80px;">
        <div style="font-size:56px;">🤖</div>
        <div style="font-size:24px;font-weight:700;">Trade Lab</div>
        <div style="font-size:14px;color:#9aa0a6;margin-bottom:28px;">Your AI-Powered Trading Assistant</div></div>""", unsafe_allow_html=True)
        password = st.text_input("Enter password", type="password", placeholder="••••••••••••")
        if st.button("🔓 Unlock Dashboard", use_container_width=True):
            if password == "Angelorea1$":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
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
    snapshots, trades, accuracy, scenarios = [], [], {"accuracy": 0, "total_checked": 0}, []
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
    return snapshots, trades, accuracy, scenarios

snapshots, trades, accuracy, scenarios = load_data()

# ==================== SIDEBAR ====================
with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    st.markdown("### 🤖 Trade Lab")
    st.divider()
    lookback_days = st.selectbox("Chart range", ["7 days", "30 days", "90 days", "All time"], index=3)
    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. Not financial advice.</div>', unsafe_allow_html=True)

if not snapshots:
    st.title("🤖 Trade Lab")
    st.info("### Setting up...\n\nCheck back after the first trading cycle.")
    st.stop()

# ==================== HEADER ====================
latest = snapshots[-1]
initial = snapshots[0].get('equity_cad', 100000)
pnl = latest.get('equity_cad', 0) - initial

col1, col2 = st.columns([3, 1])
col1.title("🤖 Trade Lab")
col1.caption("Your AI-Powered Trading Assistant")
col2.markdown('<span class="status-pill-green">🟢 Active</span>', unsafe_allow_html=True)
col2.caption(f"Updated: {datetime.now().strftime('%b %d, %I:%M %p')}")
st.divider()

# ==================== TOP METRICS ====================
st.markdown('<p class="section-title">💼 Your Portfolio</p>', unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Value", fmt_money(latest.get('equity_cad', 0)))
color = "normal" if pnl >= 0 else "inverse"
m2.metric("Profit / Loss", fmt_money(pnl), delta=f"{safe_pct(pnl, initial):+.2f}%", delta_color=color)
m3.metric("Positions", latest.get('positions_count', 0))
acc_val = accuracy.get('accuracy', 0)
m4.metric("AI Accuracy", f"{acc_val}%" if accuracy.get('total_checked') else "Collecting...")
st.metric("Cash Available", fmt_money(latest.get('cash_cad', 0)))
st.divider()

# ==================== SCENARIOS ====================
st.markdown('<p class="section-title">🧪 Scenario Simulator</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Same AI, different starting amounts. Real-time results.</p>', unsafe_allow_html=True)

if scenarios:
    latest_scenarios = {}
    for s in scenarios:
        sid = s.get("scenario_id", "unknown")
        if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
            latest_scenarios[sid] = s
    if latest_scenarios:
        cols = st.columns(len(latest_scenarios))
        for i, (sid, data) in enumerate(sorted(latest_scenarios.items())):
            with cols[i]:
                equity = data.get("equity_cad", 0)
                capital = data.get("starting_capital", 500)
                pnl_s = equity - capital
                pnl_pct_s = safe_pct(pnl_s, capital)
                c = "green" if pnl_s >= 0 else "red"
                st.markdown(f'<div class="scenario-card"><b>{data.get("name", sid)}</b><br><h4 style="color:{c};margin:4px 0">{fmt_money(equity)}</h4><small>{"↑" if pnl_s >= 0 else "↓"} {fmt_money(pnl_s)} ({pnl_pct_s:+.2f}%)</small><br><small>Trades: {data.get("trades", 0)} | Pos: {data.get("positions", 0)}</small></div>', unsafe_allow_html=True)
else:
    st.info("Scenario data will appear after the first trades. Check back soon!")
st.divider()

# ==================== CHART ====================
st.markdown('<p class="section-title">📈 Growth</p>', unsafe_allow_html=True)
df = pd.DataFrame(snapshots)
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if lookback_days != "All time":
        cutoff = df['timestamp'].max() - timedelta(days=int(lookback_days.split()[0]))
        df = df[df['timestamp'] >= cutoff]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['equity_cad'], mode='lines+markers', line=dict(color='#00c853', width=3), fill='tozeroy', fillcolor='rgba(0,200,83,0.1)'))
    fig.add_hline(y=initial, line_dash="dash", line_color="gray", annotation_text="Start")
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ==================== POSITIONS & TRADES ====================
left, right = st.columns(2)
with left:
    st.markdown('<p class="section-title">📦 Holdings</p>', unsafe_allow_html=True)
    positions = latest.get('positions', {})
    if positions:
        rows = []
        for s, p in positions.items():
            pnl_v = p.get('unrealized_pnl_cad', 0)
            rows.append({"Stock": f"{'🔺' if pnl_v > 0 else '🔻'} {s}", "Shares": f"{p.get('quantity', 0):.4f}", "Paid": f"${p.get('avg_cost_usd', 0):.2f}", "Worth": f"${p.get('market_value_cad', 0):,.2f}", "P/L": f"${pnl_v:,.2f}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No positions yet.")

with right:
    st.markdown('<p class="section-title">📋 Activity</p>', unsafe_allow_html=True)
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
                ai = " 🤖" if r.get('ai_modified') else ""
                with st.expander(f"{emoji} {r.get('action')} {r.get('quantity', 0):.4f} {r.get('symbol')} @ ${r.get('price_usd', 0):.2f}{ai}"):
                    st.write(f"**When:** {r.get('timestamp')} ({time_ago(r.get('timestamp'))})")
                    st.write(f"**Why:** {r.get('reason', '')[:300]}")
                    if r.get('fees_cad', 0) > 0: st.write(f"**Fee:** ${r['fees_cad']:.2f} CAD")
            st.download_button("⬇️ Download CSV", df_t.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
    else:
        st.info("No trades yet.")

st.divider()

# ==================== FEES & AI ====================
f1, f2 = st.columns(2)
with f1:
    st.markdown('<p class="section-title">💰 Fees</p>', unsafe_allow_html=True)
    tf = sum(t.get('fees_cad', 0) for t in trades)
    st.metric("Total Fees", fmt_money(tf))
with f2:
    st.markdown('<p class="section-title">🧠 About AI</p>', unsafe_allow_html=True)
    st.markdown("""<div class="card"><b>How it works:</b><br><br>1️⃣ <b>DeepSeek AI</b> scans news + technicals 24/7<br>2️⃣ <b>Claude AI</b> for extreme events only<br>3️⃣ <b>5/10 Rule + RSI + ATR</b> for entries<br>4️⃣ <b>Dynamic risk</b> adapts to market volatility<br><br><i>Math rules make the final call.</i></div>""", unsafe_allow_html=True)

st.divider()
st.caption(f"Trade Lab v2.1 · 24/7 on Railway · {len(snapshots)} snapshots · {len(trades)} trades · Paper trading only")