from PIL import Image, ImageDraw
import cv2 as cv
import numpy as np

# Import modules
from modules import config
from modules import shapes
from modules import get_state
from modules.settings import RenderSettings

blinker_state = {
    "left": {"state": False, "frame": 0},
    "right": {"state": False, "frame": 0},
}


def reset_blinker_state() -> None:
    """Reset blinker timing state at render/clip boundaries."""
    for blinker in blinker_state.values():
        blinker["state"] = False
        blinker["frame"] = 0


def draw_overlay(canvas, f, telemetry_df, frame_index, settings: RenderSettings):
    """Draw speed, gear, autopilot, blinker, steering, and pedal state onto the canvas."""
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
    draw.rounded_rectangle([(0, 0), (w, h)], radius=10, fill=config.OVERLAY_BG_COLOR)

    # Draw Gear Background
    draw.ellipse((10, 10, 30, 30), fill=config.CIRCLE_BG_COLOR)

    # Draw Steering Background
    draw.ellipse((145, 10, 165, 30), fill=config.CIRCLE_BG_COLOR)

    # Draw Brake Background
    draw.ellipse((10, 40, 30, 60), fill=config.CIRCLE_BG_COLOR)

    # Draw Accelerator Background
    draw.ellipse((145, 40, 165, 60), fill=config.CIRCLE_BG_COLOR)

    # Draw Blinkers
    left_blinker = current_frame_data["blinker_on_left"]
    right_blinker = current_frame_data["blinker_on_right"]

    left_blinker_fill = config.BLINKER_OFF
    right_blinker_fill = config.BLINKER_OFF

    # Right Blinker
    if right_blinker != blinker_state["right"]["state"]:
        blinker_state["right"]["state"] = right_blinker
        blinker_state["right"]["frame"] = int(f)

    if blinker_state["right"]["state"]:
        if f < blinker_state["right"]["frame"] + config.BLINKER_INTERVAL:
            right_blinker_fill = config.BLINKER_ON
        if f == blinker_state["right"]["frame"] + config.BLINKER_INTERVAL:
            right_blinker_fill = config.BLINKER_OFF
        if f == blinker_state["right"]["frame"] + (config.BLINKER_INTERVAL + 18):
            right_blinker_fill = config.BLINKER_ON
            blinker_state["right"]["frame"] = int(f)

    # Left Blinker
    if left_blinker != blinker_state["left"]["state"]:
        blinker_state["left"]["state"] = left_blinker
        blinker_state["left"]["frame"] = int(f)

    if blinker_state["left"]["state"]:
        if f < blinker_state["left"]["frame"] + config.BLINKER_INTERVAL:
            left_blinker_fill = config.BLINKER_ON
        if f == blinker_state["left"]["frame"] + config.BLINKER_INTERVAL:
            left_blinker_fill = config.BLINKER_OFF
        if f == blinker_state["left"]["frame"] + (config.BLINKER_INTERVAL + 18):
            left_blinker_fill = config.BLINKER_ON
            blinker_state["left"]["frame"] = int(f)

    # Draw blinkers
    shapes.draw_left_blinker(left_blinker_fill, draw)
    shapes.draw_right_blinker(right_blinker_fill, draw)

    # Draw accelerator pedal
    accelerator_pedal = shapes.draw_accelerator_pedal(current_frame_data)
    overlay.paste(accelerator_pedal, (145, 40), mask=accelerator_pedal)

    # Draw brake pedal

    brake_pedal = shapes.draw_brake_pedal(current_frame_data)
    overlay.paste(brake_pedal, (10, 40), mask=brake_pedal)

    # Steering Wheel
    steering_wheel = shapes.draw_steering_wheel(current_frame_data)
    overlay.paste(steering_wheel, (148, 13), mask=steering_wheel)

    # Merge layers
    roi_pil = Image.alpha_composite(roi_pil, overlay).convert("RGB")
    draw = ImageDraw.Draw(roi_pil)

    # 2. Speed
    speed, speed_unit = get_state.get_speed(current_frame_data, settings)
    speed_x = shapes.get_text_x(speed, config.FONT_SPEED, draw, rec_center_x)
    speed_y = rec_center_y - 33

    # Draw Speed
    draw.text((speed_x, speed_y), speed, font=config.FONT_SPEED, fill=config.FONT_WHITE)

    # Speed Unit
    speed_unit_x = shapes.get_text_x(
        speed_unit, config.FONT_SPEED_UNIT, draw, rec_center_x
    )
    speed_unit_y = rec_center_y + 1

    # Draw Speed Unit
    draw.text(
        (speed_unit_x, speed_unit_y),
        speed_unit,
        font=config.FONT_SPEED_UNIT,
        fill=config.FONT_WHITE,
    )

    # 3. Autopilot State
    autopilot_state = get_state.get_autopilot_state(current_frame_data)
    autopilot_state_x = shapes.get_text_x(
        autopilot_state, config.FONT_AUTOPILOT, draw, rec_center_x
    )
    autopilot_state_y = rec_center_y + 17

    # Draw Autopilot State
    draw.text(
        (autopilot_state_x, autopilot_state_y),
        autopilot_state,
        font=config.FONT_AUTOPILOT,
        fill=config.FONT_BLUE,
    )

    # 4. Gear State
    gear_state = get_state.get_gear_state(current_frame_data)
    gear_state_x = shapes.get_text_x(gear_state, config.FONT_GEAR, draw, 20) + 1
    gear_state_y = shapes.get_text_y(gear_state, config.FONT_GEAR, draw, 20) + 1

    # Draw Gear State
    draw.text(
        (gear_state_x, gear_state_y),
        gear_state,
        font=config.FONT_GEAR,
        fill=config.FONT_WHITE,
    )

    # CONVERT BACK
    final_roi = cv.cvtColor(np.array(roi_pil.convert("RGB")), cv.COLOR_RGB2BGR)

    canvas[y : y + h, x : x + w] = final_roi

    return canvas
