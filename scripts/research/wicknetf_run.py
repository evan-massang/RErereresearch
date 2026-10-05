"""H-WICKNET-F runner (reports/hypotheses/wicknetf_preregistration.json).
Usage: python wicknetf_run.py train          # 6 configs, informational
       python wicknetf_run.py valid <config> # once, selected config only
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wicknet_sim as W  # noqa: E402

FCONF = {}
for d in (30, 50):
    FCONF[f"f_d{d}_TK2"] = dict(d_bp=d, R_s=2, exit="TK", filt=True, H_s=2)
    FCONF[f"f_d{d}_TK5"] = dict(d_bp=d, R_s=2, exit="TK", filt=True, H_s=5)
    FCONF[f"f_d{d}_MK5"] = dict(d_bp=d, R_s=2, exit="MK", filt=True, H_s=5)
W.CONFIGS.clear()
W.CONFIGS.update(FCONF)
W.OUT = W.ROOT / "data/raw/web/tardis/results/wicknetf"

if __name__ == "__main__":
    sp = sys.argv[1]
    names = sys.argv[2:] or list(FCONF)
    if sp == "valid":
        assert len(names) == 1, "validation runs exactly one selected config"
    W.main(sp, names)
