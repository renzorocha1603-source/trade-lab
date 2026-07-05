#!/usr/bin/env python3
"""
TRADE LAB - Autonomous Trading System
Real Data · Simulated Money · 5/10 Strategy + RSI Filter
DeepSeek (Primary AI) + Claude Haiku (Extreme Events)
Finnhub + Alpha Vantage + Yahoo (Triple Data Source)
Wealthsimple Fees · CAD Base · 24/7 Market-Hours Loop
"""

import os
import sys
import time
import signal
import logging
import schedule
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from broker.paper_broker import PaperBroker
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.gemini_research import DeepSeekResearch
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
║         TRADE LAB - 24/7 Autonomous Trading        ║
║    5/10 Strategy + RSI · DeepSeek + Claude Haiku   ║
║    Finnhub + Alpha Vantage + Yahoo (Triple Data)   ║
║       Wealthsimple Fees · CAD · Paper Trading      ║
╚══════════════════════════════════════════════════════╝
"""


class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.broker = PaperBroker(config)
        self.strategy = FiveTenStrategy(config)
        self.deepseek = DeepSeekResearch(config) if config.use_ai else None
        self.claude = ClaudePsychology(config) if config.use_ai else None
        self.merger = SignalMerger(config)
        self.risk = RiskManager(config)
        self.tracker = PortfolioTracker()
        self.data.load_historical_data()
        self.cycle_count = 0
        self.last_news_scan = None
        logger.info("Trade Lab initialized | 24/7 Mode")

    # ==================== MARKET HOURS ====================

    def is_market_open(self) -> bool:
        """Check if US stock market is open right now"""
        now = datetime.now()
        # Weekend check
        if now.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        # Holiday check (simplified - major US holidays)
        month, day = now.month, now.day
        holidays = [
            (1, 1), (1, 20), (2, 17), (5, 25), (7, 4),
            (9, 7), (10, 12), (11, 26), (12, 25)
        ]
        if (month, day) in holidays:
            return False
        # Time check (9:30 AM - 4:00 PM EST = 13:30 - 20:00 UTC)
        hour = now.hour
        minute = now.minute
        market_open = (hour > 13 or (hour == 13 and minute >= 30))
        market_close = (hour < 20 or (hour == 20 and minute == 0))
        return market_open and market_close

    def is_weekend(self) -> bool:
        return datetime.now().weekday() >= 5

    # ==================== RSI CALCULATION ====================

    def calculate_rsi(self, prices, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index) to avoid catching falling knives"""
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data
        try:
            import numpy as np
            deltas = np.diff(prices[-period-1:])
            gains = np.sum(deltas[deltas > 0]) / period
            losses = -np.sum(deltas[deltas < 0]) / period
            if losses == 0:
                return 100.0
            rs = gains / losses
            return 100.0 - (100.0 / (1.0 + rs))
        except:
            return 50.0

    # ==================== TRADING CYCLE ====================

    def run_cycle(self):
        """Execute one complete trading cycle"""
        start = datetime.now()
        self.cycle_count += 1
        is_market = self.is_market_open()
        mode = "MARKET HOURS" if is_market else "AFTER HOURS"

        logger.info(f"{'='*60}")
        logger.info(f"CYCLE #{self.cycle_count} | {mode} | {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        try:
            # Update FX rate
            fx_rate = self.data.get_usd_cad_rate()
            self.broker.set_fx_rate(fx_rate)

            # Monthly deposit (1st of month)
            if start.day == 1 and start.hour < 1:
                self.broker.process_monthly_deposit()

            # Get prices (from Finnhub → Alpha Vantage → Yahoo)
            prices = self.data.get_live_prices()
            if not prices:
                logger.warning("No prices available — data sources may be rate-limited")
                return

            equity = self.broker.get_equity_cad(prices)
            pos_count = len([p for p in self.broker.positions.values() if p.quantity > 0])
            logger.info(f"Equity: ${equity:,.2f} CAD | Positions: {pos_count} | USD/CAD: {fx_rate:.4f}")

            # Risk checks
            safe, reason = self.risk.is_safe(equity, self.config.broker.initial_capital_cad, pos_count)
            if not safe:
                logger.warning(f"Risk blocked: {reason}")
                if "drawdown" in reason.lower() or "emergency" in reason.lower():
                    self._liquidate(prices)
                return

            # Check past prediction accuracy
            self.data.check_prediction_outcomes(prices)

            trades_made = 0

            for symbol in self.config.data.symbols:
                hist = self.data._price_cache.get(symbol)
                if hist is None or len(hist) < self.config.strategy.lookback_days + 1:
                    continue

                pos = self.broker.positions.get(symbol)
                current_qty = pos.quantity if pos else 0.0
                current_price = prices.get(symbol, 0)

                # 1. Base 5/10 strategy signal
                base_signal = self.strategy.generate_signal(symbol, hist, current_qty)
                if base_signal.action == SignalAction.HOLD:
                    continue

                # 2. RSI FILTER — don't buy falling knives
                if base_signal.action == SignalAction.BUY:
                    rsi = self.calculate_rsi(hist.values)
                    if rsi > 40:  # Only buy if oversold or near-oversold
                        logger.info(f"RSI filter: {symbol} RSI={rsi:.1f} > 40, skipping buy")
                        continue
                    logger.info(f"RSI OK: {symbol} RSI={rsi:.1f} — oversold, buying")

                # 3. AI analysis (BLIND — each AI never sees the other)
                deepseek_signal = None
                claude_signal = None

                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    volatility = 0.02
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]
                    news_freshness = self.data.get_news_freshness_factor(news_items)

                    # DeepSeek: Always runs (primary AI — research + math + psychology)
                    if self.deepseek:
                        deepseek_signal = self.deepseek.analyze(symbol, price_change, headlines, volatility)

                    # Claude Haiku: Only for extreme events (>10% moves or market panic)
                    is_extreme = (abs(price_change) > 0.10) if price_change else False
                    if self.claude and is_extreme:
                        claude_signal = self.claude.analyze(symbol, price_change, headlines, volatility, is_extreme_event=True)
                        logger.warning(f"EXTREME EVENT: {symbol} | Price change: {price_change:.1%} | Calling Claude Haiku")

                # 4. Merge signals (math only, no AI in the merger)
                final = self.merger.merge(base_signal, deepseek_signal, claude_signal, current_qty)

                if final.action == "HOLD":
                    continue

                # 5. After-hours restriction — only sell, never buy when market closed
                if not is_market and final.action == "BUY":
                    logger.info(f"After-hours: skipping BUY {symbol} — market closed")
                    continue

                # 6. Execute trade
                if final.action == "BUY":
                    if current_qty == 0:
                        max_cad = min(self.config.risk.max_position_size_cad, self.broker.cash_cad * 0.1)
                        max_usd = max_cad / fx_rate if fx_rate > 0 else 0
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
                            self.data.record_prediction(symbol, "BUY", order.filled_price_usd,
                                final.base_contribution, final.reason, news_freshness if 'news_freshness' in dir() else 0.5)
                            logger.info(f"[TRADE] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} USD")

                elif final.action == "SELL" and current_qty > 0:
                    qty = max(0.0001, current_qty * final.quantity_pct)
                    order = self.broker.place_market_order(symbol, "sell", qty, prices)
                    if order and order.status == "filled":
                        trades_made += 1
                        self.tracker.record_trade(symbol, "SELL", order.quantity,
                            order.filled_price_usd, final.reason, final.ai_modified,
                            fx_rate, order.fx_fee_cad)
                        logger.info(f"[TRADE] SELL {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} USD")

            # Snapshot
            summary = self.broker.get_portfolio_summary(prices)
            self.tracker.record_snapshot(summary)

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {trades_made} trades | {duration:.1f}s | Equity: ${summary['equity_cad']:,.2f} CAD")

            # Daily report at 4:30 PM
            if datetime.now().hour == 20 and datetime.now().minute >= 30:
                self.tracker.print_report()
                self.data.print_accuracy_report()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

    # ==================== NEWS MONITORING ====================

    def scan_news(self):
        """Scan for breaking news (runs even when market is closed)"""
        now = datetime.now()
        if self.last_news_scan and (now - self.last_news_scan).seconds < 900:  # Every 15 min
            return

        self.last_news_scan = now
        logger.debug(f"News scan: {now.strftime('%H:%M')}")

        for symbol in self.config.data.symbols[:3]:  # Top 3 symbols only (save API calls)
            try:
                news = self.data.get_news(symbol, max_items=3)
                if news and news[0].get("freshness_score", 0) > 0.8:
                    # Fresh breaking news detected
                    logger.info(f"BREAKING: {symbol} — {news[0]['title'][:100]}")
            except:
                pass

    # ==================== LIQUIDATE ====================

    def _liquidate(self, prices):
        logger.critical("LIQUIDATING ALL POSITIONS")
        for sym, pos in list(self.broker.positions.items()):
            if pos.quantity > 0:
                self.broker.place_market_order(sym, "sell", pos.quantity, prices)

    # ==================== START ====================

    def start(self):
        self.running = True
        print(BANNER)
        logger.info(f"Capital: ${self.config.broker.initial_capital_cad:,.2f} CAD")
        logger.info(f"Monthly deposit: ${self.config.broker.monthly_deposit_cad:,.2f} CAD")
        logger.info(f"AI: DeepSeek (Primary) + Claude Haiku (Extreme Events)")
        logger.info(f"Data: Finnhub → Alpha Vantage → Yahoo (triple redundancy)")
        logger.info(f"Market: {'OPEN' if self.is_market_open() else 'CLOSED'}")
        logger.info(f"Symbols: {', '.join(self.config.data.symbols)}")
        logger.info("24/7 Loop starting...\n")

        # Run first cycle immediately
        self.run_cycle()

        # 24/7 Loop
        try:
            while self.running:
                now = datetime.now()

                if self.is_market_open():
                    # Market hours: full cycle every 15 minutes
                    if now.minute % 15 == 0:
                        self.run_cycle()
                else:
                    # After hours: news scan only, full cycle once per hour
                    self.scan_news()
                    if now.minute == 0:
                        self.run_cycle()

                time.sleep(60)  # Check every minute

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