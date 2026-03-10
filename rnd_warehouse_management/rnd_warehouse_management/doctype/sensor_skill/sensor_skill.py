# Copyright (c) 2026, Prosolmex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SensorSkill(Document):
    def validate(self):
        if self.min_value is not None and self.max_value is not None:
            if self.min_value >= self.max_value:
                frappe.throw("Min Value must be less than Max Value")

    def build_skill_package(self):
        """Return a structured dict representing this sensor skill package."""
        return {
            "sensor_type": self.sensor_type,
            "version": self.version or "1.0",
            "min_value": self.min_value,
            "max_value": self.max_value,
            "arduino_sketch": self.arduino_sketch or "",
            "python_config": self.python_config or "",
            "wiring_instructions": self.wiring_instructions or "",
            "calibration_procedure": self.calibration_procedure or "",
        }
