"""
Trade Lab Dashboard — Professional yet simple enough for anyone.
Shows: Your Money, Today's Activity, AI Accuracy, Positions, Fees.
Run: streamlit run dashboard/app.py
Reads logs from GitHub for 24/7 access anywhere.
"""

import streamlit as st
import pandas as pd
import json
import os
import subprocess
from datetime import datetime, timedelta
import plotly.graph_objects as go

# ==================== PAGE SETUP ====================

st.set_page_config(
    page_title="Trade Lab — Your AI Trading Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== STYLE ====================

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .section-title { font-size: 21px; font-weight: 700; margin-top: 8px; margin-bottom: 2px; }
    .section-subtitle { font-size: 13px; color: #9aa0a6; margin-bottom: 14px; }
    .explanation { font-size: 13px; color: #888; font-style: italic; }
    .card {
        background: rgba(127,127,127,0.06);
        border: 1px solid rgba(127,127,127,0.15);
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }
    .status-pill-green {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        background: rgba(0,200,83,0.15);
        color: #00c853;
    }
    .disclaimer-box {
        background: rgba(255,193,7,0.08);
        border: 1px solid rgba(255,193,7,0.35);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 12.5px;
        color: #b58a00;
        margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==================== HELPERS ====================

def safe_pct(num, den):
    return round(num / den * 100, 2) if den else 0.0

def fmt_money(x, currency="CAD"):
    try: return f"${x:,.2f} {currency}"
    except: return f"$0.00 {currency}"

def time_ago(ts_str):
    try:
        ts = pd.to_datetime(ts_str)
        secs = (datetime.now() - ts.to_pydatetime().replace(tzinfo=None)).total_seconds()
        if secs < 60: return "just now"
        if secs < 3600: return f"{int(secs//60)} min ago"
        if secs < 86400: return f"{int(secs//3600)} hr ago"
        return f"{int(secs//86400)} day(s) ago"
    except: return ""

# ==================== LOAD DATA FROM GITHUB ====================

@st.cache_data(ttl=60)
def load_data():
    # Pull latest logs from GitHub
    try:
        subprocess.run(["git", "pull", "origin", "main"], capture_output=True, timeout=10)
    except: pass

    snapshots, trades, accuracy = [], [], {"accuracy": 0, "total_checked": 0}

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
    return snapshots, trades, accuracy

snapshots, trades, accuracy = load_data()

# ==================== SIDEBAR ====================

with st.sidebar:
    st.markdown("### 🤖 Trade Lab")
    st.caption("Your AI-powered trading assistant")
    st.divider()
    st.markdown("**How to read this dashboard**")
    st.write("- 💼 Portfolio — total value, profit/loss, cash\n- 📈 Growth chart — account over time\n- 📦 Holdings — stocks you own\n- 📋 Activity — every trade and why\n- 💰 Fees — currency costs\n- 🧠 About AI — how decisions are made")
    st.divider()
    lookback_days = st.selectbox("Chart range", ["7 days", "30 days", "90 days", "All time"], index=3)
    st.divider()
    st.markdown('<div class="disclaimer-box">⚠️ Paper trading simulation. Not financial advice. Past results do not guarantee future performance.</div>', unsafe_allow_html=True)

# ==================== NO DATA ====================

if not snapshots:
    st.title("🤖 Trade Lab")
    st.info("### Your AI Trading Assistant is setting up...\n\nThis dashboard will show your portfolio, trades, AI accuracy, and more — all in plain English.\n\n*Check back after the first trading cycle.*")
    st.stop()

# ==================== HEADER ====================

latest = snapshots[-1]
initial = snapshots[0].get('equity_cad', 100000) if snapshots else 100000
pnl = latest.get('equity_cad', 0) - initial

col1, col2 = st.columns([3, 1])
col1.title("🤖 Trade Lab")
col1.caption("Your AI-Powered Trading Assistant — plain-English view")
col2.markdown('<span class="status-pill-green">🟢 Active</span>', unsafe_allow_html=True)
col2.caption(f"Updated: {datetime.now().strftime('%b %d, %I:%M %p')}")

st.divider()

# ==================== TOP METRICS ====================

st.markdown('<p class="section-title">💼 Your Portfolio</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Everything you own, how it\'s performing, and what\'s available to invest.</p>', unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Value", fmt_money(latest.get('equity_cad', 0)))
color = "normal" if pnl >= 0 else "inverse"
m2.metric("Profit / Loss", fmt_money(pnl), delta=f"{safe_pct(pnl, initial):+.2f}%", delta_color=color)
m3.metric("Stocks Owned", latest.get('positions_count', 0))
acc = accuracy.get('accuracy', 0)
total_c = accuracy.get('total_checked', 0)
m4.metric("AI Accuracy", f"{acc}%" if total_c else "Collecting data...")

cash = latest.get('cash_cad', 0)
st.metric("Cash Available", fmt_money(cash), help=f"About {safe_pct(cash, latest.get('equity_cad', 1))}% of your portfolio — ready to invest when the AI spots an opportunity.")

st.divider()

# ==================== EQUITY CHART ====================

st.markdown('<p class="section-title">📈 How Your Money Has Grown</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">The dashed line is your starting amount. Above it = you\'re making money.</p>', unsafe_allow_html=True)

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
    c1, c2, c3 = st.columns(3)
    c1.caption(f"📈 Highest: **{fmt_money(df['equity_cad'].max())}**")
    c2.caption(f"📉 Lowest: **{fmt_money(df['equity_cad'].min())}**")
    c3.caption(f"📅 Snapshots: **{len(df)}**")

st.divider()

# ==================== POSITIONS & TRADES ====================

left, right = st.columns(2)

with left:
    st.markdown('<p class="section-title">📦 Stocks You Own</p>', unsafe_allow_html=True)
    st.markdown('<p class="explanation">🔺 = profitable, 🔻 = currently down</p>', unsafe_allow_html=True)
    positions = latest.get('positions', {})
    if positions:
        rows = []
        for s, p in positions.items():
            pnl_v = p.get('unrealized_pnl_cad', 0)
            rows.append({"Stock": f"{'🔺' if pnl_v > 0 else '🔻' if pnl_v < 0 else '➖'} {s}", "Shares": f"{p.get('quantity', 0):.4f}", "Paid": f"${p.get('avg_cost_usd', 0):.2f}", "Worth": f"${p.get('market_value_cad', 0):,.2f}", "P/L": f"${pnl_v:,.2f}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No positions yet. Waiting for the right moment.")

with right:
    st.markdown('<p class="section-title">📋 Recent Activity</p>', unsafe_allow_html=True)
    st.markdown('<p class="explanation">Every trade explained — what, when, and why.</p>', unsafe_allow_html=True)
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
            st.download_button("⬇️ Download History (CSV)", df_t.to_csv(index=False).encode("utf-8"), "trades.csv", "text/csv")
    else:
        st.info("No trades yet.")

st.divider()

# ==================== FEES & AI ====================

f1, f2 = st.columns(2)
with f1:
    st.markdown('<p class="section-title">💰 Fees Paid</p>', unsafe_allow_html=True)
    tf = sum(t.get('fees_cad', 0) for t in trades)
    st.metric("Total Fees", fmt_money(tf), help="Wealthsimple 1.5% FX fee on US stock buys & sells.")
with f2:
    st.markdown('<p class="section-title">🧠 About the AI</p>', unsafe_allow_html=True)
    st.markdown("""<div class="card"><b>How decisions are made:</b><br><br>1️⃣ <b>DeepSeek AI</b> scans news and numbers 24/7<br>2️⃣ <b>Claude AI</b> steps in for major events only<br>3️⃣ <b>5/10 Rule</b> — buy small on dips, sell small on rises<br>4️⃣ <b>RSI Filter</b> — avoids buying falling knives<br><br><i>Math rules make the final call. No impulsive decisions.</i></div>""", unsafe_allow_html=True)

st.divider()
st.caption(f"Trade Lab v1.1 · 24/7 on Railway · {len(snapshots)} snapshots · {len(trades)} trades · Paper trading only")