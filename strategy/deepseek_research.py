"""
DeepSeek Research Analyst - Elite Quantitative Analysis
Pure Math & Technical Focus — No psychology, no narratives.
Grok-optimized prompt with statistical rigor.
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import requests
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DeepSeekResearch:
    """Elite Quantitative Analyst - Pure Math & Technical Focus"""

    def __init__(self, config):
        self.api_key = config.deepseek.api_key
        self.model = config.deepseek.model
        self.temperature = config.deepseek.temperature
        self.max_retries = config.deepseek.max_retries
        self.cache_enabled = config.deepseek.cache_enabled
        self.cache_ttl_hours = config.deepseek.cache_ttl_hours

        self._cache = {}
        self._cache_ttl = timedelta(hours=self.cache_ttl_hours)

        if self.api_key and self.api_key not in ["", "your_key_here", "your_deepseek_key_here"]:
            logger.info(f"DeepSeek Research Online (model: {self.model})")
        else:
            logger.warning("DeepSeek Research OFFLINE - No API key")

    def analyze(self, symbol: str, history: pd.Series, current_price: float,
                macro: dict = None, rsi: float = None, atr: float = None) -> Optional[dict]:
        """Pure mathematical/technical analysis"""
        if not self.api_key or not symbol:
            return None

        # Create cache key based on key inputs
        cache_key = hashlib.md5(f"{symbol}_{current_price:.4f}_{rsi or 50:.1f}_{hash(str(macro))}".encode()).hexdigest()

        if self.cache_enabled and cache_key in self._cache:
            cached_time, result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return result

        # Prepare technical context
        period_return = self._calculate_return(history)
        volatility = self._calculate_volatility(history)
        ma_distance = self._calculate_ma_distance(history)

        prompt = f"""You are an elite quantitative trading analyst. Analyze {symbol} using ONLY mathematical and technical facts.

CURRENT DATA:
- Symbol: {symbol}
- Current Price: ${current_price:.2f}
- 10-day Return: {period_return:+.2% if period_return is not None else 'N/A'}
- Annualized Volatility: {volatility:.1% if volatility else 'N/A'}
- RSI (14): {rsi:.1f if rsi else 'N/A'}
- ATR (normalized): {atr:.3f if atr else 'N/A'}
- Distance from 50-day MA: {ma_distance:+.2f}% if ma_distance else 'N/A'

MACRO CONTEXT:
- VIX: {macro.get('vix', 'N/A') if macro else 'N/A'}
- Market Regime: {macro.get('regime', 'normal') if macro else 'normal'}

TASK:
Evaluate if this is a statistically attractive setup.
Be conservative. Only recommend action when there is clear edge.

Respond with **valid JSON only**:
{{
  "sentiment_score": <float from -1.0 (strong sell) to +1.0 (strong buy)>,
  "confidence": <float 0.0-1.0>,
  "recommendation": "amplify_buy | dampen_buy | amplify_sell | dampen_sell | no_change",
  "key_findings": "one short sentence citing numbers (RSI, vol, return, etc.)",
  "horizon": "short | medium | long"
}}"""

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": self.temperature,
                        "max_tokens": 400
                    },
                    timeout=25
                )

                content = response.json()["choices"][0]["message"]["content"].strip()
                # Clean possible markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1]

                data = json.loads(content.strip())

                result = {
                    "sentiment_score": float(data.get("sentiment_score", 0)),
                    "confidence": float(data.get("confidence", 0.5)),
                    "recommendation": data.get("recommendation", "no_change"),
                    "key_findings": data.get("key_findings", ""),
                    "horizon": data.get("horizon", "medium")
                }

                if self.cache_enabled:
                    self._cache[cache_key] = (datetime.now(), result)

                logger.info(f"DeepSeek {symbol} | Score: {result['sentiment_score']:.2f} | Conf: {result['confidence']:.2f} | {result['key_findings'][:80]}")
                return result

            except Exception as e:
                logger.warning(f"DeepSeek attempt {attempt+1} failed: {e}")
                time.sleep(1.5)

        return None

    # ==================== HELPER METHODS ====================

    def _calculate_return(self, prices: pd.Series) -> Optional[float]:
        """10-day period return"""
        if len(prices) < 11:
            return None
        return (prices.iloc[-1] - prices.iloc[-11]) / prices.iloc[-11]

    def _calculate_volatility(self, prices: pd.Series) -> float:
        """Annualized volatility"""
        if len(prices) < 20:
            return 0.0
        returns = prices.pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def _calculate_ma_distance(self, prices: pd.Series) -> float:
        """Distance from 50-day moving average in percent"""
        if len(prices) < 50:
            return 0.0
        ma50 = prices.iloc[-50:].mean()
        return (prices.iloc[-1] - ma50) / ma50 * 100