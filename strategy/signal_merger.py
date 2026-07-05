"""
Signal Merger - Pure Math, No AI.
Combines 3 blind signals: 5/10 Strategy + DeepSeek Research + Claude Psychology.
Each AI never sees the other. This merger uses hardcoded rules only.
"""

from typing import Optional
from dataclasses import dataclass
import logging

from .five_ten_rule import StrategySignal, SignalAction
from .deepseek_research import ResearchSignal
from .claude_psychology import PsychologySignal

logger = logging.getLogger(__name__)


@dataclass
class FinalSignal:
    symbol: str
    action: str
    quantity_pct: float
    reason: str
    base_contribution: float
    deepseek_contribution: float
    claude_contribution: float
    ai_modified: bool


class SignalMerger:
    """Blind merger - deterministic rules, zero AI."""

    def __init__(self, config):
        self.base_weight = 0.50
        self.deepseek_weight = 0.25
        self.claude_weight = 0.25
        self.min_confidence = config.deepseek.confidence_threshold

    def merge(self, base_signal: StrategySignal,
              deepseek_signal: Optional[ResearchSignal],
              claude_signal: Optional[PsychologySignal],
              current_qty: float) -> FinalSignal:

        symbol = base_signal.symbol
        base_action = base_signal.action.value
        base_qty = base_signal.quantity_pct
        final_action = base_action
        final_qty = base_qty
        ai_modified = False
        reasons = [base_signal.reason]
        deepseek_contrib = 0.0
        claude_contrib = 0.0

        deepseek_ok = deepseek_signal and deepseek_signal.confidence >= self.min_confidence
        claude_ok = claude_signal and claude_signal.confidence >= self.min_confidence

        if not deepseek_ok and not claude_ok:
            return FinalSignal(symbol=symbol, action=final_action, quantity_pct=final_qty,
                reason=" | ".join(reasons), base_contribution=1.0,
                deepseek_contribution=0.0, claude_contribution=0.0, ai_modified=False)

        if deepseek_ok and deepseek_signal.impact_horizon == "paradigm_shift":
            self.deepseek_weight = 0.60
            self.base_weight = 0.40
            reasons.append(f"DeepSeek paradigm shift: {deepseek_signal.key_findings}")

        if claude_ok and claude_signal.crowd_behavior == "capitulation":
            self.claude_weight = 0.60
            self.base_weight = 0.40
            reasons.append(f"Claude capitulation: {claude_signal.reasoning}")

        base_score = 1.0 if base_action == "BUY" else (-1.0 if base_action == "SELL" else 0.0)

        if deepseek_ok:
            deepseek_contrib = deepseek_signal.sentiment_score * self.deepseek_weight
            if deepseek_signal.recommendation == "amplify_buy":
                final_qty = min(base_qty * 1.5, 1.0); ai_modified = True
            elif deepseek_signal.recommendation == "dampen_buy":
                final_qty = max(base_qty * 0.5, 0.01); ai_modified = True
            elif deepseek_signal.recommendation == "amplify_sell":
                final_qty = min(base_qty * 1.5, 0.3); ai_modified = True
            elif deepseek_signal.recommendation == "dampen_sell":
                final_qty = max(base_qty * 0.5, 0.01); ai_modified = True
            reasons.append(f"DeepSeek: {deepseek_signal.key_findings}")

        if claude_ok:
            claude_contrib = claude_signal.sentiment_score * self.claude_weight
            if claude_signal.recommendation == "reverse" and claude_signal.confidence > 0.8:
                final_action = "HOLD"; final_qty = 0.0; ai_modified = True
                reasons.append(f"Claude REVERSED: {claude_signal.reasoning}")
            elif claude_signal.recommendation == "amplify_buy":
                final_qty = min(base_qty * 1.5, 1.0); ai_modified = True
            elif claude_signal.recommendation == "amplify_sell":
                final_qty = min(base_qty * 1.5, 0.3); ai_modified = True
            if claude_signal.recommendation != "reverse":
                reasons.append(f"Claude: {claude_signal.reasoning}")

        final_score = (base_score * self.base_weight) + deepseek_contrib + claude_contrib

        if final_score > 0.3 and final_action == "SELL":
            final_action = "HOLD"; ai_modified = True
            reasons.append("AI consensus overrides sell")
        elif final_score < -0.3 and final_action == "BUY":
            final_action = "HOLD"; ai_modified = True
            reasons.append("AI consensus overrides buy")

        return FinalSignal(symbol=symbol, action=final_action, quantity_pct=final_qty,
            reason=" | ".join(reasons), base_contribution=self.base_weight,
            deepseek_contribution=deepseek_contrib, claude_contribution=claude_contrib,
            ai_modified=ai_modified)