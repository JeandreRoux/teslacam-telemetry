import unittest
from pathlib import Path

from modules import app_service, layouts, ui_helpers


class TestUiLayoutHelpers(unittest.TestCase):
    def test_available_layout_labels_are_generic(self):
        labels = ui_helpers.available_layout_labels()

        self.assertEqual(labels, ["Four-camera standard", "Six-camera grid"])
        self.assertFalse(any("HW" in label.upper() for label in labels))

    def test_layout_display_name_maps_known_layouts(self):
        self.assertEqual(
            ui_helpers.layout_display_name(layouts.FOUR_CAMERA_DEFAULT),
            "Four-camera standard",
        )
        self.assertEqual(
            ui_helpers.layout_display_name(layouts.SIX_CAMERA_DEFAULT),
            "Six-camera grid",
        )
        self.assertEqual(ui_helpers.layout_display_name(None), "Automatic")

    def test_layout_for_display_name_returns_layout_config(self):
        self.assertIs(
            ui_helpers.layout_for_display_name("Four-camera standard"),
            layouts.FOUR_CAMERA_DEFAULT,
        )
        self.assertIs(
            ui_helpers.layout_for_display_name("Six-camera grid"),
            layouts.SIX_CAMERA_DEFAULT,
        )
        self.assertIsNone(ui_helpers.layout_for_display_name("Automatic"))

    def test_layout_diagrams_are_human_readable(self):
        four_diagram = ui_helpers.layout_diagram(layouts.FOUR_CAMERA_DEFAULT)
        six_diagram = ui_helpers.layout_diagram(layouts.SIX_CAMERA_DEFAULT)

        self.assertIn("Front", four_diagram)
        self.assertIn("Rear", four_diagram)
        self.assertIn("Left pillar", six_diagram)
        self.assertIn("Right repeater", six_diagram)

    def test_build_settings_from_options_inverts_overlay_to_no_overlay(self):
        settings = ui_helpers.build_settings_from_options(
            ui_helpers.UiRenderOptions(
                overlay_enabled=False,
                mph=True,
                keep_csv=True,
                preview=False,
                layout_label="Six-camera grid",
            )
        )

        self.assertTrue(settings.no_overlay)
        self.assertTrue(settings.mph)
        self.assertTrue(settings.keep_csv)
        self.assertFalse(settings.preview)
        self.assertIs(settings.layout, layouts.SIX_CAMERA_DEFAULT)

    def test_format_scan_summary_for_ui_replaces_internal_layout_name(self):
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            layout=layouts.FOUR_CAMERA_DEFAULT,
            camera_set="four-camera",
            clip_group_count=1,
        )

        summary = ui_helpers.format_scan_summary_for_ui(scan)

        self.assertIn("Selected layout: Four-camera standard", summary)
        self.assertNotIn("default_four_camera", summary)

    def test_format_progress_clamps_percent_and_reports_clip(self):
        progress = app_service.RenderProgress(
            timestamp="2026-06-19_23-08-01",
            clip_index=1,
            clip_count=2,
            frames_written=15,
            total_frames=10,
            status="processing",
        )

        percent, status = ui_helpers.format_progress(progress)

        self.assertEqual(percent, 100)
        self.assertIn("Clip 1/2", status)
        self.assertIn("15/10 frames", status)

    def test_default_output_folder_is_next_to_input(self):
        input_path = Path.cwd() / "TeslaCam" / "SavedClips"

        self.assertEqual(
            ui_helpers.default_output_folder(input_path),
            input_path.parent / "teslacam-telemetry-output",
        )


if __name__ == "__main__":
    unittest.main()
