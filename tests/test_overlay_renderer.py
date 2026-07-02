import unittest
from typing import cast
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from modules import config, layouts, overlay_renderer, video_processor
from modules.settings import RenderSettings


class TestBlinkerState(unittest.TestCase):
    def setUp(self):
        overlay_renderer.reset_blinker_state()

    def tearDown(self):
        overlay_renderer.reset_blinker_state()

    def test_reset_blinker_state_restarts_blink_cycle_after_clip_boundary(self):
        overlay_renderer.blinker_state["right"] = {"state": True, "frame": 41}
        overlay_renderer.reset_blinker_state()

        right_fills = []
        telemetry_df = pd.DataFrame(
            [
                {
                    "blinker_on_left": False,
                    "blinker_on_right": True,
                    "accelerator_pedal_position": 0,
                    "brake_applied": False,
                    "steering_wheel_angle": 0,
                    "autopilot_state": "",
                    "gear_state": "GEAR_DRIVE",
                    "vehicle_speed_mps": 0,
                }
            ]
        )
        settings = RenderSettings(
            no_overlay=False,
            mph=False,
            preview=False,
            keep_csv=False,
            layout=layouts.FOUR_CAMERA_DEFAULT,
        )

        def record_right(fill, _draw):
            right_fills.append(fill)

        with patch("modules.shapes.draw_right_blinker", side_effect=record_right):
            overlay_renderer.draw_overlay(
                np.zeros((config.CANVAS_HEIGHT, config.CANVAS_WIDTH, 3), dtype=np.uint8),
                1,
                telemetry_df,
                0,
                settings,
            )
            overlay_renderer.draw_overlay(
                np.zeros((config.CANVAS_HEIGHT, config.CANVAS_WIDTH, 3), dtype=np.uint8),
                1 + config.BLINKER_INTERVAL,
                telemetry_df,
                0,
                settings,
            )

        self.assertEqual(right_fills, [config.BLINKER_ON, config.BLINKER_OFF])

    def test_process_video_resets_blinker_state_for_each_clip(self):
        class EmptyCapture:
            def read(self):
                return False, None

            def get(self, _property_id):
                return 0

        captures = {camera: EmptyCapture() for camera in layouts.FOUR_CAMERA_DEFAULT["required_cameras"]}
        settings = RenderSettings(
            no_overlay=True,
            mph=False,
            preview=False,
            keep_csv=False,
            layout=layouts.FOUR_CAMERA_DEFAULT,
        )

        with patch("modules.overlay_renderer.reset_blinker_state") as reset_blinker_state:
            written_frames = video_processor.process_video(
                captures=cast(dict, captures),
                telemetry_df=None,
                out=Mock(),
                settings=settings,
            )

        reset_blinker_state.assert_called_once_with()
        self.assertEqual(written_frames, 0)


if __name__ == "__main__":
    unittest.main()
