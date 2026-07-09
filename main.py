#!/usr/bin/env python3
"""
TRADE LAB v2.6 — FAST LEARNING MODE
Stocks: Z-Score + Kelly — REAL signals + forced for training
Crypto: DIP/MOMENTUM/BREAKOUT — REAL signals + forced for training
Fiat: Pennies Scalping — REAL signals + FORCED every cycle
Letta evaluates after 1 HOUR (not 24h) for rapid learning.
GitHub API authentication for log pushing.
"""

import os, sys, time, signal, logging, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.pipeline import DataPipeline
from strategy.five_ten_rule import FiveTenStrategy, SignalAction
from strategy.deepseek_research import DeepSeekResearch
from strategy.claude_psychology import ClaudePsychology
from strategy.crypto_scalper import CryptoPenniesStrategy
from strategy.fiat_scalper import FiatPenniesStrategy
from risk.manager import RiskManager
from portfolio.tracker import PortfolioTracker
from simulator.runner import ScenarioRunner
from learning.letta_memory import LettaMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.FileHandler('logs/system.log'), logging.StreamHandler()])
logger = logging.getLogger("TradeLab")

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║   TRADE LAB v2.6 — FAST LEARNING MODE                      ║
║   Stocks · Crypto · Fiat — Real Signals + Forced Training  ║
║   Letta evaluates every 1 HOUR for rapid learning.         ║
╚══════════════════════════════════════════════════════════════╝
"""

class TradeLab:
    def __init__(self, config: Config):
        self.config = config
        self.data = DataPipeline(config)
        self.strategy = FiveTenStrategy(config)
        self.crypto_strategy = CryptoPenniesStrategy(config)
        self.fiat_strategy = FiatPenniesStrategy(config)
        self.deepseek = DeepSeekResearch(config) if config.use_ai else None
        self.claude = ClaudePsychology(config) if config.use_ai else None
        self.risk = RiskManager(config)
        self.tracker = PortfolioTracker()
        self.scenario_runner = ScenarioRunner(config, self.data)
        self.letta = LettaMemory(config)
        self.data.load_historical_data()
        self.cycle_count = 0
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
            "fiat": self.fiat_strategy.fiat_symbols,
            "international": ["BABA","TSM"],
            "consumer": ["WMT"],
        }

        logger.info(f"TradeLab v2.6 FAST MODE | Stocks: {len(self.config.data.symbols)} | Crypto: {len(self.crypto_strategy.crypto_symbols)} | Fiat: {len(self.fiat_strategy.fiat_symbols)}")

    def is_crypto_symbol(self, symbol: str) -> bool:
        return symbol in self.crypto_strategy.crypto_symbols

    def is_fiat_symbol(self, symbol: str) -> bool:
        return symbol in self.fiat_strategy.fiat_symbols

    def is_special_symbol(self, symbol: str) -> bool:
        return self.is_crypto_symbol(symbol) or self.is_fiat_symbol(symbol)

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
                logger.warning(f"AUTO-RELOAD: {scenario['name']} reset to ${self.config.risk.auto_reload_amount:,.0f}")

    def find_best_crypto(self, prices, fx_rate):
        """Find crypto trade — natural signal or best dip"""
        for symbol in self.crypto_strategy.crypto_symbols:
            signal = self.crypto_strategy.generate_signal(symbol)
            if signal:
                return signal

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
            dip_strength = min(1.0, abs(best_score) / 3.0)
            position_size = round(0.01 + (dip_strength * 0.06), 4)

            return {
                "symbol": best_symbol, "action": "BUY", "mode": "DIP",
                "current_price": current_price, "data_source": "Yahoo",
                "quantity_pct": position_size,
                "target_pct": atr * 1.5, "stop_pct": atr * 1.0,
                "entry_time": datetime.now().isoformat(), "max_hold_hours": 4.0,
                "indicators": {"vwap_zscore": round(best_score, 3), "atr": round(atr, 4), "rsi": 50},
                "reason": f"DIP BUY | Z:{best_score:.2f} | Size:{position_size:.1%} | ATR:{atr:.2%}"
            }
        return None

    def find_best_stock(self, prices, fx_rate):
        """Find stock trade — best Z-Score dip"""
        best_symbol = None
        best_z = 999
        best_hist = None

        for symbol in self.config.data.symbols:
            if self.is_special_symbol(symbol): continue
            hist = self.data._price_cache.get(symbol)
            if hist is None or len(hist) < 20: continue
            current_price = prices.get(symbol, 0)
            if current_price <= 0: continue
            z_score = self.strategy.calculate_z_score(hist)
            if z_score < best_z:
                best_z = z_score
                best_symbol = symbol
                best_hist = hist

        if best_symbol and best_hist is not None and best_z < 0:
            current_price = prices.get(best_symbol, 0)
            rsi = self.calculate_rsi(best_hist.values)
            dip_strength = min(1.0, abs(best_z) / 3.0)
            position_size = round(0.01 + (dip_strength * 0.05), 4)

            return {
                "symbol": best_symbol, "action": "BUY", "mode": "DIP",
                "current_price": current_price, "quantity_pct": position_size,
                "reason": f"DIP BUY | Z:{best_z:.2f} | Size:{position_size:.1%} | RSI:{rsi:.0f}",
                "z_score": best_z, "rsi": rsi,
            }
        return None

    def run_cycle(self):
        start = datetime.now()
        self.cycle_count += 1

        logger.info(f"{'='*70}")
        logger.info(f"CYCLE #{self.cycle_count} | FAST TRAINING | {start.strftime('%Y-%m-%d %H:%M:%S')}")
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

            # ========== CRYPTO ==========
            crypto_signal = self.find_best_crypto(prices, fx_rate)
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
                    if symbol not in prices: prices[symbol] = current_price
                    order = broker.place_market_order(symbol, "buy", qty, prices)
                    if order and order.status == "filled":
                        total_trades += 1
                        entry["trades"] += 1
                        self.tracker.record_trade(symbol, "BUY", order.quantity, order.filled_price_usd, crypto_signal["reason"], True, fx_rate, order.fx_fee_cad)
                        logger.info(f"[CRYPTO] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {crypto_signal['reason']}")
                        self.letta.remember_trade({
                            "symbol": symbol, "action": "BUY", "price": order.filled_price_usd,
                            "quantity_pct": qty, "rsi": crypto_signal.get("indicators", {}).get("rsi", 50),
                            "vix": vix, "reason": crypto_signal["reason"], "scenario_id": sid,
                        })

            # ========== FIAT: Natural + FORCED every cycle ==========
            fiat_traded = False

            for symbol in self.fiat_strategy.fiat_symbols:
                fiat_signal = self.fiat_strategy.generate_signal(symbol)
                if fiat_signal:
                    for scenario in self.scenario_runner.scenarios:
                        if scenario.get("type") != "fiat": continue
                        sid = scenario["id"]
                        if sid not in self.scenario_runner.results:
                            self.scenario_runner._init_scenario(sid)
                        entry = self.scenario_runner.results[sid]
                        broker = entry["broker"]
                        broker.set_fx_rate(fx_rate)
                        sym = fiat_signal["symbol"]
                        qty = fiat_signal["quantity_pct"]
                        cp = fiat_signal["current_price"]
                        if sym not in prices: prices[sym] = cp
                        order = broker.place_market_order(sym, "buy", qty, prices)
                        if order and order.status == "filled":
                            total_trades += 1
                            entry["trades"] += 1
                            fiat_traded = True
                            self.tracker.record_trade(sym, "BUY", order.quantity, order.filled_price_usd, fiat_signal["reason"], True, fx_rate, order.fx_fee_cad)
                            logger.info(f"[FIAT] BUY {order.quantity:.4f} {sym} @ ${order.filled_price_usd:.4f} | {fiat_signal['reason']}")
                            self.letta.remember_trade({
                                "symbol": sym, "action": "BUY", "price": order.filled_price_usd,
                                "quantity_pct": qty, "rsi": fiat_signal.get("indicators", {}).get("rsi", 50),
                                "vix": vix, "reason": fiat_signal["reason"], "scenario_id": sid,
                            })

            if not fiat_traded:
                best_pair = None
                best_rsi = 999
                best_cp = None

                for symbol in self.fiat_strategy.fiat_symbols:
                    df = self.fiat_strategy.fetch_yahoo_forex(symbol)
                    if df is None or len(df) < 15: continue
                    close_col = 'close' if 'close' in df.columns else 'Close'
                    cp = df[close_col].iloc[-1]
                    rsi_val = self.fiat_strategy.calculate_rsi(df)
                    if rsi_val < best_rsi:
                        best_rsi = rsi_val
                        best_pair = symbol
                        best_cp = cp

                if best_pair and best_cp:
                    for scenario in self.scenario_runner.scenarios:
                        if scenario.get("type") != "fiat": continue
                        sid = scenario["id"]
                        if sid not in self.scenario_runner.results:
                            self.scenario_runner._init_scenario(sid)
                        entry = self.scenario_runner.results[sid]
                        broker = entry["broker"]
                        broker.set_fx_rate(fx_rate)
                        if best_pair not in prices: prices[best_pair] = best_cp
                        order = broker.place_market_order(best_pair, "buy", 0.02, prices)
                        if order and order.status == "filled":
                            total_trades += 1
                            entry["trades"] += 1
                            self.tracker.record_trade(best_pair, "BUY", order.quantity, order.filled_price_usd, f"FORCED FIAT | RSI:{best_rsi:.0f}", True, fx_rate, order.fx_fee_cad)
                            logger.info(f"[FIAT FORCED] BUY {order.quantity:.4f} {best_pair} @ ${order.filled_price_usd:.4f} | RSI:{best_rsi:.0f}")
                            self.letta.remember_trade({
                                "symbol": best_pair, "action": "BUY", "price": order.filled_price_usd,
                                "quantity_pct": 0.02, "rsi": best_rsi, "vix": vix,
                                "reason": f"FORCED FIAT | RSI:{best_rsi:.0f}", "scenario_id": sid,
                            })

            # ========== STOCKS ==========
            stock_signal = self.find_best_stock(prices, fx_rate)
            if stock_signal:
                for scenario in self.scenario_runner.scenarios:
                    if scenario.get("type") != "stocks": continue
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
                        self.tracker.record_trade(symbol, "BUY", order.quantity, order.filled_price_usd, stock_signal["reason"], True, fx_rate, order.fx_fee_cad)
                        logger.info(f"[STOCK] BUY {order.quantity:.4f} {symbol} @ ${order.filled_price_usd:.2f} | {stock_signal['reason']}")
                        self.letta.remember_trade({
                            "symbol": symbol, "action": "BUY", "price": order.filled_price_usd,
                            "quantity_pct": qty, "rsi": stock_signal.get("rsi", 50),
                            "vix": vix, "reason": stock_signal["reason"], "scenario_id": sid,
                        })

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Cycle: {total_trades} trades | {duration:.1f}s | Letta rules: {len(self.letta.rules)}")
            self.scenario_runner.save_scenario_snapshots()
            self.push_logs_to_github()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

    def push_logs_to_github(self):
        """Push logs to GitHub using GitHub API (no git needed)"""
        try:
            import requests
            import base64

            token = (
                os.environ.get("GITHUB_TOKEN") or
                os.environ.get("github_token") or
                os.environ.get("GH_TOKEN") or
                ""
            ).strip()

            if not token:
                return

            owner = "renzorocha1603-source"
            repo = "trade-lab"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            }

            log_files = [
                "logs/trades.json",
                "logs/scenario_snapshots.json",
                "logs/learned_rules.json",
                "logs/accuracy_log.json",
                "logs/portfolio_snapshots.json"
            ]

            for filepath in log_files:
                if not os.path.exists(filepath):
                    continue

                with open(filepath, "r") as f:
                    content = f.read()

                if not content.strip():
                    continue

                url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"
                resp = requests.get(url, headers=headers)
                sha = resp.json().get("sha") if resp.status_code == 200 else None

                data = {
                    "message": f"Auto-update {filepath} [bot]",
                    "content": base64.b64encode(content.encode()).decode(),
                    "branch": "main"
                }
                if sha:
                    data["sha"] = sha

                requests.put(url, headers=headers, json=data)

            logger.info("✅ Logs pushed to GitHub via API")

        except Exception as e:
            logger.error(f"GitHub API error: {e}")

    def start(self):
        print(BANNER)
        logger.info(f"FAST LEARNING — Real signals + Forced fiat, Letta evaluates every 1 hour")
        logger.info(f"Stocks: {len(self.config.data.symbols)} | Crypto: {len(self.crypto_strategy.crypto_symbols)} | Fiat: {len(self.fiat_strategy.fiat_symbols)}")
        logger.info(f"Scenarios: {len(self.scenario_runner.scenarios)} | Auto-reload: ${self.config.risk.auto_reload_amount:,.0f}")
        logger.info(f"Letta Memory: {len(self.letta.rules)} rules")
        logger.info("24/7 Fast Training Loop starting...\n")
        self.run_cycle()

        try:
            while self.running:
                now = datetime.now()
                if now.minute % 5 == 0:
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