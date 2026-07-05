"""
Multi-Scenario Runner — Tests the same strategy across different account sizes.
Each scenario is an isolated paper account with its own risk profile.
Saves snapshots for dashboard display.
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """Runs multiple scenarios simultaneously with isolated accounts"""

    def __init__(self, config, data_pipeline):
        self.config = config
        self.data = data_pipeline
        self.scenarios = self._load_scenarios()
        self.results: Dict[str, dict] = {}
        logger.info(f"Scenario Runner: {len(self.scenarios)} scenarios loaded")

    def _load_scenarios(self) -> List[dict]:
        path = "scenarios.json"
        if not os.path.exists(path):
            logger.warning("scenarios.json not found, using defaults")
            return [{
                "id": "default_5k",
                "name": "Default $5,000",
                "starting_capital_cad": 5000,
                "monthly_deposit_cad": 0,
                "risk_profile": "balanced",
            }]
        with open(path) as f:
            data = json.load(f)
        return data.get("scenarios", [])

    def _init_scenario(self, scenario_id: str):
        """Initialize a scenario if it doesn't exist yet"""
        if scenario_id in self.results:
            return

        for scenario in self.scenarios:
            if scenario["id"] == scenario_id:
                from broker.paper_broker import PaperBroker
                broker = PaperBroker.__new__(PaperBroker)
                broker.config = self.config
                broker.cash_cad = scenario["starting_capital_cad"]
                broker.initial_capital_cad = scenario["starting_capital_cad"]
                broker.monthly_deposit_cad = scenario.get("monthly_deposit_cad", 0)
                broker.fx_fee_pct = self.config.broker.fx_fee_pct
                broker.commission = self.config.broker.commission_per_trade
                broker.slippage_pct = self.config.broker.slippage_pct
                broker.allow_fractional = self.config.broker.allow_fractional_shares
                broker.base_currency = "CAD"
                broker.positions = {}
                broker.order_history = []
                broker.deposit_history = []
                broker._current_fx_rate = 1.35
                broker.set_fx_rate = lambda r: setattr(broker, '_current_fx_rate', r)

                self.results[scenario_id] = {
                    "name": scenario["name"],
                    "broker": broker,
                    "trades": 0,
                    "risk_profile": scenario.get("risk_profile", "balanced"),
                }
                logger.info(f"Initialized scenario: {scenario['name']} (${scenario['starting_capital_cad']:,.0f} CAD)")
                return

    def execute_trade_for_scenario(self, scenario_id: str, symbol: str,
                                  action: str, quantity: float, price: float,
                                  prices: Dict[str, float]) -> bool:
        if scenario_id not in self.results:
            self._init_scenario(scenario_id)
        if scenario_id not in self.results:
            return False

        entry = self.results[scenario_id]
        broker = entry["broker"]

        capital_ratio = broker.initial_capital_cad / 100000
        adjusted_qty = quantity * capital_ratio

        if adjusted_qty <= 0:
            return False

        order = broker.place_market_order(symbol, action, adjusted_qty, prices)
        if order and order.status == "filled":
            entry["trades"] += 1
            return True
        return False

    def save_scenario_snapshots(self):
        """Save all scenario data for the dashboard"""
        os.makedirs("logs", exist_ok=True)
        snapshots = []
        for sid, entry in self.results.items():
            broker = entry["broker"]
            prices = {}
            for sym, pos in broker.positions.items():
                if pos.quantity > 0:
                    prices[sym] = pos.current_price_usd
            equity = broker.get_equity_cad(prices) if prices else broker.cash_cad
            snapshots.append({
                "scenario_id": sid,
                "name": entry["name"],
                "timestamp": datetime.now().isoformat(),
                "starting_capital": broker.initial_capital_cad,
                "equity_cad": round(equity, 2),
                "cash_cad": round(broker.cash_cad, 2),
                "trades": entry["trades"],
                "positions": len([p for p in broker.positions.values() if p.quantity > 0]),
                "monthly_deposit": broker.monthly_deposit_cad,
                "risk_profile": entry.get("risk_profile", "balanced"),
            })
        try:
            with open("logs/scenario_snapshots.json", "w") as f:
                json.dump(snapshots, f, indent=2, default=str)
        except Exception as e:
            logger.debug(f"Scenario save error: {e}")

    def get_comparison(self) -> list:
        comparison = []
        for sid, entry in self.results.items():
            capital = entry["broker"].initial_capital_cad
            equity = entry["broker"].get_equity_cad({})
            comparison.append({
                "name": entry["name"],
                "starting": f"${capital:,.2f}",
                "now": f"${equity:,.2f}",
                "pnl": f"${equity - capital:,.2f}",
                "pnl_pct": f"{((equity / capital - 1) * 100):+.2f}%" if capital > 0 else "0%",
                "trades": entry["trades"],
                "risk": entry.get("risk_profile", "balanced"),
            })
        return comparison

    def print_comparison(self):
        comparison = self.get_comparison()
        if not comparison:
            return
        print(f"\n{'='*80}")
        print(f"  SCENARIO COMPARISON")
        print(f"{'='*80}")
        for c in comparison:
            print(f"  {c['name']:<20} | Start: {c['starting']:>12} | Now: {c['now']:>12} | {c['pnl_pct']:>8} | {c['trades']} trades | {c['risk']}")
        print(f"{'='*80}\n")