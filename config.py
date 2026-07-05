import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List

load_dotenv()

@dataclass
class DeepSeekConfig:
    """DeepSeek - Primary AI for all daily analysis"""
    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_retries: int = 3
    cache_enabled: bool = True
    cache_ttl_hours: int = 4
    confidence_threshold: float = 0.6

@dataclass
class ClaudeConfig:
    """Claude Haiku - Premium backup for extreme events only"""
    api_key: str = field(default_factory=lambda: os.getenv("CLAUDE_API_KEY", ""))
    model_name: str = "claude-haiku-3-5-20241022"
    temperature: float = 0.3
    max_retries: int = 2
    confidence_threshold: float = 0.6

@dataclass
class StrategyConfig:
    lookback_days: int = 10
    loss_threshold: float = -0.03
    profit_threshold: float = 0.05
    buy_fraction: float = 0.05
    sell_fraction: float = 0.10
    initial_position_pct: float = 0.10

@dataclass
class RiskConfig:
    max_position_size_cad: float = 10000
    max_portfolio_drawdown: float = 0.20
    max_daily_loss_cad: float = 5000
    max_positions: int = 10
    emergency_stop_file: str = "EMERGENCY_STOP"
    require_market_open: bool = False

@dataclass
class ScheduleConfig:
    run_time: str = "16:30"
    run_days: List[str] = field(default_factory=lambda: ["monday","tuesday","wednesday","thursday","friday"])

@dataclass
class BrokerConfig:
    paper_trading: bool = True
    base_currency: str = "CAD"
    initial_capital_cad: float = 100000
    monthly_deposit_cad: float = 0
    fx_fee_pct: float = 0.015
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.0005
    allow_fractional_shares: bool = True

@dataclass
class DataConfig:
    historical_years: int = 1
    symbols: List[str] = field(default_factory=lambda: ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","JPM","V","JNJ"])
    benchmark: str = "SPY"

@dataclass
class NewsConfig:
    """Multi-source news configuration"""
    finnhub_api_key: str = field(default_factory=lambda: os.getenv("FINNHUB_API_KEY", ""))
    alpha_vantage_api_key: str = field(default_factory=lambda: os.getenv("ALPHA_VANTAGE_API_KEY", ""))
    max_news_age_minutes: int = 30
    freshness_decay_enabled: bool = True
    min_confidence_for_stale_news: float = 0.3

@dataclass
class Config:
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    data: DataConfig = field(default_factory=DataConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    use_ai: bool = True
    use_claude_for_extremes: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"