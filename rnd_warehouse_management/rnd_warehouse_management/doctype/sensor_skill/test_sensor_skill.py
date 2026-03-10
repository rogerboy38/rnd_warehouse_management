# Copyright (c) 2026, Prosolmex and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSensorSkill(FrappeTestCase):
    def test_sensor_skill_creation(self):
        doc = frappe.get_doc({
            "doctype": "Sensor Skill",
            "sensor_type": "_test_temperature",
            "version": "1.0",
            "min_value": -40.0,
            "max_value": 125.0,
            "wiring_instructions": "VCC to 3.3V, GND to GND, DATA to D4",
            "calibration_procedure": "Use ice water (0°C) and boiling water (100°C) as reference points."
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sensor_type, "_test_temperature")
        doc.delete()
