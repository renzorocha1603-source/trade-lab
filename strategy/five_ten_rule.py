"""
Core 5/10 Strategy - Pure mathematical rule.
Buy 5% more on dips, sell 10% on rallies.
No AI, just math.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategySignal:
    symbol: str
    action: SignalAction
    quantity_pct: float
    reason: str
    confidence: float = 1.0
    metrics: dict = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class FiveTenStrategy:
    """
    5/10 Asymmetric Position Sizing Strategy.

    Rules:
    - 10-day return < -3% → BUY 5% more
    - 10-day return > +5% → SELL 10%
    - Otherwise → HOLD

    Creates natural "buy low, sell high" rhythm.
    Sell fraction (10%) > Buy fraction (5%) = profit asymmetry.
    """

    def __init__(self, config):
        self.lookback = config.strategy.lookback_days
        self.loss_threshold = config.strategy.loss_threshold
        self.profit_threshold = config.strategy.profit_threshold
        self.buy_fraction = config.strategy.buy_fraction
        self.sell_fraction = config.strategy.sell_fraction

    def calculate_return(self, price_series: pd.Series) -> Optional[float]:
        if len(price_series) < self.lookback + 1:
            return None
        start = price_series.iloc[-(self.lookback + 1)]
        end = price_series.iloc[-1]
        if start <= 0:
            return None
        return (end - start) / start

    def generate_signal(self, symbol: str, price_series: pd.Series,
                       current_qty: float) -> StrategySignal:
        period_return = self.calculate_return(price_series)
        current_price = price_series.iloc[-1] if not price_series.empty else 0

        metrics = {"period_return": period_return, "current_price": current_price}

        if period_return is None:
            return StrategySignal(symbol=symbol, action=SignalAction.HOLD,
                                  quantity_pct=0.0, reason="Insufficient data",
                                  metrics=metrics)

        if period_return <= self.loss_threshold:
            if current_qty == 0:
                return StrategySignal(symbol=symbol, action=SignalAction.BUY,
                    quantity_pct=1.0,
                    reason=f"Initial entry: {period_return:.1%} decline in {self.lookback} days",
                    confidence=0.85, metrics=metrics)
            else:
                return StrategySignal(symbol=symbol, action=SignalAction.BUY,
                    quantity_pct=self.buy_fraction,
                    reason=f"Dip buy: {period_return:.1%} (threshold: {self.loss_threshold:.1%})",
                    confidence=0.75, metrics=metrics)

        elif period_return >= self.profit_threshold and current_qty > 0:
            return StrategySignal(symbol=symbol, action=SignalAction.SELL,
                quantity_pct=self.sell_fraction,
                reason=f"Profit take: {period_return:.1%} (threshold: {self.profit_threshold:.1%})",
                confidence=0.75, metrics=metrics)

        return StrategySignal(symbol=symbol, action=SignalAction.HOLD,
            quantity_pct=0.0,
            reason=f"No signal: {period_return:.1%} within range",
            confidence=0.9, metrics=metrics)

    def get_stats(self) -> dict:
        return {
            "name": "5/10 Asymmetric Strategy",
            "lookback_days": self.lookback,
            "loss_threshold": f"{self.loss_threshold:.1%}",
            "profit_threshold": f"{self.profit_threshold:.1%}",
            "buy_fraction": f"{self.buy_fraction:.1%}",
            "sell_fraction": f"{self.sell_fraction:.1%}"
        }