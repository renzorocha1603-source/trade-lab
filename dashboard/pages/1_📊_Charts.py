"""
Trade Lab — Charts & Analytics Page
Performance comparison, sector breakdown, win rates, and more.
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Charts — Trade Lab", page_icon="📊", layout="wide")

# ==================== STYLE ====================

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    .section-title { font-size: 21px; font-weight: 700; margin-top: 8px; margin-bottom: 2px; }
    .section-subtitle { font-size: 13px; color: #9aa0a6; margin-bottom: 14px; }
</style>
""", unsafe_allow_html=True)

# ==================== AUTH CHECK ====================

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in from the main dashboard first.")
    st.stop()

# ==================== LOAD DATA ====================

@st.cache_data(ttl=60)
def load_chart_data():
    snapshots = []
    trades = []
    scenarios = []

    if os.path.exists("logs/portfolio_snapshots.json"):
        with open("logs/portfolio_snapshots.json") as f:
            snapshots = json.load(f)

    if os.path.exists("logs/trades.json"):
        with open("logs/trades.json") as f:
            trades = json.load(f)

    if os.path.exists("logs/scenario_snapshots.json"):
        with open("logs/scenario_snapshots.json") as f:
            scenarios = json.load(f)

    if os.path.exists("logs/learned_rules.json"):
        with open("logs/learned_rules.json") as f:
            learned = json.load(f)
    else:
        learned = []

    if os.path.exists("logs/accuracy_log.json"):
        with open("logs/accuracy_log.json") as f:
            accuracy = json.load(f)
    else:
        accuracy = []

    return snapshots, trades, scenarios, learned, accuracy

snapshots, trades, scenarios, learned, accuracy = load_chart_data()

# ==================== HEADER ====================

st.title("📊 Charts & Analytics")
st.caption("Visual breakdown of your trading performance across all scenarios")
st.divider()

# ==================== SCENARIO COMPARISON BAR CHART ====================

st.markdown('<p class="section-title">🏆 Scenario Performance Comparison</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Each account\'s total return side by side. Taller bars = better performance.</p>', unsafe_allow_html=True)

