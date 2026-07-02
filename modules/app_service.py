from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import platform
from pathlib import Path
import tempfile

import cv2 as cv
import numpy as np

from modules import data_handler
from modules import layouts
from modules import video_processor
from modules.settings import RenderSettings


@dataclass(frozen=True)
class PreviewFrame:
    """Still preview image composed from the first detected clip group."""

    timestamp: str
    image_rgb: Any


@dataclass(frozen=True)
class ScanResult:
    """Side-effect-free summary of a TeslaCam input folder."""

    input_path: Path
    video_data: data_handler.VideoData = field(default_factory=dict)
    layout: layouts.LayoutConfig | None = None
    camera_set: str | None = None
    clip_group_count: int = 0
    telemetry_file_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    preview_frame: PreviewFrame | None = None

    @property
    def is_ready(self) -> bool:
        """Return True when the folder can proceed to render preflight."""
        return not self.errors and self.layout is not None and self.clip_group_count > 0

    @property
    def selected_layout_name(self) -> str | None:
        """Return the selected layout's internal name, if one was selected."""
        if self.layout is None:
            return None
        return self.layout["name"]


@dataclass(frozen=True)
class RenderJob:
    """Inputs required to render TeslaCam footage."""

    input_path: Path
    output_path: Path
    settings: RenderSettings


@dataclass(frozen=True)
class RenderProgress:
    """Progress update emitted while rendering a clip group."""

    timestamp: str
    clip_index: int
    clip_count: int
    frames_written: int
    total_frames: int
    status: str


@dataclass(frozen=True)
class RenderResult:
    """Result of a completed render."""

    output_path: Path
    clip_count: int
    selected_layout_name: str


@dataclass(frozen=True)
class CodecCheckResult:
    """Result of checking whether MP4 output can be written."""

    is_supported: bool
    message: str = ""


ProgressCallback = Callable[[RenderProgress], None]


def build_render_settings(
    *,
    no_overlay: bool = False,
    mph: bool = False,
    preview: bool = False,
    keep_csv: bool = False,
    layout: layouts.LayoutConfig | None = None,
) -> RenderSettings:
    """Create render settings with the current default layout placeholder."""
    return RenderSettings(
        no_overlay=no_overlay,
        mph=mph,
        preview=preview,
        keep_csv=keep_csv,
        layout=layout or layouts.FOUR_CAMERA_DEFAULT,
    )


def check_mp4_output_support(
    *,
    probe_dir: Path | None = None,
    platform_name: str | None = None,
) -> CodecCheckResult:
    """Check whether OpenCV can write an MP4 file on this machine."""
    cleanup_dir = None
    try:
        if probe_dir is None:
            cleanup_dir = tempfile.TemporaryDirectory()
            probe_dir = Path(cleanup_dir.name)
        else:
            probe_dir = Path(probe_dir)
            probe_dir.mkdir(parents=True, exist_ok=True)

        if video_processor.can_write_mp4(probe_dir):
            return CodecCheckResult(is_supported=True)
    except Exception as error:
        detail = str(error)
    else:
        detail = "OpenCV could not create a test MP4 file."
    finally:
        if cleanup_dir is not None:
            cleanup_dir.cleanup()

    return CodecCheckResult(
        is_supported=False,
        message=format_mp4_codec_error(platform_name=platform_name, detail=detail),
    )


def format_mp4_codec_error(
    *,
    platform_name: str | None = None,
    detail: str | None = None,
) -> str:
    """Return OS-specific guidance for missing MP4 output support."""
    system = platform_name or platform.system()
    instructions = _ffmpeg_install_instructions(system)
    lines = [
        "MP4 video support is missing.",
        "",
        "TeslaCam Telemetry needs MP4 video support to create the finished video.",
        "Install FFmpeg, then restart the app and try again.",
        "",
        instructions,
        "",
        "FFmpeg downloads: https://ffmpeg.org/download.html",
    ]
    if detail:
        lines.extend(["", f"Details: {detail}"])
    return "\n".join(lines)


def _ffmpeg_install_instructions(platform_name: str) -> str:
    system = platform_name.lower()
    if system == "windows":
        return "Open PowerShell or Command Prompt and run:\nwinget install ffmpeg"
    if system == "darwin":
        return "Open Terminal and run:\nbrew install ffmpeg"
    if system == "linux":
        return "Open Terminal and run:\nsudo apt update && sudo apt install ffmpeg"
    return "Install FFmpeg using the recommended package manager for your operating system."


