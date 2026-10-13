# SDD ledger — plan: docs/superpowers/plans/2026-10-13-storepro.md
Pre-flight: shared database, auth and money interfaces connect all six tasks; consistent.
Ruling: existing /workspace/storepro is isolated from depi; use local implementation branch, no extra worktree — requested cloud guidance and source ZIP project — no impact on depi.
Ruling: original historical sales have no product IDs or cost snapshots; migrate with linked product where uniquely identifiable and mark historical costs unknown rather than invent profits — old reports will flag estimates unavailable.
Task 1: complete — foundation suite 10 passed. Runtime uses workspace .venv after read-only user-site install failed; no global installation.
Ruling: purchase cash payments need active shifts before Task 3; introduce shared cash movement helper now and use fixture shift for Task 2 — preserves transaction interface and cash accounting.
Task 2: complete — catalog/purchases/party tests plus foundation passed (14).
Task 3: complete — full suite 26 passed; sale/debt/refund/shift tests exercised.
Ruling: store net/tax per returned item to preserve rounding in date-filtered reports — schema still version 1 because no released enhanced databases exist.
Ruling: legacy invoice returns require manual documented adjustment, not automatic refunds from missing tax allocations — protects migrated financial integrity; UI will display explanation.
Task 4: complete — reports and backup tests passed; exports include protected spreadsheet cells and Arabic font. CSV test corrected to validate content rather than arbitrary minimum file size.
Task 5: complete — virtual display UI smoke tests passed (2); actual navigation and checkout executed.
Ruling: printing uses browser print dialog with installed Windows printers, not a silent default printer call — explicit selection and standard offline HTML printing.
Ruling: snapshot.debian.org proxy denied; use signed Debian trixie repository in temporary apt configuration, extract verified Xvfb packages only into /tmp — no system changes.
