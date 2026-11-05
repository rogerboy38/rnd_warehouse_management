"""2.3.1 (TASKS-293): the approval-rule button "View Applicable Stock Entries" filters the Stock Entry list with an
EQUALITY on the exact Select option text.

Frappe's filter UI lists `like` as an invalid condition for a Select field (filter.js, invalid_condition_map.Select),
so the 2.3.0 route option ["like", "<code>%"] was dropped and the button opened an unfiltered list. DB-free: the JS
function is run under node in a vm with a stubbed `frappe` (route options, route and messages captured); skipped
if node is not installed. Run as `python tests/test_approval_rule_button.py` (a site-packages `tests` package shadows
`-m unittest tests.x`, as for test_sap_movement_types).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from rnd_warehouse_management.sap_movement_types import SAP_MOVEMENT_TYPES, option_label, select_options  # noqa: E402

JS = os.path.join(ROOT, "rnd_warehouse_management", "rnd_warehouse_management", "doctype",
                  "stock_entry_approval_rule", "stock_entry_approval_rule.js")

RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const cfg = JSON.parse(process.argv[1]);
const src = fs.readFileSync(process.argv[2], "utf8");
const calls = [];
const fmt = (s, a) => (a ? s.replace(/\{(\d+)\}/g, (m, i) => a[i]) : s);
const frappe = {
  ui: { form: { on() {} } },
  model: { with_doctype(dt, cb) { calls.push(["with_doctype", dt]); cb(); } },
  get_meta(dt) { calls.push(["get_meta", dt]); return { fields: cfg.fields }; },
  set_route(...a) { calls.push(["set_route", a]); },
  msgprint(m) { calls.push(["msgprint", typeof m === "string" ? m : (m.message || "")]); },
  call() {}, route_options: undefined,
};
const ctx = vm.createContext({ frappe, __: fmt, console, String, JSON });
vm.runInContext(src, ctx);
vm.runInContext("view_applicable_stock_entries(" + JSON.stringify({ doc: { movement_type: cfg.movement_type } }) + ")", ctx);
process.stdout.write(JSON.stringify({ route_options: frappe.route_options === undefined ? null : frappe.route_options, calls }));
"""


def run(movement_type, options_text=None, fields=None):
    if fields is None:
        fields = [{"fieldname": "custom_sap_movement_type", "fieldtype": "Select",
                   "options": select_options() if options_text is None else options_text}]
    r = subprocess.run(["node", "-e", RUNNER, json.dumps({"movement_type": movement_type, "fields": fields}), JS],
                       capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def routes(out):
    return [c[1] for c in out["calls"] if c[0] == "set_route"]


def messages(out):
    return [c[1] for c in out["calls"] if c[0] == "msgprint"]


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestTheButtonFiltersByTheExactOption(unittest.TestCase):
    def test_every_one_of_the_16_codes_resolves_to_exactly_its_option_with_an_equality_filter(self):
        self.assertEqual(len(SAP_MOVEMENT_TYPES), 16)
        for m in SAP_MOVEMENT_TYPES:
            out = run("MT-" + m["code"])
            self.assertEqual(out["route_options"], {"custom_sap_movement_type": option_label(m)}, m["code"])
            self.assertEqual(routes(out), [["List", "Stock Entry"]], m["code"])
            self.assertEqual(messages(out), [], m["code"])

    def test_a_filter_value_is_a_plain_string_never_a_condition_list(self):
        for m in SAP_MOVEMENT_TYPES:
            v = run("MT-" + m["code"])["route_options"]["custom_sap_movement_type"]
            self.assertIsInstance(v, str)

    def test_the_bare_code_without_the_MT_prefix_works_too(self):
        self.assertEqual(run("561")["route_options"], {"custom_sap_movement_type": "561 (Initial Entry - Stock Balance)"})

    def test_the_source_is_the_stock_entry_meta_loaded_first(self):
        out = run("MT-261")
        self.assertEqual([c for c in out["calls"] if c[0] in ("with_doctype", "get_meta")],
                         [["with_doctype", "Stock Entry"], ["get_meta", "Stock Entry"]])

    def test_a_code_outside_the_list_opens_nothing_and_says_so(self):
        for mt in ("MT-999", "MT-26", "MT-2610", "MT-"):
            out = run(mt)
            self.assertIsNone(out["route_options"], mt)          # no unfiltered list, no route options left behind
            self.assertEqual(routes(out), [], mt)
            self.assertEqual(len(messages(out)), 1, mt)

    def test_an_empty_movement_type_opens_nothing_and_says_so(self):
        for mt in ("", None):
            out = run(mt)
            self.assertEqual((out["route_options"], routes(out), len(messages(out))), (None, [], 1))

    def test_a_site_whose_select_lacks_the_code_does_not_get_an_invented_option(self):
        # e.g. the 2-option field of an older app order: the option the list ships is not in the field -> message, no filter
        out = run("MT-261", options_text="\n261 (FrontFlush - Goods Issue for Production)\n311 (BackFlush - Transfer for Kitting)")
        self.assertEqual(out["route_options"], {"custom_sap_movement_type": "261 (FrontFlush - Goods Issue for Production)"})
        out = run("MT-561", options_text="\n261 (FrontFlush - Goods Issue for Production)\n311 (BackFlush - Transfer for Kitting)")
        self.assertEqual((out["route_options"], routes(out), len(messages(out))), (None, [], 1))

    def test_the_legacy_561_label_stored_on_the_42_entries_is_the_option(self):
        out = run("MT-561")
        self.assertEqual(out["route_options"]["custom_sap_movement_type"], "561 (Initial Entry - Stock Balance)")

    def test_no_field_or_no_options_opens_nothing(self):
        out = run("MT-261", fields=[])
        self.assertEqual((out["route_options"], routes(out), len(messages(out))), (None, [], 1))
        out = run("MT-261", options_text="")
        self.assertEqual((out["route_options"], routes(out), len(messages(out))), (None, [], 1))

    def test_a_code_that_is_a_prefix_of_another_matches_only_its_own_option(self):
        out = run("MT-10", options_text="\n101 (A)\n10 (B)\n1099 (C)")
        self.assertEqual(out["route_options"], {"custom_sap_movement_type": "10 (B)"})


class TestTheFixIsNotALikeOnThisSelect(unittest.TestCase):
    def test_the_function_has_no_like_condition(self):
        src = open(JS, encoding="utf8").read()
        body = src[src.index("function view_applicable_stock_entries"):]
        body = re.sub(r"//[^\n]*", "", body)          # the comments may quote the old condition
        self.assertNotRegex(body, r"""["']like["']""")
        self.assertNotIn("%", body.split("frappe.route_options")[1].split("}")[0])

    def test_the_other_javascript_of_the_file_is_untouched(self):
        src = open(JS, encoding="utf8").read()
        for needle in ("test_conditional_logic(frm)", "get_movement_type_details_for_ui", "evaluate_conditional_logic",
                       "View Applicable Stock Entries"):
            self.assertIn(needle, src)


class TestVersion(unittest.TestCase):
    def test_version_is_2_3_1_or_later_in_both_places(self):
        with open(os.path.join(ROOT, "rnd_warehouse_management", "__version__.py"), encoding="utf8") as f:
            v1 = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf8") as f:
            v2 = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)
        self.assertEqual(v1, v2)
        self.assertGreaterEqual(tuple(int(x) for x in v1.split(".")), (2, 3, 1))


if __name__ == "__main__":
    unittest.main()
