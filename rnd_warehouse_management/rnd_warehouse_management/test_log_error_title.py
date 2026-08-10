"""Guard: `frappe.log_error()` must be given a CONSTANT title.  [PORTABLE TEMPLATE]

Origin: amb_w_tds `cd9f7fd` (`amb_w_tds/amb_w_tds/test_log_error_title.py`, 18 tests,
registered in that app's PROTECTED_SUITES tier 1). This copy is app-agnostic: everything
that must change per app is in CONFIG below. Nothing else should need editing.

THE DEFECT
----------
`frappe.log_error(title, message)` writes `title` into `Error Log.method`, a `varchar(140)`.
Passing the long detail first puts it in that column. frappe's swap heuristic
(`frappe/utils/error.py:48-52`) only fires when the title contains a NEWLINE, so a
single-line f-string is never rescued. Reproduced end-to-end:

    Error Log.validate()      truncates method to 140       error_log.py:32-34
    document.py:792  _validate_length()   PASSES            140 == varchar(140)
    document.py:797  _sanitize_content()  -> 149            BeautifulSoup closes the
                                                            split-open tag
    => over by 9 -> (1406) Data too long

raised from inside the `except` block written to CONTAIN the original error, so it escapes
the handler and can abort the caller.

TWO FAMILIES, ONE INVARIANT -- and they are easy to miscount separately:
  * single-arg   `log_error(f"...{e}...")`            -- message is None, title unbounded
  * two-arg      `log_error(f"...{e}...", "Title")`   -- args in the wrong order
Both put an unbounded string in `method`. Count them together or you will report a subset.

THE INVARIANT
-------------
The `title` argument (first positional, or `title=`) must be a string LITERAL of at most
140 characters. A bare `log_error()` is fine: frappe defaults the title and captures the
real traceback.

Mechanical, no special cases. Some calls pass `frappe.get_traceback()`, which IS rescued at
runtime because its newlines trigger the swap -- flag them anyway. A checker that reasons
about which unbounded titles happen to be safe is a checker with holes in it.

PER-APP CHECKLIST (all four, or the guard is decorative)
--------------------------------------------------------
1. APP_ROOT -- set `PARENTS_UP` so it resolves to the repo root. `test_app_root_resolves`
   asserts it, because a wrong root scans the wrong tree and reports a clean bill.
2. EXCLUDE_PREFIXES -- vendored/backup copies. rnd_warehouse_management ships a full second
   copy of the app under `.git_backup_20260428_155959/`; counting it inflates the debt and
   fixing it fixes nothing that runs.
3. COVERAGE FLOORS -- re-derive per app. Too high and the guard always fails; too low and a
   shrunken walk reports clean. Rule of thumb: ~80% of today's measured counts.
4. KNOWN_DEBT -- GENERATE it, never transcribe it:  python test_log_error_title.py --baseline
   For an app being fixed to zero in the same diff, leave KNOWN_DEBT empty and put the app in
   MUST_BE_CLEAN -- that asserts zero app-wide and is the strongest form.

PROVE IT CAN FAIL BEFORE YOU TRUST IT. Four controls, each reverted afterwards:
  A  add a violation in a new file      -> test_no_unlisted_file_has_violations
  B  re-invert an already-fixed call    -> test_named_files_are_clean if its file is in
                                           MUST_BE_CLEAN, otherwise
                                           test_no_file_exceeds_its_baseline (verified on
                                           rnd_warehouse_management: re-inverting the D1 fix
                                           at tasks.py:49 takes that file 3 -> 4 and fires)
  C  FIX one baselined violation        -> test_baseline_is_not_stale
  D  add an unparsable file             -> test_every_file_parses
Control D is not optional: it is what caught the original version letting SyntaxError escape
setUpClass, so only 10 of 18 tests ran and the parse test never reported. A file that will
not parse contributes zero violations and would otherwise read as an improvement.
"""

