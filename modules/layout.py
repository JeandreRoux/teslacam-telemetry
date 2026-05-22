import cv2 as cv

# Layout options
FOUR_CAMERA_DEFAULT = {
    "required_cameras": ("front", "back", "left_repeater", "right_repeater"),
    "regions": {
        "front": (276, 0, 728, 546),
        "back": (524, 546, 232, 174),
        "left_repeater": (276, 546, 232, 174),
        "right_repeater": (772, 546, 232, 174),
    },
}


def place_frame(canvas, frame, region):
    x, y, width, height = region
    resized_frame = cv.resize(frame, (width, height), interpolation=cv.INTER_LANCZOS4)
    canvas[y : y + height, x : x + width] = resized_frame


def render_layout(canvas, frames, layout_config=FOUR_CAMERA_DEFAULT):
    for camera_key, region in layout_config["regions"].items():
        frame = frames[camera_key]
        place_frame(canvas, frame, region)
    
    return canvas