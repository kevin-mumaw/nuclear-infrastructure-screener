import os
import csv
from datetime import datetime

# Set up the data storage path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "data", "trade_log.csv")

def initialize_log(log_file=None):
    """Creates the CSV file with column headers if it doesn't exist yet."""
    path = log_file or LOG_FILE
    if not os.path.exists(path):
        # Create data folder if missing
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Ticker", "Action", "Allocation_Dollar",
                "Execution_Price", "Shares", "NQS_Score", "RSI_14"
            ])

def record_trade(ticker, action, dollar_amt, price, nqs, rsi, log_file=None):
    """Logs a single paper trade transaction into the spreadsheet.

    log_file overrides the ledger path — used by the __main__ test so a
    test trade never lands in the real ledger. Omit it for real trades.
    """
    path = log_file or LOG_FILE
    initialize_log(log_file=path)

    # Calculate exact share execution sizing
    shares = round(dollar_amt / price, 4) if price > 0 else 0
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(path, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([date_str, ticker.upper(), action.upper(), dollar_amt, price, shares, nqs, rsi])

    print(f"📝 SECURED: Logged {action.upper()} for {shares} shares of ${ticker.upper()} at ${price}")

if __name__ == "__main__":
    # Test execution locally to see if it generates cleanly.
    # The test trade goes to a throwaway file, NOT the real ledger:
    # the committed trade_log.csv previously held exactly one row and
    # it was this test trade (FLS, 2026-06-23), which read as a real
    # paper trade to every consumer of the log.
    import tempfile
    print("Testing paper log framework (test trade goes to a temp file, not data/trade_log.csv)...")
    with tempfile.TemporaryDirectory() as tmp:
        test_log = os.path.join(tmp, "trade_log_test.csv")
        record_trade(ticker="FLS", action="BUY", dollar_amt=1318.68,
                     price=81.58, nqs=60.0, rsi=64.92, log_file=test_log)
        with open(test_log) as f:
            print(f.read().strip())
    print("Test complete — data/trade_log.csv untouched.")
