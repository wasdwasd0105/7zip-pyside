import os
import subprocess
import sys

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget, QProgressDialog, QPushButton, QVBoxLayout, QHBoxLayout, \
    QLabel, QProgressBar, QDialog, QInputDialog, QLineEdit
from PySide6.QtCore import QThread, Signal, Qt
from PySide6 import QtGui

import SevenZUtils
import pty
import signal
import time
import tempfile
import SevenZHelperMacOS


class ExtractionThread(QThread):
    progress_updated = Signal(int, str)
    extraction_finished = Signal()
    extraction_break = Signal()
    extraction_failed = Signal(str)
    file_conflict_made = Signal(str)
    password_required = Signal()

    def __init__(self, s7zip_bin, file_path, destination, selected_items, command_option):
        super().__init__()
        self.s7zip_bin = s7zip_bin
        self.file_path = file_path
        self.destination = destination
        self.master_fd = None
        self.paused = False
        self.stop_requested = False
        self.process = None
        self.file_conflict_option = None
        self.extraction_password = None
        self.command_option = command_option
        self.selected_items = selected_items

    def run(self):
        command = [self.s7zip_bin, self.command_option, self.file_path, *self.selected_items, '-o' + self.destination,
                   '-bsp1']

        print(command)

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                                        text=True)

        lines_to_parse = []
        hold_on_progress = False

        while True:
            line = ""
            while True:
                char = self.process.stdout.read(1)  # Read one character
                if not char:  # End of stream
                    break
                if char == '\x08':
                    hold_on_progress = True
                    continue

                line += char
                if char == '\n':
                    hold_on_progress = False
                    break

                if char == ' ' and hold_on_progress:
                    hold_on_progress = False
                    break

                if char == ':':
                    if "Enter password:" in line:
                        break

            print(line)

            if not line:
                break
            if "Would you like to replace" in line:
                lines_to_parse.append(line)

                # Buffer to accumulate characters until the prompt is found
                buffer = ""

                # Prompt string to look for
                prompt = "? (Y)es / (N)o / (A)lways / (S)kip all / A(u)to rename all / (Q)uit?"

                while prompt not in buffer:
                    char = self.process.stdout.read(1)  # Read one character
                    if not char:  # End of stream
                        break
                    buffer += char
                # Split buffer by newlines to get individual lines

                # decision = self.handle_file_conflict(existing_file_info, archive_file_info)
                self.file_conflict_made.emit(buffer)

                while self.file_conflict_option is None:
                    time.sleep(0.1)

                self.process.stdin.write(self.file_conflict_option + '\n')
                self.process.stdin.flush()
                lines_to_parse = []
                self.file_conflict_option = None

            elif "%" in line:
                percentage = int(line.split("%")[0].strip().split()[-1])
                self.progress_updated.emit(percentage, f"Extracting... {line}")

            elif "Enter password:" in line:
                self.password_required.emit()

                while self.extraction_password is None:  # Reusing the variable for simplicity
                    time.sleep(0.1)

                self.process.stdin.write(self.extraction_password + '\n')
                self.process.stdin.flush()
                self.file_conflict_option = None

        # After extraction process ends
        error_message = self.process.stderr.read()
        # print("return code is ", error_message
        if not error_message:
            self.extraction_finished.emit()
        elif "Break signaled" in error_message:
            self.extraction_break.emit()
        else:
            self.extraction_failed.emit(error_message)

    def pause_extraction(self):
        if self.process:
            self.process.send_signal(signal.SIGSTOP)
            self.paused = True

    def resume_extraction(self):
        if self.process and self.paused:
            self.process.send_signal(signal.SIGCONT)
            self.paused = False

    def stop_extraction(self):
        if self.process:
            self.process.send_signal(signal.SIGTERM)
            self.stop_requested = True


class FileConflictDialog(QDialog):
    def __init__(self, buffer, parent=None):
        super().__init__(parent)

        self.setWindowTitle("File Conflict")
        layout = QVBoxLayout(self)

        lines_to_parse = []

        lines_to_parse.extend(buffer.split("\n"))

        # Displaying the conflict details
        existing_file_label = QLabel(f"Would you like to replace the existing file:\n"
                                     f"{lines_to_parse[0]}\n"
                                     f"{lines_to_parse[1]}\n"
                                     f"{lines_to_parse[2]}\n"
                                     f"With the file from archive:\n"
                                     f"{lines_to_parse[4]}\n"
                                     f"{lines_to_parse[5]}\n"
                                     f"{lines_to_parse[6]}\n")
        layout.addWidget(existing_file_label)

        # Adding buttons for user choices
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Yes")
        self.no_button = QPushButton("No")
        self.always_button = QPushButton("Always")
        self.skip_all_button = QPushButton("Skip all")
        self.auto_rename_button = QPushButton("Auto rename all")
        self.quit_button = QPushButton("Quit")

        self.yes_button.clicked.connect(lambda: self.done(0))
        self.no_button.clicked.connect(lambda: self.done(1))
        self.always_button.clicked.connect(lambda: self.done(2))
        self.skip_all_button.clicked.connect(lambda: self.done(3))
        self.auto_rename_button.clicked.connect(lambda: self.done(4))
        self.quit_button.clicked.connect(lambda: self.done(5))

        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        button_layout.addWidget(self.always_button)
        button_layout.addWidget(self.skip_all_button)
        button_layout.addWidget(self.auto_rename_button)
        button_layout.addWidget(self.quit_button)

        layout.addLayout(button_layout)

    def closeEvent(self, event):
        # quit
        self.done(5)


