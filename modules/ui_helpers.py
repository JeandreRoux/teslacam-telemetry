from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules import app_service, layouts
from modules.settings import RenderSettings

FOUR_CAMERA_LABEL = "Four-camera standard"
SIX_CAMERA_LABEL = "Six-camera grid"
UNKNOWN_LAYOUT_LABEL = "Automatic"

_LAYOUTS_BY_LABEL: dict[str, layouts.LayoutConfig] = {
    FOUR_CAMERA_LABEL: layouts.FOUR_CAMERA_DEFAULT,
    SIX_CAMERA_LABEL: layouts.SIX_CAMERA_DEFAULT,
}

_LABELS_BY_INTERNAL_NAME = {
    layouts.FOUR_CAMERA_DEFAULT["name"]: FOUR_CAMERA_LABEL,
    layouts.SIX_CAMERA_DEFAULT["name"]: SIX_CAMERA_LABEL,
}

_CAMERA_LABELS = {
    "front": "Front",
    "back": "Rear",
    "left_repeater": "Left repeater",
    "right_repeater": "Right repeater",
    "left_pillar": "Left pillar",
    "right_pillar": "Right pillar",
}


@dataclass(frozen=True)
class UiRenderOptions:
    """Render options exposed by the desktop UI."""

    overlay_enabled: bool = True
    mph: bool = False
    keep_csv: bool = False
    preview: bool = False
    layout_label: str = UNKNOWN_LAYOUT_LABEL


def available_layout_labels() -> list[str]:
    """Return generic user-facing layout choices for the desktop UI."""
    return [FOUR_CAMERA_LABEL, SIX_CAMERA_LABEL]


def layout_display_name(layout: layouts.LayoutConfig | None) -> str:
    """Return a friendly layout name without hardware generation labels."""
    if layout is None:
        return UNKNOWN_LAYOUT_LABEL
    return _LABELS_BY_INTERNAL_NAME.get(layout.get("name", ""), layout.get("name", UNKNOWN_LAYOUT_LABEL))


def layout_for_display_name(label: str) -> layouts.LayoutConfig | None:
    """Return the layout config for a friendly label, if the label is selectable."""
    return _LAYOUTS_BY_LABEL.get(label)


def camera_display_name(camera_key: str) -> str:
    """Return a friendly camera name for UI labels."""
    return _CAMERA_LABELS.get(camera_key, camera_key.replace("_", " ").title())


def layout_diagram(layout: layouts.LayoutConfig | None) -> str:
    """Return a compact text diagram for the selected layout."""
    if layout is None:
        return "Preview will appear here."

    if layout["required_cameras"] == layouts.SIX_CAMERA_KEYS:
        return "[ Left pillar ] [    Front    ] [ Right pillar ]\n[ Left repeater ] [    Rear     ] [ Right repeater ]"

    if layout["required_cameras"] == layouts.FOUR_CAMERA_KEYS:
        return "        [        Front        ]\n[ Left repeater ] [ Rear ] [ Right repeater ]"

    return "\n".join(f"[ {camera_display_name(camera)} ]" for camera in layout["required_cameras"])


def build_settings_from_options(options: UiRenderOptions) -> RenderSettings:
    """Convert UI option state into shared render settings."""
    return app_service.build_render_settings(
        no_overlay=not options.overlay_enabled,
        mph=options.mph,
        preview=options.preview,
        keep_csv=options.keep_csv,
        layout=layout_for_display_name(options.layout_label),
    )


def format_scan_summary_for_ui(scan_result: app_service.ScanResult) -> str:
    """Format scan output with friendly layout names for the desktop UI."""
    summary = app_service.format_scan_summary(scan_result)
    internal_name = scan_result.selected_layout_name
    if internal_name:
        summary = summary.replace(
            f"Selected layout: {internal_name}",
            f"Selected layout: {layout_display_name(scan_result.layout)}",
        )
    return summary


def format_progress(progress: app_service.RenderProgress) -> tuple[int, str]:
    """Return progress percentage and status text for a render progress event."""
    if progress.total_frames <= 0:
        percent = 0
    else:
        percent = max(0, min(100, round((progress.frames_written / progress.total_frames) * 100)))
    status = (
        f"Clip {progress.clip_index}/{progress.clip_count} "
        f"({progress.timestamp}): {progress.frames_written}/{progress.total_frames} frames"
    )
    return percent, status


def default_output_folder(input_folder: Path | str | None) -> Path:
    """Suggest an output folder near the selected input folder."""
    if input_folder:
        return Path(input_folder).expanduser().resolve().parent / "teslacam-telemetry-output"
    return Path.home() / "teslacam-telemetry-output"
