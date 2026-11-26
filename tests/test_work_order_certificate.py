"""TASKS-384 B2 (Work Order form): "Certificate" on a saved Work Order works through the order's lot record.

The certificate belongs to the lot record (Batch AMB). The button looks for the lot records whose `work_order_ref`
is this order: none -> a message that a lot record is needed first; one -> the certificates app is asked for a
certificate of that lot; several -> the user chooses, then the same call. Containers (level 3 and below) are not
offered. The server's answer {doctype, name} is opened; a refusal is the server's own message.

DB-free: the form script is run under node in a vm with a stubbed `frappe` (calls, prompts, routes and messages
captured); skipped if node is not installed. Run as `python tests/test_work_order_certificate.py` (a site-packages
`tests` package shadows `-m unittest tests.x`, as for the other tests here).
"""
import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JS = os.path.join(ROOT, "rnd_warehouse_management", "public", "js", "work_order.js")
MAKE = "amb_w_tds.api.certificate.make_certificate_for_lot"

RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const cfg = JSON.parse(process.argv[1]);
const src = fs.readFileSync(process.argv[2], "utf8");
const out = { buttons: [], calls: [], prompts: [], routes: [], msgs: [] };
const fmt = (s, a) => (a ? s.replace(/\{(\d+)\}/g, (m, i) => a[i]) : s);
let handlers = {};
const frappe = {
  ui: { form: { on(dt, h) { if (dt === "Work Order") handlers = h; } } },
  call(opts) {
    out.calls.push({ method: opts.method, args: opts.args });
    if (opts.method === "frappe.client.get_list") { if (cfg.list_reply !== undefined) opts.callback(cfg.list_reply); }
    else if (cfg.make_reply !== undefined) opts.callback(cfg.make_reply);
  },
  prompt(fields, cb, title, primary) {
    out.prompts.push({ fields, title, primary });
    if (cfg.choose !== undefined) cb(cfg.choose === null ? {} : { lot: cfg.choose });
  },
  set_route(...a) { out.routes.push(a); },
  msgprint(m) { out.msgs.push(typeof m === "string" ? m : (m.message || "")); },
};
const ctx = vm.createContext({ frappe, __: fmt, console, String, JSON, Boolean,
  rnd_warehouse_management: { utils: { get_zone_badge: () => "" } } });
