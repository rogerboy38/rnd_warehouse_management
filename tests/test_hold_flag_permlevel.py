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
		self.roles = {"Stock User", "Item Manager", "Quality Manager", "System Manager", "Planeacion"}
		self.log = []
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
			if dt == "Role":
				return name in site.roles
			return False

		def match(r, filters):
			for k, v in (filters or {}).items():
				if k == "parent":
					continue
				if isinstance(v, list) and v and v[0] == "in":
					if r.get(k) not in v[1]:
						return False
				elif r.get(k) != v:
					return False
			return True

		def get_all(dt, filters=None, fields=None, pluck=None):
			src = site.custom.values() if dt == "Custom DocPerm" else site.standard if dt == "DocPerm" else []
			rows = [dict(r) for r in src if match(r, filters)]
			return [r["name"] for r in rows] if pluck else rows

		def new_doc(dt):
			d = types.SimpleNamespace(data={})
			d.update = lambda v: d.data.update(v)
			def insert(**k):
				if d.data.get("role") not in site.roles:       # what Frappe does: the Link to Role does not resolve
					raise RuntimeError(f"LinkValidationError: Could not find Role: {d.data.get('role')}")
				d.name = site._add({k2: v for k2, v in d.data.items() if k2 in ("role", "permlevel", "read", "write", "if_owner")})
			d.insert = insert
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

		f.logger.return_value.warning.side_effect = site.log.append
		f.db.get_value.side_effect = lambda dt, name, field: site.field_level
		site.last_frappe = f
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


class TestRound9a(unittest.TestCase):
	"""TASKS-361: P-B (a row whose role no longer exists) and P-A (the way back removes only the patch's own rows)."""

	def test_pb_a_row_of_a_vanished_role_does_not_stop_the_patch_and_is_left_as_it_is(self):
		gone = dict(role="Borrado", permlevel=0, read=1, write=1, if_owner=0)
		for label, s in (("shadow rows", FakeSite(SHADOW + [gone])),):
			before = [r for r in s.custom.values() if r["role"] == "Borrado"]
			s.migrate()                                       # must not raise
			after = [r for r in s.custom.values() if r["role"] == "Borrado"]
			self.assertEqual(after, before, "the row of the vanished role was touched")
			self.assertNotIn("Borrado", {r[0] for r in s.level1()}, "a level-1 row was made for a role that does not exist")
			self.assertTrue(s.consistent() and s.field_level == 1, label)
			self.assertEqual({("Stock User", 1, 0), ("Planeacion", 1, 0)} - set(s.level1()), set(), "the other readers lost their level-1 row")
			named = [l for l in s.log if "Borrado" in l]
			self.assertEqual(len(named), 1, s.log)            # one log line, and it names the role
			s.way_back()
			self.assertEqual([r for r in s.custom.values() if r["role"] == "Borrado"], before)

	def test_pb_an_edit_role_that_does_not_exist_is_skipped_not_fatal(self):
		s = FakeSite(SHADOW)
		s.roles.discard("Quality Manager")
		s.migrate()
		self.assertIn(("System Manager", 1, 1), s.level1())
		self.assertNotIn("Quality Manager", {r[0] for r in s.level1()})
		self.assertTrue(any("Quality Manager" in l for l in s.log))

	def test_pa_a_row_added_by_hand_after_the_patch_survives_the_way_back(self):
		s = FakeSite()                                        # no Custom DocPerm row before the patch
		s.migrate()
		self.assertEqual(len(s.level0()), 2)                  # the copy of the standard rows
		hand = s._add(dict(role="Planeacion", permlevel=0, read=1, write=0, if_owner=0))
		out = s.way_back()
		self.assertIn(hand, s.custom, "the way back removed a row a person added")
		self.assertEqual(s.level1(), [])                      # the patch's own level-1 rows are gone
		self.assertEqual(s.field_level, 0)
		self.assertEqual(len(s.level0()), 3, "the copy must stay: alone, the hand-made row would replace the standard rows")
		self.assertIn("KEPT", out)
		s.migrate()                                           # decision 108 still holds
		self.assertTrue(s.consistent() and s.field_level == 1)
		self.assertIn(("Planeacion", 1, 0), s.level1())
		self.assertEqual(s.executions, 2)

	def test_pa_a_copied_row_changed_by_hand_keeps_the_copy(self):
		s = FakeSite()
		s.migrate()
		name = next(n for n, r in s.custom.items() if r["role"] == "Stock User" and r["permlevel"] == 0)
		s.custom[name]["write"] = 1                           # a person gives Stock User write
		s.way_back()
		self.assertEqual(s.custom[name]["write"], 1)
		self.assertEqual(len(s.level0()), 2)

	def test_pa_an_untouched_copy_is_removed_and_the_site_is_on_the_standard_rows_again(self):
		s = FakeSite()
		s.migrate()
		out = s.way_back()
		self.assertEqual(s.custom, {})
		self.assertIn("copy removed", out)

	def test_pa_a_record_written_by_the_older_patch_has_no_list_and_still_never_removes_a_hand_row(self):
		s = FakeSite()
		s.migrate()
		rec = json.loads(s.defaults[P.STATE_KEY]); rec.pop("copied"); s.defaults[P.STATE_KEY] = json.dumps(rec); s.defaults_cache = dict(s.defaults)
		hand = s._add(dict(role="Planeacion", permlevel=0, read=1, write=0, if_owner=0))
		s.way_back()
		self.assertIn(hand, s.custom)
		self.assertEqual(len(s.level0()), 3)

	def test_pa_on_a_site_that_had_its_own_rows_nothing_but_the_level_one_rows_goes(self):
		s = FakeSite(SHADOW)
		before0 = s.level0()
		s.migrate()
		hand = s._add(dict(role="Item Manager", permlevel=0, read=1, write=1, if_owner=0))
		s.way_back()
		self.assertIn(hand, s.custom)
		self.assertEqual(sorted(s.level0()), sorted(before0 + [("Item Manager", 1, 1)]))
		self.assertEqual(s.level1(), [])


