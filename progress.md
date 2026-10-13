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
Final review: independent gpt-6-astra reviewer, read-only. Four Important findings reproduced and fixed in one pass; no Critical findings.
Final: fixed exact Decimal precision/overflow — 4 regression inputs RED→GREEN.
Final: fixed migration of duplicate legacy barcodes — preserves all products and original legacy table; secondary duplicate loses active barcode and gets migration notice; RED→GREEN.
Final: fixed barcode-vs-ID collision — exact barcode wins; RED→GREEN.
Final: fixed stale admin read/export privileges — refreshed guards on callbacks and authenticated backup export; 8 callback regressions RED→GREEN.
Final: fixed cart controls clipping — total label previously unmapped; RED→GREEN.
Final: fixed Arabic label/choice rendering — shaped visual labels preserve logical choice keys; RED→GREEN.
Ruling: Tk9 in preinstalled Python lacks Xft Arabic glyph support; verify UI using available system Python3.13/Tk8.6 in second workspace venv — Windows build still requires native validation.
Ruling: legacy duplicated barcode keeps earliest-ID product barcode and clears later active duplicates with visible migration notice; originals remain archived — user must assign replacements to scan affected products.
Ruling: single-instance OS lock prevents simultaneous UI processes accessing data during restore — Windows lock branch requires Windows verification.
Final: minor (deferred): party payments are recorded against general account balance without method/unique payment reference on party_moves; cash movements remain traceable, card method cannot be read directly from party ledger.
Task 6: validation — 48 tests passed under Python3.13/Tk8.6 with Xvfb; compileall and dependency check passed. PyInstaller Linux build succeeded and frozen first-run startup initialized schema v1 without logged errors. Windows build/physical printing remain unverified.
Ruling: user explicitly requests downloadable enhanced source ZIP; retain local implementation branch and omit merge/PR menu — no integration target or remote requested.
