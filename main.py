"""
Nuclear Infrastructure Screener — daily NQS run.
Run from the repo root: python main.py
"""

from scoring.nqs_scorer import run_full_universe


def print_report(results):
    print(f"\n{'TICKER':<8}{'DOMAIN':<28}{'NQS':<8}{'BUCKETS APPLIED'}")
    print("-" * 80)
    for r in results:
        nqs_display = r["nqs"] if r["nqs"] is not None else "N/A"
        buckets = ", ".join(r["buckets_applied"]) if r["buckets_applied"] else "none"
        print(f"{r['ticker']:<8}{r['domain']:<28}{str(nqs_display):<8}{buckets}")
    print()


if __name__ == "__main__":
    results = run_full_universe()
    print_report(results)
