from __future__ import annotations

import argparse
from dataclasses import replace
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
    from PySide6.QtGui import QDesktopServices, QFont, QImage, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
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
        "QImage": QImage,
        "QPixmap": QPixmap,
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QComboBox": QComboBox,
        "QDialog": QDialog,
        "QFileDialog": QFileDialog,
        "QFrame": QFrame,
        "QGridLayout": QGridLayout,
        "QGroupBox": QGroupBox,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QListWidget": QListWidget,
        "QListWidgetItem": QListWidgetItem,
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
    QImage = qt["QImage"]
    QPixmap = qt["QPixmap"]
    QCheckBox = qt["QCheckBox"]
    QComboBox = qt["QComboBox"]
    QDialog = qt["QDialog"]
    QFileDialog = qt["QFileDialog"]
    QFrame = qt["QFrame"]
    QGridLayout = qt["QGridLayout"]
    QGroupBox = qt["QGroupBox"]
    QHBoxLayout = qt["QHBoxLayout"]
    QLabel = qt["QLabel"]
    QLineEdit = qt["QLineEdit"]
    QListWidget = qt["QListWidget"]
    QListWidgetItem = qt["QListWidgetItem"]
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
        telemetry_prompt_required = Signal(object)
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
                    self.log.emit(f"Checking {self.input_path} ...")
                    scan_result = app_service.scan_input_folder(self.input_path, settings)
                    preview_frame = app_service.build_preview_frame(scan_result)
                    if preview_frame is not None:
                        scan_result = replace(scan_result, preview_frame=preview_frame)
                    self.scan_finished.emit(scan_result)
                else:
                    if self.output_path is None:
                        raise ValueError("Output folder is required.")
                    self.output_path.mkdir(parents=True, exist_ok=True)
                    self.log.emit(f"Rendering to {self.output_path} ...")
                    result = app_service.render_video(
                        app_service.RenderJob(
                            self.input_path,
                            self.output_path,
                            settings,
                            selected_timestamps=self.options.selected_timestamps or None,
                            prompt_for_telemetry=True,
                        ),
                        progress_callback=self.render_progress.emit,
                    )
                    self.render_finished.emit(result)
            except app_service.TelemetryPromptRequired as error:
                self.telemetry_prompt_required.emit(error)
            except BaseException as error:  # surface SystemExit from the shared render pipeline too
                self.failed.emit(str(error) or error.__class__.__name__)
            finally:
                self.done.emit()

    class ClipSelectionDialog(QDialog):
        def __init__(self, parent, scan_result: app_service.ScanResult, selected_timestamps: tuple[str, ...]):
            super().__init__(parent)
            self.scan_result = scan_result
            self.setWindowTitle("Customize clips")
            self.resize(860, 520)

            root = QVBoxLayout(self)
            content = QHBoxLayout()

            left = QVBoxLayout()
            self.clip_list = QListWidget()
            self.clip_list.setMinimumWidth(300)
            self.clip_list.itemChanged.connect(self._update_selection_summary)
            self.clip_list.currentItemChanged.connect(self._show_current_preview)
            left.addWidget(self.clip_list)

            bulk_actions = QHBoxLayout()
            select_all = QPushButton("Select all")
            select_none = QPushButton("Select none")
            select_all.clicked.connect(self._select_all)
            select_none.clicked.connect(self._select_none)
            bulk_actions.addWidget(select_all)
            bulk_actions.addWidget(select_none)
            left.addLayout(bulk_actions)
            content.addLayout(left, stretch=1)

            right = QVBoxLayout()
            self.preview_label = QLabel("Select a clip to preview it.")
            self.preview_label.setObjectName("Diagram")
            self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_label.setMinimumSize(420, 260)
            self.preview_label.setWordWrap(True)
            self.selection_summary = QLabel("")
            right.addWidget(self.preview_label, stretch=1)
            right.addWidget(self.selection_summary)
            content.addLayout(right, stretch=2)
            root.addLayout(content)

            actions = QHBoxLayout()
            actions.addStretch(1)
            cancel = QPushButton("Cancel")
            apply = QPushButton("Apply")
            apply.setObjectName("PrimaryButton")
            cancel.clicked.connect(self.reject)
            apply.clicked.connect(self.accept)
            actions.addWidget(cancel)
            actions.addWidget(apply)
            root.addLayout(actions)

            self._populate(selected_timestamps)
            self._update_selection_summary()
            if self.clip_list.count():
                self.clip_list.setCurrentRow(0)

        def _populate(self, selected_timestamps: tuple[str, ...]):
            selected = set(selected_timestamps)
            for timestamp in ui_helpers.sorted_clip_timestamps(self.scan_result):
                files_info = self.scan_result.video_data[timestamp]
                item = QListWidgetItem(ui_helpers.clip_group_label(timestamp, files_info))
                item.setData(Qt.ItemDataRole.UserRole, timestamp)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if timestamp in selected else Qt.CheckState.Unchecked)
                self.clip_list.addItem(item)

        def _select_all(self):
            for index in range(self.clip_list.count()):
                self.clip_list.item(index).setCheckState(Qt.CheckState.Checked)

        def _select_none(self):
            for index in range(self.clip_list.count()):
                self.clip_list.item(index).setCheckState(Qt.CheckState.Unchecked)

        def _show_current_preview(self, current, _previous=None):
            if current is None:
                self.preview_label.setText("Select a clip to preview it.")
                self.preview_label.setPixmap(QPixmap())
                return
            timestamp = current.data(Qt.ItemDataRole.UserRole)
            preview = app_service.build_camera_preview_frame(self.scan_result, str(timestamp))
            if preview is None:
                self.preview_label.setPixmap(QPixmap())
                self.preview_label.setText("Preview unavailable for this clip.")
                return
            pixmap = self._pixmap_from_preview(preview)
            if pixmap is None:
                return
            target_size = self.preview_label.size()
            if target_size.width() > 0 and target_size.height() > 0:
                pixmap = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.preview_label.setText("")
            self.preview_label.setPixmap(pixmap)

        def _pixmap_from_preview(self, preview_frame: app_service.PreviewFrame):
            image = preview_frame.image_rgb
            height, width, channels = image.shape
            if channels != 3:
                return None
            qimage = QImage(
                image.data,
                width,
                height,
                channels * width,
                QImage.Format.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(qimage)

        def _update_selection_summary(self):
            selected = len(self.selected_timestamps())
            total = self.clip_list.count()
            if total == 0:
                self.selection_summary.setText("No clips found.")
            elif selected == total:
                self.selection_summary.setText(f"All {total} clips selected")
            else:
                self.selection_summary.setText(f"{selected} of {total} clips selected")

        def selected_timestamps(self) -> tuple[str, ...]:
            timestamps: list[str] = []
            for index in range(self.clip_list.count()):
                item = self.clip_list.item(index)
                timestamp = item.data(Qt.ItemDataRole.UserRole)
                if timestamp and item.checkState() == Qt.CheckState.Checked:
                    timestamps.append(str(timestamp))
            return tuple(timestamps)

    class MainWindow(QMainWindow):
        def __init__(self, input_path: str | None = None, output_path: str | None = None):
            super().__init__()
            self._thread = None
            self._worker = None
            self._last_scan = None
            self._selected_timestamps: tuple[str, ...] = ()
            self._last_output_path: Path | None = None
            self._codec_warning_shown = False
            self._mp4_output_supported = True
            self._pending_render_without_telemetry = False
            self._telemetry_prompt_active = False
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
            self._show_codec_warning_if_needed()
            if input_path:
                self._scan_selected_input()

        def _build_ui(self):
            root = QWidget()
            main_layout = QVBoxLayout(root)
            main_layout.setSpacing(16)
            main_layout.setContentsMargins(22, 22, 22, 22)

            header = QLabel("TeslaCam Telemetry")
            header.setObjectName("Header")
            main_layout.addWidget(header)

            paths_group = QGroupBox("Folders")
            paths_layout = QGridLayout(paths_group)
            self.input_edit = QLineEdit()
            self.input_edit.setPlaceholderText("Add the folder with your TeslaCam videos")
            self.input_browse_button = QPushButton("Browse…")
            self.input_browse_button.clicked.connect(self._choose_input)
            self.output_edit = QLineEdit()
            self.output_edit.setPlaceholderText("Choose where to save the finished video")
            self.output_browse_button = QPushButton("Browse…")
            self.output_browse_button.clicked.connect(self._choose_output)
            paths_layout.addWidget(QLabel("Input folder"), 0, 0)
            paths_layout.addWidget(self.input_edit, 0, 1)
            paths_layout.addWidget(self.input_browse_button, 0, 2)
            paths_layout.addWidget(QLabel("Output folder"), 1, 0)
            paths_layout.addWidget(self.output_edit, 1, 1)
            paths_layout.addWidget(self.output_browse_button, 1, 2)
            main_layout.addWidget(paths_group)

            layout_group = QGroupBox("Layout preview")
            layout_box = QVBoxLayout(layout_group)
            self.layout_combo = QComboBox()
            self.layout_combo.setPlaceholderText("Automatic layout")
            self.layout_combo.setEnabled(False)
            self.layout_combo.currentTextChanged.connect(self._update_layout_diagram)
            self.diagram_label = QLabel()
            self.diagram_label.setObjectName("Diagram")
            self.diagram_label.setFrameShape(QFrame.Shape.StyledPanel)
            self.diagram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.diagram_label.setMinimumHeight(220)
            self.diagram_label.setFont(QFont("monospace"))
            layout_box.addWidget(self.layout_combo)
            layout_box.addWidget(self.diagram_label)
            main_layout.addWidget(layout_group)
            self._show_layout_placeholder()

            clips_group = QGroupBox("Clips")
            clips_layout = QHBoxLayout(clips_group)
            self.clip_summary_label = QLabel("Clips selected: none yet")
            self.customize_clips_button = QPushButton("Customize clips…")
            self.customize_clips_button.clicked.connect(self._customize_clips)
            self.customize_clips_button.setEnabled(False)
            clips_layout.addWidget(self.clip_summary_label)
            clips_layout.addStretch(1)
            clips_layout.addWidget(self.customize_clips_button)
            main_layout.addWidget(clips_group)

            options_group = QGroupBox("Options")
            options_layout = QHBoxLayout(options_group)
            self.overlay_check = QCheckBox("Telemetry overlay")
            self.overlay_check.setChecked(True)
            self.mph_check = QCheckBox("Use MPH")
            self.keep_csv_check = QCheckBox("Keep generated CSV")
            options_layout.addWidget(self.overlay_check)
            options_layout.addWidget(self.mph_check)
            options_layout.addWidget(self.keep_csv_check)
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
            self.status_label = QLabel("Add an input folder to begin.")
            main_layout.addWidget(self.progress)
            main_layout.addWidget(self.status_label)

            self.log_panel = QTextEdit()
            self.log_panel.setReadOnly(True)
            self.log_panel.setPlaceholderText("Details will appear here.")
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
                QGroupBox { border: 1px solid #2b3548; border-radius: 10px; margin-top: 12px; padding: 14px; background: #151b29; }
                QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #c8d6f0; }
                QLineEdit, QComboBox, QTextEdit, QListWidget { background: #0c1019; border: 1px solid #33405a; border-radius: 8px; padding: 8px; }
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
                selected_timestamps=self._selected_clip_timestamps(),
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
            self.diagram_label.setPixmap(QPixmap())
            self.diagram_label.setToolTip("")
            self.diagram_label.setText(ui_helpers.layout_diagram(ui_helpers.layout_for_display_name(label)))

        def _show_layout_placeholder(self):
            self.layout_combo.clear()
            self.layout_combo.setPlaceholderText("Automatic layout")
            self.diagram_label.setPixmap(QPixmap())
            self.diagram_label.setToolTip("")
            self.diagram_label.setText(ui_helpers.layout_diagram(None))

        def _show_preview_frame(self, preview_frame: app_service.PreviewFrame):
            pixmap = self._pixmap_from_preview(preview_frame)
            if pixmap is None:
                return
            target_size = self.diagram_label.size()
            if target_size.width() > 0 and target_size.height() > 0:
                pixmap = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.diagram_label.setText("")
            self.diagram_label.setPixmap(pixmap)
            self.diagram_label.setToolTip(f"Preview from {preview_frame.timestamp}")

        def _pixmap_from_preview(self, preview_frame: app_service.PreviewFrame):
            image = preview_frame.image_rgb
            height, width, channels = image.shape
            if channels != 3:
                return None
            qimage = QImage(
                image.data,
                width,
                height,
                channels * width,
                QImage.Format.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(qimage)

        def _set_selected_timestamps(self, timestamps: tuple[str, ...]):
            self._selected_timestamps = timestamps
            self._update_clip_summary()
            self._update_selected_clip_preview()
            if self._thread is None:
                self.progress.setRange(0, 100)
                self.progress.setValue(0)
            if self._last_scan and self._last_scan.is_ready and self._mp4_output_supported:
                if self._selected_timestamps:
                    self.status_label.setText("Ready to render.")
                else:
                    self.status_label.setText("Select at least one clip to render.")
            self._sync_buttons()

        def _update_selected_clip_preview(self):
            if not self._last_scan or not self._last_scan.is_ready:
                return
            if not self._selected_timestamps:
                self._update_layout_diagram(self.layout_combo.currentText())
                return
            preview_frame = app_service.build_layout_preview_frame(
                self._last_scan,
                self._selected_timestamps[0],
            )
            if preview_frame is not None:
                self._show_preview_frame(preview_frame)

        def _update_clip_summary(self):
            total = len(ui_helpers.sorted_clip_timestamps(self._last_scan)) if self._last_scan else 0
            selected = len(self._selected_timestamps)
            if total == 0:
                self.clip_summary_label.setText("Clips selected: none yet")
            elif selected == total:
                self.clip_summary_label.setText(f"Clips selected: all {total}")
            else:
                self.clip_summary_label.setText(f"Clips selected: {selected} of {total}")

        def _customize_clips(self):
            if not self._last_scan or not self._last_scan.is_ready:
                return
            dialog = ClipSelectionDialog(self, self._last_scan, self._selected_timestamps)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._set_selected_timestamps(dialog.selected_timestamps())

        def _selected_clip_timestamps(self) -> tuple[str, ...]:
            return self._selected_timestamps

        def _append_log(self, message: str):
            self.log_panel.append(message)

        def _native_path_text(self, path: Path | str) -> str:
            return QDir.toNativeSeparators(str(path))

        def _path_from_edit(self, text: str) -> Path:
            return Path(QDir.fromNativeSeparators(text.strip()))

        def _on_input_changed(self):
            self._last_scan = None
            self._selected_timestamps = ()
            self.open_output_button.setEnabled(False)
            self._show_layout_placeholder()
            self._update_clip_summary()
            if self._mp4_output_supported:
                self.status_label.setText("Press Enter to check the input folder.")
            else:
                self.status_label.setText("Install FFmpeg, then restart the app.")
            self._sync_buttons()

        def _scan_selected_input(self):
            if self._thread is not None:
                return
            if not self.input_edit.text().strip():
                self._sync_buttons()
                return
            if not self.output_edit.text().strip():
                default_output = ui_helpers.default_output_folder(self.input_edit.text().strip())
                self.output_edit.setText(self._native_path_text(default_output))
            self.log_panel.clear()
            self._last_scan = None
            self._selected_timestamps = ()
            self._update_clip_summary()
            self._start_worker("scan")

        def _sync_buttons(self):
            busy = self._thread is not None
            has_input = bool(self.input_edit.text().strip())
            has_output = bool(self.output_edit.text().strip())
            has_selected_clip = bool(
                self._last_scan
                and self._last_scan.is_ready
                and self._selected_clip_timestamps()
            )
            self.render_button.setEnabled(
                self._mp4_output_supported
                and has_input
                and has_output
                and not busy
                and has_selected_clip
            )
            self.input_browse_button.setEnabled(not busy)
            self.output_browse_button.setEnabled(not busy)
            self.customize_clips_button.setEnabled(
                bool(self._last_scan and self._last_scan.is_ready) and not busy
            )

        def _show_codec_warning_if_needed(self):
            if self._codec_warning_shown:
                return
            codec_check = app_service.check_mp4_output_support()
            if codec_check.is_supported:
                self._mp4_output_supported = True
                return
            self._mp4_output_supported = False
            self._codec_warning_shown = True
            self.status_label.setText("Install FFmpeg, then restart the app.")
            self._sync_buttons()
            self._append_log(codec_check.message)
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowTitle("MP4 video support is missing")
            dialog.setText(codec_check.message)
            dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            dialog.setStyleSheet(self._message_box_stylesheet())
            dialog.exec()

        def _message_box_stylesheet(self) -> str:
            return """
                QMessageBox { background: #10141f; }
                QMessageBox QLabel { color: #ecf2ff; font-size: 14px; }
                QMessageBox QPushButton {
                    color: #ecf2ff;
                    background: #2c7be5;
                    border: 1px solid #4390ff;
                    border-radius: 8px;
                    padding: 8px 16px;
                    min-width: 84px;
                    font-weight: 700;
                }
                QMessageBox QPushButton:hover { background: #3d8cf6; }
            """

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
            self._worker.telemetry_prompt_required.connect(self._on_telemetry_prompt_required)
            self._worker.failed.connect(self._on_failed)
            self._worker.done.connect(self._thread.quit)
            self._worker.done.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._worker_stopped)
            if action == "scan":
                self._worker.scan_finished.connect(self._on_scan_finished)
                self._set_busy(True, "Checking input folder…")
            else:
                self.progress.setRange(0, 100)
                self.progress.setValue(0)
                self._worker.render_progress.connect(self._on_render_progress)
                self._worker.render_finished.connect(self._on_render_finished)
                self._set_busy(True, "Rendering video…")
            self._thread.start()

        def _worker_stopped(self):
            retry_without_telemetry = self._pending_render_without_telemetry
            self._pending_render_without_telemetry = False
            self._thread = None
            self._worker = None
            self.progress.setRange(0, 100)
            self._sync_buttons()
            if retry_without_telemetry:
                self.render()

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
            if scan_result.preview_frame is not None:
                self._show_preview_frame(scan_result.preview_frame)
            timestamps = tuple(ui_helpers.sorted_clip_timestamps(scan_result)) if scan_result.is_ready else ()
            self._set_selected_timestamps(timestamps)
            summary = ui_helpers.format_scan_summary_for_ui(scan_result)
            self._append_log(summary)
            if self._mp4_output_supported:
                self.status_label.setText("Ready to render." if scan_result.is_ready else "Check the details before rendering.")
            else:
                self.status_label.setText("Install FFmpeg, then restart the app.")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

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
            self.status_label.setText(f"Finished: {output_text}")
            self._append_log(f"Finished: {output_text}")

        def _on_telemetry_prompt_required(self, prompt):
            if self._telemetry_prompt_active:
                return
            self._telemetry_prompt_active = True
            message = str(prompt)
            details = getattr(prompt, "details", "")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self._append_log(message)
            try:
                continue_without_telemetry = self._ask_continue_without_telemetry(message, details)
            finally:
                self._telemetry_prompt_active = False
            if continue_without_telemetry:
                self.overlay_check.setChecked(False)
                self.status_label.setText("Rendering without telemetry overlay…")
                self._append_log("Continuing without telemetry overlay.")
                self._retry_render_after_prompt()
            else:
                self._pending_render_without_telemetry = False
                self.status_label.setText("Render cancelled.")
                self._append_log("Render cancelled.")

        def _retry_render_after_prompt(self):
            if self._thread is None:
                self.render()
            else:
                self._pending_render_without_telemetry = True

        def _ask_continue_without_telemetry(self, message: str, details: str = "") -> bool:
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowTitle("Incomplete telemetry data")
            dialog.setText(message)
            dialog.setDetailedText(details or self._default_telemetry_prompt_details())
            dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            dialog.setStyleSheet(self._message_box_stylesheet())
            return dialog.exec() == QMessageBox.StandardButton.Yes

        def _default_telemetry_prompt_details(self) -> str:
            return (
                "Common causes include the car being in Park for part of the clip, "
                "missing or partial telemetry CSV data, or telemetry that cannot be matched to every video frame.\n\n"
                "TeslaCam Telemetry can still render the selected clip without the telemetry overlay.\n\n"
                "Choose Yes to render the video without telemetry. Choose No to cancel and leave your settings unchanged."
            )

        def _on_failed(self, message: str):
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status_label.setText("Something went wrong. See details below.")
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
