"""
Data Pipeline - Market data + real-time FX rates.
Fetches stock prices, news, and USD/CAD exchange rates.
"""

import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class DataPipeline:
    """Fetches and caches all market data including FX rates"""

    def __init__(self, config):
        self.config = config
        self.symbols = config.data.symbols
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self._price_cache: Dict[str, pd.Series] = {}
        self._fx_rate_cache = {"rate": None, "timestamp": None}

    def load_historical_data(self) -> Dict[str, pd.Series]:
        """Load historical price data for all symbols"""
        logger.info(f"Loading historical data for {len(self.symbols)} symbols...")
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=f"{self.config.data.historical_years}y")
                if not hist.empty:
                    self._price_cache[symbol] = hist['Close']
                    logger.info(f"  {symbol}: {len(hist)} days loaded")
            except Exception as e:
                logger.error(f"  {symbol}: Error - {e}")
        return self._price_cache

    def get_live_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols"""
        prices = {}
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                if hasattr(info, 'last_price') and info.last_price:
                    prices[symbol] = info.last_price
                else:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        prices[symbol] = hist['Close'].iloc[-1]
            except Exception as e:
                logger.debug(f"Price error {symbol}: {e}")
        return prices

    def get_news(self, symbol: str, max_items: int = 5) -> List[dict]:
        """Get recent news for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            return [{"title": n.get("title", ""), "publisher": n.get("publisher", "")}
                    for n in news[:max_items]]
        except:
            return []

    def get_usd_cad_rate(self) -> float:
        """Get real-time USD/CAD exchange rate from multiple sources"""
        if self._fx_rate_cache["rate"] and self._fx_rate_cache["timestamp"]:
            age = (datetime.now() - self._fx_rate_cache["timestamp"]).seconds
            if age < 3600:
                return self._fx_rate_cache["rate"]

        rate = self._fetch_fx_rate()
        if rate:
            self._fx_rate_cache = {"rate": rate, "timestamp": datetime.now()}
        return rate or 1.35

    def _fetch_fx_rate(self) -> Optional[float]:
        """Try multiple sources for FX rate"""
        sources = [
            "https://api.exchangerate-api.com/v4/latest/USD",
            "https://open.er-api.com/v6/latest/USD",
        ]
        for url in sources:
            try:
                resp = requests.get(url, timeout=5)
                data = resp.json()
                rate = data.get("rates", {}).get("CAD")
                if rate:
                    logger.info(f"FX rate (USD/CAD): {rate:.4f}")
                    return rate
            except Exception as e:
                logger.debug(f"FX source failed: {url} - {e}")
        try:
            ticker = yf.Ticker("USDCAD=X")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except:
            pass
        return None

    def usd_to_cad(self, usd_amount: float) -> float:
        """Convert USD to CAD"""
        rate = self.get_usd_cad_rate()
        return usd_amount * rate

    def cad_to_usd(self, cad_amount: float) -> float:
        """Convert CAD to USD"""
        rate = self.get_usd_cad_rate()
        return cad_amount / rate if rate > 0 else cad_amount

    def get_historical_fx_rates(self, days: int = 30) -> pd.Series:
        """Get historical USD/CAD rates for backtesting"""
        try:
            ticker = yf.Ticker("USDCAD=X")
            hist = ticker.history(period=f"{days}d")
            return hist['Close'] if not hist.empty else pd.Series()
        except:
            return pd.Series()