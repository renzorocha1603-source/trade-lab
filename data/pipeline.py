"""
Data Pipeline - Multi-source with async queue, Coinbase crypto, TSX support.
Finnhub (prices + news) + Alpha Vantage (sentiment) + Coinbase (crypto) + Yahoo (history).
Includes freshness scoring, rate-limit staggering, and accuracy tracking.
"""

import yfinance as yf
import pandas as pd
import requests
import json
import os
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from collections import deque
import logging
import hashlib

logger = logging.getLogger(__name__)


class DataPipeline:
    """Multi-source data pipeline with rate-limit protection and crypto support"""

    def __init__(self, config):
        self.config = config
        self.symbols = config.data.symbols
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self._price_cache: Dict[str, pd.Series] = {}
        self._fx_rate_cache = {"rate": None, "timestamp": None}
        self._news_cache: Dict[str, Tuple[datetime, List[dict]]] = {}

        # API keys
        self.finnhub_key = config.news.finnhub_api_key
        self.alpha_key = config.news.alpha_vantage_api_key
        
        # Rate limit queues (prevents burst at :00/:15/:30/:45)
        self._request_queue = deque()
        self._last_request_time = 0
        self._min_request_gap = 1.2  # 1.2 seconds between API calls

        # Accuracy tracker
        self.predictions: List[dict] = []
        self._load_accuracy_log()

        sources = ["YahooFinance"]
        if self.finnhub_key and self.finnhub_key not in ("your_finnhub_key_here", ""): 
            sources.append("Finnhub")
        if self.alpha_key and self.alpha_key not in ("your_alpha_vantage_key_here", ""): 
            sources.append("AlphaVantage")
        sources.append("Coinbase (crypto)")
        logger.info(f"Data pipeline | {len(self.symbols)} symbols | Sources: {', '.join(sources)}")

    # ==================== RATE LIMIT STAGGER ====================

    def _stagger_request(self):
        """Prevent API rate limit bursts by spacing out requests"""
        now = time.time()
        gap = now - self._last_request_time
        if gap < self._min_request_gap:
            time.sleep(self._min_request_gap - gap)
        self._last_request_time = time.time()

    # ==================== PRICE DATA ====================

    def load_historical_data(self) -> Dict[str, pd.Series]:
        logger.info(f"Loading historical data for {len(self.symbols)} symbols...")
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=f"{self.config.data.historical_years}y")
                if not hist.empty and len(hist) > 20:
                    self._price_cache[symbol] = hist['Close']
                    logger.debug(f"  {symbol}: {len(hist)} days loaded")
                else:
                    logger.warning(f"  {symbol}: No data available")
            except Exception as e:
                logger.debug(f"  {symbol}: {e}")
        logger.info(f"Historical data loaded: {len(self._price_cache)}/{len(self.symbols)} symbols")
        return self._price_cache

    def get_live_prices(self) -> Dict[str, float]:
        """Get current prices with staggered API calls"""
        prices = {}

        # Crypto via Coinbase (free, no key, unlimited)
        crypto_symbols = [s for s in self.symbols if "-USD" in s]
        for symbol in crypto_symbols:
            try:
                coin = symbol.replace("-USD", "")
                resp = requests.get(f"https://api.coinbase.com/v2/prices/{coin}-USD/spot", timeout=5)
                data = resp.json()
                price = float(data.get("data", {}).get("amount", 0))
                if price > 0:
                    prices[symbol] = price
            except Exception as e:
                logger.debug(f"Coinbase error {symbol}: {e}")

        # Stocks/ETFs via Finnhub (staggered)
        stock_symbols = [s for s in self.symbols if "-USD" not in s]
        if self.finnhub_key and self.finnhub_key not in ("your_finnhub_key_here", ""):
            for symbol in stock_symbols:
                try:
                    self._stagger_request()
                    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        current = data.get("c", 0)
                        if current > 0:
                            prices[symbol] = current
                except Exception as e:
                    logger.debug(f"Finnhub price error {symbol}: {e}")

        # Fallback to Yahoo (batch, no rate limits)
        missing = [s for s in self.symbols if s not in prices]
        if missing:
            for symbol in missing:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        prices[symbol] = hist['Close'].iloc[-1]
                except:
                    pass

        logger.info(f"Prices: {len(prices)}/{len(self.symbols)} symbols | Crypto: Coinbase | Stocks: Finnhub→Yahoo")
        return prices

    # ==================== FX RATES ====================

    def get_usd_cad_rate(self) -> float:
        if self._fx_rate_cache["rate"] and self._fx_rate_cache["timestamp"]:
            age = (datetime.now() - self._fx_rate_cache["timestamp"]).seconds
            if age < 3600:
                return self._fx_rate_cache["rate"]
        rate = self._fetch_fx_rate()
        if rate:
            self._fx_rate_cache = {"rate": rate, "timestamp": datetime.now()}
        return rate or 1.35

    def _fetch_fx_rate(self) -> Optional[float]:
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
            except:
                pass
        try:
            ticker = yf.Ticker("USDCAD=X")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except:
            pass
        return None

    # ==================== NEWS (unchanged from before) ====================

    def get_news(self, symbol: str, max_items: int = 10) -> List[dict]:
        cache_key = f"news_{symbol}"
        if cache_key in self._news_cache:
            cached_time, cached_news = self._news_cache[cache_key]
            if (datetime.now() - cached_time).seconds < 300:
                return cached_news

        all_news = []
        
        finnhub_news = self._get_finnhub_news(symbol)
        all_news.extend(finnhub_news)
        
        alpha_news = self._get_alpha_vantage_news(symbol)
        all_news.extend(alpha_news)
        
        unique_news = self._deduplicate_news(all_news)
        
        for item in unique_news:
            item["freshness_score"] = self._calculate_freshness(item.get("published_at", ""))
            item["source_quality"] = self._source_quality(item.get("source", ""))
        
        unique_news.sort(key=lambda x: (x["freshness_score"] + x["source_quality"]) / 2, reverse=True)
        result = unique_news[:max_items]
        self._news_cache[cache_key] = (datetime.now(), result)
        
        if result:
            avg = sum(n.get("freshness_score", 0) for n in result) / len(result)
            logger.info(f"News {symbol}: {len(result)} articles | Freshness: {avg:.2f}")
        return result

    def _get_finnhub_news(self, symbol: str) -> List[dict]:
        if not self.finnhub_key or self.finnhub_key in ("your_finnhub_key_here", ""):
            return []
        try:
            self._stagger_request()
            from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_date}&to={to_date}&token={self.finnhub_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            news = []
            for item in data[:20]:
                pub_time = ""
                if item.get("datetime"):
                    try:
                        pub_time = datetime.fromtimestamp(item["datetime"]).isoformat()
                    except: pass
                news.append({
                    "title": item.get("headline", ""),
                    "summary": item.get("summary", "")[:200] if item.get("summary") else "",
                    "source": "Finnhub",
                    "published_at": pub_time,
                    "url": item.get("url", ""),
                })
            return news
        except: return []

    def _get_alpha_vantage_news(self, symbol: str) -> List[dict]:
        if not self.alpha_key or self.alpha_key in ("your_alpha_vantage_key_here", ""):
            return []
        try:
            self._stagger_request()
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apikey={self.alpha_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            news = []
            for item in data.get("feed", [])[:20]:
                pub_str = item.get("time_published", "")
                pub_time = ""
                if pub_str and len(pub_str) >= 12:
                    try:
                        pub_time = f"{pub_str[:4]}-{pub_str[4:6]}-{pub_str[6:8]}T{pub_str[8:10]}:{pub_str[10:12]}:00"
                    except: pass
                news.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", "")[:200] if item.get("summary") else "",
                    "source": "AlphaVantage",
                    "published_at": pub_time,
                    "sentiment_score": float(item.get("overall_sentiment_score", 0)),
                })
            return news
        except: return []

    def _deduplicate_news(self, news_list: List[dict]) -> List[dict]:
        seen = set()
        unique = []
        for item in news_list:
            h = hashlib.md5(item["title"][:80].lower().encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(item)
        return unique

    def _calculate_freshness(self, published_at: str) -> float:
        if not published_at: return 0.3
        try:
            clean = published_at.replace("Z", "+00:00")
            if "+" in clean: clean = clean.split("+")[0].split("[")[0]
            pub_time = datetime.fromisoformat(clean)
            age = (datetime.now() - pub_time.replace(tzinfo=None)).total_seconds() / 60
            if age <= 5: return 1.0
            elif age <= 15: return 0.9
            elif age <= 30: return 0.7
            elif age <= 60: return 0.5
            elif age <= 120: return 0.3
            else: return 0.1
        except: return 0.3

    def _source_quality(self, source: str) -> float:
        return {"Finnhub": 0.9, "AlphaVantage": 0.8, "YahooFinance": 0.6}.get(source, 0.5)

    def get_news_freshness_factor(self, news_list: List[dict]) -> float:
        if not news_list: return 0.5
        avg = sum(n.get("freshness_score", 0) for n in news_list) / len(news_list)
        if avg >= 0.8: return 1.0
        elif avg >= 0.6: return 0.85
        elif avg >= 0.4: return 0.65
        else: return 0.4

    # ==================== ACCURACY TRACKING ====================

    def _load_accuracy_log(self):
        f = "logs/accuracy_log.json"
        if os.path.exists(f):
            try:
                with open(f) as fh: self.predictions = json.load(fh)
            except: self.predictions = []

    def _save_accuracy_log(self):
        os.makedirs("logs", exist_ok=True)
        with open("logs/accuracy_log.json", "w") as f:
            json.dump(self.predictions[-500:], f, indent=2, default=str)

    def record_prediction(self, symbol, action, price, confidence, reason, freshness):
        self.predictions.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol, "action": action, "entry_price": price,
            "ai_confidence": confidence, "news_freshness": freshness,
            "reason": reason[:200], "outcome_checked": False,
            "outcome_pnl_pct": None, "outcome_correct": None,
        })
        if len(self.predictions) % 10 == 0: self._save_accuracy_log()

    def check_prediction_outcomes(self, prices):
        checked = 0
        for p in self.predictions:
            if p.get("outcome_checked"): continue
            age = (datetime.now() - datetime.fromisoformat(p["timestamp"])).total_seconds() / 3600
            if age < 24: continue
            cp = prices.get(p["symbol"])
            if not cp or p["entry_price"] == 0: continue
            pnl = (cp - p["entry_price"]) / p["entry_price"]
            if p["action"] == "SELL": pnl = -pnl
            p["outcome_pnl_pct"] = round(pnl * 100, 2)
            p["outcome_correct"] = pnl > 0
            p["outcome_checked"] = True
            checked += 1
        if checked > 0: self._save_accuracy_log()

    def get_accuracy_stats(self) -> dict:
        checked = [p for p in self.predictions if p.get("outcome_checked")]
        if not checked: return {"total_checked": 0, "accuracy": 0}
        correct = sum(1 for p in checked if p.get("outcome_correct"))
        return {
            "total_checked": len(checked),
            "correct": correct,
            "accuracy": round(correct / len(checked) * 100, 1),
        }

    def print_accuracy_report(self):
        s = self.get_accuracy_stats()
        if s["total_checked"] == 0: return
        print(f"\n  AI Accuracy: {s['accuracy']}% ({s['correct']}/{s['total_checked']} correct)\n")