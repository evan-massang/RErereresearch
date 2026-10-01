"""Chronological splits, run recording, and the one-shot holdout.

Rules enforced here:
  * splits are ordered and non-overlapping: train < validation < holdout
  * train/validation runs only receive data available before their split's end,
    so holdout data does not exist for them
  * a holdout is evaluated at most once, with pass criteria registered *before*
    the run; afterwards the split is burned. Any later change needs a new, later
    holdout period.
"""

from __future__ import annotations

import hashlib
import json
import operator
import subprocess
from datetime import datetime, timezone

import duckdb

from .. import config, db
from ..ids import new_id
from .engine import SimResult, Strategy, run
from .events import EventStore
from .execution import ExecutionModel
from .metrics import performance

ORDER = ["train", "validation", "holdout"]
_OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


class HoldoutBurnedError(RuntimeError):
    pass


def _ts(x: datetime) -> float:
    return x.timestamp()


def define_splits(con: duckdb.DuckDBPyConnection, split_set: str, periods: dict[str, tuple[datetime, datetime]],
                  *, notes: str | None = None, is_synthetic: bool = False) -> None:
    if set(periods) != set(ORDER):
        raise ValueError(f"periods must define exactly {ORDER}")
    if con.execute("SELECT count(*) FROM data_splits WHERE split_set = ?", [split_set]).fetchone()[0]:
        raise ValueError(f"split set {split_set!r} already exists; splits are never redefined")
    prev_end = None
    for name in ORDER:
        start, end = periods[name]
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("use timezone-aware datetimes")
        if end <= start:
            raise ValueError(f"{name}: end must be after start")
        if prev_end is not None and start < prev_end:
            raise ValueError(f"{name} overlaps or precedes the previous split")
        prev_end = end
    for name in ORDER:
        start, end = periods[name]
        db.upsert(con, "data_splits", {
            "split_set": split_set, "split_name": name, "start_at": start, "end_at": end, "status": "open",
            "burned_at": None, "burned_by_run": None, "notes": notes, "created_at": db.now(),
            "is_synthetic": is_synthetic})


def get_split(con, split_set: str, split_name: str) -> tuple[datetime, datetime, str]:
    row = con.execute("SELECT start_at, end_at, status FROM data_splits WHERE split_set = ? AND split_name = ?",
                      [split_set, split_name]).fetchone()
    if row is None:
        raise ValueError(f"unknown split {split_set}/{split_name}")
    return row


def strategy_hash(strategy: Strategy) -> str:
    payload = json.dumps({"name": strategy.name, "spec": strategy.spec()}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _code_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.REPO_ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=config.REPO_ROOT, capture_output=True,
                               text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def record_run(con: duckdb.DuckDBPyConnection, result: SimResult, *, strategy: Strategy,
               split_set: str | None, split_name: str | None, hypothesis_id: str | None = None,
               metrics_imitation: dict | None = None, notes: str | None = None,
               is_synthetic: bool = False) -> str:
    db.require(con, "hypotheses", "hypothesis_id", hypothesis_id)
    run_id = new_id("run")
    perf = performance(result)
    db.upsert(con, "sim_runs", {
        "run_id": run_id, "hypothesis_id": hypothesis_id, "strategy_name": strategy.name,
        "strategy_hash": strategy_hash(strategy), "strategy_spec": strategy.spec(),
        "split_set": split_set, "split_name": split_name,
        "data_start": datetime.fromtimestamp(result.start, timezone.utc),
        "data_end": datetime.fromtimestamp(result.end, timezone.utc),
        "execution_model": result.execution, "code_version": _code_version(),
        "dataset_fingerprint": result.dataset_fingerprint, "metrics_imitation": metrics_imitation,
        "metrics_performance": perf, "n_trades": perf["n_trades"], "notes": notes,
        "created_at": db.now(), "is_synthetic": is_synthetic})
    return run_id


def run_on_split(con: duckdb.DuckDBPyConnection, *, strategy: Strategy, store: EventStore, split_set: str,
                 split_name: str, execution: ExecutionModel, hypothesis_id: str | None = None,
                 notes: str | None = None, is_synthetic: bool = False) -> tuple[str, SimResult]:
    """Development runs: train or validation only."""
    if split_name not in ("train", "validation"):
        raise ValueError("use evaluate_holdout() for the holdout")
    start, end, _ = get_split(con, split_set, split_name)
    # Earlier history stays visible (tokens created before the split); later data does not exist.
    result = run(strategy, store.until(_ts(end)), start=_ts(start), end=_ts(end), execution=execution)
    run_id = record_run(con, result, strategy=strategy, split_set=split_set, split_name=split_name,
                        hypothesis_id=hypothesis_id, notes=notes, is_synthetic=is_synthetic)
    return run_id, result


def evaluate_holdout(con: duckdb.DuckDBPyConnection, *, strategy: Strategy, store: EventStore, split_set: str,
                     execution: ExecutionModel, hypothesis_id: str, pass_criteria: list[dict],
                     notes: str | None = None, is_synthetic: bool = False) -> tuple[str, bool, SimResult]:
    """The single final test. ``pass_criteria`` e.g. [{"metric": "expectancy_sol", "op": ">", "value": 0}]."""
    db.require(con, "hypotheses", "hypothesis_id", hypothesis_id)
    if not pass_criteria:
        raise ValueError("register pass criteria before looking at the holdout")
    for c in pass_criteria:
        if c.get("op") not in _OPS or "metric" not in c or "value" not in c:
            raise ValueError(f"bad criterion {c}")
    start, end, status = get_split(con, split_set, "holdout")
    if status == "burned":
        db.upsert(con, "holdout_log", {"event_id": new_id("hol"), "split_set": split_set, "split_name": "holdout",
                                       "run_id": None, "strategy_hash": strategy_hash(strategy),
                                       "action": "refused", "reason": "holdout already burned", "logged_at": db.now()})
        raise HoldoutBurnedError(f"holdout of {split_set!r} was already used; define a new, later split set")
    result = run(strategy, store.until(_ts(end)), start=_ts(start), end=_ts(end), execution=execution)
    perf = performance(result)
    checks = []
    for c in pass_criteria:
        v = perf.get(c["metric"])
        checks.append({**c, "actual": v, "passed": v is not None and _OPS[c["op"]](v, c["value"])})
    passed = all(ch["passed"] for ch in checks)
    run_id = record_run(con, result, strategy=strategy, split_set=split_set, split_name="holdout",
                        hypothesis_id=hypothesis_id, is_synthetic=is_synthetic,
                        notes=json.dumps({"pass_criteria": checks, "passed": passed, "notes": notes}))
    con.execute("UPDATE data_splits SET status = 'burned', burned_at = ?, burned_by_run = ? "
                "WHERE split_set = ? AND split_name = 'holdout'", [db.now(), run_id, split_set])
    db.upsert(con, "holdout_log", {"event_id": new_id("hol"), "split_set": split_set, "split_name": "holdout",
                                   "run_id": run_id, "strategy_hash": strategy_hash(strategy),
                                   "action": "evaluated", "reason": "passed" if passed else "failed",
                                   "logged_at": db.now()})
    con.execute("UPDATE hypotheses SET status = ?, updated_at = ? WHERE hypothesis_id = ?",
                ["holdout_passed" if passed else "holdout_failed", db.now(), hypothesis_id])
    return run_id, passed, result
