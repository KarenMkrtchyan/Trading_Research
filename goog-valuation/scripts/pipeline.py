"""Verified trailing-P/E dataset: GOOG + big-tech peers + S&P 500 baseline.

Sources
  - SEC XBRL companyfacts (10-Q/10-K): revenue, net income, diluted EPS, non-operating income
  - Webull weekly bars (split-adjusted closes)
  - Shiller ie_data.xls (S&P 500 monthly price P and trailing as-reported EPS E)
  - S&P DJI sp-500-buyback.xlsx (quarterly market value + as-reported earnings) -> cross-check
  - S&P DJI PerformanceGraphExport.xls (daily S&P 500 closes, last 12 months) -> cross-check / extension
"""
import json, sys
import pandas as pd
import numpy as np

D = sys.argv[1]
OUT = sys.argv[2]

TICKERS = {
    "GOOG": (["google_facts.json", "alphabet_facts.json"], [("2014-04-03", 2), ("2022-07-18", 20)]),
    "MSFT": (["MSFT_facts.json"], []),
    "AAPL": (["AAPL_facts.json"], [("2014-06-09", 7), ("2020-08-31", 4)]),
    "AMZN": (["AMZN_facts.json"], [("2022-06-06", 20)]),
    "META": (["META_facts.json"], []),
    "NVDA": (["NVDA_facts.json"], [("2021-07-20", 4), ("2024-06-10", 10)]),
}
REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
       "RevenueFromContractWithCustomerIncludingAssessedTax"]
OIE = ["NonoperatingIncomeExpense", "OtherNonoperatingIncomeExpense"]
FORMS = {"10-Q", "10-K", "10-K/A", "10-Q/A", "10-KT"}
log = []
def note(s):
    print(s); log.append(s)

_cache = {}
def facts(fn):
    if fn not in _cache:
        _cache[fn] = json.load(open(f"{D}/{fn}"))["facts"]["us-gaap"]
    return _cache[fn]

def raw(files, concepts):
    out = []
    for fn in files:
        g = facts(fn)
        for pri, c in enumerate(concepts):
            if c not in g: continue
            for u, vals in g[c]["units"].items():
                for x in vals:
                    if "start" not in x or x["form"] not in FORMS: continue
                    s, e = pd.Timestamp(x["start"]), pd.Timestamp(x["end"])
                    out.append(dict(start=s, end=e, days=(e - s).days, val=x["val"],
                                    filed=pd.Timestamp(x["filed"]), pri=pri))
    return pd.DataFrame(out)

def quarterly(files, concepts, splits=(), per_share=False):
    df = raw(files, concepts)
    if df.empty: return pd.DataFrame(columns=["val", "first_filed"])
    if per_share:
        sp = [(pd.Timestamp(d), k) for d, k in splits]
        df["val"] = [v / np.prod([k for t, k in sp if f < t] or [1.0]) for v, f in zip(df.val, df.filed)]
    first = df.groupby(["start", "end"]).filed.min().rename("first_filed")
    # as FIRST reported (what investors knew at the time; keeps annual & quarterly values from the same era)
    df = df.sort_values(["filed", "pri"], ascending=[False, False]).groupby(["start", "end"]).last()
    df = df.join(first).reset_index()
    q = df[df.days.between(80, 100)]
    ann = df[df.days.between(350, 380)]
    have = set(q.end)
    derived = []
    for _, a in ann.iterrows():
        if a.end in have: continue
        prior = q[(q.start >= a.start - pd.Timedelta(days=7)) & (q.end < a.end)].drop_duplicates("end")
        if len(prior) == 3:
            v = a.val - prior.val.sum()
            if a.val > 0 and abs(a.val) > 1e6 and not (0.12 < v / a.val < 0.45):
                note(f"{files[-1]} {concepts[0]}: derived Q4 {a.end.date()} = {v/a.val:.0%} of FY (check)")
            derived.append(dict(end=a.end, val=v, first_filed=a.first_filed))
    q = pd.concat([q[["end", "val", "first_filed"]], pd.DataFrame(derived)])
    return q.sort_values("end").drop_duplicates("end", keep="last").set_index("end")

