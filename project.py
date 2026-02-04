import cv2 as cv
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import re
import sys
from pathlib import Path
import pandas as pd
import math

OVERLAY_BG_COLOR = (0, 0, 0, 220)
CIRCLE_BG_COLOR = (50, 50, 50, 245)
FONT_WHITE = (255, 255, 255)
FONT_BLUE = (19, 121, 227)
FONT_SPEED = ImageFont.truetype("arial.ttf", 32)
FONT_SPEED_UNIT = ImageFont.truetype("arialbd.ttf", 14)
FONT_AUTOPILOT = ImageFont.truetype("arialbd.ttf", 14)
FONT_GEAR = ImageFont.truetype("arialbd.ttf", 16)
BLINKER_OFF = (0, 102, 41, 220)
BLINKER_ON = (0, 194, 78, 250)
PEDAL_ACTIVE = (255, 255, 255, 250)
PEDAL_INACTIVE = (140, 140, 140, 250)
PEDAL_ACTIVE_CIRCLE = (170, 170, 170, 250)
BLINKER_INTERVAL = 22
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720


blinker_state = {
    "left": {"state": False, "frame": None},
    "right": {"state": False, "frame": None},
}


def main():

    input_path = Path("./sample/")

    if not input_path.is_dir():
        sys.exit(f"Input path '{input_path}' is not a directory.")

    tesla_cam = compile_tesla_cam(input_path)

    missing_data_timestamps = []
    for timestamp, files_info in tesla_cam.items():
        if files_info.get("data") == None:
            missing_data_timestamps.append(timestamp)
    if missing_data_timestamps:
        print("Error: The following timestamps are missing a data file:")
        for ts in missing_data_timestamps:
            print(f"- {ts}")
        sys.exit("Processing aborted due to missing data files.")

    # --- Initialize the VideoWriter ---
    # Get video properties
    first_timestamp = sorted(tesla_cam.keys())[0]
    temp_video_path = f"{input_path}/{tesla_cam[first_timestamp]['front']}"

    cap_temp = cv.VideoCapture(temp_video_path)
    if not cap_temp.isOpened():
        sys.exit(f"FATAL: Could not open {temp_video_path} to get video properties.")

    canvas_width = CANVAS_WIDTH
    canvas_height = CANVAS_HEIGHT
    fps = cap_temp.get(cv.CAP_PROP_FPS)
    cap_temp.release()

    # Define output file codec and create the VideoWriter object
    output_filepath = f"./output/TeslaCam_{first_timestamp}.mp4"
    fourcc = cv.VideoWriter_fourcc(*"mp4v")
    out = cv.VideoWriter(
        output_filepath, fourcc, fps, (canvas_width, canvas_height), isColor=True
    )

    for timestamp in sorted(tesla_cam.keys()):
        cap_front = None
        cap_back = None
        cap_left_repeater = None
        cap_right_repeater = None
        telemetry_df = None

        if tesla_cam[timestamp]["front"]:
            cap_front = cv.VideoCapture(f"{input_path}/{tesla_cam[timestamp]['front']}")
        if tesla_cam[timestamp]["back"]:
            cap_back = cv.VideoCapture(f"{input_path}/{tesla_cam[timestamp]['back']}")
        if tesla_cam[timestamp]["left_repeater"]:
            cap_left_repeater = cv.VideoCapture(
                f"{input_path}/{tesla_cam[timestamp]['left_repeater']}"
            )
        if tesla_cam[timestamp]["right_repeater"]:
            cap_right_repeater = cv.VideoCapture(
                f"{input_path}/{tesla_cam[timestamp]['right_repeater']}"
            )

        if tesla_cam[timestamp]["data"]:
            data_filepath = f"{input_path}/{tesla_cam[timestamp]['data']}"
            try:
                telemetry_df = pd.read_csv(data_filepath)
                print(f"Successfully loaded telemetry data from: {data_filepath}")
            except Exception as e:
                print(f"Error loading telemetry data from {data_filepath}: {e}")
                telemetry_df = None
        else:
            print(f"No telemetry data file found for timestamp: {timestamp}")

        process_video(
            cap_front=cap_front,
            cap_back=cap_back,
            cap_left_repeater=cap_left_repeater,
            cap_right_repeater=cap_right_repeater,
            telemetry_df=telemetry_df,
            out=out,
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
    out.release()
    cv.destroyAllWindows()

    ## Release capture of all clips: if cap_front: cap_front.release()


def process_video(
    cap_front, cap_back, cap_left_repeater, cap_right_repeater, telemetry_df, out
):
    canvas_width = CANVAS_WIDTH
    canvas_height = CANVAS_HEIGHT

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
            print("Can't receive frame (stream end?). Exiting ...")
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
        canvas = draw_overlay(canvas, curr_frame, telemetry_df, frame_index)

        frame_index += 1

        cv.imshow("Rendering Preview", canvas)  # Shows the video in a window
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
            sys.exit("User stopped program.")

        # write frame
        out.write(canvas)


def compile_tesla_cam(input_path):
    pattern = re.compile(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})-([a-z_]+)\.(mp4|csv)"
    )

    tesla_cam = {}

    for item in input_path.iterdir():
        if not item.is_file():
            continue

        match = pattern.search(item.name)

        if match:
            timestamp = match.group(1)
            file_id = match.group(2)
            extension = match.group(3)

            tesla_cam.setdefault(timestamp, {})
            tesla_cam[timestamp].setdefault("data", None)

            if extension == "csv":
                tesla_cam[timestamp]["data"] = item.name
            else:
                tesla_cam[timestamp][file_id] = item.name
    return tesla_cam


