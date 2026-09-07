"""
Second Layer Capital — Overnight Volatility Gap-Risk Warner
Scans active asset tracking domains to identify pre-market price dislocations.
"""

import os
import json
import yfinance as yf
from config.universe import UNIVERSE

def scan_overnight_gaps(threshold_pct=3.0):
    print("Initializing Systemic Overnight Volatility Scan...")
    
    # Extract all active tracking tickers out of your universe categories
    all_tickers = []
    for domain in UNIVERSE.values():
        all_tickers.extend(domain["tickers"])
        
    print(f"Scanning tracking universe across {len(all_tickers)} key industrial bottleneck nodes...")
    print(f"Risk Trigger Threshold set at: ±{threshold_pct}% overnight price dislocation.\n")
    
    print(f"================================================================")
    print(f"       SECOND LAYER CAPITAL — VOLATILITY OVERNIGHT TRACKER      ")
    print(f"================================================================")
    print(f"{'TICKER':<8}{'PREV CLOSE':<12}{'OPEN/LIVE':<12}{'GAP DELTA':<12}{'RISK STATUS'}")
    print("-" * 64)

    gap_alerts_found = 0

    for ticker in all_tickers:
        try:
            asset = yf.Ticker(ticker)
            # Fetch the most recent two days of pricing history
            hist = asset.history(period="2d")
            
            if len(hist) < 2:
                continue
                
            prev_close = float(hist['Close'].iloc[-2])
            live_price = float(hist['Close'].iloc[-1])
            
            # Calculate the percentage drift gap
            gap_pct = ((live_price - prev_close) / prev_close) * 100
            
            # Check if the overnight volatility breach passes our threshold filter
            if abs(gap_pct) >= threshold_pct:
                gap_alerts_found += 1
                if gap_pct < 0:
                    status = f"🚨 BREACH (Gap Down)"
                else:
                    status = f"🚀 EXPANSION (Gap Up)"
            else:
                status = "🟢 NOMINAL"

            print(f"{ticker:<8}${prev_close:<11.2f}${live_price:<11.2f}{gap_pct:+.2f}%      {status}")
            
        except Exception as e:
            print(f"{ticker:<8}Failed to compile telemetry mapping.")

    print(f"================================================================")
    print(f"🚨 SCAN COMPLETE: Identified {gap_alerts_found} high-volatility price gap events.")
    print(f"================================================================")

if __name__ == "__main__":
    # Execute scan with a 3.0% structural volatility boundary
    scan_overnight_gaps(threshold_pct=3.0)
