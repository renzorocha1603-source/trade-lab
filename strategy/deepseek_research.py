"""
DeepSeek Research Analyst - Smarter AI with technical + macro context.
Receives pre-calculated indicators (RSI, MACD, volume) and macro data.
Blind pipeline - never sees Claude's output.
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
    """DeepSeek research analyst with technical + macro awareness"""

    def __init__(self, config):
        self.api_key = config.deepseek.api_key
        self.enabled = bool(self.api_key and self.api_key not in ("your_deepseek_key_here", ""))
        self.temperature = config.deepseek.temperature
        self.max_retries = config.deepseek.max_retries
        self.cache_enabled = config.deepseek.cache_enabled
        self._cache = {}
        self._cache_ttl = timedelta(hours=config.deepseek.cache_ttl_hours)

        if self.enabled:
            logger.info("DeepSeek Research: ONLINE (smarter AI mode)")
        else:
            logger.warning("DeepSeek Research: OFFLINE")

    def analyze(self, symbol: str, price_change: float, headlines: List[str],
               volatility: float, rsi: float = 50.0, volume_trend: str = "normal",
               ma_distance: float = 0.0, macro_context: dict = None) -> Optional[ResearchSignal]:
        if not self.enabled:
            return None

        cache_key = hashlib.md5(f"{symbol}_{price_change:.4f}_{rsi:.1f}".encode()).hexdigest()
        if self.cache_enabled and cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_result

        news_text = "\n".join(f"- {h}" for h in headlines[:5]) if headlines else "No significant news."

        # Build macro context string
        macro_str = ""
        if macro_context:
            macro_str = f"""
MACRO CONTEXT (use this to judge market regime):
- VIX: {macro_context.get('vix', 'N/A')}
- USD/CAD: {macro_context.get('usdcad', 'N/A')}
- Oil (WTI): ${macro_context.get('oil', 'N/A')}
- Sector trend: {macro_context.get('sector', 'neutral')}
- Market regime: {macro_context.get('regime', 'normal')}
"""

        # Detect asset type for specific guidance
        asset_type = "stock"
        if ".TO" in symbol:
            asset_type = "canadian_stock"
        elif "-USD" in symbol:
            asset_type = "crypto"
        elif symbol in ["SPY", "QQQ", "IWM", "DIA", "VTI", "XIU.TO", "VFV.TO"]:
            asset_type = "broad_etf"
        elif symbol in ["XLF", "XLK", "XLE", "XLV"]:
            asset_type = "sector_etf"

        asset_guidance = {
            "canadian_stock": "- CAD strength and oil prices directly impact this stock.",
            "crypto": "- Crypto is volatile. Weekend moves are common. VIX correlation is inconsistent.",
            "broad_etf": "- This represents the broad market. Use macro context heavily.",
            "sector_etf": "- This represents a specific sector. Consider sector rotation patterns.",
            "stock": "- Individual stock. News and technicals matter most."
        }.get(asset_type, "")

        prompt = f"""You are an elite quantitative analyst. Analyze {symbol} ({asset_type}) using FACTS only.

PRICE DATA:
- Symbol: {symbol}
- 10-day return: {price_change:.2%}
- Recent volatility: {volatility:.2%}
- Current RSI (14): {rsi:.1f} (oversold < 30, overbought > 70)
- Volume trend: {volume_trend}
- Distance from 50-day MA: {ma_distance:+.1f}%
{macro_str}

TECHNICAL SUMMARY:
- RSI {rsi:.1f}: {'OVERSOLD - potential bounce' if rsi < 30 else 'OVERBOUGHT - potential pullback' if rsi > 70 else 'NEUTRAL'}
- Volume: {volume_trend} - {'confirms move' if volume_trend == 'increasing' else 'weak signal' if volume_trend == 'decreasing' else 'normal'}
- MA distance: {ma_distance:+.1f}% from 50-day - {'extended above' if ma_distance > 10 else 'extended below' if ma_distance < -10 else 'normal range'}

RECENT NEWS:
{news_text}

ASSET GUIDANCE:
{asset_guidance}

RULES:
- RSI, volume, and MA values are pre-calculated FACTS. Use them.
- Is this move STATISTICALLY significant or just noise?
- Consider MACRO CONTEXT: high VIX = fear, low VIX = complacency.
- For Canadian stocks: oil and CAD matter.
- Confidence must be JUSTIFIED by the data.

Return ONLY this JSON (no markdown, no explanation outside JSON):
{{"sentiment_score": <float -1.0 to 1.0>, "confidence": <float 0.0 to 1.0>, "impact_horizon": "<noise|intraday|multi-week|paradigm_shift>", "recommendation": "<amplify_buy|dampen_buy|amplify_sell|dampen_sell|no_change>", "key_findings": "<one sentence citing specific data>"}}"""

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
                logger.info(f"DeepSeek: {symbol} | RSI={rsi:.1f} | score={signal.sentiment_score:.2f} | conf={signal.confidence:.2f} | {signal.key_findings}")
                return signal
            except Exception as e:
                logger.warning(f"DeepSeek attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        return None