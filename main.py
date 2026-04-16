"""
Tesla Dashcam Telemetry Viewer

Processes Tesla dashcam MP4 files and accompanying CSV telemetry files to
produce a combined multi-camera video with real-time telemetry
overlay (speed, autopilot state, steering, brake/accelerator, blinkers).

Usage:
    python project.py -i <input_dir> -o <output_dir> [--no-overlay] [--mph] [--preview]
"""

import cv2 as cv
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import re
import sys
from pathlib import Path
import pandas as pd
import math
import argparse

# Import modules
from modules import config
from modules import get_state
from modules import overlay_renderer
from modules import data_handler
from modules import video_processor
from modules import sei_extractor


def main():
    """Parse CLI arguments, discover clip groups, and orchestrate processing."""
    parser = argparse.ArgumentParser(
        prog="Tesla Dashcam Telemetry Viewer",
        description="Processes Tesla dashcam footage and telemetry data to create a multi-camera overlay video with real-time vehicle telemetry information including speed, autopilot state, steering angle, and pedal positions.",
        allow_abbrev=False,
    )

    parser.add_argument("-i", "--input", help="input directory", required=True)
    parser.add_argument("-o", "--output", help="output directory", required=True)
    parser.add_argument(
        "--no-overlay",
        help="disables the telemetry overlay (enabled by default)",
        action="store_true",
    )
    parser.add_argument(
        "--mph", help="sets speed units to MPH (default is KM/H)", action="store_true"
    )
    parser.add_argument(
        "--preview",
        help="enabled render preview while videos are being processed",
        action="store_true",
    )
    parser.add_argument(
        "--keep-csv",
        help="keep generated telemetry csv in input directory",
        action="store_true"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_dir():
        sys.exit(f"Input path '{input_path}' is not a directory.")

    video_data = data_handler.compile_video_data(input_path, args)

    # --- Initialize the VideoWriter ---
    # Get video properties
    first_timestamp = sorted(video_data.keys())[0]
    temp_video_path = f"{input_path}/{video_data[first_timestamp]['front']}"

    if args.no_overlay:
        output_filename = f"TeslaCam_{first_timestamp}_no-overlay"
    else:
        output_filename = f"TeslaCam_{first_timestamp}"

    cap_temp = cv.VideoCapture(temp_video_path)
    if not cap_temp.isOpened():
        sys.exit(f"FATAL: Could not open {temp_video_path} to get video properties.")

    canvas_width = config.CANVAS_WIDTH
    canvas_height = config.CANVAS_HEIGHT
    fps = cap_temp.get(cv.CAP_PROP_FPS)
    total_frames = int(cap_temp.get(cv.CAP_PROP_FRAME_COUNT))
    cap_temp.release()

    # Define output file codec and create the VideoWriter object
    output_filepath = f"{output_path}/{output_filename}.mp4"
    fourcc = cv.VideoWriter_fourcc(*"mp4v")
    out = cv.VideoWriter(
        output_filepath, fourcc, fps, (canvas_width, canvas_height), isColor=True
    )

    for timestamp in sorted(video_data.keys()):
        cap_front = None
        cap_back = None
        cap_left_repeater = None
        cap_right_repeater = None
        telemetry_df = None

        if video_data[timestamp]["front"]:
            cap_front = cv.VideoCapture(f"{input_path}/{video_data[timestamp]['front']}")
            total_frames = int(cap_front.get(cv.CAP_PROP_FRAME_COUNT))
        if video_data[timestamp]["back"]:
            cap_back = cv.VideoCapture(f"{input_path}/{video_data[timestamp]['back']}")
        if video_data[timestamp]["left_repeater"]:
            cap_left_repeater = cv.VideoCapture(
                f"{input_path}/{video_data[timestamp]['left_repeater']}"
            )
        if video_data[timestamp]["right_repeater"]:
            cap_right_repeater = cv.VideoCapture(
                f"{input_path}/{video_data[timestamp]['right_repeater']}"
            )

        if video_data[timestamp]["data"]:
            data_filepath = f"{input_path}/{video_data[timestamp]['data']}"
            try:
                telemetry_df = pd.read_csv(data_filepath)
                if len(telemetry_df) != total_frames:
                    print(f"Partial telemetry data found in: {data_filepath}")
                    print(
                        "This can be caused by the vehicle being in 'Park' for a protion of the video."
                    )
                    print("Unable to sync telemetry data to video frame.")
                    args.no_overlay = data_handler.telemetry_user_input()
                else:
                    print(f"Successfully loaded telemetry data from: {data_filepath}")
            except Exception as e:
                print(f"Error loading telemetry data from {data_filepath}: {e}")
                telemetry_df = None
                args.no_overlay = data_handler.telemetry_user_input()

        if args.preview:
            print("Loading preview... press 'q' to quit.")
            print("Processing videos...")
        else:
            print("Processing videos...")

        video_processor.process_video(
            cap_front=cap_front,
            cap_back=cap_back,
            cap_left_repeater=cap_left_repeater,
            cap_right_repeater=cap_right_repeater,
            telemetry_df=telemetry_df,
            out=out,
            args=args,
            input_path=input_path,
            video_data=video_data
        )

        # Release the input video captures for this timestamp
        if cap_front:
            cap_front.release()
        if cap_back:
            cap_back.release()
        if cap_left_repeater:
            cap_left_repeater.release()
        if cap_right_repeater:
            cap_right_repeater.release()

    print(f"Finished all clips. Releasing final video file: {output_filepath}")
    
    data_handler.remove_generated_csv(input_path, video_data, args)
    
    out.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()