import ast
import collections
import pathlib
import sys
import unittest

# ===================== CONFIG -- the only per-app section =====================

#: Directory levels from this file up to the repo root. Verified by a test below.
PARENTS_UP = 2

#: A file proving APP_ROOT is the right tree (relative to APP_ROOT).
ROOT_MARKER = "rnd_warehouse_management/hooks.py"

#: Path prefixes (relative to APP_ROOT) excluded from the scan. Vendored or
#: backup copies of the app itself belong here.
EXCLUDE_PREFIXES = (
    ".git_backup",
)

#: Coverage floors -- re-derive per app (see checklist item 3).
#: RE-DERIVED by VM3 on its own branch @ 796a140 with --baseline, per Reconciliation 6 §1
#: (derive your own numbers, do not inherit): 67 files scanned, 38 log_error calls,
#: 35 non-conforming across 16 files, 0 unparsable. Generator-suggested 80% floors below.
#: NOTE the generator's 35 supersedes VM3's hand-derived "~33 vulnerable of 41" census: that
#: count included 3 hits inside .git_backup (now excluded, 41-3 = 38 calls, which matches),
#: treated 1 traceback-first call as safe (the guard flags it deliberately) and left 5
#: multi-line calls unclassified (the AST resolves them). Pre-agreed: the generator wins.
MIN_FILES_SCANNED = 53
MIN_CALLS_FOUND = 30

#: file -> non-conforming count. GENERATE with `--baseline`; never hand-write.
#: Derived on rnd_warehouse_management @ d45e31e (VM3's branch) under R1-FINAL (two sites).
#: RE-GENERATE on your own branch before committing -- per Reconciliation 6 §1, derive your
#: own numbers, do not inherit these.
KNOWN_DEBT = {
    "rnd_warehouse_management/api/api.py": 1,
    "rnd_warehouse_management/patches/v1_0/create_default_workflows.py": 1,
    "rnd_warehouse_management/patches/v1_0/install_print_formats.py": 2,
    "rnd_warehouse_management/patches/v1_0/setup_custom_roles.py": 1,
    "rnd_warehouse_management/patches/v1_0/update_existing_stock_entries.py": 1,
    "rnd_warehouse_management/rnd_warehouse_management/doctype/movement_type_master/movement_type_master.py": 1,
    "rnd_warehouse_management/rnd_warehouse_management/doctype/stock_entry_approval_rule/stock_entry_approval_rule.py": 1,
    "rnd_warehouse_management/rnd_warehouse_management/doctype/stock_entry_audit_log/stock_entry_audit_log.py": 1,
    "rnd_warehouse_management/rnd_warehouse_management/qi_automation.py": 2,
    "rnd_warehouse_management/rnd_warehouse_management/skills/warehouse.py": 1,
    "rnd_warehouse_management/rnd_warehouse_management/stock_entry.py": 2,
    "rnd_warehouse_management/rnd_warehouse_management/tasks.py": 3,
    "rnd_warehouse_management/rnd_warehouse_management/utils.py": 10,
    "rnd_warehouse_management/rnd_warehouse_management/warehouse.py": 3,
    "rnd_warehouse_management/rnd_warehouse_management/warehouse_monitoring.py": 3,
    "rnd_warehouse_management/rnd_warehouse_management/work_order.py": 2,
}

#: Files that must be and stay at ZERO.
#: ⚠ EMPTY UNDER R1-FINAL, DELIBERATELY. My first version listed tasks.py and work_order.py
#: here, assuming R1 would take all seven of their sites to zero. R1 was re-ruled to the TWO
#: abort-path sites (Reconciliation 6 §1), so those files legitimately still carry 3 and 2.
#: Listing them made this guard RED on the branch and would have blocked SHA_FINAL.
#: The two fixed sites are still protected -- by the RATCHET, not by this tuple: re-inverting
#: either one pushes its file above its KNOWN_DEBT baseline and fails
#: `test_no_file_exceeds_its_baseline`. Protection moved from "must be zero" to "must not get
#: worse", which is exactly what an accepted-latent-risk ruling means.
MUST_BE_CLEAN = ()

