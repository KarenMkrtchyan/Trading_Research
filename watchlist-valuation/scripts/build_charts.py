#!/usr/bin/env python3
"""Build watchlist P/E and revenue charts from Webull + SEC + StockAnalysis data.

NOTE: reads Webull exports and raw SEC/StockAnalysis files from the box that produced them
(paths below), so it documents the method but will not run elsewhere without those inputs.
The processed outputs are committed in ../data/ and the charts as SVG next to index.html.
"""
from __future__ import annotations

import json
import math
import csv
from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np

ASSETS = Path("/cursor/stores/user/grok-bot/agents/3bbcc3a4-5b29-4700-a4d5-7510bc6ec997/assets")
RAW = Path("/workspace/watchlist-charts/raw")
OUT = Path("/workspace/tr_build/out")
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

# Webull source files
Q_FILES = {
    "TSLA": "01M8CBP2FPZJXZ0M6K0681MJ70.txt",
    "ANT": "01M8CBP2XWANEA6WP97WQ9S7NY.txt",
    "ACMR": "01M8CBP3CRT7WY4Q4C341M5V8W.txt",
    "LRCX": "01M8CBP3XX09575V8Q45HVF4YW.txt",
    "GOOG": "01M8CBP4AT58H3AMCXRJF5YRGZ.txt",
    "LULU": "01M8CBP4JAEFKR57NW7130AX1D.txt",
    "WM": "01M8CBQ64T0PTYJ9BBXQXAM0N5.txt",
    "AVGO": "01M8CBQ6KF5BTPD0E57NJK2TCD.txt",
    "MU": "01M8CBQ6Z9C4J2WK0R5ZAS7WZC.txt",
    "FTNT": "01M8CBQ7D3F43Z15WFGR42678C.txt",
    "FSLR": "01M8CBQ7XHFGPT75XZ9EJFD7RP.txt",
    "MRVL": "01M8CBQ89BX28MGENKE975MRMB.txt",
    "TSM": "01M8CBQ8N28CV3SP7WJ46Z05FR.txt",
    "RBLX": "01M8CBQ8X11GDXEZBFCV5BYY1Y.txt",
}
A_FILES = {
    "TSLA": "01M8CBMPDMW2FMR4B0XRZTWWCZ.txt",
    "ANT": "01M8CBTRDD0TA0WNDJWHSN5241.txt",
    "ACMR": "01M8CBTRDC7CCBYXCRQ1EH67SQ.txt",
    "LRCX": "01M8CBTRDX1EZ4ND1749N6KHQW.txt",
    "GOOG": "01M8CBTRGVXCFAEA283KXYT8DV.txt",
    "LULU": "01M8CBTRN0911ZJWJKNWTSMP00.txt",
    "WM": "01M8CBTRXRS2442AFTQVYE7M74.txt",
    "AVGO": "01M8CBTS19SKQGDC77CSF31AJT.txt",
    "MU": "01M8CBTS1YESAAXXSQK24A5S03.txt",
    "FTNT": "01M8CBVRM4G170CE6VFGCYAYXM.txt",
    "FSLR": "01M8CBVRZ8TBJB7T0MXJNAQHAZ.txt",
    "MRVL": "01M8CBVSASXD00Q6FX274SRADC.txt",
    "TSM": "01M8CBVSNHTK7TWTXW1X0MT9FC.txt",
    "RBLX": "01M8CBVT3BD3JCNJCGHQMJDCT6.txt",
}
BARS_FILE = "01M8CBNTV10KADR1NBAEVKZDSN.txt"
SNAP_STOCKS = "01M8CBNQMCGKNW4S5QZ0EV0HMN.txt"
SNAP_ETFS = "01M8CBNRB7WFCB10AXHM87T578.txt"

COMPANIES = [
    "TSLA", "ANT", "ACMR", "LRCX", "GOOG", "LULU", "WM",
    "AVGO", "MU", "FTNT", "FSLR", "MRVL", "TSM", "RBLX",
]
ETFS = ["VOO", "QQQ", "SOXX", "VXUS"]
NAMES = {
    "TSLA": "Tesla",
    "ANT": "Anthropic",
    "ACMR": "ACM Research",
    "LRCX": "Lam Research",
    "GOOG": "Alphabet",
    "LULU": "lululemon",
    "WM": "Waste Management",
    "AVGO": "Broadcom",
    "MU": "Micron",
    "FTNT": "Fortinet",
    "FSLR": "First Solar",
    "MRVL": "Marvell",
    "TSM": "TSMC (ADR)",
    "RBLX": "Roblox",
    "VOO": "Vanguard S&P 500",
    "QQQ": "Invesco QQQ",
    "SOXX": "iShares Semiconductor",
    "VXUS": "Vanguard Total Intl",
}
# Official TSMC ADR ratio
TSM_ADR_RATIO = 5

# StockAnalysis forward/trailing (scraped 2026-11-26)
SA_PE = {
    # stocks: trailing used only as a cross-check; primary trailing from Webull
    "TSLA": {"trailing": 417.65, "forward": 178.25, "eps": 0.91},
    "GOOG": {"trailing": 14.15, "forward": 19.27, "eps": 19.15},
    "MU": {"trailing": 8.09, "forward": 3.43, "eps": 74.33},
    "TSM": {"trailing": 23.18, "forward": 16.57, "eps": 14.77},
    "ANT": {"trailing": None, "forward": 225.96, "eps": -59.74},
    "ACMR": {"trailing": 24.87, "forward": 15.50, "eps": 1.62},
    "LRCX": {"trailing": 27.57, "forward": 17.99, "eps": 6.71},
    "LULU": {"trailing": 8.79, "forward": 12.79, "eps": 12.22},
    "WM": {"trailing": 32.46, "forward": 28.80, "eps": 7.62},
    "AVGO": {"trailing": 38.40, "forward": 17.31, "eps": 7.83},
    "FTNT": {"trailing": 44.09, "forward": 35.91, "eps": 3.06},
    "FSLR": {"trailing": 8.55, "forward": 6.90, "eps": 17.29},
    "MRVL": {"trailing": 43.99, "forward": 23.21, "eps": 2.98},
    "RBLX": {"trailing": None, "forward": None, "eps": -1.36},
    "VOO": {"trailing": 21.55, "forward": 16.86, "eps": None},
    "QQQ": {"trailing": 24.04, "forward": 17.64, "eps": None},
    "SOXX": {"trailing": 22.28, "forward": 12.89, "eps": None},
    "VXUS": {"trailing": 14.02, "forward": 10.80, "eps": None},
}

