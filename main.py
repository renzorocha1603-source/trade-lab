#!/usr/bin/env python3
"""
TRADE LAB v2.9 — FORCED TRAINING MODE
Stocks: Z-Score + Kelly + FORCED ENTRIES
Crypto: DIP/MOMENTUM/BREAKOUT + FORCED ENTRIES
If no natural signals trigger, force trades on best candidates.
Letta learns from EVERY outcome — good AND bad.
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
║   TRADE LAB v2.9 — FORCED TRAINING MODE                    ║
║   No perfect setup? Force trade on best candidate.         ║
║   Letta learns from EVERY outcome.                         ║
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
        self.training_mode = True

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

        logger.info(f"TradeLab v2.9 FORCED TRAINING | Crypto: {len(self.crypto_strategy.crypto_symbols)} | Stocks: {len(self.config.data.symbols)}")

    def is_market_open(self) -> bool:
        return True

    def is_crypto_symbol(self, symbol: str) -> bool:
        return symbol in self.crypto_strategy.crypto_symbols

    def should_scan_symbol(self, symbol: str) -> bool:
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
        try: context["usdcad"] = f"{self.data.get_usd_cad_rate():.4f}"
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
        for scenario in self.scenario_runner.scenarios:
            sid = scenario["id"]
            if sid not in self.scenario_runner.results: continue
            entry = self.scenario_runner.results[sid]
            broker = entry["broker"]
            equity = broker.get_equity_cad({})
            if equity < self.config.risk.auto_reload_threshold:
                broker.cash_cad = self.config.risk.auto_reload_amount
                broker.initial_capital_cad = self.config.risk.auto_reload_amount
                broker.positions = {}
                broker.order_history = []
                entry["trades"] = 0
                logger.warning(f"🔄 AUTO-RELOAD: {scenario['name']} reset to ${self.config.risk.auto_reload_amount:,.0f}")

    def force_trade_crypto(self, prices, fx_rate):
        """Force a crypto trade on the best candidate if no natural signals"""
        # First try natural signals
        for symbol in self.crypto_strategy.crypto_symbols:
            signal = self.crypto_strategy.generate_signal(symbol)
            if signal:
                return signal

        # No natural signals — force on best candidate
        best_symbol = None
        best_score = 999
        best_df = None

        for symbol in self.crypto_strategy.crypto_symbols:
            df = self.crypto_strategy.fetch_yahoo_crypto(symbol, "1h")
            if df is None or len(df) < 15: continue
            
            vwap_z = self.crypto_strategy.calculate_vwap_zscore(df)
            
            if vwap_z < best_score:
                best_score = vwap_z
                best_symbol = symbol
                best_df = df

        if best_symbol and best_df is not None and best_score < 0:
            close_col = 'close' if 'close' in best_df.columns else 'Close'
            current_price = best_df[close_col].iloc[-1]
            atr = self.crypto_strategy.calculate_atr(best_df)

            return {
                "symbol": best_symbol,
                "action": "BUY",
                "mode": "FORCED",
                "current_price": current_price,
                "data_source": "Yahoo",
                "quantity_pct": 0.03,
                "target_pct": atr * 1.0,
                "stop_pct": atr * 0.8,
                "net_target": atr * 1.0 - 0.006,
                "risk_reward": 1.25,
                "kelly": 0.1,
                "entry_time": datetime.now().isoformat(),
                "max_hold_hours": 2.0,
                "market_cap_tier": "unknown",
                "indicators": {"vwap_zscore": round(best_score, 3), "atr": round(atr, 4), "rsi": 50},
                "reason": f"FORCED TRAINING | Z:{best_score:.2f} | ATR:{atr:.2%}"
            }
        return None

    def force_trade_stocks(self, prices, fx_rate):
        """Force a stock trade on the best candidate"""
        best_symbol = None
        best_z = 999
        best_hist = None

        for symbol in self.config.data.symbols:
            if self.is_crypto_symbol(symbol): continue
            hist = self.data._price_cache.get(symbol)
            if hist is None or len(hist) < 20: continue

            current_price = prices.get(symbol, 0)
            if current_price <= 0: continue

            z_score = self.strategy.calculate_z_score(hist)

            if z_score < best_z:
                best_z = z_score
                best_symbol = symbol
                best_hist = hist

        if best_symbol and best_hist is not None and best_z < 0.5:
            current_price = prices.get(best_symbol, 0)
            rsi = self.calculate_rsi(best_hist.values)

            return {
                "symbol": best_symbol,
                "action": "BUY",
                "mode": "FORCED",
                "current_price": current_price,
                "quantity_pct": 0.02,
                "reason": f"FORCED TRAINING | Z:{best_z:.2f} | RSI:{rsi:.0f}",
                "z_score": best_z,
                "rsi": rsi,
            }
        return None

    def run_cycle(self):
        start = datetime.now()
        self.cycle_count += 1

        logger.info(f"{'='*70}")
        logger.info(f"CYCLE #{self.cycle_count} | FORCED TRAINING | {start.strftime('%Y-%m-%d %H:%M:%S')}")
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

            # ========== CRYPTO: Natural + Forced ==========
            crypto_signal = self.force_trade_crypto(prices, fx_rate)

            if crypto_signal:
                for scenario in self.scenario_runner.scenarios:
                    if scenario.get("type") != "crypto": continue
                    sid = scenario["id"]
                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)
                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    symbol = crypto_signal["symbol"]
                    qty = crypto_signal["quantity_pct"]
                    current_price = crypto_signal["current_price"]

                    if symbol not in prices:
                        prices[symbol] = current_price

                    order = broker.place_market_order(symbol, "buy", qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        logger.info(f"[CRYPTO {crypto_signal.get('mode', 'SIGNAL')}] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {crypto_signal['reason']}")

                        self.letta.remember_trade({
                            "symbol": symbol, "action": "BUY",
                            "price": order.filled_price_usd, "quantity_pct": qty,
                            "rsi": crypto_signal.get("indicators", {}).get("rsi", 50), "vix": vix,
                            "reason": crypto_signal["reason"], "scenario_id": sid,
                        })

            # ========== STOCKS: Natural + Forced ==========
            stock_signal = self.force_trade_stocks(prices, fx_rate)

            if stock_signal:
                for scenario in self.scenario_runner.scenarios:
                    if scenario.get("type") == "crypto": continue
                    sid = scenario["id"]
                    profile = self.get_risk_profile(sid)

                    if sid not in self.scenario_runner.results:
                        self.scenario_runner._init_scenario(sid)

                    entry = self.scenario_runner.results[sid]
                    broker = entry["broker"]
                    broker.set_fx_rate(fx_rate)

                    symbol = stock_signal["symbol"]
                    qty = stock_signal["quantity_pct"]
                    current_price = stock_signal["current_price"]

                    equity = broker.get_equity_cad(prices)
                    pos_count = len([p for p in broker.positions.values() if p.quantity > 0])
                    proposed_value = qty * current_price * fx_rate if fx_rate > 0 else 0

                    safe, reason = self.risk.can_execute(
                        decision=stock_signal, symbol=symbol, current_equity=equity,
                        initial_capital=broker.initial_capital_cad,
                        current_positions_count=pos_count, proposed_value_cad=proposed_value
                    )

                    if not safe: continue
                    if pos_count >= profile["max_positions"]: continue
                    if qty <= 0: continue

                    order = broker.place_market_order(symbol, "buy", qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        logger.info(f"[STOCK {stock_signal.get('mode', 'SIGNAL')}] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {stock_signal['reason']}")

                        self.letta.remember_trade({
                            "symbol": symbol, "action": "BUY",
                            "price": order.filled_price_usd, "quantity_pct": qty,
                            "rsi": stock_signal.get("rsi", 50), "vix": vix,
                            "reason": stock_signal["reason"], "scenario_id": sid,
                        })

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {total_trades} trades | {duration:.1f}s | Letta rules: {len(self.letta.rules)}")
            self.scenario_runner.save_scenario_snapshots()
            self.push_logs_to_github()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

    def scan_news(self):
        pass

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
        logger.info(f"FORCED TRAINING: ON — Trading every cycle regardless of signals")
        logger.info(f"Crypto: {len(self.crypto_strategy.crypto_symbols)} symbols | Stocks: {len(self.config.data.symbols)} symbols")
        logger.info(f"Auto-reload: ${self.config.risk.auto_reload_amount:,.0f} at ${self.config.risk.auto_reload_threshold:,.0f}")
        logger.info(f"Letta Memory: {len(self.letta.rules)} rules")
        logger.info("24/7 Forced Training Loop starting...\n")
        self.run_cycle()

        try:
            while self.running:
                now = datetime.now()
                if now.minute % 10 == 0:
                    self.run_cycle()
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