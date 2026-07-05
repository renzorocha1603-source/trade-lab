"""
Portfolio Tracker - Trades, snapshots, performance reports.
Saves everything to logs/ folder for dashboard to read.
"""

import json
import os
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Tracks portfolio performance over time"""

    def __init__(self):
        self.snapshots: List[Dict] = []
        self.trades: List[Dict] = []
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self._load_history()

    def _load_history(self):
        snapshot_file = f"{self.log_dir}/portfolio_snapshots.json"
        trades_file = f"{self.log_dir}/trades.json"
        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file) as f:
                    self.snapshots = json.load(f)
                logger.info(f"Loaded {len(self.snapshots)} snapshots")
            except: pass
        if os.path.exists(trades_file):
            try:
                with open(trades_file) as f:
                    self.trades = json.load(f)
                logger.info(f"Loaded {len(self.trades)} trades")
            except: pass

    def record_snapshot(self, portfolio_summary: Dict):
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "equity_cad": portfolio_summary.get("equity_cad", 0),
            "cash_cad": portfolio_summary.get("cash_cad", 0),
            "total_pnl_cad": portfolio_summary.get("total_pnl_cad", 0),
            "total_pnl_pct": portfolio_summary.get("total_pnl_pct", 0),
            "fx_rate": portfolio_summary.get("fx_rate_usd_cad", 1.35),
            "total_fx_fees_cad": portfolio_summary.get("total_fx_fees_cad", 0),
            "positions_count": len(portfolio_summary.get("positions", {})),
            "total_trades": portfolio_summary.get("total_trades", 0),
            "positions": portfolio_summary.get("positions", {})
        }
        self.snapshots.append(snapshot)
        with open(f"{self.log_dir}/portfolio_snapshots.json", "w") as f:
            json.dump(self.snapshots, f, indent=2, default=str)

    def record_trade(self, symbol: str, action: str, quantity: float,
                    price_usd: float, reason: str, ai_modified: bool = False,
                    fx_rate: float = 1.35, fees_cad: float = 0):
        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": action,
            "quantity": round(quantity, 4),
            "price_usd": round(price_usd, 2),
            "value_cad": round(quantity * price_usd * fx_rate, 2),
            "fx_rate": round(fx_rate, 4),
            "fees_cad": round(fees_cad, 2),
            "reason": reason,
            "ai_modified": ai_modified
        }
        self.trades.append(trade)
        with open(f"{self.log_dir}/trades.json", "w") as f:
            json.dump(self.trades, f, indent=2, default=str)
        logger.info(f"Trade: {action} {quantity} {symbol} @ ${price_usd:.2f} USD")

    def get_metrics(self) -> Dict:
        if len(self.snapshots) < 2:
            return {"message": "Not enough data yet"}
        first = self.snapshots[0]
        last = self.snapshots[-1]
        ai_trades = sum(1 for t in self.trades if t.get("ai_modified"))
        return {
            "start_date": first["timestamp"][:10],
            "current_date": last["timestamp"][:10],
            "starting_equity_cad": first["equity_cad"],
            "current_equity_cad": last["equity_cad"],
            "total_return_cad": round(last["equity_cad"] - first["equity_cad"], 2),
            "total_return_pct": round(last.get("total_pnl_pct", 0), 2),
            "total_trades": len(self.trades),
            "ai_modified_trades": ai_trades,
            "total_fx_fees_cad": round(sum(t.get("fees_cad", 0) for t in self.trades), 2),
            "current_positions": last.get("positions_count", 0),
            "current_fx_rate": last.get("fx_rate", 1.35)
        }

    def print_report(self):
        m = self.get_metrics()
        print(f"""
╔══════════════════════════════════════════════════╗
║              PORTFOLIO REPORT                     ║
╠══════════════════════════════════════════════════╣
║ Start:      {m.get('start_date', 'N/A'):<38} ║
║ Current:    {m.get('current_date', 'N/A'):<38} ║
╠══════════════════════════════════════════════════╣
║ Start Equity:   ${m.get('starting_equity_cad', 0):>10,.2f} CAD               ║
║ Current Equity: ${m.get('current_equity_cad', 0):>10,.2f} CAD               ║
║ Total Return:   ${m.get('total_return_cad', 0):>10,.2f} CAD               ║
║ Return %:       {m.get('total_return_pct', 0):>10.2f}%                    ║
╠══════════════════════════════════════════════════╣
║ Total Trades:   {m.get('total_trades', 0):>10}                      ║
║ AI Modified:    {m.get('ai_modified_trades', 0):>10}                      ║
║ FX Fees Paid:   ${m.get('total_fx_fees_cad', 0):>10,.2f} CAD               ║
║ Positions:      {m.get('current_positions', 0):>10}                      ║
║ USD/CAD Rate:   {m.get('current_fx_rate', 1.35):>10.4f}                    ║
╚══════════════════════════════════════════════════╝
        """)