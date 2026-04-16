# Tesla Dashcam Telemetry Viewer

Processes Tesla dashcam MP4 files and accompanying CSV telemetry files to produce a combined multi-camera video with real-time telemetry overlay.

---

## Features
* **Multi-cam Sync**: Automatically stitches Front, Rear, and Side Repeater clips into a single frame.
* **Batch Processing**: Ability to add multiple sets of clips to be processed into one large video automatically in order of timestamp.
* **Telemetry Overlay**: Real-time visualization of:
	* Speed
	* Gear selection
	* Steering wheel angle
	* Turn signal state
	* Accelerator pedal position
	* Brake pedal state
	* Self driving state

## Layout

![Screenshot of example output layout](example.png)


## Prerequisites
1. **Python 3.10+**: Check version with `python --version` in a terminal window.
2. **FFmpeg**: Required for video encoding. Verify with `ffmpeg -version`.

## Installation

1.	**Clone this repository**:
    ```bash
    git clone [https://github.com/JeandreRoux/tesla-dashcam-telemetry-viewer.git](https://github.com/JeandreRoux/tesla-dashcam-telemetry-viewer.git)
    cd tesla-dashcam-telemetry-viewer

2.	**Install dependencies**:
	```bash
	pip install -r requirements.txt
	```
3.	**Install FFmpeg (if not already installed)**:
	* **Windows**:
	1. Open PowerShell as Administrator (Right-click the Start button > Terminal Admin)
	2. Run the following command:
	```bash
	winget install ffmpeg
	```
	* **macOS**:
	Open Terminal and run:
	```bash
	brew install ffmpeg
	```
	* **Linux (Ubuntu/Debian)**
	Open Terminal and run:
	```bash
	sudo apt update && sudo apt install ffmpeg
	```

## Usage

1. **Run the script**
```bash
python main.py --input /path/to/teslacam/clips --output /path/to/save/video
```

2. **Optional Arguments**
* `--no-overlay`: Disables the telemetry overlay and only produces the multi-camera stitched video.
* `--mph`: Sets the speed units to MPH. Default is KM/H.
* `--preview`: Enables render preview while videos are being processed. Will cause processing to take slightly longer.
* `--keep-csv`: Keeps generated `csv` data file, instead of just deleting it after use.

## 	Future Roadmap:
* **Layout Options**: Allow users to toggle specific cameras (e.g. "Front View Only") or choose between different stitching configurations (Equal size 4x4 grid, Front and Rear in a 2x2 grid)
* **Theming Engine**: Add 'Light' and 'Dark' mode presets for the telemetry overlay.
* **GUI**: Build a graphical interface for ease of use.

## Troubleshooting
* Not all Tesla-generated dashcam clips contain SEI data. Only clips recorded on Tesla firmware 2025.44.25 or later and HW3 or above contain SEI data. If car is parked, SEI data may not be present.
If no SEI metadata is found, ensure your dashcam footage meets these requirements.
* If there is an error with data extraction and you meet the SEI data requirements above, you can extract the data manually via the [Tesla SEI Explorer](https://teslamotors.github.io/dashcam/sei_explorer.html) and place the `csv` file in the input directory before starting the program.