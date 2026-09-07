import os
import csv
from datetime import datetime

# Set up the data storage path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "data", "trade_log.csv")

def initialize_log():
    """Creates the CSV file with column headers if it doesn't exist yet."""
    if not os.path.exists(LOG_FILE):
        # Create data folder if missing
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Ticker", "Action", "Allocation_Dollar", 
                "Execution_Price", "Shares", "NQS_Score", "RSI_14"
            ])

def record_trade(ticker, action, dollar_amt, price, nqs, rsi):
    """Logs a single paper trade transaction into the spreadsheet."""
    initialize_log()
    
    # Calculate exact share execution sizing
    shares = round(dollar_amt / price, 4) if price > 0 else 0
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([date_str, ticker.upper(), action.upper(), dollar_amt, price, shares, nqs, rsi])
        
    print(f"📝 SECURED: Logged {action.upper()} for {shares} shares of ${ticker.upper()} at ${price}")

if __name__ == "__main__":
    # Test execution locally to see if it generates cleanly
    print("Testing paper log framework...")
    record_trade(ticker="FLS", action="BUY", dollar_amt=1318.68, price=81.58, nqs=60.0, rsi=64.92)
