"""Forward paper trading: frozen strategies scored only on tape recorded after they were frozen.

A strategy is a function ``fn(con, start, end, data_end, params) -> list[dict]`` in a module under
``scripts/research`` (or ``pipeline``). Each returned trade needs ``t`` (entry signal time) and ``pnl_sol``
(after every cost). Freezing writes ``reports/paper/<name>.json`` with the parameters, the module's SHA-256 and
``frozen_at``; scoring refuses if the module changed and only takes entries at or after ``frozen_at``.

The bar (agreed with the project owner 2026-10-03), all required:
  * at least 50 paper trades,
  * net PnL > 0 after all costs,
  * profit factor > 1.2,
  * net PnL > 0 with the 3 best trades removed.

    python -m pipeline.paper freeze NAME MODULE FUNCTION '<params json>' "<rationale>"
    python -m pipeline.paper score NAME
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import statistics
import sys
import time
from pathlib import Path

import duckdb

from pipeline import config

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports/paper"
BAR = {"min_trades": 50, "min_pnl_sol": 0.0, "min_profit_factor": 1.2, "min_pnl_without_top3_sol": 0.0}


def _module_path(module: str) -> Path:
    for base in (ROOT / "scripts/research", ROOT / "pipeline"):
        p = base / f"{module}.py"
        if p.exists():
            return p
    raise FileNotFoundError(module)


def _sha(module: str) -> str:
    return hashlib.sha256(_module_path(module).read_bytes()).hexdigest()


def freeze(name: str, module: str, function: str, params: dict, rationale: str, max_hold_s: float) -> dict:
    p = DIR / f"{name}.json"
    if p.exists():
        raise SystemExit(f"{p} exists; a frozen strategy is never changed. Use a new name.")
    DIR.mkdir(parents=True, exist_ok=True)
    rec = {"name": name, "module": module, "function": function, "params": params, "max_hold_s": max_hold_s,
           "module_sha256": _sha(module), "frozen_at": time.time(),
           "frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rationale": rationale, "bar": BAR}
    p.write_text(json.dumps(rec, indent=1))
    return rec


def verdict(trades: list[dict]) -> dict:
    v = sorted(t["pnl_sol"] for t in trades)
    wins, losses = [x for x in v if x > 0], [x for x in v if x <= 0]
    pf = sum(wins) / -sum(losses) if losses and sum(losses) < 0 else (float("inf") if wins else None)
    s = {"n_trades": len(v), "pnl_sol": round(sum(v), 4),
         "expectancy_sol": round(statistics.mean(v), 4) if v else None,
         "win_rate": round(len(wins) / len(v), 3) if v else None,
         "profit_factor": round(pf, 3) if pf not in (None, float("inf")) else pf,
         "pnl_without_top3_sol": round(sum(v[:-3]), 4) if len(v) > 3 else None}
    checks = {"min_trades": len(v) >= BAR["min_trades"], "pnl": s["pnl_sol"] > BAR["min_pnl_sol"],
              "profit_factor": pf is not None and pf > BAR["min_profit_factor"],
              "without_top3": s["pnl_without_top3_sol"] is not None and s["pnl_without_top3_sol"] > 0}
    return s | {"checks": checks, "pass": all(checks.values())}


def score(name: str, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    rec = json.loads((DIR / f"{name}.json").read_text())
    if _sha(rec["module"]) != rec["module_sha256"]:
        raise SystemExit(f"{rec['module']} changed since {name} was frozen; scoring refused.")
    con = con or duckdb.connect(str(config.path("data") / "market.duckdb"), read_only=True)
    data_end = con.execute("SELECT max(recv) FROM curve_trades").fetchone()[0]
    start, end = rec["frozen_at"], data_end - rec["max_hold_s"]
    sys.path.insert(0, str(ROOT / "scripts/research"))
    fn = getattr(importlib.import_module(rec["module"]), rec["function"])
    trades = [t for t in fn(con, start, end, data_end, rec["params"]) if t["t"] >= rec["frozen_at"]] if end > start else []
    out = {"name": name, "frozen_at_utc": rec["frozen_at_utc"], "scored_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "window": [start, end], "data_end": data_end, **verdict(trades), "trades": trades}
    (DIR / f"{name}_ledger.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("name"), f.add_argument("module"), f.add_argument("function"), f.add_argument("params")
    f.add_argument("rationale"), f.add_argument("--max-hold-s", type=float, default=3600)
    s = sub.add_parser("score")
    s.add_argument("name")
    a = ap.parse_args(argv)
    if a.cmd == "freeze":
        print(json.dumps(freeze(a.name, a.module, a.function, json.loads(a.params), a.rationale, a.max_hold_s), indent=1))
    else:
        print(json.dumps({k: v for k, v in score(a.name).items() if k != "trades"}, indent=1))


if __name__ == "__main__":
    main()
