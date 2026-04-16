from PIL import Image, ImageDraw
import math

# Import modules
from modules import config
from modules import get_state


def draw_accelerator_pedal(current_frame_data, width=300, height=300):
    """Create an accelerator pedal visualization as a PIL RGBA image."""
    accelerator_pedal_position = current_frame_data["accelerator_pedal_position"]

    if accelerator_pedal_position > 0:
        color = config.PEDAL_ACTIVE
    else:
        color = config.PEDAL_INACTIVE

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
        fill=config.PEDAL_ACTIVE_CIRCLE,
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


def draw_brake_pedal(current_frame_data, width=300, height=300):
    """Create a brake pedal visualization as a PIL RGBA image."""
    brake_pedal_state = current_frame_data["brake_applied"]

    if brake_pedal_state:
        color = config.PEDAL_ACTIVE
    else:
        color = config.PEDAL_INACTIVE

    # Create canvas
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pedal_width = 190
    pedal_height = 130

    pedal_x = (width // 2) - (pedal_width // 2)
    pedal_y = (height // 2) - (pedal_height // 2)

    if brake_pedal_state:
        draw.ellipse((0, 0, 300, 300), fill=config.PEDAL_ACTIVE_CIRCLE)

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


def draw_steering_wheel(current_frame_data, size=200):
    """Create a steering wheel icon rotated by steering angle and colored by autopilot state."""
    steering_angle = int(current_frame_data["steering_wheel_angle"])
    
    if get_state.get_autopilot_state(current_frame_data) == ("Autopilot" or "Self Driving"):
        color = config.FONT_BLUE
    else:
        color = config.FONT_WHITE

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
    """Compute start/end angles for a circular chord representing pedal fill."""
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
    """Draw the left blinker polygon into the provided ImageDraw context."""
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
    """Draw the right blinker polygon into the provided ImageDraw context."""
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
    """Return the X coordinate to horizontally center text at a given center."""
    # bbox = (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font)
    text_width = bbox[2] - bbox[0]
    return shape_center - (text_width // 2) - bbox[0]


def get_text_y(text, font, draw, shape_center):
    """Return the Y coordinate to vertically center text at a given center."""
    # bbox = (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font)
    text_height = bbox[3] - bbox[1]
    return shape_center - (text_height // 2) - bbox[1]