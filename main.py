#!/usr/bin/env python3
"""
TRADE LAB v2.8 — TRAINING MODE
Stocks: Z-Score + Kelly + Sharpe (Ultra-aggressive)
Crypto: Pennies Scalping 24/7 (DIP + MOMENTUM + BREAKOUT)
DeepSeek (Math) + Claude (Psychology) + Letta (Brain + Memory)
Maximum trade volume for AI education.
"""

import os, sys, time, signal, logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.deepseek_research import DeepSeekResearch
from strategy.claude_psychology import ClaudePsychology
from strategy.crypto_scalper import CryptoPenniesStrategy
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker
from simulator.runner import ScenarioRunner
from learning.letta_memory import LettaMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()])
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║     TRADE LAB v2.8 — TRAINING MODE (Ultra-Aggressive)      ║
║   Stocks: Z-Score + Kelly · Crypto: DIP/MOMENTUM/BREAKOUT  ║
║   Letta Brain Learning From Every Trade                     ║
╚══════════════════════════════════════════════════════════════╝
"""

class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.strategy = FiveTenStrategy(config)
        self.crypto_strategy = CryptoPenniesStrategy(config)
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
        self.training_mode = getattr(config.strategy, 'training_mode', True)

        self.sectors = {
            "tech": ["AAPL","MSFT","GOOGL","META","NVDA","TSLA","QQQ","XLK"],
            "finance": ["JPM","V","XLF"],
            "energy": ["XOM","XLE","ENB.TO","CNQ.TO"],
            "healthcare": ["JNJ","XLV"],
            "canadian": ["RY.TO","TD.TO","SHOP.TO","XIU.TO","VFV.TO"],
            "broad_market": ["SPY","IWM","DIA","VTI"],
            "crypto": self.crypto_strategy.crypto_symbols,
            "international": ["BABA","TSM"],
            "consumer": ["WMT"],
        }

        logger.info(f"TradeLab v2.8 TRAINING MODE | {'Ultra-Aggressive' if self.training_mode else 'Production'} | Crypto: {len(self.crypto_strategy.crypto_symbols)} symbols")

    def is_market_open(self) -> bool:
        if self.training_mode: return True  # Always trade in training mode
        now = datetime.now()
        if now.weekday() >= 5: return False
        month, day = now.month, now.day
        holidays = [(1,1),(1,20),(2,17),(5,25),(7,4),(9,7),(10,12),(11,26),(12,25)]
        if (month, day) in holidays: return False
        return (now.hour > 13 or (now.hour == 13 and now.minute >= 30)) and (now.hour < 20)

    def is_crypto_symbol(self, symbol: str) -> bool:
        return symbol in self.crypto_strategy.crypto_symbols

    def get_symbol_tier(self, symbol: str) -> int:
        if self.is_crypto_symbol(symbol): return 1  # Always scan crypto
        if symbol in ["SPY","QQQ","AAPL","MSFT","NVDA"]: return 1
        if symbol in ["GOOGL","AMZN","META","TSLA","JPM","V","JNJ","IWM","DIA","XLF","XLK","XLE"]: return 2
        return 3

    def should_scan_symbol(self, symbol: str) -> bool:
        if self.is_crypto_symbol(symbol): return True
        if self.training_mode: return True  # Scan everything in training
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
        return ".TO" in symbol or self.is_crypto_symbol(symbol)

    def get_risk_profile(self, scenario_id: str) -> dict:
        for s in self.scenario_runner.scenarios:
            if s["id"] == scenario_id:
                profile_name = s.get("risk_profile", "balanced")
                return getattr(self.config.risk_profile, profile_name, self.config.risk_profile.balanced)
        return self.config.risk_profile.balanced

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

    def auto_reload_accounts(self):
        """Auto-reload accounts that dropped below threshold"""
        for scenario in self.scenario_runner.scenarios:
            sid = scenario["id"]
            if sid not in self.scenario_runner.results: continue
            entry = self.scenario_runner.results[sid]
            broker = entry["broker"]
            equity = broker.get_equity_cad({})
            threshold = self.config.risk.auto_reload_threshold
            reload_amount = self.config.risk.auto_reload_amount
            
            if equity < threshold and broker.initial_capital_cad > 0:
                broker.cash_cad = reload_amount
                broker.initial_capital_cad = reload_amount
                broker.positions = {}
                broker.order_history = []
                entry["trades"] = 0
                logger.warning(f"🔄 AUTO-RELOAD: {scenario['name']} reset to ${reload_amount:,.0f} (was ${equity:,.2f})")

    def run_cycle(self):
        start = datetime.now()
        self.cycle_count += 1
        is_market = self.is_market_open()
        mode = "TRAINING" if self.training_mode else ("MARKET HOURS" if is_market else "AFTER HOURS")

        logger.info(f"{'='*70}")
        logger.info(f"CYCLE #{self.cycle_count} | {mode} | {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")

        try:
            fx_rate = self.data.get_usd_cad_rate()
            prices = self.data.get_live_prices()
            if not prices: return

            self.letta.check_outcomes(prices)
            self.auto_reload_accounts()
            
            macro = self.get_macro_context()
            vix = macro.get("vix", 20)
            total_trades = 0

            # ========== CRYPTO: Scan ALL crypto symbols ==========
            for symbol in self.crypto_strategy.crypto_symbols:
                crypto_signal = self.crypto_strategy.generate_signal(symbol)
                if not crypto_signal: continue

                for scenario in self.scenario_runner.scenarios:
                    if scenario.get("type") != "crypto": continue
                    sid = scenario["id"]
                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)
                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    qty = crypto_signal["quantity_pct"]
                    current_price = crypto_signal["current_price"]
                    
                    # Add crypto price to prices dict for broker
                    if symbol not in prices:
                        prices[symbol] = current_price

                    order = broker.place_market_order(symbol, "buy", qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        logger.info(f"[PENNIES] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {crypto_signal['reason']}")
                        
                        self.letta.remember_trade({
                            "symbol": symbol, "action": "BUY",
                            "price": order.filled_price_usd, "quantity_pct": qty,
                            "rsi": crypto_signal["indicators"]["rsi"], "vix": vix,
                            "reason": crypto_signal["reason"], "scenario_id": sid,
                        })

            # ========== STOCKS: Scan all stock symbols ==========
            for symbol in self.config.data.symbols:
                if self.is_crypto_symbol(symbol): continue  # Already handled above
                if not self.should_scan_symbol(symbol): continue

                hist = self.data._price_cache.get(symbol)
                if hist is None or len(hist) < 20: continue

                current_price = prices.get(symbol, 0)
                if current_price <= 0: continue

                rsi = self.calculate_rsi(hist.values)

                base_signal = self.strategy.generate_signal(symbol, hist, 0)
                if base_signal.action == SignalAction.HOLD: continue

                if base_signal.metrics is None:
                    base_signal.metrics = {}
                base_signal.metrics["rsi"] = rsi

                deepseek_signal_dict = None
                claude_opinion_dict = None

                if self.config.use_ai:
                    price_change = base_signal.metrics.get("period_return", 0) or 0
                    news_items = self.data.get_news(symbol)
                    headlines = [n.get("title", "") for n in news_items]
                    news_freshness = self.data.get_news_freshness_factor(news_items)
                    base_signal.metrics["news_freshness"] = news_freshness

                    if self.deepseek:
                        raw_ds = self.deepseek.analyze(
                            symbol=symbol, history=hist, current_price=current_price,
                            macro=macro, rsi=rsi, atr=0.02
                        )
                        if raw_ds:
                            deepseek_signal_dict = {
                                "sentiment_score": raw_ds.get("sentiment_score", 0),
                                "confidence": raw_ds.get("confidence", 0.5),
                                "recommendation": raw_ds.get("recommendation", "no_change"),
                                "key_findings": raw_ds.get("key_findings", ""),
                            }

                    if self.claude and abs(price_change) > 0.10:
                        raw_cl = self.claude.analyze(
                            symbol=symbol, price_change=price_change,
                            headlines=headlines, volatility=0.02, is_extreme=True
                        )
                        if raw_cl:
                            claude_opinion_dict = {
                                "sentiment_score": raw_cl.get("sentiment_score", 0),
                                "confidence": raw_cl.get("confidence", 0.5),
                                "recommendation": raw_cl.get("recommendation", "no_change"),
                                "reasoning": raw_cl.get("reasoning", ""),
                            }

                final = self.letta.make_final_decision(
                    symbol=symbol, base_signal=base_signal,
                    deepseek_signal=deepseek_signal_dict,
                    claude_opinion=claude_opinion_dict,
                    current_price=current_price, macro=macro
                )

                if final["action"] == "HOLD": continue

                for scenario in self.scenario_runner.scenarios:
                    if scenario.get("type") == "crypto": continue
                    sid = scenario["id"]
                    profile = self.get_risk_profile(sid)

                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)

                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    equity = broker.get_equity_cad(prices)
                    pos_count = len([p for p in broker.positions.values() if p.quantity > 0])
                    qty = final["quantity_pct"]
                    proposed_value = qty * current_price * fx_rate if fx_rate > 0 else 0

                    safe, reason = self.risk.can_execute(
                        decision=final, symbol=symbol, current_equity=equity,
                        initial_capital=broker.initial_capital_cad,
                        current_positions_count=pos_count, proposed_value_cad=proposed_value
                    )

                    if not safe: continue
                    if pos_count >= profile["max_positions"]: continue
                    if not profile["can_trade_us"] and not self.is_canadian_or_crypto(symbol): continue
                    if profile["use_rsi_filter"] and final["action"] == "BUY":
                        rsi_threshold = 40 + (20 - vix) * 0.5 + profile["rsi_threshold_modifier"]
                        if rsi > rsi_threshold: continue
                    if qty <= 0: continue

                    order = broker.place_market_order(symbol, final["action"].lower(), qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        logger.info(f"[{profile['name']}] {final['action']} {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | Z:{base_signal.z_score:.2f}")

                        self.letta.remember_trade({
                            "symbol": symbol, "action": final["action"],
                            "price": order.filled_price_usd, "quantity_pct": final["quantity_pct"],
                            "rsi": rsi, "vix": vix,
                            "deepseek_score": deepseek_signal_dict.get("sentiment_score") if deepseek_signal_dict else None,
                            "deepseek_confidence": deepseek_signal_dict.get("confidence") if deepseek_signal_dict else None,
                            "claude_sentiment": claude_opinion_dict.get("sentiment_score") if claude_opinion_dict else None,
                            "claude_bias": claude_opinion_dict.get("recommendation") if claude_opinion_dict else None,
                            "models_agree": final.get("models_agree"),
                            "news_freshness": base_signal.metrics.get("news_freshness"),
                            "reason": final["reason"], "scenario_id": sid,
                        })

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {total_trades} trades | {duration:.1f}s | Letta rules: {len(self.letta.rules)}")
            self.scenario_runner.save_scenario_snapshots()
            self.push_logs_to_github()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

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

    def start(self):
        print(BANNER)
        logger.info(f"TRAINING MODE: {'ON' if self.training_mode else 'OFF'}")
        logger.info(f"Stocks: Z-Score + Kelly | Crypto: DIP/MOMENTUM/BREAKOUT")
        logger.info(f"Symbols: {len(self.config.data.symbols)} stocks + {len(self.crypto_strategy.crypto_symbols)} crypto")
        logger.info(f"Scenarios: {len(self.scenario_runner.scenarios)} | Auto-reload: ${self.config.risk.auto_reload_amount:,.0f} at ${self.config.risk.auto_reload_threshold:,.0f}")
        logger.info(f"Letta Memory: {len(self.letta.rules)} rules")
        logger.info("24/7 Training Loop starting...\n")
        self.run_cycle()

        try:
            while self.running:
                now = datetime.now()
                if self.training_mode or self.is_market_open():
                    if now.minute % 10 == 0:  # Every 10 minutes in training
                        self.run_cycle()
                else:
                    self.scan_news()
                    if now.minute == 0: self.run_cycle()
                time.sleep(60)
        except KeyboardInterrupt:
            self._shutdown()

    def _shutdown(self):
        logger.info("Shutting down...")
        stats = self.letta.get_stats()
        logger.info(f"Letta: {stats['total_rules']} rules | {stats['win_rate']}% win rate | {stats['total_trades']} trades")
        self.scenario_runner.print_comparison()


def main():
    os.makedirs("logs", exist_ok=True)
    config = Config()
    lab = TradeLab(config)
    signal.signal(signal.SIGINT, lambda s, f: setattr(lab, 'running', False))
    lab.start()


if __name__ == "__main__":
    main()