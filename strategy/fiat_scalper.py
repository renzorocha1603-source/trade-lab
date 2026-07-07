"""
Fiat Pennies Strategy — SMART TRAINING MODE
Looser thresholds for more real trading opportunities.
Same mathematical model as crypto, tuned for tighter spreads.
Data from Yahoo Finance (free, works everywhere).
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)


class FiatPenniesStrategy:
    """Pennies Strategy for Forex — SMART TRAINING MODE"""

    def __init__(self, config):
        self.config = config
        self.fiat_config = config.fiat
        self.atr_target = config.fiat.atr_multiplier_target
        self.atr_stop = config.fiat.atr_multiplier_stop
        self.max_hold = config.fiat.max_hold_hours
        self.kelly_frac = config.fiat.kelly_fraction
        self.min_volume_mult = 1.2
        self.fee_pct = config.fiat.fee_pct
        self.min_net_ev = config.fiat.min_net_ev

        # Looser thresholds for SMART TRAINING
        self.dip_vwap_threshold = -0.2
        self.momentum_vwap_threshold = 1.0
        self.rsi_max = 75
        self.bbw_min = 0.003

        self.active_positions = {}
        self.fiat_symbols = config.fiat.fiat_symbols

        logger.info(f"Fiat SMART MODE | {len(self.fiat_symbols)} pairs | Dip Z:<{self.dip_vwap_threshold} | Mom Z:>{self.momentum_vwap_threshold} | RSI<{self.rsi_max}")

    def fetch_yahoo_forex(self, symbol: str, period: str = "5d", interval: str = "1h") -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return None
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            logger.debug(f"Yahoo forex error: {e}")
            return None

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1: return 0.005
        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'
        high = df[high_col].values[-period-1:]
        low = df[low_col].values[-period-1:]
        close = df[close_col].values[-period-1:]
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = np.mean(tr) / close[-1] if close[-1] > 0 else 0.005
        return atr

    def calculate_vwap_zscore(self, df: pd.DataFrame, window: int = 24) -> float:
        if len(df) < window: return 0.0
        close_col = 'close' if 'close' in df.columns else 'Close'
        vol_col = 'volume' if 'volume' in df.columns else 'Volume'
        recent_close = df[close_col].iloc[-window:]
        recent_vol = df[vol_col].iloc[-window:] if vol_col in df.columns else pd.Series([1] * window)
        if recent_vol.sum() == 0: return 0.0
        vwap = (recent_close * recent_vol).sum() / recent_vol.sum()
        current = df[close_col].iloc[-1]
        deviations = recent_close - vwap
        std_dev = deviations.std()
        if std_dev == 0: return 0.0
        return (current - vwap) / std_dev

    def calculate_bollinger_width(self, df: pd.DataFrame, period: int = 20) -> float:
        if len(df) < period: return 0.01
        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col].values[-period:]
        sma = np.mean(close)
        std = np.std(close)
        upper = sma + (2 * std)
        lower = sma - (2 * std)
        width = (upper - lower) / sma
        return width

    def calculate_volume_ratio(self, df: pd.DataFrame, window: int = 20) -> float:
        if len(df) < window: return 1.0
        vol_col = 'volume' if 'volume' in df.columns else 'Volume'
        if vol_col not in df.columns: return 1.0
        current_vol = df[vol_col].iloc[-1]
        avg_vol = df[vol_col].iloc[-window:].mean()
        if avg_vol == 0: return 1.0
        return current_vol / avg_vol

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1: return 50.0
        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col].values[-period-1:]
        deltas = np.diff(close)
        gains = np.sum(deltas[deltas > 0]) / period
        losses = -np.sum(deltas[deltas < 0]) / period
        if losses == 0: return 100.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    def generate_signal(self, symbol: str) -> Optional[dict]:
        """Smart signal generation with looser thresholds"""
        df = self.fetch_yahoo_forex(symbol)
        if df is None or len(df) < 20:
            return None

        close_col = 'close' if 'close' in df.columns else 'Close'
        current_price = df[close_col].iloc[-1]

        atr = self.calculate_atr(df)
        vwap_z = self.calculate_vwap_zscore(df)
        bb_width = self.calculate_bollinger_width(df)
        vol_ratio = self.calculate_volume_ratio(df)
        rsi = self.calculate_rsi(df)

        logger.info(f"Fiat {symbol} | ${current_price:.4f} | Z:{vwap_z:.2f} | ATR:{atr:.3%} | BBW:{bb_width:.4f} | Vol:{vol_ratio:.1f}x | RSI:{rsi:.0f}")

        mode = None
        target_pct = 0
        stop_pct = 0

        # DIP MODE
        if vwap_z < self.dip_vwap_threshold and rsi < self.rsi_max and bb_width > self.bbw_min:
            mode = "DIP"
            target_pct = atr * self.atr_target
            stop_pct = atr * self.atr_stop

        # MOMENTUM MODE
        elif vwap_z > self.momentum_vwap_threshold and vol_ratio > 1.5 and rsi < self.rsi_max:
            mode = "MOMENTUM"
            target_pct = atr * 1.5
            stop_pct = atr * 0.6

        if mode is None:
            return None

        net_target = target_pct - (self.fee_pct * 2)
        net_risk = stop_pct + (self.fee_pct * 2)
        if net_target < self.min_net_ev: return None

        risk_reward = net_target / net_risk if net_risk > 0 else 0
        p_win = 0.52
        b_ratio = risk_reward
        kelly = (p_win * b_ratio - (1 - p_win)) / b_ratio if b_ratio > 0 else 0
        position_size = max(0.01, min(0.25, kelly * self.kelly_frac))

        return {
            "symbol": symbol, "action": "BUY", "mode": mode,
            "current_price": current_price, "data_source": "Yahoo",
            "quantity_pct": round(position_size, 4),
            "target_pct": round(target_pct, 4),
            "stop_pct": round(stop_pct, 4),
            "net_target": round(net_target, 4),
            "risk_reward": round(risk_reward, 2),
            "kelly": round(kelly, 3),
            "entry_time": datetime.now().isoformat(),
            "max_hold_hours": self.max_hold,
            "indicators": {"vwap_zscore": round(vwap_z, 3), "atr": round(atr, 4), "rsi": round(rsi, 1)},
            "reason": f"{mode} | Z:{vwap_z:.2f} | ATR:{atr:.3%} | RSI:{rsi:.0f}"
        }

    def should_exit(self, symbol: str, current_price: float, entry_price: float,
                   entry_time: str, target_pct: float, stop_pct: float) -> Optional[str]:
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct >= target_pct: return f"SELL (+{pnl_pct:.3%})"
        if pnl_pct <= -stop_pct: return f"SELL ({pnl_pct:.3%})"
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            hours_held = (datetime.now() - entry_dt).total_seconds() / 3600
            if hours_held >= self.max_hold: return f"SELL ({hours_held:.1f}h)"
        except: pass
        return None

    def get_stats(self) -> dict:
        return {
            "strategy": "Fiat Pennies — SMART TRAINING",
            "pairs": len(self.fiat_symbols),
            "dip_threshold": self.dip_vwap_threshold,
            "rsi_max": self.rsi_max,
        }