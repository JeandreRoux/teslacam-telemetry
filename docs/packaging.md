# Windows packaging

TeslaCam Telemetry keeps `v1` reserved for a reliable packaged app. This packaging setup is an early Windows portable ZIP build so the desktop app can be tested outside a source checkout.

## Build locally on Windows

From the repository root:

```powershell
python -m pip install -e . pyinstaller
./scripts/build_windows.ps1
```

The script creates:

```text
dist/TeslaCamTelemetry-windows-portable.zip
```

Unzip it and run:

```text
TeslaCamTelemetry.exe
```

## GitHub Actions

The **Windows App** workflow builds the same app folder on `windows-latest` and uploads it as a workflow artifact. GitHub downloads artifacts as ZIP files, so the workflow uploads the app folder directly to avoid a ZIP inside another ZIP.

For now, the artifact is for testing only. It is not attached to releases automatically, and it is not the `v1` executable yet.

## Current packaging expectations

- Python, PySide6, OpenCV, NumPy, and app modules are bundled by PyInstaller.
- FFmpeg is not bundled. The app checks MP4 output support at startup and shows OS-specific FFmpeg install instructions if needed.
- macOS packaging should be handled separately with a `.app` bundle and signing/notarization decisions later.
