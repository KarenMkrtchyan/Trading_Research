"""Inject the verified dataset + events + findings into the page template."""
import json, sys
import pandas as pd
D, TEMPLATE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(f"{D}/dataset.json"))
G = d["tickers"]["GOOG"]; gs = G["stats"]
q = {r[0]: r for r in G["quarters"]}          # [end, rev, ni, oie, eps, core_eps, ttm, ttm_core, avail]
cash = {r[0]: r for r in G["cash"]}           # [end, capex, buybacks, ocf]
wk = pd.Series({pd.Timestamp(r[0]): r[1] for r in G["weekly"]})
pe = pd.Series({pd.Timestamp(r[0]): r[2] for r in G["weekly"]})

# cross-check with user-supplied sp500-pe-ratio.csv
c = pd.read_csv(f"{D}/sp500-pe-ratio.csv", parse_dates=["date"]).set_index("date").pe_ratio
s = pd.Series({pd.Timestamp(r[0][:7] + "-01"): r[1] for r in d["spx"]["monthly"]})
j = pd.concat([s, c], axis=1, keys=["mine", "csv"]).dropna()
d["log"].append(f"sp500-pe-ratio.csv vs Shiller-derived series: {len(j)} months since 2011, max diff {100*(j.mine/j.csv-1).abs().max():.3f}% "
                f"-> same underlying Shiller data (not independent); its Oct/Nov 2026 rows also hold E at 295.52")

def wchg(a, b):
    return wk.asof(pd.Timestamp(b)) / wk.asof(pd.Timestamp(a)) - 1
peak18 = pe["2018-02-01":"2018-04-30"]
q3drop = wchg("2026-10-23", "2026-10-30")
sep25 = wchg("2025-08-29", "2025-09-05")