def scan_input_folder(input_path: Path, settings: RenderSettings | None = None) -> ScanResult:
    """Inspect an input folder without generating telemetry or prompting the user."""
    input_path = Path(input_path)
    settings = settings or build_render_settings(no_overlay=True)

    errors: list[str] = []
    warnings: list[str] = []

    if not input_path.is_dir():
        return ScanResult(
            input_path=input_path,
            errors=[f"Input path '{input_path}' is not a directory."],
        )

    video_data = data_handler.compile_video_data(
        input_path,
        settings,
        generate_missing_telemetry=False,
    )
    clip_group_count = len(video_data)
    telemetry_file_count = sum(
        1 for files_info in video_data.values() if files_info.get("data")
    )

    try:
        layout = layouts.select_default_layout(video_data)
    except ValueError as error:
        return ScanResult(
            input_path=input_path,
            video_data=video_data,
            clip_group_count=clip_group_count,
            telemetry_file_count=telemetry_file_count,
            errors=[str(error)],
        )

    missing_camera_groups = data_handler.get_missing_camera_groups(video_data, layout)
    if missing_camera_groups:
        errors.append("Missing camera files for the selected layout.")
        for timestamp, missing_cameras in missing_camera_groups:
            warnings.append(f"{timestamp}: missing {', '.join(missing_cameras)}")

    if not settings.no_overlay:
        invalid_existing_telemetry = _get_invalid_existing_telemetry_groups(
            video_data,
            input_path,
        )
        if invalid_existing_telemetry:
            warnings.append(
                "One or more existing telemetry CSV files are invalid. "
                "Render may regenerate telemetry from SEI or ask to continue without overlays."
            )
            for timestamp, reason in invalid_existing_telemetry:
                warnings.append(f"{timestamp}: {reason}")

    camera_set = _camera_set_for_layout(layout)

    return ScanResult(
        input_path=input_path,
        video_data=video_data,
        layout=layout,
        camera_set=camera_set,
        clip_group_count=clip_group_count,
        telemetry_file_count=telemetry_file_count,
        warnings=warnings,
        errors=errors,
    )


def build_preview_frame(scan_result: ScanResult) -> PreviewFrame | None:
    """Return a still layout preview for the first detected clip group, if possible."""
    if not scan_result.is_ready or scan_result.layout is None or not scan_result.video_data:
        return None

    timestamp = sorted(scan_result.video_data.keys())[0]
    files_info = scan_result.video_data[timestamp]
    captures = {}

    try:
        captures = video_processor.open_captures(
            scan_result.input_path,
            files_info,
            scan_result.layout,
        )
        frames = {}
        for camera_key in scan_result.layout["required_cameras"]:
            ok, frame = captures[camera_key].read()
            if not ok:
                return None
            frames[camera_key] = frame

        canvas = np.zeros(
            (video_processor.CANVAS_HEIGHT, video_processor.CANVAS_WIDTH, 3),
            dtype=np.uint8,
        )
        preview_bgr = layouts.render_layout(canvas, frames, scan_result.layout)
        preview_rgb = cv.cvtColor(preview_bgr, cv.COLOR_BGR2RGB)
        return PreviewFrame(timestamp=timestamp, image_rgb=preview_rgb)
    except (Exception, SystemExit):
        return None
    finally:
        if captures:
            video_processor.release_captures(captures)