def draw_overlay(canvas, f, telemetry_df, frame_index):
    # Read current frame data
    current_frame_data = telemetry_df.iloc[frame_index]

    # 1. Background
    x, y, w, h = 552, 22, 175, 70

    # CROP
    roi = canvas[y : y + h, x : x + w]

    # CONVERT
    roi_pil = Image.fromarray(cv.cvtColor(roi, cv.COLOR_BGR2RGB)).convert("RGBA")

    # Center point
    rec_center_x = w // 2
    rec_center_y = h // 2

    overlay = Image.new("RGBA", roi_pil.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw Background
    draw.rounded_rectangle([(0, 0), (w, h)], radius=10, fill=OVERLAY_BG_COLOR)

    # Draw Gear Background
    draw.ellipse((10, 10, 30, 30), fill=CIRCLE_BG_COLOR)

    # Draw Steering Background
    draw.ellipse((145, 10, 165, 30), fill=CIRCLE_BG_COLOR)

    # Draw Brake Background
    draw.ellipse((10, 40, 30, 60), fill=CIRCLE_BG_COLOR)

    # Draw Accelerator Background
    draw.ellipse((145, 40, 165, 60), fill=CIRCLE_BG_COLOR)

    # Draw Blinkers
    global blinker_state
    left_blinker = current_frame_data["blinker_on_left"]
    right_blinker = current_frame_data["blinker_on_right"]

    left_blinker_fill = BLINKER_OFF
    right_blinker_fill = BLINKER_OFF

    # Right Blinker
    if right_blinker != blinker_state["right"]["state"]:
        blinker_state["right"]["state"] = right_blinker
        blinker_state["right"]["frame"] = int(f)

    if blinker_state["right"]["state"]:
        if f < blinker_state["right"]["frame"] + BLINKER_INTERVAL:
            right_blinker_fill = BLINKER_ON
        if f == blinker_state["right"]["frame"] + BLINKER_INTERVAL:
            right_blinker_fill = BLINKER_OFF
        if f == blinker_state["right"]["frame"] + (BLINKER_INTERVAL + 18):
            right_blinker_fill = BLINKER_ON
            blinker_state["right"]["frame"] = int(f)

    # Left Blinker
    if left_blinker != blinker_state["left"]["state"]:
        blinker_state["left"]["state"] = left_blinker
        blinker_state["left"]["frame"] = int(f)

    if blinker_state["left"]["state"]:
        if f < blinker_state["left"]["frame"] + BLINKER_INTERVAL:
            left_blinker_fill = BLINKER_ON
        if f == blinker_state["left"]["frame"] + BLINKER_INTERVAL:
            left_blinker_fill = BLINKER_OFF
        if f == blinker_state["left"]["frame"] + (BLINKER_INTERVAL + 18):
            left_blinker_fill = BLINKER_ON
            blinker_state["left"]["frame"] = int(f)

    # Draw blinkers
    draw_left_blinker(left_blinker_fill, draw)
    draw_right_blinker(right_blinker_fill, draw)

    # Draw accelerator pedal
    accelerator_pedal = draw_accelerator_pedal(f, current_frame_data)
    overlay.paste(accelerator_pedal, (145, 40), mask=accelerator_pedal)

    # Draw brake pedal

    brake_pedal = draw_brake_pedal(f, current_frame_data)
    overlay.paste(brake_pedal, (10, 40), mask=brake_pedal)

    # Steering Wheel
    steering_wheel = draw_steering_wheel(f, current_frame_data)
    overlay.paste(steering_wheel, (148, 13), mask=steering_wheel)

    # Merge layers
    roi_pil = Image.alpha_composite(roi_pil, overlay).convert("RGB")
    draw = ImageDraw.Draw(roi_pil)

    # 2. Speed
    speed, speed_unit = get_speed(f, current_frame_data)
    speed_x = get_text_x(speed, FONT_SPEED, draw, rec_center_x)
    speed_y = rec_center_y - 33

    # Draw Speed
    draw.text((speed_x, speed_y), speed, font=FONT_SPEED, fill=FONT_WHITE)

    # Speed Unit
    speed_unit_x = get_text_x(speed_unit, FONT_SPEED_UNIT, draw, rec_center_x)
    speed_unit_y = rec_center_y + 1

    # Draw Speed Unit
    draw.text(
        (speed_unit_x, speed_unit_y), speed_unit, font=FONT_SPEED_UNIT, fill=FONT_WHITE
    )

    # 3. Autopilot State
    autopilot_state = get_autopilot_state(f, current_frame_data)
    autopilot_state_x = get_text_x(autopilot_state, FONT_AUTOPILOT, draw, rec_center_x)
    autopilot_state_y = rec_center_y + 17

    # Draw Autopilot State
    draw.text(
        (autopilot_state_x, autopilot_state_y),
        autopilot_state,
        font=FONT_AUTOPILOT,
        fill=FONT_BLUE,
    )

    # 4. Gear State
    gear_state = get_gear_state(f, current_frame_data)
    gear_state_x = get_text_x(gear_state, FONT_GEAR, draw, 20) + 1
    gear_state_y = get_text_y(gear_state, FONT_GEAR, draw, 20) + 1

    # Draw Gear State
    draw.text((gear_state_x, gear_state_y), gear_state, font=FONT_GEAR, fill=FONT_WHITE)

    # CONVERT BACK
    final_roi = cv.cvtColor(np.array(roi_pil.convert("RGB")), cv.COLOR_RGB2BGR)

    canvas[y : y + h, x : x + w] = final_roi

    return canvas


def draw_accelerator_pedal(f, current_frame_data, width=300, height=300):
    accelerator_pedal_position = current_frame_data["accelerator_pedal_position"]

    if accelerator_pedal_position > 0:
        color = PEDAL_ACTIVE
    else:
        color = PEDAL_INACTIVE

    acc_start_angle, acc_end_angle = calculate_fill_angles(accelerator_pedal_position)

    # Create canvas
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pedal_width = 100
    pedal_height = 225

    pedal_x = (width // 2) - (pedal_width // 2)
    pedal_y = (height // 2) - (pedal_height // 2)

    # Draw accelerator position
    draw.chord(
        (0, 0, 300, 300),
        start=acc_start_angle,
        end=acc_end_angle,
        fill=PEDAL_ACTIVE_CIRCLE,
    )

    # Draw the main pedal body
    shape = [pedal_x, pedal_y, pedal_x + pedal_width, pedal_y + pedal_height]
    draw.rounded_rectangle(shape, radius=12, fill=color)

    num_lines = 4
    for i in range(1, num_lines + 1):
        y = (pedal_height // (num_lines + 1)) * i + 35
        draw.line(
            [pedal_x + 15, y, pedal_x + pedal_width - 15, y], fill="black", width=10
        )

    img = img.resize((20, 20), Image.LANCZOS)

    return img


def draw_brake_pedal(f, current_frame_data, width=300, height=300):
    brake_pedal_state = current_frame_data["brake_applied"]

    if brake_pedal_state:
        color = PEDAL_ACTIVE
    else:
        color = PEDAL_INACTIVE

    # Create canvas
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pedal_width = 190
    pedal_height = 130

    pedal_x = (width // 2) - (pedal_width // 2)
    pedal_y = (height // 2) - (pedal_height // 2)

    if brake_pedal_state:
        draw.ellipse((0, 0, 300, 300), fill=PEDAL_ACTIVE_CIRCLE)

    # Draw the main pedal body
    shape = [pedal_x, pedal_y, pedal_x + pedal_width, pedal_y + pedal_height]
    draw.rounded_rectangle(shape, radius=10, fill=color)

    # Add "grip" lines
    for i in range(1, 4):
        x = (pedal_width // 4) * i + 55
        draw.line(
            [x, pedal_y + 15, x, pedal_y + pedal_height - 15], fill="black", width=10
        )

    img = img.resize((20, 20), Image.LANCZOS)

    return img


def draw_steering_wheel(f, current_frame_data, size=200):
    steering_angle = int(current_frame_data["steering_wheel_angle"])

    match current_frame_data["autopilot_state"]:
        case "AUTOSTEER":
            color = FONT_BLUE
        case "SELF_DRIVING":
            color = FONT_BLUE
        case _:
            color = FONT_WHITE

    # Create a new transparent canvas
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Define dimentions based on size
    center = size // 2
    rim_thickness = size // 10
    hub_size = size // 4

    # 1. Draw outer rim
    draw.ellipse([0, 0, size, size], outline=color, width=rim_thickness)

    # 2. Draw the horizontal spoke
    # (Left, Top, Right, Bottom)
    spoke_height = rim_thickness
    draw.rectangle(
        [
            rim_thickness,
            center - spoke_height // 2,
            size - rim_thickness,
            center + spoke_height // 2,
        ],
        fill=color,
    )

    # 3. Draw vertical spoke
    draw.rectangle([center - 15, center, center + 15, size - rim_thickness], fill=color)

    # 4. Draw center hub
    draw.ellipse(
        [
            center - hub_size // 2,
            center - hub_size // 2,
            center + hub_size // 2,
            center + hub_size // 2,
        ],
        fill=color,
    )

    img = img.rotate(-steering_angle, resample=Image.BICUBIC)

    img = img.resize((15, 15), Image.LANCZOS)

    return img


def calculate_fill_angles(accelerator_pedal_position):
    """
    Calculates start and end angles for a bottom-top fill of the accelerator circle
    percent: 0.0 to 1.0
    """
    fill_pct = int(accelerator_pedal_position) / 100

    # Calculate the vertical distance from the center (radius = 1)
    # Height goes from 0 to 2, so center is at 1
    height = fill_pct * 2
    distance_from_center = 1 - height

    # Calculate angle from vertical center line in radians
    phi = math.acos(distance_from_center)

    # Convert to degrees
    phi_deg = int(math.degrees(phi))

    # In Pillow, 90 is the bottom. So +/- phi_deg from 90
    return 90 - phi_deg, 90 + phi_deg


def draw_left_blinker(blinker_fill, draw):
    shape = [
        (40, 35),  # Tip
        (50, 25),
        (50, 30),
        (60, 30),  # Top half
        (60, 40),
        (50, 40),
        (50, 45),  # Bottom half
    ]

    draw.polygon(shape, fill=blinker_fill)


def draw_right_blinker(blinker_fill, draw):
    shape = [
        (115, 30),
        (125, 30),
        (125, 25),  # Top half
        (135, 35),  # Tip
        (125, 45),
        (125, 40),
        (115, 40),  # Bottom half
    ]

    draw.polygon(shape, fill=blinker_fill)


def get_text_x(text, font, draw, shape_center):
    # bbox = (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font)
    text_width = bbox[2] - bbox[0]
    return shape_center - (text_width // 2) - bbox[0]


def get_text_y(text, font, draw, shape_center):
    # bbox = (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font)
    text_height = bbox[3] - bbox[1]
    return shape_center - (text_height // 2) - bbox[1]


def get_gear_state(f, current_frame_data) -> str:
    match current_frame_data["gear_state"]:
        case "GEAR_PARK":
            return "P"
        case "GEAR_DRIVE":
            return "D"
        case "GEAR_REVERSE":
            return "R"
        case "GEAR_NEUTRAL":
            return "N"
        case _:
            return ""


def get_autopilot_state(f, current_frame_data) -> str:
    match current_frame_data["autopilot_state"]:
        case "TACC":
            return "Cruise"
        case "AUTOSTEER":
            return "Autopilot"
        case "SELF_DRIVING":
            return "Self Driving"
        case _:
            return ""


def get_speed(f, current_frame_data) -> int:
    speed_mps = float(current_frame_data["vehicle_speed_mps"])
    speed_kph = speed_mps * 3.6
    speed_unit = "km/h"

    if speed_kph < 0:
        speed = f"{speed_kph*speed_kph:.0f}"
    else:
        speed = f"{speed_kph:.0f}"

    return speed, speed_unit


if __name__ == "__main__":
    main()
