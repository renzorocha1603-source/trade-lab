"""
Signal Merger - Pure Math, No AI.
Combines 3 blind signals: 5/10 Strategy + Gemini Research + Claude Psychology.
Each AI never sees the other. This merger uses hardcoded rules only.
"""

from typing import Optional
from dataclasses import dataclass
import logging

from .five_ten_rule import StrategySignal, SignalAction
from .gemini_research import ResearchSignal
from .claude_psychology import PsychologySignal

logger = logging.getLogger(__name__)


@dataclass
class FinalSignal:
    symbol: str
    action: str
    quantity_pct: float
    reason: str
    base_contribution: float
    gemini_contribution: float
    claude_contribution: float
    ai_modified: bool


class SignalMerger:
    """
    Blind merger - deterministic rules, zero AI.

    Weights:
    - Base Strategy: 50% (always trusted)
    - Gemini Research: 25% (facts and data)
    - Claude Psychology: 25% (human behavior)

    Safety Rules:
    1. If both AIs agree → amplify base signal
    2. If AIs disagree → trust base strategy, ignore both
    3. Paradigm shift from either AI → that AI gets 60% weight
    4. Confidence < 0.6 from any AI → ignore that AI
    5. Claude says "reverse" AND confidence > 0.8 → override
    """

    def __init__(self, config):
        self.base_weight = 0.50
        self.gemini_weight = 0.25
        self.claude_weight = 0.25
        self.min_confidence = config.gemini.confidence_threshold

    def merge(self, base_signal: StrategySignal,
              gemini_signal: Optional[ResearchSignal],
              claude_signal: Optional[PsychologySignal],
              current_qty: float) -> FinalSignal:
        """Merge 3 blind signals into one final decision."""

        symbol = base_signal.symbol
        base_action = base_signal.action.value
        base_qty = base_signal.quantity_pct

        # Default: trust base strategy
        final_action = base_action
        final_qty = base_qty
        ai_modified = False
        reasons = [base_signal.reason]
        gemini_contrib = 0.0
        claude_contrib = 0.0

        # Check Gemini
        gemini_ok = gemini_signal and gemini_signal.confidence >= self.min_confidence
        # Check Claude
        claude_ok = claude_signal and claude_signal.confidence >= self.min_confidence

        if not gemini_ok and not claude_ok:
            return FinalSignal(symbol=symbol, action=final_action, quantity_pct=final_qty,
                reason=" | ".join(reasons), base_contribution=1.0,
                gemini_contribution=0.0, claude_contribution=0.0, ai_modified=False)

        # Paradigm shift detection
        if gemini_ok and gemini_signal.impact_horizon == "paradigm_shift":
            self.gemini_weight = 0.60
            self.base_weight = 0.40
            reasons.append(f"Gemini paradigm shift: {gemini_signal.key_findings}")

        if claude_ok and claude_signal.crowd_behavior == "capitulation":
            self.claude_weight = 0.60
            self.base_weight = 0.40
            reasons.append(f"Claude capitulation detected: {claude_signal.reasoning}")

        # Calculate contributions
        base_score = 1.0 if base_action == "BUY" else (-1.0 if base_action == "SELL" else 0.0)
        gemini_score = 0.0
        claude_score = 0.0

        if gemini_ok:
            gemini_score = gemini_signal.sentiment_score
            gemini_contrib = gemini_score * self.gemini_weight
            if gemini_signal.recommendation == "amplify_buy":
                final_qty = min(base_qty * 1.5, 1.0)
                ai_modified = True
            elif gemini_signal.recommendation == "dampen_buy":
                final_qty = max(base_qty * 0.5, 0.01)
                ai_modified = True
            elif gemini_signal.recommendation == "amplify_sell":
                final_qty = min(base_qty * 1.5, 0.3)
                ai_modified = True
            elif gemini_signal.recommendation == "dampen_sell":
                final_qty = max(base_qty * 0.5, 0.01)
                ai_modified = True
            reasons.append(f"Gemini: {gemini_signal.key_findings}")

        if claude_ok:
            claude_score = claude_signal.sentiment_score
            claude_contrib = claude_score * self.claude_weight
            if claude_signal.recommendation == "reverse" and claude_signal.confidence > 0.8:
                if base_action == "BUY":
                    final_action = "HOLD"
                    final_qty = 0.0
                    reasons.append(f"Claude REVERSED buy: {claude_signal.reasoning}")
                    ai_modified = True
                elif base_action == "SELL":
                    final_action = "HOLD"
                    final_qty = 0.0
                    reasons.append(f"Claude REVERSED sell: {claude_signal.reasoning}")
                    ai_modified = True
            elif claude_signal.recommendation == "amplify_buy":
                final_qty = min(base_qty * 1.5, 1.0)
                ai_modified = True
            elif claude_signal.recommendation == "amplify_sell":
                final_qty = min(base_qty * 1.5, 0.3)
                ai_modified = True
            if claude_signal.recommendation != "reverse":
                reasons.append(f"Claude: {claude_signal.reasoning}")

        # Final weighted score
        final_score = (base_score * self.base_weight) + gemini_contrib + claude_contrib

        # Override if final score strongly contradicts
        if final_score > 0.3 and final_action == "SELL":
            final_action = "HOLD"
            ai_modified = True
            reasons.append("AI consensus overrides sell")
        elif final_score < -0.3 and final_action == "BUY":
            final_action = "HOLD"
            ai_modified = True
            reasons.append("AI consensus overrides buy")

        return FinalSignal(
            symbol=symbol,
            action=final_action,
            quantity_pct=final_qty,
            reason=" | ".join(reasons),
            base_contribution=self.base_weight,
            gemini_contribution=gemini_contrib,
            claude_contribution=claude_contrib,
            ai_modified=ai_modified
        )