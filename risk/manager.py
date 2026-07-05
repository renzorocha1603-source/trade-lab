"""
Risk Manager - Circuit breakers and safety limits.
Protects portfolio from catastrophic losses.
"""

import os
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class RiskManager:
    """Central risk management with circuit breakers"""

    def __init__(self, config):
        self.config = config.risk
        self.max_position_size = config.risk.max_position_size_cad
        self.max_drawdown = config.risk.max_portfolio_drawdown
        self.max_daily_loss = config.risk.max_daily_loss_cad
        self.max_positions = config.risk.max_positions
        self.daily_start_equity = None
        self.last_trading_day = None
        self.emergency_stop_triggered = False

    def check_emergency_stop(self) -> bool:
        if os.path.exists(self.config.emergency_stop_file):
            if not self.emergency_stop_triggered:
                logger.critical("EMERGENCY STOP FILE DETECTED!")
                self.emergency_stop_triggered = True
            return True
        return False

    def check_market_hours(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        return True

    def reset_daily_if_needed(self, current_equity: float):
        today = datetime.now().date()
        if self.last_trading_day != today:
            self.daily_start_equity = current_equity
            self.last_trading_day = today

    def check_daily_loss(self, current_equity: float) -> bool:
        if self.daily_start_equity is None:
            self.daily_start_equity = current_equity
            return True
        loss = self.daily_start_equity - current_equity
        if loss > self.max_daily_loss:
            logger.critical(f"DAILY LOSS LIMIT: ${loss:,.2f} (max: ${self.max_daily_loss:,.2f})")
            return False
        return True

    def check_drawdown(self, current_equity: float, initial_capital: float) -> bool:
        drawdown = (initial_capital - current_equity) / initial_capital
        if drawdown > self.max_drawdown:
            logger.critical(f"MAX DRAWDOWN: {drawdown:.1%} (max: {self.max_drawdown:.1%})")
            return False
        return True

    def check_position_count(self, current_positions: int) -> bool:
        if current_positions >= self.max_positions:
            logger.warning(f"Max positions reached: {current_positions}")
            return False
        return True

    def check_position_size(self, value_cad: float) -> bool:
        if value_cad > self.max_position_size:
            logger.warning(f"Position size ${value_cad:,.2f} exceeds max ${self.max_position_size:,.2f}")
            return False
        return True

    def is_safe(self, current_equity: float, initial_capital: float,
                current_positions: int) -> tuple:
        if self.check_emergency_stop():
            return False, "Emergency stop active"
        if self.config.require_market_open and not self.check_market_hours():
            return False, "Market closed"
        if not self.check_drawdown(current_equity, initial_capital):
            return False, "Max drawdown exceeded"
        self.reset_daily_if_needed(current_equity)
        if not self.check_daily_loss(current_equity):
            return False, "Daily loss limit reached"
        if not self.check_position_count(current_positions):
            return False, "Max positions reached"
        return True, "OK"

    def get_report(self) -> dict:
        return {
            "emergency_stop": self.check_emergency_stop(),
            "max_drawdown": f"{self.max_drawdown:.1%}",
            "max_daily_loss": f"${self.max_daily_loss:,.2f}",
            "max_positions": self.max_positions,
            "max_position_size": f"${self.max_position_size:,.2f}"
        }