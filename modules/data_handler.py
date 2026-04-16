import re
import sys

# Import modules
from modules import sei_extractor

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
                print(f"Found telemetry CSV: {video_data[timestamp]["data"]}")
            else:
                video_data[timestamp][file_id] = item.name
                
    video_data = generate_sei_data(video_data, input_path, args)
    
    return video_data


def generate_sei_data(video_data, input_path, args):
    """Generate SEI Data from mp4 dashcam file using Tesla's sei_extractor.py"""
    # Auto-generate missing CSV from SEI data
    for timestamp, files_info in video_data.items():
        if files_info.get("data") is None and files_info.get("front"):
            mp4_path = f"{input_path}/{files_info['front']}"
            csv_path = f"{input_path}/{timestamp}-generated_sei.csv"
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


def missing_data(args, video_data):
    if not args.no_overlay:
        missing_data_timestamps = []
        for timestamp, files_info in video_data.items():
            if files_info.get("data") is None:
                missing_data_timestamps.append(timestamp)
        if missing_data_timestamps:
            print("Error: The following timestamps are missing a data file:")
            for ts in missing_data_timestamps:
                print(f"- {ts}")
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