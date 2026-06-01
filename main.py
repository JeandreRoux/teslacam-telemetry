"""
Tesla Dashcam Telemetry Viewer

Processes Tesla dashcam MP4 files and accompanying CSV telemetry files to
produce a combined multi-camera video with real-time telemetry
overlay (speed, autopilot state, steering, brake/accelerator, blinkers).

Usage:
    python main.py -i <input_dir> -o <output_dir> [--no-overlay] [--mph] [--preview] [--keep-csv]
"""

import sys
from pathlib import Path
import argparse

# Import modules
from modules import data_handler
from modules import video_processor
from modules import layouts
from modules.settings import RenderSettings


def main():
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
        action="store_true",
    )
    args = parser.parse_args()

    settings = RenderSettings(
        no_overlay=args.no_overlay,
        mph=args.mph,
        preview=args.preview,
        keep_csv=args.keep_csv,
        layout=layouts.FOUR_CAMERA_DEFAULT,
    )

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_dir():
        sys.exit(f"Input path '{input_path}' is not a directory.")

    video_data = {}

    try:
        video_data = data_handler.compile_video_data(input_path, settings)
        data_handler.validate_camera_data(video_data, settings.layout)
        data_handler.validate_telemetry_data(settings, video_data, input_path)

        first_timestamp, fps = video_processor.get_video_fps(input_path, video_data)

        if settings.no_overlay:
            output_filename = f"TeslaCam_{first_timestamp}_no-overlay"
        else:
            output_filename = f"TeslaCam_{first_timestamp}"

        out, output_filepath = video_processor.create_video_writer(
            output_path=output_path,
            output_filename=output_filename,
            fps=fps,
        )

        try:
            for timestamp in sorted(video_data.keys()):
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

                    video_processor.process_video(
                        captures=captures,
                        telemetry_df=telemetry_df,
                        out=out,
                        settings=settings,
                    )
                finally:
                    video_processor.release_captures(captures)

            print(f"Finished all clips. Released final video file: {output_filepath}")
        finally:
            out.release()
            video_processor.close_preview_windows()
    finally:
        data_handler.remove_generated_csv(input_path, video_data, settings)


if __name__ == "__main__":
    main()
