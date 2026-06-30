from __future__ import annotations

import argparse
import sys
from pathlib import Path

from modules import app_service, ui_helpers

APP_NAME = "TeslaCam Telemetry"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="teslacam-telemetry-ui",
        description="Launch the TeslaCam Telemetry desktop application.",
        allow_abbrev=False,
    )
    parser.add_argument("--input", help="optional input folder to prefill")
    parser.add_argument("--output", help="optional output folder to prefill")
    return parser


def _load_qt():
    from PySide6.QtCore import QDir, QObject, QThread, Qt, QUrl, Signal, Slot
    from PySide6.QtGui import QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QSizePolicy,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    return {
        "QDir": QDir,
        "QObject": QObject,
        "QThread": QThread,
        "Qt": Qt,
        "QUrl": QUrl,
        "Signal": Signal,
        "Slot": Slot,
        "QDesktopServices": QDesktopServices,
        "QFont": QFont,
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QComboBox": QComboBox,
        "QFileDialog": QFileDialog,
        "QFrame": QFrame,
        "QGridLayout": QGridLayout,
        "QGroupBox": QGroupBox,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPushButton": QPushButton,
        "QProgressBar": QProgressBar,
        "QSizePolicy": QSizePolicy,
        "QTextEdit": QTextEdit,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


def create_main_window(qt: dict[str, object]):
    QDir = qt["QDir"]
    QObject = qt["QObject"]
    QThread = qt["QThread"]
    Qt = qt["Qt"]
    QUrl = qt["QUrl"]
    Signal = qt["Signal"]
    Slot = qt["Slot"]
    QDesktopServices = qt["QDesktopServices"]
    QFont = qt["QFont"]
    QCheckBox = qt["QCheckBox"]
    QComboBox = qt["QComboBox"]
    QFileDialog = qt["QFileDialog"]
    QFrame = qt["QFrame"]
    QGridLayout = qt["QGridLayout"]
    QGroupBox = qt["QGroupBox"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QMainWindow = qt["QMainWindow"]
    QMessageBox = qt["QMessageBox"]
    QPushButton = qt["QPushButton"]
    QProgressBar = qt["QProgressBar"]
    QSizePolicy = qt["QSizePolicy"]
    QTextEdit = qt["QTextEdit"]
    QVBoxLayout = qt["QVBoxLayout"]
    QWidget = qt["QWidget"]

    class Worker(QObject):
        scan_finished = Signal(object)
        render_progress = Signal(object)
        render_finished = Signal(object)
        failed = Signal(str)
        log = Signal(str)
        done = Signal()

        def __init__(self, action: str, input_path: Path, output_path: Path | None, options: ui_helpers.UiRenderOptions):
            super().__init__()
            self.action = action
            self.input_path = input_path
            self.output_path = output_path
            self.options = options

        @Slot()
        def run(self):
            try:
                settings = ui_helpers.build_settings_from_options(self.options)
                if self.action == "scan":
                    self.log.emit(f"Scanning {self.input_path} ...")
                    self.scan_finished.emit(app_service.scan_input_folder(self.input_path, settings))
                else:
                    if self.output_path is None:
                        raise ValueError("Output folder is required.")
                    self.output_path.mkdir(parents=True, exist_ok=True)
                    self.log.emit(f"Rendering to {self.output_path} ...")
                    result = app_service.render_video(
                        app_service.RenderJob(self.input_path, self.output_path, settings),
                        progress_callback=self.render_progress.emit,
                    )
                    self.render_finished.emit(result)
            except BaseException as error:  # surface SystemExit from the shared render pipeline too
                self.failed.emit(str(error) or error.__class__.__name__)
            finally:
                self.done.emit()

    class MainWindow(QMainWindow):
        def __init__(self, input_path: str | None = None, output_path: str | None = None):
            super().__init__()
            self._thread = None
            self._worker = None
            self._last_scan = None
            self._last_output_path: Path | None = None
            self.setWindowTitle(APP_NAME)
            self.resize(960, 720)
            self._build_ui()
            self._apply_styles()
            if input_path:
                self.input_edit.setText(self._native_path_text(input_path))
            if output_path:
                self.output_edit.setText(self._native_path_text(output_path))
            elif input_path:
                self.output_edit.setText(self._native_path_text(ui_helpers.default_output_folder(input_path)))
            self._sync_buttons()
            if input_path:
                self._scan_selected_input()

        def _build_ui(self):
            root = QWidget()
            main_layout = QVBoxLayout(root)
            main_layout.setSpacing(16)
            main_layout.setContentsMargins(22, 22, 22, 22)

            header = QLabel("TeslaCam Telemetry")
            header.setObjectName("Header")
            subtitle = QLabel("Render TeslaCam clips with telemetry overlays from a simple desktop workflow.")
            subtitle.setObjectName("Subtitle")
            main_layout.addWidget(header)
            main_layout.addWidget(subtitle)

            paths_group = QGroupBox("Folders")
            paths_layout = QGridLayout(paths_group)
            self.input_edit = QLineEdit()
            self.input_edit.setPlaceholderText("Choose a TeslaCam folder containing camera MP4 files")
            input_browse = QPushButton("Browse…")
            input_browse.clicked.connect(self._choose_input)
            self.output_edit = QLineEdit()
            self.output_edit.setPlaceholderText("Choose where rendered videos should be written")
            output_browse = QPushButton("Browse…")
            output_browse.clicked.connect(self._choose_output)
            paths_layout.addWidget(QLabel("Input folder"), 0, 0)
            paths_layout.addWidget(self.input_edit, 0, 1)
            paths_layout.addWidget(input_browse, 0, 2)
            paths_layout.addWidget(QLabel("Output folder"), 1, 0)
            paths_layout.addWidget(self.output_edit, 1, 1)
            paths_layout.addWidget(output_browse, 1, 2)
            main_layout.addWidget(paths_group)

            layout_group = QGroupBox("Layout")
            layout_box = QVBoxLayout(layout_group)
            self.layout_combo = QComboBox()
            self.layout_combo.setPlaceholderText("Select an input folder to detect layout")
            self.layout_combo.setEnabled(False)
            self.layout_combo.setToolTip("The first desktop UI auto-selects the default layout for the detected camera set. Manual layout choices come next.")
            self.layout_combo.currentTextChanged.connect(self._update_layout_diagram)
            self.diagram_label = QLabel()
            self.diagram_label.setObjectName("Diagram")
            self.diagram_label.setFrameShape(QFrame.Shape.StyledPanel)
            self.diagram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.diagram_label.setMinimumHeight(94)
            self.diagram_label.setFont(QFont("monospace"))
            layout_box.addWidget(self.layout_combo)
            layout_box.addWidget(self.diagram_label)
            main_layout.addWidget(layout_group)
            self._show_layout_placeholder()

            options_group = QGroupBox("Options")
            options_layout = QHBoxLayout(options_group)
            self.overlay_check = QCheckBox("Telemetry overlay")
            self.overlay_check.setChecked(True)
            self.mph_check = QCheckBox("Use MPH")
            self.keep_csv_check = QCheckBox("Keep generated CSV")
            self.preview_check = QCheckBox("Preview while rendering")
            self.preview_check.setChecked(False)
            self.preview_check.setEnabled(False)
            self.preview_check.setToolTip("Preview is disabled in the desktop UI to keep rendering non-interactive.")
            options_layout.addWidget(self.overlay_check)
            options_layout.addWidget(self.mph_check)
            options_layout.addWidget(self.keep_csv_check)
            options_layout.addWidget(self.preview_check)
            options_layout.addStretch(1)
            main_layout.addWidget(options_group)

            actions = QHBoxLayout()
            self.render_button = QPushButton("Render")
            self.render_button.setObjectName("PrimaryButton")
            self.render_button.clicked.connect(self.render)
            self.open_output_button = QPushButton("Open output folder")
            self.open_output_button.clicked.connect(self.open_output_folder)
            self.open_output_button.setEnabled(False)
            actions.addWidget(self.render_button)
            actions.addWidget(self.open_output_button)
            actions.addStretch(1)
            main_layout.addLayout(actions)

            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.status_label = QLabel("Ready. Choose an input folder; the app will scan it automatically.")
            main_layout.addWidget(self.progress)
            main_layout.addWidget(self.status_label)

            self.log_panel = QTextEdit()
            self.log_panel.setReadOnly(True)
            self.log_panel.setPlaceholderText("Scan and render logs will appear here.")
            self.log_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            main_layout.addWidget(self.log_panel, stretch=1)

            self.setCentralWidget(root)
            self.input_edit.textChanged.connect(self._on_input_changed)
            self.input_edit.editingFinished.connect(self._scan_selected_input)
            self.output_edit.textChanged.connect(self._sync_buttons)

        def _apply_styles(self):
            self.setStyleSheet(
                """
                QMainWindow { background: #10141f; }
                QWidget { color: #ecf2ff; font-size: 14px; }
                QLabel#Header { font-size: 28px; font-weight: 700; }
                QLabel#Subtitle { color: #a9b7d0; }
                QGroupBox { border: 1px solid #2b3548; border-radius: 10px; margin-top: 12px; padding: 14px; background: #151b29; }
                QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #c8d6f0; }
                QLineEdit, QComboBox, QTextEdit { background: #0c1019; border: 1px solid #33405a; border-radius: 8px; padding: 8px; }
                QPushButton { background: #24314a; border: 1px solid #3a4b6f; border-radius: 8px; padding: 9px 14px; }
                QPushButton:hover { background: #2e3e5d; }
                QPushButton:disabled { color: #6d7890; background: #192030; border-color: #252d3d; }
                QPushButton#PrimaryButton { background: #2c7be5; border-color: #4390ff; font-weight: 700; }
                QPushButton#PrimaryButton:disabled { color: #7f8aa3; background: #192030; border-color: #252d3d; }
                QLabel#Diagram { background: #0c1019; border: 1px solid #33405a; border-radius: 10px; padding: 12px; color: #d9e6ff; }
                QProgressBar { border: 1px solid #33405a; border-radius: 8px; background: #0c1019; text-align: center; }
                QProgressBar::chunk { background: #2c7be5; border-radius: 7px; }
                """
            )

        def _options(self) -> ui_helpers.UiRenderOptions:
            return ui_helpers.UiRenderOptions(
                overlay_enabled=self.overlay_check.isChecked(),
                mph=self.mph_check.isChecked(),
                keep_csv=self.keep_csv_check.isChecked(),
                preview=False,
                layout_label=self.layout_combo.currentText(),
            )

        def _choose_input(self):
            folder = QFileDialog.getExistingDirectory(self, "Choose input folder", self.input_edit.text() or str(Path.home()))
            if folder:
                self.input_edit.setText(self._native_path_text(folder))
                if not self.output_edit.text().strip():
                    self.output_edit.setText(self._native_path_text(ui_helpers.default_output_folder(folder)))
                self._scan_selected_input()

        def _choose_output(self):
            folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text() or str(Path.home()))
            if folder:
                self.output_edit.setText(self._native_path_text(folder))

        def _update_layout_diagram(self, label: str):
            self.diagram_label.setText(ui_helpers.layout_diagram(ui_helpers.layout_for_display_name(label)))

        def _show_layout_placeholder(self):
            self.layout_combo.clear()
            self.layout_combo.setPlaceholderText("Select an input folder to detect layout")
            self.diagram_label.setText(ui_helpers.layout_diagram(None))

        def _append_log(self, message: str):
            self.log_panel.append(message)

        def _native_path_text(self, path: Path | str) -> str:
            return QDir.toNativeSeparators(str(path))

        def _path_from_edit(self, text: str) -> Path:
            return Path(QDir.fromNativeSeparators(text.strip()))

        def _on_input_changed(self):
            self._last_scan = None
            self.open_output_button.setEnabled(False)
            self._show_layout_placeholder()
            self.status_label.setText("Input changed. Scanning will run automatically when the folder is selected.")
            self._sync_buttons()

        def _scan_selected_input(self):
            if self._thread is not None:
                return
            if not self.input_edit.text().strip():
                self._sync_buttons()
                return
            if not self.output_edit.text().strip():
                self.output_edit.setText(self._native_path_text(ui_helpers.default_output_folder(self.input_edit.text().strip())))
            self.log_panel.clear()
            self._last_scan = None
            self._start_worker("scan")

        def _sync_buttons(self):
            busy = self._thread is not None
            has_input = bool(self.input_edit.text().strip())
            has_output = bool(self.output_edit.text().strip())
            self.render_button.setEnabled(has_input and has_output and not busy and bool(self._last_scan and self._last_scan.is_ready))

        def _set_busy(self, busy: bool, status: str):
            self.status_label.setText(status)
            self.progress.setRange(0, 0 if busy else 100)
            if not busy:
                self.progress.setValue(0)
            self._sync_buttons()

        def _start_worker(self, action: str):
            input_path = self._path_from_edit(self.input_edit.text())
            output_text = self.output_edit.text().strip()
            output_path = self._path_from_edit(output_text) if output_text else None
            self._thread = QThread(self)
            self._worker = Worker(action, input_path, output_path, self._options())
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.log.connect(self._append_log)
            self._worker.failed.connect(self._on_failed)
            self._worker.done.connect(self._thread.quit)
            self._worker.done.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._worker_stopped)
            if action == "scan":
                self._worker.scan_finished.connect(self._on_scan_finished)
                self._set_busy(True, "Scanning input folder…")
            else:
                self.progress.setRange(0, 100)
                self.progress.setValue(0)
                self._worker.render_progress.connect(self._on_render_progress)
                self._worker.render_finished.connect(self._on_render_finished)
                self._set_busy(True, "Rendering video…")
            self._thread.start()

        def _worker_stopped(self):
            self._thread = None
            self._worker = None
            self.progress.setRange(0, 100)
            self._sync_buttons()

        def scan(self):
            self.log_panel.clear()
            self._last_scan = None
            self._start_worker("scan")

        def render(self):
            self._start_worker("render")

        def _on_scan_finished(self, scan_result):
            self._last_scan = scan_result
            if scan_result.layout is not None:
                label = ui_helpers.layout_display_name(scan_result.layout)
                self.layout_combo.clear()
                self.layout_combo.addItems(ui_helpers.available_layout_labels())
                index = self.layout_combo.findText(label)
                if index >= 0:
                    self.layout_combo.setCurrentIndex(index)
                else:
                    self._update_layout_diagram(label)
            else:
                self._show_layout_placeholder()
            summary = ui_helpers.format_scan_summary_for_ui(scan_result)
            self._append_log(summary)
            self.status_label.setText("Ready to render." if scan_result.is_ready else "Scan found issues. See log.")
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if scan_result.is_ready else 0)

        def _on_render_progress(self, progress):
            percent, status = ui_helpers.format_progress(progress)
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.status_label.setText(status)

        def _on_render_finished(self, result):
            self._last_output_path = result.output_path.parent
            self.open_output_button.setEnabled(True)
            self.progress.setValue(100)
            output_text = self._native_path_text(result.output_path)
            self.status_label.setText(f"Render complete: {output_text}")
            self._append_log(f"Render complete: {output_text}")

        def _on_failed(self, message: str):
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status_label.setText("Operation failed. See log.")
            self._append_log(f"Error: {message}")
            QMessageBox.warning(self, APP_NAME, message)

        def open_output_folder(self):
            folder = self._last_output_path or self._path_from_edit(self.output_edit.text() or str(Path.home()))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    return MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    qt = _load_qt()
    QApplication = qt["QApplication"]
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    MainWindow = create_main_window(qt)
    window = MainWindow(input_path=args.input, output_path=args.output)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