def ytd_quarterly(files, concepts, splits=(), per_share=False):
    """Cash-flow style facts are reported year-to-date; difference them into quarters."""
    df = raw(files, concepts)
    if df.empty: return pd.Series(dtype=float)
    if per_share:
        sp = [(pd.Timestamp(d), k) for d, k in splits]
        df["val"] = [v / np.prod([k for t, k in sp if f < t] or [1.0]) for v, f in zip(df.val, df.filed)]
    df = df.sort_values(["filed", "pri"], ascending=[True, False]).groupby(["start", "end"]).last().reset_index()
    df = df[df.days.between(80, 380)]
    out = {}
    for s, g in df.groupby("start"):
        g = g.sort_values("end"); prev = 0.0; prev_end = s - pd.Timedelta(days=1)
        for _, r in g.iterrows():
            n = round(r.days / 91)
            if n < 1 or n > 4: continue
            if (r.end - prev_end).days < 80: continue
            out.setdefault(r.end, r.val - prev); prev = r.val; prev_end = r.end
    return pd.Series(out).sort_index()

def unadjust(t, px, files, splits):
    """Webull closes are back-adjusted for dividends; undo that using SEC dividends/share."""
    dps = ytd_quarterly(files, ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
                        splits, per_share=True)
    if dps.empty: return px.copy(), dps
    dps = dps[(dps > 0) & (dps.index >= "2010-01-01")]
    factor = pd.Series(1.0, index=px.index)
    for q, d in dps.items():
        i = px.index.searchsorted(q)  # ex-date approximated by quarter end
        if i >= len(px): continue
        factor.iloc[:i] *= (1 - d / px.iloc[i])
    return px / factor, dps

