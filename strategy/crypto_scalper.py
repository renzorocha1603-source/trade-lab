"""
Crypto Pennies Strategy v2.8 — SMART TRAINING MODE
Looser thresholds for more real trading opportunities.
Dual Mode: Dip Buying + Momentum Riding + Breakout entries.
24/7 trading — Letta learns from genuine signals.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)


class CryptoPenniesStrategy:
    """Pennies Strategy for Crypto — SMART TRAINING MODE"""

    def __init__(self, config):
        self.config = config
        self.crypto_config = config.crypto

        self.atr_target = 1.2
        self.atr_stop = 0.8
        self.max_hold = 3.0
        self.kelly_frac = 0.5
        self.min_volume_mult = 1.2
        self.fee_pct = config.crypto.fee_pct
        self.min_net_ev = 0.002

        # Looser thresholds for SMART TRAINING
        self.dip_vwap_threshold = -0.3
        self.momentum_vwap_threshold = 1.0
        self.bbw_min = 0.01
        self.bbw_max = 0.25
        self.rsi_max = 78
        self.risk_reward_min = 0.4
        self.max_positions = 10

        self.active_positions = {}
        self._market_cap_cache = {}
        self._market_cap_cache_time = None

        self.crypto_symbols = [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "ADA-USD", "AVAX-USD", "DOT-USD", "LINK-USD",
            "ATOM-USD", "XLM-USD", "FIL-USD", "NEAR-USD",
            "ALGO-USD", "VET-USD", "ICP-USD"
        ]

        logger.info(f"Crypto SMART MODE | {len(self.crypto_symbols)} symbols | Dip Z:<{self.dip_vwap_threshold} | Mom Z:>{self.momentum_vwap_threshold} | RSI<{self.rsi_max}")

    # ==================== DATA SOURCES ====================

    def fetch_binance_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        try:
            binance_symbol = symbol.replace("-USD", "USDT")
            url = f"https://api.binance.com/api/v3/klines"
            params = {"symbol": binance_symbol, "interval": interval, "limit": limit}
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if not data or "code" in data:
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
            logger.debug(f"Binance error: {e}")
            return None

    def fetch_yahoo_crypto(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            period_map = {"1h": "5d", "15m": "5d", "4h": "1mo", "1d": "3mo"}
            period = period_map.get(interval, "5d")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return None
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            logger.debug(f"Yahoo error: {e}")
            return None

    def fetch_coingecko_data(self, symbol: str) -> Optional[dict]:
        try:
            coin_map = {
                "BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana",
                "XRP-USD": "ripple", "DOGE-USD": "dogecoin", "ADA-USD": "cardano",
                "AVAX-USD": "avalanche-2", "DOT-USD": "polkadot", "LINK-USD": "chainlink",
                "ATOM-USD": "cosmos", "XLM-USD": "stellar", "FIL-USD": "filecoin",
                "NEAR-USD": "near", "ALGO-USD": "algorand", "VET-USD": "vechain",
                "ICP-USD": "internet-computer"
            }
            coin_id = coin_map.get(symbol, symbol.lower().replace("-usd", ""))
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": coin_id, "vs_currencies": "usd", "include_market_cap": "true", "include_24hr_vol": "true", "include_24hr_change": "true"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                return None
            data = resp.json()
            coin_data = data.get(coin_id, {})
            if coin_data:
                self._market_cap_cache[symbol] = coin_data.get("usd_market_cap")
                self._market_cap_cache[f"{symbol}_volume"] = coin_data.get("usd_24h_vol")
                self._market_cap_cache[f"{symbol}_change"] = coin_data.get("usd_24h_change")
                self._market_cap_cache_time = datetime.now()
            return coin_data
        except Exception as e:
            logger.debug(f"CoinGecko error: {e}")
            return None

    def get_market_cap_rank(self, symbol: str) -> str:
        market_cap = self._market_cap_cache.get(symbol)
        if market_cap is None: return "unknown"
        if market_cap > 500_000_000_000: return "mega_cap"
        elif market_cap > 100_000_000_000: return "large_cap"
        elif market_cap > 10_000_000_000: return "mid_cap"
        elif market_cap > 1_000_000_000: return "small_cap"
        else: return "micro_cap"

    # ==================== TECHNICAL INDICATORS ====================

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1: return 0.02
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
        atr = np.mean(tr) / close[-1] if close[-1] > 0 else 0.02
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
        if len(df) < period: return 0.03
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

    # ==================== SIGNAL GENERATION (SMART TRAINING) ====================

    def generate_signal(self, symbol: str, price_history: pd.Series = None) -> Optional[dict]:
        """Smart signal generation with looser thresholds for training"""

        high_vol_coins = ["DOGE-USD", "SOL-USD", "AVAX-USD", "NEAR-USD", "ICP-USD"]
        if symbol in high_vol_coins:
            interval = "15m"
        elif "BTC" in symbol:
            interval = "1h"
        else:
            interval = "30m"

        df = self.fetch_binance_klines(symbol, interval)
        data_source = "Binance"
        if df is None or len(df) < 20:
            df = self.fetch_yahoo_crypto(symbol, interval)
            data_source = "Yahoo"
        if df is None or len(df) < 15:
            return None

        close_col = 'close' if 'close' in df.columns else 'Close'
        current_price = df[close_col].iloc[-1]

        atr = self.calculate_atr(df)
        vwap_z = self.calculate_vwap_zscore(df)
        bb_width = self.calculate_bollinger_width(df)
        vol_ratio = self.calculate_volume_ratio(df)
        rsi = self.calculate_rsi(df)

        self.fetch_coingecko_data(symbol)
        cap_tier = self.get_market_cap_rank(symbol)

        logger.info(f"{symbol} [{data_source}] | ${current_price:.2f} | Z:{vwap_z:.2f} | ATR:{atr:.2%} | BBW:{bb_width:.3f} | Vol:{vol_ratio:.1f}x | RSI:{rsi:.0f} | {cap_tier}")

        mode = None
        target_pct = 0
        stop_pct = 0
        position_multiplier = 1.0

        # MODE 1: DIP BUYING
        if vwap_z < self.dip_vwap_threshold and rsi < self.rsi_max and bb_width > self.bbw_min:
            mode = "DIP"
            target_pct = atr * self.atr_target
            stop_pct = atr * self.atr_stop
            if vwap_z < -1.5: position_multiplier = 1.5
            elif vwap_z < -1.0: position_multiplier = 1.2

        # MODE 2: MOMENTUM RIDING
        elif vwap_z > self.momentum_vwap_threshold and vol_ratio > self.min_volume_mult and rsi < self.rsi_max and bb_width > self.bbw_min:
            mode = "MOMENTUM"
            target_pct = atr * 0.8
            stop_pct = atr * 0.5
            position_multiplier = 0.8

        # MODE 3: BREAKOUT
        elif bb_width < self.bbw_min and vol_ratio > 2.5 and rsi > 50:
            mode = "BREAKOUT"
            target_pct = atr * 1.5
            stop_pct = atr * 0.6
            position_multiplier = 1.3

        if mode is None:
            return None

        cap_multiplier = {"mega_cap": 1.0, "large_cap": 0.9, "mid_cap": 0.7, "small_cap": 0.5, "micro_cap": 0.3, "unknown": 0.3}
        tier_mult = cap_multiplier.get(cap_tier, 0.3)
        if atr > 0.06: tier_mult *= 0.6

        net_target = target_pct - (self.fee_pct * 2)
        net_risk = stop_pct + (self.fee_pct * 2)
        if net_target < self.min_net_ev: return None

        risk_reward = net_target / net_risk if net_risk > 0 else 0
        if risk_reward < self.risk_reward_min: return None

        p_win = 0.52
        b_ratio = risk_reward
        kelly = (p_win * b_ratio - (1 - p_win)) / b_ratio if b_ratio > 0 else 0
        position_size = max(0.01, min(0.25, kelly * self.kelly_frac * tier_mult * position_multiplier))

        return {
            "symbol": symbol, "action": "BUY", "mode": mode,
            "current_price": current_price, "data_source": data_source,
            "quantity_pct": round(position_size, 4),
            "target_pct": round(target_pct, 4),
            "stop_pct": round(stop_pct, 4),
            "net_target": round(net_target, 4),
            "risk_reward": round(risk_reward, 2),
            "kelly": round(kelly, 3),
            "entry_time": datetime.now().isoformat(),
            "max_hold_hours": self.max_hold,
            "market_cap_tier": cap_tier,
            "indicators": {"vwap_zscore": round(vwap_z, 3), "atr": round(atr, 4), "bb_width": round(bb_width, 4), "vol_ratio": round(vol_ratio, 2), "rsi": round(rsi, 1)},
            "reason": f"{mode} | Z:{vwap_z:.2f} | ATR:{atr:.2%} | Vol:{vol_ratio:.1f}x | RSI:{rsi:.0f} | {cap_tier}"
        }

    def should_exit(self, symbol: str, current_price: float, entry_price: float,
                   entry_time: str, target_pct: float, stop_pct: float) -> Optional[str]:
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct >= target_pct: return f"SELL (+{pnl_pct:.2%})"
        if pnl_pct <= -stop_pct: return f"SELL ({pnl_pct:.2%})"
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            hours_held = (datetime.now() - entry_dt).total_seconds() / 3600
            if hours_held >= self.max_hold: return f"SELL ({hours_held:.1f}h)"
        except: pass
        return None

    def get_stats(self) -> dict:
        return {
            "strategy": "Crypto Pennies — SMART TRAINING",
            "symbols": len(self.crypto_symbols),
            "max_positions": self.max_positions,
            "dip_threshold": self.dip_vwap_threshold,
            "momentum_threshold": self.momentum_vwap_threshold,
            "rsi_max": self.rsi_max,
        }