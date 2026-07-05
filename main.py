#!/usr/bin/env python3
"""
TRADE LAB - Autonomous Trading System
Real Data · Simulated Money · 5/10 Strategy · Gemini + Claude AI
Wealthsimple fee simulation · CAD base currency · USD/CAD real-time FX
"""

import os
import sys
import time
import signal
import logging
import schedule
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from broker.paper_broker import PaperBroker
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.gemini_research import GeminiResearch
from strategy.claude_psychology import ClaudePsychology
from strategy.signal_merger import SignalMerger
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()]
)
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════╗
║         🤖  TRADE LAB - Autonomous Trading          ║
║         Real Data · Fake Money · Multi-AI           ║
║         5/10 Strategy · Gemini + Claude             ║
║         Wealthsimple Fees · CAD Base Currency       ║
╚══════════════════════════════════════════════════════╝
"""


class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.broker = PaperBroker(config)
        self.strategy = FiveTenStrategy(config)
        self.gemini = GeminiResearch(config) if config.use_ai else None
        self.claude = ClaudePsychology(config) if config.use_ai else None
        self.merger = SignalMerger(config)
        self.risk = RiskManager(config)
        self.tracker = PortfolioTracker()
        self.data.load_historical_data()
        self.cycle_count = 0
        logger.info("Trade Lab initialized")

    def run_cycle(self):
        start = datetime.now()
        self.cycle_count += 1
        logger.info(f"{'='*60}")
        logger.info(f"CYCLE #{self.cycle_count} | {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        try:
            # Update FX rate
            fx_rate = self.data.get_usd_cad_rate()
            self.broker.set_fx_rate(fx_rate)
            logger.info(f"USD/CAD: {fx_rate:.4f}")

            # Monthly deposit
            if start.day == 1:
                self.broker.process_monthly_deposit()

            # Get prices
            prices = self.data.get_live_prices()
            if not prices:
                logger.warning("No prices available")
                return

            equity = self.broker.get_equity_cad(prices)
            logger.info(f"Equity: ${equity:,.2f} CAD")

            # Risk checks
            pos_count = len([p for p in self.broker.positions.values() if p.quantity > 0])
            safe, reason = self.risk.is_safe(equity, self.config.broker.initial_capital_cad, pos_count)
            if not safe:
                logger.warning(f"Risk check failed: {reason}")
                if "drawdown" in reason.lower() or "emergency" in reason.lower():
                    self._liquidate(prices)
                return

            trades_made = 0

            for symbol in self.config.data.symbols:
                hist = self.data._price_cache.get(symbol)
                if hist is None or len(hist) < self.config.strategy.lookback_days + 1:
                    continue

                pos = self.broker.positions.get(symbol)
                current_qty = pos.quantity if pos else 0.0
                current_price = prices.get(symbol, 0)

                # 1. Base strategy signal
                base_signal = self.strategy.generate_signal(symbol, hist, current_qty)
                if base_signal.action == SignalAction.HOLD:
                    continue

                # 2. AI analysis (blind - they never see each other)
                gemini_signal = None
                claude_signal = None

                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    volatility = 0.02
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]

                    gemini_signal = self.gemini.analyze(symbol, price_change, headlines, volatility) if self.gemini else None
                    claude_signal = self.claude.analyze(symbol, price_change, headlines, volatility) if self.claude else None

                # 3. Merge signals
                final = self.merger.merge(base_signal, gemini_signal, claude_signal, current_qty)

                if final.action == "HOLD":
                    continue

                # 4. Execute
                if final.action == "BUY":
                    if current_qty == 0:
                        max_cad = min(self.config.risk.max_position_size_cad, self.broker.cash_cad * 0.1)
                        max_usd = max_cad / fx_rate
                        qty = max_usd / current_price if current_price > 0 else 0
                    else:
                        qty = max(0.0001, current_qty * final.quantity_pct)

                    if qty > 0 and self.risk.check_position_size(qty * current_price * fx_rate):
                        order = self.broker.place_market_order(symbol, "buy", qty, prices)
                        if order and order.status == "filled":
                            trades_made += 1
                            self.tracker.record_trade(symbol, "BUY", order.quantity,
                                order.filled_price_usd, final.reason, final.ai_modified,
                                fx_rate, order.fx_fee_cad)
                            logger.info(f"✅ BUY {order.quantity} {symbol} @ ${order.filled_price_usd:.2f} USD")

                elif final.action == "SELL" and current_qty > 0:
                    qty = max(0.0001, current_qty * final.quantity_pct)
                    order = self.broker.place_market_order(symbol, "sell", qty, prices)
                    if order and order.status == "filled":
                        trades_made += 1
                        self.tracker.record_trade(symbol, "SELL", order.quantity,
                            order.filled_price_usd, final.reason, final.ai_modified,
                            fx_rate, order.fx_fee_cad)
                        logger.info(f"✅ SELL {order.quantity} {symbol} @ ${order.filled_price_usd:.2f} USD")

            # Snapshot
            summary = self.broker.get_portfolio_summary(prices)
            self.tracker.record_snapshot(summary)

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle complete: {trades_made} trades in {duration:.1f}s")
            logger.info(f"Equity: ${summary['equity_cad']:,.2f} CAD | P&L: ${summary['total_pnl_cad']:,.2f} | FX Fees: ${summary['total_fx_fees_cad']:,.2f}")

            if self.cycle_count == 1 or self.cycle_count % 5 == 0:
                self.tracker.print_report()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

    def _liquidate(self, prices):
        logger.critical("LIQUIDATING ALL POSITIONS")
        for sym, pos in list(self.broker.positions.items()):
            if pos.quantity > 0:
                self.broker.place_market_order(sym, "sell", pos.quantity, prices)

    def start(self):
        self.running = True
        print(BANNER)
        logger.info(f"Starting Trade Lab...")
        logger.info(f"Capital: ${self.config.broker.initial_capital_cad:,.2f} CAD")
        logger.info(f"Monthly deposit: ${self.config.broker.monthly_deposit_cad:,.2f} CAD")
        logger.info(f"AI: {'Enabled' if self.config.use_ai else 'Disabled'}")
        logger.info(f"Schedule: Daily at {self.config.schedule.run_time} EST")
        logger.info(f"Symbols: {', '.join(self.config.data.symbols)}")

        # First cycle
        self.run_cycle()

        # Schedule
        schedule.every().day.at(self.config.schedule.run_time).do(self.run_cycle)
        logger.info(f"Scheduled daily at {self.config.schedule.run_time} EST")
        logger.info("System LIVE. Ctrl+C to stop.\n")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)
                if datetime.now().minute == 0:
                    logger.info("💓 Heartbeat")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.tracker.print_report()


def main():
    os.makedirs("logs", exist_ok=True)
    config = Config()
    lab = TradeLab(config)
    signal.signal(signal.SIGINT, lambda s, f: setattr(lab, 'running', False))
    lab.start()


if __name__ == "__main__":
    main()