class ExtractorProgressDialog(QProgressDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setWindowTitle("Extraction Progress")
        self.setRange(0, 100)
        self.setCancelButton(None)

        # Create the layout for the buttons
        btn_layout = QHBoxLayout()

        # Add Pause/Resume and Stop buttons
        self.pause_resume_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        btn_layout.addWidget(self.pause_resume_button)
        btn_layout.addWidget(self.stop_button)

        # Create our own label and progress bar
        self._label = QLabel("Extracting files...")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)

        # Add the button layout to the main layout
        layout = QVBoxLayout()
        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        layout.addLayout(btn_layout)

        # Apply the custom layout to the QDialog
        self.setLayout(layout)

    # Expose methods to control the label and bar values
    def setLabelText(self, text):
        self._label.setText(text)

    def setValue(self, value):
        self._bar.setValue(value)


class CustomFileDialog(QDialog):
    def __init__(self, initial_directory=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Extract")
        self.setMinimumSize(400, 150)

        layout = QVBoxLayout()

        label = QLabel("Extract to:")
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.initial_directory = initial_directory

        # Set the initial directory if provided
        if initial_directory:
            self.path_input.setText('')

        browse_button = QPushButton("...")
        browse_button.clicked.connect(self.browse_for_directory)

        self.extract_button = QPushButton("Extract")
        self.extract_button.clicked.connect(self.extract_directory)
        self.extract_button.setEnabled(False)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel)

        hbox = QHBoxLayout()
        hbox.addWidget(self.path_input)
        hbox.addWidget(browse_button)

        button_box = QHBoxLayout()
        button_box.addStretch(1)
        button_box.addWidget(self.extract_button)
        button_box.addWidget(cancel_button)

        layout.addWidget(label)
        layout.addLayout(hbox)
        layout.addLayout(button_box)

        self.setLayout(layout)

    def browse_for_directory(self):
        # Open the file dialog at the initial directory
        initial_directory = self.path_input.text() if self.path_input.text() != '' else self.initial_directory
        destination = QFileDialog.getExistingDirectory(self, "Select Extraction Destination", initial_directory)
        if destination:
            self.path_input.setText(destination)
            self.extract_button.setEnabled(True)

    def extract_directory(self):
        selected_directory = self.path_input.text()
        print(f"Selected directory for extraction: {selected_directory}")
        self.accept()

    def cancel(self):
        self.reject()


