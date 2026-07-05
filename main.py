#!/usr/bin/env python3
"""
TRADE LAB v2.3 — Self-Learning AI Trading
DeepSeek (Research) + Claude (Psychology) + Letta (Learning Memory)
3 Risk Profiles · 5 Scenarios · Self-Improving Over Time
Finnhub + Alpha Vantage + Coinbase + Yahoo
CAD Base · 24/7 Market-Hours Loop
"""

import os, sys, time, signal, logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.deepseek_research import DeepSeekResearch
from strategy.claude_psychology import ClaudePsychology
from strategy.signal_merger import SignalMerger
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker
from simulator.runner import ScenarioRunner
from learning.letta_memory import LettaMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()])
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════╗
║   TRADE LAB v2.3 — Self-Learning AI Trading        ║
║   DeepSeek · Claude · Letta (Learning Memory)      ║
║   Conservative · Balanced · Aggressive             ║
║   5 Scenarios · Self-Improving Over Time           ║
╚══════════════════════════════════════════════════════╝
"""

class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.strategy = FiveTenStrategy(config)
        self.deepseek = DeepSeekResearch(config) if config.use_ai else None
        self.claude = ClaudePsychology(config) if config.use_ai else None
        self.merger = SignalMerger(config)
        self.risk = RiskManager(config)
        self.tracker = PortfolioTracker()
        self.scenario_runner = ScenarioRunner(config, self.data)
        self.letta = LettaMemory(config)
        self.data.load_historical_data()
        self.cycle_count = 0
        self.last_news_scan = None
        self.last_tier3_scan = None

        self.sectors = {
            "tech": ["AAPL","MSFT","GOOGL","META","NVDA","TSLA","QQQ","XLK"],
            "finance": ["JPM","V","XLF"],
            "energy": ["XOM","XLE","ENB.TO","CNQ.TO"],
            "healthcare": ["JNJ","XLV"],
            "canadian": ["RY.TO","TD.TO","SHOP.TO","XIU.TO","VFV.TO"],
            "broad_market": ["SPY","IWM","DIA","VTI"],
            "crypto": ["BTC-USD","ETH-USD"],
            "international": ["BABA","TSM"],
            "consumer": ["WMT"],
        }

        logger.info("Trade Lab v2.3 | Self-Learning AI | 5 Scenarios | 3 Risk Profiles")

    # ==================== HELPERS ====================

    def is_market_open(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5: return False
        month, day = now.month, now.day
        holidays = [(1,1),(1,20),(2,17),(5,25),(7,4),(9,7),(10,12),(11,26),(12,25)]
        if (month, day) in holidays: return False
        return (now.hour > 13 or (now.hour == 13 and now.minute >= 30)) and (now.hour < 20)

    def get_symbol_tier(self, symbol: str) -> int:
        if symbol in ["SPY","QQQ","AAPL","MSFT","NVDA"]: return 1
        if symbol in ["GOOGL","AMZN","META","TSLA","JPM","V","JNJ","IWM","DIA","XLF","XLK","XLE"]: return 2
        return 3

    def should_scan_symbol(self, symbol: str) -> bool:
        tier = self.get_symbol_tier(symbol)
        now = datetime.now()
        if tier == 1: return True
        if tier == 2: return now.minute == 0
        if tier == 3:
            if self.last_tier3_scan is None or (now - self.last_tier3_scan).seconds >= 14400:
                self.last_tier3_scan = now; return True
            return False
        return True

    def get_symbol_sector(self, symbol: str) -> str:
        for sector, symbols in self.sectors.items():
            if symbol in symbols: return sector
        return "other"

    def is_canadian_or_crypto(self, symbol: str) -> bool:
        return ".TO" in symbol or "-USD" in symbol

    def get_risk_profile(self, scenario_id: str) -> dict:
        for s in self.scenario_runner.scenarios:
            if s["id"] == scenario_id:
                profile_name = s.get("risk_profile", "balanced")
                return getattr(self.config.risk_profile, profile_name, self.config.risk_profile.balanced)
        return self.config.risk_profile.balanced

    # ==================== TECHNICALS ====================

    def calculate_rsi(self, prices, period=14) -> float:
        if len(prices) < period + 1: return 50.0
        try:
            import numpy as np
            deltas = np.diff(prices[-period-1:])
            gains = np.sum(deltas[deltas > 0]) / period
            losses = -np.sum(deltas[deltas < 0]) / period
            if losses == 0: return 100.0
            return 100.0 - (100.0 / (1.0 + gains / losses))
        except: return 50.0

    def calculate_atr(self, prices, period=14) -> float:
        if len(prices) < period + 1: return 0.02
        try:
            import numpy as np
            closes = prices[-period-1:]
            tr = np.abs(np.diff(closes))
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

    def get_dynamic_rsi_threshold(self, vix: float = 20, modifier: float = 0) -> float:
        return 40 + (20 - vix) * 0.5 + modifier

    def get_macro_context(self) -> dict:
        context = {"vix": 20, "usdcad": "1.35", "regime": "normal"}
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
        except: pass
        return context

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
            prices = self.data.get_live_prices()
            if not prices: return

            # Letta checks past trade outcomes and learns
            self.letta.check_outcomes(prices)

            macro = self.get_macro_context()
            vix = macro.get("vix", 20)
            total_trades = 0

            for symbol in self.config.data.symbols:
                if not self.should_scan_symbol(symbol): continue

                hist = self.data._price_cache.get(symbol)
                if hist is None or len(hist) < 20: continue

                current_price = prices.get(symbol, 0)
                if current_price <= 0: continue

                atr = self.calculate_atr(hist.values)
                rsi = self.calculate_rsi(hist.values)
                volume_trend = self.calculate_volume_trend()
                ma_distance = self.calculate_ma_distance(hist.values)

                base_signal = self.strategy.generate_signal(symbol, hist, 0)
                if base_signal.action == SignalAction.HOLD: continue

                if not is_market and base_signal.action == SignalAction.BUY: continue

                # AI analysis
                deepseek_signal = None
                claude_signal = None
                news_freshness = 0.5
                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]
                    news_freshness = self.data.get_news_freshness_factor(news_items)
                    if self.deepseek:
                        deepseek_signal = self.deepseek.analyze(
                            symbol, price_change, headlines, atr,
                            rsi=rsi, volume_trend=volume_trend, ma_distance=ma_distance,
                            macro_context=macro
                        )
                    if self.claude and abs(price_change) > 0.10:
                        claude_signal = self.claude.analyze(symbol, price_change, headlines, atr, is_extreme_event=True)

                # Letta advice based on past learning
                letta_advice = self.letta.get_advice(symbol, rsi, vix)

                final = self.merger.merge(base_signal, deepseek_signal, claude_signal, 0)

                # Apply Letta learning on top
                if letta_advice and final.action != "HOLD":
                    if letta_advice["advice"] == "amplify_buy" and final.action == "BUY":
                        final.quantity_pct = min(final.quantity_pct * 1.3, 1.0)
                        final.reason += f" | Letta: {letta_advice['reason']} ({letta_advice['based_on']})"
                    elif letta_advice["advice"] == "dampen_buy" and final.action == "BUY":
                        final.quantity_pct = max(final.quantity_pct * 0.5, 0.01)
                        final.reason += f" | Letta: {letta_advice['reason']} ({letta_advice['based_on']})"

                if final.action == "HOLD": continue

                # ====== EXECUTE TRADE IN EACH SCENARIO ======
                for scenario in self.scenario_runner.scenarios:
                    sid = scenario["id"]
                    profile = self.get_risk_profile(sid)

                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)

                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    capital = broker.initial_capital_cad
                    equity = broker.get_equity_cad(prices)
                    pos_count = len([p for p in broker.positions.values() if p.quantity > 0])
                    cash_reserve = profile["cash_reserve_pct"]
                    available_cash = broker.cash_cad * (1 - cash_reserve)
                    max_pos = profile["max_positions"]

                    # Position cap
                    if pos_count >= max_pos: continue

                    # US stock restriction
                    if not profile["can_trade_us"] and not self.is_canadian_or_crypto(symbol): continue

                    # Sector limit
                    if profile["use_sector_limits"]:
                        sector = self.get_symbol_sector(symbol)
                        sector_count = sum(1 for sym, pos in broker.positions.items() 
                                         if pos.quantity > 0 and self.get_symbol_sector(sym) == sector)
                        if sector_count >= profile["max_sector_positions"]: continue

                    # RSI filter
                    if profile["use_rsi_filter"] and base_signal.action == SignalAction.BUY:
                        rsi_threshold = self.get_dynamic_rsi_threshold(vix, profile["rsi_threshold_modifier"])
                        if rsi > rsi_threshold: continue

                    # ATR filter
                    if profile["use_atr_filter"] and base_signal.action == SignalAction.BUY:
                        if atr > 0.05: continue

                    # Calculate quantity
                    if final.action == "BUY":
                        max_allocation = min(self.config.risk.max_position_size_cad, available_cash * 0.10)
                        qty = max_allocation / (current_price * fx_rate) if fx_rate > 0 else 0
                        notional_cad = qty * current_price * fx_rate
                        if notional_cad < profile["min_notional"]: continue
                        if qty <= 0: continue
                    else:
                        pos = broker.positions.get(symbol)
                        if not pos or pos.quantity <= 0: continue
                        qty = max(0.0001, pos.quantity * final.quantity_pct)

                    # Execute
                    order = broker.place_market_order(symbol, "buy" if final.action == "BUY" else "sell", qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        action_label = "BUY" if final.action == "BUY" else "SELL"
                        
                        # Record in Letta memory for future learning
                        self.letta.remember_trade(
                            symbol, action_label, order.filled_price_usd,
                            rsi, vix, final.reason, sid
                        )
                        
                        # Record in tracker
                        self.tracker.record_trade(symbol, action_label, order.quantity,
                            order.filled_price_usd, final.reason, final.ai_modified,
                            fx_rate, order.fx_fee_cad)
                        
                        logger.info(f"[{profile['name']}] {action_label} {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {sid} | Letta rules: {len(self.letta.rules)}")

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {total_trades} trades | {duration:.1f}s | Letta: {len(self.letta.rules)} rules learned")
            self.scenario_runner.save_scenario_snapshots()
            self.push_logs_to_github()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

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
            subprocess.run(["git","config","user.email","bot@tradelab.com"], capture_output=True, timeout=5)
            subprocess.run(["git","config","user.name","TradeLab Bot"], capture_output=True, timeout=5)
            subprocess.run(["git","add","logs/"], capture_output=True, timeout=10)
            r = subprocess.run(["git","commit","-m","Auto-update logs [bot]"], capture_output=True, timeout=10)
            if "nothing to commit" not in r.stdout.decode() and "nothing to commit" not in r.stderr.decode():
                subprocess.run(["git","push"], capture_output=True, timeout=15)
        except: pass

    # ==================== START ====================

    def start(self):
        self.running = True
        print(BANNER)
        logger.info(f"AI: DeepSeek + Claude Haiku + Letta (Self-Learning)")
        logger.info(f"Symbols: {len(self.config.data.symbols)} | Scenarios: {len(self.scenario_runner.scenarios)}")
        logger.info(f"Risk Profiles: Conservative | Balanced | Aggressive")
        logger.info(f"Letta Memory: {len(self.letta.rules)} learned rules loaded")
        logger.info(f"Market: {'OPEN' if self.is_market_open() else 'CLOSED'}")
        logger.info("24/7 Self-Learning Loop starting...\n")
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
            logger.info(f"Letta learned {len(self.letta.rules)} rules from {len(self.letta.trade_history)} trades")
            self.scenario_runner.print_comparison()


def main():
    os.makedirs("logs", exist_ok=True)
    config = Config()
    lab = TradeLab(config)
    signal.signal(signal.SIGINT, lambda s, f: setattr(lab, 'running', False))
    lab.start()


if __name__ == "__main__":
    main()