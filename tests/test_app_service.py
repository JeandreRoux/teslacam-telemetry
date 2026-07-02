import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from modules import app_service
from modules import layouts
from modules.settings import RenderSettings


TIMESTAMP = "2026-06-19_23-08-01"
FOUR_CAMERAS = ("front", "back", "left_repeater", "right_repeater")
SIX_CAMERAS = (*FOUR_CAMERAS, "left_pillar", "right_pillar")


def touch_camera_files(directory: Path, cameras: tuple[str, ...], timestamp: str = TIMESTAMP) -> None:
    for camera in cameras:
        (directory / f"{timestamp}-{camera}.mp4").write_text("placeholder")


class TestBuildRenderSettings(unittest.TestCase):
    def test_uses_four_camera_default_as_placeholder_layout(self):
        settings = app_service.build_render_settings(no_overlay=True)

        self.assertTrue(settings.no_overlay)
        self.assertIs(settings.layout, layouts.FOUR_CAMERA_DEFAULT)


class TestMp4CodecCheck(unittest.TestCase):
    def test_reports_supported_codec_without_message(self):
        with patch("modules.video_processor.can_write_mp4", return_value=True):
            result = app_service.check_mp4_output_support(platform_name="Windows")

        self.assertTrue(result.is_supported)
        self.assertEqual(result.message, "")

    def test_reports_windows_ffmpeg_instruction_when_codec_is_missing(self):
        with patch("modules.video_processor.can_write_mp4", return_value=False):
            result = app_service.check_mp4_output_support(platform_name="Windows")

        self.assertFalse(result.is_supported)
        self.assertIn("MP4 video support is missing", result.message)
        self.assertIn("Open PowerShell or Command Prompt", result.message)
        self.assertIn("winget install ffmpeg", result.message)
        self.assertIn("https://ffmpeg.org/download.html", result.message)

    def test_formats_macos_and_linux_install_instructions(self):
        mac_message = app_service.format_mp4_codec_error(platform_name="Darwin")
        linux_message = app_service.format_mp4_codec_error(platform_name="Linux")

        self.assertIn("brew install ffmpeg", mac_message)
        self.assertIn("sudo apt update && sudo apt install ffmpeg", linux_message)


class TestScanInputFolder(unittest.TestCase):
    def test_returns_error_for_missing_input_directory(self):
        scan = app_service.scan_input_folder(Path("/definitely/missing"))

        self.assertFalse(scan.is_ready)
        self.assertIn("is not a directory", scan.errors[0])

    def test_scans_complete_four_camera_folder_without_side_effects(self):
        with TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            touch_camera_files(input_path, FOUR_CAMERAS)
            settings = app_service.build_render_settings(no_overlay=True)

            with patch("modules.data_handler.generate_sei_data") as generate_sei_data:
                scan = app_service.scan_input_folder(input_path, settings)

            generate_sei_data.assert_not_called()
            self.assertTrue(scan.is_ready)
            self.assertEqual(scan.camera_set, "four-camera")
            self.assertEqual(scan.clip_group_count, 1)
            self.assertIs(scan.layout, layouts.FOUR_CAMERA_DEFAULT)
            self.assertEqual(scan.errors, [])

    def test_scans_complete_six_camera_folder(self):
        with TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            touch_camera_files(input_path, SIX_CAMERAS)

            scan = app_service.scan_input_folder(input_path)

            self.assertTrue(scan.is_ready)
            self.assertEqual(scan.camera_set, "six-camera")
            self.assertEqual(scan.selected_layout_name, "default_six_camera")

    def test_reports_mixed_camera_sets_as_preflight_error(self):
        with TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            touch_camera_files(input_path, SIX_CAMERAS, TIMESTAMP)
            touch_camera_files(input_path, FOUR_CAMERAS, "2026-06-19_23-09-01")

            scan = app_service.scan_input_folder(input_path)

            self.assertFalse(scan.is_ready)
            self.assertIn("mixed or incomplete", scan.errors[0])

    def test_does_not_warn_when_overlay_requested_and_csv_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            touch_camera_files(input_path, FOUR_CAMERAS)
            settings = app_service.build_render_settings(no_overlay=False)

            scan = app_service.scan_input_folder(input_path, settings)

            self.assertTrue(scan.is_ready)
            self.assertEqual(scan.warnings, [])
            self.assertEqual(scan.telemetry_file_count, 0)

    def test_warns_when_existing_csv_is_invalid(self):
        with TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            touch_camera_files(input_path, FOUR_CAMERAS)
            (input_path / f"{TIMESTAMP}-data.csv").write_text("not,a,valid,telemetry,csv\n")
            settings = app_service.build_render_settings(no_overlay=False)

            scan = app_service.scan_input_folder(input_path, settings)

            self.assertTrue(scan.is_ready)
            self.assertTrue(
                any("existing telemetry CSV files are invalid" in warning for warning in scan.warnings)
            )


