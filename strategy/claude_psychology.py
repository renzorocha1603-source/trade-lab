"""
Claude AI - Behavioral Psychologist (Blind Pipeline)
Analyzes human emotional reaction, fear/greed, cognitive biases.
NEVER sees Gemini's output. NEVER debates.
Outputs structured JSON signal only.
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import logging

from anthropic import Anthropic

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
    """Blind psychology analyst - human behavior only, no fundamentals"""

    def __init__(self, config):
        self.config = config.claude
        self.enabled = bool(self.config.api_key and self.config.api_key != "your_claude_key_here")
        if not self.enabled:
            logger.warning("Claude API key not set. Psychology module disabled.")
            return

        self.client = Anthropic(api_key=self.config.api_key)
        self._cache = {}
        self._cache_ttl = timedelta(hours=4)
        logger.info(f"Claude Psychology initialized (model: {self.config.model_name})")

    def analyze(self, symbol: str, price_change: float, headlines: List[str],
               volatility: float) -> Optional[PsychologySignal]:
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"{symbol}_{'|'.join(sorted(headlines))}".encode()).hexdigest()
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_result

        news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No significant news."

        prompt = f"""You are a behavioral finance psychologist. Analyze the HUMAN REACTION to this market event.

Symbol: {symbol}
10-day return: {price_change:.2%}
Recent volatility: {volatility:.2%}

Recent news:
{news_text}

CRITICAL RULES:
- Analyze human psychology, emotions, and behavioral biases ONLY
- Do NOT analyze fundamentals, valuations, or economic data
- Do NOT mention company performance or financial metrics
- Focus on: fear, greed, panic, euphoria, anchoring, herding, overreaction

Return ONLY this JSON (no other text):
{{
    "sentiment_score": <float -1.0 (extreme fear) to 1.0 (extreme greed)>,
    "confidence": <float 0.0 to 1.0>,
    "behavioral_bias": "<anchoring|herding|overreaction|loss_aversion|confirmation|recency>",
    "crowd_behavior": "<panic_selling|fomo_buying|complacent|confused|capitulation>",
    "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|reverse|no_change>",
    "reasoning": "<one sentence on what the crowd is likely doing wrong>"
}}"""

        for attempt in range(self.config.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.config.model_name,
                    max_tokens=500,
                    temperature=self.config.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
                if text.startswith("```"): text = text.split("\n", 1)[1]
                if text.endswith("```"): text = text[:-3]
                text = text.strip()

                data = json.loads(text)
                signal = PsychologySignal(
                    sentiment_score=float(data["sentiment_score"]),
                    confidence=float(data["confidence"]),
                    behavioral_bias=data["behavioral_bias"],
                    crowd_behavior=data["crowd_behavior"],
                    recommendation=data["recommendation"],
                    reasoning=data["reasoning"]
                )
                self._cache[cache_key] = (datetime.now(), signal)
                logger.info(f"Claude: {symbol} | bias={signal.behavioral_bias} | crowd={signal.crowd_behavior}")
                return signal

            except json.JSONDecodeError as e:
                logger.warning(f"Claude JSON error (attempt {attempt+1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Claude API error: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2)

        return None