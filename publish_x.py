import json
import os
import yfinance as yf
from scoring.nqs_scorer import run_full_universe

def generate_x_post():
    scores = run_full_universe()
    valid_scores = [item for item in scores if item['nqs'] is not None]
    
    if not valid_scores:
        return
        
    top_ticker = valid_scores[0]['ticker']
    top_nqs = valid_scores[0]['nqs']
    
    # Scan for gaps on the top pick to see if it's experiencing volatility
    alert_suffix = ""
    try:
        asset = yf.Ticker(top_ticker)
        hist = asset.history(period="2d")
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            live_price = float(hist['Close'].iloc[-1])
            gap_pct = ((live_price - prev_close) / prev_close) * 100
            if abs(gap_pct) >= 3.0:
                alert_suffix = f"\n⚠️ Volatility Alert: {gap_pct:+.1f}% shift!"
    except Exception:
        pass
        
    # Build strict character-capped 280-char block
    line1 = f"📊 SECOND LAYER CAPITAL | Screener\n"
    line2 = f"Top Pick: ${top_ticker} ({top_nqs} NQS){alert_suffix}\n\n"
    line3 = f"System Standings:\n"
    
    rank_lines = ""
    for rank, item in enumerate(valid_scores[:3], 1):
        rank_lines += f"{rank}. ${item['ticker']} ({item['nqs']} NQS)\n"
        
    line4 = f"\n#Nuclear #Quantitative"
    
    full_post = line1 + line2 + line3 + rank_lines + line4
    char_count = len(full_post)
    
    print("\n[ COPY AND PASTE THE BLOCK BELOW FOR YOUR X POST ]")
    print("==================================================")
    print(full_post)
    print("==================================================")
    print(f"TOTAL CHARACTERS: {char_count} / 280")
    
    if char_count > 280:
        print("⚠️ WARNING: Post exceeds 280 characters!")
    else:
        print("✅ PASS: Ready to broadcast.")

if __name__ == "__main__":
    generate_x_post()
