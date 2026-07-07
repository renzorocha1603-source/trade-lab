"""
Crypto Pennies Strategy — Small consistent wins compound into big returns.
24/7 trading with fee-aware math, VWAP Z-Score, Bollinger Bands, ATR stops.
Includes market cap data from CoinGecko (free, no API key).
Uses Yahoo Finance for price data when Binance is blocked.
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
    Entry: VWAP Z-Score + Volume confirmation + Bollinger Band filter + Market Cap check
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

        logger.info(f"Crypto Pennies Strategy | Target: {self.atr_target}× ATR | Stop: {self.atr_stop}× ATR | Max Hold: {self.max_hold}h | Fees: {self.fee_pct:.2%}")

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
                logger.debug(f"Binance blocked for {binance_symbol}: {data.get('msg', 'Unknown')}")
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
            
            # Map interval to Yahoo Finance period
            period_map = {"1h": "5d", "15m": "5d", "4h": "1mo", "1d": "3mo"}
            period = period_map.get(interval, "5d")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                return None
            
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'datetimelamb': 'timestamp'}) if 'datetimelamb' in df.columns else df
            
            if 'timestamp' not in df.columns and 'date' in df.columns:
                df['timestamp'] = df['date']
            
            return df
        except Exception as e:
            logger.debug(f"Yahoo crypto fetch error: {e}")
            return None

    def fetch_coingecko_price(self, symbol: str) -> Optional[float]:
        """Fetch current price from CoinGecko (works everywhere, free, no key)"""
        try:
            coin_map = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum"}
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
                logger.warning("CoinGecko rate limit hit — using cached data")
                return self._market_cap_cache.get(symbol)

            data = resp.json()
            coin_data = data.get(coin_id, {})

            market_cap = coin_data.get("usd_market_cap")
            volume_24h = coin_data.get("usd_24h_vol")
            change_24h = coin_data.get("usd_24h_change")

            self._market_cap_cache[symbol] = market_cap
            if volume_24h:
                self._market_cap_cache[f"{symbol}_volume"] = volume_24h
            if change_24h is not None:
                self._market_cap_cache[f"{symbol}_change"] = change_24h

            self._market_cap_cache_time = datetime.now()

            price = coin_data.get("usd")
            if price:
                logger.debug(f"CoinGecko {symbol}: ${price:.2f} | Cap: ${market_cap:,.0f}" if market_cap else f"CoinGecko {symbol}: ${price:.2f}")

            return price

        except Exception as e:
            logger.debug(f"CoinGecko error for {symbol}: {e}")
            return None

    def get_market_cap_rank(self, symbol: str) -> str:
        """Get market cap tier for risk assessment"""
        market_cap = self._market_cap_cache.get(symbol)
        
        if market_cap is None:
            market_cap = self.fetch_coingecko_price(symbol)
            market_cap = self._market_cap_cache.get(symbol)

        if market_cap is None:
            return "unknown"

        if market_cap > 500_000_000_000:
            return "mega_cap"
        elif market_cap > 100_000_000_000:
            return "large_cap"
        elif market_cap > 10_000_000_000:
            return "mid_cap"
        else:
            return "small_cap"

    # ==================== TECHNICAL INDICATORS ====================

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range"""
        if len(df) < period:
            return 0.02

        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'

        high = df[high_col].values[-period:]
        low = df[low_col].values[-period:]
        close = df[close_col].values[-period-1:-1] if len(df) > period else df[close_col].values[:-1]

        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close)
        tr3 = np.abs(low[1:] - close)
        tr = np.maximum(np.maximum(tr1, tr2), tr3)

        atr = np.mean(tr) / df[close_col].iloc[-1]
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
        """RSI for additional confirmation"""
        if len(df) < period + 1:
            return 50.0

        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col].values
        deltas = np.diff(close[-period-1:])
        gains = np.sum(deltas[deltas > 0]) / period
        losses = -np.sum(deltas[deltas < 0]) / period

        if losses == 0:
            return 100.0

        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    # ==================== SIGNAL GENERATION ====================

    def generate_signal(self, symbol: str, price_history: pd.Series = None) -> Optional[dict]:
        """Generate a trading signal for crypto"""

        if "BTC" in symbol:
            interval = self.crypto_config.btc_timeframe
        else:
            interval = self.crypto_config.eth_timeframe

        # Try Binance first, fallback to Yahoo Finance
        df = self.fetch_binance_klines(symbol, interval)
        data_source = "Binance"

        if df is None or len(df) < 30:
            df = self.fetch_yahoo_crypto(symbol, interval)
            data_source = "Yahoo Finance"

        if df is None or len(df) < 20:
            logger.debug(f"Crypto {symbol}: Insufficient data from all sources")
            return None

        close_col = 'close' if 'close' in df.columns else 'Close'
        current_price = df[close_col].iloc[-1]

        # Calculate all indicators
        atr = self.calculate_atr(df)
        vwap_z = self.calculate_vwap_zscore(df)
        bb_width = self.calculate_bollinger_width(df)
        vol_ratio = self.calculate_volume_ratio(df)
        rsi = self.calculate_rsi(df)

        # Market cap data
        self.fetch_coingecko_price(symbol)
        market_cap = self._market_cap_cache.get(symbol)
        cap_tier = self.get_market_cap_rank(symbol)
        volume_24h = self._market_cap_cache.get(f"{symbol}_volume")
        change_24h = self._market_cap_cache.get(f"{symbol}_change")

        logger.info(f"Crypto {symbol} [{data_source}] | ${current_price:.2f} | VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | BBW: {bb_width:.3f} | Vol: {vol_ratio:.1f}x | RSI: {rsi:.0f} | Cap: {cap_tier}")

        # Entry conditions
        entry_conditions = {
            "vwap_zscore_ok": vwap_z < -1.5,
            "volume_ok": vol_ratio > self.min_volume_mult,
            "bollinger_ok": 0.02 < bb_width < 0.15,
            "rsi_not_overbought": rsi < 65,
            "market_cap_ok": cap_tier in ["mega_cap", "large_cap", "mid_cap"],
        }

        all_pass = all(entry_conditions.values())

        if not all_pass:
            failed = [k for k, v in entry_conditions.items() if not v]
            logger.debug(f"Crypto {symbol}: Conditions not met — {failed}")
            return None

        # Adjust position size by market cap tier
        cap_multiplier = {
            "mega_cap": 1.0,
            "large_cap": 0.9,
            "mid_cap": 0.7,
            "small_cap": 0.5,
            "unknown": 0.5
        }

        # Calculate profit target and stop loss
        target_pct = atr * self.atr_target
        stop_pct = atr * self.atr_stop

        # Fee-aware check
        net_target = target_pct - (self.fee_pct * 2)
        net_risk = stop_pct + (self.fee_pct * 2)

        if net_target < self.min_net_ev:
            logger.debug(f"Crypto {symbol}: Net target {net_target:.3%} < min EV {self.min_net_ev:.3%}")
            return None

        # Risk/reward
        risk_reward = net_target / net_risk if net_risk > 0 else 0

        # Kelly position sizing
        p_win = 0.55
        b_ratio = risk_reward
        kelly = (p_win * b_ratio - (1 - p_win)) / b_ratio if b_ratio > 0 else 0
        position_size = max(0.01, min(0.20, kelly * self.kelly_frac * cap_multiplier.get(cap_tier, 0.5)))

        return {
            "symbol": symbol,
            "action": "BUY",
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
            "volume_24h": volume_24h,
            "change_24h": change_24h,
            "indicators": {
                "vwap_zscore": round(vwap_z, 3),
                "atr": round(atr, 4),
                "bb_width": round(bb_width, 4),
                "vol_ratio": round(vol_ratio, 2),
                "rsi": round(rsi, 1),
            },
            "reason": f"VWAP-Z: {vwap_z:.2f} | ATR: {atr:.2%} | Vol: {vol_ratio:.1f}x | RSI: {rsi:.0f} | Cap: {cap_tier} [{data_source}]"
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
            "strategy": "Crypto Pennies Scalping",
            "atr_target_multiplier": self.atr_target,
            "atr_stop_multiplier": self.atr_stop,
            "max_hold_hours": self.max_hold,
            "kelly_fraction": self.kelly_frac,
            "fee_pct": self.fee_pct,
            "min_net_ev": self.min_net_ev,
        }