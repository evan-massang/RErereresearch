"""Findings (rule-level conclusions), hypotheses, and the feature registry.

The four evidence types from the research brief are kept apart structurally:

  stated     the trader's own words            -> must cite >=1 'said' observation by that trader
  observed   what the trader actually did       -> must cite decisions / screen|action|onchain
                                                   observations, with counts (n_supporting of n_observable)
  inferred   our interpretation                 -> must be derived_from >=1 stated/observed finding
  validated  survived a quantitative test       -> must cite a sim_run on validation/holdout data
                                                   and be derived_from the finding it validates

A finding's evidence_type never changes. Upgrading an inference means creating a
new validated finding derived_from it, so the trail of what was assumed stays visible.
"""

from __future__ import annotations

from typing import Iterable

import duckdb

from . import db
from .ids import new_id

EVIDENCE_TYPES = {"stated", "observed", "inferred", "validated"}
FUNNEL_STAGES = {"discovery", "attention", "narrative", "matching", "safety", "market", "entry",
                 "sizing", "hold", "exit", "risk", "tooling", "meta"}
FINDING_STATUSES = {"open", "supported", "weakened", "rejected", "superseded"}
RELATIONS = {"supports", "contradicts", "derived_from", "validated_by"}
EVIDENCE_KINDS = {"observation": ("observations", "observation_id"),
                  "decision": ("decisions", "decision_id"),
                  "finding": ("findings", "finding_id"),
                  "sim_run": ("sim_runs", "run_id")}
HYPOTHESIS_STATUSES = {"proposed", "testing", "rejected", "supported_validation", "holdout_passed",
                       "holdout_failed", "retired"}
FEATURE_STATUSES = {"candidate", "in_use", "retired"}

Evidence = tuple[str, str, str] | tuple[str, str, str, str]   # (kind, id, relation[, note])


def _rule_problems(con, finding_id: str) -> list[str]:
    f = con.execute("SELECT evidence_type, trader_id, n_supporting, n_observable, is_synthetic "
                    "FROM findings WHERE finding_id = ?", [finding_id]).fetchone()
    etype, trader_id, n_sup, n_obs, synthetic = f
    links = con.execute("SELECT evidence_kind, evidence_id, relation FROM finding_evidence WHERE finding_id = ?",
                        [finding_id]).fetchall()
    problems = []
    for kind, eid, _ in links:
        table, col = EVIDENCE_KINDS[kind]
        if not db.exists(con, table, col, eid):
            problems.append(f"links missing {kind} {eid}")

    def obs(relation: str, modalities: set[str]) -> list[tuple]:
        ids = [e for k, e, r in links if k == "observation" and r == relation]
        if not ids:
            return []
        return con.execute(
            f"SELECT observation_id, modality, trader_id FROM observations WHERE observation_id IN "
            f"({', '.join('?' for _ in ids)}) AND modality IN ({', '.join('?' for _ in modalities)})",
            [*ids, *modalities]).fetchall()

    def linked_findings(relation: str, types: set[str]) -> list[tuple]:
        ids = [e for k, e, r in links if k == "finding" and r == relation]
        if not ids:
            return []
        return con.execute(
            f"SELECT finding_id FROM findings WHERE finding_id IN ({', '.join('?' for _ in ids)}) "
            f"AND evidence_type IN ({', '.join('?' for _ in types)})", [*ids, *types]).fetchall()

    if etype == "stated":
        said = obs("supports", {"said"})
        if not said:
            problems.append("stated finding needs >=1 supporting 'said' observation (the trader's own words)")
        elif trader_id and any(t != trader_id for _, _, t in said):
            problems.append("stated finding cites words attributed to a different trader (or unattributed)")
    elif etype == "observed":
        decisions = [e for k, e, r in links if k == "decision" and r == "supports"]
        seen = obs("supports", {"screen", "action", "onchain"})
        if not decisions and not seen:
            problems.append("observed finding needs supporting decisions or screen/action/onchain observations")
        if n_sup is None or n_obs is None:
            problems.append("observed finding needs n_supporting and n_observable (e.g. 35 of 42)")
        elif not 0 <= n_sup <= n_obs:
            problems.append("n_supporting must be between 0 and n_observable")
    elif etype == "inferred":
        if not linked_findings("derived_from", {"stated", "observed"}):
            problems.append("inferred finding must be derived_from >=1 stated/observed finding")
    elif etype == "validated":
        runs = [e for k, e, r in links if k == "sim_run" and r == "validated_by"]
        ok_runs = con.execute(
            f"SELECT run_id FROM sim_runs WHERE run_id IN ({', '.join('?' for _ in runs)}) "
            f"AND split_name IN ('validation', 'holdout') AND (NOT is_synthetic OR ?)",
            [*runs, synthetic]).fetchall() if runs else []
        if not ok_runs:
            problems.append("validated finding needs a validated_by sim_run on validation or holdout data")
        if not linked_findings("derived_from", {"stated", "observed", "inferred"}):
            problems.append("validated finding must be derived_from the finding it validates")
    return problems


