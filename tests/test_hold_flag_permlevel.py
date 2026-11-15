"""TASKS-350 decision 102, DB-free: the permission level of `custom_qc_hold`. What the patch does to a real Custom DocPerm set,
with real roles, is proved on a scratch site (see the reply); here: the decision of which rows are added, and what ships."""
import configparser
import importlib
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
APP = os.path.join(ROOT, "rnd_warehouse_management")

P = importlib.import_module("rnd_warehouse_management.patches.v2_4.hold_flag_permlevel")


def r0(role, read=1, write=0, if_owner=0):
	return {"role": role, "read": read, "write": write, "if_owner": if_owner}


class TestPlan(unittest.TestCase):
	def test_every_reader_gets_a_read_only_level_one_row_and_the_two_roles_get_write(self):
		add, up = P.plan([r0("Stock User"), r0("Stock Manager", write=1), r0("Item Manager")], [])
		by = {(a["role"], a["if_owner"]): a for a in add}
		for role in ("Stock User", "Stock Manager", "Item Manager"):
			self.assertEqual((by[(role, 0)]["read"], by[(role, 0)]["write"]), (1, 0), role)       # nobody else gains write
		for role in P.EDIT_ROLES:
			self.assertEqual((by[(role, 0)]["read"], by[(role, 0)]["write"]), (1, 1), role)
		self.assertEqual(up, [])

	def test_a_role_that_writes_at_level_zero_does_not_get_write_at_level_one(self):
		add, _ = P.plan([r0("Stock Manager", write=1), r0("Quality Manager", write=1)], [])
		by = {a["role"]: a for a in add}
		self.assertEqual(by["Stock Manager"]["write"], 0)     # this is the point of the decision
		self.assertEqual(by["Quality Manager"]["write"], 1)

	def test_a_role_without_a_read_row_gets_nothing(self):
		add, _ = P.plan([r0("Hidden Role", read=0, write=1)], [])
		self.assertNotIn("Hidden Role", {a["role"] for a in add})

	def test_if_owner_rows_keep_their_condition(self):
		add, _ = P.plan([r0("Stock User", if_owner=1)], [])
		self.assertIn(("Stock User", 1), {(a["role"], a["if_owner"]) for a in add})

	def test_it_is_idempotent_and_never_duplicates_a_row_that_exists(self):
		level0 = [r0("Stock User"), r0("Stock Manager", write=1)]
		add, _ = P.plan(level0, [])
		again = [dict(a, name=f"x{i}") for i, a in enumerate(add)]
		self.assertEqual(P.plan(level0, again), ([], []))

	def test_an_existing_level_one_row_of_an_edit_role_without_write_is_upgraded_not_duplicated(self):
		add, up = P.plan([r0("Quality Manager")], [{"name": "ABC", "role": "Quality Manager", "if_owner": 0, "read": 1, "write": 0}])
		self.assertNotIn("Quality Manager", {a["role"] for a in add})
		self.assertEqual(up, ["ABC"])


class TestShipping(unittest.TestCase):
	def test_the_fixture_puts_the_field_at_permission_level_one(self):
		rows = json.load(open(os.path.join(APP, "fixtures", "custom_field.json"), encoding="utf-8"))
		(r,) = [x for x in rows if x["name"] == "Warehouse-custom_qc_hold"]
		self.assertEqual((r["permlevel"], r["fieldtype"], r["read_only"]), (1, "Check", 0))

	def test_patches_txt_parses_like_frappe_does_and_lists_the_patch_after_the_model_sync(self):
		parser = configparser.ConfigParser(allow_no_value=True, delimiters="\n")
		parser.optionxform = str
		parser.read(os.path.join(APP, "patches.txt"))
		self.assertEqual(sorted(parser.sections()), ["post_model_sync", "pre_model_sync"])
		self.assertEqual(list(parser["post_model_sync"]), ["rnd_warehouse_management.patches.v2_4.hold_flag_permlevel"])
		pre = list(parser["pre_model_sync"])
		self.assertEqual(len(pre), 5)
		self.assertTrue(all(p.startswith("rnd_warehouse_management.patches.v1_0.") for p in pre))

	def test_there_is_a_way_back(self):
		self.assertTrue(callable(P.rollback) and callable(P.execute))


if __name__ == "__main__":
	unittest.main()