if __name__ == "__main__":
	unittest.main()


class TestRound9c(unittest.TestCase):
	"""TASKS-365: L-1 (the line reaches a log file), R-1 (a damaged or missing record), W-1 (the count of the kept copy)."""

	def damage(self, s, text):
		s.defaults[P.STATE_KEY] = text
		s.defaults_cache = dict(s.defaults)

	def test_l1_the_line_goes_to_a_logger_of_its_own_at_warning_level(self):
		import logging

		s = FakeSite([dict(role="Stock User", permlevel=0, read=1, write=0, if_owner=0), dict(role="Borrado", permlevel=0, read=1, write=0, if_owner=0)])
		s.migrate()
		f = s.last_frappe
		f.logger.assert_called_with(P.LOG_NAME)
		f.logger.return_value.setLevel.assert_called_with(logging.WARNING)
		self.assertTrue(any("Borrado" in line for line in s.log))
		self.assertEqual(P.LOG_NAME, "rnd_hold_flag")

	def test_r1_a_record_that_cannot_be_read_stops_the_way_back_plainly_and_changes_nothing(self):
		for text, word in (("not json {", "not JSON"), ("null", "null"), ("[]", "[]"), ('"text"', "text"), ('{"added": 5}', "`added` is not a list"), ('{"copied": "x"}', "`copied` is not a list")):
			s = FakeSite()
			s.migrate()
			rows, log = dict(s.custom), set(s.patch_log)
			self.damage(s, text)
			out = s.way_back()                                # no exception
			self.assertIn("cannot be read", out, text)
			self.assertIn(word, out, text)
			self.assertIn("changed NOTHING", out)
			self.assertEqual((s.custom, s.patch_log, s.field_level, s.defaults[P.STATE_KEY]), (rows, log, 1, text), text)
			self.assertTrue(any("cannot be read" in line for line in s.log))

	def test_r1_a_record_that_cannot_be_read_does_not_fail_the_migrate_and_the_patch_changes_nothing(self):
		for text in ("null", "[]", "not json {", '{"added": 5}'):
			s = FakeSite()
			s.migrate()
			rows = dict(s.custom)
			self.damage(s, text)
			s.patch_log.clear()                               # the patch has to run again
			s.migrate()                                       # no exception: the migrate goes on
			self.assertEqual((s.custom, s.defaults[P.STATE_KEY]), (rows, text), text)
			self.assertTrue(any("changed NOTHING" in line and "run-patch" in line for line in s.log), text)

	def test_r1_a_record_with_keys_missing_is_still_a_record(self):
		s = FakeSite()
		s.migrate()
		rec = json.loads(s.defaults[P.STATE_KEY]); rec.pop("upgraded"); self.damage(s, json.dumps(rec))
		self.assertIn("copy removed", s.way_back())
		self.assertEqual(s.custom, {})

	def test_r1_a_deleted_record_the_way_back_says_what_it_finds_and_what_it_cannot_do(self):
		s = FakeSite()
		s.migrate()
		rows = dict(s.custom)
		s.defaults.pop(P.STATE_KEY); s.defaults_cache = {}
		out = s.way_back()
		self.assertEqual((s.custom, s.field_level), (rows, 1))                # nothing removed, the level left
		self.assertIn("nothing recorded: nothing removed", out)
		self.assertIn("the field at level 1, 4 level-1 Custom DocPerm row(s)", out)
		self.assertIn("cannot tell the patch's rows from a person's", out)
		self.assertNotIn(P.PATCH_NAME, s.patch_log)                           # the one thing it does
		s.migrate()                                                           # the next migrate writes a new record
		self.assertEqual(len(s.custom), len(rows))                            # and duplicates no row
		self.assertIn(P.STATE_KEY, s.defaults)

	def test_r1_nothing_recorded_on_a_clean_site_stays_one_short_line(self):
		s = FakeSite()
		self.assertEqual(s.way_back(), "nothing recorded: nothing removed")
		s.migrate(); s.way_back()
		self.assertEqual(s.way_back(), "nothing recorded: nothing removed")

	def test_w1_the_count_of_the_kept_copy_is_right_in_each_case(self):
		hand = dict(role="Planeacion", permlevel=0, read=1, write=0, if_owner=0)

		def site(old_record=False):
			s = FakeSite(); s.migrate()
			if old_record:
				rec = json.loads(s.defaults[P.STATE_KEY]); rec.pop("copied"); self.damage(s, json.dumps(rec))
			return s

		def copied_row(s):
			return next(n for n, r in s.custom.items() if r["role"] == "Stock User" and r["permlevel"] == 0)

		s = site(); s._add(dict(hand))
		self.assertIn("copy KEPT (3 rows left as they are): 1 row(s) added by hand, 0 copied row(s) changed, 0 copied row(s) deleted", s.way_back())
		s = site(); s.custom[copied_row(s)]["write"] = 1
		self.assertIn("copy KEPT (2 rows left as they are): 0 row(s) added by hand, 1 copied row(s) changed, 0 copied row(s) deleted", s.way_back())
		s = site(); s.custom.pop(copied_row(s))
		self.assertIn("copy KEPT (1 rows left as they are): 0 row(s) added by hand, 0 copied row(s) changed, 1 copied row(s) deleted", s.way_back())
		s = site(); s._add(dict(hand)); s.custom[copied_row(s)]["write"] = 1
		self.assertIn("1 row(s) added by hand, 1 copied row(s) changed, 0 copied row(s) deleted", s.way_back())
		s = site(); s.custom = {n: r for n, r in s.custom.items() if r["permlevel"] == 1}      # every copied row gone
		out = s.way_back()
		self.assertIn("no Custom DocPerm row of Warehouse is left", out)
		self.assertNotIn("KEPT", out)
		s = site(old_record=True); s._add(dict(hand))
		self.assertIn("copy KEPT (3 rows left as they are): 1 row(s) that equal no standard row (added or changed by hand), 0 standard row(s) with no equal row left", s.way_back())
		s = site(old_record=True); s.custom[copied_row(s)]["write"] = 1
		self.assertIn("1 row(s) that equal no standard row (added or changed by hand), 1 standard row(s) with no equal row left", s.way_back())
		s = site(old_record=True)
		self.assertIn("copy removed: 2 rows", s.way_back())