def add_finding(
    con: duckdb.DuckDBPyConnection,
    *,
    trader_id: str | None,
    funnel_stage: str,
    evidence_type: str,
    statement: str,
    evidence: Iterable[Evidence],
    n_supporting: int | None = None,
    n_observable: int | None = None,
    n_contradicting: int | None = None,
    confidence: float | None = None,
    status: str = "open",
    notes: str | None = None,
    is_synthetic: bool = False,
) -> str:
    """Create a finding and its evidence links atomically; refuse if the rules for its type fail."""
    db.require(con, "traders", "trader_id", trader_id)
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"evidence_type must be one of {sorted(EVIDENCE_TYPES)}")
    if funnel_stage not in FUNNEL_STAGES:
        raise ValueError(f"funnel_stage must be one of {sorted(FUNNEL_STAGES)}")
    if status not in FINDING_STATUSES or status == "superseded":
        raise ValueError("status must be open/supported/weakened/rejected at creation")
    if not statement.strip():
        raise ValueError("statement is required")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    finding_id = new_id("fnd")
    con.execute("BEGIN TRANSACTION")
    try:
        db.upsert(con, "findings", {
            "finding_id": finding_id, "trader_id": trader_id, "funnel_stage": funnel_stage,
            "evidence_type": evidence_type, "statement": statement.strip(), "n_supporting": n_supporting,
            "n_observable": n_observable, "n_contradicting": n_contradicting, "confidence": confidence,
            "status": status, "superseded_by": None, "notes": notes, "created_at": db.now(),
            "updated_at": db.now(), "is_synthetic": is_synthetic,
        })
        for ev in evidence:
            _link(con, finding_id, *ev)
        problems = _rule_problems(con, finding_id)
        if problems:
            raise ValueError("; ".join(problems))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return finding_id


def _link(con, finding_id: str, kind: str, evidence_id: str, relation: str, note: str | None = None) -> None:
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"evidence kind must be one of {sorted(EVIDENCE_KINDS)}")
    if relation not in RELATIONS:
        raise ValueError(f"relation must be one of {sorted(RELATIONS)}")
    table, col = EVIDENCE_KINDS[kind]
    db.require(con, table, col, evidence_id)
    if kind == "finding" and evidence_id == finding_id:
        raise ValueError("a finding cannot cite itself")
    db.upsert(con, "finding_evidence", {"finding_id": finding_id, "evidence_kind": kind,
                                        "evidence_id": evidence_id, "relation": relation, "note": note})


def link_evidence(con: duckdb.DuckDBPyConnection, finding_id: str, kind: str, evidence_id: str,
                  relation: str, note: str | None = None) -> None:
    """Add evidence to an existing finding (e.g. a contradicting case found later)."""
    db.require(con, "findings", "finding_id", finding_id)
    _link(con, finding_id, kind, evidence_id, relation, note)
    con.execute("UPDATE findings SET updated_at = ? WHERE finding_id = ?", [db.now(), finding_id])


def set_finding_status(con: duckdb.DuckDBPyConnection, finding_id: str, status: str, note: str,
                       superseded_by: str | None = None) -> None:
    db.require(con, "findings", "finding_id", finding_id)
    if status not in FINDING_STATUSES:
        raise ValueError(f"status must be one of {sorted(FINDING_STATUSES)}")
    if status == "superseded":
        db.require(con, "findings", "finding_id", superseded_by)
        if not superseded_by:
            raise ValueError("superseded needs superseded_by")
    if not note.strip():
        raise ValueError("a status change needs a note saying why")
    con.execute(
        "UPDATE findings SET status = ?, superseded_by = ?, updated_at = ?, "
        "notes = concat_ws(' | ', notes, ?) WHERE finding_id = ?",
        [status, superseded_by, db.now(), note, finding_id])


