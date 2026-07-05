import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List

load_dotenv()

@dataclass
class GeminiConfig:
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.3
    max_retries: int = 3
    cache_enabled: bool = True
    cache_ttl_hours: int = 4
    confidence_threshold: float = 0.6

@dataclass
class ClaudeConfig:
    api_key: str = field(default_factory=lambda: os.getenv("CLAUDE_API_KEY", ""))
    model_name: str = "claude-sonnet-4-20250514"
    temperature: float = 0.3
    max_retries: int = 3
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
    require_market_open: bool = True

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
class Config:
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    data: DataConfig = field(default_factory=DataConfig)
    use_ai: bool = True
    debug_mode: bool = False