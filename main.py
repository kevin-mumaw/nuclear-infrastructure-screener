"""
Nuclear Infrastructure Screener — daily NQS run.
Run from the repo root: python main.py
"""

from scoring.nqs_scorer import run_full_universe, print_results_table


if __name__ == "__main__":
    print_results_table(run_full_universe())
