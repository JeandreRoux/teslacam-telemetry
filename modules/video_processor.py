from typing import Callable

import cv2 as cv
import numpy as np
import sys
import pandas as pd
from pathlib import Path

# Import modules
from modules import config
from modules import overlay_renderer
from modules import data_handler
from modules import layouts
from modules.settings import RenderSettings

CANVAS_WIDTH = config.CANVAS_WIDTH
CANVAS_HEIGHT = config.CANVAS_HEIGHT


def can_write_mp4(output_path: Path) -> bool:
    """Return True when OpenCV can create and write a small MP4 file."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    test_file = output_path / "teslacam_telemetry_codec_check.mp4"
    writer = cv.VideoWriter(
        str(test_file),
        cv.VideoWriter_fourcc(*"mp4v"),
        1.0,
        (16, 16),
        isColor=True,
    )
    try:
        if not writer.isOpened():
            return False
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        writer.write(frame)
    finally:
        writer.release()

    try:
        return test_file.exists() and test_file.stat().st_size > 0
    finally:
        test_file.unlink(missing_ok=True)


def get_video_fps(
    input_path: Path,
    video_data: data_handler.VideoData,
) -> tuple[str, float]:
    """Return the first clip timestamp and FPS from the first available camera file."""
    first_timestamp = sorted(video_data.keys())[0]
    reference_video = data_handler.get_available_video_file(video_data[first_timestamp])
    if reference_video is None:
        sys.exit("FATAL: No reference video file found.")

    reference_video_path = input_path / reference_video
    cap_temp = cv.VideoCapture(reference_video_path)
    if not cap_temp.isOpened():
        sys.exit(
            f"FATAL: Could not open {reference_video_path} to get video properties."
        )

    fps = cap_temp.get(cv.CAP_PROP_FPS)
    cap_temp.release()

    return first_timestamp, fps


def create_video_writer(
    output_path: Path,
    output_filename: str,
    fps: float,
) -> tuple[cv.VideoWriter, Path]:
    """Create and validate the MP4 VideoWriter for the final output."""
    if output_path.exists() and not output_path.is_dir():
        sys.exit(f"Output path '{output_path}' exists but is not a directory.")

    output_path.mkdir(parents=True, exist_ok=True)
    output_filepath = output_path / f"{output_filename}.mp4"

    fourcc = cv.VideoWriter_fourcc(*"mp4v")
    out = cv.VideoWriter(
        output_filepath,
        fourcc,
        fps,
        (CANVAS_WIDTH, CANVAS_HEIGHT),
        isColor=True,
    )

    if not out.isOpened():
        sys.exit(f"FATAL: Could not create output video file: {output_filepath}")

    return out, output_filepath


def open_captures(
    input_path: Path,
    files_info: data_handler.ClipFiles,
    layout: layouts.LayoutConfig,
) -> dict[str, cv.VideoCapture]:
    """Open VideoCapture objects for the required cameras in a clip group."""
    required_cameras = layout["required_cameras"]

    captures = {}

    for camera_key in required_cameras:
        video_file = files_info.get(camera_key)
        if video_file:
            video_path = input_path / video_file
            capture = cv.VideoCapture(video_path)

            if not capture.isOpened():
                release_captures(captures)
                sys.exit(f"FATAL: Could not open {video_path}")

            captures[camera_key] = capture

    return captures


def get_total_frames(
    captures: dict[str, cv.VideoCapture],
    layout: layouts.LayoutConfig,
) -> int:
    """Return the frame count from the layout's reference camera."""
    reference_camera = layouts.get_reference_camera(layout)
    return int(captures[reference_camera].get(cv.CAP_PROP_FRAME_COUNT))


def process_video(
    captures: dict[str, cv.VideoCapture],
    telemetry_df: pd.DataFrame | None,
    out: cv.VideoWriter,
    settings: RenderSettings,
    progress_callback: Callable[[int], None] | None = None,
) -> int:
    """Render frames from the selected layout and write them to the output video.

    Returns the number of frames written. ``progress_callback`` receives the
    one-based frame count after each written frame so GUI callers can update
    progress without parsing stdout.
    """

    frame_index = 0
    overlay_renderer.reset_blinker_state()

    reference_camera = layouts.get_reference_camera(settings.layout)

    while True:
        frames = {}

        for camera_key in settings.layout["required_cameras"]:
            ret, frame = captures[camera_key].read()
            if not ret:
                return frame_index
            frames[camera_key] = frame

        # Get current frame index
        curr_frame = int(captures[reference_camera].get(cv.CAP_PROP_POS_FRAMES))

        # Create canvas
        canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)

        canvas = layouts.render_layout(canvas, frames, settings.layout)

        # Write text overlay
        if not settings.no_overlay and telemetry_df is not None:
            canvas = overlay_renderer.draw_overlay(
                canvas, curr_frame, telemetry_df, frame_index, settings
            )

        frame_index += 1

        if settings.preview:
            # Shows the video in a window
            cv.imshow("Preview", canvas)
            # Lets you quit by pressing 'q'
            if cv.waitKey(1) & 0xFF == ord("q"):
                sys.exit("User stopped program.")

        # write frame
        out.write(canvas)
        if progress_callback is not None:
            progress_callback(frame_index)


def release_captures(captures: dict[str, cv.VideoCapture]) -> None:
    """Release all open VideoCapture objects."""
    for capture in captures.values():
        capture.release()


def close_preview_windows() -> None:
    """Close any OpenCV preview windows."""
    cv.destroyAllWindows()
