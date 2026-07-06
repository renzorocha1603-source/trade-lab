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
    Enhanced 5/10 Asymmetric Strategy - Pure Mathematical Core
    """

    def __init__(self, config):
        self.lookback = config.strategy.lookback_days
        self.loss_threshold = config.strategy.loss_threshold
        self.profit_threshold = config.strategy.profit_threshold
        self.buy_fraction = config.strategy.buy_fraction
        self.sell_fraction = config.strategy.sell_fraction
        self.vol_window = 20
        self.max_position_pct = getattr(config.strategy, 'max_position_pct', 0.25)
        self.min_volatility_filter = 0.60

    def calculate_return(self, price_series: pd.Series) -> Optional[float]:
        if len(price_series) < self.lookback + 1:
            return None
        start_price = price_series.iloc[-(self.lookback + 1)]
        current_price = price_series.iloc[-1]
        if start_price <= 0:
            return None
        return (current_price - start_price) / start_price

    def calculate_volatility(self, price_series: pd.Series) -> float:
        if len(price_series) < self.vol_window + 1:
            return 0.0
        returns = price_series.pct_change().dropna()
        return returns.iloc[-self.vol_window:].std() * np.sqrt(252)

    def generate_signal(self, symbol: str, price_series: pd.Series,
                       current_qty: float = 0) -> StrategySignal:

        period_return = self.calculate_return(price_series)
        volatility = self.calculate_volatility(price_series)
        current_price = price_series.iloc[-1] if len(price_series) > 0 else 0

        metrics = {
            "period_return": period_return,
            "volatility": volatility,
            "current_price": current_price
        }

        if volatility > self.min_volatility_filter:
            return StrategySignal(
                symbol=symbol,
                action=SignalAction.HOLD,
                quantity_pct=0.0,
                reason=f"High volatility filter ({volatility:.1%})",
                confidence=0.85,
                metrics=metrics
            )

        if period_return is None:
            return StrategySignal(symbol=symbol, action=SignalAction.HOLD,
                                  quantity_pct=0.0, reason="Insufficient data", metrics=metrics)

        if period_return <= self.loss_threshold:
            size = self.buy_fraction
            if volatility > 0.35:
                size *= 0.65
            return StrategySignal(
                symbol=symbol,
                action=SignalAction.BUY,
                quantity_pct=size,
                reason=f"5/10 Dip Buy: {period_return:.1%} decline over {self.lookback} days",
                confidence=0.78,
                metrics=metrics
            )

        elif period_return >= self.profit_threshold and current_qty > 0:
            return StrategySignal(
                symbol=symbol,
                action=SignalAction.SELL,
                quantity_pct=self.sell_fraction,
                reason=f"5/10 Profit Take: {period_return:.1%} gain",
                confidence=0.82,
                metrics=metrics
            )

        return StrategySignal(
            symbol=symbol,
            action=SignalAction.HOLD,
            quantity_pct=0.0,
            reason=f"No signal: {period_return:.1%} within neutral range",
            confidence=0.9,
            metrics=metrics
        )

    def get_stats(self) -> dict:
        return {
            "strategy": "Enhanced 5/10 Asymmetric",
            "lookback_days": self.lookback,
            "loss_threshold": f"{self.loss_threshold:.1%}",
            "profit_threshold": f"{self.profit_threshold:.1%}",
            "buy_fraction": f"{self.buy_fraction:.1%}",
            "sell_fraction": f"{self.sell_fraction:.1%}",
            "volatility_window": self.vol_window
        }