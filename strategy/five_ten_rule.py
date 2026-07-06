"""
Enhanced 5/10 Asymmetric Strategy with Z-Score, Sharpe, and Kelly.
Mathematically precise entries and exits.
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
    z_score: float = 0.0
    sharpe: float = 0.0

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class FiveTenStrategy:
    """Enhanced 5/10 Strategy with Z-Score and Sharpe Ratio"""

    def __init__(self, config):
        self.lookback = config.strategy.lookback_days
        self.loss_threshold = config.strategy.loss_threshold
        self.profit_threshold = config.strategy.profit_threshold
        self.buy_fraction = config.strategy.buy_fraction
        self.sell_fraction = config.strategy.sell_fraction
        self.vol_window = 20
        self.max_position_pct = getattr(config.strategy, 'max_position_pct', 0.25)
        self.min_volatility_filter = 0.60
        self.z_lookback = getattr(config.strategy, 'z_score_lookback', 252)
        self.sharpe_lookback = getattr(config.strategy, 'sharpe_lookback', 60)

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

    def calculate_z_score(self, price_series: pd.Series) -> float:
        """Z-Score of current 10-day return vs historical distribution"""
        if len(price_series) < self.z_lookback + self.lookback:
            return 0.0
        
        # Calculate rolling 10-day returns
        returns_10d = []
        for i in range(self.lookback, len(price_series)):
            ret = (price_series.iloc[i] - price_series.iloc[i - self.lookback]) / price_series.iloc[i - self.lookback]
            returns_10d.append(ret)
        
        if len(returns_10d) < 20:
            return 0.0
        
        current_return = returns_10d[-1]
        mean_return = np.mean(returns_10d)
        std_return = np.std(returns_10d)
        
        if std_return == 0:
            return 0.0
        
        return (current_return - mean_return) / std_return

    def calculate_sharpe(self, price_series: pd.Series) -> float:
        """Sharpe Ratio of recent returns"""
        if len(price_series) < self.sharpe_lookback + 1:
            return 0.0
        
        returns = price_series.pct_change().dropna().iloc[-self.sharpe_lookback:]
        
        if len(returns) < 20 or returns.std() == 0:
            return 0.0
        
        avg_return = returns.mean() * 252  # Annualized
        std_return = returns.std() * np.sqrt(252)
        
        return avg_return / std_return

    def calculate_kelly_position(self, z_score: float, sharpe: float, profile: dict) -> float:
        """Kelly-optimized position size"""
        # Base win probability from Z-Score
        # Z = -2 → ~98% of moves are worse → high win probability
        # Z = -1 → ~84% of moves are worse → medium win probability
        from scipy import stats
        p_win = stats.norm.cdf(abs(z_score))  # Probability this is an extreme move
        
        # Adjust by Sharpe quality
        if sharpe > 1.0:
            p_win = min(0.75, p_win * 1.2)
        elif sharpe < 0.3:
            p_win = max(0.40, p_win * 0.7)
        
        # b_ratio from profile risk/reward settings
        b_ratio = abs(self.profit_threshold / self.loss_threshold)  # ~1.67 for 5%/3%
        
        # Kelly formula
        q_loss = 1 - p_win
        kelly = (p_win * b_ratio - q_loss) / b_ratio if b_ratio > 0 else 0
        
        # Apply Kelly fraction from profile
        kelly_frac = profile.get("kelly_fraction", 0.5)
        position = max(0.01, min(self.max_position_pct, kelly * kelly_frac))
        
        return round(position, 4)

    def generate_signal(self, symbol: str, price_series: pd.Series,
                       current_qty: float = 0, profile: dict = None) -> StrategySignal:

        period_return = self.calculate_return(price_series)
        volatility = self.calculate_volatility(price_series)
        z_score = self.calculate_z_score(price_series)
        sharpe = self.calculate_sharpe(price_series)
        current_price = price_series.iloc[-1] if len(price_series) > 0 else 0

        metrics = {
            "period_return": period_return,
            "volatility": volatility,
            "current_price": current_price,
            "z_score": z_score,
            "sharpe": sharpe,
        }

        # Default profile if none provided
        if profile is None:
            profile = {"z_score_threshold": -1.5, "kelly_fraction": 0.5}

        if volatility > self.min_volatility_filter:
            return StrategySignal(symbol=symbol, action=SignalAction.HOLD, quantity_pct=0.0,
                reason=f"High volatility ({volatility:.1%})", confidence=0.85, metrics=metrics,
                z_score=z_score, sharpe=sharpe)

        if period_return is None:
            return StrategySignal(symbol=symbol, action=SignalAction.HOLD, quantity_pct=0.0,
                reason="Insufficient data", metrics=metrics, z_score=z_score, sharpe=sharpe)

        z_threshold = profile.get("z_score_threshold", -1.5)
        
        # Z-Score based entry (replaces fixed -3% threshold)
        if z_score <= z_threshold and period_return < 0:
            position_size = self.calculate_kelly_position(z_score, sharpe, profile)
            return StrategySignal(symbol=symbol, action=SignalAction.BUY, quantity_pct=position_size,
                reason=f"Z-Score entry: {z_score:.2f} (threshold: {z_threshold}) | Sharpe: {sharpe:.2f}",
                confidence=0.78, metrics=metrics, z_score=z_score, sharpe=sharpe)

        # Profit taking (keep the +5% rule but enhanced with Z-Score)
        elif period_return >= self.profit_threshold and current_qty > 0 and z_score > 1.5:
            return StrategySignal(symbol=symbol, action=SignalAction.SELL, quantity_pct=self.sell_fraction,
                reason=f"Profit take: {period_return:.1%} | Z-Score: {z_score:.2f} (extended)",
                confidence=0.82, metrics=metrics, z_score=z_score, sharpe=sharpe)

        return StrategySignal(symbol=symbol, action=SignalAction.HOLD, quantity_pct=0.0,
            reason=f"No signal: Z={z_score:.2f} Sharpe={sharpe:.2f}", confidence=0.9,
            metrics=metrics, z_score=z_score, sharpe=sharpe)

    def get_stats(self) -> dict:
        return {
            "strategy": "Enhanced 5/10 with Z-Score & Sharpe",
            "lookback_days": self.lookback,
            "z_score_lookback": self.z_lookback,
            "sharpe_lookback": self.sharpe_lookback,
        }