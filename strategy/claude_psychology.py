import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ClaudePsychology:
    """Behavioral Finance & Psychology Analyst"""

    def __init__(self, config):
        self.deepseek_key = config.deepseek.api_key
        self.claude_key = config.claude.api_key
        self.use_claude_for_extremes = config.use_claude_for_extremes
        self.temperature = config.claude.temperature
        self.max_retries = config.claude.max_retries

        self.deepseek_enabled = bool(self.deepseek_key and self.deepseek_key.strip() and self.deepseek_key != "your_deepseek_key_here")
        self.claude_enabled = bool(self.claude_key and self.claude_key.strip() and self.claude_key != "your_claude_key_here")

        self.claude_client = None
        if self.claude_enabled and self.use_claude_for_extremes:
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=self.claude_key)
                self.claude_model = config.claude.model_name
            except ImportError:
                logger.error("Anthropic package not installed. Claude disabled.")
                self.claude_enabled = False

        self.enabled = self.deepseek_enabled or self.claude_enabled
        self._cache = {}
        self._cache_ttl = timedelta(hours=4)

        if self.enabled:
            logger.info(f"Psychology Module Online | DeepSeek: {self.deepseek_enabled} | Claude (extremes): {self.claude_enabled}")

    def analyze(self, symbol: str, price_change: float, headlines: List[str], 
                volatility: float, is_extreme: bool = False) -> Optional[dict]:
        """Main entry point"""
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"psych_{symbol}_{price_change:.3f}_{len(headlines)}".encode()).hexdigest()

        if cache_key in self._cache:
            ts, result = self._cache[cache_key]
            if datetime.now() - ts < self._cache_ttl:
                return result

        # Use Claude only for true extremes
        if is_extreme and self.claude_enabled and self.claude_client:
            result = self._call_claude(symbol, price_change, headlines, volatility)
        else:
            result = self._call_deepseek(symbol, price_change, headlines, volatility)

        if result:
            self._cache[cache_key] = (datetime.now(), result)

        return result

    def _call_deepseek(self, symbol: str, price_change: float, headlines: List[str], volatility: float) -> Optional[dict]:
        """Daily psychology using DeepSeek"""
        news_text = "\n".join(f"- {h}" for h in headlines[:4]) if headlines else "No major news."

        prompt = f"""You are a behavioral finance expert. Analyze the human psychology behind {symbol}.

Price movement: {price_change:+.2%}
Volatility: {volatility:.2%}
Recent headlines:
{news_text}

Focus ONLY on cognitive biases, crowd psychology, and emotional drivers.

Return valid JSON only:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "confidence": <float 0.0-1.0>,
  "behavioral_bias": "<herding|overreaction|loss_aversion|FOMO|panic|anchoring|recency>",
  "crowd_behavior": "<capitulation|fomo_buying|panic_selling|complacency|confusion>",
  "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|no_change>",
  "reasoning": "<one concise sentence>"
}}"""

        # ... (same request code as before, using DeepSeek API)

        # (I'll skip repeating the full request boilerplate to save space - it's similar to your original)

        return result  # return the dict

    def _call_claude(self, symbol: str, price_change: float, headlines: List[str], volatility: float) -> Optional[dict]:
        """Claude for extreme events only"""
        if not self.claude_client:
            return self._call_deepseek(symbol, price_change, headlines, volatility)

        prompt = f"""EXTREME MARKET EVENT ANALYSIS

Symbol: {symbol}
10-day return: {price_change:+.2%}
Volatility: {volatility:.2%}

Headlines:
{chr(10).join(f'- {h}' for h in headlines)}

This may be capitulation, euphoria, or a paradigm shift.
Analyze the mass psychology deeply and give your best judgment.

Return only clean JSON with the same structure as above."""

        # Claude call logic...

        return result