class Extractor:
    def __init__(self, parent: QWidget):
        self.selected_items = None
        self.temp_dir = None
        self.double_click_file = None
        self.extraction_thread = None
        self.double_click_file_temp_dir = None
        self.parent = parent
        self.s7zip_bin = SevenZUtils.determine_7zip_binary()
        self.is_from_double_click = False
        self.extract_mode = None

    def is_supported_archive(self, file_path):
        supported_extensions = SevenZUtils.get_supported_extensions()
        _, extension = os.path.splitext(file_path)
        return extension.lower() in supported_extensions

    def extract_file(self, destination: str, file_path: str, selected_items: list, command: str):
        if not self.is_supported_archive(file_path):
            QMessageBox.critical(self.parent, "Error", "Unsupported or corrupted file for extraction.")
            return

        if not destination:
            return

        self.extraction_thread = ExtractionThread(self.s7zip_bin, file_path, destination, selected_items, command)
        self.extraction_thread.progress_updated.connect(self.update_progress)
        self.extraction_thread.extraction_finished.connect(self.finish_extraction)
        self.extraction_thread.extraction_break.connect(self.break_extraction)
        self.extraction_thread.extraction_failed.connect(self.show_error)

        self.extraction_thread.file_conflict_made.connect(self.handel_file_conflict)

        self.progress_dialog = ExtractorProgressDialog(self.parent)

        self.progress_dialog.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        self.progress_dialog.stop_button.clicked.connect(self.extraction_thread.stop_extraction)

        self.extraction_thread.password_required.connect(self.prompt_password)

        self.extraction_thread.start()

    def update_progress(self, percentage, message):
        self.progress_dialog.setValue(percentage)
        self.progress_dialog.setLabelText(message)

    def extract_from_navigation_pane(self, file_path: str):
        self.extract_mode = 'NaviPane'
        # Get the parent directory of file_path
        parent_directory = os.path.dirname(file_path)
        # Pass the parent directory to CustomFileDialog
        dialog = CustomFileDialog(initial_directory=parent_directory, parent=self.parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            destination = dialog.path_input.text()
            if not destination:
                return
            self.extract_file(destination, file_path, [], 'x')

    def extract_from_main_pane(self, file_path: str, selected_items: list):
        self.extract_mode = 'MainPane'
        # Get the parent directory of file_path
        parent_directory = os.path.dirname(file_path)
        # Pass the parent directory to CustomFileDialog
        dialog = CustomFileDialog(initial_directory=parent_directory, parent=self.parent)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            destination = dialog.path_input.text()
            if not destination:
                return
            self.extract_file(destination, file_path, selected_items, 'x')

    def finish_extraction(self):
        self.progress_dialog.close()
        if self.extract_mode == 'DoubleClick':
            self.open_double_click_file()

        if self.extract_mode == 'CopyToClipboard':
            self.copy_to_clipboard()

        else:
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowTitle("Extraction Complete")
            msg_box.setText("Extraction Complete")
            msg_box.setIcon(QMessageBox.Icon.NoIcon)
            msg_box.exec()

        self.extract_mode = None

    def break_extraction(self):
        self.progress_dialog.close()
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Extraction Abort")
        msg_box.setText("Extraction Abort")
        msg_box.setIcon(QMessageBox.Icon.NoIcon)
        msg_box.exec()

    def toggle_pause_resume(self):
        if self.extraction_thread.paused:
            self.extraction_thread.resume_extraction()
            self.progress_dialog.pause_resume_button.setText("Pause")
        else:
            self.extraction_thread.pause_extraction()
            self.progress_dialog.pause_resume_button.setText("Continue")

    def show_error(self, message):
        self.progress_dialog.close()
        QMessageBox.critical(self.parent, "Extraction Error", message)

    def handel_file_conflict(self, buffer):
        conflict_dialog = FileConflictDialog(buffer)
        result = conflict_dialog.exec()
        decisions = ['Y', 'N', 'A', 'S', 'U', 'Q']
        self.extraction_thread.file_conflict_option = decisions[result]

    def prompt_password(self):
        self.progress_dialog.setVisible(False)
        password, ok = QInputDialog.getText(
            self.parent,
            "Password Required",
            "Enter password for the archive:",
            echo=QLineEdit.EchoMode.Password
        )
        if ok and password:
            self.extraction_thread.extraction_password = password
        else:
            self.extraction_thread.extraction_password = ''
        self.progress_dialog.setVisible(True)

    def extract_and_open_double_click_file(self, archive_path, file_path):
        temp_dir = tempfile.mkdtemp()
        self.extract_mode = "DoubleClick"
        self.double_click_file_temp_dir = temp_dir
        self.double_click_file = file_path
        self.extract_file(temp_dir, archive_path, [file_path], 'e')

    def open_double_click_file(self):
        if self.double_click_file_temp_dir is None or self.double_click_file is None:
            return

        extracted_file_path = os.path.join(self.double_click_file_temp_dir, os.path.basename(self.double_click_file))
        # Open the file (this will open the file with the default application associated with its file type)
        if os.path.exists(extracted_file_path):
            if sys.platform == "win32":
                os.startfile(extracted_file_path)
            elif sys.platform == "darwin":
                print(extracted_file_path)
                subprocess.run(["open", extracted_file_path])
            else:
                subprocess.run(["xdg-open", extracted_file_path])
        else:
            return

    def extract_and_copy_files_to_clipboard(self, archive_path: str, selected_items: list):
        temp_dir = tempfile.mkdtemp()
        self.extract_mode = "CopyToClipboard"
        self.temp_dir = temp_dir
        self.selected_items = selected_items
        self.extract_file(temp_dir, archive_path, selected_items, 'x')

    def copy_to_clipboard(self):
        if self.temp_dir is None or self.selected_items is None:
            return

        file_path_items = []

        for item in self.selected_items:
            extracted_file_path = os.path.join(self.temp_dir, item)
            file_path_items.append(extracted_file_path)

        print(file_path_items)

        SevenZHelperMacOS.copy_files_to_clipboard(file_path_items)
