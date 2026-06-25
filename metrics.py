"""
Second Layer Capital — Portfolio Performance Metrics Engine
Analyzes local trade_log.csv against live market prices.
"""

import os
import csv
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "data", "trade_log.csv")

def run_performance_analysis():
    if not os.path.exists(LOG_FILE):
        print("⚠️ No trade log file found yet. Execute some trades via allocator.py first!")
        return

    print("Reading transaction history from ledger...")
    trades = []
    unique_tickers = set()

    with open(LOG_FILE, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
            unique_tickers.add(row['Ticker'])

    if not trades:
        print("The trade log is currently empty.")
        return

    # Fetch live current prices for all tickers in the log to calculate performance
    print(f"Fetching live market updates for {list(unique_tickers)}...")
    live_prices = {}
    for ticker in unique_tickers:
        try:
            asset = yf.Ticker(ticker)
            live_prices[ticker] = float(asset.history(period="1d")['Close'].iloc[-1])
        except Exception:
            live_prices[ticker] = 0.0

    total_invested = 0.0
    total_current_value = 0.0
    winning_trades = 0
    total_trades = 0

    print(f"\n==========================================================")
    print(f"         SECOND LAYER CAPITAL — PERFORMANCE METRICS        ")
    print(f"==========================================================")
    print(f"{'TICKER':<8}{'SHARES':<10}{'ENTRY_PX':<10}{'LIVE_PX':<10}{'RETURN %'}")
    print("-" * 58)

    for trade in trades:
        ticker = trade['Ticker']
        shares = float(trade['Shares'])
        entry_price = float(trade['Execution_Price'])
        allocated_dollar = float(trade['Allocation_Dollar'])
        
        live_price = live_prices.get(ticker, 0.0)
        
        if live_price == 0.0:
            continue
            
        current_value = shares * live_price
        trade_return_pct = ((live_price - entry_price) / entry_price) * 100
        
        total_invested += allocated_dollar
        total_current_value += current_value
        total_trades += 1
        
        if trade_return_pct > 0:
            winning_trades += 1

        print(f"{ticker:<8}{shares:<10.2f}${entry_price:<9.2f}${live_price:<9.2f}{trade_return_pct:+.2f}%")

    # Portfolio Summary Calculations
    total_profit_loss = total_current_value - total_invested
    total_return_pct = (total_profit_loss / total_invested * 100) if total_invested > 0 else 0.0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    print(f"==========================================================")
    print(f"🏆 PORTFOLIO SUMMARY STATISTICS:")
    print(f"  • Total Capital Invested : ${total_invested:,.2f}")
    print(f"  • Current Net Asset Val  : ${total_current_value:,.2f}")
    print(f"  • Total Unrealized PnL   : ${total_profit_loss:+,.2f} ({total_return_pct:+.2f}%)")
    print(f"  • Win Rate Percentage    : {win_rate:.1f}% ({winning_trades}/{total_trades} Successful Trades)")
    print(f"==========================================================")

if __name__ == "__main__":
    run_performance_analysis()
