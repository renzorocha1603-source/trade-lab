"""
Crypto Pennies Strategy v2.0 — Dual Mode: Dip Buying + Momentum Riding
24/7 trading with fee-aware math, VWAP Z-Score, Bollinger Bands, ATR stops.
Includes market cap data from CoinGecko (free, no API key).
Uses Yahoo Finance for price data when Binance is blocked.
Trades top 20 cryptos by market cap.
DIP MODE: Buy when price below VWAP (oversold)
MOMENTUM MODE: Buy when price above VWAP with strong volume (breakout)
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
    Pennies Strategy v2.0 — Dual Mode Crypto Trading
    DIP MODE: VWAP-Z < -0.8 + volume + BB width + RSI not overbought
    MOMENTUM MODE: VWAP-Z > 2.0 + strong volume + RSI not extreme
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

        self.active_positions = {}
        self._market_cap_cache = {}
        self._market_cap_cache_time = None

        self.crypto_symbols = [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "ADA-USD", "AVAX-USD", "DOT-USD", "MATIC-USD", "LINK-USD",
            "UNI-USD", "ATOM-USD", "XLM-USD", "FIL-USD", "NEAR-USD",
            "ALGO-USD", "VET-USD", "ICP-USD", "GRT-USD", "FTM-USD"
        ]

        logger.info(f"Crypto Pennies v2.0 | {len(self.crypto_symbols)} symbols | Dual Mode: Dip + Momentum | Target: {self.atr_target}× ATR | Stop: {self.atr_stop}× ATR | Max Hold: {self.max_hold}h | Fees: {self.fee_pct:.2%}")

    # ==================== DATA SOURCES ====================

    def fetch_binance_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Binance public API (free, no key needed)"""
        try:
            binance_symbol = symbol.replace("-USD", "USDT")
            url = f"https://api.binance.com/api/v3/klines"
            params = {"symbol": binance_symbol, "interval": interval, "limit": limit}
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if not data or "code" in data:
                logger.debug(f"Binance blocked for {binance_symbol}")
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
            logger.debug(f"Binance fetch error: {e}")
            return None

    def fetch_yahoo_crypto(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch crypto data from Yahoo Finance (works everywhere)"""
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
            logger.debug(f"Yahoo crypto fetch error: {e}")
            return None

    def fetch_coingecko_data(self, symbol: str) -> Optional[dict]:
        """Fetch price, market cap, volume from CoinGecko (free, no key)"""
        try:
            coin_map = {
                "BTC-USD": "bitcoin", "ETH-USD": "ethereum", "SOL-USD": "solana",
                "XRP-USD": "ripple", "DOGE-USD": "dogecoin", "ADA-USD": "cardano",
                "AVAX-USD": "avalanche-2", "DOT-USD": "polkadot", "MATIC-USD": "matic-network",
                "LINK-USD": "chainlink", "UNI-USD": "uniswap", "ATOM-USD": "cosmos",
                "XLM-USD": "stellar", "FIL-USD": "filecoin", "NEAR-USD": "near",
                "ALGO-USD": "algorand", "VET-USD": "vechain", "ICP-USD": "internet-computer",
                "GRT-USD": "the-graph", "FTM-USD": "fantom"
            }
            coin_id = coin_map.get(symbol, symbol.lower().replace("-usd", ""))

            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true"
            }
            resp = requests.get(url, params=params, timeout=10)

            if resp.status_code == 429:
                logger.warning("CoinGecko rate limit hit")
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
            logger.debug(f"CoinGecko error for {symbol}: {e}")
            return None

    def get_market_cap_rank(self, symbol: str) -> str:
        """Get market cap tier for risk assessment"""
        market_cap = self._market_cap_cache.get(symbol)

        if market_cap is None:
            return "unknown"

        if market_cap > 500_000_000_000:
            return "mega_cap"
        elif market_cap > 100_000_000_000:
            return "large_cap"
        elif market_cap > 10_000_000_000:
            return "mid_cap"
        elif market_cap > 1_000_000_000:
            return "small_cap"
        else:
            return "micro_cap"

    # ==================== TECHNICAL INDICATORS ====================

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range"""
        if len(df) < period + 1:
            return 0.02

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
        """Z-Score of current price vs Volume-Weighted Average Price"""
        if len(df) < window:
            return 0.0

        close_col = 'close' if 'close' in df.columns else 'Close'
        vol_col = 'volume' if 'volume' in df.columns else 'Volume'

        recent_close = df[close_col].iloc[-window:]
        recent_vol = df[vol_col].iloc[-window:] if vol_col in df.columns else pd.Series([1] * window)

        if recent_vol.sum() == 0:
            return 0.0

        vwap = (recent_close * recent_vol).sum() / recent_vol.sum()
        current = df[close_col].iloc[-1]

        deviations = recent_close - vwap
        std_dev = deviations.std()

        if std_dev == 0:
            return 0.0

        return (current - vwap) / std_dev

    def calculate_bollinger_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Bollinger Band Width"""
        if len(df) < period:
            return 0.03

        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col].values[-period:]
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

        vol_col = 'volume' if 'volume' in df.columns else 'Volume'
        if vol_col not in df.columns:
            return 1.0

        current_vol = df[vol_col].iloc[-1]
        avg_vol = df[vol_col].iloc[-window:].mean()

        if avg_vol == 0:
            return 1.0

        return current_vol / avg_vol

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """RSI"""
        if len(df) < period + 1:
            return 50.0

        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col].values[-period-1:]
        deltas = np.diff(close)
        gains = np.sum(deltas[deltas > 0]) / period
        losses = -np.sum(deltas[deltas < 0]) / period

        if losses == 0:
            return 100.0

        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    # ==================== SIGNAL GENERATION (DUAL MODE) ====================

    def generate_signal(self, symbol: str, price_history: pd.Series = None) -> Optional[dict]:
        """Generate a trading signal — DIP MODE or MOMENTUM MODE"""

        high_vol_coins = ["DOGE-USD", "SOL-USD", "AVAX-USD", "NEAR-USD", "GRT-USD", "FTM-USD"]
        if symbol in high_vol_coins:
            interval = "15m"
        elif "BTC" in symbol:
            interval = self.crypto_config.btc_timeframe
        elif "ETH" in symbol:
            interval = self.crypto_config.eth_timeframe
        else:
            interval = "1h"

        df = self.fetch_binance_klines(symbol, interval)
        data_source = "Binance"

        if df is None or len(df) < 30:
            df = self.fetch_yahoo_crypto(symbol, interval)
            data_source = "Yahoo Finance"

        if df is None or len(df) < 20:
            logger.debug(f"Crypto {symbol}: Insufficient data")
            return None

        close_col = 'close' if 'close' in df.columns else 'Close'
        current_price = df[close_col].iloc[-1]

        atr = self.calculate_atr(df)
        vwap_z = self.calculate_vwap_zscore(df)
        bb_width = self.calculate_bollinger_width(df)
        vol_ratio = self.calculate_volume_ratio(df)
        rsi = self.calculate_rsi(df)

        self.fetch_coingecko_data(symbol)
        market_cap = self._market_cap_cache.get(symbol)
        cap_tier = self.get_market_cap_rank(symbol)
        volume_24h = self._market_cap_cache.get(f"{symbol}_volume")
        change_24h = self._market_cap_cache.get(f"{symbol}_change")

        # ==================== MODE SELECTION ====================

        mode = None
        target_pct = 0
        stop_pct = 0

        # DIP MODE: Price below VWAP, oversold, good volume
        dip_conditions = (
            vwap_z < -0.8 and
            rsi < 65 and
            bb_width > 0.02 and
            vol_ratio > self.min_volume_mult and
            cap_tier in ["mega_cap", "large_cap", "mid_cap", "small_cap"]
        )

        # MOMENTUM MODE: Price above VWAP, strong volume, breaking out
        momentum_conditions = (
            vwap_z > 1.5 and
            vol_ratio > 2.0 and
            rsi < 75 and
            bb_width > 0.02 and
            cap_tier in ["mega_cap", "large_cap", "mid_cap", "small_cap"]
        )

        if dip_conditions:
            mode = "DIP"
            target_pct = atr * self.atr_target
            stop_pct = atr * self.atr_stop
        elif momentum_conditions:
            mode = "MOMENTUM"
            target_pct = atr * 1.0  # Smaller target for momentum
            stop_pct = atr * 0.5    # Tighter stop for momentum
        else:
            failed_dip = [
                f"VWAP-Z:{vwap_z:.2f}(<-0.8)" if vwap_z >= -0.8 else "",
                f"RSI:{rsi:.0f}(<65)" if rsi >= 65 else "",
                f"BBW:{bb_width:.3f}(>0.02)" if bb_width <= 0.02 else "",
                f"Vol:{vol_ratio:.1f}x(>{self.min_volume_mult})" if vol_ratio <= self.min_volume_mult else "",
            ]
            failed_mom = [
                f"VWAP-Z:{vwap_z:.2f}(>1.5)" if vwap_z <= 1.5 else "",
                f"Vol:{vol_ratio:.1f}x(>2.0)" if vol_ratio <= 2.0 else "",
                f"RSI:{rsi:.0f}(<75)" if rsi >= 75 else "",
            ]
            failed_dip = [f for f in failed_dip if f]
            failed_mom = [f for f in failed_mom if f]
            if failed_dip or failed_mom:
                logger.debug(f"Crypto {symbol}: DIP({','.join(failed_dip[:2])}) | MOM({','.join(failed_mom[:2])})")
            return None

        # ==================== POSITION SIZING ====================

        cap_multiplier = {
            "mega_cap": 1.0, "large_cap": 0.9, "mid_cap": 0.6,
            "small_cap": 0.4, "micro_cap": 0.2, "unknown": 0.3
        }

        if atr > 0.05:
            cap_multiplier[cap_tier] *= 0.7

        net_target = target_pct - (self.fee_pct * 2)
        net_risk = stop_pct + (self.fee_pct * 2)

        if net_target < self.min_net_ev:
            logger.debug(f"Crypto {symbol}: Net target {net_target:.3%} < min EV")
            return None

        risk_reward = net_target / net_risk if net_risk > 0 else 0

        if risk_reward < 0.6:
            logger.debug(f"Crypto {symbol}: Poor R:R {risk_reward:.2f}")
            return None

        p_win = 0.55
        b_ratio = risk_reward
        kelly = (p_win * b_ratio - (1 - p_win)) / b_ratio if b_ratio > 0 else 0
        position_size = max(0.01, min(0.20, kelly * self.kelly_frac * cap_multiplier.get(cap_tier, 0.5)))

        logger.info(f"Crypto {symbol} [{data_source}] | {mode} MODE | ${current_price:.2f} | VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | Vol: {vol_ratio:.1f}x | RSI: {rsi:.0f} | Size: {position_size:.1%} | Target: {target_pct:.2%} | Stop: {stop_pct:.2%}")

        return {
            "symbol": symbol,
            "action": "BUY",
            "mode": mode,
            "current_price": current_price,
            "data_source": data_source,
            "quantity_pct": round(position_size, 4),
            "target_pct": round(target_pct, 4),
            "stop_pct": round(stop_pct, 4),
            "net_target": round(net_target, 4),
            "risk_reward": round(risk_reward, 2),
            "kelly": round(kelly, 3),
            "entry_time": datetime.now().isoformat(),
            "max_hold_hours": self.max_hold,
            "market_cap": market_cap,
            "market_cap_tier": cap_tier,
            "indicators": {
                "vwap_zscore": round(vwap_z, 3),
                "atr": round(atr, 4),
                "bb_width": round(bb_width, 4),
                "vol_ratio": round(vol_ratio, 2),
                "rsi": round(rsi, 1),
            },
            "reason": f"[{mode}] VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | Vol: {vol_ratio:.1f}x | RSI: {rsi:.0f} | {data_source}"
        }

    # ==================== EXIT CHECK ====================

    def should_exit(self, symbol: str, current_price: float, entry_price: float,
                   entry_time: str, target_pct: float, stop_pct: float) -> Optional[str]:
        """Check if we should exit a position"""

        pnl_pct = (current_price - entry_price) / entry_price

        if pnl_pct >= target_pct:
            return f"SELL (profit: +{pnl_pct:.2%})"

        if pnl_pct <= -stop_pct:
            return f"SELL (stop: {pnl_pct:.2%})"

        try:
            entry_dt = datetime.fromisoformat(entry_time)
            hours_held = (datetime.now() - entry_dt).total_seconds() / 3600
            if hours_held >= self.max_hold:
                return f"SELL (time: {hours_held:.1f}h)"
        except:
            pass

        return None

    def get_stats(self) -> dict:
        return {
            "strategy": "Crypto Pennies v2.0 — Dual Mode",
            "symbols": len(self.crypto_symbols),
            "modes": "DIP (VWAP-Z < -0.8) + MOMENTUM (VWAP-Z > 1.5, Vol > 2x)",
            "atr_target_multiplier": self.atr_target,
            "atr_stop_multiplier": self.atr_stop,
            "max_hold_hours": self.max_hold,
            "kelly_fraction": self.kelly_frac,
            "fee_pct": self.fee_pct,
        }