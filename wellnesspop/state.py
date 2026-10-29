"""Per-session plan state over any mutable mapping (``st.session_state`` in the app).

No module globals, files, URLs, browser storage, or shared caches hold user data.
Validation happens before mutation, so a failed edit leaves the committed plan intact.
"""

from __future__ import annotations

import copy
import datetime as dt
import uuid
from collections.abc import MutableMapping

from wellnesspop import schema as S
from wellnesspop.demos import load_demo
from wellnesspop.planner import (PlanResult, build_plan, empty_edits, input_fingerprint,
                                 run_simulation)
from wellnesspop.validation import Issue, check_plan

KEY = "wellnesspop"


def _state(store: MutableMapping) -> dict:
    if KEY not in store:
        raise RuntimeError("session not initialised")
    return store[KEY]


def init(store: MutableMapping, today: dt.date | None = None) -> None:
    if KEY in store:
        return
    today = today or S.today_in(S.DEFAULT_TZ)
    plan, issues = check_plan(S.default_plan(today), today)
    assert plan is not None, issues
    store[KEY] = {"plan": plan, "revision": 1, "edits": empty_edits(), "simulation": None,
                  "exports": {}, "source": "blank", "import_preview": None,
                  "nonce": uuid.uuid4().hex[:8]}


def plan(store: MutableMapping) -> S.PlanInput:
    return _state(store)["plan"]


def raw(store: MutableMapping) -> dict:
    return plan(store).to_dict()


def revision(store: MutableMapping) -> int:
    return _state(store)["revision"]


def edits(store: MutableMapping) -> dict:
    return copy.deepcopy(_state(store)["edits"])


def _track_provenance(old: S.PlanInput | None, new_raw: dict, today: dt.date) -> dict:
    """Mark changed fields as user-entered, keeping their original provenance."""
    prov = copy.deepcopy(new_raw.get("provenance") or {})
    if old is None:
        return prov
    old_raw = old.to_dict()
    for spec in S.SCALAR_SPECS:
        before, after = S.get_path(old_raw, spec.path), S.get_path(new_raw, spec.path)
        if _norm(before) != _norm(after):
            _mark_user(prov, spec.path, spec.provenance, before, today)
    for group in S.RECORD_SPECS:
        old_rows = {r["id"]: r for r in (old_raw.get(group) or [])}
        for row in new_raw.get(group) or []:
            rid = row.get("id")
            if rid in old_rows and _norm(old_rows[rid]) != _norm(row) or rid not in old_rows:
                _mark_user(prov, f"{group}:{rid}", "illustrative", old_rows.get(rid), today)
    return prov


def _norm(v):
    return S.to_jsonable(v)


def _mark_user(prov: dict, key: str, default_kind: str, before, today: dt.date) -> None:
    rec = prov.get(key, {})
    if rec.get("source_kind") == "user":
        rec["as_of_date"] = today.isoformat()
        prov[key] = rec
        return
    prov[key] = {"source_kind": "user", "source_reference": "Entered by organizer",
                 "as_of_date": today.isoformat(), "note": rec.get("note", ""),
                 "original_source_kind": rec.get("source_kind", default_kind),
                 "original_source_reference": rec.get("source_reference", ""),
                 "original_value": _norm(before)}


def commit_plan(store: MutableMapping, new_raw: dict, today: dt.date | None = None,
                track: bool = True) -> list[Issue]:
    """Validate the whole proposed plan, then commit atomically. Returns issues."""
    s = _state(store)
    candidate = copy.deepcopy(new_raw)
    today = today or S.today_in(S.DEFAULT_TZ)
    if track:
        candidate["provenance"] = _track_provenance(s["plan"], candidate, today)
    new_plan, issues = check_plan(candidate, today)
    if new_plan is None:
        return issues
    s["plan"] = new_plan
    s["revision"] += 1
    s["exports"] = {}
    sim = s.get("simulation")
    if sim is not None and sim.fingerprint != input_fingerprint(new_plan):
        s["simulation"] = None  # invalidate results tied to an older input fingerprint
    return issues


def commit_edits(store: MutableMapping, kind: str, new_edits: dict) -> None:
    s = _state(store)
    s["edits"] = {**s["edits"], kind: copy.deepcopy(new_edits)}
    s["revision"] += 1
    s["exports"] = {}


def reset_edits(store: MutableMapping, kind: str) -> None:
    commit_edits(store, kind, empty_edits()[kind])


def load_demo_into(store: MutableMapping, key: str, today: dt.date | None = None) -> list[Issue]:
    today = today or S.today_in(S.DEFAULT_TZ)
    clear(store, today)
    issues = commit_plan(store, load_demo(key, today), today, track=False)
    _state(store)["source"] = key
    return issues


def clear(store: MutableMapping, today: dt.date | None = None) -> None:
    """Clear Plan: remove inputs, results, uploads, and download buffers from the session."""
    for k in list(store.keys()):
        if str(k).startswith("wp_") or k == KEY:
            del store[k]
    init(store, today)


def result(store: MutableMapping, today: dt.date | None = None) -> PlanResult:
    s = _state(store)
    r = build_plan(s["plan"], s["edits"], today)
    return r.with_simulation(s.get("simulation"))


def simulate(store: MutableMapping, today: dt.date | None = None) -> PlanResult:
    r = result(store, today)
    sim = run_simulation(r)
    _state(store)["simulation"] = sim
    return r.with_simulation(sim)


def cached_export(store: MutableMapping, fingerprint: str, kind: str, builder) -> bytes:
    """Export bytes are kept in session memory and dropped whenever the revision changes."""
    exports = _state(store)["exports"]
    key = (fingerprint, kind)
    if key not in exports:
        for stale in [k for k in exports if k[0] != fingerprint]:
            del exports[stale]
        exports[key] = builder()
    return exports[key]
