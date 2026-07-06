"""
Letta Memory v2.4 — Self-learning trading memory with multi-signal analysis.
Learns from DeepSeek + Claude agreement patterns, market regimes, and time decay.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class LettaMemory:
    """Advanced Self-improving Letta-style Trading Memory"""

    def __init__(self, config):
        self.config = config
        self.memory_dir = "logs"
        self.memory_file = f"{self.memory_dir}/learned_rules.json"
        self.trade_memory_file = f"{self.memory_dir}/trade_memory.json"

        self.rules: List[dict] = self._load(self.memory_file, [])
        self.trade_history: List[dict] = self._load(self.trade_memory_file, [])

        self.max_trades = getattr(config, 'max_trades', 1000) if hasattr(config, 'max_trades') else 1000
        self.min_confidence = 0.55
        self.rule_decay_days = 90

        # Market regime definitions
        self.regimes = {
            "fear": {"min_vix": 30},
            "cautious": {"min_vix": 25, "max_vix": 30},
            "normal": {"min_vix": 15, "max_vix": 25},
            "complacent": {"max_vix": 15},
        }

        logger.info(f"Letta Memory v2.4 | {len(self.rules)} rules | {len(self.trade_history)} trades | Decay: {self.rule_decay_days}d")

    def _load(self, path: str, default: any) -> any:
        os.makedirs(self.memory_dir, exist_ok=True)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")
        return default

    def _save(self):
        os.makedirs(self.memory_dir, exist_ok=True)
        with open(self.memory_file, "w") as f:
            json.dump(self.rules, f, indent=2, default=str)
        with open(self.trade_memory_file, "w") as f:
            json.dump(self.trade_history, f, indent=2, default=str)

    def _get_market_regime(self, vix: float) -> str:
        """Determine market regime from VIX"""
        if vix >= 30:
            return "fear"
        elif vix >= 25:
            return "cautious"
        elif vix >= 15:
            return "normal"
        else:
            return "complacent"

    def _get_symbol_category(self, symbol: str) -> str:
        """Categorize symbol type"""
        if "-USD" in symbol:
            return "crypto"
        elif ".TO" in symbol:
            return "canadian_stock"
        elif symbol in ["SPY", "QQQ", "IWM", "DIA", "VTI", "XIU.TO", "VFV.TO"]:
            return "broad_etf"
        elif symbol in ["XLF", "XLK", "XLE", "XLV"]:
            return "sector_etf"
        else:
            return "individual_stock"

    # ==================== TRADE MEMORY ====================

    def remember_trade(self, trade_data: dict):
        """Record trade with rich context including AI scores"""
        symbol = trade_data.get("symbol", "unknown")
        vix = trade_data.get("vix", 20)

        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": trade_data.get("action", "unknown"),
            "price": trade_data.get("price", 0),
            "rsi": trade_data.get("rsi"),
            "vix": vix,
            "regime": self._get_market_regime(vix) if vix else "unknown",
            "symbol_category": self._get_symbol_category(symbol),
            "deepseek_score": trade_data.get("deepseek_score"),
            "deepseek_confidence": trade_data.get("deepseek_confidence"),
            "claude_sentiment": trade_data.get("claude_sentiment"),
            "claude_bias": trade_data.get("claude_bias"),
            "models_agree": trade_data.get("models_agree"),
            "reason": trade_data.get("reason", "")[:300],
            "scenario": trade_data.get("scenario_id"),
            "news_freshness": trade_data.get("news_freshness"),
            "outcome_checked": False,
            "outcome_pnl_pct": None,
            "outcome_success": None,
        }

        self.trade_history.append(trade)
        if len(self.trade_history) > self.max_trades:
            self.trade_history = self.trade_history[-self.max_trades:]
        self._save()

    # ==================== OUTCOME CHECKING ====================

    def check_outcomes(self, current_prices: Dict[str, float]):
        """Update outcomes and trigger learning from completed trades"""
        learned_count = 0

        for trade in self.trade_history:
            if trade.get("outcome_checked"):
                continue

            trade_time = datetime.fromisoformat(trade["timestamp"])
            hours_elapsed = (datetime.now() - trade_time).total_seconds() / 3600
            if hours_elapsed < 24:
                continue

            current_price = current_prices.get(trade["symbol"])
            if not current_price or trade["price"] == 0:
                continue

            pnl_pct = ((current_price - trade["price"]) / trade["price"]) * 100
            if trade["action"].upper() == "SELL":
                pnl_pct = -pnl_pct

            trade["outcome_pnl_pct"] = round(pnl_pct, 3)
            trade["outcome_success"] = pnl_pct > 0
            trade["outcome_checked"] = True

            # Learn from this outcome
            self._learn_from_trade(trade)
            learned_count += 1

        if learned_count > 0:
            self._apply_time_decay()
            self._save()
            logger.info(f"Letta learned from {learned_count} outcomes | {len(self.rules)} rules active")

    # ==================== LEARNING ENGINE ====================

    def _learn_from_trade(self, trade: dict):
        """Extract patterns from a completed trade"""
        success = trade.get("outcome_success", False)
        pnl = trade.get("outcome_pnl_pct", 0)

        # 1. RSI + VIX combination rule
        if trade.get("rsi") and trade.get("vix"):
            self._create_signal_rule(trade)

        # 2. Model agreement/disagreement rule
        if trade.get("deepseek_score") is not None and trade.get("claude_sentiment") is not None:
            self._learn_model_combination(trade)

        # 3. Symbol category performance
        category = trade.get("symbol_category", "unknown")
        self._update_category_rule(category, success, pnl)

        # 4. News freshness impact
        freshness = trade.get("news_freshness")
        if freshness is not None:
            self._update_news_freshness_rule(freshness, success, pnl)

    def _create_signal_rule(self, trade: dict):
        """Create rules based on RSI + VIX + regime combinations"""
        rsi = trade["rsi"]
        vix = trade["vix"]
        regime = trade.get("regime", "unknown")
        success = trade.get("outcome_success", False)
        pnl = trade.get("outcome_pnl_pct", 0)
        action = trade.get("action", "").upper()

        # Define condition buckets
        if rsi < 35 and vix > 25:
            rule_id = "high_vix_low_rsi"
            description = f"High VIX ({vix:.0f}) + Low RSI ({rsi:.0f}) = dip buys tend to work in {regime} markets"
            conditions = {"min_vix": 25, "max_rsi": 35}
        elif rsi > 65 and vix < 18:
            rule_id = "low_vix_high_rsi"
            description = f"Low VIX ({vix:.0f}) + High RSI ({rsi:.0f}) = profit taking works in calm markets"
            conditions = {"max_vix": 18, "min_rsi": 65}
        elif rsi < 30:
            rule_id = "oversold_any_vix"
            description = f"Deeply oversold RSI ({rsi:.0f}) = bounce potential regardless of VIX"
            conditions = {"max_rsi": 30}
        elif vix > 28:
            rule_id = "high_vix_caution"
            description = f"Elevated VIX ({vix:.0f}) = reduced position sizes recommended"
            conditions = {"min_vix": 28}
        else:
            # No clear pattern — don't create a rule
            return

        recommendation = "amplify_buy" if (success and action == "BUY") else "dampen_buy" if (not success and action == "BUY") else "no_change"

        self._upsert_rule(rule_id, description, conditions, recommendation, success, pnl)

    def _learn_model_combination(self, trade: dict):
        """Learn from DeepSeek + Claude agreement or disagreement"""
        ds_score = trade.get("deepseek_score", 0)
        claude_sent = trade.get("claude_sentiment", 0)
        models_agree = trade.get("models_agree", None)
        success = trade.get("outcome_success", False)
        pnl = trade.get("outcome_pnl_pct", 0)

        # Determine agreement
        ds_direction = "bullish" if ds_score > 0.2 else "bearish" if ds_score < -0.2 else "neutral"
        claude_direction = "bullish" if claude_sent > 0.2 else "bearish" if claude_sent < -0.2 else "neutral"

        if ds_direction == claude_direction and ds_direction != "neutral":
            rule_id = f"models_agree_{ds_direction}"
            description = f"When both AIs agree ({ds_direction}), outcomes improve (avg {pnl:+.2f}%)"
            conditions = {"models_agree": True, "direction": ds_direction}
            recommendation = "amplify_buy" if success else "dampen_buy"
        elif ds_direction != claude_direction and ds_direction != "neutral" and claude_direction != "neutral":
            rule_id = f"models_disagree"
            description = f"When AIs disagree (DS:{ds_direction}, Claude:{claude_direction}), trust DeepSeek math over Claude sentiment"
            conditions = {"models_agree": False}
            recommendation = "follow_deepseek" if success else "reduce_position"
        else:
            return

        self._upsert_rule(rule_id, description, conditions, recommendation, success, pnl)

    def _update_category_rule(self, category: str, success: bool, pnl: float):
        """Track performance by symbol category"""
        rule_id = f"category_{category}"
        description = f"{category.replace('_', ' ').title()} trades performance"

        self._upsert_rule(rule_id, description, {"category": category}, "no_change", success, pnl)

    def _update_news_freshness_rule(self, freshness: float, success: bool, pnl: float):
        """Track how news freshness affects outcomes"""
        if freshness >= 0.7:
            rule_id = "fresh_news"
            description = f"Fresh news (>0.7) leads to better outcomes (+{pnl:+.2f}% avg)"
            conditions = {"min_news_freshness": 0.7}
        elif freshness < 0.4:
            rule_id = "stale_news"
            description = f"Stale news (<0.4) leads to worse outcomes — wait for fresh data"
            conditions = {"max_news_freshness": 0.4}
        else:
            return

        recommendation = "amplify_buy" if success else "dampen_buy"
        self._upsert_rule(rule_id, description, conditions, recommendation, success, pnl)

    def _upsert_rule(self, rule_id: str, description: str, conditions: dict,
                     recommendation: str, success: bool, pnl: float):
        """Insert or update a rule with success tracking"""
        for rule in self.rules:
            if rule.get("id") == rule_id:
                rule["times_seen"] += 1
                if success:
                    rule["times_worked"] += 1
                rule["total_pnl"] = rule.get("total_pnl", 0) + pnl
                rule["confidence"] = rule["times_worked"] / max(rule["times_seen"], 1)
                rule["avg_pnl"] = round(rule["total_pnl"] / rule["times_seen"], 2)
                rule["last_updated"] = datetime.now().isoformat()
                rule["last_seen"] = datetime.now().isoformat()
                return

        # New rule
        self.rules.append({
            "id": rule_id,
            "description": description,
            "conditions": conditions,
            "recommendation": recommendation,
            "confidence": 0.7 if success else 0.4,
            "times_seen": 1,
            "times_worked": 1 if success else 0,
            "total_pnl": pnl,
            "avg_pnl": round(pnl, 2),
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        })

    # ==================== TIME DECAY ====================

    def _apply_time_decay(self):
        """Reduce confidence of old rules that haven't been seen recently"""
        now = datetime.now()
        for rule in self.rules:
            last_seen = rule.get("last_seen")
            if last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen)
                    days_since = (now - last_seen_dt).days
                    if days_since > self.rule_decay_days:
                        decay = max(0.3, 1.0 - (days_since - self.rule_decay_days) / 180)
                        rule["confidence"] = round(rule["confidence"] * decay, 3)
                        rule["decayed"] = True
                except:
                    pass

    # ==================== ADVICE ENGINE ====================

    def get_advice(self, current_state: dict) -> Optional[dict]:
        """Get the best learned advice for current market conditions"""
        symbol = current_state.get("symbol", "")
        rsi = current_state.get("rsi", 50)
        vix = current_state.get("vix", 20)
        ds_score = current_state.get("deepseek_score")
        claude_sent = current_state.get("claude_sentiment")
        news_freshness = current_state.get("news_freshness")
        category = self._get_symbol_category(symbol)
        regime = self._get_market_regime(vix)

        applicable_rules = []

        for rule in self.rules:
            if rule.get("confidence", 0) < self.min_confidence:
                continue

            conditions = rule.get("conditions", {})
            matches = True

            for key, value in conditions.items():
                if key == "category" and value != category:
                    matches = False
                elif key == "min_vix" and vix < value:
                    matches = False
                elif key == "max_vix" and vix > value:
                    matches = False
                elif key == "min_rsi" and rsi < value:
                    matches = False
                elif key == "max_rsi" and rsi > value:
                    matches = False
                elif key == "min_news_freshness" and (news_freshness or 0) < value:
                    matches = False
                elif key == "max_news_freshness" and (news_freshness or 1) > value:
                    matches = False
                elif key == "models_agree":
                    ds_dir = "bullish" if (ds_score or 0) > 0.2 else "bearish" if (ds_score or 0) < -0.2 else "neutral"
                    cl_dir = "bullish" if (claude_sent or 0) > 0.2 else "bearish" if (claude_sent or 0) < -0.2 else "neutral"
                    agree = (ds_dir == cl_dir and ds_dir != "neutral")
                    if value != agree:
                        matches = False
                elif key == "direction":
                    ds_dir = "bullish" if (ds_score or 0) > 0.2 else "bearish" if (ds_score or 0) < -0.2 else "neutral"
                    if value != ds_dir:
                        matches = False

            if matches:
                applicable_rules.append(rule)

        if not applicable_rules:
            return None

        # Sort by confidence × times_seen (values proven rules more)
        applicable_rules.sort(key=lambda r: r["confidence"] * min(r["times_seen"], 20), reverse=True)
        best = applicable_rules[0]

        # Collect all matching advice
        amplify_count = sum(1 for r in applicable_rules if r.get("recommendation") in ["amplify_buy", "amplify_sell"])
        dampen_count = sum(1 for r in applicable_rules if r.get("recommendation") in ["dampen_buy", "dampen_sell"])

        final_advice = "amplify" if amplify_count > dampen_count else "dampen" if dampen_count > amplify_count else best.get("recommendation", "no_change")

        return {
            "advice": final_advice,
            "reason": best.get("description", "Based on historical patterns"),
            "confidence": round(best.get("confidence", 0.5), 2),
            "based_on": f"{best.get('times_seen', 0)} similar situations, worked {best.get('times_worked', 0)} times",
            "avg_pnl": best.get("avg_pnl", 0),
            "rules_matched": len(applicable_rules),
            "top_rules": [{"id": r["id"], "conf": r["confidence"], "desc": r["description"][:80]} for r in applicable_rules[:3]]
        }

    # ==================== STATISTICS ====================

    def _calculate_overall_winrate(self) -> float:
        """Calculate overall win rate from trade history"""
        checked = [t for t in self.trade_history if t.get("outcome_checked")]
        if not checked:
            return 0.0
        return round(sum(1 for t in checked if t.get("outcome_success")) / len(checked) * 100, 1)

    def get_stats(self) -> dict:
        """Get comprehensive memory statistics"""
        checked = [t for t in self.trade_history if t.get("outcome_checked")]
        wins = [t for t in checked if t.get("outcome_success")]
        losses = [t for t in checked if not t.get("outcome_success")]

        # Win rate by category
        category_stats = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in checked:
            cat = t.get("symbol_category", "unknown")
            category_stats[cat]["total"] += 1
            if t.get("outcome_success"):
                category_stats[cat]["wins"] += 1

        # Win rate by regime
        regime_stats = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in checked:
            reg = t.get("regime", "unknown")
            regime_stats[reg]["total"] += 1
            if t.get("outcome_success"):
                regime_stats[reg]["wins"] += 1

        # Best and worst performing rules
        proven_rules = sorted(
            [r for r in self.rules if r.get("times_seen", 0) >= 3],
            key=lambda r: r.get("confidence", 0),
            reverse=True
        )

        return {
            "total_rules": len(self.rules),
            "active_rules": len([r for r in self.rules if r.get("confidence", 0) >= self.min_confidence]),
            "total_trades_remembered": len(self.trade_history),
            "trades_evaluated": len(checked),
            "overall_win_rate": self._calculate_overall_winrate(),
            "avg_win_pnl": round(np.mean([t.get("outcome_pnl_pct", 0) for t in wins]), 2) if wins else 0,
            "avg_loss_pnl": round(np.mean([t.get("outcome_pnl_pct", 0) for t in losses]), 2) if losses else 0,
            "by_category": {k: {"win_rate": round(v["wins"]/max(v["total"],1)*100,1), "trades": v["total"]} for k,v in category_stats.items()},
            "by_regime": {k: {"win_rate": round(v["wins"]/max(v["total"],1)*100,1), "trades": v["total"]} for k,v in regime_stats.items()},
            "top_rules": [{"id": r["id"], "confidence": r["confidence"], "seen": r["times_seen"], "description": r["description"][:100]} for r in proven_rules[:5]]
        }

    def print_report(self):
        """Print a formatted learning report"""
        stats = self.get_stats()
        print(f"""
╔══════════════════════════════════════════════════╗
║           LETTA MEMORY REPORT                   ║
╠══════════════════════════════════════════════════╣
║ Rules: {stats['total_rules']:>5} | Active: {stats['active_rules']:>5}                    ║
║ Trades: {stats['total_trades_remembered']:>5} | Evaluated: {stats['trades_evaluated']:>5}            ║
║ Win Rate: {stats['overall_win_rate']:>5.1f}%                              ║
║ Avg Win: {stats['avg_win_pnl']:>+6.2f}% | Avg Loss: {stats['avg_loss_pnl']:>+6.2f}%         ║
╠══════════════════════════════════════════════════╣
║ By Category:                                     ║""")
        for cat, data in stats.get("by_category", {}).items():
            print(f"║   {cat:<20}: {data['win_rate']:>5.1f}% ({data['trades']} trades)           ║")
        print(f"╠══════════════════════════════════════════════════╣")
        print(f"║ By Regime:                                       ║")
        for reg, data in stats.get("by_regime", {}).items():
            print(f"║   {reg:<20}: {data['win_rate']:>5.1f}% ({data['trades']} trades)           ║")
        print(f"╚══════════════════════════════════════════════════╝")
"""