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
    risk_profile: str = "balanced"
    z_score_lookback: int = 252
    sharpe_lookback: int = 60
    training_mode: bool = True

@dataclass
class RiskConfig:
    max_position_size_cad: float = 10000
    max_portfolio_drawdown: float = 0.95
    max_daily_loss_cad: float = 50000
    max_positions: int = 20
    emergency_stop_file: str = "EMERGENCY_STOP"
    require_market_open: bool = False
    auto_reload_threshold: float = 50.0
    auto_reload_amount: float = 5000.0

@dataclass
class ScheduleConfig:
    run_time: str = "16:30"
    run_days: List[str] = field(default_factory=lambda: ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"])

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
    symbols: List[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "AAPL", "MSFT", "NVDA",
        "GOOGL", "AMZN", "META", "TSLA", "JPM", "V", "JNJ",
        "IWM", "DIA", "XLF", "XLK", "XLE",
        "RY.TO", "TD.TO", "SHOP.TO", "ENB.TO", "CNQ.TO",
        "XIU.TO", "VFV.TO",
        "BABA", "TSM", "WMT", "XOM", "XLV",
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
        "ADA-USD", "AVAX-USD", "DOT-USD", "MATIC-USD", "LINK-USD",
        "UNI-USD", "ATOM-USD", "XLM-USD", "FIL-USD", "NEAR-USD",
        "ALGO-USD", "VET-USD", "ICP-USD", "GRT-USD", "FTM-USD"
    ])
    benchmark: str = "SPY"

@dataclass
class NewsConfig:
    finnhub_api_key: str = field(default_factory=lambda: os.getenv("FINNHUB_API_KEY", ""))
    alpha_vantage_api_key: str = field(default_factory=lambda: os.getenv("ALPHA_VANTAGE_API_KEY", ""))
    max_news_age_minutes: int = 30
    freshness_decay_enabled: bool = True
    min_confidence_for_stale_news: float = 0.3

@dataclass
class CryptoConfig:
    binance_api_key: str = ""
    binance_api_secret: str = ""
    use_binance_public: bool = True
    atr_multiplier_target: float = 1.5
    atr_multiplier_stop: float = 1.0
    max_hold_hours: float = 4.0
    kelly_fraction: float = 0.3
    min_volume_multiplier: float = 1.5
    fee_pct: float = 0.003
    min_net_ev: float = 0.005
    btc_timeframe: str = "1h"
    eth_timeframe: str = "15m"
    crypto_symbols: List[str] = field(default_factory=lambda: [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
        "ADA-USD", "AVAX-USD", "DOT-USD", "MATIC-USD", "LINK-USD",
        "UNI-USD", "ATOM-USD", "XLM-USD", "FIL-USD", "NEAR-USD",
        "ALGO-USD", "VET-USD", "ICP-USD", "GRT-USD", "FTM-USD"
    ])

@dataclass
class RiskProfileConfig:
    """TRAINING MODE — Ultra-aggressive for maximum learning"""
    conservative: dict = field(default_factory=lambda: {
        "name": "Conservative Training",
        "z_score_threshold": -0.8,
        "kelly_fraction": 0.75,
        "ev_minimum": 0.0,
        "sharpe_minimum": 0.0,
        "use_rsi_filter": True,
        "rsi_threshold_modifier": 5,
        "use_atr_filter": False,
        "use_sector_limits": False,
        "max_sector_positions": 99,
        "cash_reserve_pct": 0.03,
        "max_positions": 10,
        "can_trade_us": True,
        "min_notional": 0.50,
    })
    balanced: dict = field(default_factory=lambda: {
        "name": "Balanced Training",
        "z_score_threshold": -0.5,
        "kelly_fraction": 1.0,
        "ev_minimum": -0.001,
        "sharpe_minimum": 0.0,
        "use_rsi_filter": True,
        "rsi_threshold_modifier": 0,
        "use_atr_filter": False,
        "use_sector_limits": False,
        "max_sector_positions": 99,
        "cash_reserve_pct": 0.02,
        "max_positions": 15,
        "can_trade_us": True,
        "min_notional": 0.25,
    })
    aggressive: dict = field(default_factory=lambda: {
        "name": "Aggressive Training",
        "z_score_threshold": -0.3,
        "kelly_fraction": 1.5,
        "ev_minimum": -0.005,
        "sharpe_minimum": -0.5,
        "use_rsi_filter": False,
        "rsi_threshold_modifier": -20,
        "use_atr_filter": False,
        "use_sector_limits": False,
        "max_sector_positions": 99,
        "cash_reserve_pct": 0.01,
        "max_positions": 20,
        "can_trade_us": True,
        "min_notional": 0.10,
    })
    pennies: dict = field(default_factory=lambda: {
        "name": "Pennies Training",
        "z_score_threshold": -1.5,
        "kelly_fraction": 0.30,
        "ev_minimum": 0.005,
        "sharpe_minimum": 0.3,
        "use_rsi_filter": False,
        "rsi_threshold_modifier": 0,
        "use_atr_filter": True,
        "use_sector_limits": False,
        "max_sector_positions": 99,
        "cash_reserve_pct": 0.05,
        "max_positions": 5,
        "can_trade_us": True,
        "min_notional": 1.0,
    })

@dataclass
class Config:
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    risk_profile: RiskProfileConfig = field(default_factory=RiskProfileConfig)
    crypto: CryptoConfig = field(default_factory=CryptoConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    data: DataConfig = field(default_factory=DataConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    use_ai: bool = True
    use_claude_for_extremes: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"