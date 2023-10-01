import os
import signal
import subprocess

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QHBoxLayout, QPushButton, QLineEdit, QLabel, \
    QSpinBox, QComboBox, QVBoxLayout, QDialog, QCheckBox, QProgressBar
from PySide6.QtCore import QThread, Signal, Qt
import SevenZUtils  # Assuming this contains your utility functions


class ArchivingThread(QThread):
    progress_updated = Signal(int, str)
    archive_failed = Signal(str)
    archive_finished = Signal()
    archive_break = Signal()

    def __init__(self, s7zip_bin, source_files, destination, archive_type, password=None, compression_level='normal'):
        super().__init__()
        self.stop_requested = None
        self.s7zip_bin = s7zip_bin
        self.source_files = source_files
        self.destination = destination
        self.archive_type = archive_type
        self.password = password
        self.compression_level = compression_level
        self.process = None
        self.paused = False

    def run(self):
        command = [
            self.s7zip_bin,
            'a',  # 'a' command to add files to the archive
            '-t' + self.archive_type,  # Archive type (e.g., zip, 7z)
            self.destination,  # Destination archive file
        ]

        # List of source files to be archived
        command.extend(self.source_files)

        command.append('-bsp1')

        # If password is provided, add it to the command
        if self.password:
            command += ['-p' + self.password]

        # Add compression level if provided
        if self.compression_level:
            command += ['-mx=' + self.compression_level]

        print(command)

        # Start the 7-Zip process
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

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

            if not line:
                break

            if "%" in line:
                percentage = int(line.split("%")[0].strip().split()[-1])
                self.progress_updated.emit(percentage, f"Archiving... {line}")

        # After extraction process ends
        error_message = self.process.stderr.read()
        # print("return code is ", error_message
        if not error_message:
            self.archive_finished.emit()
        elif "Break signaled" in error_message:
            self.archive_break.emit()
        else:
            self.archive_failed.emit(error_message)

    def pause_archive(self):
        if self.process:
            self.process.send_signal(signal.SIGSTOP)
            self.paused = True

    def resume_archive(self):
        if self.process and self.paused:
            self.process.send_signal(signal.SIGCONT)
            self.paused = False

    def stop_archive(self):
        if self.process:
            self.process.send_signal(signal.SIGTERM)
            self.stop_requested = True


class AddFilesThread(QThread):
    progress_updated = Signal(int, str)
    add_files_failed = Signal(str)
    add_files_finished = Signal()
    archive_break = Signal()

    def __init__(self, s7zip_bin, archive_path, files_to_add, sub_dir=None):
        super().__init__()
        self.s7zip_bin = s7zip_bin
        self.archive_path = archive_path
        self.files_to_add = files_to_add
        self.sub_dir = sub_dir  # The subdirectory within the archive where files will be added
        self.process = None
        self.process = None
        self.paused = False
        self.stop_requested = None

    def run(self):

        command = [
            self.s7zip_bin,
            'a',  # 'a' command to add files to the archive
            self.archive_path,  # Archive to which files will be added
        ]

        if self.sub_dir:
            # If a subdirectory is specified, prepend it to each file
            command.extend([f"{self.sub_dir}/{file}" for file in self.files_to_add])
        else:
            command.extend(self.files_to_add)

        command.append('-bsp1')

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

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

            if not line:
                break

            if "%" in line:
                percentage = int(line.split("%")[0].strip().split()[-1])
                self.progress_updated.emit(percentage, f"Adding files... {line}")

        error_message = self.process.stderr.read()
        if not error_message:
            self.add_files_finished.emit()
        else:
            self.add_files_failed.emit(error_message)

    def pause_archive(self):
        if self.process:
            self.process.send_signal(signal.SIGSTOP)
            self.paused = True

    def resume_archive(self):
        if self.process and self.paused:
            self.process.send_signal(signal.SIGCONT)
            self.paused = False

    def stop_archive(self):
        if self.process:
            self.process.send_signal(signal.SIGTERM)
            self.stop_requested = True


class RenameFilesThread(QThread):
    rename_files_finished = Signal()
    rename_files_failed = Signal(str)

    def __init__(self, s7zip_bin, files_to_add, archive_path, sub_dir):
        super().__init__()
        self.s7zip_bin = s7zip_bin
        self.files_to_add = files_to_add
        self.archive_path = archive_path
        self.sub_dir = sub_dir
        self.process = None

    def run(self):
        try:
            for file in self.files_to_add:
                # Extract just the filename from the file path
                filename = os.path.basename(file)

                # Construct the new path for the file
                new_path = os.path.join(self.sub_dir, filename)

                # Run the 7zz command to rename the file
                command = [self.s7zip_bin, 'rn', self.archive_path, filename, new_path]
                subprocess.check_call(command)

            # If all files are renamed successfully, emit the finish signal
            self.rename_files_finished.emit()
        except subprocess.CalledProcessError as e:
            # If an error occurs during the subprocess call, emit the fail signal with the error message
            self.rename_files_failed.emit(f"Failed to rename files. Error: {str(e)}")
        except Exception as e:
            # For other exceptions, emit the fail signal with the error message
            self.rename_files_failed.emit(str(e))


