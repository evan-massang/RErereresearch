"""Validation (Oct 3) for H-DEXPAID configs that passed the full bar on train at the main lag (120 s), at BOTH tips.
Runs once. Exits without loading validation data if nothing passed on train.

    python scripts/research/dex_paid_validate.py <train_results.json>
"""
import json
import sys

sys.path.insert(0, "/home/user/RErereresearch/scripts/research")
import dex_paid_sim as D  # noqa: E402

tr = json.load(open(sys.argv[1]))
todo = {w: tr[f"{w}|lag120"]["passing"] for w in ("prof", "prof_or_boost")}
if not any(todo.values()):
    print("no config passed on train; validation not examined")
    sys.exit(0)
out = {}
for w, cfgs in todo.items():
    if not cfgs:
        continue
    for lag in (120, 30, 600):
        df = D.build("valid", lag, "prof" if w == "prof" else "pb")
        g = D.grid_stats(df)
        out[f"{w}|lag{lag}"] = {k: g[k] for k in cfgs}
print(json.dumps(out, indent=1))
