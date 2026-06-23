import json
from scoring.nqs_scorer import run_full_universe

def generate_x_post():
    scores = run_full_universe()
    valid_scores = [item for item in scores if item['nqs'] is not None]
    
    if not valid_scores:
        return
        
    top_ticker = valid_scores[0]['ticker']
    top_nqs = valid_scores[0]['nqs']
    
    # Constructing a tight, high-impact post under 280 characters
    line1 = f"📊 SECOND LAYER CAPITAL | Nuclear Screener\n"
    line2 = f"Top Pick: ${top_ticker} ({top_nqs} NQS)\n\n"
    line3 = f"Top System Rankings:\n"
    
    rank_lines = ""
    for rank, item in enumerate(valid_scores[:4], 1):
        rank_lines += f"{rank}. ${item['ticker']} ({item['nqs']} NQS)\n"
        
    line4 = f"\n#Nuclear #Quantitative"
    
    # Combine everything
    full_post = line1 + line2 + line3 + rank_lines + line4
    char_count = len(full_post)
    
    print("\n[ COPY AND PASTE THE BLOCK BELOW FOR YOUR X POST ]")
    print("==================================================")
    print(full_post)
    print("==================================================")
    print(f"TOTAL CHARACTERS: {char_count} / 280 (X Standard Cap)")
    
    if char_count > 280:
        print("⚠️ WARNING: Post exceeds 280 characters! Shorten your text.")
    else:
        print("✅ PASS: Post is within the safe 280 character limit.")

if __name__ == "__main__":
    generate_x_post()
