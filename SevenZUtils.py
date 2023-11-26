import subprocess
import sys
import os

import chardet
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QDialog, QTextEdit, QPushButton, QVBoxLayout, QProgressDialog, QMessageBox, QFormLayout, \
    QLabel

import SevenZHelperMacOS


def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    print(os.path.join(base_path, relative_path))
    return os.path.join(base_path, relative_path)


def determine_7zip_binary():
    if sys.platform == "win32":
        return ""  # Path to 7-Zip binary on Windows

    elif sys.platform == "darwin":
        if 'APP_SANDBOX_CONTAINER_ID' in os.environ:
            return resource_path('./bin/macos/7zz-mango')
        return "./bin/macos/7zz"

    elif sys.platform.startswith("linux"):
        return ""  # Path to 7-Zip binary on Linux

    else:
        raise Exception("Unsupported OS platform")


def get_supported_extensions():
    return (
        '.7z', '.apfs', '.img', '.apm', '.ar', '.a', '.deb', '.udeb', '.lib', '.arj', '.b64', '.obj', '.cab',
        '.chm',
        '.chi', '.chq', '.chw',
        '.msi', '.msp', '.doc', '.xls', '.ppt', '.cpio', '.cramfs', '.dmg', '.elf', '.ext', '.ext2', '.ext3',
        '.ext4',
        '.fat', '.flv', '.gpt',
        '.mbr', '.hfs', '.hfsx', '.hxs', '.hxi', '.hxr', '.hxq', '.hxw', '.lit', '.ihex', '.iso', '.lpimg', '.lzh',
        '.lha', '.mbr', '.macho',
        '.mslz', '.mub', '.ntfs', '.nsis', '.exe', '.dll', '.sys', '.pmd', '.qcow', '.qcow2', '.qcow2c', '.rar',
        '.r00',
        '.rpm', '.swf', '.simg',
        '.001', '.squashfs', '.te', '.scap', '.uefif', '.udf', '.vdi', '.vhd', '.vhdx', '.avhdx', '.vmdk', '.xar',
        '.pkg', '.xip', '.z', '.taz', '.zip',
        '.bz2', '.bzip2', '.tbz2', '.tbz', '.gz', '.gzip', '.tgz', '.tpz', '.apk', '.lzma', '.lzma86', '.tar',
        '.ova',
        '.wim', '.swm', '.esd', '.ppkg', '.xz', '.txz')


def show_file_properties(file_path: str):
    # Platform-specific commands to show properties
    if sys.platform == "win32":
        # Windows
        subprocess.Popen(["explorer", "/select,", file_path])


    elif sys.platform == "darwin":
        # macOS
        dialog = FileInfoDialogOSX(file_path)
        dialog.exec()


    elif sys.platform.startswith("linux"):
        # Linux (assuming Nautilus is the file manager)
        subprocess.Popen(["nautilus", "--properties", file_path])


def get_file_metadata_osx(file_path: str) -> dict:
    try:
        # Run the mdls command and get the output
        result = subprocess.check_output(['mdls', file_path], text=True)

        # Parse the output into a dictionary
        metadata = {}
        for line in result.splitlines():
            key, _, value = line.partition("=")
            metadata[key.strip()] = value.strip()

        return metadata
    except subprocess.CalledProcessError:
        print(f"Error retrieving metadata for {file_path}")
        return {}


def display_metadata(file_path: str):
    metadata = get_file_metadata_osx(file_path)

    # Convert the metadata dictionary to a string for display
    metadata_str = "\n".join(f"{key}: {value}" for key, value in metadata.items())

    # Display the metadata in a message box
    msg_box = QMessageBox()
    msg_box.setWindowTitle("File Metadata")
    msg_box.setText(metadata_str)
    msg_box.exec()


