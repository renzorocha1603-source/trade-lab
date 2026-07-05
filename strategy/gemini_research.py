"""
Gemini AI - Research Analyst (Blind Pipeline)
Analyzes news, fundamentals, macro context.
NEVER sees Claude's output. NEVER debates.
Outputs structured JSON signal only.
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class ResearchSignal:
    sentiment_score: float
    confidence: float
    impact_horizon: str
    recommendation: str
    key_findings: str


class GeminiResearch:
    """Blind research analyst - facts and data only, no psychology"""

    def __init__(self, config):
        self.config = config.gemini
        self.enabled = bool(self.config.api_key and self.config.api_key != "your_gemini_key_here")
        if not self.enabled:
            logger.warning("Gemini API key not set. Research module disabled.")
            return

        genai.configure(api_key=self.config.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config={"temperature": self.config.temperature, "top_p": 0.95}
        )
        self._cache = {}
        self._cache_ttl = timedelta(hours=self.config.cache_ttl_hours)
        logger.info(f"Gemini Research initialized (model: {self.config.model_name})")

    def analyze(self, symbol: str, price_change: float, headlines: List[str],
               volatility: float) -> Optional[ResearchSignal]:
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"{symbol}_{'|'.join(sorted(headlines))}".encode()).hexdigest()
        if self.config.cache_enabled and cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_result

        news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No significant news."

        prompt = f"""You are a quantitative research analyst. Analyze this stock based on FACTS AND DATA ONLY.

Symbol: {symbol}
10-day return: {price_change:.2%}
Recent volatility: {volatility:.2%}

Recent news:
{news_text}

CRITICAL RULES:
- Analyze fundamentals, data patterns, and factual information ONLY
- Do NOT speculate about psychology, fear, greed, or human behavior
- Do NOT mention emotions or sentiment
- Be cold, clinical, and data-driven

Return ONLY this JSON (no other text):
{{
    "sentiment_score": <float -1.0 to 1.0 based on data>,
    "confidence": <float 0.0 to 1.0>,
    "impact_horizon": "<noise|intraday|multi-week|paradigm_shift>",
    "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|no_change>",
    "key_findings": "<one sentence summary of your data analysis>"
}}"""

        for attempt in range(self.config.max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
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
                if self.config.cache_enabled:
                    self._cache[cache_key] = (datetime.now(), signal)
                logger.info(f"Gemini: {symbol} | sentiment={signal.sentiment_score:.2f} | rec={signal.recommendation}")
                return signal

            except json.JSONDecodeError as e:
                logger.warning(f"Gemini JSON parse error (attempt {attempt+1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2)

        return None