E = lambda n, date, title, detail, status, check: dict(n=n, date=date, title=title, detail=detail, status=status, check=check)
d["events"] = [
    E(1, "2012-05-22", "Motorola Mobility acquisition closes ($12.5B)", "Google completes its largest acquisition.", "pub", "Public record; not testable from price or filing data here."),
    E(2, "2015-08-10", "Alphabet holding-company structure announced", "Google reorganizes under Alphabet. SEC data for the next three quarters reports EPS by share class only, so EPS for those quarters is net income ÷ interpolated diluted shares.", "pub", "Public record. Data note: Q2–Q4 2015 EPS filled from net income ÷ shares."),
    E(3, "2017-06-27", "EU fines Google €2.42B (Shopping)", "First of three EU antitrust fines; the charge lands in Q2 2017 net income ($3.52B, down from $5.43B in Q1).", "ok", f"Q2'17 net income $3.52B in SEC data."),
    E(4, "2018-02-01", "Q4'17 results: one-time US tax-reform charge", f"Quarterly net income turns negative (−${-q['2017-12-31'][2]:.2f}B), trailing EPS collapses, P/E spikes to {peak18.max():.0f}x.", "ok", f"SEC: Q4'17 net income −${-q['2017-12-31'][2]:.2f}B; weekly P/E peak {peak18.max():.1f}x (chart said ~64x)."),
    E(5, "2018-07-18", "EU fines Google €4.34B (Android)", f"Q2'18 net income drops to ${q['2018-06-30'][2]:.2f}B.", "ok", f"SEC: Q2'18 net income ${q['2018-06-30'][2]:.2f}B (chart said $3.2B)."),
    E(6, "2019-03-20", "EU fines Google €1.49B (AdSense)", "Third EU antitrust fine.", "pub", "Public record. (An EU court later annulled this fine; a court adviser recommended revisiting it in Nov 2026.)"),
    E(7, "2020-03-16", "COVID crash", "Market-wide multiple compression.", "pub", "Public record; visible in the S&P 500 and GOOG lines."),
    E(8, "2022-02-01", "20-for-1 stock split announced", "Effective July 2022. All prices and EPS here are split-adjusted.", "pub", "Public record; split factors applied by filing date."),
    E(9, "2022-03-16", "Fed starts hiking rates", "Growth multiples reset across tech.", "pub", "Public record."),
    E(10, "2022-11-30", "ChatGPT launches", "AI-disruption fears for Search begin.", "pub", "Public record."),
    E(11, "2023-02-08", "Bard demo error", "GOOG falls 7.4% in a day ($108.03 → $100.02).", "fix", "Alpaca daily bars: GOOG −7.4%. The chart's ~7.7% is the GOOGL share class."),
    E(12, "2024-08-05", "US court rules Google's search business is an illegal monopoly", "Antitrust liability ruling in US v. Google.", "pub", "Public record."),
    E(13, "2025-04-02", "US tariff announcements trigger a market sell-off", "GOOG trades near $148 in the following days.", "pub", "Public record; low visible in weekly prices."),
    E(14, "2025-09-02", "Search remedies ruling: no Chrome divestiture ordered", f"GOOG rises {100*sep25:.0f}% that week.", "ok", f"Weekly closes: {100*sep25:+.1f}% for the week of the ruling."),
    E(15, "2026-07-23", "Q2'26 results: huge non-operating gains", f"Net income ${q['2026-06-30'][2]:.1f}B including ${q['2026-06-30'][3]:.1f}B of non-operating income (Q1'26: ${q['2026-03-31'][3]:.1f}B). Trailing EPS jumps and the P/E compresses.", "ok", f"SEC: Q2'26 net income ${q['2026-06-30'][2]:.2f}B, non-operating ${q['2026-06-30'][3]:.2f}B; Q1'26 ${q['2026-03-31'][3]:.2f}B. Matches the chart."),
    E(16, "2026-10-28", "Q3'26 results: miss, capex surge, buybacks stay at zero", f"Revenue ${q['2026-09-30'][1]:.1f}B, net income ${q['2026-09-30'][2]:.1f}B with a ${-q['2026-09-30'][3]:.1f}B non-operating loss; capex ${cash['2026-09-30'][1]:.1f}B. GOOG falls {100*-q3drop:.0f}% that week.", "new", "SEC figures verified. Also confirmed in review: CNBC (LSEG consensus) reports adjusted EPS $2.67 vs $3.02 expected and revenue $127.58B vs $128.22B, Alphabet's first top-and-bottom-line miss in nearly four years; the ~$41B financing is $29.0B of debt plus $12.4B of stock issued in Q3 (Q3 release cash flow statement)."),
]

