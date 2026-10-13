# SDD ledger — plan: docs/superpowers/plans/2026-10-13-storepro.md
Pre-flight: shared database, auth and money interfaces connect all six tasks; consistent.
Ruling: existing /workspace/storepro is isolated from depi; use local implementation branch, no extra worktree — requested cloud guidance and source ZIP project — no impact on depi.
Ruling: original historical sales have no product IDs or cost snapshots; migrate with linked product where uniquely identifiable and mark historical costs unknown rather than invent profits — old reports will flag estimates unavailable.
Task 1: complete — foundation suite 10 passed. Runtime uses workspace .venv after read-only user-site install failed; no global installation.
Ruling: purchase cash payments need active shifts before Task 3; introduce shared cash movement helper now and use fixture shift for Task 2 — preserves transaction interface and cash accounting.
