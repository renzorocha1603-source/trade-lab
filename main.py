#!/usr/bin/env python3
"""
TRADE LAB v2.4 — Letta as Final Decision Maker
DeepSeek (Math) + Claude (Psychology) + Letta (Brain + Memory)
Multi-Scenario · 3 Risk Profiles · 24/7 Self-Learning
"""

import os, sys, time, signal, logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.deepseek_research import DeepSeekResearch
from strategy.claude_psychology import ClaudePsychology
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker
from simulator.runner import ScenarioRunner
from learning.letta_memory import LettaMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()])
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║           TRADE LAB v2.4 — SELF-LEARNING AI                ║
║   DeepSeek (Math) • Claude (Psychology) • Letta (Brain)    ║
║   5 Scenarios · 3 Risk Profiles · 24/7 Operation           ║
╚══════════════════════════════════════════════════════════════╝
"""

class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.strategy = FiveTenStrategy(config)
        self.deepseek = DeepSeekResearch(config) if config.use_ai else None
        self.claude = ClaudePsychology(config) if config.use_ai else None
        self.risk = RiskManager(config)
        self.tracker = PortfolioTracker()
        self.scenario_runner = ScenarioRunner(config, self.data)
        self.letta = LettaMemory(config)
        self.data.load_historical_data()
        self.cycle_count = 0
        self.last_news_scan = None
        self.last_tier3_scan = None
        self.running = True

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

        logger.info(f"TradeLab v2.4 | Letta Brain | {len(self.letta.rules)} rules loaded")

    # ==================== MARKET HOURS ====================

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

        logger.info(f"{'='*70}")
        logger.info(f"CYCLE #{self.cycle_count} | {mode} | {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")

        try:
            fx_rate = self.data.get_usd_cad_rate()
            prices = self.data.get_live_prices()
            if not prices: return

            # 1. Letta learns from past trade outcomes
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

                rsi = self.calculate_rsi(hist.values)

                # 2. Base strategy signal
                base_signal = self.strategy.generate_signal(symbol, hist, 0, current_price)
                if base_signal.action == SignalAction.HOLD: continue

                if not is_market and base_signal.action == SignalAction.BUY: continue

                # Add RSI to metrics for Letta
                if base_signal.metrics is None:
                    base_signal.metrics = {}
                base_signal.metrics["rsi"] = rsi

                # 3. AI Analysis
                deepseek_signal_dict = None
                claude_opinion_dict = None

                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]
                    news_freshness = self.data.get_news_freshness_factor(news_items)
                    base_signal.metrics["news_freshness"] = news_freshness

                    if self.deepseek:
                        raw_ds = self.deepseek.analyze(symbol, price_change, headlines, 0.02,
                            rsi=rsi, volume_trend="normal", ma_distance=0, macro_context=macro)
                        if raw_ds:
                            deepseek_signal_dict = {
                                "sentiment_score": raw_ds.sentiment_score,
                                "confidence": raw_ds.confidence,
                                "recommendation": raw_ds.recommendation,
                                "key_findings": raw_ds.key_findings,
                            }

                    if self.claude and abs(price_change) > 0.10:
                        raw_cl = self.claude.analyze(symbol, price_change, headlines, 0.02, is_extreme_event=True)
                        if raw_cl:
                            claude_opinion_dict = {
                                "sentiment_score": raw_cl.sentiment_score,
                                "confidence": raw_cl.confidence,
                                "recommendation": raw_cl.recommendation,
                                "reasoning": raw_cl.reasoning,
                            }

                # 4. LETTA MAKES THE FINAL DECISION
                final = self.letta.make_final_decision(
                    symbol=symbol,
                    base_signal=base_signal,
                    deepseek_signal=deepseek_signal_dict,
                    claude_opinion=claude_opinion_dict,
                    current_price=current_price,
                    macro=macro
                )

                if final["action"] == "HOLD": continue

                # 5. Execute in each scenario
                for scenario in self.scenario_runner.scenarios:
                    sid = scenario["id"]
                    profile = self.get_risk_profile(sid)

                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)

                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    # Risk checks
                    pos_count = len([p for p in broker.positions.values() if p.quantity > 0])
                    if pos_count >= profile["max_positions"]: continue
                    if not profile["can_trade_us"] and not self.is_canadian_or_crypto(symbol): continue

                    if profile["use_rsi_filter"] and final["action"] == "BUY":
                        rsi_threshold = 40 + (20 - vix) * 0.5 + profile["rsi_threshold_modifier"]
                        if rsi > rsi_threshold: continue

                    qty = final["quantity_pct"]
                    if qty <= 0: continue

                    order = broker.place_market_order(symbol, final["action"].lower(), qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        logger.info(f"[{profile['name']}] {final['action']} {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | Score: {final['final_score']:.3f}")

                        # 6. Remember for future learning
                        self.letta.remember_trade({
                            "symbol": symbol,
                            "action": final["action"],
                            "price": order.filled_price_usd,
                            "quantity_pct": final["quantity_pct"],
                            "rsi": rsi,
                            "vix": vix,
                            "deepseek_score": deepseek_signal_dict.get("sentiment_score") if deepseek_signal_dict else None,
                            "deepseek_confidence": deepseek_signal_dict.get("confidence") if deepseek_signal_dict else None,
                            "claude_sentiment": claude_opinion_dict.get("sentiment_score") if claude_opinion_dict else None,
                            "claude_bias": claude_opinion_dict.get("recommendation") if claude_opinion_dict else None,
                            "models_agree": final.get("models_agree"),
                            "news_freshness": base_signal.metrics.get("news_freshness"),
                            "reason": final["reason"],
                            "scenario_id": sid,
                        })

                        self.tracker.record_trade(symbol, final["action"], order.quantity,
                            order.filled_price_usd, final["reason"], True, fx_rate, order.fx_fee_cad)

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {total_trades} trades | {duration:.1f}s | Letta: {len(self.letta.rules)} rules | Score range: {final.get('final_score', 0):+.3f}" if total_trades > 0 else f"Cycle: 0 trades | {duration:.1f}s")

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
        print(BANNER)
        logger.info(f"AI: DeepSeek (Math) + Claude (Psychology) + Letta (Final Decision)")
        logger.info(f"Symbols: {len(self.config.data.symbols)} | Scenarios: {len(self.scenario_runner.scenarios)}")
        logger.info(f"Letta Memory: {len(self.letta.rules)} rules | {len(self.letta.trade_history)} trades remembered")
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
            self._shutdown()

    def _shutdown(self):
        logger.info("Shutting down...")
        stats = self.letta.get_stats()
        logger.info(f"Letta final stats: {stats['total_rules']} rules | {stats['win_rate']}% win rate")
        self.scenario_runner.print_comparison()


def main():
    os.makedirs("logs", exist_ok=True)
    config = Config()
    lab = TradeLab(config)
    signal.signal(signal.SIGINT, lambda s, f: setattr(lab, 'running', False))
    lab.start()


if __name__ == "__main__":
    main()