SEC_CIK = {
    "TSLA": "0001318605", "ANT": "0002130357", "ACMR": "0001680062",
    "LRCX": "0000707549", "GOOG": "0001652044", "LULU": "0001397187",
    "WM": "0000823768", "AVGO": "0001730168", "MU": "0000723125",
    "FTNT": "0001262039", "FSLR": "0001274494", "MRVL": "0001835632",
    "TSM": "0001046179", "RBLX": "0001315098",
}

REV_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
    "Revenue",
]


def load_json_file(path: Path):
    raw = Path(path).read_text()
    dec = json.JSONDecoder()
    for i, c in enumerate(raw):
        if c in "[{":
            try:
                obj, _ = dec.raw_decode(raw[i:])
                return obj
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no json in {path}")


def fnum(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_date(s):
    if not s:
        return None
    s = str(s)[:10]
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_fx_twd_per_usd():
    d = json.loads((RAW / "yahoo_twd.json").read_text())
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    close = res["indicators"]["quote"][0]["close"]
    pts = []
    for t, c in zip(ts, close):
        if c is None:
            continue
        dt = datetime.fromtimestamp(t, tz=timezone.utc).date()
        pts.append((dt, float(c)))
    pts.sort()
    return pts


def fx_on_or_before(fx_pts, d: date) -> float:
    """TWD per 1 USD on or before d; fallback to nearest."""
    prev = None
    for dt, val in fx_pts:
        if dt <= d:
            prev = val
        else:
            break
    if prev is not None:
        return prev
    return fx_pts[0][1]


# ---------- load webull ----------
def load_income(files):
    out = {}
    for sym, fn in files.items():
        rows = load_json_file(ASSETS / fn)
        if not isinstance(rows, list):
            raise TypeError(sym)
        clean = []
        for r in rows:
            rec = dict(r)
            rec["end"] = parse_date(r.get("end_date"))
            rec["published"] = parse_date(r.get("publish_date")) or rec["end"]
            rec["revenue"] = fnum(r.get("total_revenue") or r.get("revenue"))
            rec["eps"] = fnum(r.get("diluted_eps_incl_extra") or r.get("diluted_eps_excl_extra"))
            rec["ni"] = fnum(r.get("net_income") or r.get("ni_common_incl_extra"))
            rec["shares"] = fnum(r.get("diluted_avg_shares"))
            rec["currency"] = r.get("currency") or "USD"
            rec["fy"] = r.get("fiscal_year")
            rec["fp"] = r.get("fiscal_period")
            clean.append(rec)
        clean.sort(key=lambda x: (x["end"] or date.min, x["fp"] or 0))
        out[sym] = clean
    return out


def load_bars():
    data = load_json_file(ASSETS / BARS_FILE)
    out = {}
    for item in data["result"]:
        sym = item["symbol"]
        series = []
        for b in item.get("result") or []:
            t = parse_date(b["time"])
            series.append({"date": t, "close": fnum(b["close"])})
        series.sort(key=lambda x: x["date"])
        out[sym] = series
    return out


def load_snapshots():
    out = {}
    for fn in (SNAP_STOCKS, SNAP_ETFS):
        for s in load_json_file(ASSETS / fn):
            out[s["symbol"]] = {
                "price": fnum(s.get("price") or s.get("close")),
                "pe_ratio": fnum(s.get("pe_ratio")),
                "eps": fnum(s.get("eps")),
                "eps_ttm": fnum(s.get("eps_ttm")),
                "ps_ratio": fnum(s.get("ps_ratio")),
                "pb_ratio": fnum(s.get("pb_ratio")),
                "market_value": fnum(s.get("market_value")),
                "total_shares": fnum(s.get("total_shares")),
                "out_standing_shares": fnum(s.get("out_standing_shares")),
            }
    return out


def convert_tsm_quarters(quarters, fx_pts):
    """Add USD revenue and USD ADR EPS to TSM quarterly rows."""
    out = []
    for r in quarters:
        rec = dict(r)
        fx = fx_on_or_before(fx_pts, rec["end"])
        rec["fx_twd_per_usd"] = fx
        if rec["currency"] == "TWD":
            rec["revenue_usd"] = rec["revenue"] / fx if rec["revenue"] is not None else None
            # ADR EPS in USD: common-share TWD EPS * 5 / FX
            if rec["eps"] is not None:
                rec["eps_usd_adr"] = rec["eps"] * TSM_ADR_RATIO / fx
            else:
                rec["eps_usd_adr"] = None
        else:
            rec["revenue_usd"] = rec["revenue"]
            rec["eps_usd_adr"] = rec["eps"]
        out.append(rec)
    return out


def convert_tsm_annual(annual, fx_pts):
    out = []
    for r in annual:
        rec = dict(r)
        fx = fx_on_or_before(fx_pts, rec["end"])
        rec["fx_twd_per_usd"] = fx
        if rec["currency"] == "TWD" and rec["revenue"] is not None:
            rec["revenue_usd"] = rec["revenue"] / fx
        else:
            rec["revenue_usd"] = rec["revenue"]
        out.append(rec)
    return out


def ttm_from_quarters(quarters, asof: date, value_key: str, min_n=4):
    """Sum of the 4 most recently published quarters as of asof (by publish date, end <= asof)."""
    avail = [q for q in quarters if q["end"] and q["end"] <= asof and q.get("published") and q["published"] <= asof]
    # if publish is missing or equal end, still use end <= asof
    if not avail:
        avail = [q for q in quarters if q["end"] and q["end"] <= asof]
    avail = [q for q in avail if q.get(value_key) is not None]
    if len(avail) < min_n:
        return None, avail[-len(avail):] if avail else []
    last4 = avail[-4:]
    return sum(q[value_key] for q in last4), last4


def pe_history(sym, quarters, bars, value_key="eps"):
    """Monthly trailing P/E using TTM diluted EPS known at that month-end."""
    rows = []
    for b in bars:
        ttm, used = ttm_from_quarters(quarters, b["date"], value_key, min_n=4)
        pe = None
        status = "ok"
        if ttm is None:
            status = "insufficient"
        elif ttm <= 0:
            status = "N/M"
        elif b["close"] is None:
            status = "no price"
        else:
            pe = b["close"] / ttm
        rows.append({
            "date": b["date"],
            "close": b["close"],
            "ttm_eps": ttm,
            "pe": pe,
            "status": status,
        })
    return rows


def sec_fy_revenues(sym):
    path = RAW / f"sec_facts_{sym}.json"
    if not path.exists():
        return []
    facts = json.loads(path.read_text()).get("facts", {})
    # prefer us-gaap then ifrs-full
    candidates = []
    for tax in ("us-gaap", "ifrs-full"):
        concepts = facts.get(tax, {})
        for tag in REV_TAGS:
            if tag not in concepts:
                continue
            units = concepts[tag].get("units", {})
            # prefer USD, also keep TWD for TSM
            for unit in ("USD", "TWD"):
                if unit in units:
                    candidates.append((tax, tag, unit, units[unit]))
    if not candidates:
        return []
    # pick the tag/unit with most FY points
    def fy_pts(points):
        out = []
        seen = set()
        for p in points:
            if p.get("form") not in ("10-K", "10-K/A", "20-F", "20-F/A", "40-F"):
                # also allow fp FY
                if p.get("fp") != "FY":
                    continue
            # skip parenthetical amendments preferring later filed
            key = p.get("end")
            if not key:
                continue
            # ignore very short windows? annual should be ~360-380 days if start present
            start = p.get("start")
            if start and p.get("end"):
                ds = (parse_date(p["end"]) - parse_date(start)).days
                if ds < 300 or ds > 400:
                    continue
            rec = (p["end"], p.get("fy"), p["val"], p.get("filed"), p.get("form"), p.get("accn"))
            # keep latest filed for same end
            if key in seen:
                # replace if later filed
                for i, existing in enumerate(out):
                    if existing[0] == p["end"] and (p.get("filed") or "") >= (existing[3] or ""):
                        out[i] = rec
                continue
            seen.add(key)
            out.append(rec)
        out.sort(key=lambda x: x[0])
        return out

    best = None
    best_n = -1
    best_meta = None
    for tax, tag, unit, pts in candidates:
        fy = fy_pts(pts)
        # prefer USD
        score = len(fy) + (100 if unit == "USD" else 0)
        if score > best_n:
            best_n = score
            best = fy
            best_meta = (tax, tag, unit)
    return best_meta, best


def main():
    fx_pts = load_fx_twd_per_usd()
    quarterly = load_income(Q_FILES)
    annual = load_income(A_FILES)
    bars = load_bars()
    snaps = load_snapshots()

    # TSM conversions
    quarterly["TSM"] = convert_tsm_quarters(quarterly["TSM"], fx_pts)
    annual["TSM"] = convert_tsm_annual(annual["TSM"], fx_pts)

    # Persist cleaned data
    clean_dir = RAW / "clean"
    clean_dir.mkdir(exist_ok=True)

    asof = date(2026, 11, 25)

    summaries = []
    pe_series = {}
    annual_plot = {}
    ttm_rev = {}
    ttm_yoy = {}
    notes = {}

    print("=" * 80)
    print("CURRENT SNAPSHOT vs computed TTM")
    print(f"{'SYM':6} {'px':>10} {'wb_pe':>10} {'wb_eps_ttm':>12} {'comp_eps':>10} {'comp_pe':>10} {'ttm_rev_B':>10}")

    for sym in COMPANIES:
        qs = quarterly[sym]
        eps_key = "eps_usd_adr" if sym == "TSM" else "eps"
        rev_key = "revenue_usd" if sym == "TSM" else "revenue"

        ttm_eps, used_eps = ttm_from_quarters(qs, asof, eps_key, min_n=4 if sym != "ANT" else 4)
        # ANT has 6 quarters, last 4 exist
        ttm_r, used_r = ttm_from_quarters(qs, asof, rev_key, min_n=4)
        prior_r, used_prior = ttm_from_quarters(
            [q for q in qs if q["end"] and ttm_r is not None],
            # asof for prior TTM: end date of the quarter just before the first of last 4
            (used_r[0]["end"] - __import__("datetime").timedelta(days=1)) if used_r else asof,
            rev_key,
            min_n=4,
        )
        # more reliable prior: quarters before last 4
        if len([q for q in qs if q.get(rev_key) is not None]) >= 8:
            last8 = [q for q in qs if q.get(rev_key) is not None][-8:]
            prior_r = sum(q[rev_key] for q in last8[:4])
            ttm_r_chk = sum(q[rev_key] for q in last8[4:])
            ttm_r = ttm_r_chk
            yoy = (ttm_r / prior_r - 1.0) * 100.0 if prior_r else None
        else:
            yoy = None
            notes.setdefault(sym, []).append(
                f"TTM YoY unavailable or partial: only {len(qs)} quarterly periods in Webull."
            )

        px = snaps[sym]["price"]
        wb_pe = snaps[sym]["pe_ratio"]
        wb_eps = snaps[sym]["eps_ttm"]
        comp_pe = (px / ttm_eps) if (ttm_eps and ttm_eps > 0 and px) else None
        if ttm_eps is not None and ttm_eps <= 0:
            comp_pe = None

        pe_s = pe_history(sym, qs, bars.get(sym, []), eps_key)
        pe_series[sym] = pe_s
        pos = [r["pe"] for r in pe_s if r["pe"] is not None and r["date"] >= date(asof.year - 5, asof.month, 1)]
        # last 5 years of valid PE
        median_5y = float(np.median(pos)) if pos else None

        # annual last 5 FY + note fiscal year end
        anns = [a for a in annual[sym] if a.get(rev_key if sym == "TSM" else "revenue") is not None]
        anns = anns[-6:]
        annual_plot[sym] = anns
        ttm_rev[sym] = ttm_r
        ttm_yoy[sym] = yoy

        fy_end = anns[-1]["end"].strftime("%b %d") if anns and anns[-1]["end"] else "?"
        print(
            f"{sym:6} {px:10.2f} {wb_pe:10.2f} {wb_eps:12.4f} "
            f"{(ttm_eps or math.nan):10.4f} {(comp_pe or math.nan):10.2f} "
            f"{(ttm_r or 0)/1e9:10.2f}  yoy={yoy if yoy is not None else 'n/a'}  nPE={len(pos)} med={median_5y}"
        )

        # quarterly YoY for ANT if TTM yoy missing
        q_yoy = None
        if yoy is None:
            by_end = {q["end"]: q for q in qs if q.get(rev_key) is not None}
            latest = qs[-1]
            prev_year = date(latest["end"].year - 1, latest["end"].month, latest["end"].day) if latest["end"] else None
            # find closest same fiscal period prior year
            cands = [q for q in qs if q["fp"] == latest["fp"] and q["fy"] == latest["fy"] - 1]
            if cands and cands[-1].get(rev_key) and latest.get(rev_key):
                q_yoy = (latest[rev_key] / cands[-1][rev_key] - 1) * 100.0

        summaries.append({
            "symbol": sym,
            "name": NAMES[sym],
            "price": px,
            "webull_trailing_pe": wb_pe if (wb_pe and wb_pe > 0) else None,
            "computed_trailing_pe": comp_pe,
            "trailing_pe": comp_pe if comp_pe is not None else (wb_pe if wb_pe and wb_pe > 0 else None),
            "forward_pe": SA_PE[sym]["forward"],
            "eps_ttm_webull": wb_eps,
            "eps_ttm_computed": ttm_eps,
            "ttm_revenue": ttm_r,
            "ttm_revenue_yoy_pct": yoy,
            "latest_quarter_yoy_pct": q_yoy,
            "pe_5y_median": median_5y,
            "pe_history_n": len(pos),
            "currency_native": qs[-1]["currency"] if qs else "USD",
            "fiscal_year_end": anns[-1]["end"].isoformat() if anns and anns[-1]["end"] else None,
            "n_quarters": len(qs),
            "n_annual": len(annual[sym]),
        })

    # SEC verification
    print("\n======= SEC vs Webull annual revenue (USD bn, latest FY) =======")
    sec_comp = {}
    for sym in COMPANIES:
        if sym == "ANT":
            print("ANT: SEC companyfacts has no income-statement tags (S-1 fee facts only). Using Webull/S-1.")
            sec_comp[sym] = {"status": "no_xbrl"}
            continue
        meta, fy = sec_fy_revenues(sym)
        anns = annual[sym]
        print(f"{sym}: SEC tag {meta}")
        sec_map = {}
        if fy:
            for end, fy_, val, filed, form, accn in fy[-8:]:
                sec_map[end] = val
                print(f"   SEC {end} FY{fy_} {form} {val/1e9:.3f}B filed {filed}")
        for a in anns[-6:]:
            key = a["end"].isoformat() if a["end"] else None
            wb = a.get("revenue_usd") if sym == "TSM" else a["revenue"]
            secv = sec_map.get(key)
            # also try nearby
            if secv is None and key:
                for sk, sv in sec_map.items():
                    if sk[:7] == key[:7]:
                        secv = sv
            diff = None
            if secv and wb:
                diff = (wb - secv) / secv * 100
            sec_s = "None" if secv is None else f"{secv/1e9:.3f}B"
            print(f"   WB  {key} FY{a['fy']} {(wb or 0)/1e9:.3f}B  SEC={sec_s}  diff={diff}")
        sec_comp[sym] = {"meta": meta, "fy": fy}

    # TSM current EPS check
    tsm_eps, used = ttm_from_quarters(quarterly["TSM"], asof, "eps_usd_adr")
    print("\nTSM TTM USD ADR EPS computed:", ttm_eps, "Webull", snaps["TSM"]["eps_ttm"])
    for q in used or []:
        print(" ", q["end"], "eps_twd", q["eps"], "fx", q.get("fx_twd_per_usd"), "eps_usd_adr", q.get("eps_usd_adr"), "rev_usd_B", (q.get("revenue_usd") or 0)/1e9)

    # GOOG Q2 check
    print("\nGOOG recent quarters (look for one-time earnings):")
    for q in quarterly["GOOG"][-6:]:
        print(f"  {q['end']} FY{q['fy']}P{q['fp']} rev={q['revenue']/1e9:.1f}B NI={q['ni']/1e9:.1f}B EPS={q['eps']} unusual={q.get('unusual_expense_income')} other={q.get('other_net_income')}")

    # ANT
    print("\nANT quarters:")
    for q in quarterly["ANT"]:
        print(f"  {q['end']} FY{q['fy']}P{q['fp']} rev={q['revenue']/1e9:.3f}B NI={q['ni']/1e9:.1f}B EPS={q['eps']} shares={q['shares']}")
    print("ANT annual:")
    for a in annual["ANT"]:
        print(f"  {a['end']} FY{a['fy']} rev={a['revenue']} NI={a['ni']} EPS={a['eps']}")

    # save intermediate
    (clean_dir / "summaries.json").write_text(json.dumps(summaries, indent=2, default=str))
    (clean_dir / "sec_compare_meta.json").write_text(json.dumps({k: {"meta": v.get("meta")} for k, v in sec_comp.items()}, indent=2, default=str))

    # proceed to charts
    build_outputs(summaries, pe_series, annual, quarterly, ttm_rev, ttm_yoy, snaps, asof)


def style_ax(ax):
    ax.set_facecolor("white")
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.6, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(colors="#222222", labelsize=8)


def footer(fig, text):
    fig.text(0.01, 0.01, text, fontsize=6.5, color="#444444", ha="left", va="bottom", wrap=True)


def build_outputs(summaries, pe_series, annual, quarterly, ttm_rev, ttm_yoy, snaps, asof):
    # ---------- CSV ----------
    # wide-ish tidy CSVs
    pe_csv = OUT / "pe_history.csv"
    with pe_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "date", "month_end_close_usd", "ttm_diluted_eps", "trailing_pe", "status"])
        for sym in COMPANIES:
            for r in pe_series[sym]:
                w.writerow([
                    sym,
                    r["date"].isoformat(),
                    None if r["close"] is None else f"{r['close']:.6f}",
                    None if r["ttm_eps"] is None else f"{r['ttm_eps']:.6f}",
                    None if r["pe"] is None else f"{r['pe']:.4f}",
                    r["status"],
                ])

    snap_csv = OUT / "pe_snapshot.csv"
    with snap_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ticker", "name", "price_2026-11-25", "ttm_revenue_usd", "ttm_revenue_yoy_pct",
            "trailing_pe", "forward_pe", "pe_5y_median", "eps_ttm_webull", "eps_ttm_computed",
            "webull_trailing_pe", "sa_trailing_pe", "source_forward_pe", "notes",
        ])
        for s in summaries:
            sym = s["symbol"]
            notes = []
            if sym == "TSM":
                notes.append("Revenue and EPS converted from TWD to USD; P/E uses ADR (5 common shares).")
            if sym == "ANT":
                notes.append("IPO Nov 19, 2026; trailing P/E not meaningful (unprofitable); limited public history.")
            if sym == "RBLX":
                notes.append("Trailing and forward P/E not meaningful (unprofitable).")
            if sym == "GOOG":
                notes.append("TTM EPS includes a very large Q2 2026 net-income print, so trailing P/E is pulled down vs forward.")
            w.writerow([
                sym, s["name"], s["price"],
                None if s["ttm_revenue"] is None else f"{s['ttm_revenue']:.0f}",
                None if s["ttm_revenue_yoy_pct"] is None else f"{s['ttm_revenue_yoy_pct']:.2f}",
                None if s["trailing_pe"] is None else f"{s['trailing_pe']:.2f}",
                None if s["forward_pe"] is None else f"{s['forward_pe']:.2f}",
                None if s["pe_5y_median"] is None else f"{s['pe_5y_median']:.2f}",
                s["eps_ttm_webull"], s["eps_ttm_computed"],
                s["webull_trailing_pe"], SA_PE[sym]["trailing"],
                "StockAnalysis.com, retrieved 2026-11-26",
                " ".join(notes),
            ])
        for etf in ETFS:
            w.writerow([
                etf, NAMES[etf], snaps[etf]["price"],
                "", "",
                SA_PE[etf]["trailing"], SA_PE[etf]["forward"],
                "", "", "",
                "", SA_PE[etf]["trailing"],
                "StockAnalysis.com, retrieved 2026-11-26",
                "ETF: no company revenue. Aggregate P/E from StockAnalysis (Webull pe_ratio was 0).",
            ])

    rev_csv = OUT / "revenue_history.csv"
    with rev_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "kind", "fiscal_year", "period_end", "currency_native", "revenue_usd", "revenue_native", "fx_twd_per_usd"])
        for sym in COMPANIES:
            rev_key = "revenue_usd" if sym == "TSM" else "revenue"
            for a in annual[sym]:
                w.writerow([
                    sym, "annual", a["fy"], a["end"].isoformat() if a["end"] else "",
                    a["currency"], a.get(rev_key) if sym == "TSM" else a["revenue"],
                    a["revenue"], a.get("fx_twd_per_usd", ""),
                ])
            # TTM row
            w.writerow([
                sym, "ttm", "TTM", asof.isoformat(),
                "USD" if sym != "TSM" else "TWD converted",
                ttm_rev[sym], "", "",
            ])

    # combined tidy file requested ("a CSV")
    master = OUT / "watchlist_pe_revenue.csv"
    # I'll also write a compact summary as the main CSV
    with master.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ticker", "security_type", "name", "price_2026-11-25",
            "ttm_revenue_usd_bn", "ttm_revenue_yoy_pct",
            "trailing_pe", "forward_pe", "pe_5y_median",
            "eps_ttm", "fiscal_year_end", "notes",
        ])
        for s in summaries:
            notes = []
            if s["symbol"] == "TSM":
                notes.append("TWD converted to USD; ADR 1:5.")
            if s["symbol"] == "ANT":
                notes.append("Unprofitable; IPO 2026-11-19; trailing P/E N/M.")
            if s["symbol"] == "RBLX":
                notes.append("Unprofitable; P/E N/M.")
            if s["symbol"] == "GOOG":
                notes.append("Trailing P/E pulled down by large Q2 2026 earnings.")
            if s["ttm_revenue_yoy_pct"] is None and s["latest_quarter_yoy_pct"] is not None:
                notes.append(f"TTM YoY n/a (short history); latest quarter YoY {s['latest_quarter_yoy_pct']:.0f}%.")
            w.writerow([
                s["symbol"], "stock", s["name"], f"{s['price']:.4f}",
                None if s["ttm_revenue"] is None else f"{s['ttm_revenue']/1e9:.4f}",
                None if s["ttm_revenue_yoy_pct"] is None else f"{s['ttm_revenue_yoy_pct']:.2f}",
                "N/M" if s["trailing_pe"] is None else f"{s['trailing_pe']:.2f}",
                "N/M" if s["forward_pe"] is None else f"{s['forward_pe']:.2f}",
                "n/a" if s["pe_5y_median"] is None else f"{s['pe_5y_median']:.2f}",
                s["eps_ttm_computed"], s["fiscal_year_end"],
                " ".join(notes),
            ])
        for etf in ETFS:
            w.writerow([
                etf, "etf", NAMES[etf], f"{snaps[etf]['price']:.4f}",
                "", "",
                f"{SA_PE[etf]['trailing']:.2f}", f"{SA_PE[etf]['forward']:.2f}",
                "n/a", "", "",
                "No company revenue. Aggregate P/E from StockAnalysis.com as of 2026-11-26.",
            ])

    print("\nWrote CSVs:", pe_csv, snap_csv, rev_csv, master)

    # ---------- charts ----------
    plt.rcParams.update({"svg.fonttype":"none","svg.hashsalt":"x",
        "font.family": "DejaVu Sans",
        "axes.titlesize": 10,
        "axes.labelsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "text.color": "#111111",
        "axes.labelcolor": "#111111",
        "xtick.color": "#222222",
        "ytick.color": "#222222",
        "axes.edgecolor": "#444444",
    })

    # 1) pe_history small multiples
    n = len(COMPANIES)
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13.5, 9.2), sharex=True)
    axes = axes.flatten()
    for i, sym in enumerate(COMPANIES):
        ax = axes[i]
        style_ax(ax)
        rows = pe_series[sym]
        xs = [r["date"] for r in rows]
        ys = [r["pe"] if r["status"] == "ok" else np.nan for r in rows]
        ax.plot(xs, ys, color="#1f4e79", linewidth=1.4, zorder=3)
        nm = np.array([r["status"] == "N/M" for r in rows], dtype=bool)
        insuff = np.array([r["status"] == "insufficient" for r in rows], dtype=bool)
        if nm.any():
            ax.fill_between(xs, 0, 1, where=nm, step="pre", interpolate=False,
                            transform=ax.get_xaxis_transform(),
                            color="#f4d6d6", alpha=0.85, linewidth=0, zorder=1)
        if insuff.any():
            ax.fill_between(xs, 0, 1, where=insuff, step="pre", interpolate=False,
                            transform=ax.get_xaxis_transform(),
                            color="#f0f0f0", alpha=0.9, linewidth=0, zorder=0)
        valid = [y for y in ys if not (isinstance(y, float) and math.isnan(y))]
        med = summaries[i]["pe_5y_median"]
        cur = summaries[i]["trailing_pe"]
        if med is not None:
            ax.axhline(med, color="#c47b17", linewidth=0.9, linestyle="--", zorder=2)
        # y cap
        if valid:
            p95 = float(np.nanpercentile(valid, 95))
            ymax = max(p95 * 1.15, (cur or 0) * 1.1, 20)
            ymax = min(ymax, 200) if max(valid) > 250 else ymax
            # TSLA can be very high; cap at 250 and note
            if max(valid) > ymax + 1:
                # mark capped points
                ax.plot(xs, [min(y, ymax) if not (isinstance(y, float) and math.isnan(y)) else np.nan for y in ys],
                        color="#1f4e79", linewidth=1.4, zorder=3)
            ax.set_ylim(0, ymax)
            if max(valid) > ymax + 1:
                ax.text(0.98, 0.92, f"axis cap {ymax:.0f} (max {max(valid):.0f})",
                        transform=ax.transAxes, ha="right", va="top", fontsize=6.5, color="#8a1f1f")
        else:
            ax.set_ylim(0, 20)
            if sym == "ANT":
                ax.text(0.5, 0.55, "IPO 19 Nov 2026\nTrailing P/E N/M\n(unprofitable)",
                        transform=ax.transAxes, ha="center", va="center", fontsize=8, color="#555555")
            elif sym == "RBLX":
                ax.text(0.5, 0.55, "Trailing P/E N/M\nthrough this window\n(unprofitable)",
                        transform=ax.transAxes, ha="center", va="center", fontsize=8, color="#555555")
        title = f"{sym}  {NAMES[sym]}"
        if cur is not None:
            title += f"   now {cur:.1f}x"
        elif snaps[sym]["pe_ratio"] is not None and snaps[sym]["pe_ratio"] < 0:
            title += "   now N/M"
        ax.set_title(title, loc="left", fontsize=9, fontweight="bold", color="#111111")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        if i % ncols == 0:
            ax.set_ylabel("Trailing P/E")
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    fig.suptitle("Trailing P/E, last ~5 years  (month-end price / TTM diluted EPS)",
                 fontsize=13, fontweight="bold", color="#111111", y=0.995)
    # legend
    from matplotlib.lines import Line2D
    fig.legend(handles=[
        Line2D([0], [0], color="#1f4e79", lw=1.6, label="Trailing P/E"),
        Line2D([0], [0], color="#c47b17", lw=1.0, ls="--", label="5y median (valid months)"),
        Line2D([0], [0], color="#f4d6d6", lw=6, label="N/M (negative TTM EPS)"),
        Line2D([0], [0], color="#d0d0d0", lw=6, label="Insufficient TTM history"),
    ], loc="upper right", frameon=False, fontsize=7.5, bbox_to_anchor=(0.99, 0.972), ncol=4)
    footer(
        fig,
        "As of Wed 25 Nov 2026 close (US markets closed Thu 26 Nov, Thanksgiving). "
        "P/E = Webull month-end close / TTM diluted EPS from Webull income statements (4 most recently published quarters). "
        "TSM: TWD EPS converted to USD ADR EPS using official 1:5 ADR ratio and Yahoo TWD=X at each quarter end. "
        "ANT: only one monthly close (IPO 19 Nov 2026). Negative or missing TTM EPS plotted as N/M, not a negative multiple. "
        "Sources: Webull (prices, income statements); Yahoo Finance TWD=X for TSM FX. Research, not advice."
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    fig.savefig(OUT / "pe_history.png", dpi=160)
    fig.savefig(OUT / "pe_history.svg")
    plt.close(fig)
    print("wrote pe_history.png")

    # 2) pe_snapshot horizontal bars
    fig, ax = plt.subplots(figsize=(11.2, 8.2))
    style_ax(ax)
    # include ETFs + profitable stocks in sort; unprofitable annotated
    rows = []
    for s in summaries:
        rows.append({
            "ticker": s["symbol"], "name": s["name"],
            "trail": s["trailing_pe"], "fwd": s["forward_pe"],
            "kind": "stock",
        })
    for etf in ETFS:
        rows.append({
            "ticker": etf, "name": NAMES[etf],
            "trail": SA_PE[etf]["trailing"], "fwd": SA_PE[etf]["forward"],
            "kind": "etf",
        })
    # sort: those with trailing first (low to high), then N/M
    def sort_key(r):
        return (0, r["trail"]) if r["trail"] is not None else (1, r["fwd"] or 9999)
    # barh draws the first row at the bottom. Sort so N/M and richest trailing
    # are first (bottom) and cheapest trailing is last (top).
    rows_plot = sorted(rows, key=sort_key, reverse=True)

    y = np.arange(len(rows_plot))
    trail = [r["trail"] if r["trail"] is not None else np.nan for r in rows_plot]
    fwd = [r["fwd"] if r["fwd"] is not None else np.nan for r in rows_plot]
    h = 0.38
    ax.barh(y + h/2, trail, height=h, color="#1f4e79", label="Trailing P/E", zorder=3)
    ax.barh(y - h/2, fwd, height=h, color="#e07a3d", label="Forward P/E", zorder=3)

    labels = []
    for r in rows_plot:
        tag = f"{r['ticker']}"
        if r["kind"] == "etf":
            tag += "  (ETF)"
        labels.append(tag)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    # values at end of bars
    xmax_candidates = [v for v in trail + fwd if not (isinstance(v, float) and (math.isnan(v) if v is not None else True)) and v is not None]
    # ANT forward 226 would wreck the scale
    xmax = max([v for v in xmax_candidates if v <= 120] or [80]) * 1.18
    ax.set_xlim(0, xmax)
    for yi, r in enumerate(rows_plot):
        bbox = dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.9)
        if r["trail"] is not None:
            val = r["trail"]
            if val <= xmax:
                ax.text(val + 0.4, yi + h/2, f"{val:.1f}", va="center", ha="left", fontsize=6.5, color="#1f4e79")
            else:
                ax.text(xmax - 0.6, yi + h/2, f"{val:.1f}  (off scale)", va="center", ha="right",
                        fontsize=6.5, color="#1f4e79", bbox=bbox, zorder=5)
        else:
            ax.text(0.4, yi + h/2, "N/M", va="center", ha="left", fontsize=6.5, color="#888888")
        if r["fwd"] is not None:
            val = r["fwd"]
            if val <= xmax:
                ax.text(val + 0.4, yi - h/2, f"{val:.1f}", va="center", ha="left", fontsize=6.5, color="#b55a20")
            else:
                ax.text(xmax - 0.6, yi - h/2, f"{val:.1f}  (off scale)", va="center", ha="right",
                        fontsize=6.5, color="#b55a20", bbox=bbox, zorder=5)
        else:
            ax.text(0.4, yi - h/2, "N/M", va="center", ha="left", fontsize=6.5, color="#888888")

    ax.set_xlabel("P/E")
    ax.set_title("Current trailing vs forward P/E  (sorted cheapest trailing at top)",
                 loc="left", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="upper right")
    footer(
        fig,
        "Prices and trailing P/E: Webull, Wed 25 Nov 2026 close (price / TTM diluted EPS). "
        "Forward P/E and ETF aggregate P/E: StockAnalysis.com, retrieved Thu 26 Nov 2026. "
        "Webull ETF pe_ratio was 0, so ETF multiples use StockAnalysis. "
        "ANT trailing P/E is N/M (unprofitable); its StockAnalysis forward P/E of 226 is off the scale. "
        "RBLX trailing and forward P/E are both N/M. TSM is the NYSE ADR. Research, not advice."
    )
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(OUT / "pe_snapshot.png", dpi=160)
    fig.savefig(OUT / "pe_snapshot.svg")
    plt.close(fig)
    print("wrote pe_snapshot.png")

    # 3) revenue_history small multiples
    fig, axes = plt.subplots(nrows, ncols, figsize=(13.5, 9.2))
    axes = axes.flatten()
    for i, sym in enumerate(COMPANIES):
        ax = axes[i]
        style_ax(ax)
        rev_key = "revenue_usd" if sym == "TSM" else "revenue"
        anns = [a for a in annual[sym] if a.get(rev_key) is not None]
        # last 5 or 6 fiscal years
        anns = anns[-5:]
        labels = []
        vals = []
        for a in anns:
            labels.append(f"FY{a['fy']}")
            vals.append(a[rev_key] / 1e9)
        x = np.arange(len(vals))
        ax.bar(x, vals, color="#2a6f7f", width=0.72, zorder=3, label="Fiscal year")
        # TTM as hatched bar to the right if we have it
        if ttm_rev[sym] is not None:
            ax.bar([len(vals)], [ttm_rev[sym] / 1e9], color="#d9eef2", edgecolor="#2a6f7f",
                   hatch="///", width=0.72, zorder=3, label="TTM")
            labels.append("TTM")
            x = np.arange(len(labels))
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, fontsize=7, rotation=0)
        ax.set_title(f"{sym}  {NAMES[sym]}", loc="left", fontsize=9, fontweight="bold")
        if i % ncols == 0:
            ax.set_ylabel("Revenue ($B)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: f"{v:.0f}" if v >= 10 else f"{v:.1f}"))
        subtitle = []
        if anns:
            subtitle.append("FY ends " + anns[-1]["end"].strftime("%b"))
        if sym == "TSM":
            subtitle.append("USD from TWD")
        extra = ("  " + ", ".join(subtitle)) if subtitle else ""
        disp = "TSMC" if sym=="TSM" else NAMES[sym]
        ax.set_title(f"{sym}  {disp}{extra}", loc="left", fontsize=8, fontweight="bold")
        if i == 0:
            ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    fig.suptitle("Annual revenue ($ billions) and trailing-twelve-month revenue",
                 fontsize=13, fontweight="bold", y=0.995)
    footer(
        fig,
        "Company revenue, not portfolio value. Webull annual income statements; TTM = sum of the last four reported quarters. "
        "TSM reported in TWD (20-F foreign filer); converted to USD at Yahoo TWD=X on each fiscal period end (TWD per USD). "
        "FY labels are the company's fiscal year (LULU and MRVL end in late Jan / early Feb; LRCX in June; MU in late Aug / early Sep; AVGO in early Nov). "
        "ANT history is short (S-1 / IPO financials via Webull); TTM uses the last four available quarters. "
        "ETFs (VOO, QQQ, SOXX, VXUS) have no company revenue and are omitted. Sources: Webull; Yahoo TWD=X; SEC companyfacts used as a check. Research, not advice."
    )
    fig.tight_layout(rect=[0, 0.08, 1, 0.96])
    fig.savefig(OUT / "revenue_history.png", dpi=160)
    fig.savefig(OUT / "revenue_history.svg")
    plt.close(fig)
    print("wrote revenue_history.png")

    # 4) revenue_growth
    fig, ax = plt.subplots(figsize=(11.2, 7.2))
    style_ax(ax)
    grow = []
    for s in summaries:
        grow.append({
            "ticker": s["symbol"],
            "yoy": s["ttm_revenue_yoy_pct"],
            "q_yoy": s["latest_quarter_yoy_pct"],
        })
    # sort by TTM yoy where present, ANT at end if missing
    grow_have = [g for g in grow if g["yoy"] is not None]
    grow_miss = [g for g in grow if g["yoy"] is None]
    grow_have = sorted(grow_have, key=lambda g: g["yoy"])
    ordered = grow_miss + grow_have  # missing at bottom if we want highest at top...
    # cheapest? this is growth: highest at top
    ordered = list(reversed(grow_have)) + list(reversed(grow_miss))
    # wait barh first = bottom, so to have highest at top put lowest first
    ordered = grow_have + grow_miss  # low at bottom, high later? grow_have is ascending, first=lowest at bottom, last=highest near top, then missing above. Better: missing at bottom, high at top.
    ordered = grow_miss + grow_have

    y = np.arange(len(ordered))
    vals = [g["yoy"] if g["yoy"] is not None else np.nan for g in ordered]
    colors = []
    for g in ordered:
        if g["yoy"] is None:
            colors.append("#aaaaaa")
        elif g["yoy"] >= 0:
            colors.append("#2d6a4f")
        else:
            colors.append("#9b2226")
    # for missing, maybe show 0-width and annotate
    plot_vals = [0 if g["yoy"] is None else g["yoy"] for g in ordered]
    ax.barh(y, plot_vals, color=colors, height=0.7, zorder=3)
    ax.axvline(0, color="#444444", linewidth=0.8, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels([g["ticker"] for g in ordered], fontsize=10)
    for yi, g in enumerate(ordered):
        if g["yoy"] is not None:
            x = g["yoy"]
            ha = "left" if x >= 0 else "right"
            ax.text(x + (1.2 if x >= 0 else -1.2), yi, f"{x:.0f}%", va="center", ha=ha, fontsize=8)
        else:
            extra = ""
            if g["q_yoy"] is not None:
                extra = f" (latest quarter YoY {g['q_yoy']:.0f}%)"
            ax.text(1.0, yi, f"TTM YoY n/a{extra}", va="center", ha="left", fontsize=8, color="#555555")
    ax.set_xlabel("TTM revenue growth vs prior TTM (%)")
    ax.set_title("Trailing-twelve-month revenue growth", loc="left", fontsize=13, fontweight="bold")
    footer(
        fig,
        "TTM revenue / TTM revenue from the prior four quarters, minus 1. Webull quarterly income statements, as of 25 Nov 2026. "
        "TSM converted from TWD to USD (FX effects are in the USD growth rate). "
        "ANT has only six public quarters, so a full TTM-vs-prior-TTM rate is not available; Q3 2026 revenue vs Q3 2025 is shown in the note instead. "
        "ETFs omitted (no company revenue). Research, not advice."
    )
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(OUT / "revenue_growth.png", dpi=160)
    fig.savefig(OUT / "revenue_growth.svg")
    plt.close(fig)
    print("wrote revenue_growth.png")

    # print summary table for the note
    print("\n======= SUMMARY TABLE =======")
    print(f"{'ticker':6} {'ttm yoy':>8} {'trail PE':>8} {'fwd PE':>8} {'5y med':>8}  vs med")
    for s in summaries:
        yoy = "n/a" if s["ttm_revenue_yoy_pct"] is None else f"{s['ttm_revenue_yoy_pct']:.1f}%"
        tr = "N/M" if s["trailing_pe"] is None else f"{s['trailing_pe']:.1f}"
        fw = "N/M" if s["forward_pe"] is None else f"{s['forward_pe']:.1f}"
        med = "n/a" if s["pe_5y_median"] is None else f"{s['pe_5y_median']:.1f}"
        vs = ""
        if s["trailing_pe"] is not None and s["pe_5y_median"] is not None:
            vs = "ABOVE" if s["trailing_pe"] > s["pe_5y_median"] else "below"
        print(f"{s['symbol']:6} {yoy:>8} {tr:>8} {fw:>8} {med:>8}  {vs}")
    for etf in ETFS:
        print(f"{etf:6} {'—':>8} {SA_PE[etf]['trailing']:8.1f} {SA_PE[etf]['forward']:8.1f} {'n/a':>8}")


if __name__ == "__main__":
    main()
