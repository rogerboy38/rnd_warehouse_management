"""TASKS-335 / D-10, DB-free: the Manufacture hook (a) does not raise 1054 for a column no app ships,
(b) files its Error Log under a stable class, with the detail as the message."""

import datetime
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from rnd_warehouse_management.rnd_warehouse_management import qi_automation as qa  # noqa: E402


patch_time = mock.patch.multiple(
	qa, nowdate=lambda: "2026-11-13", now_datetime=lambda: datetime.datetime(2026, 11, 13, 9, 0, 0)
)


def _doc(work_order="WO-1"):
	item = types.SimpleNamespace(
		t_warehouse="FG", is_finished_item=1, item_code="X", item_name="X", batch_no="B1"
	)
	return types.SimpleNamespace(
		name="SE-1", purpose="Manufacture", stock_entry_type="Manufacture", work_order=work_order, items=[item]
	)


def _frappe(has_custom_field, insert_raises=None):
	f = mock.MagicMock()
	f.db.get_value.return_value = "TPL"
	qi = mock.MagicMock()
	qi.name = "QI-1"
	if insert_raises:
		qi.insert.side_effect = insert_raises
	f.get_doc.side_effect = lambda arg, *rest: (
		mock.MagicMock(item_quality_inspection_parameter=[]) if isinstance(arg, str) else qi
	)
	f.get_meta.return_value.has_field.return_value = has_custom_field
	f.session.user = "u"
	f.conf = {}
	# nowdate()/now_datetime() read site settings through the real frappe: keep the tests DB-free
	patch_time.start()
	return f, qi


class TestManufactureHook(unittest.TestCase):
	def tearDown(self):
		patch_time.stop()

	def test_no_custom_field_no_db_set_no_error_log(self):
		f, qi = _frappe(False)
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		qi.insert.assert_called_once()
		qi.db_set.assert_not_called()
		f.log_error.assert_not_called()

	def test_custom_field_present_is_still_linked(self):
		f, qi = _frappe(True)
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		qi.db_set.assert_called_once_with("custom_work_order", "WO-1")
		f.log_error.assert_not_called()

	def test_error_log_class_is_stable_and_detail_is_the_message(self):
		f, qi = _frappe(False, insert_raises=RuntimeError("boom"))
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		(call,) = f.log_error.call_args_list
		self.assertEqual(call.kwargs["title"], "QI Auto-Creation Error")
		self.assertIn("SE-1", call.kwargs["message"])
		self.assertIn("boom", call.kwargs["message"])

	def test_switch_off_creates_nothing(self):
		f, qi = _frappe(False)
		f.conf = {"rnd_auto_quality_inspection": 0}
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		f.get_doc.assert_not_called()
		f.log_error.assert_not_called()

	def test_switch_one_means_on(self):
		f, qi = _frappe(False)
		f.conf = {"rnd_auto_quality_inspection": 1}
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		qi.insert.assert_called_once()

	def test_switch_absent_means_on(self):
		f, qi = _frappe(False)
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(_doc())
		qi.insert.assert_called_once()

	def test_non_manufacture_entry_does_nothing(self):
		f, qi = _frappe(False)
		d = _doc()
		d.purpose = d.stock_entry_type = "Material Receipt"
		with mock.patch.object(qa, "frappe", f):
			qa.create_quality_inspection_on_manufacture(d)
		f.get_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
