"""
DeepSeek Research Analyst - Primary AI for daily analysis.
Blind pipeline - facts, data, and math. Never sees psychology output.
DeepSeek excels at quantitative reasoning and numerical analysis.
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import logging
import requests

logger = logging.getLogger(__name__)


@dataclass
class ResearchSignal:
    sentiment_score: float
    confidence: float
    impact_horizon: str
    recommendation: str
    key_findings: str


class DeepSeekResearch:
    """DeepSeek research analyst - math & data focused"""

    def __init__(self, config):
        self.api_key = config.deepseek.api_key
        self.enabled = bool(self.api_key and self.api_key not in ("your_deepseek_key_here", ""))
        self.temperature = config.deepseek.temperature
        self.max_retries = config.deepseek.max_retries
        self.cache_enabled = config.deepseek.cache_enabled
        self._cache = {}
        self._cache_ttl = timedelta(hours=config.deepseek.cache_ttl_hours)
        if self.enabled:
            logger.info("DeepSeek Research: ONLINE (primary AI)")
        else:
            logger.warning("DeepSeek Research: OFFLINE - no API key")

    def analyze(self, symbol: str, price_change: float, headlines: List[str],
               volatility: float) -> Optional[ResearchSignal]:
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"research_{symbol}_{'|'.join(sorted(headlines))}".encode()).hexdigest()
        if self.cache_enabled and cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                logger.debug(f"Research cache hit for {symbol}")
                return cached_result

        news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No significant news."

        prompt = f"""You are an elite quantitative research analyst with deep mathematical expertise.

Symbol: {symbol}
10-day return: {price_change:.2%}
Recent volatility: {volatility:.2%}
Recent news: {news_text}

Analyze using your mathematical and engineering mindset:
1. Statistical significance of the price movement
2. Pattern recognition from historical behavior
3. Data-driven probability assessment
4. Ignore emotions - pure quantitative analysis

Return ONLY this JSON (no markdown, no code blocks):
{{"sentiment_score": <float -1.0 to 1.0>, "confidence": <float 0.0 to 1.0>, "impact_horizon": "<noise|intraday|multi-week|paradigm_shift>", "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|no_change>", "key_findings": "<one sentence quantitative summary>"}}"""

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": self.temperature, "max_tokens": 300},
                    timeout=30
                )
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text.startswith("```"): text = text.split("\n", 1)[1]
                if text.endswith("```"): text = text[:-3]
                text = text.strip()

                data = json.loads(text)
                signal = ResearchSignal(
                    sentiment_score=float(data["sentiment_score"]),
                    confidence=float(data["confidence"]),
                    impact_horizon=data["impact_horizon"],
                    recommendation=data["recommendation"],
                    key_findings=data["key_findings"]
                )
                if self.cache_enabled:
                    self._cache[cache_key] = (datetime.now(), signal)
                logger.info(f"DeepSeek Research: {symbol} | score={signal.sentiment_score:.2f} | confidence={signal.confidence:.2f} | {signal.key_findings}")
                return signal
            except Exception as e:
                logger.warning(f"DeepSeek research attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        return None