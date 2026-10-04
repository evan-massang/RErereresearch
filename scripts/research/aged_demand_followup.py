"""Agent aged_demand follow-up (4 configs, total grid 40): on train the 36-config grid improved monotonically with
a stricter aged-buyer count (K 10 -> 25) and with the share/wash and human (<= 100 prior mints) filters, but no
config passed. Rationale-backed last step: K = 40 in a 30 s window, filters share | human, exits tp30_sl15_300 |
tp50_sl20_300 (the two least negative exits). Train only; validation only if a config passes on train.

    python scripts/research/aged_demand_followup.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import aged_demand_eval as ev  # noqa: E402


def configs(f):
    sh = (f["share30"] >= 0.5) & (f["wash30"] <= 0.2)
    return {"W30_K40_share": (f["nA30"] >= 40) & sh, "W30_K40_human": (f["nAh30"] >= 40) & sh}


ev.configs = configs
ev.EXITS = tuple(e for e in ev.EXITS if e[0] != "tp100_sl30_1800")
ev.SCR = ev.SCR / "followup"
ev.SCR.mkdir(exist_ok=True)
(ev.SCR / "duck_tmp").mkdir(exist_ok=True)
d, res, sel = ev.run(validate=False)
for k, v in res.items():
    print(k, v)
print("passing train:", sel)
(ev.EVID / "evidence_aged_demand_followup_train_20261004.json").write_text(json.dumps(
    {"n_configs": 4, "cumulative_configs": 40, "passing_train": sel, "results": res}, indent=1))