# =============================================================================

APP_ROOT = pathlib.Path(__file__).resolve().parents[PARENTS_UP]
MAX_TITLE_LEN = 140          # Error Log.method is varchar(140)


def _title_node(call):
    for keyword in call.keywords:
        if keyword.arg == "title":
            return keyword.value
    if call.args:
        return call.args[0]
    return None


def _is_conforming(node):
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value) <= MAX_TITLE_LEN
    )


def scan_source(source):
    """(violating line numbers, total log_error calls). Raises SyntaxError."""
    tree = ast.parse(source)
    violations, total = [], 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr if isinstance(func, ast.Attribute)
            else func.id if isinstance(func, ast.Name)
            else None
        )
        if name != "log_error":
            continue
        total += 1
        title = _title_node(node)
        if title is None:
            continue
        if not _is_conforming(title):
            violations.append(node.lineno)
    return violations, total


ScanResult = collections.namedtuple(
    "ScanResult", "per_file files_scanned calls_found unparsable"
)


def scan_app():
    """Walk the app. Unparsable files are COLLECTED, not raised past -- letting the
    SyntaxError escape aborts setUpClass and the dedicated parse test never runs."""
    per_file = collections.Counter()
    files_scanned = calls_found = 0
    unparsable = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = str(path.relative_to(APP_ROOT))
        if "/node_modules/" in str(path) or rel.startswith(EXCLUDE_PREFIXES):
            continue
        files_scanned += 1
        try:
            violations, total = scan_source(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except SyntaxError as exc:
            unparsable.append(f"{rel}: {exc.msg} (line {exc.lineno})")
            continue
        calls_found += total
        if violations:
            per_file[rel] = len(violations)
    return ScanResult(per_file, files_scanned, calls_found, unparsable)


class TestScannerItself(unittest.TestCase):
    """Paired controls: neither a dead detector nor a flag-everything detector passes."""

    def test_fstring_title_is_flagged(self):
        self.assertEqual(scan_source('frappe.log_error(f"failed: {e}", "T")')[0], [1])

    def test_variable_title_is_flagged(self):
        self.assertEqual(scan_source('frappe.log_error(msg, "T")')[0], [1])

    def test_call_expression_title_is_flagged(self):
        self.assertEqual(scan_source('frappe.log_error(frappe.get_traceback(), "T")')[0], [1])

    def test_single_argument_variable_title_is_flagged(self):
        self.assertEqual(scan_source('frappe.log_error(str(e))')[0], [1])

    def test_overlong_literal_title_is_flagged(self):
        src = 'frappe.log_error("%s", "x")' % ("A" * (MAX_TITLE_LEN + 1))
        self.assertEqual(scan_source(src)[0], [1])

    def test_literal_title_positional_is_clean(self):
        self.assertEqual(scan_source('frappe.log_error("Zone Status", f"d {e}")')[0], [])

    def test_literal_title_keyword_is_clean(self):
        self.assertEqual(
            scan_source('frappe.log_error(title="Zone Status", message=f"d {e}")')[0], []
        )

    def test_no_title_is_clean(self):
        self.assertEqual(scan_source('frappe.log_error()')[0], [])

    def test_keyword_title_wins_over_positional(self):
        self.assertEqual(scan_source('frappe.log_error(f"long {e}", title="S")')[0], [])

    def test_unrelated_calls_are_ignored(self):
        self.assertEqual(scan_source('frappe.msgprint(f"x {e}")\nlogger.error(f"y {e}")'), ([], 0))


class TestScanCoverage(unittest.TestCase):
    """The denominator. Zero violations from a scan of nothing is not a pass."""

    @classmethod
    def setUpClass(cls):
        cls.scan = scan_app()

    def test_app_root_resolves_to_the_app(self):
        self.assertTrue(
            (APP_ROOT / ROOT_MARKER).is_file(),
            f"APP_ROOT {APP_ROOT} does not contain {ROOT_MARKER}; PARENTS_UP is wrong "
            f"and the scan is measuring the wrong tree",
        )

    def test_enough_files_were_scanned(self):
        self.assertGreaterEqual(
            self.scan.files_scanned, MIN_FILES_SCANNED,
            f"only {self.scan.files_scanned} files scanned (floor {MIN_FILES_SCANNED})",
        )

    def test_enough_log_error_calls_were_found(self):
        self.assertGreaterEqual(
            self.scan.calls_found, MIN_CALLS_FOUND,
            f"only {self.scan.calls_found} log_error calls found "
            f"(floor {MIN_CALLS_FOUND}); if the detector stopped matching, "
            f"every file reads as clean",
        )

    def test_every_file_parses(self):
        self.assertEqual(
            self.scan.unparsable, [],
            "files the scanner could not parse (counted as zero violations, so this "
            "is a hole, not a pass):\n  " + "\n  ".join(self.scan.unparsable),
        )


class TestLogErrorTitleRatchet(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.per_file = scan_app().per_file

    def test_named_files_are_clean(self):
        for rel in MUST_BE_CLEAN:
            with self.subTest(file=rel):
                self.assertEqual(
                    self.per_file.get(rel, 0), 0,
                    f"{rel} must pass a constant title to every frappe.log_error(). "
                    f"An unbounded title reaches Error Log.method (varchar 140) and "
                    f"can raise 1406 from inside the except block.",
                )

    def test_no_unlisted_file_has_violations(self):
        new = sorted(set(self.per_file) - set(KNOWN_DEBT) - set(MUST_BE_CLEAN))
        self.assertEqual(
            new, [],
            "new file(s) pass a non-constant title:\n  "
            + "\n  ".join(f"{f} ({self.per_file[f]})" for f in new)
            + "\nUse frappe.log_error(title='Short Constant', message=f'...detail...').",
        )

    def test_no_file_exceeds_its_baseline(self):
        worse = [
            (f, KNOWN_DEBT[f], self.per_file.get(f, 0))
            for f in KNOWN_DEBT if self.per_file.get(f, 0) > KNOWN_DEBT[f]
        ]
        self.assertEqual(worse, [], f"debt INCREASED: {worse}")

    def test_baseline_is_not_stale(self):
        """Failing here is good news -- a file was fixed. Lower its number."""
        better = [
            (f, KNOWN_DEBT[f], self.per_file.get(f, 0))
            for f in KNOWN_DEBT if self.per_file.get(f, 0) < KNOWN_DEBT[f]
        ]
        self.assertEqual(
            better, [],
            f"debt REDUCED but KNOWN_DEBT still claims the old number: {better}. "
            f"Lower it in the same commit (delete the entry at 0).",
        )


def _print_baseline():
    """`python test_log_error_title.py --baseline` -- derive, never transcribe."""
    scan = scan_app()
    print(f"# scanned {scan.files_scanned} files, {scan.calls_found} log_error calls")
    print(f"# unparsable: {len(scan.unparsable)}")
    print("KNOWN_DEBT = {")
    for f in sorted(scan.per_file):
        print(f'    "{f}": {scan.per_file[f]},')
    print("}")
    print(f"# total non-conforming: {sum(scan.per_file.values())} "
          f"across {len(scan.per_file)} files")
    print(f"# suggested floors: MIN_FILES_SCANNED = {int(scan.files_scanned * 0.8)}  "
          f"MIN_CALLS_FOUND = {int(scan.calls_found * 0.8)}")


if __name__ == "__main__":
    if "--baseline" in sys.argv:
        _print_baseline()
    else:
        unittest.main()