core_pe, pe_now = gs["core_pe"], gs["pe"]
ttm_oie = sum(q[k][3] for k in list(q)[-4:]); ttm_ni = sum(q[k][2] for k in list(q)[-4:])
capex_now, capex_yr = cash["2026-09-30"][1], cash["2025-09-30"][1]
bb_yr = cash["2025-09-30"][2]
spx_now = d["spx"]["extension"][-1][1]
T = d["tickers"]
def st(t): return T[t]["stats"]
d["findings"] = [
    dict(hi=True, title=f"The {pe_now:.0f}x P/E is mostly an accounting effect",
         body=f"Over the last four quarters Alphabet booked ${ttm_ni:.0f}B of net income, and ${ttm_oie:.0f}B of that ({100*ttm_oie/ttm_ni:.0f}%) was non-operating income, almost all of it in Q1 and Q2 2026. "
              f"Those gains don't recur the way ad and cloud revenue does. Removing them after tax puts GOOG at about {core_pe:.0f}x earnings, not {pe_now:.0f}x. The original chart's 14.2x is arithmetically right but answers a different question."),
    dict(hi=False, title="Excluding one-offs, GOOG is cheap for GOOG but priced about like the market",
         body=f"{core_pe:.1f}x sits at the {100*st('GOOG')['core_pct']:.0f}th percentile of GOOG's own history since 2011 (median {st('GOOG')['core_med']:.1f}x). "
              f"The S&P 500 is near {spx_now:.1f}x on the latest earnings. You pay roughly a market multiple for revenue growing {100*st('GOOG')['rev_yoy']:.0f}% a year. That gap is the case for cheapness; the next point is the case against."),
    dict(hi=True, title="What the market is pricing in: the capex bill",
         body=f"Capex was ${capex_now:.1f}B in Q3 2026, up from ${capex_yr:.1f}B a year earlier. Buybacks went from ${bb_yr:.1f}B a quarter to zero for three straight quarters, and diluted shares rose from 12.20B to 12.37B (Alphabet's reported diluted weighted-average count). "
              f"Trailing free cash flow fell from ${st('GOOG')['ttm_fcf_prev']:.0f}B to ${st('GOOG')['ttm_fcf']:.0f}B. On cash flow, GOOG now trades at far more than its P/E suggests. The stock fell {100*-q3drop:.0f}% in the week of the Q3 report."),
    dict(hi=False, title="The tech sell-off is uneven",
         body=f"Off 52-week highs: NVDA {100*st('NVDA')['off_high']:.0f}%, GOOG {100*st('GOOG')['off_high']:.0f}%, META {100*st('META')['off_high']:.0f}%, AMZN {100*st('AMZN')['off_high']:.0f}%, MSFT {100*st('MSFT')['off_high']:.0f}%, while AAPL is at its high and the {100*st('AAPL')['pe_pct']:.0f}th percentile of its own P/E history. "
              f"Amazon's {st('AMZN')['pe']:.0f}x reported P/E is flattered by non-operating gains just like Alphabet's ({st('AMZN')['core_pe']:.0f}x without them), and its trailing free cash flow is negative. Nvidia's figure uses EPS through July because its October-quarter 10-Q wasn't in the SEC data yet."),
    dict(hi=False, title="Questions that decide whether the dip is an opportunity",
         body="Will the data-centre spending earn its return, as Cloud growth and margins should show over the next few quarters? Does free cash flow recover once capex levels off, or does financing keep replacing buybacks? "
              "Treat the non-operating gains as zero when valuing it. These are quarterly checkpoints you can track against the core P/E line here, and they fit a 2–4 year horizon better than a swing trade."),
]
d["method"] = [
    "Earnings: SEC XBRL company facts (10-Q/10-K) for Google Inc. (2009–2015) and Alphabet Inc. (2015–), plus MSFT, AAPL, AMZN, META, NVDA. Values as first reported; Q4 derived as fiscal year minus Q1–Q3; EPS put on today's share basis by filing date.",
    "Trailing P/E steps on the date each quarter's filing reached the SEC, so the line only uses information public at the time.",
    "'Excluding one-offs' removes the 'other income (expense), net' line (non-operating) after tax at 35% before 2018 and 21% after. It's an approximation: real tax effects differ by item.",
    "Prices: Webull weekly closes, converted back from dividend-adjusted to split-only using SEC dividends per share; checked against Alpaca split-only month-end closes since Aug 2020 (median error ≤0.1% for every ticker).",
    "S&P 500: Robert Shiller's ie_data.xls (monthly average price ÷ trailing as-reported EPS), with earnings through Sep 2026. Cross-checked against S&P Dow Jones Indices' own aggregates (within ±7%, typically ±2–3%) and daily closes (exact). After Sep 2026 the line holds earnings flat and is drawn dotted.",
    "Changed from the original chart: no dual y-axis (revenue and P/E sit in separate panels on one time axis); real S&P 500 earnings through Sep 2026 replace interpolated estimates; the Bard-day drop is corrected for the GOOG share class; Q3 2026 and the capex shift are added.",
]
html = open(TEMPLATE, encoding="utf-8").read().replace("__DATA__", json.dumps(d, separators=(",", ":")).replace("</", "<\\/"))
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, len(html) // 1024, "KB")
for f in d["findings"]: print("-", f["title"], "|", f["body"][:160])