def render_video(
    job: RenderJob,
    progress_callback: ProgressCallback | None = None,
) -> RenderResult:
    """Render a TeslaCam video using the shared app service pipeline."""
    input_path = Path(job.input_path)
    output_path = Path(job.output_path)
    settings = job.settings

    if not input_path.is_dir():
        raise SystemExit(f"Input path '{input_path}' is not a directory.")

    video_data: data_handler.VideoData = {}

    try:
        video_data = data_handler.compile_video_data(input_path, settings)
        try:
            settings.layout = layouts.select_default_layout(video_data)
        except ValueError as error:
            raise SystemExit(str(error)) from error

        print(f"Selected layout: {settings.layout['name']}")
        data_handler.validate_camera_data(video_data, settings.layout)
        data_handler.validate_telemetry_data(settings, video_data, input_path)

        first_timestamp, fps = video_processor.get_video_fps(input_path, video_data)
        output_filename = _output_filename(first_timestamp, settings)

        out, output_filepath = video_processor.create_video_writer(
            output_path=output_path,
            output_filename=output_filename,
            fps=fps,
        )

        sorted_timestamps = sorted(video_data.keys())
        clip_count = len(sorted_timestamps)

        try:
            for clip_index, timestamp in enumerate(sorted_timestamps, start=1):
                telemetry_df = None

                captures = video_processor.open_captures(
                    input_path=input_path,
                    files_info=video_data[timestamp],
                    layout=settings.layout,
                )

                try:
                    total_frames = video_processor.get_total_frames(
                        captures,
                        settings.layout,
                    )

                    data_file = video_data[timestamp].get("data")
                    if data_file:
                        telemetry_df = data_handler.load_telemetry_data(
                            input_path=input_path,
                            data_file=data_file,
                            total_frames=total_frames,
                            settings=settings,
                        )

                    if settings.preview:
                        print("Loading preview... press 'q' to quit.")
                        print("Processing videos...")
                    else:
                        print("Processing videos...")

                    def on_frame(frames_written: int) -> None:
                        if progress_callback is None:
                            return
                        progress_callback(
                            RenderProgress(
                                timestamp=timestamp,
                                clip_index=clip_index,
                                clip_count=clip_count,
                                frames_written=frames_written,
                                total_frames=total_frames,
                                status="processing",
                            )
                        )

                    video_processor.process_video(
                        captures=captures,
                        telemetry_df=telemetry_df,
                        out=out,
                        settings=settings,
                        progress_callback=on_frame,
                    )
                finally:
                    video_processor.release_captures(captures)

            print(f"Finished all clips. Released final video file: {output_filepath}")
        finally:
            out.release()
            video_processor.close_preview_windows()
    finally:
        data_handler.remove_generated_csv(input_path, video_data, settings)

    return RenderResult(
        output_path=output_filepath,
        clip_count=len(video_data),
        selected_layout_name=settings.layout["name"],
    )


def format_scan_summary(scan_result: ScanResult) -> str:
    """Format a scan result for CLI/UI status panels."""
    lines: list[str] = []

    if scan_result.camera_set:
        lines.append(f"Found {scan_result.camera_set} TeslaCam set")
    lines.append(f"Clip groups: {scan_result.clip_group_count}")

    if scan_result.selected_layout_name:
        lines.append(f"Selected layout: {scan_result.selected_layout_name}")

    if scan_result.telemetry_file_count:
        lines.append(f"Existing telemetry CSV files: {scan_result.telemetry_file_count}")
    elif scan_result.is_ready:
        lines.append("Telemetry source: SEI extraction will run during render if overlays are enabled")

    if scan_result.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in scan_result.warnings)

    if scan_result.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in scan_result.errors)
    elif scan_result.is_ready:
        lines.append("Ready to render")

    return "\n".join(lines)


def _get_invalid_existing_telemetry_groups(
    video_data: data_handler.VideoData,
    input_path: Path,
) -> list[tuple[str, str]]:
    """Return invalid telemetry CSVs that already exist in the input folder.

    Missing CSV files are not a scan warning because normal render behavior is to
    generate them from embedded SEI data when overlays are enabled.
    """
    invalid_data_timestamps = []

    for timestamp, files_info in video_data.items():
        data_file = files_info.get("data")
        if data_file is None:
            continue

        csv_path = input_path / data_file
        if not data_handler.telemetry_csv_is_valid(csv_path):
            invalid_data_timestamps.append(
                (timestamp, f"invalid telemetry CSV: {data_file}")
            )

    return invalid_data_timestamps


def _camera_set_for_layout(layout: layouts.LayoutConfig) -> str:
    required_cameras = layout["required_cameras"]
    if required_cameras == layouts.SIX_CAMERA_KEYS:
        return "six-camera"
    if required_cameras == layouts.FOUR_CAMERA_KEYS:
        return "four-camera"
    return f"{len(required_cameras)}-camera"


def _output_filename(first_timestamp: str, settings: RenderSettings) -> str:
    if settings.no_overlay:
        return f"TeslaCam_{first_timestamp}_no-overlay"
    return f"TeslaCam_{first_timestamp}"
