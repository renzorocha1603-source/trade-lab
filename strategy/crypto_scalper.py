"""
Crypto Pennies Strategy — Small consistent wins compound into big returns.
24/7 trading with fee-aware math, VWAP Z-Score, Bollinger Bands, ATR stops.
Separate from stock strategy — completely different mathematical model.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)


class CryptoPenniesStrategy:
    """
    Pennies Strategy for Crypto
    Entry: VWAP Z-Score + Volume confirmation + Bollinger Band filter
    Exit: ATR-based target + ATR-based stop + Time stop
    Sizing: Kelly Criterion × 0.3
    """

    def __init__(self, config):
        self.config = config
        self.crypto_config = config.crypto
        self.atr_target = config.crypto.atr_multiplier_target
        self.atr_stop = config.crypto.atr_multiplier_stop
        self.max_hold = config.crypto.max_hold_hours
        self.kelly_frac = config.crypto.kelly_fraction
        self.min_volume_mult = config.crypto.min_volume_multiplier
        self.fee_pct = config.crypto.fee_pct
        self.min_net_ev = config.crypto.min_net_ev
        
        # Track active positions
        self.active_positions = {}
        
        logger.info(f"Crypto Pennies Strategy initialized | Target: {self.atr_target}× ATR | Stop: {self.atr_stop}× ATR | Max Hold: {self.max_hold}h")

    # ==================== DATA FETCHING ====================

    def fetch_binance_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Binance public API (free, no key needed)"""
        try:
            # Convert BTC-USD to BTCUSDT for Binance
            binance_symbol = symbol.replace("-USD", "USDT")
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": binance_symbol,
                "interval": interval,
                "limit": limit
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if not data or "code" in data:
                logger.warning(f"Binance error for {binance_symbol}: {data}")
                return None
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df['close'] = pd.to_numeric(df['close'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['volume'] = pd.to_numeric(df['volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        except Exception as e:
            logger.error(f"Binance fetch error: {e}")
            return None

    # ==================== TECHNICAL INDICATORS ====================

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range"""
        if len(df) < period:
            return 0.02
        
        high = df['high'].values[-period:]
        low = df['low'].values[-period:]
        close = df['close'].values[-period-1:-1] if len(df) > period else df['close'].values[:-1]
        
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close)
        tr3 = np.abs(low[1:] - close)
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        atr = np.mean(tr) / df['close'].iloc[-1]
        return atr

    def calculate_vwap_zscore(self, df: pd.DataFrame, window: int = 24) -> float:
        """Z-Score of current price vs Volume-Weighted Average Price"""
        if len(df) < window:
            return 0.0
        
        recent = df.iloc[-window:]
        vwap = (recent['close'] * recent['volume']).sum() / recent['volume'].sum()
        current = df['close'].iloc[-1]
        
        # Calculate standard deviation of price from VWAP
        deviations = recent['close'] - vwap
        std_dev = deviations.std()
        
        if std_dev == 0:
            return 0.0
        
        z_score = (current - vwap) / std_dev
        return z_score

    def calculate_bollinger_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Bollinger Band Width — measures volatility compression"""
        if len(df) < period:
            return 0.03
        
        close = df['close'].values[-period:]
        sma = np.mean(close)
        std = np.std(close)
        
        upper = sma + (2 * std)
        lower = sma - (2 * std)
        
        width = (upper - lower) / sma
        return width

    def calculate_volume_ratio(self, df: pd.DataFrame, window: int = 20) -> float:
        """Current volume vs average volume"""
        if len(df) < window:
            return 1.0
        
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].iloc[-window:].mean()
        
        if avg_vol == 0:
            return 1.0
        
        return current_vol / avg_vol

    # ==================== SIGNAL GENERATION ====================

    def generate_signal(self, symbol: str) -> Optional[dict]:
        """Generate a trading signal for crypto"""
        
        # Use different timeframes for BTC vs ETH
        if "BTC" in symbol:
            interval = self.crypto_config.btc_timeframe
        else:
            interval = self.crypto_config.eth_timeframe
        
        df = self.fetch_binance_klines(symbol, interval)
        if df is None or len(df) < 30:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Calculate indicators
        atr = self.calculate_atr(df)
        vwap_z = self.calculate_vwap_zscore(df)
        bb_width = self.calculate_bollinger_width(df)
        vol_ratio = self.calculate_volume_ratio(df)
        
        logger.info(f"Crypto {symbol} | Price: ${current_price:.2f} | VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | BBW: {bb_width:.3f} | Vol: {vol_ratio:.1f}x")
        
        # Entry conditions
        entry_conditions = {
            "vwap_zscore_ok": vwap_z < -1.5,
            "volume_ok": vol_ratio > self.min_volume_mult,
            "bollinger_ok": bb_width > 0.02,  # Bands wide enough to trade
            "not_extreme": bb_width < 0.15,   # Not in crazy volatility
        }
        
        all_pass = all(entry_conditions.values())
        
        if not all_pass:
            failed = [k for k, v in entry_conditions.items() if not v]
            logger.debug(f"Crypto {symbol}: Conditions not met — {failed}")
            return None
        
        # Calculate profit target and stop loss
        target_pct = atr * self.atr_target
        stop_pct = atr * self.atr_stop
        
        # Fee-aware check
        net_target = target_pct - (self.fee_pct * 2)  # Buy + sell fees
        net_risk = stop_pct + (self.fee_pct * 2)
        
        if net_target < self.min_net_ev:
            logger.debug(f"Crypto {symbol}: Net target {net_target:.3%} < min EV {self.min_net_ev:.3%}")
            return None
        
        # Calculate risk/reward
        risk_reward = net_target / net_risk if net_risk > 0 else 0
        
        # Kelly position sizing
        # Assume 55% win rate as baseline (Letta will refine)
        p_win = 0.55
        b_ratio = risk_reward
        kelly = (p_win * b_ratio - (1 - p_win)) / b_ratio if b_ratio > 0 else 0
        position_size = max(0.01, min(0.20, kelly * self.kelly_frac))
        
        return {
            "symbol": symbol,
            "action": "BUY",
            "current_price": current_price,
            "quantity_pct": round(position_size, 4),
            "target_pct": round(target_pct, 4),
            "stop_pct": round(stop_pct, 4),
            "net_target": round(net_target, 4),
            "risk_reward": round(risk_reward, 2),
            "kelly": round(kelly, 3),
            "entry_time": datetime.now().isoformat(),
            "max_hold_hours": self.max_hold,
            "indicators": {
                "vwap_zscore": round(vwap_z, 3),
                "atr": round(atr, 4),
                "bb_width": round(bb_width, 4),
                "vol_ratio": round(vol_ratio, 2),
            },
            "reason": f"VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | Vol: {vol_ratio:.1f}x | R:R 1:{risk_reward:.1f}"
        }

    # ==================== EXIT CHECK ====================

    def should_exit(self, symbol: str, current_price: float, entry_price: float,
                   entry_time: str, target_pct: float, stop_pct: float) -> Optional[str]:
        """Check if we should exit a position"""
        
        pnl_pct = (current_price - entry_price) / entry_price
        
        # Take profit
        if pnl_pct >= target_pct:
            return f"SELL (profit target hit: +{pnl_pct:.2%})"
        
        # Stop loss
        if pnl_pct <= -stop_pct:
            return f"SELL (stop loss hit: {pnl_pct:.2%})"
        
        # Time stop
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            hours_held = (datetime.now() - entry_dt).total_seconds() / 3600
            if hours_held >= self.max_hold:
                return f"SELL (time stop: held for {hours_held:.1f}h, max {self.max_hold}h)"
        except:
            pass
        
        return None  # Hold

    def get_stats(self) -> dict:
        return {
            "strategy": "Crypto Pennies Scalping",
            "atr_target_multiplier": self.atr_target,
            "atr_stop_multiplier": self.atr_stop,
            "max_hold_hours": self.max_hold,
            "kelly_fraction": self.kelly_frac,
            "fee_pct": self.fee_pct,
            "min_net_ev": self.min_net_ev,
        }