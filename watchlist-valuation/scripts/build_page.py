"""Build index.html for the watchlist valuation page from data/watchlist_pe_revenue.csv.

Usage: python scripts/build_page.py data index.html
"""
import csv, html, json, sys

D, OUT = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(f"{D}/watchlist_pe_revenue.csv")))

def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

NM = {"ANT": "Unprofitable", "RBLX": "Unprofitable"}
data = []
for r in rows:
    g, tp, fp, med = num(r["ttm_revenue_yoy_pct"]), num(r["trailing_pe"]), num(r["forward_pe"]), num(r["pe_5y_median"])
    px, eps = num(r["price_2026-11-25"]), num(r["eps_ttm"])
    if tp and px and eps and eps > 0:
        tp = px / eps  # avoid double rounding of the 2-decimal CSV value
    d = dict(t=r["ticker"], name=r["name"], etf=r["security_type"] == "etf",
             g=g, tp=tp, fp=fp, med=med,
             vs_med=(tp / med if tp and med else None),
             impl=((tp / fp - 1) * 100 if tp and fp else None),
             pg=(fp / g if fp and g and g > 0 else None))
    data.append(d)

def f(v, nd=1, suf=""):
    return "n/m" if v is None else f"{v:,.{nd}f}{suf}"

body = []
for d in data:
    body.append(
        f'<tr data-t="{d["t"]}"><td><b>{d["t"]}</b> <span class="note">{html.escape(d["name"])}</span></td>'
        f'<td data-v="{d["g"] if d["g"] is not None else ""}">{"n/a" if d["etf"] else f(d["g"],1,"%")}</td>'
        f'<td data-v="{d["tp"] or ""}">{f(d["tp"])}</td><td data-v="{d["fp"] or ""}">{f(d["fp"])}</td>'
        f'<td data-v="{d["med"] or ""}">{f(d["med"])}</td>'
        f'<td data-v="{d["vs_med"] or ""}">{f(d["vs_med"],2,"x")}</td>'
        f'<td data-v="{d["impl"] if d["impl"] is not None else ""}">{f(d["impl"],0,"%")}</td>'
        f'<td data-v="{d["pg"] or ""}">{f(d["pg"],2)}</td></tr>')

TEMPLATE = open(__file__.replace("build_page.py", "template.html"), encoding="utf-8").read()
out = TEMPLATE.replace("__ROWS__", "\n".join(body))
open(OUT, "w", encoding="utf-8").write(out)
print("wrote", OUT, len(out) // 1024, "KB")
for d in data:
    print(d["t"], f(d["g"]), f(d["tp"]), f(d["fp"]), f(d["vs_med"], 2), f(d["impl"], 0), f(d["pg"], 2))
