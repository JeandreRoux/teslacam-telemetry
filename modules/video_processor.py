import cv2 as cv
import numpy as np
import sys

# Import modules
from modules import config
from modules import overlay_renderer
from modules import data_handler


def process_video(
    cap_front, cap_back, cap_left_repeater, cap_right_repeater, telemetry_df, out, args, input_path, video_data
):
    """Compose frames from camera captures, optionally draw telemetry overlay, and write output."""
    canvas_width = config.CANVAS_WIDTH
    canvas_height = config.CANVAS_HEIGHT

    if not cap_front.isOpened() or not cap_back.isOpened():
        print("Cannot open file")

    frame_index = 0

    while True:
        ret_front, frame_front = cap_front.read()
        ret_back, frame_back = cap_back.read()
        ret_left_repeater, frame_left_repeater = cap_left_repeater.read()
        ret_right_repeater, frame_right_repeater = cap_right_repeater.read()
        if (
            not ret_front
            or not ret_back
            or not ret_left_repeater
            or not ret_right_repeater
        ):
            break

        # Get current frame index
        curr_frame = int(cap_front.get(cv.CAP_PROP_POS_FRAMES))

        # Create canvas
        canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)

        # Resize videos
        frame_front_resized = cv.resize(
            frame_front, (728, 546), interpolation=cv.INTER_LANCZOS4
        )
        frame_back_resized = cv.resize(
            frame_back, (232, 174), interpolation=cv.INTER_LANCZOS4
        )
        frame_left_repeater_resized = cv.resize(
            frame_left_repeater, (232, 174), interpolation=cv.INTER_LANCZOS4
        )
        frame_right_repeater_resized = cv.resize(
            frame_right_repeater, (232, 174), interpolation=cv.INTER_LANCZOS4
        )

        # Position videos
        canvas[0:546, 276:1004] = frame_front_resized
        canvas[546:720, 524:756] = frame_back_resized
        canvas[546:720, 276:508] = frame_left_repeater_resized
        canvas[546:720, 772:1004] = frame_right_repeater_resized

        # Write text overlay
        if not args.no_overlay:
            canvas = overlay_renderer.draw_overlay(canvas, curr_frame, telemetry_df, frame_index, args)

        frame_index += 1

        if args.preview:
            cv.imshow("Preview", canvas)  # Shows the video in a window
            if cv.waitKey(1) & 0xFF == ord("q"):  # Lets you quit by pressing 'q'
                if cap_front:
                    cap_front.release()
                if cap_back:
                    cap_back.release()
                if cap_left_repeater:
                    cap_left_repeater.release()
                if cap_right_repeater:
                    cap_right_repeater.release()
                out.release()
                cv.destroyAllWindows()
                data_handler.remove_generated_csv(input_path, video_data, args)
                sys.exit("User stopped program.")

        # write frame
        out.write(canvas)