class TestBuildPreviewFrame(unittest.TestCase):
    def test_returns_none_when_scan_is_not_ready(self):
        scan = app_service.ScanResult(input_path=Path("/input"))

        self.assertIsNone(app_service.build_preview_frame(scan))

    def test_builds_preview_from_first_clip_group(self):
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            video_data={
                TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS},
            },
            layout=layouts.FOUR_CAMERA_DEFAULT,
            camera_set="four-camera",
            clip_group_count=1,
        )
        captures = {
            camera: _FakeCapture(np.full((4, 4, 3), index + 1, dtype=np.uint8))
            for index, camera in enumerate(FOUR_CAMERAS)
        }

        with patch("modules.video_processor.open_captures", return_value=captures) as open_captures, patch(
            "modules.video_processor.release_captures"
        ) as release_captures:
            preview = app_service.build_preview_frame(scan)

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.timestamp, TIMESTAMP)
        self.assertEqual(preview.image_rgb.shape, (720, 1280, 3))
        open_captures.assert_called_once_with(
            Path("/input"),
            scan.video_data[TIMESTAMP],
            layouts.FOUR_CAMERA_DEFAULT,
        )
        release_captures.assert_called_once_with(captures)


class TestFormatScanSummary(unittest.TestCase):
    def test_formats_ready_scan_summary(self):
        scan = app_service.ScanResult(
            input_path=Path("/input"),
            layout=layouts.FOUR_CAMERA_DEFAULT,
            camera_set="four-camera",
            clip_group_count=2,
            telemetry_file_count=1,
        )

        summary = app_service.format_scan_summary(scan)

        self.assertIn("Found four-camera TeslaCam set", summary)
        self.assertIn("Clip groups: 2", summary)
        self.assertIn("Selected layout: default_four_camera", summary)
        self.assertIn("Existing telemetry CSV files: 1", summary)
        self.assertIn("Ready to render", summary)


