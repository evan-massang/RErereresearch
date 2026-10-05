"""H-LISTBASIS census: first trading date of every HL main-dex perp and Binance USDT-M perp (archive), used to
review by hand which validation-window listings are Solana memecoins (identity only, no prices).
Writes data/raw/web/listbasis/census_first_dates.json.  Run from the repo root."""
import sys, json, time, datetime as dt
sys.path.insert(0, "scripts/research")
import listbasis_count as L
from concurrent.futures import ThreadPoolExecutor
meta = json.loads((L.C/"hl_meta.json").read_text())["data"]
bn = json.loads((L.C/"bn_um_symbols.json").read_text())["data"]
def hl(n):
    try: return ("HL", n, L.first_date("HL", n, None))
    except Exception as e: return ("HL", n, str(e))
def b(s):
    try: return ("BN", s, L.first_date("BN", s, None))
    except Exception as e: return ("BN", s, str(e))
with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(hl, [u["name"] for u in meta["universe"]])) + list(ex.map(b, [s for s in bn if s.endswith("USDT")]))
out = []
for v, s, t in res:
    if isinstance(t, int):
        out.append((v, s, dt.datetime.utcfromtimestamp(t/1000).strftime("%Y-%m-%d")))
    else: out.append((v, s, str(t)))
json.dump(out, open(L.C/"census_first_dates.json", "w"))
for v, s, d in sorted(out, key=lambda x: x[2]):
    if "2025-07-01" <= d < "2026-04-01": print(v, s, d)
print("errors/none:", [x for x in out if not x[2][:2] == "20"][:40])
