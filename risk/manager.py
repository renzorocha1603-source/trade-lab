import os
import logging
from datetime import datetime, date
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class RiskManager:
    """Advanced Risk Management with Circuit Breakers & Safety Layers"""

    def __init__(self, config):
        self.config = config.risk
        
        self.max_position_size_cad = config.risk.max_position_size_cad
        self.max_portfolio_drawdown = config.risk.max_portfolio_drawdown
        self.max_daily_loss_cad = config.risk.max_daily_loss_cad
        self.max_positions = config.risk.max_positions
        self.emergency_stop_file = config.risk.emergency_stop_file

        # Internal state
        self.daily_start_equity: Optional[float] = None
        self.current_day: Optional[date] = None
        self.emergency_stop_triggered = False
        self.session_losses = 0.0

    def reset_daily(self, current_equity: float):
        """Reset daily tracking at the start of a new day"""
        today = datetime.now().date()
        if self.current_day != today:
            self.daily_start_equity = current_equity
            self.current_day = today
            self.session_losses = 0.0
            logger.info(f"RiskManager: Daily limits reset | Starting equity: ${current_equity:,.2f}")

    def check_emergency_stop(self) -> bool:
        if os.path.exists(self.emergency_stop_file):
            if not self.emergency_stop_triggered:
                logger.critical("🚨 EMERGENCY STOP FILE DETECTED - TRADING HALTED")
                self.emergency_stop_triggered = True
            return True
        return False

    def check_drawdown(self, current_equity: float, initial_capital: float) -> Tuple[bool, str]:
        drawdown = (initial_capital - current_equity) / initial_capital
        if drawdown > self.max_portfolio_drawdown:
            logger.critical(f"🚨 MAX DRAWDOWN BREACHED: {drawdown:.1%} (limit: {self.max_portfolio_drawdown:.1%})")
            return False, "max_drawdown"
        return True, "OK"

    def check_daily_loss(self, current_equity: float) -> Tuple[bool, str]:
        if self.daily_start_equity is None:
            return True, "OK"
        
        daily_loss = self.daily_start_equity - current_equity
        if daily_loss > self.max_daily_loss_cad:
            logger.critical(f"🚨 DAILY LOSS LIMIT BREACHED: ${daily_loss:,.2f} (max: ${self.max_daily_loss_cad:,.2f})")
            return False, "daily_loss"
        return True, "OK"

    def can_execute(self, decision: dict, symbol: str, 
                   current_equity: float, 
                   initial_capital: float,
                   current_positions_count: int,
                   proposed_value_cad: float) -> Tuple[bool, str]:
        
        if self.check_emergency_stop():
            return False, "emergency_stop"

        self.reset_daily(current_equity)

        # Core safety checks
        safe, reason = self.check_drawdown(current_equity, initial_capital)
        if not safe:
            return False, reason

        safe, reason = self.check_daily_loss(current_equity)
        if not safe:
            return False, reason

        # Position limits
        if current_positions_count >= self.max_positions:
            logger.warning(f"Max positions reached ({current_positions_count}/{self.max_positions})")
            return False, "max_positions"

        if proposed_value_cad > self.max_position_size_cad:
            logger.warning(f"Position size ${proposed_value_cad:,.2f} exceeds limit ${self.max_position_size_cad:,.2f}")
            return False, "max_position_size"

        return True, "OK"

    def get_risk_report(self) -> dict:
        return {
            "emergency_stop_active": self.emergency_stop_triggered,
            "max_drawdown_limit": f"{self.max_portfolio_drawdown:.1%}",
            "max_daily_loss_cad": f"${self.max_daily_loss_cad:,.2f}",
            "max_positions": self.max_positions,
            "max_single_position_cad": f"${self.max_position_size_cad:,.2f}",
            "daily_start_equity": self.daily_start_equity
        }