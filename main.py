#!/usr/bin/env python3
"""
TRADE LAB - Autonomous Trading System v2.1
Optimized: Dynamic RSI, Cash Reserve, Sector Limits, ATR Triggers,
Small Account Protection (TSX/Crypto only), Min Notional $1 CAD
DeepSeek (Primary AI) + Claude Haiku (Extreme Events)
Finnhub + Alpha Vantage + Coinbase + Yahoo (Multi-Source)
Wealthsimple Fees · CAD Base · 24/7 Market-Hours Loop
Multi-Scenario Simulator · Smarter AI with Technicals + Macro
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from broker.paper_broker import PaperBroker
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.deepseek_research import DeepSeekResearch
from strategy.claude_psychology import ClaudePsychology
from strategy.signal_merger import SignalMerger
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker
from simulator.runner import ScenarioRunner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()]
)
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════╗
║      TRADE LAB v2.1 - Optimized AI Trading         ║
║   Dynamic RSI · Cash Reserve · Sector Limits       ║
║   Small Account Protection · ATR Triggers          ║
║   Finnhub + Alpha Vantage + Coinbase + Yahoo       ║
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
        self.scenario_runner = ScenarioRunner(config, self.data)
        self.data.load_historical_data()
        self.cycle_count = 0
        self.last_news_scan = None
        self.last_tier3_scan = None
        
        # Sector definitions for correlation throttling
        self.sectors = {
            "tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSLA", "QQQ", "XLK"],
            "finance": ["JPM", "V", "XLF"],
            "energy": ["XOM", "XLE", "ENB.TO", "CNQ.TO"],
            "healthcare": ["JNJ", "XLV"],
            "canadian": ["RY.TO", "TD.TO", "SHOP.TO", "XIU.TO", "VFV.TO"],
            "broad_market": ["SPY", "IWM", "DIA", "VTI"],
            "crypto": ["BTC-USD", "ETH-USD"],
            "international": ["BABA", "TSM"],
            "consumer": ["WMT"],
        }
        
        logger.info("Trade Lab v2.1 initialized | Optimized | Dynamic RSI | Sector Limits")

    # ==================== MARKET HOURS ====================

    def is_market_open(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        month, day = now.month, now.day
        holidays = [(1, 1), (1, 20), (2, 17), (5, 25), (7, 4), (9, 7), (10, 12), (11, 26), (12, 25)]
        if (month, day) in holidays:
            return False
        hour = now.hour
        minute = now.minute
        return (hour > 13 or (hour == 13 and minute >= 30)) and (hour < 20)

    def get_symbol_tier(self, symbol: str) -> int:
        if symbol in ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]:
            return 1
        elif symbol in ["GOOGL", "AMZN", "META", "TSLA", "JPM", "V", "JNJ", "IWM", "DIA", "XLF", "XLK", "XLE"]:
            return 2
        return 3

    def should_scan_symbol(self, symbol: str) -> bool:
        tier = self.get_symbol_tier(symbol)
        now = datetime.now()
        if tier == 1: return True
        if tier == 2: return now.minute == 0
        if tier == 3:
            if self.last_tier3_scan is None or (now - self.last_tier3_scan).seconds >= 14400:
                self.last_tier3_scan = now
                return True
            return False
        return True

    def get_symbol_sector(self, symbol: str) -> str:
        for sector, symbols in self.sectors.items():
            if symbol in symbols:
                return sector
        return "other"

    def count_sector_positions(self, sector: str) -> int:
        count = 0
        for sym, pos in self.broker.positions.items():
            if pos.quantity > 0 and self.get_symbol_sector(sym) == sector:
                count += 1
        return count

    def is_canadian_or_crypto(self, symbol: str) -> bool:
        return ".TO" in symbol or "-USD" in symbol

    # ==================== TECHNICAL INDICATORS ====================

    def calculate_rsi(self, prices, period: int = 14) -> float:
        if len(prices) < period + 1: return 50.0
        try:
            import numpy as np
            deltas = np.diff(prices[-period-1:])
            gains = np.sum(deltas[deltas > 0]) / period
            losses = -np.sum(deltas[deltas < 0]) / period
            if losses == 0: return 100.0
            return 100.0 - (100.0 / (1.0 + gains / losses))
        except: return 50.0

    def calculate_atr(self, prices, period: int = 14) -> float:
        """Average True Range for dynamic triggers"""
        if len(prices) < period + 1: return 0.02
        try:
            import numpy as np
            highs = prices[-period-1:]
            lows = prices[-period-1:]
            closes = prices[-period-1:]
            tr = np.maximum(highs[1:] - lows[1:], 
                           np.abs(highs[1:] - closes[:-1]),
                           np.abs(lows[1:] - closes[:-1]))
            return np.mean(tr) / closes[-1] if closes[-1] > 0 else 0.02
        except: return 0.02

    def calculate_volume_trend(self, volumes=None) -> str:
        if volumes is None or len(volumes) < 5: return "normal"
        try:
            recent = sum(volumes[-3:]) / 3
            older = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else recent
            if recent > older * 1.3: return "increasing"
            if recent < older * 0.7: return "decreasing"
        except: pass
        return "normal"

    def calculate_ma_distance(self, prices) -> float:
        if len(prices) < 50: return 0.0
        try:
            import numpy as np
            ma50 = np.mean(prices[-50:])
            return ((prices[-1] - ma50) / ma50) * 100
        except: return 0.0

    def get_dynamic_rsi_threshold(self, vix: float = 20) -> float:
        """Dynamic RSI: 40 + (20 - VIX) × 0.5"""
        return 40 + (20 - vix) * 0.5

    def get_macro_context(self) -> dict:
        context = {"vix": 20, "usdcad": "1.35", "oil": "N/A", "regime": "normal"}
        try:
            context["usdcad"] = f"{self.data.get_usd_cad_rate():.4f}"
        except: pass
        try:
            import yfinance as yf
            vix_t = yf.Ticker("^VIX")
            vix_h = vix_t.history(period="5d")
            if not vix_h.empty:
                vix_val = vix_h['Close'].iloc[-1]
                context["vix"] = vix_val
                if vix_val > 30: context["regime"] = "fear"
                elif vix_val > 25: context["regime"] = "cautious"
                elif vix_val < 15: context["regime"] = "complacent"
                else: context["regime"] = "normal"
            oil_t = yf.Ticker("CL=F")
            oil_h = oil_t.history(period="5d")
            if not oil_h.empty: context["oil"] = f"{oil_h['Close'].iloc[-1]:.2f}"
        except: pass
        return context

    # ==================== ACCOUNT SIZE LOGIC ====================

    def get_account_tier(self, equity_cad: float) -> str:
        """Determine account tier for restrictions"""
        if equity_cad < 1000: return "micro"
        elif equity_cad < 5000: return "small"
        elif equity_cad < 25000: return "medium"
        return "large"

    def can_trade_us_stocks(self, equity_cad: float) -> bool:
        """Micro accounts (<$1000) should only trade TSX/Crypto to avoid FX bleed"""
        return equity_cad >= 1000

    # ==================== TRADING CYCLE ====================

    def run_cycle(self):
        start = datetime.now()
        self.cycle_count += 1
        is_market = self.is_market_open()
        mode = "MARKET HOURS" if is_market else "AFTER HOURS"

        logger.info(f"{'='*60}")
        logger.info(f"CYCLE #{self.cycle_count} | {mode} | {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        try:
            fx_rate = self.data.get_usd_cad_rate()
            self.broker.set_fx_rate(fx_rate)
            if start.day == 1 and start.hour < 1:
                self.broker.process_monthly_deposit()

            prices = self.data.get_live_prices()
            if not prices: return

            equity = self.broker.get_equity_cad(prices)
            account_tier = self.get_account_tier(equity)
            pos_count = len([p for p in self.broker.positions.values() if p.quantity > 0])
            
            # Cash reserve: 15% for micro/small, 10% for medium/large
            cash_reserve_pct = 0.15 if account_tier in ("micro", "small") else 0.10
            available_cash = self.broker.cash_cad * (1 - cash_reserve_pct)
            max_positions = 3 if account_tier == "micro" else 4 if account_tier == "small" else 8

            logger.info(f"Equity: ${equity:,.2f} | Tier: {account_tier} | Positions: {pos_count}/{max_positions} | Reserve: {cash_reserve_pct:.0%}")

            safe, reason = self.risk.is_safe(equity, self.config.broker.initial_capital_cad, pos_count)
            if not safe:
                logger.warning(f"Risk blocked: {reason}")
                return

            self.data.check_prediction_outcomes(prices)
            macro = self.get_macro_context()
            vix = macro.get("vix", 20)
            dynamic_rsi_threshold = self.get_dynamic_rsi_threshold(vix)
            trades_made = 0

            for symbol in self.config.data.symbols:
                if not self.should_scan_symbol(symbol): continue

                # Small account US stock restriction
                if not self.can_trade_us_stocks(equity) and not self.is_canadian_or_crypto(symbol):
                    continue

                # Position cap
                if pos_count >= max_positions:
                    logger.debug(f"Max positions ({max_positions}) reached, skipping {symbol}")
                    continue

                # Sector limit: max 2 per sector
                sector = self.get_symbol_sector(symbol)
                if self.count_sector_positions(sector) >= 2:
                    logger.debug(f"Sector limit: {sector} has 2 positions, skipping {symbol}")
                    continue

                hist = self.data._price_cache.get(symbol)
                if hist is None or len(hist) < 20: continue

                pos = self.broker.positions.get(symbol)
                current_qty = pos.quantity if pos else 0.0
                current_price = prices.get(symbol, 0)
                if current_price <= 0: continue

                # ATR for dynamic trigger scaling
                atr = self.calculate_atr(hist.values)
                
                # Dynamic thresholds based on ATR
                dyn_loss = min(-0.03, -atr * 0.5)  # At least -3%, or half ATR if larger
                dyn_profit = max(0.05, atr * 0.8)   # At least 5%, or 0.8x ATR if larger

                base_signal = self.strategy.generate_signal(symbol, hist, current_qty)
                if base_signal.action == SignalAction.HOLD: continue

                # Dynamic RSI filter
                rsi = self.calculate_rsi(hist.values)
                volume_trend = self.calculate_volume_trend()
                ma_distance = self.calculate_ma_distance(hist.values)

                if base_signal.action == SignalAction.BUY:
                    if rsi > dynamic_rsi_threshold:
                        logger.info(f"RSI filter: {symbol} RSI={rsi:.1f} > {dynamic_rsi_threshold:.1f} (VIX={vix:.0f}), skipping")
                        continue
                    logger.info(f"RSI OK: {symbol} RSI={rsi:.1f} | VIX={vix:.0f} | Threshold={dynamic_rsi_threshold:.1f} | ATR={atr:.1%}")

                # AI analysis
                deepseek_signal = None
                claude_signal = None

                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    volatility = atr
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]
                    news_freshness = self.data.get_news_freshness_factor(news_items)

                    if self.deepseek:
                        deepseek_signal = self.deepseek.analyze(
                            symbol, price_change, headlines, volatility,
                            rsi=rsi, volume_trend=volume_trend, ma_distance=ma_distance,
                            macro_context=macro
                        )

                    if self.claude and abs(price_change) > 0.10:
                        claude_signal = self.claude.analyze(symbol, price_change, headlines, volatility, is_extreme_event=True)
                        logger.warning(f"EXTREME: {symbol} | {price_change:.1%} | Claude called")

                final = self.merger.merge(base_signal, deepseek_signal, claude_signal, current_qty)
                if final.action == "HOLD": continue
                if not is_market and final.action == "BUY": continue

                # ===== EXECUTE TRADE =====
                if final.action == "BUY":
                    # Position sizing with cash reserve
                    max_allocation = min(
                        self.config.risk.max_position_size_cad,
                        available_cash * 0.15 if account_tier == "micro" else available_cash * 0.10
                    )
                    
                    if current_qty == 0:
                        qty = max_allocation / (current_price * fx_rate) if fx_rate > 0 else 0
                    else:
                        qty = max(0.0001, current_qty * final.quantity_pct)

                    # Minimum notional check ($1 CAD)
                    notional_cad = qty * current_price * fx_rate
                    if notional_cad < 1.0:
                        logger.debug(f"Min notional: {symbol} trade = ${notional_cad:.2f} CAD < $1.00, skipping")
                        continue

                    # Fee check for small accounts
                    if account_tier == "micro" and not self.is_canadian_or_crypto(symbol):
                        fee_estimate = notional_cad * 0.03  # 3% round-trip
                        if fee_estimate > notional_cad * 0.5:
                            logger.warning(f"Fee too high: {symbol} fees=${fee_estimate:.2f} > 50% of trade, skipping")
                            continue

                    if qty > 0 and self.risk.check_position_size(notional_cad):
                        order = self.broker.place_market_order(symbol, "buy", qty, prices)
                        if order and order.status == "filled":
                            trades_made += 1
                            pos_count += 1
                            self.tracker.record_trade(symbol, "BUY", order.quantity,
                                order.filled_price_usd, final.reason, final.ai_modified,
                                fx_rate, order.fx_fee_cad)
                            self.data.record_prediction(symbol, "BUY", order.filled_price_usd,
                                final.base_contribution, final.reason, news_freshness if 'news_freshness' in dir() else 0.5)
                            logger.info(f"[TRADE] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | Tier: {account_tier}")

                            for sid in self.scenario_runner.results:
                                self.scenario_runner.execute_trade_for_scenario(
                                    sid, symbol, "buy", order.quantity, order.filled_price_usd, prices)

                elif final.action == "SELL" and current_qty > 0:
                    qty = max(0.0001, current_qty * final.quantity_pct)
                    order = self.broker.place_market_order(symbol, "sell", qty, prices)
                    if order and order.status == "filled":
                        trades_made += 1
                        pos_count -= 1
                        self.tracker.record_trade(symbol, "SELL", order.quantity,
                            order.filled_price_usd, final.reason, final.ai_modified,
                            fx_rate, order.fx_fee_cad)
                        logger.info(f"[TRADE] SELL {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f}")

                        for sid in self.scenario_runner.results:
                            self.scenario_runner.execute_trade_for_scenario(
                                sid, symbol, "sell", order.quantity, order.filled_price_usd, prices)

            summary = self.broker.get_portfolio_summary(prices)
            self.tracker.record_snapshot(summary)
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {trades_made} trades | {duration:.1f}s | Equity: ${summary['equity_cad']:,.2f}")

            if datetime.now().hour == 20 and datetime.now().minute >= 30:
                self.tracker.print_report()
                self.data.print_accuracy_report()
                self.scenario_runner.print_comparison()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

        self.push_logs_to_github()

    # ==================== NEWS SCAN ====================

    def scan_news(self):
        now = datetime.now()
        if self.last_news_scan and (now - self.last_news_scan).seconds < 900: return
        self.last_news_scan = now
        for symbol in self.config.data.symbols[:5]:
            try:
                news = self.data.get_news(symbol, max_items=3)
                if news and news[0].get("freshness_score", 0) > 0.8:
                    logger.info(f"BREAKING: {symbol} — {news[0]['title'][:100]}")
            except: pass

    # ==================== GIT PUSH ====================

    def push_logs_to_github(self):
        try:
            import subprocess
            subprocess.run(["git", "config", "user.email", "bot@tradelab.com"], capture_output=True, timeout=5)
            subprocess.run(["git", "config", "user.name", "TradeLab Bot"], capture_output=True, timeout=5)
            subprocess.run(["git", "add", "logs/"], capture_output=True, timeout=10)
            r = subprocess.run(["git", "commit", "-m", "Auto-update logs [bot]"], capture_output=True, timeout=10)
            if "nothing to commit" not in r.stdout.decode() and "nothing to commit" not in r.stderr.decode():
                subprocess.run(["git", "push"], capture_output=True, timeout=15)
        except: pass

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
        logger.info(f"AI: DeepSeek + Technicals + Macro | Claude (Extreme Events)")
        logger.info(f"Optimizations: Dynamic RSI | Cash Reserve | Sector Limits | ATR Triggers | Min Notional $1")
        logger.info(f"Symbols: {len(self.config.data.symbols)} (Tier 1:5, Tier 2:12, Tier 3:14)")
        logger.info(f"Scenarios: {len(self.scenario_runner.scenarios)} active ($500-$10K)")
        logger.info(f"Market: {'OPEN' if self.is_market_open() else 'CLOSED'}")
        logger.info("24/7 Loop starting...\n")
        self.run_cycle()

        try:
            while self.running:
                now = datetime.now()
                if self.is_market_open():
                    if now.minute % 15 == 0: self.run_cycle()
                else:
                    self.scan_news()
                    if now.minute == 0: self.run_cycle()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.tracker.print_report()
            self.scenario_runner.print_comparison()


def main():
    os.makedirs("logs", exist_ok=True)
    config = Config()
    lab = TradeLab(config)
    signal.signal(signal.SIGINT, lambda s, f: setattr(lab, 'running', False))
    lab.start()


if __name__ == "__main__":
    main()