class Archiver:
    def __init__(self, parent):
        self.archiving_thread = None
        self.progress_dialog = None
        self.parent = parent
        self.s7zip_bin = SevenZUtils.determine_7zip_binary()

    def is_supported_archive_type(self, archive_type):
        # Implement this method to check if the archive_type is supported
        pass

    def archive_file(self, source_files, destination, archive_type, password=None, compression_level='normal'):
        # if not self.is_supported_archive_type(archive_type):
        #     QMessageBox.critical(self.parent, "Error", "Unsupported archive type.")
        #     return

        self.archiving_thread = ArchivingThread(
            self.s7zip_bin, source_files, destination, archive_type, password, compression_level
        )
        self.archiving_thread.progress_updated.connect(self.update_progress)
        self.archiving_thread.archive_finished.connect(self.finish_archive)
        self.archiving_thread.archive_failed.connect(self.show_error)
        self.archiving_thread.archive_break.connect(self.break_archive)

        self.progress_dialog = ArchiverProgressDialog(self.parent)
        self.progress_dialog.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        self.progress_dialog.stop_button.clicked.connect(self.archiving_thread.stop_archive)

        self.archiving_thread.start()

    def add_files_to_archive(self, archive_path, files_to_add, sub_dir=None):
        self.sub_dir = sub_dir  # Store sub_dir as an instance variable
        self.files_to_add = files_to_add  # Store files_to_add as an instance variable
        self.archive_path = archive_path  # Store archive_path as an instance variable

        self.add_files_thread = AddFilesThread(self.s7zip_bin, archive_path, files_to_add)
        self.add_files_thread.progress_updated.connect(self.update_progress)
        self.add_files_thread.add_files_failed.connect(self.show_error)
        self.add_files_thread.add_files_finished.connect(self.on_add_files_finished)

        self.progress_dialog = ArchiverProgressDialog(self.parent)
        self.progress_dialog.pause_resume_button.clicked.connect(self.toggle_pause_resume_add_files)
        self.progress_dialog.stop_button.clicked.connect(self.add_files_thread.stop_archive)

        self.add_files_thread.start()

    def toggle_pause_resume_add_files(self):
        if self.add_files_thread.paused:
            self.add_files_thread.resume_archive()
            self.progress_dialog.pause_resume_button.setText("Pause")
        else:
            self.add_files_thread.pause_archive()
            self.progress_dialog.pause_resume_button.setText("Continue")

    def toggle_pause_resume(self):
        if self.archiving_thread.paused:
            self.archiving_thread.resume_archive()
            self.progress_dialog.pause_resume_button.setText("Pause")
        else:
            self.archiving_thread.pause_archive()
            self.progress_dialog.pause_resume_button.setText("Continue")

    def show_error(self, message):
        self.progress_dialog.close()
        QMessageBox.critical(self.parent, "Extraction Error", message)

    def update_progress(self, percentage, message):
        self.progress_dialog.setValue(percentage)
        self.progress_dialog.setLabelText(message)

    def finish_archive(self):
        self.progress_dialog.close()
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Archive Complete")
        msg_box.setText("Archive Complete")
        msg_box.setIcon(QMessageBox.Icon.NoIcon)
        msg_box.exec()

    def break_archive(self):
        self.progress_dialog.close()
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Archive Abort")
        msg_box.setText("Archive Abort")
        msg_box.setIcon(QMessageBox.Icon.NoIcon)
        msg_box.exec()

    def confirm_add_files(self, archive_path, files_to_add, sub_dir=None):
        message = f'Are you sure you want to add these files to {archive_path}?'
        if sub_dir:
            message += f'\nThey will be added to the subdirectory: {sub_dir}'

        reply = QMessageBox.question(self.parent, 'Add Files',
                                     message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.add_files_to_archive(archive_path, files_to_add, sub_dir)

    def archive_file_by_archive_options(self, input_paths: list):
        dialog = ArchiveDialog(input_paths[0])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return  # Exit if the user cancels the dialog

        options = dialog.get_selected_options()

        source_files = input_paths
        destination = options.get('save_path', '')
        archive_type = options.get('archive_type', '')
        password = options.get('password', None)
        compression_level = options.get('compression_level', 'normal')

        self.archive_file(source_files, destination, archive_type, password, compression_level)

    def on_add_files_finished(self):
        if self.sub_dir is not None:
            self.start_rename_files_thread()
        else:
            self.finish_adding_files()

    def start_rename_files_thread(self):
        self.rename_files_thread = RenameFilesThread(self.s7zip_bin, self.files_to_add, self.archive_path, self.sub_dir)
        self.rename_files_thread.rename_files_finished.connect(self.finish_adding_files)
        self.rename_files_thread.rename_files_failed.connect(self.show_error)
        self.rename_files_thread.start()

    def finish_adding_files(self):
        self.progress_dialog.close()
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Add Files Complete")
        msg_box.setText("Files have been successfully added.")
        msg_box.setIcon(QMessageBox.Icon.NoIcon)
        msg_box.exec()
        self.parent.reload_archive()



class ArchiverProgressDialog(QProgressDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setWindowTitle("Archiving Progress")
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
        self._label = QLabel("Archiving files...")
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


class ArchiveDialog(QDialog):
    def __init__(self, input_path, parent=None):
        super(ArchiveDialog, self).__init__(parent)
        self.setWindowTitle("Archive Options")

        layout = QVBoxLayout()

        # Initialize with input_path
        self.input_path = input_path

        # Directory Line Edit (for displaying the path)
        self.dir_line_edit = QLineEdit()
        self.dir_line_edit.setReadOnly(True)  # Make it appear disabled

        # Save Path (for displaying the filename)
        self.filename_line_edit = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_save_path)

        # Archive Type ComboBox
        self.archive_type_combo = QComboBox()
        self.archive_type_combo.addItems(["7z", "zip"])
        self.archive_type_combo.currentIndexChanged.connect(self.update_filename_extension)

        # Automatically set default save path based on input_path and archive type
        self.set_default_save_path("7z")

        # Laying out dir_line_edit and browse_button
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Directory:"))
        dir_layout.addWidget(self.dir_line_edit)
        dir_layout.addWidget(self.browse_button)

        # Laying out filename_line_edit
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("Filename:"))
        filename_layout.addWidget(self.filename_line_edit)

        # Laying out archive type ComboBox
        archive_type_layout = QHBoxLayout()
        archive_type_layout.addWidget(QLabel("Archive format:"))
        archive_type_layout.addWidget(self.archive_type_combo)

        layout.addLayout(dir_layout)
        layout.addLayout(filename_layout)
        layout.addLayout(archive_type_layout)

        # Compression Level
        self.compress_level_combo = QComboBox()
        self.compress_level_combo.addItems(["0", "1", "3", "5", "7", "9"])
        self.compress_level_combo.setCurrentIndex(3)
        compress_level_layout = QHBoxLayout()
        compress_level_layout.addWidget(QLabel("Compression Level:"))
        compress_level_layout.addWidget(self.compress_level_combo)

        layout.addLayout(compress_level_layout)

        # Encryption Option
        self.password_line_edit = QLineEdit()
        self.show_password_check_box = QCheckBox("Show Password")
        self.show_password_check_box.stateChanged.connect(self.toggle_password_visibility)
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Password: (Optional)"))
        password_layout.addWidget(self.password_line_edit)
        password_layout.addWidget(self.show_password_check_box)

        layout.addLayout(password_layout)

        # OK and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def set_default_save_path(self, extension):
        default_save_path = os.path.basename(f"{self.input_path}.{extension}")
        self.filename_line_edit.setText(default_save_path)

    def update_filename_extension(self):
        current_filename = self.filename_line_edit.text()
        new_extension = self.archive_type_combo.currentText()

        # Update the filename extension
        filename_without_extension, _ = os.path.splitext(current_filename)
        new_filename = f"{filename_without_extension}.{new_extension}"

        self.filename_line_edit.setText(new_filename)

    def browse_save_path(self):
        default_dir = os.path.dirname(self.input_path)
        chosen_dir = QFileDialog.getExistingDirectory(self, "Select Save Directory", default_dir)
        if chosen_dir:
            self.ok_button.setEnabled(True)
            self.dir_line_edit.setText(chosen_dir)

    def toggle_password_visibility(self):
        if self.show_password_check_box.isChecked():
            self.password_line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_line_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def get_selected_options(self):
        archive_type = self.archive_type_combo.currentText()
        compression_level = self.compress_level_combo.currentText()
        password = self.password_line_edit.text()
        save_path = os.path.join(self.dir_line_edit.text(), self.filename_line_edit.text())
        return {
            'source_files': self.input_path,
            'archive_type': archive_type,
            'compression_level': compression_level,
            'password': password,
            'save_path': save_path,
        }

    def accept(self):
        options = self.get_selected_options()
        save_path = options['save_path']
        base_path, ext = os.path.splitext(save_path)

        if os.path.exists(save_path):
            msg_box = QMessageBox()
            msg_box.setWindowTitle("File Exists")
            msg_box.setText(f"The file {os.path.basename(save_path)} already exists.")

            keep_button = msg_box.addButton('Auto Rename', QMessageBox.ButtonRole.YesRole)
            msg_box.setDefaultButton(keep_button)  # Set as default button

            replace_button = msg_box.addButton('Replace', QMessageBox.ButtonRole.NoRole)
            cancel_button = msg_box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)

            msg_box.exec()

            if msg_box.clickedButton() == keep_button:
                # Rename the file if it already exists
                counter = 1
                while os.path.exists(f"{base_path}({counter}){ext}"):
                    counter += 1
                save_path = f"{base_path}({counter}){ext}"
                self.filename_line_edit.setText(os.path.basename(save_path))
                self.dir_line_edit.setText(os.path.dirname(save_path))
                super().accept()

            elif msg_box.clickedButton() == replace_button:
                super().accept()
            else:
                return
        else:
            super().accept()
