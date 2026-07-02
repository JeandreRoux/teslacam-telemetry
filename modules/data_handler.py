from typing import Mapping

import re
import sys
import pandas as pd
from pathlib import Path

# Import modules
from modules import sei_extractor
from modules import layouts
from modules.settings import RenderSettings

CAMERA_KEYS = layouts.ALL_CAMERA_KEYS

DEFAULT_REQUIRED_CAMERAS = layouts.FOUR_CAMERA_KEYS

REQUIRED_TELEMETRY_COLUMNS = (
    "gear_state",
    "vehicle_speed_mps",
    "accelerator_pedal_position",
    "steering_wheel_angle",
    "blinker_on_left",
    "blinker_on_right",
    "brake_applied",
    "autopilot_state",
)

ClipFiles = dict[str, str | None]
VideoData = dict[str, ClipFiles]


def compile_video_data(
    input_path: Path,
    settings: RenderSettings,
    *,
    generate_missing_telemetry: bool = True,
) -> VideoData:
    """Build clip groups from Tesla dashcam filenames in the input directory.

    By default this preserves the CLI behavior of generating missing telemetry CSV
    files from embedded SEI data. UI/preflight callers can disable that side
    effect by passing ``generate_missing_telemetry=False``.
    """
    pattern = re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})-([a-z_]+)\.(mp4|csv)"
    )

    video_data = {}

    for item in input_path.iterdir():
        if not item.is_file():
            continue

        match = pattern.search(item.name)

        if match:
            timestamp = match.group(1)
            file_id = match.group(2)
            extension = match.group(3)

            video_data.setdefault(timestamp, {})
            video_data[timestamp].setdefault("data", None)

            if extension == "csv":
                video_data[timestamp]["data"] = item.name
                print(f"Found telemetry CSV: {video_data[timestamp]['data']}")
            else:
                video_data[timestamp][file_id] = item.name
    if generate_missing_telemetry and not settings.no_overlay:
        video_data = generate_sei_data(video_data, input_path, settings)

    return video_data


def get_available_video_file(files_info: Mapping[str, str | None]) -> str | None:
    """Return the first available video filename in camera preference order."""
    for camera_key in layouts.CAMERA_REFERENCE_PREFERENCE:
        video_file = files_info.get(camera_key)
        if video_file:
            return video_file

    return None


def generate_sei_data(
    video_data: VideoData,
    input_path: Path,
    settings: RenderSettings,
) -> VideoData:
    """Generate missing telemetry CSV files from embedded SEI metadata."""
    # Auto-generate missing CSV from SEI data
    for timestamp, files_info in video_data.items():
        if files_info.get("data") is not None:
            continue

        video_file = get_available_video_file(files_info)
        if video_file is None:
            continue

        mp4_path = input_path / video_file
        csv_path = input_path / f"{timestamp}-generated_sei.csv"
        print(f"Generating telemetry CSV from SEI: {csv_path}")
        try:
            csv_content = sei_extractor.extract_sei_csv(mp4_path)
            if csv_content:
                with open(csv_path, "w") as f:
                    f.write(csv_content)
                video_data[timestamp]["data"] = f"{timestamp}-generated_sei.csv"
            else:
                print(f"Warning: No SEI data in {mp4_path}")
                settings.no_overlay = continue_without_telemetry_overlay(settings)
                break
        except Exception as e:
            print(f"Error generating CSV for {timestamp}: {e}")
    return video_data


def telemetry_csv_is_valid(csv_path: Path) -> bool:
    """Return True when a CSV contains the required telemetry columns."""
    try:
        df = pd.read_csv(csv_path, nrows=0)
    except Exception as e:
        print(f"ERROR reading telemetry csv for validation: {e}")
        return False

    return all(column in df.columns for column in REQUIRED_TELEMETRY_COLUMNS)


def telemetry_csv_matches_frame_count(csv_path: Path, total_frames: int) -> bool:
    """Return True when telemetry row count matches the video frame count."""
    try:
        telemetry_df = pd.read_csv(csv_path, usecols=[0])
    except Exception as e:
        print(f"ERROR reading telemetry csv for frame count validation: {e}")
        return False

    return len(telemetry_df) == total_frames