class FileInfoDialogOSX(QDialog):
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle("File Properties")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        # Get the metadata
        metadata = get_file_metadata_osx(file_path)

        # Map raw metadata keys to user-friendly labels
        label_map = {
            "kMDItemDisplayName": "File Name",
            "kMDItemKind": "Type",
            "kMDItemDateAdded": "Date Created",
            "kMDItemContentModificationDate": "Date Modified",
            "kMDItemLogicalSize": "Size",
            "kMDItemContentType": "Content Type",
            "kMDItemContentCreationDate": "Content Creation Date",
            "kMDItemLastUsedDate": "Last Used Date",
            "kMDItemUseCount": "Use Count",
            "kMDItemVersion": "Version",
            "kMDItemWhereFroms": "Downloaded From",
            "kMDItemPixelHeight": "Pixel Height",
            "kMDItemPixelWidth": "Pixel Width",
            "kMDItemDurationSeconds": "Duration (seconds)",
            "kMDItemTitle": "Title",
            "kMDItemAuthors": "Authors",
            "kMDItemKeywords": "Keywords",
            "kMDItemNumberOfPages": "Number of Pages",
            "kMDItemPageHeight": "Page Height",
            "kMDItemPageWidth": "Page Width",
            "kMDItemAlbum": "Album",
            "kMDItemArtist": "Artist",
            "kMDItemGenre": "Genre",
            "kMDItemDescription": "Description",
            "kMDItemCopyright": "Copyright",
            "kMDItemResolutionWidthDPI": "Resolution Width DPI",
            "kMDItemResolutionHeightDPI": "Resolution Height DPI",
        }

        # Create a form layout to display the metadata
        form_layout = QFormLayout()
        for raw_key, label in label_map.items():
            if raw_key in metadata:
                form_layout.addRow(QLabel(label), QLabel(str(metadata[raw_key])))

        layout.addLayout(form_layout)

        # Add a close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.setLayout(layout)


def get_app_version():
    if sys.platform == "darwin":
        # macOS
        return SevenZHelperMacOS.get_app_version()

    # Not yet finish
    else:
        return "Github"


class DeleteWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, s7zip_bin, archive_path, item_full_path):
        super().__init__()
        self.s7zip_bin = s7zip_bin
        self.archive_path = archive_path
        self.item_full_path = item_full_path

    def run(self):
        command = [self.s7zip_bin, 'd', self.archive_path, self.item_full_path]
        try:
            subprocess.check_call(command)
            self.finished.emit(True, "")
        except subprocess.CalledProcessError:
            self.finished.emit(False, "Failed to delete the file.")


class TestArchiveWorker(QThread):
    finished = Signal(str)

    def __init__(self, archive_path, s7zip_bin):
        super().__init__()
        self.archive_path = archive_path
        self.s7zip_bin = s7zip_bin

    def run(self):
        command = [self.s7zip_bin, 't', self.archive_path]
        try:
            raw_output = subprocess.check_output(command)
            encoding_detected = chardet.detect(raw_output)['encoding']
            output = raw_output.decode(encoding_detected)
            self.finished.emit(output)
        except subprocess.CalledProcessError:
            self.finished.emit("Failed to test the archive.")


class ArchiveTester:
    def __init__(self, parent):
        self.parent = parent
        self.s7zip_bin = determine_7zip_binary()

    def test_archive(self, archive_path):
        if archive_path is None:
            return
        self.progress_dialog = QProgressDialog("Testing archive...", "Cancel", 0, 0, self.parent)
        self.progress_dialog.setModal(True)
        self.progress_dialog.show()

        self.worker = TestArchiveWorker(archive_path, self.s7zip_bin)
        self.worker.finished.connect(self.show_test_result)
        self.worker.start()

    def show_test_result(self, output):
        self.progress_dialog.close()

        # Extract the relevant part of the output
        start_index = output.find("Scanning the drive for archives:")
        if start_index != -1:
            output = output[start_index:]

        result_dialog = QDialog(self.parent)
        result_dialog.setWindowTitle("Test Result")

        text_edit = QTextEdit()
        text_edit.setPlainText(output)
        text_edit.setReadOnly(True)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(result_dialog.accept)

        layout = QVBoxLayout()
        layout.addWidget(text_edit)
        layout.addWidget(ok_button)

        result_dialog.setLayout(layout)
        result_dialog.exec()


class AboutDialog(QDialog):
    def __init__(self):
        super(AboutDialog, self).__init__()
        self.setWindowTitle("About 7-Zip Archiver")

        layout = QVBoxLayout()

        image_label = QLabel(self)
        pic_location = resource_path('./pics/7-zip-logo.png')
        pixmap = QPixmap(pic_location)

        scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # Set resized QPixmap
        image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(image_label)

        version_label = QLabel(f"Version: {get_app_version()}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        license_label = QLabel("7-Zip Archiver is Open Source \nunder GNU GPL 3.0")
        license_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(license_label)

        igor_pavlov_label = QLabel("Based on Igor Pavlov's 7zz executable")
        igor_pavlov_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(igor_pavlov_label)

        website_button = QPushButton("Project Website")
        website_button.clicked.connect(lambda: QDesktopServices.openUrl("https://www.7zip-pyqt.com/"))

        copyright_label = QLabel("© MANGO FESTIVAL LLC")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)

        layout.addWidget(website_button)

        self.setLayout(layout)
