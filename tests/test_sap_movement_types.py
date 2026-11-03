"""TASKS-272 (2026-11-02), DB-free: the 16 SAP movement types live in ONE list and every carrier agrees with it —
fixtures/movement_type.json (records), fixtures/custom_field.json (the Select options), boot info, the installer seed."""

import json
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
PKG = os.path.join(ROOT, "rnd_warehouse_management")

from rnd_warehouse_management import sap_movement_types as smt  # noqa: E402

EXPECTED = ["101", "102", "103", "104", "105", "106", "107", "108", "109", "261", "281", "311", "313", "501", "545", "561"]


def fixture(name):
	with open(os.path.join(PKG, "fixtures", name), encoding="utf-8") as f:
		return json.load(f)


class TestOneList(unittest.TestCase):
	def test_the_sixteen_codes_in_order(self):
		self.assertEqual(smt.CODES, EXPECTED)
		self.assertEqual(len(set(smt.CODES)), 16)

	def test_fixture_records_carry_the_same_codes_once_each(self):
		rows = fixture("movement_type.json")
		codes = sorted((r["movement_code"] for r in rows), key=int)
		self.assertEqual(codes, EXPECTED)
		for r in rows:
			self.assertEqual(r["sap_equivalent"], r["movement_code"], r["name"])
		for code in ("281", "501"):
			(r,) = [x for x in rows if x["movement_code"] == code]
			self.assertEqual(r["name"], code)
		(r501,) = [x for x in rows if x["movement_code"] == "501"]
		self.assertEqual(r501["default_stock_entry_type"], "Material Receipt")
		# TASKS-272c: 281 = Goods Issue for Sampling, Stock Entry Type Material Issue (as 103 and 109)
		(r281,) = [x for x in rows if x["movement_code"] == "281"]
		self.assertEqual((r281["purpose"], r281["default_stock_entry_type"]), ("Material Issue", "Material Issue"))
		self.assertEqual(r281["movement_description"], "Goods Issue for Sampling")

	def test_select_options_equal_the_list(self):
		(cf,) = [c for c in fixture("custom_field.json") if c["fieldname"] == "custom_sap_movement_type"]
		self.assertEqual((cf["dt"], cf["fieldtype"]), ("Stock Entry", "Select"))
		self.assertEqual(cf["options"], smt.select_options())
		lines = cf["options"].split("\n")
		self.assertEqual(lines[0], "")                       # the leading blank option stays
		self.assertEqual([smt.sap_code(l) for l in lines[1:]], EXPECTED)
		for l in lines[1:]:
			self.assertRegex(l, r"^\d{3} \(.+\)$")

	def test_the_561_label_is_the_string_the_submitted_documents_store(self):
		# TASKS-272b: prod stores exactly this in 42 submitted Stock Entries; a value outside `options` throws on save
		(cf,) = [c for c in fixture("custom_field.json") if c["fieldname"] == "custom_sap_movement_type"]
		self.assertIn("\n561 (Initial Entry - Stock Balance)\n", cf["options"] + "\n")
		self.assertNotIn("Material Receipt)", [l for l in cf["options"].split("\n") if l.startswith("561")][0])

	def test_the_other_fixture_owner_ships_the_same_options_if_present(self):
		# amb_w_spc/fixtures/custom_field.json carries the same 25 Stock Entry Custom Fields and syncs AFTER this app;
		# when its checkout is reachable (AMB_W_SPC_FIXTURES env), its options must be byte-identical to ours
		other = os.environ.get("AMB_W_SPC_FIXTURES")
		if not other:
			self.skipTest("AMB_W_SPC_FIXTURES not set")
		with open(os.path.join(other, "custom_field.json"), encoding="utf-8") as f:
			(theirs,) = [c for c in json.load(f) if c["name"] == "Stock Entry-custom_sap_movement_type"]
		self.assertEqual(theirs["options"], smt.select_options())

	def test_the_three_shipped_labels_are_untouched(self):
		(cf,) = [c for c in fixture("custom_field.json") if c["fieldname"] == "custom_sap_movement_type"]
		for kept in ("261 (FrontFlush - Goods Issue for Production)", "311 (BackFlush - Transfer for Kitting)",
		             "561 (Initial Entry - Stock Balance)", "281 (Goods Issue for Sampling)",
		             "501 (Receipt without Purchase Order)"):
			self.assertIn("\n" + kept + "\n", cf["options"] + "\n")

	def test_boot_dict_equals_the_list(self):
		b = smt.boot_dict()
		self.assertEqual(list(b.keys()), EXPECTED)
		self.assertEqual(b["311"]["required_signatures"], ["warehouse_supervisor", "kitting_supervisor"])
		self.assertEqual(b["561"]["purpose"], "Material Receipt")
		with open(os.path.join(PKG, "boot.py"), encoding="utf-8") as f:
			src = f.read()
		self.assertIn("boot_dict()", src)
		self.assertNotRegex(src, r'"261":\s*\{')       # no second hand-written copy

	def test_installer_seeds_from_the_list(self):
		with open(os.path.join(PKG, "install.py"), encoding="utf-8") as f:
			src = f.read()
		self.assertIn("from rnd_warehouse_management.sap_movement_types import SAP_MOVEMENT_TYPES", src)
		self.assertNotIn('"movement_code": "101"', src)
		# drive it with frappe stubbed: nothing exists -> one insert per code, keyed by movement_code
		import importlib.util
		fake = mock.MagicMock()
		fake.db.exists.return_value = False
		inserted = []
		fake.get_doc.side_effect = lambda d: (inserted.append(d) or mock.MagicMock())
		with mock.patch.dict(sys.modules, {"frappe": fake}):
			spec = importlib.util.spec_from_file_location("rnd_install_under_test", os.path.join(PKG, "install.py"))
			mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
			mod.create_default_movement_types()
		self.assertEqual([d["movement_code"] for d in inserted], EXPECTED)
		self.assertEqual([d["name"] for d in inserted], EXPECTED)
		self.assertEqual(fake.db.exists.call_args_list[0].args, ("Movement Type", {"movement_code": "101"}))

	def test_sap_code_reads_the_leading_code(self):
		self.assertEqual(smt.sap_code("311 (BackFlush - Transfer for Kitting)"), "311")
		self.assertEqual(smt.sap_code("311"), "311")
		self.assertEqual(smt.sap_code(""), "")
		self.assertEqual(smt.sap_code(None), "")


if __name__ == "__main__":
	unittest.main()
