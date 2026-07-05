# ==================== SCENARIO COMPARISON ====================

st.markdown('<p class="section-title">🧪 Scenario Simulator</p>', unsafe_allow_html=True)
st.markdown('<p class="explanation">Same AI, different starting amounts. See how each account size performs with identical trades.</p>', unsafe_allow_html=True)

# Load scenario data from logs
scenario_data = []
if os.path.exists("logs/scenario_snapshots.json"):
    try:
        with open("logs/scenario_snapshots.json") as f:
            scenario_data = json.load(f)
    except:
        pass

if scenario_data:
    # Get latest snapshot for each scenario
    latest_scenarios = {}
    for s in scenario_data:
        sid = s.get("scenario_id", "unknown")
        if sid not in latest_scenarios or s.get("timestamp", "") > latest_scenarios[sid].get("timestamp", ""):
            latest_scenarios[sid] = s
    
    if latest_scenarios:
        cols = st.columns(len(latest_scenarios))
        for i, (sid, data) in enumerate(sorted(latest_scenarios.items())):
            with cols[i]:
                equity = data.get("equity_cad", 0)
                capital = data.get("starting_capital", 500)
                pnl = equity - capital
                pnl_pct = (pnl / capital * 100) if capital > 0 else 0
                color = "green" if pnl >= 0 else "red"
                st.markdown(f"**{data.get('name', sid)}**")
                st.markdown(f"<h3 style='color:{color}'>${equity:,.2f}</h3>", unsafe_allow_html=True)
                st.caption(f"{'↑' if pnl >= 0 else '↓'} ${pnl:,.2f} ({pnl_pct:+.2f}%)")
                st.caption(f"Trades: {data.get('trades', 0)}")
else:
    st.info("Scenario data will appear after the first trades execute across all account sizes. Check back soon!")

st.divider()