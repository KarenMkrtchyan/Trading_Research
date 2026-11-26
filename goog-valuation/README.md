# Is GOOG actually cheap?

**Live page:** https://karenmkrtchyan.github.io/Trading_Research/goog-valuation/

This rebuilds a widely shared chart ("Alphabet (GOOG): Revenue vs. Trailing P/E, with S&P 500 baseline and key events") from primary data, and checks every claim in it. It also adds five big-tech peers and a P/E that leaves out one-off gains. Data runs through the week of Nov 25, 2026. This is an analysis of valuation data, not investment advice.

![GOOG trailing P/E](goog-pe-chart.png)

## Findings

| Measure (Nov 25, 2026) | Value |
|---|---|
| GOOG P/E, reported GAAP | **14.1x**, lowest weekly reading since 2011 |
| GOOG P/E, excluding non-operating items | **25.2x**, 27th percentile of its history since 2011 (median 29.3x) |
| S&P 500 P/E | **~24.3x** (Shiller; earnings held at Sep 2026) |
| GOOG vs 52-week high | **−32%** |
| GOOG trailing free cash flow | **$19.7B**, down from $73.6B a year earlier |

1. **The 14x P/E is mostly an accounting effect.** $131B of $236B trailing net income (55%) is non-operating income ($37.7B in Q1'26, $98.0B in Q2'26). Without it, after tax, GOOG trades at about 25x.
2. **Excluding one-offs, GOOG is cheap relative to its own history, but priced about like the market**, with revenue growing +24.7% year over year.
3. **The sell-off tracks the capex bill.** Capex went from $24.0B in Q3'25 to $51.4B in Q3'26. Buybacks have been $0 for three quarters and diluted shares are rising. GOOG fell 12% in the week of the Q3'26 report.
4. **The tech sell-off is uneven.** NVDA −36%, GOOG −32%, META −19%, AMZN −11%, MSFT −8%, AAPL at its high. AMZN's reported P/E is also flattered by non-operating gains, and its trailing free cash flow is negative.

## Corrections to the original chart

- Bard demo day: GOOG fell 7.4% (the chart's 7.7% is the GOOGL share class).
- The S&P 500 baseline uses Shiller's actual earnings through Sep 2026 instead of estimates from mid-2023 on.
- The dual y-axis is replaced by stacked panels on one time axis.
- Q3 2026 is added (a non-operating loss, the capex surge, zero buybacks).
- Confirmed as published: the 14.2x P/E, Q4'17 net income −$3.02B (P/E peak 64.4x), Q2'18 $3.19B, Q2'26 $112.19B including $97.98B non-operating, Q3'26 revenue $127.58B.

## Data and method

- **Earnings:** SEC XBRL company facts (data.sec.gov), as first reported. Q4 is derived as FY − (Q1+Q2+Q3). EPS is split-adjusted by filing date. Trailing P/E steps forward on each filing date.
- **Excluding one-offs:** removes "other income (expense), net" after tax (35% before 2018, 21% after). This is an approximation.
- **Prices:** weekly closes from Webull, converted from dividend-adjusted to split-only using SEC dividends per share, and checked against Alpaca split-only closes (median error ≤0.1%). Webull's GOOG closes for Nov 2010 to Mar 2014 were 2× too high (missing the 2014 class-C split adjustment); this is detected and fixed in `pipeline.py`.
- **S&P 500:** Robert Shiller's `ie_data.xls`, cross-checked against S&P Dow Jones Indices aggregates (±2–7%) and daily closes.
- **Not verified:** that Q3'26 "missed estimates" and the ~$41B financing figure, which come from news headlines.

## Rebuild

```
python scripts/pipeline.py <raw_dir> data/dataset.json
python scripts/build_page.py data scripts/template.html index.html
```

`<raw_dir>` must contain the SEC company-facts JSON files (`alphabet_facts.json`, `google_facts.json`, `MSFT_facts.json`, …), the weekly price files (`<TICKER>_weekly.json`), `alpaca_monthly.json`, `ie_data.xls`, `sp-500-buyback.xlsx`, `PerformanceGraphExport.xls` and `sp500-pe-ratio.csv`. Those raw files aren't committed. `data/dataset.json` is the processed output the page is built from.
