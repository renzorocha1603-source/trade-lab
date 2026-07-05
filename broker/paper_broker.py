"""
Paper Broker - Simulates Wealthsimple trading with real fees.
- 0% commission on all trades
- 1.5% FX fee on US stock buys AND sells
- Fractional shares supported
- Monthly deposits in CAD
- Tracks P&L in both CAD and USD
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_cost_usd: float = 0.0
    current_price_usd: float = 0.0

    @property
    def market_value_usd(self) -> float:
        return self.quantity * self.current_price_usd

    @property
    def cost_basis_usd(self) -> float:
        return self.quantity * self.avg_cost_usd

    @property
    def unrealized_pnl_usd(self) -> float:
        return self.market_value_usd - self.cost_basis_usd


@dataclass
class Order:
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    filled_price_usd: float = 0.0
    fx_rate: float = 1.35
    fx_fee_pct: float = 0.015
    fx_fee_cad: float = 0.0
    commission_cad: float = 0.0
    total_cost_cad: float = 0.0
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)


class PaperBroker:
    """Simulated Wealthsimple broker with real fee structure"""

    def __init__(self, config):
        self.config = config
        self.cash_cad = config.broker.initial_capital_cad
        self.initial_capital_cad = config.broker.initial_capital_cad
        self.monthly_deposit_cad = config.broker.monthly_deposit_cad
        self.fx_fee_pct = config.broker.fx_fee_pct
        self.commission = config.broker.commission_per_trade
        self.slippage_pct = config.broker.slippage_pct
        self.allow_fractional = config.broker.allow_fractional_shares
        self.base_currency = config.broker.base_currency
        self.positions: Dict[str, Position] = {}
        self.order_history: List[Order] = []
        self.deposit_history: List[dict] = []
        self._current_fx_rate = 1.35

    def set_fx_rate(self, rate: float):
        self._current_fx_rate = rate

    def get_equity_cad(self, market_prices_usd: Dict[str, float]) -> float:
        """Total portfolio value in CAD"""
        self.update_market_prices(market_prices_usd)
        position_value_usd = sum(p.market_value_usd for p in self.positions.values())
        position_value_cad = position_value_usd * self._current_fx_rate
        return self.cash_cad + position_value_cad

    def update_market_prices(self, market_prices_usd: Dict[str, float]):
        for symbol, price in market_prices_usd.items():
            if symbol in self.positions:
                self.positions[symbol].current_price_usd = price

    def process_monthly_deposit(self):
        """Add monthly deposit if configured"""
        if self.monthly_deposit_cad > 0:
            self.cash_cad += self.monthly_deposit_cad
            self.deposit_history.append({
                "date": datetime.now().isoformat(),
                "amount_cad": self.monthly_deposit_cad,
                "new_balance_cad": self.cash_cad
            })
            logger.info(f"Monthly deposit: ${self.monthly_deposit_cad:,.2f} CAD added")

    def place_market_order(self, symbol: str, side: str, quantity_usd: float,
                          market_prices_usd: Dict[str, float]) -> Optional[Order]:
        """
        Execute trade with full Wealthsimple fee simulation.
        """
        current_price = market_prices_usd.get(symbol, 0)
        if current_price <= 0:
            return None

        # Apply slippage
        slippage = 1 + (self.slippage_pct if side.lower() == "buy" else -self.slippage_pct)
        fill_price_usd = current_price * slippage

        order = Order(
            symbol=symbol,
            side=side.lower(),
            quantity=quantity_usd if self.allow_fractional else int(quantity_usd),
            filled_price_usd=fill_price_usd,
            fx_rate=self._current_fx_rate,
            fx_fee_pct=self.fx_fee_pct
        )

        trade_value_usd = order.quantity * fill_price_usd

        if side.lower() == "buy":
            # Wealthsimple: 1.5% FX fee on US stock buys
            fx_fee_cad = trade_value_usd * self._current_fx_rate * self.fx_fee_pct
            total_cost_cad = (trade_value_usd * self._current_fx_rate) + fx_fee_cad + self.commission

            if total_cost_cad > self.cash_cad:
                max_usd = (self.cash_cad / (self._current_fx_rate * (1 + self.fx_fee_pct)))
                order.quantity = max_usd / fill_price_usd if self.allow_fractional else int(max_usd / fill_price_usd)
                if order.quantity <= 0:
                    order.status = "rejected"
                    return order
                trade_value_usd = order.quantity * fill_price_usd
                fx_fee_cad = trade_value_usd * self._current_fx_rate * self.fx_fee_pct
                total_cost_cad = (trade_value_usd * self._current_fx_rate) + fx_fee_cad

            self.cash_cad -= total_cost_cad
            order.fx_fee_cad = fx_fee_cad
            order.total_cost_cad = total_cost_cad

            if symbol not in self.positions:
                self.positions[symbol] = Position(symbol=symbol)
            pos = self.positions[symbol]
            total_cost_basis = (pos.cost_basis_usd) + trade_value_usd
            pos.quantity += order.quantity
            pos.avg_cost_usd = total_cost_basis / pos.quantity if pos.quantity > 0 else 0

        else:  # sell
            pos = self.positions.get(symbol)
            if not pos or pos.quantity <= 0:
                order.status = "rejected"
                return order

            order.quantity = min(order.quantity, pos.quantity)
            trade_value_usd = order.quantity * fill_price_usd

            # Wealthsimple: 1.5% FX fee on US stock sells too
            fx_fee_cad = trade_value_usd * self._current_fx_rate * self.fx_fee_pct
            proceeds_cad = (trade_value_usd * self._current_fx_rate) - fx_fee_cad - self.commission

            self.cash_cad += proceeds_cad
            order.fx_fee_cad = fx_fee_cad
            order.total_cost_cad = proceeds_cad

            pos.quantity -= order.quantity
            if pos.quantity <= 0:
                pos.avg_cost_usd = 0.0

        order.status = "filled"
        self.order_history.append(order)
        return order

    def get_portfolio_summary(self, market_prices_usd: Dict[str, float]) -> dict:
        equity_cad = self.get_equity_cad(market_prices_usd)
        return {
            "cash_cad": round(self.cash_cad, 2),
            "equity_cad": round(equity_cad, 2),
            "initial_capital_cad": self.initial_capital_cad,
            "total_pnl_cad": round(equity_cad - self.initial_capital_cad, 2),
            "total_pnl_pct": round((equity_cad / self.initial_capital_cad - 1) * 100, 2),
            "fx_rate_usd_cad": round(self._current_fx_rate, 4),
            "total_fx_fees_cad": round(sum(o.fx_fee_cad for o in self.order_history), 2),
            "positions": {
                s: {
                    "quantity": round(p.quantity, 4),
                    "avg_cost_usd": round(p.avg_cost_usd, 2),
                    "current_price_usd": round(p.current_price_usd, 2),
                    "market_value_cad": round(p.market_value_usd * self._current_fx_rate, 2),
                    "unrealized_pnl_cad": round(p.unrealized_pnl_usd * self._current_fx_rate, 2)
                }
                for s, p in self.positions.items() if p.quantity > 0
            },
            "total_trades": len(self.order_history),
            "deposits_made": len(self.deposit_history)
        }