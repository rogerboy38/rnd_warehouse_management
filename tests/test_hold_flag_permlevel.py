"""TASKS-350 decision 102, DB-free: the permission level of `custom_qc_hold`. What the patch does to a real Custom DocPerm set,
with real roles, is proved on a scratch site (see the reply); here: the decision of which rows are added, and what ships."""
import configparser
import importlib
import json
import os
import sys
import types
import unittest
from unittest import mock

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


class FakeSite:
	"""A site as the patch sees it: the Custom DocPerm rows of Warehouse, the standard rows, the site default that holds
	the patch's record, the Patch Log, and the Custom Field's level. `migrate()` does what Frappe's migrate does that
	matters here, in Frappe's order: a patch line runs only when no Patch Log row holds that exact string, then the
	fixture puts the field at the level the deployed code ships."""

	def __init__(self, custom_rows=None):
		self.standard = [dict(role="Stock User", permlevel=0, read=1, write=0, if_owner=0), dict(role="Item Manager", permlevel=0, read=1, write=1, if_owner=0)]
		self.custom = {}
		self.n = 0
		for r in custom_rows or []:
			self._add(dict(r))
		self.defaults = {}          # what the database holds
		self.defaults_cache = {}    # what frappe.db.get_default answers from, until the cache is dropped
		self.patch_log = set()
		self.field_level = 0
		self.executions = 0

	def _add(self, row):
		self.n += 1
		name = f"cdp{self.n}"
		self.custom[name] = dict(row, name=name)
		return name

	# --- what the patch calls
	def frappe(self):
		site = self
		f = mock.MagicMock()

		def exists(dt, name=None):
			if dt == "DocType":
				return True
			if dt == "Custom DocPerm":
				return name in site.custom
			if dt == "Custom Field":
				return True
			return False

		def get_all(dt, filters=None, fields=None, pluck=None):
			rows = [r for r in site.custom.values() if all(r.get(k, "Warehouse" if k == "parent" else None) == v for k, v in (filters or {}).items())]
			return [r["name"] for r in rows] if pluck else [types.SimpleNamespace(**r).__dict__ for r in rows]

		def new_doc(dt):
			d = types.SimpleNamespace(data={})
			d.update = lambda v: d.data.update(v)
			d.insert = lambda **k: setattr(d, "name", site._add({k2: v for k2, v in d.data.items() if k2 in ("role", "permlevel", "read", "write", "if_owner")}))
			return d

		def set_value(dt, name, field, value):
			if dt == "Custom DocPerm":
				site.custom[name][field] = value
			elif dt == "Custom Field":
				site.field_level = value

		def delete(dt, filters):
			if dt == "Patch Log":
				site.patch_log.discard(filters["patch"])
			elif dt == "DefaultValue":
				site.defaults.pop(filters["defkey"], None)      # the row only: Frappe's cache still answers

		def set_default(k, v):
			site.defaults[k] = v
			site.defaults_cache = dict(site.defaults)       # frappe.db.set_default drops the cache

		def clear_default(key=None, parent=None, **kw):
			site.defaults.pop(key, None)
			site.defaults_cache = dict(site.defaults)       # frappe.defaults.clear_default drops it too

		f.db.exists.side_effect = exists
		f.get_all.side_effect = get_all
		f.new_doc.side_effect = new_doc
		f.db.set_value.side_effect = set_value
		f.db.delete.side_effect = delete
		f.db.get_default.side_effect = lambda k: site.defaults_cache.get(k)
		f.db.set_default.side_effect = set_default
		f.defaults.clear_default.side_effect = clear_default
		f.delete_doc.side_effect = lambda dt, name, **k: site.custom.pop(name, None)
		return f

	def setup_custom_perms(self, dt):
		if not self.custom:
			for r in self.standard:
				self._add(dict(r))
			return True

	def call(self, fn):
		with mock.patch.object(P, "frappe", self.frappe()), mock.patch("frappe.permissions.setup_custom_perms", self.setup_custom_perms):
			return fn()

	def migrate(self, new_code=True):
		if new_code and P.PATCH_NAME not in self.patch_log:
			self.call(P.execute)
			self.executions += 1
			self.patch_log.add(P.PATCH_NAME)
		self.field_level = 1 if new_code else 0          # the fixture of the deployed code

	def way_back(self):
		return self.call(P.rollback)

	# --- what a person would see
	def level1(self):
		return sorted((r["role"], r["read"], r["write"]) for r in self.custom.values() if r["permlevel"] == 1)

	def level0(self):
		return sorted((r["role"], r["read"], r["write"]) for r in self.custom.values() if r["permlevel"] == 0)

	def consistent(self):
		"""a level-1 field needs its level-1 rows, with write for the two roles; a level-0 field needs none"""
		if self.field_level == 1:
			return {(r, 1, 1) for r in P.EDIT_ROLES} <= set(self.level1())
		return self.level1() == []


