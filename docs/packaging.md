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

The **Release** workflow runs when a `v*.*.*` tag is pushed. It builds the Python package and the Windows portable app, then attaches both to the GitHub Release. The Windows release asset is named like:

```text
TeslaCamTelemetry-v0.4.0-windows-portable.zip
```

For now, the Windows ZIP is still a pre-v1 portable test build, not the final `v1` executable.

## Current packaging expectations

- Python, PySide6, OpenCV, NumPy, and app modules are bundled by PyInstaller.
- FFmpeg is not bundled. The app checks MP4 output support at startup and shows OS-specific FFmpeg install instructions if needed.
- macOS packaging should be handled separately with a `.app` bundle and signing/notarization decisions later.
