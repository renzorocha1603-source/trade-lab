"""
Letta Memory v2.6 — Fast Learning Mode
Clean structure + Rich multi-condition learning + Time decay + Category/Regime tracking
Learns from DeepSeek + Claude signals, market regimes, symbol categories, and model agreement.
Letta is the FINAL DECISION MAKER — combines all signals with learned memory.
Grok-optimized decision engine with improved scoring formulas.
FAST MODE: Evaluates trades after 1 hour instead of 24 hours.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class LettaMemory:
    """Advanced Self-improving Trading Memory — Fast Learning Mode"""

    def __init__(self, config):
        self.config = config
        self.memory_dir = "logs"
        self.rules_file = f"{self.memory_dir}/learned_rules.json"
        self.trades_file = f"{self.memory_dir}/trade_memory.json"

        self.rules: List[dict] = self._load(self.rules_file, [])
        self.trade_history: List[dict] = self._load(self.trades_file, [])

        self.max_trades = 5000
        self.max_rules = 100
        self.min_confidence = 0.50
        self.rule_decay_days = 45
        self.evaluation_hours = 1  # FAST MODE: Evaluate after 1 hour

        self.regimes = {
            "fear": {"min_vix": 30},
            "cautious": {"min_vix": 25, "max_vix": 30},
            "normal": {"min_vix": 15, "max_vix": 25},
            "complacent": {"max_vix": 15},
        }

        logger.info(f"Letta Memory v2.6 FAST MODE | {len(self.rules)} rules | {len(self.trade_history)} trades | Evaluate: {self.evaluation_hours}h | Decay: {self.rule_decay_days}d")

    # ==================== FILE I/O ====================

    def _load(self, path: str, default: any) -> any:
        os.makedirs(self.memory_dir, exist_ok=True)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {path}: {e}")
        return default

    def _save(self):
        os.makedirs(self.memory_dir, exist_ok=True)
        with open(self.rules_file, "w") as f:
            json.dump(self.rules, f, indent=2, default=str)
        with open(self.trades_file, "w") as f:
            json.dump(self.trade_history, f, indent=2, default=str)

    # ==================== HELPERS ====================

    def _get_regime(self, vix: float) -> str:
        if vix >= 30: return "fear"
        elif vix >= 25: return "cautious"
        elif vix >= 15: return "normal"
        return "complacent"

    def _get_category(self, symbol: str) -> str:
        if "-USD" in symbol: return "crypto"
        elif ".TO" in symbol: return "canadian_stock"
        elif symbol in ["SPY", "QQQ", "IWM", "DIA", "VTI"]: return "broad_etf"
        elif symbol in ["XLF", "XLK", "XLE", "XLV"]: return "sector_etf"
        return "individual_stock"

    # ==================== TRADE MEMORY ====================

    def remember_trade(self, trade_data: dict):
        """Record rich trade context from all agents"""
        symbol = trade_data.get("symbol", "unknown")
        vix = trade_data.get("vix", 20)

        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": trade_data.get("action", "").upper(),
            "price": float(trade_data.get("price", 0)),
            "quantity_pct": float(trade_data.get("quantity_pct", 0)),
            "rsi": trade_data.get("rsi"),
            "vix": vix,
            "regime": self._get_regime(vix) if vix else "unknown",
            "category": self._get_category(symbol),
            "deepseek_score": trade_data.get("deepseek_score"),
            "deepseek_confidence": trade_data.get("deepseek_confidence"),
            "claude_sentiment": trade_data.get("claude_sentiment"),
            "claude_bias": trade_data.get("claude_bias"),
            "models_agree": trade_data.get("models_agree"),
            "news_freshness": trade_data.get("news_freshness"),
            "reason": trade_data.get("reason", "")[:400],
            "scenario": trade_data.get("scenario_id"),
            "outcome_checked": False,
            "outcome_pnl_pct": None,
            "outcome_success": None,
        }

        self.trade_history.append(trade)
        if len(self.trade_history) > self.max_trades:
            self.trade_history = self.trade_history[-self.max_trades:]
        self._save()
        logger.debug(f"Letta: {trade['symbol']} {trade['action']} remembered")

    # ==================== OUTCOME CHECKING ====================

    def check_outcomes(self, current_prices: Dict[str, float]):
        """Check past trades and trigger learning — FAST MODE (1 hour)"""
        learned = 0

        for trade in self.trade_history:
            if trade.get("outcome_checked"):
                continue

            trade_time = datetime.fromisoformat(trade["timestamp"])
            hours_elapsed = (datetime.now() - trade_time).total_seconds() / 3600
            if hours_elapsed < self.evaluation_hours:
                continue

            current_price = current_prices.get(trade["symbol"])
            if not current_price or trade["price"] == 0:
                logger.debug(f"Letta: No price for {trade['symbol']} — skipping evaluation")
                continue

            pnl_pct = ((current_price - trade["price"]) / trade["price"]) * 100
            if trade["action"] == "SELL":
                pnl_pct = -pnl_pct

            trade["outcome_pnl_pct"] = round(pnl_pct, 3)
            trade["outcome_success"] = pnl_pct > 0.0
            trade["outcome_checked"] = True

            logger.info(f"Letta evaluating: {trade['symbol']} {trade['action']} | Entry: ${trade['price']:.2f} | Current: ${current_price:.2f} | PnL: {pnl_pct:+.2f}% | {'✅ WIN' if pnl_pct > 0 else '❌ LOSS'}")

            self._learn_from_outcome(trade)
            learned += 1

        if learned > 0:
            self._decay_old_rules()
            self._prune_rules()
            self._save()
            logger.info(f"🧠 Letta learned from {learned} outcomes | {len(self.rules)} rules active")

    # ==================== LEARNING ENGINE ====================

    def _learn_from_outcome(self, trade: dict):
        """Create multiple rule types from a single trade outcome"""
        success = trade.get("outcome_success", False)
        pnl = trade.get("outcome_pnl_pct", 0)
        rsi = trade.get("rsi")
        vix = trade.get("vix")
        ds_score = trade.get("deepseek_score")
        claude_sent = trade.get("claude_sentiment")
        category = trade.get("category", "unknown")
        regime = trade.get("regime", "unknown")
        freshness = trade.get("news_freshness")

        if rsi is not None and vix is not None:
            if rsi < 35 and vix > 25:
                self._add_rule(
                    rule_id="high_vix_low_rsi",
                    description=f"High VIX ({vix:.0f}) + Low RSI ({rsi:.0f}) = dip buys work in {regime}",
                    conditions={"min_vix": 25, "max_rsi": 35},
                    recommendation="amplify_buy" if success else "dampen_buy",
                    success=success, pnl=pnl
                )
            elif rsi > 65 and vix < 18:
                self._add_rule(
                    rule_id="low_vix_high_rsi",
                    description=f"Low VIX ({vix:.0f}) + High RSI ({rsi:.0f}) = profit taking works",
                    conditions={"max_vix": 18, "min_rsi": 65},
                    recommendation="amplify_sell" if success else "no_change",
                    success=success, pnl=pnl
                )

        if ds_score is not None and claude_sent is not None:
            ds_dir = "bullish" if ds_score > 0.2 else "bearish" if ds_score < -0.2 else "neutral"
            cl_dir = "bullish" if claude_sent > 0.2 else "bearish" if claude_sent < -0.2 else "neutral"
            agree = (ds_dir == cl_dir and ds_dir != "neutral")

            if agree:
                self._add_rule(
                    rule_id=f"models_agree_{ds_dir}",
                    description=f"Both AIs agree ({ds_dir}) = higher confidence",
                    conditions={"models_agree": True, "direction": ds_dir},
                    recommendation="amplify_buy" if success else "dampen_buy",
                    success=success, pnl=pnl
                )
            else:
                self._add_rule(
                    rule_id="models_disagree",
                    description=f"AIs disagree (DS:{ds_dir}, Claude:{cl_dir}) = trust DeepSeek math",
                    conditions={"models_agree": False},
                    recommendation="follow_deepseek" if success else "reduce_position",
                    success=success, pnl=pnl
                )

        self._add_rule(
            rule_id=f"category_{category}",
            description=f"{category.replace('_',' ').title()} performance in {regime}",
            conditions={"category": category, "regime": regime},
            recommendation="no_change",
            success=success, pnl=pnl
        )

        if freshness is not None:
            if freshness >= 0.7:
                self._add_rule(
                    rule_id="fresh_news",
                    description="Fresh news (>0.7) leads to better outcomes",
                    conditions={"min_news_freshness": 0.7},
                    recommendation="amplify_buy" if success else "no_change",
                    success=success, pnl=pnl
                )
            elif freshness < 0.4:
                self._add_rule(
                    rule_id="stale_news",
                    description="Stale news (<0.4) = wait for fresh data",
                    conditions={"max_news_freshness": 0.4},
                    recommendation="dampen_buy" if not success else "no_change",
                    success=success, pnl=pnl
                )

        self._add_rule(
            rule_id=f"regime_{regime}",
            description=f"Trading in {regime} regime",
            conditions={"regime": regime},
            recommendation="amplify_buy" if success else "dampen_buy",
            success=success, pnl=pnl
        )

    def _add_rule(self, rule_id: str, description: str, conditions: dict,
                  recommendation: str, success: bool, pnl: float):
        """Insert or update a rule"""
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

    # ==================== MAINTENANCE ====================

    def _decay_old_rules(self):
        """Reduce confidence of rules not seen recently"""
        now = datetime.now()
        for rule in self.rules:
            last_seen = rule.get("last_seen")
            if last_seen:
                try:
                    age_days = (now - datetime.fromisoformat(last_seen)).days
                    if age_days > self.rule_decay_days:
                        decay = max(0.3, 1.0 - (age_days - self.rule_decay_days) * 0.008)
                        rule["confidence"] = round(rule["confidence"] * decay, 3)
                        rule["decayed"] = True
                except:
                    pass

    def _prune_rules(self):
        """Keep only the best rules"""
        if len(self.rules) > self.max_rules:
            self.rules.sort(key=lambda r: r.get("confidence", 0) * min(r.get("times_seen", 1), 10), reverse=True)
            self.rules = self.rules[:self.max_rules]

    # ==================== ADVICE ENGINE ====================

    def get_advice(self, symbol: str, rsi: float = None, vix: float = None,
                   deepseek_score: float = None, claude_sentiment: float = None,
                   news_freshness: float = None) -> Optional[dict]:
        """Get best learned advice for current conditions"""
        category = self._get_category(symbol)
        regime = self._get_regime(vix) if vix else "unknown"

        applicable = []
        for rule in self.rules:
            if rule.get("confidence", 0) < self.min_confidence:
                continue

            conditions = rule.get("conditions", {})
            match = True

            for key, value in conditions.items():
                if key == "category" and value != category:
                    match = False
                elif key == "regime" and value != regime:
                    match = False
                elif key == "min_vix" and (vix or 20) < value:
                    match = False
                elif key == "max_vix" and (vix or 20) > value:
                    match = False
                elif key == "min_rsi" and (rsi or 50) < value:
                    match = False
                elif key == "max_rsi" and (rsi or 50) > value:
                    match = False
                elif key == "min_news_freshness" and (news_freshness or 0) < value:
                    match = False
                elif key == "max_news_freshness" and (news_freshness or 1) > value:
                    match = False
                elif key == "models_agree":
                    ds_dir = "bullish" if (deepseek_score or 0) > 0.2 else "bearish" if (deepseek_score or 0) < -0.2 else "neutral"
                    cl_dir = "bullish" if (claude_sentiment or 0) > 0.2 else "bearish" if (claude_sentiment or 0) < -0.2 else "neutral"
                    agree = (ds_dir == cl_dir and ds_dir != "neutral")
                    if value != agree:
                        match = False
                elif key == "direction":
                    ds_dir = "bullish" if (deepseek_score or 0) > 0.2 else "bearish" if (deepseek_score or 0) < -0.2 else "neutral"
                    if value != ds_dir:
                        match = False

            if match:
                applicable.append(rule)

        if not applicable:
            return None

        applicable.sort(key=lambda r: r["confidence"] * min(r["times_seen"], 20), reverse=True)
        best = applicable[0]

        amplify = sum(1 for r in applicable if r.get("recommendation") in ["amplify_buy", "amplify_sell"])
        dampen = sum(1 for r in applicable if r.get("recommendation") in ["dampen_buy", "dampen_sell"])

        final_advice = "amplify" if amplify > dampen else "dampen" if dampen > amplify else best.get("recommendation", "no_change")

        return {
            "advice": final_advice,
            "reason": best.get("description", "Based on historical patterns"),
            "confidence": round(best.get("confidence", 0.5), 2),
            "based_on": f"{best.get('times_seen', 0)} similar situations, worked {best.get('times_worked', 0)} times",
            "avg_pnl": best.get("avg_pnl", 0),
            "rules_matched": len(applicable),
            "top_rules": [{"id": r["id"], "conf": r["confidence"], "desc": r["description"][:80]} for r in applicable[:3]]
        }

    # ==================== FINAL DECISION ENGINE (Grok Optimized) ====================

    def make_final_decision(self, symbol: str, base_signal, deepseek_signal: dict = None,
                           claude_opinion: dict = None, current_price: float = 0,
                           macro: dict = None) -> dict:
        """
        Letta is the final decision maker.
        Weights: Strategy 40% | DeepSeek 30% | Claude 15% | Letta Memory 15%
        Grok-optimized scoring formulas with improved quantity scaling.
        """

        # Normalize base_signal (supports both object and dict)
        if hasattr(base_signal, 'action'):
            base_action = base_signal.action.value
            base_qty = getattr(base_signal, 'quantity_pct', 0.05)
            base_conf = getattr(base_signal, 'confidence', 0.6)
            base_reason = getattr(base_signal, 'reason', '')
        else:
            base_action = base_signal.get('action', 'HOLD')
            base_qty = base_signal.get('quantity_pct', 0.05)
            base_conf = base_signal.get('confidence', 0.6)
            base_reason = base_signal.get('reason', '')

        # Extract AI signals with safe defaults
        ds_score = deepseek_signal.get('sentiment_score', 0) if deepseek_signal else 0
        ds_conf = deepseek_signal.get('confidence', 0.5) if deepseek_signal else 0.5
        ds_rec = deepseek_signal.get('recommendation', 'no_change') if deepseek_signal else 'no_change'

        cl_score = claude_opinion.get('sentiment_score', 0) if claude_opinion else 0
        cl_conf = claude_opinion.get('confidence', 0.5) if claude_opinion else 0.5
        cl_rec = claude_opinion.get('recommendation', 'no_change') if claude_opinion else 'no_change'

        # Get Letta learned advice
        rsi = base_signal.metrics.get('rsi', 50) if hasattr(base_signal, 'metrics') and base_signal.metrics else 50
        vix = macro.get('vix', 20) if macro else 20
        news_freshness = base_signal.metrics.get('news_freshness', 0.5) if hasattr(base_signal, 'metrics') and base_signal.metrics else 0.5

        letta_advice = self.get_advice(
            symbol=symbol, rsi=rsi, vix=vix,
            deepseek_score=ds_score, claude_sentiment=cl_score,
            news_freshness=news_freshness
        )

        # Weighted scoring
        base_score = 1.0 if base_action == "BUY" else (-1.0 if base_action == "SELL" else 0.0)
        base_weighted = base_score * base_conf * 0.40
        ds_weighted = ds_score * ds_conf * 0.30
        cl_weighted = cl_score * cl_conf * 0.15

        letta_weighted = 0.0
        letta_reason = ""
        letta_rules_used = 0
        if letta_advice:
            if letta_advice.get("advice") in ["amplify", "amplify_buy"]:
                letta_weighted = 0.6 * letta_advice.get("confidence", 0.5) * 0.15
            elif letta_advice.get("advice") in ["dampen", "dampen_buy", "reduce_position"]:
                letta_weighted = -0.4 * letta_advice.get("confidence", 0.5) * 0.15
            letta_reason = letta_advice.get("reason", "")
            letta_rules_used = letta_advice.get("rules_matched", 0)

        final_score = base_weighted + ds_weighted + cl_weighted + letta_weighted

        # Grok's improved decision logic with dynamic quantity scaling
        if final_score > 0.28:
            action = "BUY"
            qty = min(1.0, base_qty * (1.0 + final_score))
        elif final_score < -0.28:
            action = "SELL"
            qty = min(1.0, base_qty * (0.6 + abs(final_score)))
        else:
            action = "HOLD"
            qty = 0.0

        # Build reason string
        reason_parts = [f"Strategy: {base_reason[:60]}"]
        if deepseek_signal:
            reason_parts.append(f"DeepSeek: {ds_rec} ({ds_score:+.2f})")
        if claude_opinion:
            reason_parts.append(f"Claude: {cl_rec} ({cl_score:+.2f})")
        if letta_reason:
            reason_parts.append(f"Letta: {letta_reason[:70]}")
        reason_parts.append(f"Score: {final_score:+.3f}")

        # Track model agreement
        ds_dir = "bullish" if ds_score > 0.2 else "bearish" if ds_score < -0.2 else "neutral"
        cl_dir = "bullish" if cl_score > 0.2 else "bearish" if cl_score < -0.2 else "neutral"
        models_agree = (ds_dir == cl_dir and ds_dir != "neutral")

        return {
            "action": action,
            "quantity_pct": round(qty, 4),
            "confidence": round(abs(final_score), 3),
            "reason": " | ".join(reason_parts),
            "final_score": round(final_score, 3),
            "weights": {
                "base": round(base_weighted, 3),
                "deepseek": round(ds_weighted, 3),
                "claude": round(cl_weighted, 3),
                "letta": round(letta_weighted, 3),
            },
            "models_agree": models_agree,
            "letta_rules_used": letta_rules_used,
        }

    # ==================== STATISTICS ====================

    def get_stats(self) -> dict:
        """Comprehensive statistics"""
        checked = [t for t in self.trade_history if t.get("outcome_checked")]
        wins = [t for t in checked if t.get("outcome_success")]
        losses = [t for t in checked if not t.get("outcome_success")]

        category_stats = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in checked:
            cat = t.get("category", "unknown")
            category_stats[cat]["total"] += 1
            if t.get("outcome_success"):
                category_stats[cat]["wins"] += 1

        regime_stats = defaultdict(lambda: {"wins": 0, "total": 0})
        for t in checked:
            reg = t.get("regime", "unknown")
            regime_stats[reg]["total"] += 1
            if t.get("outcome_success"):
                regime_stats[reg]["wins"] += 1

        active = [r for r in self.rules if r.get("confidence", 0) >= self.min_confidence]
        win_rate = round(len(wins) / max(len(checked), 1) * 100, 1)

        return {
            "total_rules": len(self.rules),
            "active_rules": len(active),
            "total_trades": len(self.trade_history),
            "checked_trades": len(checked),
            "win_rate": win_rate,
            "avg_win_pnl": round(sum(t.get("outcome_pnl_pct", 0) for t in wins) / max(len(wins), 1), 2),
            "avg_loss_pnl": round(sum(t.get("outcome_pnl_pct", 0) for t in losses) / max(len(losses), 1), 2),
            "by_category": {k: {"win_rate": round(v["wins"]/max(v["total"],1)*100,1), "trades": v["total"]} for k,v in category_stats.items()},
            "by_regime": {k: {"win_rate": round(v["wins"]/max(v["total"],1)*100,1), "trades": v["total"]} for k,v in regime_stats.items()},
            "top_rules": [{"id": r["id"], "conf": r["confidence"], "seen": r["times_seen"], "desc": r["description"][:100]} for r in sorted(active, key=lambda x: x["confidence"], reverse=True)[:5]]
        }

    def print_report(self):
        """Formatted learning report"""
        stats = self.get_stats()
        print(f"""
╔══════════════════════════════════════════════════╗
║           LETTA MEMORY v2.6 REPORT              ║
╠══════════════════════════════════════════════════╣
║ Rules: {stats['total_rules']:>5} | Active: {stats['active_rules']:>5} | Trades: {stats['total_trades']:>5}         ║
║ Win Rate: {stats['win_rate']:>5.1f}% | Avg Win: {stats['avg_win_pnl']:>+6.2f}% | Avg Loss: {stats['avg_loss_pnl']:>+6.2f}% ║
╠══════════════════════════════════════════════════╣
║ By Category:                                     ║""")
        for cat, data in stats.get("by_category", {}).items():
            print(f"║   {cat:<20}: {data['win_rate']:>5.1f}% ({data['trades']} trades)           ║")
        print(f"╠══════════════════════════════════════════════════╣")
        print(f"║ By Regime:                                       ║")
        for reg, data in stats.get("by_regime", {}).items():
            print(f"║   {reg:<20}: {data['win_rate']:>5.1f}% ({data['trades']} trades)           ║")
        print(f"╚══════════════════════════════════════════════════╝")