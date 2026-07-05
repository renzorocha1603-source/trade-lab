"""
Trade Lab Dashboard - Monitor your trading system.
Run with: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="Trade Lab", page_icon="🤖", layout="wide")
st.title("🤖 Trade Lab Dashboard")
st.caption("Real Data · Simulated Money · 5/10 Strategy + AI")

# Load data
@st.cache_data(ttl=30)
def load_data():
    snapshots, trades = [], []
    if os.path.exists("logs/portfolio_snapshots.json"):
        with open("logs/portfolio_snapshots.json") as f:
            snapshots = json.load(f)
    if os.path.exists("logs/trades.json"):
        with open("logs/trades.json") as f:
            trades = json.load(f)
    return snapshots, trades

snapshots, trades = load_data()

if not snapshots:
    st.warning("No data yet. Run main.py first!")
    st.stop()

df_snap = pd.DataFrame(snapshots)
df_snap['timestamp'] = pd.to_datetime(df_snap['timestamp'])
df_trades = pd.DataFrame(trades)
if not df_trades.empty:
    df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])

latest = df_snap.iloc[-1]
initial = df_snap.iloc[0]['equity_cad'] if len(df_snap) > 0 else 100000

# Top row metrics
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("💰 Equity (CAD)", f"${latest['equity_cad']:,.2f}")
with col2:
    pnl = latest['equity_cad'] - initial
    st.metric("📈 P&L", f"${pnl:,.2f}", delta=f"{(pnl/initial)*100:.2f}%")
with col3:
    st.metric("💵 Cash (CAD)", f"${latest['cash_cad']:,.2f}")
with col4:
    st.metric("📊 Positions", latest.get('positions_count', 0))
with col5:
    fx = latest.get('fx_rate', 1.35)
    st.metric("💱 USD/CAD", f"{fx:.4f}")

# Equity curve
st.subheader("Equity Curve (CAD)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_snap['timestamp'], y=df_snap['equity_cad'],
    mode='lines+markers', name='Portfolio', line=dict(color='green', width=2)))
fig.add_hline(y=initial, line_dash="dash", line_color="gray", annotation_text="Start")
fig.update_layout(xaxis_title="Date", yaxis_title="Equity (CAD)", hovermode='x unified')
st.plotly_chart(fig, use_container_width=True)

# Positions and Trades
c1, c2 = st.columns(2)
with c1:
    st.subheader("Open Positions")
    positions = latest.get('positions', {})
    if positions:
        pos_rows = []
        for sym, p in positions.items():
            pos_rows.append({
                "Symbol": sym,
                "Qty": p['quantity'],
                "Avg Cost USD": f"${p['avg_cost_usd']:.2f}",
                "Price USD": f"${p['current_price_usd']:.2f}",
                "Value CAD": f"${p['market_value_cad']:,.2f}",
                "P&L CAD": f"${p['unrealized_pnl_cad']:,.2f}"
            })
        st.dataframe(pd.DataFrame(pos_rows), use_container_width=True)
    else:
        st.info("No open positions")

with c2:
    st.subheader("Recent Trades")
    if not df_trades.empty:
        recent = df_trades.sort_values('timestamp', ascending=False).head(15)
        st.dataframe(recent[['timestamp', 'symbol', 'action', 'quantity', 'price_usd', 'ai_modified', 'fees_cad']],
            use_container_width=True)
    else:
        st.info("No trades yet")

# Fees summary
st.subheader("💰 Fee Breakdown")
total_fees = sum(t.get('fees_cad', 0) for t in trades)
total_trades_count = len(trades)
st.metric("Total FX Fees Paid (CAD)", f"${total_fees:,.2f}",
    help="Wealthsimple charges 1.5% FX fee on US stock buys AND sells")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Snapshots: {len(snapshots)} | Trades: {total_trades_count}")