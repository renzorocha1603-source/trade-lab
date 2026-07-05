"""
Letta Learning Memory — Self-improving trading memory.
Learns from every trade outcome and creates rules automatically.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class LettaMemory:
    """Self-learning memory that improves trading decisions over time"""

    def __init__(self, config):
        self.config = config
        self.memory_file = "logs/learned_rules.json"
        self.trade_memory_file = "logs/trade_memory.json"
        self.rules: List[dict] = self._load(self.memory_file, [])
        self.trade_history: List[dict] = self._load(self.trade_memory_file, [])
        self.enabled = True
        logger.info(f"Letta Memory: {len(self.rules)} learned rules | {len(self.trade_history)} past trades")

    def _load(self, path: str, default: any) -> any:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except:
                return default
        return default

    def _save(self, path: str, data: any):
        os.makedirs("logs", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def remember_trade(self, symbol: str, action: str, price: float,
                       rsi: float, vix: float, reason: str, scenario_id: str):
        """Record a trade for future learning"""
        self.trade_history.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": action,
            "price": price,
            "rsi": rsi,
            "vix": vix,
            "reason": reason[:200],
            "scenario_id": scenario_id,
            "outcome_checked": False,
            "outcome_pnl_pct": None,
            "outcome_success": None,
        })
        if len(self.trade_history) > 500:
            self.trade_history = self.trade_history[-500:]
        self._save(self.trade_memory_file, self.trade_history)

    def check_outcomes(self, prices: Dict[str, float]):
        """Check past trade outcomes and learn from them"""
        learned = False
        for trade in self.trade_history:
            if trade.get("outcome_checked"):
                continue
            trade_time = datetime.fromisoformat(trade["timestamp"])
            hours_ago = (datetime.now() - trade_time).total_seconds() / 3600
            if hours_ago < 24:
                continue
            current_price = prices.get(trade["symbol"])
            if not current_price or trade["price"] == 0:
                continue
            pnl_pct = ((current_price - trade["price"]) / trade["price"]) * 100
            if trade["action"] == "SELL":
                pnl_pct = -pnl_pct
            trade["outcome_checked"] = True
            trade["outcome_pnl_pct"] = round(pnl_pct, 2)
            trade["outcome_success"] = pnl_pct > 0
            self._learn_from_outcome(trade)
            learned = True
        if learned:
            self._save(self.trade_memory_file, self.trade_history)
            self._save(self.memory_file, self.rules)
            logger.info(f"Letta learned from outcomes | {len(self.rules)} rules active")

    def _learn_from_outcome(self, trade: dict):
        """Analyze a trade outcome and create/update rules"""
        rsi = trade.get("rsi", 50)
        vix = trade.get("vix", 20)
        pnl = trade.get("outcome_pnl_pct", 0)
        success = trade.get("outcome_success", False)

        # Rule: High VIX + Low RSI = good dip buy
        if rsi < 35 and vix > 25 and success:
            self._add_rule("high_vix_dip", 
                f"VIX high ({vix:.0f}) + RSI low ({rsi:.0f}) = dip buys work (+{pnl:.1f}%)",
                {"min_vix": 25, "max_rsi": 35}, "amplify_buy", 0.7)

        # Rule: High RSI + High VIX = avoid buying
        if rsi > 60 and vix > 28 and not success:
            self._add_rule("high_rsi_avoid",
                f"VIX high + RSI > 60 = avoid buying ({pnl:.1f}%)",
                {"min_vix": 28, "min_rsi": 60}, "dampen_buy", 0.65)

        # Rule: Low VIX = good environment
        if vix < 15 and success:
            self._add_rule("low_vix_bull",
                f"Low VIX ({vix:.0f}) = market is calm, buying works",
                {"max_vix": 15}, "amplify_buy", 0.6)

        # Rule: Crypto weekend success
        if "-USD" in trade["symbol"] and success:
            self._add_rule("crypto_win",
                f"Crypto trade on {trade['symbol']} worked (+{pnl:.1f}%)",
                {}, "amplify_buy", 0.55)

        # Rule: Canadian stock with oil correlation
        if ".TO" in trade["symbol"] and success:
            self._add_rule("tsx_win",
                f"TSX stock {trade['symbol']} trade worked (+{pnl:.1f}%)",
                {}, "amplify_buy", 0.55)

    def _add_rule(self, rule_id: str, description: str, conditions: dict,
                  action: str, confidence: float, times_seen: int = 1, times_worked: int = 1):
        """Add or update a learned rule"""
        for rule in self.rules:
            if rule.get("id") == rule_id:
                rule["times_seen"] += times_seen
                rule["times_worked"] += times_worked
                rule["confidence"] = rule["times_worked"] / max(rule["times_seen"], 1)
                rule["last_updated"] = datetime.now().isoformat()
                return
        self.rules.append({
            "id": rule_id,
            "description": description,
            "conditions": conditions,
            "action": action,
            "confidence": confidence,
            "times_seen": times_seen,
            "times_worked": times_worked,
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        })

    def get_advice(self, symbol: str, rsi: float, vix: float) -> Optional[dict]:
        """Get learned advice for current market conditions"""
        applicable = []
        for rule in self.rules:
            conditions = rule.get("conditions", {})
            match = True
            if "min_vix" in conditions and vix < conditions["min_vix"]: match = False
            if "max_vix" in conditions and vix > conditions["max_vix"]: match = False
            if "min_rsi" in conditions and rsi < conditions["min_rsi"]: match = False
            if "max_rsi" in conditions and rsi > conditions["max_rsi"]: match = False
            if match and rule["confidence"] >= 0.5:
                applicable.append(rule)
        if not applicable:
            return None
        applicable.sort(key=lambda r: r["confidence"], reverse=True)
        best = applicable[0]
        return {
            "advice": best["action"],
            "reason": best["description"],
            "confidence": best["confidence"],
            "based_on": f"{best['times_seen']} situations, worked {best['times_worked']} times"
        }

    def get_stats(self) -> dict:
        return {
            "total_rules": len(self.rules),
            "total_trades_remembered": len(self.trade_history),
            "rules": [{"id": r["id"], "desc": r["description"][:80], "conf": f"{r['confidence']:.0%}"} for r in self.rules]
        }