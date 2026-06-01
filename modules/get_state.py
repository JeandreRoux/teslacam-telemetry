import pandas as pd

from modules.settings import RenderSettings


def get_gear_state(current_frame_data: pd.Series) -> str:
    """Map telemetry 'gear_state' to a single-letter display."""
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


def get_autopilot_state(current_frame_data: pd.Series) -> str:
    """Map telemetry 'autopilot_state' to a user-friendly string."""
    match current_frame_data["autopilot_state"]:
        case "TACC":
            return "Cruise"
        case "AUTOSTEER":
            return "Autosteer"
        case "SELF_DRIVING":
            return "Self Driving"
        case _:
            return ""


def get_speed(
    current_frame_data: pd.Series, settings: RenderSettings
) -> tuple[str, str]:
    """Convert and format vehicle speed according to render settings."""
    speed_mps = float(current_frame_data["vehicle_speed_mps"])
    if settings.mph:
        speed = speed_mps * 2.237
        unit = "MPH"
    else:
        speed = speed_mps * 3.6
        unit = "KM/H"

    speed = f"{abs(speed):.0f}"

    return speed, unit
