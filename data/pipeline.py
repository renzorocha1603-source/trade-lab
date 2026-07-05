"""
Data Pipeline - Finnhub (prices + news) + Alpha Vantage (sentiment) + Yahoo (fallback)
Multi-source with freshness scoring, deduplication, and accuracy tracking.
Optimized for Railway 24/7 deployment.
"""

import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import logging
import hashlib
import time

logger = logging.getLogger(__name__)


class DataPipeline:
    """Multi-source data pipeline - Finnhub primary, Alpha Vantage supplement, Yahoo fallback"""

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
        self.max_news_age = config.news.max_news_age_minutes
        self.freshness_decay = config.news.freshness_decay_enabled

        # Rate limiting
        self._last_finnhub_call = 0
        self._last_alpha_call = 0
        self._finnhub_delay = 1.1  # 60 calls/min max
        self._alpha_delay = 12.5   # 5 calls/min max

        # Accuracy tracker
        self.predictions: List[dict] = []
        self._load_accuracy_log()

        sources = []
        if self.finnhub_key and self.finnhub_key not in ("your_finnhub_key_here", ""): sources.append("Finnhub")
        if self.alpha_key and self.alpha_key not in ("your_alpha_vantage_key_here", ""): sources.append("AlphaVantage")
        sources.append("YahooFinance")
        logger.info(f"Data pipeline initialized | Sources: {', '.join(sources)}")

    # ==================== RATE LIMITING ====================

    def _wait_finnhub(self):
        elapsed = time.time() - self._last_finnhub_call
        if elapsed < self._finnhub_delay:
            time.sleep(self._finnhub_delay - elapsed)
        self._last_finnhub_call = time.time()

    def _wait_alpha(self):
        elapsed = time.time() - self._last_alpha_call
        if elapsed < self._alpha_delay:
            time.sleep(self._alpha_delay - elapsed)
        self._last_alpha_call = time.time()

    # ==================== PRICE DATA ====================

    def load_historical_data(self) -> Dict[str, pd.Series]:
        """Load historical data - Yahoo primary (no rate limits), Alpha Vantage fallback"""
        logger.info(f"Loading historical data for {len(self.symbols)} symbols...")
        
        for symbol in self.symbols:
            # Try Yahoo first (best for historical, no rate limits)
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=f"{self.config.data.historical_years}y")
                if not hist.empty and len(hist) > 50:
                    self._price_cache[symbol] = hist['Close']
                    logger.info(f"  {symbol}: {len(hist)} days loaded (Yahoo)")
                    continue
            except Exception as e:
                logger.debug(f"  Yahoo history failed for {symbol}: {e}")

            # Fallback to Alpha Vantage
            if self.alpha_key and self.alpha_key not in ("your_alpha_vantage_key_here", ""):
                try:
                    self._wait_alpha()
                    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=full&apikey={self.alpha_key}"
                    resp = requests.get(url, timeout=15)
                    data = resp.json()
                    series_data = data.get("Time Series (Daily)", {})
                    if series_data:
                        dates = []
                        closes = []
                        for date_str, values in sorted(series_data.items())[-252:]:
                            dates.append(date_str)
                            closes.append(float(values["4. close"]))
                        self._price_cache[symbol] = pd.Series(closes, index=pd.to_datetime(dates))
                        logger.info(f"  {symbol}: {len(dates)} days loaded (Alpha Vantage)")
                        continue
                except Exception as e:
                    logger.debug(f"  Alpha Vantage history failed for {symbol}: {e}")

            logger.warning(f"  {symbol}: No historical data available")

        return self._price_cache

    def get_live_prices(self) -> Dict[str, float]:
        """Get current prices - Finnhub primary (fast, reliable), Alpha Vantage fallback"""
        prices = {}

        # Try Finnhub first (60 calls/min, real-time)
        if self.finnhub_key and self.finnhub_key not in ("your_finnhub_key_here", ""):
            for symbol in self.symbols:
                try:
                    self._wait_finnhub()
                    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
                    resp = requests.get(url, timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    current = data.get("c", 0)  # Current price
                    if current > 0:
                        prices[symbol] = current
                except Exception as e:
                    logger.debug(f"Finnhub price error {symbol}: {e}")

            if prices:
                logger.info(f"Prices from Finnhub: {len(prices)} symbols")
                return prices

        # Fallback to Alpha Vantage (slower, 5 calls/min)
        if self.alpha_key and self.alpha_key not in ("your_alpha_vantage_key_here", ""):
            for symbol in self.symbols:
                if symbol in prices:
                    continue
                try:
                    self._wait_alpha()
                    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.alpha_key}"
                    resp = requests.get(url, timeout=10)
                    data = resp.json()
                    quote = data.get("Global Quote", {})
                    price = float(quote.get("05. price", 0))
                    if price > 0:
                        prices[symbol] = price
                except Exception as e:
                    logger.debug(f"Alpha Vantage price error {symbol}: {e}")

            if prices:
                logger.info(f"Prices from Alpha Vantage: {len(prices)} symbols")
                return prices

        # Last resort: Yahoo Finance
        for symbol in self.symbols:
            if symbol in prices:
                continue
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
                if not hist.empty:
                    prices[symbol] = hist['Close'].iloc[-1]
            except:
                pass

        logger.info(f"Prices from Yahoo fallback: {len(prices)} symbols")
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

    # ==================== MULTI-SOURCE NEWS ====================

    def get_news(self, symbol: str, max_items: int = 10) -> List[dict]:
        """Get fresh news from Finnhub + Alpha Vantage, merged and deduplicated"""
        cache_key = f"news_{symbol}"
        if cache_key in self._news_cache:
            cached_time, cached_news = self._news_cache[cache_key]
            if (datetime.now() - cached_time).seconds < 120:
                return cached_news

        all_news = []

        # Source 1: Finnhub (fastest, real-time)
        finnhub_news = self._get_finnhub_news(symbol)
        all_news.extend(finnhub_news)

        # Source 2: Alpha Vantage (with sentiment scores)
        alpha_news = self._get_alpha_vantage_news(symbol)
        all_news.extend(alpha_news)

        # Deduplicate
        unique_news = self._deduplicate_news(all_news)

        # Score freshness and quality
        for item in unique_news:
            item["freshness_score"] = self._calculate_freshness(item.get("published_at", ""))
            item["source_quality"] = self._source_quality(item.get("source", ""))

        # Sort by combined score
        unique_news.sort(key=lambda x: (x["freshness_score"] + x["source_quality"]) / 2, reverse=True)

        result = unique_news[:max_items]
        self._news_cache[cache_key] = (datetime.now(), result)

        if result:
            avg_freshness = sum(n.get("freshness_score", 0) for n in result) / len(result)
            logger.info(f"News for {symbol}: {len(result)} articles | Freshness: {avg_freshness:.2f}")
        else:
            logger.warning(f"No news found for {symbol}")

        return result

    def _get_finnhub_news(self, symbol: str) -> List[dict]:
        """Finnhub - real-time financial news"""
        if not self.finnhub_key or self.finnhub_key in ("your_finnhub_key_here", ""):
            return []
        try:
            self._wait_finnhub()
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
                    except:
                        pass
                news.append({
                    "title": item.get("headline", ""),
                    "summary": item.get("summary", "")[:200] if item.get("summary") else "",
                    "source": "Finnhub",
                    "published_at": pub_time,
                    "url": item.get("url", ""),
                    "category": item.get("category", ""),
                })
            return news
        except Exception as e:
            logger.debug(f"Finnhub news error {symbol}: {e}")
            return []

    def _get_alpha_vantage_news(self, symbol: str) -> List[dict]:
        """Alpha Vantage - news with sentiment scores"""
        if not self.alpha_key or self.alpha_key in ("your_alpha_vantage_key_here", ""):
            return []
        try:
            self._wait_alpha()
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
                    except:
                        pass
                news.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", "")[:200] if item.get("summary") else "",
                    "source": "AlphaVantage",
                    "published_at": pub_time,
                    "url": item.get("url", ""),
                    "sentiment_score": float(item.get("overall_sentiment_score", 0)),
                })
            return news
        except Exception as e:
            logger.debug(f"Alpha Vantage news error {symbol}: {e}")
            return []

    def _deduplicate_news(self, news_list: List[dict]) -> List[dict]:
        """Remove duplicate headlines using title hashing"""
        seen = set()
        unique = []
        for item in news_list:
            title_hash = hashlib.md5(item["title"][:80].lower().encode()).hexdigest()
            if title_hash not in seen:
                seen.add(title_hash)
                unique.append(item)
        return unique

    def _calculate_freshness(self, published_at: str) -> float:
        """Score news freshness from 0 (very old) to 1 (just published)"""
        if not published_at:
            return 0.3
        try:
            clean = published_at.replace("Z", "+00:00")
            if "+" in clean:
                clean = clean.split("+")[0].split("[")[0]
            pub_time = datetime.fromisoformat(clean)
            age_minutes = (datetime.now() - pub_time.replace(tzinfo=None)).total_seconds() / 60
            if age_minutes <= 5: return 1.0
            elif age_minutes <= 15: return 0.9
            elif age_minutes <= 30: return 0.7
            elif age_minutes <= 60: return 0.5
            elif age_minutes <= 120: return 0.3
            else: return 0.1
        except:
            return 0.3

    def _source_quality(self, source: str) -> float:
        """Rate source reliability from 0 to 1"""
        ratings = {"Finnhub": 0.9, "AlphaVantage": 0.8, "YahooFinance": 0.6}
        return ratings.get(source, 0.5)

    def get_news_freshness_factor(self, news_list: List[dict]) -> float:
        """Calculate confidence multiplier based on news freshness"""
        if not news_list:
            return 0.5
        avg = sum(n.get("freshness_score", 0) for n in news_list) / len(news_list)
        if avg >= 0.8: return 1.0
        elif avg >= 0.6: return 0.85
        elif avg >= 0.4: return 0.65
        else: return 0.4

    # ==================== ACCURACY TRACKING ====================

    def _load_accuracy_log(self):
        accuracy_file = "logs/accuracy_log.json"
        if os.path.exists(accuracy_file):
            try:
                with open(accuracy_file) as f:
                    self.predictions = json.load(f)
                logger.info(f"Loaded {len(self.predictions)} historical predictions")
            except:
                self.predictions = []

    def _save_accuracy_log(self):
        os.makedirs("logs", exist_ok=True)
        with open("logs/accuracy_log.json", "w") as f:
            json.dump(self.predictions[-500:], f, indent=2, default=str)

    def record_prediction(self, symbol: str, action: str, price: float,
                         ai_confidence: float, reason: str, news_freshness: float):
        prediction = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": action,
            "entry_price": price,
            "ai_confidence": ai_confidence,
            "news_freshness": news_freshness,
            "reason": reason[:200],
            "outcome_checked": False,
            "outcome_pnl_pct": None,
            "outcome_correct": None,
        }
        self.predictions.append(prediction)
        if len(self.predictions) % 10 == 0:
            self._save_accuracy_log()

    def check_prediction_outcomes(self, market_prices: Dict[str, float]):
        checked = 0
        for pred in self.predictions:
            if pred.get("outcome_checked"):
                continue
            age_hours = (datetime.now() - datetime.fromisoformat(pred["timestamp"])).total_seconds() / 3600
            if age_hours < 24:
                continue
            current_price = market_prices.get(pred["symbol"])
            if not current_price or pred["entry_price"] == 0:
                continue
            pnl_pct = (current_price - pred["entry_price"]) / pred["entry_price"]
            if pred["action"] == "SELL":
                pnl_pct = -pnl_pct
            pred["outcome_pnl_pct"] = round(pnl_pct * 100, 2)
            pred["outcome_correct"] = pnl_pct > 0
            pred["outcome_checked"] = True
            checked += 1
        if checked > 0:
            self._save_accuracy_log()
            logger.info(f"Checked outcomes for {checked} past predictions")

    def get_accuracy_stats(self) -> dict:
        checked = [p for p in self.predictions if p.get("outcome_checked")]
        if not checked:
            return {"total_checked": 0, "accuracy": 0, "message": "No predictions checked yet"}
        correct = sum(1 for p in checked if p.get("outcome_correct"))
        total = len(checked)
        accuracy = (correct / total) * 100
        high_conf = [p for p in checked if p.get("ai_confidence", 0) >= 0.8]
        med_conf = [p for p in checked if 0.5 <= p.get("ai_confidence", 0) < 0.8]
        low_conf = [p for p in checked if p.get("ai_confidence", 0) < 0.5]
        high_acc = (sum(1 for p in high_conf if p.get("outcome_correct")) / max(len(high_conf), 1)) * 100
        med_acc = (sum(1 for p in med_conf if p.get("outcome_correct")) / max(len(med_conf), 1)) * 100
        low_acc = (sum(1 for p in low_conf if p.get("outcome_correct")) / max(len(low_conf), 1)) * 100
        fresh = [p for p in checked if p.get("news_freshness", 0) >= 0.7]
        stale = [p for p in checked if p.get("news_freshness", 0) < 0.7]
        fresh_acc = (sum(1 for p in fresh if p.get("outcome_correct")) / max(len(fresh), 1)) * 100
        stale_acc = (sum(1 for p in stale if p.get("outcome_correct")) / max(len(stale), 1)) * 100
        return {
            "total_checked": total,
            "correct": correct,
            "accuracy": round(accuracy, 1),
            "by_confidence": {
                "high_confidence_accuracy": round(high_acc, 1),
                "medium_confidence_accuracy": round(med_acc, 1),
                "low_confidence_accuracy": round(low_acc, 1),
            },
            "by_freshness": {
                "fresh_news_accuracy": round(fresh_acc, 1),
                "stale_news_accuracy": round(stale_acc, 1),
            },
        }

    def print_accuracy_report(self):
        stats = self.get_accuracy_stats()
        if stats["total_checked"] == 0:
            return
        print(f"""
╔══════════════════════════════════════════╗
║        AI ACCURACY REPORT               ║
╠══════════════════════════════════════════╣
║ Checked: {stats['total_checked']:>5} | Correct: {stats['correct']:>5}     ║
║ Accuracy: {stats['accuracy']:>5.1f}%                    ║
╠══════════════════════════════════════════╣
║ High Conf: {stats['by_confidence']['high_confidence_accuracy']:>5.1f}% | Med: {stats['by_confidence']['medium_confidence_accuracy']:>5.1f}% | Low: {stats['by_confidence']['low_confidence_accuracy']:>5.1f}% ║
║ Fresh News: {stats['by_freshness']['fresh_news_accuracy']:>5.1f}% | Stale: {stats['by_freshness']['stale_news_accuracy']:>5.1f}% ║
╚══════════════════════════════════════════╝
        """)