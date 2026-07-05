"""
Data Pipeline - Multi-source market data + real-time FX rates + news aggregator.
Fetches stock prices from Yahoo Finance, news from Finnhub + Alpha Vantage + Yahoo.
Includes freshness scoring, confidence decay, and accuracy tracking.
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

logger = logging.getLogger(__name__)


class DataPipeline:
    """Multi-source data pipeline with news freshness and accuracy tracking"""

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

        # Accuracy tracker
        self.predictions: List[dict] = []
        self._load_accuracy_log()

        sources = []
        if self.finnhub_key and self.finnhub_key not in ("your_finnhub_key_here", ""): sources.append("Finnhub")
        if self.alpha_key and self.alpha_key not in ("your_alpha_vantage_key_here", ""): sources.append("AlphaVantage")
        sources.append("YahooFinance")
        logger.info(f"Data pipeline initialized | News sources: {', '.join(sources)}")

    # ==================== PRICE DATA ====================

    def load_historical_data(self) -> Dict[str, pd.Series]:
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

    def usd_to_cad(self, usd_amount: float) -> float:
        rate = self.get_usd_cad_rate()
        return usd_amount * rate

    def cad_to_usd(self, cad_amount: float) -> float:
        rate = self.get_usd_cad_rate()
        return cad_amount / rate if rate > 0 else cad_amount

    # ==================== MULTI-SOURCE NEWS ====================

    def get_news(self, symbol: str, max_items: int = 10) -> List[dict]:
        """Get fresh news from multiple sources, merged and deduplicated"""
        cache_key = f"news_{symbol}"
        if cache_key in self._news_cache:
            cached_time, cached_news = self._news_cache[cache_key]
            if (datetime.now() - cached_time).seconds < 300:
                logger.debug(f"News cache hit for {symbol}")
                return cached_news

        all_news = []

        # Source 1: Finnhub (fastest - real-time)
        finnhub_news = self._get_finnhub_news(symbol)
        all_news.extend(finnhub_news)
        logger.debug(f"  Finnhub: {len(finnhub_news)} articles for {symbol}")

        # Source 2: Alpha Vantage
        alpha_news = self._get_alpha_vantage_news(symbol)
        all_news.extend(alpha_news)
        logger.debug(f"  Alpha Vantage: {len(alpha_news)} articles for {symbol}")

        # Source 3: Yahoo Finance (fallback)
        yahoo_news = self._get_yahoo_news(symbol)
        all_news.extend(yahoo_news)
        logger.debug(f"  Yahoo: {len(yahoo_news)} articles for {symbol}")

        # Deduplicate
        unique_news = self._deduplicate_news(all_news)

        # Score freshness and source quality
        for item in unique_news:
            item["freshness_score"] = self._calculate_freshness(item.get("published_at", ""))
            item["source_quality"] = self._source_quality(item.get("source", ""))

        # Sort by combined score (newest + best source first)
        unique_news.sort(key=lambda x: (x["freshness_score"] + x["source_quality"]) / 2, reverse=True)

        result = unique_news[:max_items]
        self._news_cache[cache_key] = (datetime.now(), result)

        if result:
            avg_freshness = sum(n.get("freshness_score", 0) for n in result) / len(result)
            logger.info(f"News for {symbol}: {len(result)} articles | Avg freshness: {avg_freshness:.2f}/1.0")
        else:
            logger.warning(f"No news found for {symbol}")

        return result

    def _get_finnhub_news(self, symbol: str) -> List[dict]:
        """Finnhub - real-time financial news (fastest free source)"""
        if not self.finnhub_key or self.finnhub_key in ("your_finnhub_key_here", ""):
            return []
        try:
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
            logger.debug(f"Finnhub error for {symbol}: {e}")
            return []

    def _get_alpha_vantage_news(self, symbol: str) -> List[dict]:
        """Alpha Vantage - news with sentiment scores"""
        if not self.alpha_key or self.alpha_key in ("your_alpha_vantage_key_here", ""):
            return []
        try:
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
            logger.debug(f"Alpha Vantage error for {symbol}: {e}")
            return []

    def _get_yahoo_news(self, symbol: str) -> List[dict]:
        """Yahoo Finance - fallback news source"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            parsed = []
            for item in news[:15]:
                pub_time = ""
                if item.get("providerPublishTime"):
                    try:
                        pub_time = datetime.fromtimestamp(item["providerPublishTime"]).isoformat()
                    except:
                        pass
                parsed.append({
                    "title": item.get("title", ""),
                    "source": "YahooFinance",
                    "published_at": pub_time,
                    "url": item.get("link", ""),
                })
            return parsed
        except Exception as e:
            logger.debug(f"Yahoo news error for {symbol}: {e}")
            return []

    def _deduplicate_news(self, news_list: List[dict]) -> List[dict]:
        """Remove duplicate/similar headlines using title hashing"""
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
            pub_time = None
            if "T" in published_at:
                clean = published_at.replace("Z", "+00:00")
                if "+" in clean:
                    clean = clean.split("+")[0].split("[")[0]
                pub_time = datetime.fromisoformat(clean)
            else:
                return 0.3

            if pub_time:
                age_minutes = (datetime.now() - pub_time.replace(tzinfo=None)).total_seconds() / 60
                if age_minutes <= 5:
                    return 1.0
                elif age_minutes <= 15:
                    return 0.9
                elif age_minutes <= 30:
                    return 0.7
                elif age_minutes <= 60:
                    return 0.5
                elif age_minutes <= 120:
                    return 0.3
                else:
                    return 0.1
        except:
            pass
        return 0.3

    def _source_quality(self, source: str) -> float:
        """Rate source reliability from 0 to 1"""
        ratings = {
            "Finnhub": 0.9,
            "AlphaVantage": 0.8,
            "YahooFinance": 0.6,
        }
        return ratings.get(source, 0.5)

    def get_news_freshness_factor(self, news_list: List[dict]) -> float:
        """Calculate a confidence multiplier based on news freshness"""
        if not news_list:
            return 0.5

        avg_freshness = sum(n.get("freshness_score", 0) for n in news_list) / len(news_list)

        if avg_freshness >= 0.8:
            return 1.0
        elif avg_freshness >= 0.6:
            return 0.85
        elif avg_freshness >= 0.4:
            return 0.65
        else:
            return 0.4

    # ==================== ACCURACY TRACKING ====================

    def _load_accuracy_log(self):
        """Load previous prediction accuracy data"""
        accuracy_file = "logs/accuracy_log.json"
        if os.path.exists(accuracy_file):
            try:
                with open(accuracy_file) as f:
                    self.predictions = json.load(f)
                logger.info(f"Loaded {len(self.predictions)} historical predictions")
            except:
                self.predictions = []

    def _save_accuracy_log(self):
        """Save prediction accuracy data"""
        os.makedirs("logs", exist_ok=True)
        with open("logs/accuracy_log.json", "w") as f:
            json.dump(self.predictions[-500:], f, indent=2, default=str)  # Keep last 500

    def record_prediction(self, symbol: str, action: str, price: float,
                         ai_confidence: float, reason: str, news_freshness: float):
        """Record an AI prediction for later accuracy checking"""
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
        """Check past predictions against current prices"""
        checked = 0
        for pred in self.predictions:
            if pred.get("outcome_checked"):
                continue

            age_hours = (datetime.now() - datetime.fromisoformat(pred["timestamp"])).total_seconds() / 3600
            if age_hours < 24:
                continue  # Too soon to check

            current_price = market_prices.get(pred["symbol"])
            if not current_price or pred["entry_price"] == 0:
                continue

            pnl_pct = (current_price - pred["entry_price"]) / pred["entry_price"]
            if pred["action"] == "SELL":
                pnl_pct = -pnl_pct  # For sells, we want price to go down

            pred["outcome_pnl_pct"] = round(pnl_pct * 100, 2)
            pred["outcome_correct"] = pnl_pct > 0
            pred["outcome_checked"] = True
            checked += 1

        if checked > 0:
            self._save_accuracy_log()
            logger.info(f"Checked outcomes for {checked} past predictions")

    def get_accuracy_stats(self) -> dict:
        """Get AI prediction accuracy statistics"""
        checked = [p for p in self.predictions if p.get("outcome_checked")]
        if not checked:
            return {"total_checked": 0, "accuracy": 0, "message": "No predictions checked yet"}

        correct = sum(1 for p in checked if p.get("outcome_correct"))
        total = len(checked)
        accuracy = (correct / total) * 100

        # Accuracy by confidence level
        high_conf = [p for p in checked if p.get("ai_confidence", 0) >= 0.8]
        med_conf = [p for p in checked if 0.5 <= p.get("ai_confidence", 0) < 0.8]
        low_conf = [p for p in checked if p.get("ai_confidence", 0) < 0.5]

        high_acc = (sum(1 for p in high_conf if p.get("outcome_correct")) / max(len(high_conf), 1)) * 100
        med_acc = (sum(1 for p in med_conf if p.get("outcome_correct")) / max(len(med_conf), 1)) * 100
        low_acc = (sum(1 for p in low_conf if p.get("outcome_correct")) / max(len(low_conf), 1)) * 100

        # Accuracy by news freshness
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
        """Display accuracy statistics"""
        stats = self.get_accuracy_stats()
        if stats["total_checked"] == 0:
            return

        print(f"""
╔══════════════════════════════════════════════════╗
║           AI ACCURACY REPORT                     ║
╠══════════════════════════════════════════════════╣
║ Predictions Checked: {stats['total_checked']:>5}                        ║
║ Overall Accuracy:    {stats['accuracy']:>5.1f}%                       ║
╠══════════════════════════════════════════════════╣
║ By Confidence:                                   ║
║   High (>80%):       {stats['by_confidence']['high_confidence_accuracy']:>5.1f}%                       ║
║   Medium (50-80%):   {stats['by_confidence']['medium_confidence_accuracy']:>5.1f}%                       ║
║   Low (<50%):        {stats['by_confidence']['low_confidence_accuracy']:>5.1f}%                       ║
╠══════════════════════════════════════════════════╣
║ By News Freshness:                               ║
║   Fresh News:        {stats['by_freshness']['fresh_news_accuracy']:>5.1f}%                       ║
║   Stale News:        {stats['by_freshness']['stale_news_accuracy']:>5.1f}%                       ║
╚══════════════════════════════════════════════════╝
        """)