SHADOW = [dict(role="Stock User", permlevel=0, read=1, write=0, if_owner=0), dict(role="Planeacion", permlevel=0, read=1, write=0, if_owner=0)]


class TestApplyAgainAfterAWayBack(unittest.TestCase):
	"""TASKS-353 decision 108, the five orders, on a site with the standard rows and on one with shadow rows."""

	def sites(self):
		return [("standard rows", FakeSite()), ("shadow rows", FakeSite(SHADOW))]

	def test_1_install_way_back_install_again(self):
		for label, s in self.sites():
			before0 = s.level0()
			s.migrate()
			first = (s.level0(), s.level1())
			self.assertTrue(s.consistent() and s.field_level == 1, label)
			s.way_back()
			self.assertEqual((s.level1(), s.field_level), ([], 0), f"{label}: the way back itself leaves no level-1 row and the field at level 0")
			s.migrate(new_code=False)                    # the older code
			self.assertEqual((s.level0(), s.level1(), s.field_level), (before0, [], 0), label)
			s.migrate()                                  # the new code again: no step by hand
			self.assertEqual((s.level0(), s.level1()), first, label)
			self.assertTrue(s.consistent() and s.field_level == 1, label)
			self.assertEqual(s.executions, 2, label)     # the patch really ran again

	def test_2_install_way_back_then_migrate_on_the_new_code(self):
		for label, s in self.sites():
			s.migrate()
			first = (s.level0(), s.level1())
			s.way_back()
			s.migrate()                                  # the older code was never deployed
			self.assertEqual(s.field_level, 1, label)
			self.assertTrue(s.consistent(), f"{label}: a level-1 field without its level-1 rows")
			self.assertEqual((s.level0(), s.level1()), first, label)

	def test_3_install_twice_with_no_way_back(self):
		for label, s in self.sites():
			s.migrate()
			first = (s.level0(), s.level1(), len(s.custom))
			s.migrate()
			self.assertEqual((s.level0(), s.level1(), len(s.custom)), first, label)
			self.assertEqual(s.executions, 1, label)     # Frappe does not run it twice
			s.call(P.execute)                            # and if someone runs it by hand it adds nothing
			self.assertEqual((s.level0(), s.level1(), len(s.custom)), first, label)

	def test_4_way_back_called_twice(self):
		for label, s in self.sites():
			before0 = s.level0()
			s.migrate()
			s.way_back()
			after_one = (s.level0(), s.level1(), s.field_level, dict(s.defaults), set(s.patch_log))
			out = s.way_back()
			self.assertIn("nothing", out, label)
			self.assertEqual((s.level0(), s.level1(), s.field_level, dict(s.defaults), set(s.patch_log)), after_one, label)
			self.assertEqual(s.level0(), before0 if label == "shadow rows" else [], label)   # standard rows: the copy is gone
			s.migrate()
			self.assertTrue(s.consistent() and s.field_level == 1, label)

	def test_5_way_back_on_a_site_where_the_patch_never_ran(self):
		for label, s in self.sites():
			before = (s.level0(), s.level1(), s.field_level, dict(s.defaults), len(s.custom))
			out = s.way_back()
			self.assertIn("nothing", out, label)
			self.assertEqual((s.level0(), s.level1(), s.field_level, dict(s.defaults), len(s.custom)), before, label)
			s.migrate()                                  # and the first install after it works
			self.assertTrue(s.consistent() and s.field_level == 1, label)

	def test_the_way_back_forgets_exactly_this_patch_line(self):
		lines = [l.strip() for l in open(os.path.join(APP, "patches.txt"), encoding="utf-8") if l.strip() and not l.startswith(("#", "["))]
		self.assertIn(P.PATCH_NAME, lines)               # the string Frappe stores in Patch Log.patch
		s = FakeSite()
		s.patch_log.add("rnd_warehouse_management.patches.v1_0.setup_custom_roles")
		s.migrate()
		s.way_back()
		self.assertEqual(s.patch_log, {"rnd_warehouse_management.patches.v1_0.setup_custom_roles"})


if __name__ == "__main__":
	unittest.main()
