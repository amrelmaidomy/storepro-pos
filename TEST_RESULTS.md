# Validation — 2026-10-13

- `DISPLAY=:99 XDG_CACHE_HOME=/tmp/storepro-fontcache .venv-tk/bin/python -m pytest -q`: **48 passed**, zero failed or skipped in the final display-enabled run.
- Foundation: authentication, permissions, transactions, exact numeric precision, legacy migration and duplicate barcodes.
- Inventory/purchases: unique barcodes, Arabic lookup, fractional stock, weighted cost, duplicate receipt prevention, returns, supplier balances.
- Sales/shifts: stock rollback, duplicate checkout prevention, payment/change, credit permission, tax/discount, cumulative partial refunds, cash reconciliation and shift ownership.
- Reports/backup: historical cost, returns, date filters, CSV/XLSX/PDF, spreadsheet formula protection, Arabic receipts, integrity/schema rejection and safe restore.
- UI: real startup/navigation, cart checkout, invalid quantity, visible payment controls, Arabic visual labels/logical choice keys, exact barcode priority, refreshed permissions on open admin pages.
- Full workflow: purchase → sale on credit → refund → collect/pay balances → close shift → backup → restore.
- OS-backed single-instance lock tested on Linux.
- `compileall` and installed dependency check: passed.
- PyInstaller build with `StorePro.spec`: passed on Linux; frozen initial setup startup created version-1 DB without logged errors.

Independent review found four Important issues (barcode/ID priority, duplicate legacy barcodes, Decimal context rounding, stale export permissions); all were reproduced and fixed with regression tests. No Critical findings reported.

## Still requires Windows hardware

Windows executable build, Windows locking branch, actual receipt printer and paper layout. The ZIP is source code with a Windows build script, not a validated Windows exe. Tk9 in the preinstalled Linux runtime lacked Arabic glyph rendering; GUI was validated with system Python 3.13 and Tk8.6. Minor ledger limitation: party-payment rows do not directly retain cash/card method; cash movements are separately recorded.

See README_AR.md for operations, migration rules, scopes and limitations, and progress.md for implementation decisions.


# UI redesign validation — 2026-10-14

Display-enabled suite: **66 passed** after product-card/checkout redesign. Covers live search/categories, cart +/- and fractional quantities, default exact cash/change, card/mixed/credit payment, duplicate submission, modal cancellation, shift opening, drafts across navigation, logout clearing, refreshed product price, normal display units, click on product label, and payment visibility at 1060x780 and 1360x900.

Independent UI review identified unsellable fractional remaining stock and six-significant-digit rounding in quantity controls. Both were reproduced and fixed with regressions; clicking labels inside cards was also verified and fixed. Existing business-service regressions remain green. python-bidi 0.6.11 used in validation. All runtime requirements resolved as binary/pure-Python wheels for Windows x64 CPython3.14; this verifies package availability, not native Windows UI execution.

Additional DPI regression: CustomTkinter5.2.2 dropdowns retained scaling callbacks after destruction. Shared ComboBox wrapper unregisters those callbacks before destroying menus. Scaling after repeated navigation tested RED→GREEN, with manual 125% widget scaling and expanded payment details at both supported sizes.
