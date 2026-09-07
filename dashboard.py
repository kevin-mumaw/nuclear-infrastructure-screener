"""
Second Layer Capital — Nuclear Infrastructure Screener Dashboard
Streamlit app: three-tab institutional interface.

  Tab 1 — NQS Scorecard   : Domain breakdown, three-bucket scores, gate status
  Tab 2 — Engine Backtester: Performance matrix + interactive Plotly equity curves
  Tab 3 — Universe Auditing: Live prices, raw backlog overrides, watchlist log

Run:  streamlit run dashboard.py
"""

import json
import os
import warnings
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Nuclear Infrastructure — Second Layer Capital",
    page_icon="⚛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #06090f;
    color: #c8d0e0;
  }
  .slc-header { border-bottom: 1px solid #1e2a3a; padding-bottom: 0.75rem; margin-bottom: 1.5rem; }
  .slc-header h1 { font-size: 1.25rem; font-weight: 600; letter-spacing: 0.04em; color: #e8edf5; margin: 0; }
  .slc-header p { font-size: 0.78rem; color: #5a7090; margin: 0.2rem 0 0 0; font-family: 'IBM Plex Mono', monospace; }
  .metric-tile { background: #0c1220; border: 1px solid #1e2a3a; border-radius: 4px; padding: 1rem 1.25rem; }
  .metric-tile .label { font-size: 0.70rem; color: #5a7090; font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; }
  .metric-tile .value { font-size: 1.6rem; font-weight: 600; color: #e8b84b; font-family: 'IBM Plex Mono', monospace; line-height: 1.2; }
  .metric-tile .sub { font-size: 0.72rem; color: #5a7090; margin-top: 0.15rem; }
  .nqs-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .nqs-table th { background: #0c1220; color: #5a7090; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.06em; padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #1e2a3a; }
  .nqs-table td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #111820; font-family: 'IBM Plex Mono', monospace; color: #c8d0e0; }
  .nqs-table tr:hover td { background: #0c1220; }
  .gate-active { color: #4caf82; font-weight: 600; }
  .gate-gated  { color: #e05a5a; }
  .gate-watch  { color: #e8b84b; }
  .nqs-high    { color: #4caf82; font-weight: 600; }
  .nqs-mid     { color: #e8b84b; }
  .nqs-low     { color: #e05a5a; }
  .nqs-null    { color: #3a4a5a; }
  .section-label { font-size: 0.68rem; font-family: 'IBM Plex Mono', monospace; color: #5a7090; letter-spacing: 0.08em; text-transform: uppercase; border-left: 2px solid #e8b84b; padding-left: 0.5rem; margin: 1.5rem 0 0.75rem 0; }
  .stTabs [data-baseweb="tab-list"] { background: #06090f; border-bottom: 1px solid #1e2a3a; gap: 0; }
  .stTabs [data-baseweb="tab"] { background: transparent; color: #5a7090; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; letter-spacing: 0.04em; padding: 0.6rem 1.25rem; border-radius: 0; border-bottom: 2px solid transparent; }
  .stTabs [aria-selected="true"] { color: #e8edf5; border-bottom: 2px solid #e8b84b; background: transparent; }
</style>
""", unsafe_allow_html=True)
TICKERS = [
    "CCJ", "UEC", "DNN", "LEU",
    "BWXT", "GEV", "FLS", "IR",
    "OKLO", "SMR",
    "CEG", "VST", "TLN",
    "J", "FLR",
]

DOMAIN_LABELS = {
    "fuel_cycle":      "Uranium Fuel Cycle",
    "components_grid": "Components & Grid",
    "smr_pureplay":    "SMR Pure-Plays",
    "utilities":       "Utilities",
    "epc":             "EPC",
}

WATCHLIST        = ["NXE", "URG", "EU", "ISOU", "NNE"]
DEFENSIVE        = "SGOV"
NQS_GATE         = 40
START_DATE       = "2022-01-01"
OVERRIDES_PATH   = os.path.join(os.path.dirname(__file__), "config", "manual_overrides.json")
MOMENTUM_WINDOWS = [14, 60, 200]
DRAWDOWN_LIMIT   = 0.15
TAKE_PROFIT      = 1.00
SLIPPAGE         = 0.0005
RISK_FREE_RATE   = 0.05

IPO_FLOORS = {
    "OKLO": "2024-05-10",
    "GEV":  "2024-04-02",
    "TLN":  "2023-05-17",
}

@st.cache_data(ttl=3600)
def load_nqs_scores():
    try:
        from scoring.nqs_scorer import calculate_nqs
        overrides = load_overrides()
        rows = []
        for ticker in TICKERS:
            r   = calculate_nqs(ticker, overrides)
            bs  = next((b for b in r["bucket_detail"] if b["bucket"] == "balance_sheet_runway"), {})
            me  = next((b for b in r["bucket_detail"] if b["bucket"] == "margin_expansion"), {})
            blg = next((b for b in r["bucket_detail"] if b["bucket"] == "backlog_momentum"), {})
            rows.append({
                "Ticker":  ticker,
                "Domain":  DOMAIN_LABELS.get(r["domain"], r["domain"]),
                "NQS":     r["nqs"],
                "Runway":  bs.get("score"),
                "Margin":  me.get("score"),
                "Backlog": blg.get("score"),
                "_domain": r["domain"],
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"NQS load failed: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_prices():
    all_tickers = TICKERS + [DEFENSIVE]
    raw = yf.download(all_tickers, start=START_DATE,
                      end=datetime.today().strftime("%Y-%m-%d"),
                      auto_adjust=True, progress=False)["Close"]
    raw = raw.ffill().dropna(how="all")
    eq  = raw[TICKERS].copy()
    for ticker, floor in IPO_FLOORS.items():
        if ticker in eq.columns:
            eq.loc[eq.index < pd.Timestamp(floor), ticker] = float("nan")
    return eq, raw[DEFENSIVE]

@st.cache_data(ttl=3600)
def load_live_quotes():
    rows = []
    for ticker in TICKERS:
        try:
            info = yf.Ticker(ticker).fast_info
            rows.append({
                "Ticker":   ticker,
                "Price":    round(info.last_price, 2) if info.last_price else None,
                "52W High": round(info.year_high, 2)  if info.year_high  else None,
                "52W Low":  round(info.year_low, 2)   if info.year_low   else None,
            })
        except Exception:
            rows.append({"Ticker": ticker, "Price": None, "52W High": None, "52W Low": None})
    return pd.DataFrame(rows)

def load_overrides():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH) as f:
            return json.load(f)
    return {}

def nqs_color(val):
    if val is None: return "nqs-null"
    if val >= 70:   return "nqs-high"
    if val >= 40:   return "nqs-mid"
    return "nqs-low"

def gate_class(val, domain):
    if domain == "smr_pureplay": return "gate-watch"
    if val is None:              return "nqs-null"
    if val >= NQS_GATE:         return "gate-active"
    return "gate-gated"

def gate_label(val, domain):
    if domain == "smr_pureplay": return "EXCEPTION"
    if val is None:              return "—"
    if val >= NQS_GATE:         return "ACTIVE"
    return "GATED"

def fmt_score(val):
    if val is None: return '<span class="nqs-null">—</span>'
    return f'<span class="{nqs_color(val)}">{val}</span>'

def fmt_bucket(val):
    if val is None: return '<span class="nqs-null">—</span>'
    if val >= 7:    return f'<span class="nqs-high">{val}/10</span>'
    if val >= 4:    return f'<span class="nqs-mid">{val}/10</span>'
    return f'<span class="nqs-low">{val}/10</span>'
def run_backtest_engine(equity_prices, defensive_prices, nqs_df):
    nqs_map = dict(zip(nqs_df["Ticker"], nqs_df["NQS"])) if not nqs_df.empty else {}

    def nqs_passes(ticker):
        score = nqs_map.get(ticker)
        return True if score is None else score >= NQS_GATE

    results = {}
    for window in MOMENTUM_WINDOWS:
        momentum = equity_prices.pct_change(periods=window)
        peaks    = equity_prices.cummax()
        drawdown = (equity_prices - peaks) / peaks
        eq_ret   = equity_prices.pct_change()
        def_ret  = defensive_prices.pct_change()

        trading_days  = equity_prices.index[window + 1:]
        equity_value  = 1.0
        curve         = [1.0]
        daily_returns = []
        prev_basket   = []
        entry_px      = {t: None for t in TICKERS}

        for i, current_day in enumerate(trading_days):
            sig_day = equity_prices.index[window + i]
            mom_row = momentum.loc[sig_day]
            dd_row  = drawdown.loc[sig_day]
            basket  = []

            for t in TICKERS:
                if pd.isna(mom_row[t]):          continue
                if mom_row[t] <= 0:              entry_px[t] = None; continue
                if dd_row[t] <= -DRAWDOWN_LIMIT: entry_px[t] = None; continue
                if entry_px[t] is None:
                    entry_px[t] = equity_prices.loc[sig_day, t]
                gain = (equity_prices.loc[sig_day, t] / entry_px[t]) - 1.0
                if gain >= TAKE_PROFIT:          entry_px[t] = None; continue
                if not nqs_passes(t):            continue
                basket.append(t)

            slip = SLIPPAGE if basket != prev_basket else 0.0
            if basket:
                dr = eq_ret.loc[current_day, basket].sum() / len(basket) - slip
            else:
                dr = def_ret.loc[current_day] - slip

            daily_returns.append(dr)
            equity_value *= (1 + dr)
            curve.append(equity_value)
            prev_basket = basket

        returns_s = pd.Series(daily_returns, index=trading_days)
        curve_s   = pd.Series(curve, index=equity_prices.index[window:])
        results[f"{window}-Day Momentum"] = {"returns": returns_s, "curve": curve_s}

    bench_rets = []
    bench_days = equity_prices.index[max(MOMENTUM_WINDOWS) + 1:]
    ret_df     = equity_prices.pct_change()
    for day in bench_days:
        valid = ret_df.loc[day].dropna()
        bench_rets.append(valid.mean() if len(valid) else 0.0)
    bench_s     = pd.Series(bench_rets, index=bench_days)
    bench_curve = (1 + bench_s).cumprod()
    results["Benchmark (Buy & Hold)"] = {"returns": bench_s, "curve": bench_curve}
    return results


def calc_metrics(returns, label):
    if returns.empty:
        return {"Strategy": label, "Return": None, "Vol": None, "Sharpe": None, "MaxDD": None}
    total  = (1 + returns).prod() - 1
    vol    = returns.std() * (252 ** 0.5)
    excess = returns - (RISK_FREE_RATE / 252)
    sharpe = excess.mean() / returns.std() * (252 ** 0.5) if returns.std() > 0 else None
    cum    = (1 + returns).cumprod()
    maxdd  = ((cum - cum.cummax()) / cum.cummax()).min()
    return {
        "Strategy": label,
        "Return":   f"{total*100:.1f}%",
        "Vol":      f"{vol*100:.1f}%",
        "Sharpe":   f"{sharpe:.3f}" if sharpe else "—",
        "MaxDD":    f"{maxdd*100:.1f}%",
    }


st.markdown("""
<div class="slc-header">
  <h1>⚛ Nuclear Infrastructure Screener</h1>
  <p>Second Layer Capital &nbsp;·&nbsp; picks-and-shovels, five domains, three-bucket NQS</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["NQS Scorecard", "Engine Backtester", "Universe Auditing"])

with tab1:
    nqs_df = load_nqs_scores()

    if nqs_df.empty:
        st.warning("NQS scores could not be loaded.")
    else:
        active  = nqs_df[nqs_df["NQS"] >= NQS_GATE]
        gated   = nqs_df[nqs_df["NQS"] < NQS_GATE]
        avg_nqs = nqs_df["NQS"].mean()

        c1, c2, c3, c4 = st.columns(4)
        tiles = [
            ("Active Names", len(active),              f"NQS >= {NQS_GATE}"),
            ("Gated Names",  len(gated),               f"NQS < {NQS_GATE}"),
            ("Avg NQS",      f"{avg_nqs:.1f}",         "universe average"),
            ("Top Score",    f"{nqs_df['NQS'].max():.0f}", nqs_df.loc[nqs_df['NQS'].idxmax(), 'Ticker']),
        ]
        for col, (label, value, sub) in zip([c1, c2, c3, c4], tiles):
            with col:
                st.markdown(f"""
                <div class="metric-tile">
                  <div class="label">{label}</div>
                  <div class="value">{value}</div>
                  <div class="sub">{sub}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-label">Full Universe — NQS Matrix</div>', unsafe_allow_html=True)

        rows_html = ""
        for domain_key, domain_label in DOMAIN_LABELS.items():
            domain_rows = nqs_df[nqs_df["_domain"] == domain_key]
            for _, row in domain_rows.sort_values("NQS", ascending=False).iterrows():
                gc = gate_class(row["NQS"], row["_domain"])
                gl = gate_label(row["NQS"], row["_domain"])
                rows_html += f"""
                <tr>
                  <td><strong>{row['Ticker']}</strong></td>
                  <td>{domain_label}</td>
                  <td>{fmt_score(row['NQS'])}</td>
                  <td>{fmt_bucket(row['Runway'])}</td>
                  <td>{fmt_bucket(row['Margin'])}</td>
                  <td>{fmt_bucket(row['Backlog'])}</td>
                  <td><span class="{gc}">{gl}</span></td>
                </tr>"""

        st.markdown(f"""
        <table class="nqs-table">
          <thead>
            <tr>
              <th>Ticker</th><th>Domain</th><th>NQS (0-100)</th>
              <th>Runway</th><th>Margin</th><th>Backlog</th><th>Gate</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>""", unsafe_allow_html=True)

        st.markdown(f"""
        <p style="font-size:0.70rem;color:#3a4a5a;margin-top:0.75rem;font-family:'IBM Plex Mono',monospace;">
        Gate threshold: NQS >= {NQS_GATE} &nbsp;·&nbsp;
        EXCEPTION layer: smr_pureplay bypasses gate by design &nbsp;·&nbsp;
        Backlog bucket: components_grid and epc domains only
        </p>""", unsafe_allow_html=True)
with tab2:
    with st.spinner("Running backtest engine..."):
        try:
            eq_prices, def_prices = load_prices()
            nqs_df_bt  = load_nqs_scores()
            bt_results = run_backtest_engine(eq_prices, def_prices, nqs_df_bt)

            st.markdown('<div class="section-label">Performance Matrix</div>', unsafe_allow_html=True)
            metrics_rows = [calc_metrics(v["returns"], k) for k, v in bt_results.items()]
            metrics_df   = pd.DataFrame(metrics_rows).set_index("Strategy")

            st.markdown(f"""
            <p style="font-size:0.72rem;color:#5a7090;font-family:'IBM Plex Mono',monospace;margin-bottom:0.5rem;">
            Risk controls: {int(DRAWDOWN_LIMIT*100)}% trailing stop-loss &nbsp;·&nbsp;
            {int(TAKE_PROFIT*100)}% take-profit &nbsp;·&nbsp;
            {SLIPPAGE*100:.2f}% slippage &nbsp;·&nbsp;
            Defensive: {DEFENSIVE}
            </p>""", unsafe_allow_html=True)

            st.dataframe(metrics_df, use_container_width=True)

            st.markdown('<div class="section-label">Cumulative Return — Interactive</div>', unsafe_allow_html=True)

            COLORS = {
                "14-Day Momentum":        "#4fc3f7",
                "60-Day Momentum":        "#e8b84b",
                "200-Day Momentum":       "#4caf82",
                "Benchmark (Buy & Hold)": "#5a7090",
            }

            fig = go.Figure()
            for label, data in bt_results.items():
                curve    = data["curve"]
                is_bench = label.startswith("Benchmark")
                fig.add_trace(go.Scatter(
                    x=curve.index,
                    y=curve.values,
                    name=label,
                    line=dict(
                        color=COLORS.get(label, "#ffffff"),
                        width=1.5 if is_bench else 2,
                        dash="dot" if is_bench else "solid",
                    ),
                    hovertemplate="<b>%{x|%b %d %Y}</b><br>Growth: $%{y:.3f}<extra>" + label + "</extra>",
                ))

            fig.update_layout(
                paper_bgcolor="#06090f",
                plot_bgcolor="#06090f",
                font=dict(family="IBM Plex Mono", color="#c8d0e0", size=11),
                xaxis=dict(
                    gridcolor="#111820", showgrid=True,
                    tickformat="%b '%y", tickangle=-30,
                    zeroline=False,
                ),
                yaxis=dict(
                    gridcolor="#111820", showgrid=True,
                    title="Growth of $1.00",
                    zeroline=False,
                ),
                legend=dict(
                    bgcolor="#0c1220", bordercolor="#1e2a3a", borderwidth=1,
                    font=dict(size=11),
                ),
                hovermode="x unified",
                margin=dict(l=20, r=20, t=20, b=20),
                height=480,
            )

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Backtest failed: {e}")
            st.exception(e)


with tab3:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown('<div class="section-label">Live Price Tracker</div>', unsafe_allow_html=True)
        with st.spinner("Fetching quotes..."):
            try:
                quotes_df = load_live_quotes()
                nqs_map   = dict(zip(nqs_df["Ticker"], nqs_df["NQS"])) if not nqs_df.empty else {}
                quotes_df["NQS"]  = quotes_df["Ticker"].map(nqs_map)
                quotes_df["Gate"] = quotes_df["NQS"].apply(
                    lambda v: "ACTIVE" if v and v >= NQS_GATE else ("GATED" if v else "—")
                )
                st.dataframe(quotes_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Quote fetch failed: {e}")

    with col_right:
        st.markdown('<div class="section-label">Backlog Overrides — manual_overrides.json</div>',
                    unsafe_allow_html=True)
        overrides     = load_overrides()
        override_rows = []
        for ticker in ["BWXT", "GEV", "FLS", "IR", "J", "FLR"]:
            entry = overrides.get(ticker, {})
            override_rows.append({
                "Ticker":      ticker,
                "BTB":         entry.get("book_to_bill"),
                "Backlog YoY": f"{entry.get('backlog_growth_yoy', 0)*100:.1f}%"
                               if entry.get("backlog_growth_yoy") is not None else "—",
                "Updated":     entry.get("last_updated", "—"),
            })
        st.dataframe(pd.DataFrame(override_rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label">Watchlist — Promotion Criteria</div>', unsafe_allow_html=True)
    watchlist_data = {
        "NNE":  "Containerized microreactor, defense/remote industrial focus. Promote on: first commercial contract or NRC licensing milestone.",
        "NXE":  "Earlier-stage uranium developer. Promote on: supply tightening re-rating or production commencement.",
        "URG":  "Earlier-stage uranium developer. Promote on: supply tightening re-rating.",
        "EU":   "Earlier-stage uranium developer. Promote on: supply tightening re-rating.",
        "ISOU": "Earlier-stage uranium developer. Promote on: supply tightening re-rating.",
    }
    for ticker, note in watchlist_data.items():
        st.markdown(f"""
        <div style="background:#0c1220;border:1px solid #1e2a3a;border-radius:4px;
                    padding:0.6rem 0.85rem;margin-bottom:0.4rem;font-size:0.78rem;">
          <span style="color:#e8b84b;font-family:'IBM Plex Mono',monospace;font-weight:600;">
            {ticker}
          </span>
          <span style="color:#5a7090;margin-left:0.75rem;">{note}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <p style="font-size:0.68rem;color:#3a4a5a;margin-top:1rem;font-family:'IBM Plex Mono',monospace;">
    Last data pull: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;·&nbsp;
    NQS cache TTL: 1 hour &nbsp;·&nbsp; Price cache TTL: 1 hour
    </p>""", unsafe_allow_html=True)        