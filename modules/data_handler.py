import re
import sys
import pandas as pd

# Import modules
from modules import sei_extractor

CAMERA_KEYS = ("front", "back", "left_repeater", "right_repeater")

DEFAULT_REQUIRED_CAMERAS = CAMERA_KEYS

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

def telemetry_csv_is_valid(csv_path):
    """Read CSV headers to verify valid telemetry file"""
    try:
        df = pd.read_csv(csv_path, nrows=0)
    except Exception as e:
        print(f"ERROR reading telemetry csv for validation: {e}")
        return False
    
    return all(column in df.columns for column in REQUIRED_TELEMETRY_COLUMNS)


def validate_camera_data(video_data, required_cameras=DEFAULT_REQUIRED_CAMERAS):
    if not video_data:
        sys.exit("No Tesla dashcam files found in the input directory.")

    invalid_timestamps = []

    for timestamp, files_info in video_data.items():
        missing_cameras = [
            camera_key
            for camera_key in required_cameras
            if not files_info.get(camera_key)
        ]

        if missing_cameras:
            invalid_timestamps.append((timestamp, missing_cameras))

    if invalid_timestamps:
        print("The following timestamps are missing required camera files:")
        for timestamp, missing_cameras in invalid_timestamps:
            missing = ", ".join(missing_cameras)
            print(f"- {timestamp}: {missing}")

        sys.exit("Processing aborted due to missing camera files.")


def compile_video_data(input_path, args):
    """Scan input directory and map timestamps to camera/telemetry filenames."""
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
                
    video_data = generate_sei_data(video_data, input_path, args)
    
    return video_data


def get_available_video_file(files_info):
    """Return the first available video filename in camera preference order."""
    for camera_key in CAMERA_KEYS:
        video_file = files_info.get(camera_key)
        if video_file:
            return video_file
        
    return None


def generate_sei_data(video_data, input_path, args):
    """Generate SEI Data from mp4 dashcam file using Tesla's sei_extractor.py"""
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
                args.no_overlay = telemetry_user_input()
        except Exception as e:
            print(f"Error generating CSV for {timestamp}: {e}")
    return video_data


def validate_telemetry_data(args, video_data, input_path):
    if args.no_overlay:
        return

    invalid_data_timestamps = []

    for timestamp, files_info in video_data.items():
        data_file = files_info.get("data")

        if data_file is None:
            invalid_data_timestamps.append((timestamp, "missing telemetry CSV"))
            continue

        csv_path = input_path / data_file

        if not telemetry_csv_is_valid(csv_path):
            invalid_data_timestamps.append((timestamp, f"invalid telemetry CSV: {data_file}"))

    if invalid_data_timestamps:
        print("Telemetry data could not be used for the following timestamps:")
        for timestamp, reason in invalid_data_timestamps:
            print(f"- {timestamp}: {reason}")
        
        args.no_overlay = telemetry_user_input()


def remove_generated_csv(input_path, video_data, args):
        # --- Cleanup auto-generated SEI files ---
    if not args.keep_csv:
        for timestamp, files_info in video_data.items():
            data_file = files_info.get("data")
            if data_file and data_file.endswith("-generated_sei.csv"):
                sei_csv_path = input_path / data_file
                if sei_csv_path.exists():
                    sei_csv_path.unlink()
                    print(f"Cleaned up temporary telemetry file: {sei_csv_path}")
                    
                    
def telemetry_user_input():
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