class TestRenderVideo(unittest.TestCase):
    def test_render_video_uses_shared_pipeline_and_progress_callback(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=True)
            video_data = {TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS}}
            writer = _FakeWriter()
            progress_updates = []

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ) as compile_video_data, patch(
                "modules.data_handler.validate_camera_data"
            ) as validate_camera_data, patch(
                "modules.data_handler.validate_telemetry_data"
            ) as validate_telemetry_data, patch(
                "modules.video_processor.get_video_fps", return_value=(TIMESTAMP, 5.0)
            ) as get_video_fps, patch(
                "modules.video_processor.create_video_writer",
                return_value=(writer, output_path / "TeslaCam_test.mp4"),
            ) as create_video_writer, patch(
                "modules.video_processor.open_captures", return_value={}
            ) as open_captures, patch(
                "modules.video_processor.get_total_frames", return_value=3
            ) as get_total_frames, patch(
                "modules.video_processor.process_video"
            ) as process_video, patch(
                "modules.video_processor.release_captures"
            ) as release_captures, patch(
                "modules.video_processor.close_preview_windows"
            ) as close_preview_windows, patch(
                "modules.data_handler.remove_generated_csv"
            ) as remove_generated_csv:

                def emit_progress(*, progress_callback=None, **_kwargs):
                    if progress_callback is not None:
                        progress_callback(1)
                        progress_callback(2)
                    return 2

                process_video.side_effect = emit_progress

                result = app_service.render_video(
                    app_service.RenderJob(input_path, output_path, settings),
                    progress_callback=progress_updates.append,
                )

            compile_video_data.assert_called_once_with(
                input_path,
                settings,
                generate_missing_telemetry=False,
            )
            validate_camera_data.assert_called_once_with(video_data, layouts.FOUR_CAMERA_DEFAULT)
            validate_telemetry_data.assert_called_once_with(settings, video_data, input_path)
            get_video_fps.assert_called_once_with(input_path, video_data)
            create_video_writer.assert_called_once()
            open_captures.assert_called_once()
            get_total_frames.assert_called_once()
            process_video.assert_called_once()
            release_captures.assert_called_once_with({})
            close_preview_windows.assert_called_once()
            remove_generated_csv.assert_called_once_with(input_path, video_data, settings)
            self.assertTrue(writer.released)
            self.assertEqual(result.output_path, output_path / "TeslaCam_test.mp4")
            self.assertEqual(result.clip_count, 1)
            self.assertEqual(result.selected_layout_name, "default_four_camera")
            self.assertEqual([update.frames_written for update in progress_updates], [1, 2])
            self.assertEqual(progress_updates[0].timestamp, TIMESTAMP)
            self.assertEqual(progress_updates[0].clip_index, 1)
            self.assertEqual(progress_updates[0].clip_count, 1)
            self.assertEqual(progress_updates[0].total_frames, 3)

    def test_render_video_prompts_for_partial_selected_telemetry_before_writer_starts(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=False)
            later_timestamp = "2026-06-19_23-09-01"
            video_data = {
                TIMESTAMP: {
                    **{camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS},
                    "data": f"{TIMESTAMP}-data.csv",
                },
                later_timestamp: {
                    **{camera: f"{later_timestamp}-{camera}.mp4" for camera in FOUR_CAMERAS},
                    "data": f"{later_timestamp}-data.csv",
                },
            }

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ), patch(
                "modules.data_handler.validate_camera_data"
            ), patch(
                "modules.data_handler.generate_sei_data", return_value=video_data
            ), patch(
                "modules.data_handler.validate_telemetry_data"
            ), patch(
                "modules.video_processor.open_captures", return_value={}
            ) as open_captures, patch(
                "modules.video_processor.get_total_frames", return_value=3
            ), patch(
                "modules.video_processor.release_captures"
            ) as release_captures, patch(
                "modules.data_handler.telemetry_csv_matches_frame_count",
                side_effect=[True, False],
            ), patch(
                "modules.video_processor.create_video_writer"
            ) as create_video_writer, patch(
                "modules.data_handler.remove_generated_csv"
            ):
                with self.assertRaisesRegex(
                    app_service.TelemetryPromptRequired,
                    "Continue rendering without the telemetry overlay",
                ) as raised:
                    app_service.render_video(
                        app_service.RenderJob(
                            input_path,
                            output_path,
                            settings,
                            selected_timestamps=(TIMESTAMP, later_timestamp),
                            prompt_for_telemetry=True,
                        )
                    )

            self.assertIn(later_timestamp, raised.exception.details)
            self.assertIn(f"{later_timestamp}-data.csv", raised.exception.details)
            self.assertEqual(open_captures.call_count, 2)
            self.assertEqual(release_captures.call_count, 2)
            create_video_writer.assert_not_called()

    def test_render_video_raises_desktop_telemetry_prompt_before_using_input(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=False)
            video_data = {TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS}}

            def request_prompt(settings, _video_data, _input_path):
                assert settings.telemetry_prompt is not None
                settings.telemetry_prompt()

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ), patch(
                "modules.data_handler.validate_camera_data"
            ), patch(
                "modules.data_handler.generate_sei_data", return_value=video_data
            ), patch(
                "modules.data_handler.validate_telemetry_data", side_effect=request_prompt
            ):
                with self.assertRaisesRegex(
                    app_service.TelemetryPromptRequired,
                    "Continue rendering without the telemetry overlay",
                ):
                    app_service.render_video(
                        app_service.RenderJob(
                            input_path,
                            output_path,
                            settings,
                            prompt_for_telemetry=True,
                        )
                    )

    def test_render_video_uses_selected_clip_groups_when_provided(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=True)
            selected_timestamp = "2026-06-19_23-09-01"
            video_data = {
                TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS},
                selected_timestamp: {camera: f"{selected_timestamp}-{camera}.mp4" for camera in FOUR_CAMERAS},
            }
            selected_video_data = {selected_timestamp: video_data[selected_timestamp]}
            writer = _FakeWriter()

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ) as compile_video_data, patch("modules.data_handler.validate_camera_data"), patch(
                "modules.data_handler.validate_telemetry_data"
            ), patch(
                "modules.video_processor.get_video_fps", return_value=(selected_timestamp, 5.0)
            ) as get_video_fps, patch(
                "modules.video_processor.create_video_writer",
                return_value=(writer, output_path / f"TeslaCam_{selected_timestamp}.mp4"),
            ), patch(
                "modules.video_processor.open_captures", return_value={}
            ) as open_captures, patch(
                "modules.video_processor.get_total_frames", return_value=1
            ), patch(
                "modules.video_processor.process_video"
            ), patch(
                "modules.video_processor.release_captures"
            ), patch(
                "modules.video_processor.close_preview_windows"
            ), patch(
                "modules.data_handler.remove_generated_csv"
            ) as remove_generated_csv:
                result = app_service.render_video(
                    app_service.RenderJob(
                        input_path,
                        output_path,
                        settings,
                        selected_timestamps=(selected_timestamp,),
                    )
                )

            compile_video_data.assert_called_once_with(
                input_path,
                settings,
                generate_missing_telemetry=False,
            )
            get_video_fps.assert_called_once_with(input_path, selected_video_data)
            open_captures.assert_called_once_with(
                input_path=input_path,
                files_info=selected_video_data[selected_timestamp],
                layout=layouts.FOUR_CAMERA_DEFAULT,
            )
            remove_generated_csv.assert_called_once_with(input_path, selected_video_data, settings)
            self.assertEqual(result.clip_count, 1)
            self.assertEqual(result.output_path, output_path / f"TeslaCam_{selected_timestamp}.mp4")

    def test_render_video_generates_telemetry_only_for_selected_clip_groups(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=False)
            selected_timestamp = "2026-06-19_23-09-01"
            video_data = {
                TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS},
                selected_timestamp: {camera: f"{selected_timestamp}-{camera}.mp4" for camera in FOUR_CAMERAS},
            }
            selected_video_data = {selected_timestamp: video_data[selected_timestamp]}
            generated_video_data = {
                selected_timestamp: {
                    **video_data[selected_timestamp],
                    "data": f"{selected_timestamp}-generated_sei.csv",
                }
            }
            writer = _FakeWriter()

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ), patch("modules.data_handler.validate_camera_data"), patch(
                "modules.data_handler.generate_sei_data", return_value=generated_video_data
            ) as generate_sei_data, patch(
                "modules.data_handler.validate_telemetry_data"
            ) as validate_telemetry_data, patch(
                "modules.video_processor.get_video_fps", return_value=(selected_timestamp, 5.0)
            ), patch(
                "modules.video_processor.create_video_writer",
                return_value=(writer, output_path / f"TeslaCam_{selected_timestamp}.mp4"),
            ), patch(
                "modules.video_processor.open_captures", return_value={}
            ), patch(
                "modules.video_processor.get_total_frames", return_value=1
            ), patch(
                "modules.data_handler.telemetry_csv_matches_frame_count", return_value=True
            ), patch(
                "modules.data_handler.load_telemetry_data"
            ), patch(
                "modules.video_processor.process_video"
            ), patch(
                "modules.video_processor.release_captures"
            ), patch(
                "modules.video_processor.close_preview_windows"
            ), patch(
                "modules.data_handler.remove_generated_csv"
            ) as remove_generated_csv:
                result = app_service.render_video(
                    app_service.RenderJob(
                        input_path,
                        output_path,
                        settings,
                        selected_timestamps=(selected_timestamp,),
                    )
                )

            generate_sei_data.assert_called_once_with(selected_video_data, input_path, settings)
            validate_telemetry_data.assert_called_once_with(settings, generated_video_data, input_path)
            remove_generated_csv.assert_called_once_with(input_path, generated_video_data, settings)
            self.assertEqual(result.clip_count, 1)

    def test_render_video_removes_partial_output_when_cancelled(self):
        with TemporaryDirectory() as temp_input, TemporaryDirectory() as temp_output:
            input_path = Path(temp_input)
            output_path = Path(temp_output)
            settings = app_service.build_render_settings(no_overlay=True)
            video_data = {TIMESTAMP: {camera: f"{TIMESTAMP}-{camera}.mp4" for camera in FOUR_CAMERAS}}
            output_file = output_path / f"TeslaCam_{TIMESTAMP}.mp4"
            output_file.write_bytes(b"partial output")
            writer = _FakeWriter()
            cancel_after_progress = {"called": False}

            def cancel_requested():
                return cancel_after_progress["called"]

            def process_video(*, progress_callback=None, **_kwargs):
                cancel_after_progress["called"] = True
                if progress_callback is not None:
                    progress_callback(1)

            with patch(
                "modules.data_handler.compile_video_data", return_value=video_data
            ), patch("modules.data_handler.validate_camera_data"), patch(
                "modules.data_handler.validate_telemetry_data"
            ), patch(
                "modules.video_processor.get_video_fps", return_value=(TIMESTAMP, 5.0)
            ), patch(
                "modules.video_processor.create_video_writer",
                return_value=(writer, output_file),
            ), patch(
                "modules.video_processor.open_captures", return_value={}
            ), patch(
                "modules.video_processor.get_total_frames", return_value=1
            ), patch(
                "modules.video_processor.process_video", side_effect=process_video
            ), patch(
                "modules.video_processor.release_captures"
            ), patch(
                "modules.video_processor.close_preview_windows"
            ), patch(
                "modules.data_handler.remove_generated_csv"
            ):
                with self.assertRaisesRegex(app_service.RenderCancelled, "Render cancelled"):
                    app_service.render_video(
                        app_service.RenderJob(
                            input_path,
                            output_path,
                            settings,
                            cancel_requested=cancel_requested,
                        )
                    )

            self.assertTrue(writer.released)
            self.assertFalse(output_file.exists())


class _FakeCapture:
    def __init__(self, frame):
        self.frame = frame

    def read(self):
        return True, self.frame


class _FakeWriter:
    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


if __name__ == "__main__":
    unittest.main()