def get_missing_camera_groups(
    video_data: VideoData,
    layout: layouts.LayoutConfig,
) -> list[tuple[str, list[str]]]:
    """Return timestamps and camera keys missing from the selected layout."""
    required_cameras = layout["required_cameras"]
    invalid_timestamps = []

    for timestamp, files_info in video_data.items():
        missing_cameras = [
            camera_key
            for camera_key in required_cameras
            if not files_info.get(camera_key)
        ]

        if missing_cameras:
            invalid_timestamps.append((timestamp, missing_cameras))

    return invalid_timestamps


def validate_camera_data(
    video_data: VideoData,
    layout: layouts.LayoutConfig,
) -> None:
    """Exit if any clip group is missing cameras required by the selected layout."""
    if not video_data:
        sys.exit("No Tesla dashcam files found in the input directory.")

    invalid_timestamps = get_missing_camera_groups(video_data, layout)

    if invalid_timestamps:
        print("The following timestamps are missing required camera files:")
        for timestamp, missing_cameras in invalid_timestamps:
            missing = ", ".join(missing_cameras)
            print(f"- {timestamp}: {missing}")

        sys.exit("Processing aborted due to missing camera files.")


def get_invalid_telemetry_groups(
    video_data: VideoData,
    input_path: Path,
) -> list[tuple[str, str]]:
    """Return timestamps where telemetry CSV data is missing or invalid."""
    invalid_data_timestamps = []

    for timestamp, files_info in video_data.items():
        data_file = files_info.get("data")

        if data_file is None:
            invalid_data_timestamps.append((timestamp, "missing telemetry CSV"))
            continue

        csv_path = input_path / data_file

        if not telemetry_csv_is_valid(csv_path):
            invalid_data_timestamps.append(
                (timestamp, f"invalid telemetry CSV: {data_file}")
            )

    return invalid_data_timestamps


def validate_telemetry_data(
    settings: RenderSettings,
    video_data: VideoData,
    input_path: Path,
) -> None:
    """Validate telemetry files and prompt to continue without overlays if needed."""
    if settings.no_overlay:
        return

    invalid_data_timestamps = get_invalid_telemetry_groups(video_data, input_path)

    if invalid_data_timestamps:
        print("Telemetry data could not be used for the following timestamps:")
        for timestamp, reason in invalid_data_timestamps:
            print(f"- {timestamp}: {reason}")

        settings.no_overlay = continue_without_telemetry_overlay(settings)


def load_telemetry_data(
    input_path: Path,
    data_file: str,
    total_frames: int,
    settings: RenderSettings,
) -> pd.DataFrame | None:
    """Load telemetry CSV data and disable overlays if it cannot sync to video frames."""
    data_filepath = input_path / data_file

    try:
        telemetry_df = pd.read_csv(data_filepath)
    except Exception as e:
        print(f"Error loading telemetry data from {data_filepath}: {e}")
        settings.no_overlay = continue_without_telemetry_overlay(settings)
        return None

    if len(telemetry_df) != total_frames:
        print(f"Partial telemetry data found in: {data_filepath}")
        print(
            "This can be caused by the vehicle being in 'Park' for a portion of the video."
        )
        print("Unable to sync telemetry data to video frame.")
        settings.no_overlay = continue_without_telemetry_overlay(settings)
        return None

    print(f"Successfully loaded telemetry data from: {data_filepath}")
    return telemetry_df


def telemetry_user_input() -> bool:
    """Ask whether processing should continue without telemetry overlays."""
    while True:
        response = input(
            "Would you like to continue without the telemetry overlay? 'y' or 'n': "
        ).strip()
        if response == "n":
            sys.exit("Processing aborted due to missing telemetry data.")
        elif response == "y":
            return True
        else:
            print("Expected response 'y' or 'n'. Please try again.")


def continue_without_telemetry_overlay(settings: RenderSettings) -> bool:
    """Return whether processing should continue without telemetry overlays."""
    if settings.telemetry_prompt is not None:
        return settings.telemetry_prompt()
    return telemetry_user_input()


def remove_generated_csv(
    input_path: Path,
    video_data: VideoData,
    settings: RenderSettings,
) -> None:
    """Remove temporary SEI-generated CSV files unless the user chose to keep them."""
    if not settings.keep_csv:
        for timestamp, files_info in video_data.items():
            data_file = files_info.get("data")
            if data_file and data_file.endswith("-generated_sei.csv"):
                sei_csv_path = input_path / data_file
                if sei_csv_path.exists():
                    sei_csv_path.unlink()
                    print(f"Cleaned up temporary telemetry file: {sei_csv_path}")
