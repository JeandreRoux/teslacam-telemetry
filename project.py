import cv2 as cv
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import re
import sys
from pathlib import Path
import pandas as pd


OVERLAY_BG_COLOR = (0, 0, 0, 200)
CIRCLE_BG_COLOR = (53, 53, 53, 220)
FONT_WHITE = (255, 255, 255)
FONT_BLUE = (19, 121, 227)
FONT_SPEED = ImageFont.truetype("arial.ttf", 30)
FONT_SPEED_UNIT = ImageFont.truetype("arialbd.ttf", 14)
FONT_AUTOPILOT = ImageFont.truetype("arialbd.ttf", 14)
FONT_GEAR = ImageFont.truetype("arialbd.ttf", 16)
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720


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
    output_filepath = "./output/output.mp4"
    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    out = cv.VideoWriter(output_filepath, fourcc, fps, (canvas_width, canvas_height), isColor=True)
        
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
            cap_left_repeater = cv.VideoCapture(f"{input_path}/{tesla_cam[timestamp]['left_repeater']}")
        if tesla_cam[timestamp]["right_repeater"]:
            cap_right_repeater = cv.VideoCapture(f"{input_path}/{tesla_cam[timestamp]['right_repeater']}")
            
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
        out=out
        )
        
        # Release the input video captures for this timestamp
        if cap_front: cap_front.release()
        if cap_back: cap_back.release()
    
    
    print(f"Finished all clips. Releasing final video file: {output_filepath}")
    out.release()
    cv.destroyAllWindows()
    
        ## Release capture of all clips: if cap_front: cap_front.release()
    
    
def process_video(cap_front, cap_back, cap_left_repeater, cap_right_repeater, telemetry_df, out):
    canvas_width = CANVAS_WIDTH
    canvas_height = CANVAS_HEIGHT
    
    if not cap_front.isOpened() or not cap_back.isOpened():
        print("Cannot open file")
        
    frame_index = 0
    
    while True:
        ret1, frame1 = cap_front.read()
        ret2, frame2 = cap_back.read()
        if not ret1 or not ret2:
            print("Can't receive frame (stream end?). Exiting ...")
            break
        
        # Get current frame index
        curr_frame = int(cap_front.get(cv.CAP_PROP_POS_FRAMES))
        
        # Create canvas
        canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
        
        # Resize videos
        frame1_resized = cv.resize(frame1, (728, 546), interpolation=cv.INTER_LANCZOS4)
        frame2_resized = cv.resize(frame2, (232, 174), interpolation=cv.INTER_LANCZOS4)
        
        # Position videos
        canvas[0:546, 276:1004] = frame1_resized
        canvas[546:720, 524:756] = frame2_resized
        
        # Write text overlay
        canvas = draw_overlay(canvas, curr_frame, telemetry_df, frame_index)
        
        frame_index += 1
        
        cv.imshow("Rendering Preview", canvas) # Shows the video in a window
        if cv.waitKey(1) & 0xFF == ord('q'):    # Lets you quit by pressing 'q'
            cap_front.release()
            cap_back.release()
            out.release()
            cv.destroyAllWindows()
            sys.exit("User stopped program.")
        
        # write frame
        out.write(canvas)
    
    
def compile_tesla_cam(input_path):
    pattern = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2})-([a-z_]+)\.(mp4|csv)")
    
    ## Create Dict for files -> Move to function
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
    
    
def draw_overlay(canvas, f:int, telemetry_df, frame_index):
    # 1. Background
    x, y, w, h = 552, 22, 175, 70
    
    # CROP
    roi = canvas[y:y+h, x:x+w]
    
    # CONVERT
    roi_pil = Image.fromarray(cv.cvtColor(roi, cv.COLOR_BGR2RGB)).convert("RGBA")
    
    # Center point
    rec_center_x = w // 2
    rec_center_y = h // 2
    
    overlay = Image.new("RGBA", roi_pil.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Draw Background
    draw.rounded_rectangle(
        [(0, 0), (w, h)],
        radius=10,
        fill=OVERLAY_BG_COLOR
    )
    
    # Draw Gear Background
    draw.ellipse(
        (10, 10, 30, 30),
        fill=CIRCLE_BG_COLOR
    )
    
    # Draw Steering Background
    draw.ellipse(
        (145, 10, 165, 30),
        fill=CIRCLE_BG_COLOR
    )
    
    # Draw Brake Background
    draw.ellipse(
        (10, 40, 30, 60),
        fill=CIRCLE_BG_COLOR
    )
    
    # Draw Accelerator Background
    draw.ellipse(
        (145, 40, 165, 60),
        fill=CIRCLE_BG_COLOR
    )
    
    # Merge layers
    roi_pil = Image.alpha_composite(roi_pil, overlay).convert("RGB")
    draw = ImageDraw.Draw(roi_pil)
    
    # Read current frame data
    current_frame_data = telemetry_df.iloc[frame_index]
    
    # 2. Speed
    speed, speed_unit = get_speed(f, current_frame_data)
    speed_x = get_text_x(speed, FONT_SPEED, draw, rec_center_x)
    speed_y = rec_center_y - 32
    
    # Draw Speed
    draw.text((speed_x, speed_y), speed, font=FONT_SPEED, fill=FONT_WHITE)
    
    # Speed Unit
    speed_unit_x = get_text_x(speed_unit, FONT_SPEED_UNIT, draw, rec_center_x)
    speed_unit_y = rec_center_y + 2
    
    # Draw Speed Unit
    draw.text((speed_unit_x, speed_unit_y), speed_unit, font=FONT_SPEED_UNIT, fill=FONT_WHITE)
    
    # 3. Autopilot State
    autopilot_state = get_autopilot_state(f, current_frame_data)
    autopilot_state_x = get_text_x(autopilot_state, FONT_AUTOPILOT, draw, rec_center_x)
    autopilot_state_y = rec_center_y + 17
    
    # Draw Autopilot State
    draw.text((autopilot_state_x, autopilot_state_y), autopilot_state, font=FONT_AUTOPILOT, fill=FONT_BLUE)
    
    # 4. Gear State
    gear_state = get_gear_state(f, current_frame_data)
    gear_state_x = get_text_x(gear_state, FONT_GEAR, draw, 20) + 1
    gear_state_y = get_text_y(gear_state, FONT_GEAR, draw, 20) + 1
    
    # Draw Gear State
    draw.text((gear_state_x, gear_state_y), gear_state, font=FONT_GEAR, fill=FONT_BLUE)
    
    
    # CONVERT BACK
    final_roi = cv.cvtColor(np.array(roi_pil.convert("RGB")), cv.COLOR_RGB2BGR)
    
    canvas[y:y+h, x:x+w] = final_roi
    
    return canvas


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
            return "Cruise Control"
        case "AUTOSTEER":
            return "Autopilot"
        case "SELF_DRIVING":
            return "Self Driving"
        case _:
            return ""
    

def get_speed(f, current_frame_data) -> int:
    speed_mps = float(current_frame_data['vehicle_speed_mps'])
    speed_kph = speed_mps * 3.6
    speed_unit = "km/h"
    
    return f"{speed_kph:.0f}", speed_unit
    
    
if __name__ == "__main__":
    main()