def update_counts(con: duckdb.DuckDBPyConnection, finding_id: str, *, n_supporting: int, n_observable: int,
                  n_contradicting: int | None = None, note: str) -> None:
    """Counts change as more videos are coded; the type of the finding does not."""
    db.require(con, "findings", "finding_id", finding_id)
    if not 0 <= n_supporting <= n_observable:
        raise ValueError("n_supporting must be between 0 and n_observable")
    con.execute(
        "UPDATE findings SET n_supporting = ?, n_observable = ?, n_contradicting = ?, updated_at = ?, "
        "notes = concat_ws(' | ', notes, ?) WHERE finding_id = ?",
        [n_supporting, n_observable, n_contradicting, db.now(), note, finding_id])


def check_integrity(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Re-check every finding against its type's rules (catches edits made outside this module)."""
    out = {}
    for (fid,) in con.execute("SELECT finding_id FROM findings ORDER BY created_at").fetchall():
        problems = _rule_problems(con, fid)
        if problems:
            out[fid] = problems
    # hypotheses must still rest on what they were registered on
    for hid, n_basis, n_missing, parent in con.execute("""
            SELECT h.hypothesis_id, count(b.finding_id), count(b.finding_id) FILTER (WHERE f.finding_id IS NULL),
                   h.parent_id
            FROM hypotheses h LEFT JOIN hypothesis_basis b USING (hypothesis_id)
            LEFT JOIN findings f ON f.finding_id = b.finding_id GROUP BY h.hypothesis_id, h.parent_id""").fetchall():
        problems = []
        if n_missing:
            problems.append(f"{n_missing} basis finding(s) no longer exist")
        if parent is None and n_basis - n_missing == 0:
            problems.append("root hypothesis has no basis finding")
        if problems:
            out[hid] = problems
    return out


# ------------------------------------------------------------------ hypotheses

def add_hypothesis(
    con: duckdb.DuckDBPyConnection,
    *,
    statement: str,
    measurable_definition: str,
    rationale: str,
    basis_finding_ids: list[str] | None = None,
    parent_id: str | None = None,
    motivated_by_run_id: str | None = None,
    trader_scope: str | None = None,
    is_synthetic: bool = False,
) -> str:
    """A testable hypothesis. Every iteration must say why it exists.

    Root hypotheses must rest on >=1 finding. Refinements (parent_id set) must cite
    either the run whose failure motivated them or >=1 finding the parent did not use.
    """
    basis = list(dict.fromkeys(basis_finding_ids or []))
    for fid in basis:
        db.require(con, "findings", "finding_id", fid)
    db.require(con, "hypotheses", "hypothesis_id", parent_id)
    db.require(con, "sim_runs", "run_id", motivated_by_run_id)
    for field, value in (("statement", statement), ("measurable_definition", measurable_definition),
                         ("rationale", rationale)):
        if not value or not value.strip():
            raise ValueError(f"{field} is required")
    if parent_id is None and not basis:
        raise ValueError("a root hypothesis must rest on at least one finding")
    if parent_id is not None:
        parent_basis = {r[0] for r in con.execute(
            "SELECT finding_id FROM hypothesis_basis WHERE hypothesis_id = ?", [parent_id]).fetchall()}
        if not motivated_by_run_id and not (set(basis) - parent_basis):
            raise ValueError("a refinement must cite the run that motivated it or new evidence (findings)")
    hypothesis_id = new_id("hyp")
    db.upsert(con, "hypotheses", {
        "hypothesis_id": hypothesis_id, "parent_id": parent_id, "trader_scope": trader_scope,
        "statement": statement.strip(), "measurable_definition": measurable_definition.strip(),
        "rationale": rationale.strip(), "motivated_by_run_id": motivated_by_run_id, "status": "proposed",
        "created_at": db.now(), "updated_at": db.now(), "is_synthetic": is_synthetic,
    })
    for fid in basis:
        db.upsert(con, "hypothesis_basis", {"hypothesis_id": hypothesis_id, "finding_id": fid})
    return hypothesis_id


def set_hypothesis_status(con: duckdb.DuckDBPyConnection, hypothesis_id: str, status: str) -> None:
    db.require(con, "hypotheses", "hypothesis_id", hypothesis_id)
    if status not in HYPOTHESIS_STATUSES:
        raise ValueError(f"status must be one of {sorted(HYPOTHESIS_STATUSES)}")
    con.execute("UPDATE hypotheses SET status = ?, updated_at = ? WHERE hypothesis_id = ?",
                [status, db.now(), hypothesis_id])


def hypothesis_lineage(con: duckdb.DuckDBPyConnection, hypothesis_id: str) -> list[dict]:
    """Root-first chain of a hypothesis and its ancestors, with the reason for each step."""
    chain = []
    current = hypothesis_id
    while current:
        row = con.execute("SELECT hypothesis_id, parent_id, statement, rationale, motivated_by_run_id, status "
                          "FROM hypotheses WHERE hypothesis_id = ?", [current]).fetchone()
        if row is None:
            raise ValueError(f"unknown hypothesis_id {current!r}")
        chain.append(dict(zip(["hypothesis_id", "parent_id", "statement", "rationale",
                               "motivated_by_run_id", "status"], row)))
        current = row[1]
    return list(reversed(chain))


# ------------------------------------------------------------------ features

def register_feature(con: duckdb.DuckDBPyConnection, name: str, *, human_observation: str, definition: str,
                     inputs: str | None = None, min_resolution_s: float | None = None,
                     implementation: str | None = None, status: str = "candidate",
                     notes: str | None = None, is_synthetic: bool = False) -> str:
    if status not in FEATURE_STATUSES:
        raise ValueError(f"status must be one of {sorted(FEATURE_STATUSES)}")
    if not human_observation.strip() or not definition.strip():
        raise ValueError("human_observation and definition are required")
    db.upsert(con, "features", {
        "feature_name": name, "human_observation": human_observation, "definition": definition,
        "inputs": inputs, "min_resolution_s": min_resolution_s, "implementation": implementation,
        "status": status, "notes": notes, "created_at": db.now(), "is_synthetic": is_synthetic,
    })
    return name


def reregister_hypothesis(con: duckdb.DuckDBPyConnection, prefix: str, **kw) -> str:
    """Re-run-safe add_hypothesis for scripts that rebuild their findings.

    If a hypothesis whose statement starts with ``prefix`` exists, it is rebuilt on the new basis
    findings but keeps its id, status and original created_at (its pre-registration time), so runs
    stay linked. Changing an existing hypothesis's measurable definition is refused: a changed test
    is a new hypothesis (a child with its own rationale), never an edit of a registered one.
    """
    old = con.execute("SELECT hypothesis_id, created_at, measurable_definition, status FROM hypotheses "
                      "WHERE statement LIKE ?", [prefix + "%"]).fetchall()
    if len(old) > 1:
        raise ValueError(f"{len(old)} hypotheses start with {prefix!r}")
    if old and old[0][2] != kw["measurable_definition"]:
        raise ValueError(f"{prefix} is pre-registered with a different measurable definition; "
                         "register a child hypothesis instead of editing it")
    if old:
        con.execute("DELETE FROM hypothesis_basis WHERE hypothesis_id = ?", [old[0][0]])
        con.execute("DELETE FROM hypotheses WHERE hypothesis_id = ?", [old[0][0]])
    new = add_hypothesis(con, **kw)
    if not old:
        return new
    oid, created, _, status = old[0]
    con.execute("UPDATE hypotheses SET hypothesis_id = ?, created_at = ?, status = ? WHERE hypothesis_id = ?",
                [oid, created, status, new])
    con.execute("UPDATE hypothesis_basis SET hypothesis_id = ? WHERE hypothesis_id = ?", [oid, new])
    return oid


def clear_previous(con: duckdb.DuckDBPyConnection, tag: str, extractor: str) -> list[str]:
    """For scripts that rebuild their findings: delete their earlier findings and observations, except
    findings a hypothesis rests on (and the observations those cite). Returns the kept finding ids, which the
    caller marks superseded by the rebuilt finding, so a registered hypothesis never loses its basis."""
    kept = [r[0] for r in con.execute(
        "SELECT finding_id FROM findings WHERE notes LIKE ? AND finding_id IN (SELECT finding_id FROM hypothesis_basis) "
        "AND status <> 'superseded'", [f"%{tag}%"]).fetchall()]
    con.execute("DELETE FROM finding_evidence WHERE finding_id IN (SELECT finding_id FROM findings WHERE notes LIKE ?) "
                "AND finding_id NOT IN (SELECT finding_id FROM hypothesis_basis)", [f"%{tag}%"])
    con.execute("DELETE FROM findings WHERE notes LIKE ? AND finding_id NOT IN (SELECT finding_id FROM hypothesis_basis)",
                [f"%{tag}%"])
    con.execute("DELETE FROM observations WHERE extractor = ? AND observation_id NOT IN "
                "(SELECT evidence_id FROM finding_evidence WHERE evidence_kind = 'observation')", [extractor])
    return kept