vm.runInContext(src, ctx);
const frm = {
  doc: { name: cfg.name, docstatus: cfg.docstatus },
  is_new: () => cfg.is_new,
  set_intro() {},
  add_custom_button(label, fn, group) { out.buttons.push([label, group || null]); if (label === "Certificate") frm._cert = fn; },
};
handlers.refresh(frm);
if (frm._cert && cfg.click) frm._cert();
process.stdout.write(JSON.stringify(out));
"""


def run(lots=None, **cfg):
    cfg.setdefault("name", "WO-0001")
    cfg.setdefault("docstatus", 1)
    cfg.setdefault("is_new", False)
    cfg.setdefault("click", True)
    if lots is not None:
        cfg["list_reply"] = {"message": lots}
    r = subprocess.run(["node", "-e", RUNNER, json.dumps(cfg), JS], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def lot(name, level="1", **kw):
    return dict({"name": name, "title": name, "custom_batch_level": level, "quality_status": "Pending"}, **kw)


def made(out):
    return [c["args"] for c in out["calls"] if c["method"] == MAKE]


OK = {"message": {"doctype": "COA AMB2", "name": "COA2-0001"}}


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestWhereTheButtonIs(unittest.TestCase):
    def test_a_saved_order_has_it_draft_or_submitted_or_cancelled(self):
        for docstatus in (0, 1, 2):
            self.assertIn(["Certificate", "Create"], run(click=False, docstatus=docstatus)["buttons"], docstatus)

    def test_an_unsaved_order_does_not(self):
        out = run(click=False, is_new=True, docstatus=0)
        self.assertNotIn("Certificate", [b[0] for b in out["buttons"]])
        self.assertIn("Check Material Availability", [b[0] for b in out["buttons"]])   # the existing button stays


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestThroughTheLot(unittest.TestCase):
    def test_it_looks_for_the_lot_records_of_this_order(self):
        out = run(lots=[])
        (c,) = out["calls"]
        self.assertEqual(c["method"], "frappe.client.get_list")
        self.assertEqual(c["args"]["doctype"], "Batch AMB")
        self.assertEqual(c["args"]["filters"], {"work_order_ref": "WO-0001"})
        self.assertEqual(c["args"]["limit_page_length"], 0)             # all of them, not the first 20

    def test_no_lot_record_says_one_is_needed_first_and_creates_nothing(self):
        out = run(lots=[])
        self.assertEqual(made(out), [])
        self.assertEqual((out["routes"], out["prompts"]), ([], []))
        (msg,) = out["msgs"]
        self.assertIn("no lot record", msg)
        self.assertIn("WO-0001", msg)

    def test_one_lot_record_is_used_without_asking_and_the_certificate_is_opened(self):
        out = run(lots=[lot("LOTE-00001")], make_reply=OK)
        self.assertEqual(out["prompts"], [])
        self.assertEqual(made(out), [{"lot": "LOTE-00001"}])
        self.assertEqual(out["routes"], [["Form", "COA AMB2", "COA2-0001"]])
        self.assertEqual(out["msgs"], [])

    def test_several_lot_records_the_user_chooses_then_the_same_call(self):
        lots = [lot("LOTE-00001"), lot("LOTE-00002", "2", quality_status="Passed"), lot("LOTE-00003", "2")]
        out = run(lots=lots, choose="LOTE-00003", make_reply={"message": {"doctype": "COA AMB", "name": "COA-9"}})
        (p,) = out["prompts"]
        (field,) = p["fields"]
        self.assertEqual((field["fieldname"], field["fieldtype"], field["reqd"]), ("lot", "Select", 1))
        self.assertEqual([o["value"] for o in field["options"]], ["LOTE-00001", "LOTE-00002", "LOTE-00003"])
        self.assertIn("level 2", field["options"][1]["label"])
        self.assertIn("Passed", field["options"][1]["label"])
        self.assertEqual(made(out), [{"lot": "LOTE-00003"}])            # the chosen one, not the first
        self.assertEqual(out["routes"], [["Form", "COA AMB", "COA-9"]])

    def test_several_and_no_choice_creates_nothing(self):
        lots = [lot("LOTE-00001"), lot("LOTE-00002", "2")]
        self.assertEqual(made(run(lots=lots)), [])                      # dialog left open / closed
        self.assertEqual(made(run(lots=lots, choose=None)), [])         # confirmed with nothing chosen

    def test_containers_are_not_offered(self):
        lots = [lot("LOTE-00001"), lot("LOTE-00002", "2"), lot("LOTE-00003", "3"), lot("LOTE-00004", "3")]
        out = run(lots=lots, choose="LOTE-00002", make_reply=OK)
        self.assertEqual([o["value"] for o in out["prompts"][0]["fields"][0]["options"]], ["LOTE-00001", "LOTE-00002"])
        # one lot and its containers: the lot, without asking
        out = run(lots=[lot("LOTE-00001"), lot("LOTE-00003", "3")], make_reply=OK)
        self.assertEqual((out["prompts"], made(out)), ([], [{"lot": "LOTE-00001"}]))
        # containers only: no lot record a certificate can be made for
        out = run(lots=[lot("LOTE-00003", "3")])
        self.assertEqual((made(out), len(out["msgs"])), ([], 1))

    def test_a_record_with_no_level_counts_as_a_lot(self):
        out = run(lots=[lot("LOTE-00001", None)], make_reply=OK)
        self.assertEqual(made(out), [{"lot": "LOTE-00001"}])


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestRefusals(unittest.TestCase):
    def test_a_refusal_by_the_server_routes_nowhere_and_gets_no_message_of_ours(self):
        for reply in ({"exc": "ValidationError"}, {}, {"message": None}, {"message": {"name": "X"}}):
            out = run(lots=[lot("LOTE-00001")], make_reply=reply)
            self.assertEqual(len(made(out)), 1)
            self.assertEqual((out["routes"], out["msgs"]), ([], []), reply)

    def test_a_failed_lookup_creates_nothing_and_does_not_claim_there_is_no_lot(self):
        out = run(list_reply={"exc": "PermissionError"})
        self.assertEqual((made(out), out["msgs"], out["prompts"]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