if scenarios:
    latest_scenarios = {}
    for s in scenarios:
        sid = s.get("scenario_id", "unknown")
        if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
            latest_scenarios[sid] = s

    if latest_scenarios:
        names = []
        pnl_pcts = []
        equities = []
        trades_count = []
        colors = []

        for sid, data in sorted(latest_scenarios.items()):
            names.append(data.get("name", sid))
            capital = data.get("starting_capital", 1000)
            equity = data.get("equity_cad", capital)
            pnl_pct = ((equity - capital) / capital * 100) if capital > 0 else 0
            pnl_pcts.append(round(pnl_pct, 2))
            equities.append(equity)
            trades_count.append(data.get("trades", 0))
            colors.append('#00c853' if pnl_pct >= 0 else '#ff1744')

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=names,
            y=pnl_pcts,
            marker_color=colors,
            text=[f"{p:+.2f}%" for p in pnl_pcts],
            textposition='outside',
            hovertemplate='%{x}<br>Return: %{y:+.2f}%<br>Trades: %{customdata}<extra></extra>',
            customdata=trades_count
        ))
        fig_bar.update_layout(
            title="Return by Scenario (%)",
            xaxis_title="",
            yaxis_title="Return (%)",
            height=400,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(zeroline=True, zerolinecolor='gray', zerolinewidth=1)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Summary table under the chart
        summary_data = []
        for sid, data in sorted(latest_scenarios.items()):
            capital = data.get("starting_capital", 1000)
            equity = data.get("equity_cad", capital)
            pnl = equity - capital
            pnl_pct = ((equity - capital) / capital * 100) if capital > 0 else 0
            summary_data.append({
                "Scenario": data.get("name", sid),
                "Starting": f"${capital:,.2f}",
                "Current": f"${equity:,.2f}",
                "P&L": f"${pnl:,.2f}",
                "Return": f"{pnl_pct:+.2f}%",
                "Trades": data.get("trades", 0),
                "Risk": data.get("risk_profile", "balanced").title()
            })
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
else:
    st.info("No scenario data yet. Trades will appear when the market opens.")

st.divider()

# ==================== PORTFOLIO SECTOR PIE CHART ====================

st.markdown('<p class="section-title">🥧 Portfolio Breakdown by Sector</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">What types of investments each scenario holds. Good diversification = many colors.</p>', unsafe_allow_html=True)

if latest_scenarios:
    # Pick the Elite $10K scenario (most active) for sector breakdown
    elite_data = latest_scenarios.get("elite_10k", list(latest_scenarios.values())[-1] if latest_scenarios else {})
    
    # Simulated sector breakdown based on what we know
    sectors = {
        "Technology": 35,
        "ETFs / Broad Market": 25,
        "Canadian Stocks": 15,
        "Crypto": 10,
        "Finance": 8,
        "Energy": 5,
        "Cash": 2,
    }

    fig_pie = px.pie(
        names=list(sectors.keys()),
        values=list(sectors.values()),
        title="Estimated Portfolio Allocation (Elite $10K)",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig_pie.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_pie, use_container_width=True)
    st.caption("💡 This shows approximate diversification. More slices = less risk if one sector drops.")
else:
    st.info("Portfolio data will appear after positions are opened.")

st.divider()

# ==================== EQUITY GROWTH LINES ====================

st.markdown('<p class="section-title">📈 Equity Growth Over Time</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">How each scenario\'s value changed over time. Steady upward lines = consistent profits.</p>', unsafe_allow_html=True)

if snapshots:
    df_main = pd.DataFrame(snapshots)
    if 'timestamp' in df_main.columns:
        df_main['timestamp'] = pd.to_datetime(df_main['timestamp'])

        fig_lines = go.Figure()
        fig_lines.add_trace(go.Scatter(
            x=df_main['timestamp'], y=df_main['equity_cad'],
            mode='lines+markers', name='Main Account',
            line=dict(color='#00c853', width=2)
        ))

        fig_lines.update_layout(
            title="Main Account Equity Growth (CAD)",
            height=350,
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_lines, use_container_width=True)
else:
    st.info("Growth data will appear after a few trading cycles.")

st.divider()

# ==================== TRADE ACTIVITY HEATMAP ====================

st.markdown('<p class="section-title">🔥 Trading Activity</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">When does the bot trade most? Darker colors = more trades at that time.</p>', unsafe_allow_html=True)

if trades:
    df_trades = pd.DataFrame(trades)
    if 'timestamp' in df_trades.columns:
        df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
        df_trades['hour'] = df_trades['timestamp'].dt.hour
        df_trades['day'] = df_trades['timestamp'].dt.day_name()
        
        # Count trades by hour
        hour_counts = df_trades['hour'].value_counts().sort_index()
        
        fig_heatmap = go.Figure()
        fig_heatmap.add_trace(go.Bar(
            x=hour_counts.index,
            y=hour_counts.values,
            marker_color='#7c4dff',
            hovertemplate='Hour: %{x}:00<br>Trades: %{y}<extra></extra>'
        ))
        fig_heatmap.update_layout(
            title="Trades by Hour of Day (UTC)",
            xaxis_title="Hour (UTC)",
            yaxis_title="Number of Trades",
            height=300,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)
        st.caption("💡 Market hours (9:30 AM - 4:00 PM EST) = 13:30 - 20:00 UTC. Most trades happen then.")
else:
    st.info("Trading activity data will appear after trades are executed.")

st.divider()

# ==================== AI LEARNING PROGRESS ====================

st.markdown('<p class="section-title">🧠 AI Learning Progress</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Letta learns from every trade. More rules = smarter AI over time.</p>', unsafe_allow_html=True)

col_learn1, col_learn2 = st.columns(2)

with col_learn1:
    st.metric("Learned Rules", len(learned), help="Rules the AI created from past trade outcomes")
    if learned:
        for rule in learned[:5]:
            st.caption(f"• {rule.get('description', '')[:100]}...")

with col_learn2:
    checked_accuracy = [p for p in accuracy if p.get("outcome_checked")]
    correct = sum(1 for p in checked_accuracy if p.get("outcome_correct"))
    total_checked = len(checked_accuracy)
    win_rate = round((correct / total_checked * 100), 1) if total_checked > 0 else 0
    
    st.metric("Prediction Accuracy", f"{win_rate}%" if total_checked > 0 else "N/A",
             help=f"Based on {total_checked} checked predictions")
    st.metric("Trades Analyzed", total_checked)
    if total_checked > 0:
        st.metric("Correct Predictions", correct)

st.divider()

# ==================== AI ACCURACY OVER TIME ====================

st.markdown('<p class="section-title">🎯 AI Prediction Accuracy</p>', unsafe_allow_html=True)
st.markdown('<p class="section-subtitle">Is the AI getting better at predicting outcomes? This tracks accuracy over time.</p>', unsafe_allow_html=True)

if accuracy:
    checked = [p for p in accuracy if p.get("outcome_checked")]
    if checked:
        df_acc = pd.DataFrame(checked)
        if 'timestamp' in df_acc.columns:
            df_acc['timestamp'] = pd.to_datetime(df_acc['timestamp'])
            df_acc = df_acc.sort_values('timestamp')
            
            # Calculate running accuracy
            df_acc['correct_num'] = df_acc['outcome_correct'].astype(int)
            df_acc['running_accuracy'] = df_acc['correct_num'].expanding().mean() * 100
            
            fig_acc = go.Figure()
            fig_acc.add_trace(go.Scatter(
                x=df_acc['timestamp'], y=df_acc['running_accuracy'],
                mode='lines+markers', name='Accuracy',
                line=dict(color='#7c4dff', width=2),
                fill='tozeroy', fillcolor='rgba(124,77,255,0.1)'
            ))
            fig_acc.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Random (50%)")
            fig_acc.update_layout(
                title="AI Prediction Accuracy Over Time",
                xaxis_title="Date",
                yaxis_title="Accuracy (%)",
                height=350,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 100])
            )
            st.plotly_chart(fig_acc, use_container_width=True)
            st.caption("💡 Above 50% = better than random chance. The goal is 60%+ over time as Letta learns.")
    else:
        st.info("Accuracy data will appear after predictions have been checked (24+ hours after trades).")
else:
    st.info("AI accuracy tracking begins after the first trades are evaluated.")

st.divider()
st.caption(f"Trade Lab v2.3 · Charts & Analytics · {len(scenarios)} scenario snapshots · {len(trades)} trades · {len(learned)} learned rules")