import json
import os
import yfinance as yf
from scoring.nqs_scorer import run_full_universe

def generate_order_sheet(total_capital=10000):
    # 1. Fetch our fresh quality scores
    print("Gathering live calculations from NQS Engine...")
    scores = run_full_universe()
    
    # 2. Get current stock prices via yfinance
    tickers = [item['ticker'] for item in scores]
    print(f"Fetching live market pricing for {len(tickers)} assets...")
    
    prices = {}
    for ticker in tickers:
        try:
            asset = yf.Ticker(ticker)
            prices[ticker] = asset.history(period="1d")['Close'].iloc[-1]
        except Exception:
            prices[ticker] = 0.0

    # 3. Filter out low scores (Minimum quality floor of 50 NQS)
    valid_scores = [item for item in scores if item['nqs'] is not None and item['nqs'] >= 50.0]
    
    if not valid_scores:
        print("No companies passed the minimum quality score threshold.")
        return

    # 4. Calculate weights based on NQS performance
    total_nqs = sum(item['nqs'] for item in valid_scores)
    
    print(f"\n==============================================================")
    print(f"         SECOND LAYER CAPITAL — NUCLEAR ALLOCATION SHEET       ")
    print(f"         TOTAL CASH BUDGET: ${total_capital:,}                  ")
    print(f"==============================================================")
    print(f"{'TICKER':<8}{'DOMAIN':<18}{'NQS':<8}{'TARGET %':<12}{'DOLLAR':<12}{'SHARES'}")
    print("-" * 62)

    for item in valid_scores:
        ticker = item['ticker']
        domain = item['domain']
        nqs = item['nqs']
        price = prices.get(ticker, 0.0)
        
        target_weight = nqs / total_nqs
        target_dollar = total_capital * target_weight
        target_shares = target_dollar / price if price > 0 else 0.0
        
        short_domain = domain.replace('components_grid', 'Components').replace('fuel_cycle', 'Fuel Cycle').replace('smr_pureplay', 'SMR Play')

        print(f"{ticker:<8}{short_domain:<18}{nqs:<8}{target_weight*100:<11.2f}% ${target_dollar:<10.2f}{target_shares:.2f}")
    print(f"==============================================================")

if __name__ == "__main__":
    generate_order_sheet(total_capital=10000)
