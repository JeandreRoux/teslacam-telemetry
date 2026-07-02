import os
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from modules import app_service, layouts


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


try:
    import desktop_ui
except ImportError as error:  # pragma: no cover - only used when optional UI deps are absent locally
    desktop_ui = None
    IMPORT_ERROR = error
else:
    IMPORT_ERROR = None


@unittest.skipIf(desktop_ui is None, f"desktop UI dependencies unavailable: {IMPORT_ERROR}")
class TestDesktopUiLayoutState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert desktop_ui is not None
        try:
            cls.qt = desktop_ui._load_qt()
        except ImportError as error:
            raise unittest.SkipTest(f"desktop UI dependencies unavailable: {error}") from error
        cls.QApplication = cls.qt["QApplication"]
        cls.app = cls.QApplication.instance() or cls.QApplication([])
        cls.MainWindow = desktop_ui.create_main_window(cls.qt)

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            widget.close()

    def test_launch_does_not_show_default_layout_before_input_scan(self):
        with patch_supported_codec():
            window = self.MainWindow()

        self.assertEqual(window.layout_combo.count(), 0)
        self.assertEqual(window.layout_combo.currentText(), "")
        self.assertEqual(window.layout_combo.placeholderText(), "Automatic layout")
        self.assertIn("Preview", window.diagram_label.text())
        self.assertEqual(window.status_label.text(), "Add an input folder to begin.")
        self.assertEqual(window.layout_combo.toolTip(), "")
        self.assertEqual(window.diagram_label.toolTip(), "")
        self.assertFalse(window.render_button.isEnabled())

    def test_scan_result_populates_detected_layout(self):
        with patch_supported_codec():
            window = self.MainWindow()
        window.input_edit.setText("/input")
        window.output_edit.setText("/output")
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            video_data=clip_group_video_data(layouts.SIX_CAMERA_KEYS, count=2),
            layout=layouts.SIX_CAMERA_DEFAULT,
            camera_set="six-camera",
            clip_group_count=2,
        )

        window._on_scan_finished(scan)
        window._sync_buttons()

        self.assertEqual(window.layout_combo.currentText(), "Six-camera grid")
        self.assertIn("Left pillar", window.diagram_label.text())
        self.assertEqual(window.clip_summary_label.text(), "Clips selected: all 2")
        self.assertEqual(
            window._selected_clip_timestamps(),
            ("2026-06-19_23-08-01", "2026-06-19_23-09-01"),
        )
        self.assertTrue(window.customize_clips_button.isEnabled())
        self.assertEqual(window.status_label.text(), "Ready to render.")
        self.assertEqual(window.progress.value(), 0)
        self.assertTrue(window.render_button.isEnabled())
        self.assertTrue(window.input_browse_button.isEnabled())
        self.assertTrue(window.output_browse_button.isEnabled())

        window._thread = object()
        window._sync_buttons()

        self.assertFalse(window.render_button.isEnabled())
        self.assertFalse(window.customize_clips_button.isEnabled())
        self.assertFalse(window.input_browse_button.isEnabled())
        self.assertFalse(window.output_browse_button.isEnabled())

        window._thread = None
        window._sync_buttons()

        self.assertTrue(window.customize_clips_button.isEnabled())
        self.assertTrue(window.input_browse_button.isEnabled())
        self.assertTrue(window.output_browse_button.isEnabled())

        window.progress.setValue(100)
        window._set_selected_timestamps(("2026-06-19_23-09-01",))

        self.assertEqual(window.progress.value(), 0)
        self.assertEqual(window.clip_summary_label.text(), "Clips selected: 1 of 2")
        self.assertTrue(window.render_button.isEnabled())

        window._set_selected_timestamps(())

        self.assertEqual(window.clip_summary_label.text(), "Clips selected: 0 of 2")
        self.assertEqual(window.status_label.text(), "Select at least one clip to render.")
        self.assertFalse(window.render_button.isEnabled())

    def test_customized_clip_selection_updates_layout_preview(self):
        with patch_supported_codec():
            window = self.MainWindow()
        window.input_edit.setText("/input")
        window.output_edit.setText("/output")
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            video_data=clip_group_video_data(layouts.SIX_CAMERA_KEYS, count=2),
            layout=layouts.SIX_CAMERA_DEFAULT,
            camera_set="six-camera",
            clip_group_count=2,
        )
        preview = app_service.PreviewFrame(
            timestamp="2026-06-19_23-09-01",
            image_rgb=np.zeros((720, 1280, 3), dtype=np.uint8),
        )

        window._on_scan_finished(scan)
        with patch("modules.app_service.build_layout_preview_frame", return_value=preview) as build_preview:
            window._set_selected_timestamps(("2026-06-19_23-09-01",))

        build_preview.assert_called_once_with(scan, "2026-06-19_23-09-01")
        pixmap = window.diagram_label.pixmap()
        self.assertIsNotNone(pixmap)
        assert pixmap is not None
        self.assertFalse(pixmap.isNull())
        self.assertEqual(window.diagram_label.text(), "")
        self.assertIn("2026-06-19_23-09-01", window.diagram_label.toolTip())

    def test_scan_result_shows_preview_frame_when_available(self):
        with patch_supported_codec():
            window = self.MainWindow()
        window.input_edit.setText("/input")
        window.output_edit.setText("/output")
        preview = app_service.PreviewFrame(
            timestamp="2026-06-19_23-08-01",
            image_rgb=np.zeros((720, 1280, 3), dtype=np.uint8),
        )
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            video_data=clip_group_video_data(layouts.FOUR_CAMERA_KEYS),
            layout=layouts.FOUR_CAMERA_DEFAULT,
            camera_set="four-camera",
            clip_group_count=1,
            preview_frame=preview,
        )

        window._on_scan_finished(scan)

        pixmap = window.diagram_label.pixmap()
        self.assertIsNotNone(pixmap)
        assert pixmap is not None
        self.assertFalse(pixmap.isNull())
        self.assertEqual(window.diagram_label.text(), "")
        self.assertIn("2026-06-19_23-08-01", window.diagram_label.toolTip())

    def test_telemetry_prompt_can_retry_render_without_overlay(self):
        prompts = []

        class FakeMessageBox:
            class Icon:
                Warning = "warning"

            class StandardButton:
                Yes = 1
                No = 2

            def __init__(self, parent=None):
                self.parent = parent
                self.title = ""
                self.message = ""
                self.informative_text = ""
                self.detailed_text = ""
                self.stylesheet = ""

            def setIcon(self, icon):
                self.icon = icon

            def setWindowTitle(self, title):
                self.title = title

            def setText(self, message):
                self.message = message

            def setInformativeText(self, informative_text):
                self.informative_text = informative_text

            def setDetailedText(self, detailed_text):
                self.detailed_text = detailed_text

            def setStandardButtons(self, buttons):
                self.buttons = buttons

            def setDefaultButton(self, button):
                self.default_button = button

            def setStyleSheet(self, stylesheet):
                self.stylesheet = stylesheet

            def exec(self):
                prompts.append(self)
                return self.StandardButton.Yes

        qt = dict(self.qt)
        qt["QMessageBox"] = FakeMessageBox
        assert desktop_ui is not None
        MainWindow = desktop_ui.create_main_window(qt)

        with patch_supported_codec():
            window = MainWindow()
        render_calls = []
        window.render = lambda: render_calls.append("render")

        window._on_telemetry_prompt_required(
            app_service.TelemetryPromptRequired(
                "Telemetry data is incomplete or unavailable for one or more selected clips.\n\n"
                "Continue rendering without the telemetry overlay?",
                details="The following selected clips have partial telemetry data:\n\n- 2026-06-19_23-09-01: 2026-06-19_23-09-01-data.csv",
            )
        )

        self.assertFalse(window.overlay_check.isChecked())
        self.assertEqual(render_calls, ["render"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].title, "Incomplete telemetry data")
        self.assertEqual(prompts[0].informative_text, "")
        self.assertIn("2026-06-19_23-09-01", prompts[0].detailed_text)
        self.assertIn("2026-06-19_23-09-01-data.csv", prompts[0].detailed_text)
        self.assertIn("without the telemetry overlay", prompts[0].message)
        self.assertIn("Continuing without telemetry overlay.", window.log_panel.toPlainText())

        window._worker_stopped()

        self.assertEqual(render_calls, ["render"])

    def test_cancel_render_requests_worker_stop_and_reports_cancelled(self):
        with patch_supported_codec():
            window = self.MainWindow()

        class FakeWorker:
            def __init__(self):
                self.cancelled = False

            def cancel(self):
                self.cancelled = True

        worker = FakeWorker()
        window._thread = object()
        window._worker = worker  # type: ignore[assignment]
        window._active_action = "render"
        window._sync_buttons()

        self.assertFalse(window.render_button.isEnabled())
        self.assertTrue(window.cancel_button.isEnabled())

        window.cancel_render()

        self.assertTrue(worker.cancelled)
        self.assertFalse(window.cancel_button.isEnabled())
        self.assertEqual(window.status_label.text(), "Cancelling render…")
        self.assertIn("Cancelling render…", window.log_panel.toPlainText())

        window._on_render_cancelled("Render cancelled.")

        self.assertEqual(window.progress.value(), 0)
        self.assertEqual(window.status_label.text(), "Render cancelled.")
        self.assertIn("Partial output was removed.", window.log_panel.toPlainText())

    def test_launch_warns_when_mp4_codec_is_missing(self):
        warnings = []

        class FakeMessageBox:
            class Icon:
                Warning = "warning"

            class StandardButton:
                Ok = "ok"

            def __init__(self, parent=None):
                self.parent = parent
                self.title = ""
                self.message = ""
                self.informative_text = ""
                self.detailed_text = ""
                self.stylesheet = ""

            def setIcon(self, icon):
                self.icon = icon

            def setWindowTitle(self, title):
                self.title = title

            def setText(self, message):
                self.message = message

            def setInformativeText(self, informative_text):
                self.informative_text = informative_text

            def setDetailedText(self, detailed_text):
                self.detailed_text = detailed_text

            def setStandardButtons(self, buttons):
                self.buttons = buttons

            def setStyleSheet(self, stylesheet):
                self.stylesheet = stylesheet

            def exec(self):
                warnings.append((self.title, self.message, self.stylesheet))

        qt = dict(self.qt)
        qt["QMessageBox"] = FakeMessageBox
        assert desktop_ui is not None
        MainWindow = desktop_ui.create_main_window(qt)

        with patch(
            "modules.app_service.check_mp4_output_support",
            return_value=app_service.CodecCheckResult(
                is_supported=False,
                message="MP4 video support is missing.\n\nOpen PowerShell or Command Prompt and run:\nwinget install ffmpeg",
            ),
        ):
            window = MainWindow()

        self.assertEqual(warnings[0][0], "MP4 video support is missing")
        self.assertIn("Open PowerShell or Command Prompt", warnings[0][1])
        self.assertIn("winget install ffmpeg", warnings[0][1])
        self.assertIn("#10141f", warnings[0][2])
        self.assertEqual(window.status_label.text(), "Install FFmpeg, then restart the app.")
        self.assertFalse(window.render_button.isEnabled())
        self.assertIn("winget install ffmpeg", window.log_panel.toPlainText())

        window.input_edit.setText("/input")
        window.output_edit.setText("/output")
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            layout=layouts.SIX_CAMERA_DEFAULT,
            camera_set="six-camera",
            clip_group_count=2,
        )
        window._on_scan_finished(scan)
        window._sync_buttons()

        self.assertEqual(window.status_label.text(), "Install FFmpeg, then restart the app.")
        self.assertFalse(window.render_button.isEnabled())


def clip_group_video_data(cameras: tuple[str, ...], *, count: int = 1):
    timestamps = ["2026-06-19_23-08-01", "2026-06-19_23-09-01", "2026-06-19_23-10-01"]
    return {
        timestamp: {camera: f"{timestamp}-{camera}.mp4" for camera in cameras}
        for timestamp in timestamps[:count]
    }


def patch_supported_codec():
    return patch(
        "modules.app_service.check_mp4_output_support",
        return_value=app_service.CodecCheckResult(is_supported=True),
    )


if __name__ == "__main__":
    unittest.main()
