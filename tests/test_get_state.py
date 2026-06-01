import unittest
from argparse import Namespace

from modules.get_state import get_speed, get_gear_state, get_autopilot_state


class TestGetSpeed(unittest.TestCase):
    def test_positive_speed_uses_kmh_by_default(self):
        current_frame_data = {"vehicle_speed_mps": 10}
        settings = Namespace(mph=False)

        speed, unit = get_speed(current_frame_data, settings)

        self.assertEqual(speed, "36")
        self.assertEqual(unit, "KM/H")

    def test_negative_speed_uses_absolute_value(self):
        current_frame_data = {"vehicle_speed_mps": -5}
        settings = Namespace(mph=False)

        speed, unit = get_speed(current_frame_data, settings)

        self.assertEqual(speed, "18")
        self.assertEqual(unit, "KM/H")

    def test_speed_can_use_mph(self):
        current_frame_data = {"vehicle_speed_mps": 10}
        settings = Namespace(mph=True)

        speed, unit = get_speed(current_frame_data, settings)

        self.assertEqual(speed, "22")
        self.assertEqual(unit, "MPH")


class TestGetGearState(unittest.TestCase):
    def test_drive_maps_to_d(self):
        current_frame_data = {"gear_state": "GEAR_DRIVE"}

        gear = get_gear_state(current_frame_data)

        self.assertEqual(gear, "D")

    def test_unknown_gear_maps_to_empty_string(self):
        current_frame_data = {"gear_state": "UNKNOWN"}

        gear = get_gear_state(current_frame_data)

        self.assertEqual(gear, "")


class TestGetAutopilotState(unittest.TestCase):
    def test_autosteer_maps_to_autopilot(self):
        current_frame_data = {"autopilot_state": "AUTOSTEER"}

        autopilot_state = get_autopilot_state(current_frame_data)

        self.assertEqual(autopilot_state, "Autosteer")

    def test_unknown_autopilot_state_maps_to_empty_string(self):
        current_frame_data = {"autopilot_state": "NONE"}

        autopilot_state = get_autopilot_state(current_frame_data)

        self.assertEqual(autopilot_state, "")


if __name__ == "__main__":
    unittest.main()
