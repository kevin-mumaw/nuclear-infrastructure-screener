import json
import os
from scoring.nqs_scorer import run_full_universe
from data.fetch_fundamentals import fetch_technical_signals

def generate_order_sheet(total_capital=10000):
    print("Gathering live calculations from NQS Engine...")
    scores = run_full_universe()
    
    valid_scores = [item for item in scores if item['nqs'] is not None and item['nqs'] >= 50.0]
    
    if not valid_scores:
        print("No companies passed the minimum quality score threshold.")
        return

    total_nqs = sum(item['nqs'] for item in valid_scores)
    
    print(f"\n=============================================================================")
    print(f"         SECOND LAYER CAPITAL — NUCLEAR ALLOCATION & TECHNICAL FILTER        ")
    print(f"         TOTAL CASH BUDGET: ${total_capital:,}                                 ")
    print(f"=============================================================================")
    print(f"{'TICKER':<8}{'NQS':<6}{'TARGET %':<10}{'DOLLAR':<10}{'PRICE':<9}{'RSI(14)':<9}{'50-SMA':<8}{'ACTION STATUS'}")
    print("-" * 77)

    for item in valid_scores:
        ticker = item['ticker']
        nqs = item['nqs']
        
        # Pull live technical signals
        tech = fetch_technical_signals(ticker)
        price = tech["close_price"]
        rsi = tech["rsi_14"]
        above_sma = tech["above_50_sma"]
        
        # Pro-rata weight allocation
        target_weight = nqs / total_nqs
        target_dollar = total_capital * target_weight
        
        # Determine actionable status based on technical rules
        sma_status = "ABOVE" if above_sma else "BELOW"
        
        if rsi is not None:
            if rsi >= 70.0:
                action = "HOLD (Overbought)"
            elif rsi <= 35.0 and above_sma:
                action = "💥 BUY ALERT (Dip)"
            elif above_sma:
                action = "✅ EXECUTE BUY"
            else:
                action = "WAIT (No Trend)"
        else:
            action = "DATA ERROR"

        rsi_display = str(rsi) if rsi is not None else "N/A"

        print(f"{ticker:<8}{nqs:<6}{target_weight*100:<9.1f}% ${target_dollar:<9.2f}${price:<8.2f}{rsi_display:<9}{sma_status:<8}{action}")
    print(f"=============================================================================")

if __name__ == "__main__":
    generate_order_sheet(total_capital=10000)
