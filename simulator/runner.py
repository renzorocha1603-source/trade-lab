"""
Multi-Scenario Runner — Tests the same strategy across different account sizes.
Each scenario is an isolated paper account. Same AI, same trades, different money.
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
        """Load scenario configurations"""
        path = "scenarios.json"
        if not os.path.exists(path):
            logger.warning("scenarios.json not found, using defaults")
            return [{
                "id": "default_100k",
                "name": "Default - $100,000",
                "starting_capital_cad": 100000,
                "monthly_deposit_cad": 0,
            }]
        with open(path) as f:
            data = json.load(f)
        return data.get("scenarios", [])

    def run_all_scenarios(self, prices: Dict[str, float], fx_rate: float,
                         base_signal, deepseek_signal, claude_signal,
                         merger) -> Dict[str, dict]:
        """
        Run the same signal through every scenario.
        Returns results for each scenario independently.
        """
        results = {}

        for scenario in self.scenarios:
            scenario_id = scenario["id"]
            scenario_name = scenario["name"]
            capital = scenario["starting_capital_cad"]
            monthly = scenario["monthly_deposit_cad"]

            # Each scenario has its own isolated broker
            if scenario_id not in self.results:
                # Initialize new scenario account
                from broker.paper_broker import PaperBroker
                broker = PaperBroker.__new__(PaperBroker)
                broker.config = self.config
                broker.cash_cad = capital
                broker.initial_capital_cad = capital
                broker.monthly_deposit_cad = monthly
                broker.fx_fee_pct = self.config.broker.fx_fee_pct
                broker.commission = self.config.broker.commission_per_trade
                broker.slippage_pct = self.config.broker.slippage_pct
                broker.allow_fractional = self.config.broker.allow_fractional_shares
                broker.base_currency = "CAD"
                broker.positions = {}
                broker.order_history = []
                broker.deposit_history = []
                broker._current_fx_rate = fx_rate
                broker.set_fx_rate = lambda r: setattr(broker, '_current_fx_rate', r)

                self.results[scenario_id] = {
                    "name": scenario_name,
                    "broker": broker,
                    "trades": 0,
                    "snapshots": [],
                }

            entry = self.results[scenario_id]
            broker = entry["broker"]
            broker.set_fx_rate(fx_rate)

            # Monthly deposit (1st of month)
            if datetime.now().day == 1:
                broker.process_monthly_deposit()

            # Get current equity
            equity = broker.get_equity_cad(prices)

            # Record snapshot
            entry["snapshots"].append({
                "timestamp": datetime.now().isoformat(),
                "equity_cad": round(equity, 2),
                "cash_cad": round(broker.cash_cad, 2),
                "positions_count": len([p for p in broker.positions.values() if p.quantity > 0]),
                "trades_count": entry["trades"],
            })

            # Build scenario-specific results
            results[scenario_id] = {
                "name": scenario_name,
                "capital": capital,
                "monthly": monthly,
                "equity": round(equity, 2),
                "cash": round(broker.cash_cad, 2),
                "pnl": round(equity - capital, 2),
                "pnl_pct": round((equity / capital - 1) * 100, 2) if capital > 0 else 0,
                "trades": entry["trades"],
                "positions": len([p for p in broker.positions.values() if p.quantity > 0]),
            }

        return results

    def execute_trade_for_scenario(self, scenario_id: str, symbol: str,
                                  action: str, quantity: float, price: float,
                                  prices: Dict[str, float]) -> bool:
        """Execute a trade in a specific scenario account"""
        if scenario_id not in self.results:
            return False

        entry = self.results[scenario_id]
        broker = entry["broker"]

        # Scale quantity based on account size
        capital_ratio = broker.initial_capital_cad / self.config.broker.initial_capital_cad
        adjusted_qty = quantity * capital_ratio

        if adjusted_qty <= 0:
            return False

        order = broker.place_market_order(symbol, action, adjusted_qty, prices)
        if order and order.status == "filled":
            entry["trades"] += 1
            return True
        return False

    def get_comparison(self) -> dict:
        """Get side-by-side comparison of all scenarios"""
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
            })
        return comparison

    def print_comparison(self):
        """Print all scenarios side by side"""
        comparison = self.get_comparison()
        if not comparison:
            return

        print(f"\n{'='*80}")
        print(f"  SCENARIO COMPARISON — Same AI, Different Starting Amounts")
        print(f"{'='*80}")
        print(f"  {'Scenario':<25} {'Start':>12} {'Now':>12} {'P&L':>12} {'Return':>10} {'Trades':>8}")
        print(f"  {'-'*75}")
        for c in comparison:
            print(f"  {c['name']:<25} {c['starting']:>12} {c['now']:>12} {c['pnl']:>12} {c['pnl_pct']:>10} {c['trades']:>8}")
        print(f"{'='*80}\n")