def build(t):
    files, splits = TICKERS[t]
    rev, ni = quarterly(files, REV), quarterly(files, ["NetIncomeLoss"])
    eps = quarterly(files, ["EarningsPerShareDiluted"], splits, per_share=True)
    oie = quarterly(files, OIE)
    f = pd.DataFrame({"revenue": rev.val, "net_income": ni.val, "eps": eps.val, "oie": oie.val,
                      "avail": ni.first_filed})
    f = f[f.index >= "2009-06-30"]
    f["capex"] = ytd_quarterly(files, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"])
    f["buybacks"] = ytd_quarterly(files, ["PaymentsForRepurchaseOfCommonStock"])
    f["ocf"] = ytd_quarterly(files, ["NetCashProvidedByUsedInOperatingActivities"])
    # gaps: fill EPS = NI / implied diluted shares (interpolated through time)
    shares = (f.net_income / f.eps).where(f.eps.abs() > 0.005)
    shares = shares.interpolate(method="time", limit_direction="both")
    miss = f.eps.isna() & f.net_income.notna()
    if miss.any():
        note(f"{t}: EPS missing in SEC data for {[d.strftime('%Y-%m-%d') for d in f.index[miss]]} -> filled as NI / interpolated diluted shares")
    f.loc[miss, "eps"] = f.net_income[miss] / shares[miss]
    f["shares"] = shares
    # quarter-gap check
    gaps = f.index.to_series().diff().dt.days
    for d, g in gaps[gaps > 100].items():
        note(f"{t}: missing quarter before {d.date()} (gap {g}d)")
    tax = np.where(f.index < "2018-01-01", 0.35, 0.21)
    f["core_eps"] = (f.net_income - f.oie.fillna(0) * (1 - tax)) / f.shares
    f["ttm_eps"] = f.eps.rolling(4).sum()
    f["ttm_core_eps"] = f.core_eps.rolling(4).sum()
    f["ttm_rev"] = f.revenue.rolling(4).sum()
    f["ttm_ni"] = f.net_income.rolling(4).sum()
    f["ttm_oie"] = f.oie.rolling(4).sum()
    # availability: if the 10-Q date is missing use quarter end + 35d
    f["avail"] = f.avail.fillna(f.index.to_series() + pd.Timedelta(days=35))
    return f

def prices(t):
    j = json.load(open(f"{D}/{t}_weekly.json"))
    s = pd.Series({pd.Timestamp(x["time"][:10]): float(x["close"]) for x in j}).sort_index()
    # repair split-adjustment glitches: a ~2x jump up that later reverses with a ~0.5x jump down
    r = s / s.shift(1)
    ups = list(r[(r > 1.8) & (r < 2.2)].index); downs = list(r[(r > 0.45) & (r < 0.55)].index)
    for u in ups:
        dn = [x for x in downs if x > u]
        if dn:
            seg = (s.index >= u) & (s.index < dn[0])
            note(f"{t}: Webull closes {u.date()}..{dn[0].date()} are 2x too high (unadjusted for the 2014 class-C split: "
                 f"jump x{r[u]:.2f} in, x{r[dn[0]]:.2f} out) -> divided by 2")
            s[seg] = s[seg] / 2
    return s

def weekly_pe(t, f, px):
    f2 = f.dropna(subset=["ttm_eps"]).sort_values("avail")
    idx = f2.avail.searchsorted(px.index, side="right") - 1
    rows = []
    for d, p, i in zip(px.index, px.values, idx):
        if i < 0: continue
        r = f2.iloc[i]
        pe = p / r.ttm_eps if r.ttm_eps > 0 else None
        cpe = p / r.ttm_core_eps if r.ttm_core_eps > 0 else None
        rows.append(dict(date=d, close=p, pe=pe, core_pe=cpe, ttm_eps=r.ttm_eps, q=f2.index[i]))
    return pd.DataFrame(rows).set_index("date")

ALP = json.load(open(f"{D}/alpaca_monthly.json"))["data"]["bars"]
result = {"tickers": {}, "log": log}
for t in TICKERS:
    f = build(t)
    px_adj = prices(t)
    px, dps = unadjust(t, px_adj, *TICKERS[t])
    # validate un-adjusted closes against Alpaca split-only monthly closes (IEX)
    al = pd.Series({pd.Timestamp(b["t"][:10]): b["c"] for b in ALP.get(t, [])})
    errs = []
    for m, c in al.items():
        me = m + pd.offsets.MonthEnd(0)
        wk = px[(px.index <= me + pd.Timedelta(days=3)) & (px.index > me - pd.Timedelta(days=4))]
        wa = px_adj[(px_adj.index <= me + pd.Timedelta(days=3)) & (px_adj.index > me - pd.Timedelta(days=4))]
        if len(wk) and me < px.index[-1] - pd.Timedelta(days=7):
            errs.append((wk.iloc[-1] / c - 1, wa.iloc[-1] / c - 1))
    if errs:
        e = np.array(errs)
        note(f"{t}: vs Alpaca split-only month-end closes since 2020-08 (n={len(e)}): "
             f"un-adjusted median err {100*np.median(e[:,0]):+.2f}% (max |{100*np.abs(e[:,0]).max():.1f}|%), "
             f"Webull raw median err {100*np.median(e[:,1]):+.2f}%; dividends used: {len(dps)} quarters")
    w = weekly_pe(t, f, px)
    w = w[w.index >= "2011-01-01"]
    last = w.iloc[-1]
    hi = px[px.index >= px.index[-1] - pd.Timedelta(days=365)].max()
    note(f"{t}: last close {last.close:.2f} ({w.index[-1].date()}), TTM EPS {last.ttm_eps:.2f} (thru {last.q.date()}), "
         f"P/E {last.pe:.1f}x, core P/E {last.core_pe:.1f}x, off 52w-high {100*(last.close/hi-1):.1f}%")
    result["tickers"][t] = {
        "weekly": [[d.strftime("%Y-%m-%d"), round(r.close, 2),
                    None if r.pe is None or pd.isna(r.pe) else round(r.pe, 2),
                    None if r.core_pe is None or pd.isna(r.core_pe) else round(r.core_pe, 2)] for d, r in w.iterrows()],
        "quarters": [[d.strftime("%Y-%m-%d"), *(None if pd.isna(v) else round(float(v), 4) for v in
                      (r.revenue / 1e9, r.net_income / 1e9, r.oie / 1e9, r.eps, r.core_eps, r.ttm_eps, r.ttm_core_eps)),
                      r.avail.strftime("%Y-%m-%d")] for d, r in f[f.index >= "2010-12-31"].iterrows()],
        "high52": hi,
        "cash": [[d.strftime("%Y-%m-%d"), *(None if pd.isna(v) else round(float(v) / 1e9, 3) for v in (r.capex, r.buybacks, r.ocf))]
                 for d, r in f[f.index >= "2019-12-31"].iterrows()],
    }
    pe_s, cpe_s = w.pe.dropna(), w.core_pe.dropna()
    result["tickers"][t]["stats"] = {
        "close": last.close, "date": w.index[-1].strftime("%Y-%m-%d"), "eps_thru": last.q.strftime("%Y-%m-%d"),
        "pe": last.pe, "core_pe": last.core_pe, "off_high": last.close / hi - 1,
        "pe_med": pe_s.median(), "core_med": cpe_s.median(),
        "pe_pct": (pe_s < last.pe).mean(), "core_pct": (cpe_s < last.core_pe).mean(),
        "rev_yoy": f.revenue.iloc[-1] / f.revenue.iloc[-5] - 1,
        "ttm_fcf": (f.ocf - f.capex).iloc[-4:].sum() / 1e9, "ttm_fcf_prev": (f.ocf - f.capex).iloc[-8:-4].sum() / 1e9,
    }
    s = result["tickers"][t]["stats"]
    note(f"{t}: P/E pct {100*s['pe_pct']:.0f} (median {s['pe_med']:.1f}x), core pct {100*s['core_pct']:.0f} (median {s['core_med']:.1f}x), "
         f"rev yoy {100*s['rev_yoy']:+.1f}%, TTM FCF {s['ttm_fcf']:.1f}B vs prior {s['ttm_fcf_prev']:.1f}B")
    if t == "GOOG":
        goog_f, goog_w = f, w

# ---------- S&P 500 ----------
sh = pd.read_excel(f"{D}/ie_data.xls", sheet_name="Data", header=None, skiprows=8)
sh = sh[[0, 1, 3]].rename(columns={0: "date", 1: "P", 3: "E"})
sh = sh[pd.to_numeric(sh.date, errors="coerce").notna()].copy()
sh["date"] = sh.date.astype(float).map(lambda x: pd.Timestamp(int(x), int(round((x % 1) * 100)), 15))
sh = sh.set_index("date").astype(float)
sh["pe"] = sh.P / sh.E
spx = sh[sh.index >= "2011-01-01"].dropna(subset=["pe"])
note(f"Shiller: earnings through {spx.index[-1]:%Y-%m}; last P/E {spx.pe.iloc[-1]:.2f}x (P {spx.P.iloc[-1]:.0f}, E {spx.E.iloc[-1]:.2f})")

# cross-check with S&P DJI aggregate data (market value / trailing-4Q as-reported earnings)
bb = pd.read_excel(f"{D}/sp-500-buyback.xlsx", sheet_name="TABLE", header=None)
bq = bb[pd.to_datetime(bb[0], errors="coerce").notna() & bb[0].apply(lambda v: isinstance(v, (pd.Timestamp,)) or hasattr(v, "year"))]
bq = bq[[0, 1, 3]].rename(columns={0: "q", 1: "mv", 3: "ar"})
bq["q"] = pd.to_datetime(bq.q); bq = bq.set_index("q").sort_index().astype(float)
bq["ttm"] = bq.ar.rolling(4).sum()
annual = bb[bb[0].astype(str).str.fullmatch(r"20\d\d")][[0, 1, 3]]
xc = []
for _, r in annual.iterrows():
    y = int(r[0]); d = pd.Timestamp(y, 12, 15)
    if d in sh.index:
        xc.append((f"{y}", r[1] / r[3], sh.loc[d, "pe"]))
for q, r in bq.dropna().iterrows():
    d = pd.Timestamp(q.year, q.month, 15)
    if d in sh.index: xc.append((q.strftime("%Y-%m"), r.mv / r.ttm, sh.loc[d, "pe"]))
r12 = bb[bb[0].astype(str).str.contains("12 Mo Sep,'25")]
if len(r12):
    xc.append(("12Mo Sep'25", float(r12.iloc[0, 1]) / float(r12.iloc[0, 3]), sh.loc[pd.Timestamp(2025, 9, 15), "pe"]))
for k, a, b in xc:
    note(f"S&P P/E cross-check {k}: S&P DJI aggregates {a:.2f}x vs Shiller {b:.2f}x (diff {100*(b/a-1):+.1f}%)")

# extend with daily closes since the last Shiller earnings month, E held flat (labelled as estimate)
pg = pd.read_excel(f"{D}/PerformanceGraphExport.xls", header=None, skiprows=7).dropna()
pg = pg.rename(columns={0: "d", 1: "px"}); pg["d"] = pd.to_datetime(pg.d); pg = pg.set_index("d").px.astype(float)
lastE = spx.E.iloc[-1]; lastE_m = spx.index[-1]
ext = pg[pg.index > lastE_m + pd.offsets.MonthEnd(0)].resample("W-FRI").last().dropna()
# cross-check Shiller monthly average price vs daily closes
for m in sh.index[(sh.index >= pg.index[0]) & sh.P.notna()]:
    mm = pg[(pg.index.year == m.year) & (pg.index.month == m.month)]
    if len(mm) > 10:
        note(f"S&P price check {m:%Y-%m}: Shiller avg {sh.loc[m,'P']:.1f} vs daily-close avg {mm.mean():.1f} ({100*(sh.loc[m,'P']/mm.mean()-1):+.2f}%)")
note(f"S&P extension: {len(ext)} weekly closes after {lastE_m:%Y-%m} using E={lastE:.2f} (held flat); last {ext.index[-1].date()} P/E {ext.iloc[-1]/lastE:.2f}x")
result["spx"] = {
    "monthly": [[d.strftime("%Y-%m-%d"), round(r.pe, 2), round(r.P, 1), round(r.E, 2)] for d, r in spx.iterrows()],
    "extension": [[d.strftime("%Y-%m-%d"), round(p / lastE, 2), round(p, 1)] for d, p in ext.items()],
    "crosscheck": [[k, round(a, 2), round(b, 2)] for k, a, b in xc],
}

# ---------- spot checks of the original chart's claims ----------
gq = goog_f
def q(d): return gq.loc[pd.Timestamp(d)]
note(f"Claim #4: Q4'17 NI {q('2017-12-31').net_income/1e9:.2f}B; peak weekly P/E Feb-Apr 2018 = "
     f"{goog_w.loc['2018-02-01':'2018-04-30'].pe.max():.1f}x")
note(f"Claim #5: Q2'18 NI {q('2018-06-30').net_income/1e9:.2f}B")
note(f"Claim #15: Q1'26 OI&E {q('2026-03-31').oie/1e9:.2f}B; Q2'26 NI {q('2026-06-30').net_income/1e9:.2f}B incl OI&E {q('2026-06-30').oie/1e9:.2f}B")
note(f"Latest bar: Q3'26 revenue {q('2026-09-30').revenue/1e9:.2f}B, NI {q('2026-09-30').net_income/1e9:.2f}B, OI&E {q('2026-09-30').oie/1e9:.2f}B")
note(f"GOOG TTM (thru Q3'26): revenue {gq.ttm_rev.iloc[-1]/1e9:.1f}B, NI {gq.ttm_ni.iloc[-1]/1e9:.1f}B, OI&E {gq.ttm_oie.iloc[-1]/1e9:.1f}B "
     f"({100*gq.ttm_oie.iloc[-1]/gq.ttm_ni.iloc[-1]:.0f}% of NI)")
# GOOG P/E percentile history
pe = goog_w.pe.dropna(); cpe = goog_w.core_pe.dropna()
note(f"GOOG GAAP P/E since 2011: median {pe.median():.1f}x, 10th pct {pe.quantile(.1):.1f}x; current {pe.iloc[-1]:.1f}x is at the {100*(pe<pe.iloc[-1]).mean():.0f}th percentile")
note(f"GOOG core P/E since 2011: median {cpe.median():.1f}x, 10th pct {cpe.quantile(.1):.1f}x; current {cpe.iloc[-1]:.1f}x is at the {100*(cpe<cpe.iloc[-1]).mean():.0f}th percentile")
gl = gq[gq.index >= "2024-09-30"]
for d, r in gl.iterrows():
    note(f"GOOG {d.date()}: capex {r.capex/1e9 if pd.notna(r.capex) else float('nan'):.1f}B, buybacks {r.buybacks/1e9 if pd.notna(r.buybacks) else float('nan'):.1f}B, diluted shares {r.shares/1e9:.2f}B")
for a, b in [("2026-05-01", "2026-11-30")]:
    seg = goog_w.loc[a:b]
    pk = seg.close.idxmax()
    note(f"GOOG drawdown: peak {seg.close.max():.2f} on {pk.date()} -> {seg.close.iloc[-1]:.2f} ({100*(seg.close.iloc[-1]/seg.close.max()-1):.1f}%)")

json.dump(result, open(OUT, "w"), default=str)
print("wrote", OUT)
