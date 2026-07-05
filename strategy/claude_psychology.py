"""
Psychology Module - DeepSeek for daily analysis, Claude Haiku for extremes.
Blind pipeline - human behavior only, never sees research output.
Claude only activates on: paradigm_shift, capitulation, or extreme sentiment.
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
class PsychologySignal:
    sentiment_score: float
    confidence: float
    behavioral_bias: str
    crowd_behavior: str
    recommendation: str
    reasoning: str


class ClaudePsychology:
    """Psychology: DeepSeek daily, Claude Haiku for extreme events"""

    def __init__(self, config):
        self.deepseek_key = config.deepseek.api_key
        self.claude_key = config.claude.api_key
        self.use_claude_backup = config.use_claude_for_extremes
        self.temperature = config.claude.temperature
        self.max_retries = config.claude.max_retries
        
        self.deepseek_enabled = bool(self.deepseek_key and self.deepseek_key not in ("your_deepseek_key_here", ""))
        self.claude_enabled = bool(self.claude_key and self.claude_key not in ("your_claude_key_here", ""))
        
        if self.claude_enabled and self.use_claude_backup:
            from anthropic import Anthropic
            self.claude_client = Anthropic(api_key=self.claude_key)
            self.claude_model = config.claude.model_name
            logger.info("Psychology: DeepSeek (daily) + Claude Haiku (extreme events backup)")
        elif self.deepseek_enabled:
            logger.info("Psychology: DeepSeek only (cheap mode)")
        else:
            logger.warning("Psychology: OFFLINE - no API keys")
        
        self.enabled = self.deepseek_enabled or self.claude_enabled
        self._cache = {}
        self._cache_ttl = timedelta(hours=4)

    def analyze(self, symbol: str, price_change: float, headlines: List[str],
               volatility: float, is_extreme_event: bool = False) -> Optional[PsychologySignal]:
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"psych_{symbol}_{'|'.join(sorted(headlines))}".encode()).hexdigest()
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_result

        # Use Claude ONLY for extreme events (paradigm shift, capitulation)
        use_claude = is_extreme_event and self.claude_enabled and self.use_claude_backup
        
        if use_claude:
            logger.info(f"Psychology: Using CLAUDE HAIIKU for extreme event on {symbol}")
            result = self._call_claude(symbol, price_change, headlines, volatility)
        else:
            result = self._call_deepseek(symbol, price_change, headlines, volatility)

        if result:
            self._cache[cache_key] = (datetime.now(), result)
        return result

    def _call_deepseek(self, symbol: str, price_change: float, headlines: List[str], volatility: float) -> Optional[PsychologySignal]:
        if not self.deepseek_enabled:
            return None
        
        news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No significant news."
        
        prompt = f"""You are a behavioral finance psychologist and pattern recognition expert.

Symbol: {symbol}
10-day return: {price_change:.2%}
Recent volatility: {volatility:.2%}
Recent news: {news_text}

Using your mathematical psychology expertise:
1. Identify the dominant cognitive bias at play
2. Predict crowd behavior using quantitative behavioral models
3. Assess if this is an overreaction or rational response
4. Output a mathematical confidence score

CRITICAL: Focus on human psychology patterns only. No fundamental analysis.

Return ONLY this JSON (no markdown):
{{"sentiment_score": <float -1.0 (extreme fear) to 1.0 (extreme greed)>, "confidence": <float 0.0 to 1.0>, "behavioral_bias": "<anchoring|herding|overreaction|loss_aversion|confirmation|recency>", "crowd_behavior": "<panic_selling|fomo_buying|complacent|confused|capitulation>", "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|reverse|no_change>", "reasoning": "<one sentence>"}}"""

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.deepseek_key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": self.temperature, "max_tokens": 300},
                    timeout=30
                )
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text.startswith("```"): text = text.split("\n", 1)[1]
                if text.endswith("```"): text = text[:-3]
                data = json.loads(text.strip())
                signal = PsychologySignal(
                    sentiment_score=float(data["sentiment_score"]),
                    confidence=float(data["confidence"]),
                    behavioral_bias=data["behavioral_bias"],
                    crowd_behavior=data["crowd_behavior"],
                    recommendation=data["recommendation"],
                    reasoning=data["reasoning"]
                )
                logger.info(f"DeepSeek Psych: {symbol} | bias={signal.behavioral_bias} | crowd={signal.crowd_behavior}")
                return signal
            except Exception as e:
                logger.warning(f"DeepSeek psych attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        return None

    def _call_claude(self, symbol: str, price_change: float, headlines: List[str], volatility: float) -> Optional[PsychologySignal]:
        news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No significant news."
        
        prompt = f"""You are an expert behavioral psychologist. This is a POTENTIALLY EXTREME market event requiring your best judgment.

Symbol: {symbol}
10-day return: {price_change:.2%}
Recent volatility: {volatility:.2%}
Recent news: {news_text}

This event may be a paradigm shift or capitulation. Analyze the HUMAN PSYCHOLOGY deeply.
Return ONLY JSON: {{"sentiment_score": <float -1.0 to 1.0>, "confidence": <float 0.0 to 1.0>, "behavioral_bias": "<anchoring|herding|overreaction|loss_aversion|confirmation|recency>", "crowd_behavior": "<panic_selling|fomo_buying|complacent|confused|capitulation>", "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|reverse|no_change>", "reasoning": "<one sentence>"}}"""

        for attempt in range(self.max_retries):
            try:
                response = self.claude_client.messages.create(
                    model=self.claude_model,
                    max_tokens=300,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
                if text.startswith("```"): text = text.split("\n", 1)[1]
                if text.endswith("```"): text = text[:-3]
                data = json.loads(text.strip())
                signal = PsychologySignal(**data)
                logger.info(f"Claude Haiku: {symbol} | EXTREME EVENT | bias={signal.behavioral_bias}")
                return signal
            except Exception as e:
                logger.warning(f"Claude attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        return None