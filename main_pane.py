import shutil

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QStyle, QProgressDialog, QMenu, QLabel, QWidget, QVBoxLayout, \
    QLineEdit, QMessageBox, QInputDialog, QApplication
from PySide6.QtCore import Qt, QMimeData, QUrl, QThread, Signal, QCoreApplication
from PySide6.QtGui import QIcon, QDrag, QAction
import subprocess
import sys
import os
import tempfile
import SevenZUtils
from extractor import Extractor
from archiver import Archiver
from qsetting_manager import SettingsManager
import chardet


class MainPane(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_inside_path = None
        self.current_folder_label = QLineEdit("     Open archive from the left or Drop archive below")
        self.current_folder_label.setReadOnly(True)

        self.tree_widget = QTreeWidget()

        layout = QVBoxLayout()
        layout.addWidget(self.current_folder_label)
        layout.addWidget(self.tree_widget)

        layout.setSpacing(8)
        layout.setContentsMargins(5, 4, 0, 0)

        self.setLayout(layout)

        self.s7zip_bin = SevenZUtils.determine_7zip_binary()

        # Setup tree columns and reordered headers
        self.tree_widget.setColumnCount(4)  # Merging date & time reduces it to 4 columns
        self.tree_widget.setHeaderLabels(["Name", "Size", "Compressed", "DateTime"])

        # Enable sorting
        self.tree_widget.setSortingEnabled(True)
        self.tree_widget.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Fetch the standard folder icon provided by PyQt
        self.folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self.file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.tree_widget.setColumnWidth(0, int(0.4 * self.width()))

        # set the drag-drop mode
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tree_widget.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)

        # Allow multi-selection
        self.tree_widget.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

        # Connect the itemDoubleClicked signal to the custom slot
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        self.tree_widget.itemSelectionChanged.connect(self.update_folder_label)

        # Create context menu actions
        self.pasteAction = QAction("Paste", self)
        self.pasteAction.triggered.connect(self.paste_from_clipboard)
        self.pasteAction.setEnabled(False)

        self.renameAction = QAction("Rename", self)
        self.renameAction.triggered.connect(self.rename_item)
        self.renameAction.setEnabled(False)

        self.deleteAction = QAction("Delete", self)
        self.deleteAction.triggered.connect(self.delete_item)
        self.deleteAction.setEnabled(False)

        self.openAction = QAction("Open", self)
        self.openAction.triggered.connect(self.on_item_open)
        self.openAction.setEnabled(False)

        self.extractAction = QAction("Extract", self)
        self.extractAction.triggered.connect(self.extract_selected_item)
        self.extractAction.setEnabled(False)

        self.copy_action = QAction("Copy to Clipboard", self)
        self.copy_action.triggered.connect(self.copy_files_to_clipboard)
        self.copy_action.setEnabled(False)

        self.archiver = Archiver(self)

        self.extractor = Extractor(self.parent())
        self.archive_path = None

        self.settings_manager = SettingsManager()


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.copy_files_to_clipboard()
        else:
            super().keyPressEvent(event)

    def get_full_path(self, item):
        """Construct the full path for the given item in the tree view."""
        parts = []
        while item:
            parts.insert(0, item.text(0))
            item = item.parent()
        return '/'.join(parts)

    def format_size(self, size):
        try:
            int(size)
        except:
            return ""

        """Converts bytes to a human-readable string."""
        size = int(size)  # Make sure the size is an integer
        units = ["bytes", "KiB", "MiB", "GiB", "TiB"]

        for unit in units:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TiB"

    def display_archive_contents(self, archive_path):

        chardet_option = self.settings_manager.get_value("chardet_option", False)

        self.archive_path = archive_path
        if self.archive_path is None:
            return

        command = [self.s7zip_bin, 'l', archive_path]
        try:
            raw_output = subprocess.check_output(command)

            if chardet_option:
                output = raw_output.decode('utf-8')
            else:
                encoding_detected = chardet.detect(raw_output)['encoding']
                output = raw_output.decode(encoding_detected)

        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Error",
                                 "Failed to open the archive. It might be corrupted or not a supported archive file.")
            self.close_and_clear()
            return

        # Check the file extension to enable or disable write-related actions
        file_extension = os.path.splitext(archive_path)[1]
        if file_extension.lower() in ['.7z', '.zip']:
            self.pasteAction.setEnabled(True)
            self.renameAction.setEnabled(True)
            self.deleteAction.setEnabled(True)
        else:
            self.pasteAction.setEnabled(False)
            self.renameAction.setEnabled(False)
            self.deleteAction.setEnabled(False)

        self.openAction.setEnabled(True)
        self.extractAction.setEnabled(True)
        self.copy_action.setEnabled(True)

        entries = self.parse_7zip_output(output)

        entries.sort(key=lambda x: (x['name'], 'D' in x['attr']))

        self.archive_path = archive_path
        self.tree_widget.clear()  # Clear existing items

        # Update the QLineEdit to display the current folder
        folder_name = os.path.basename(archive_path)
        self.current_folder_label.setText(f" {folder_name}")

        # Dictionary to keep track of directories and their corresponding QTreeWidgetItems
        dir_dict = {}

        # Dictionary to keep track of orphan files (NEW)
        orphan_files = {}

        for entry in entries:
            parts = entry['name'].split('/')
            current_path = ''
            parent_item = None  # This will be used to keep track of the parent item in the nested structure

            # Create or retrieve directory items for all parts except the last one
            for i, part in enumerate(parts[:-1]):
                current_path = '/'.join(parts[:i + 1])
                if current_path not in dir_dict:
                    item = QTreeWidgetItem([part, '--', '--', ''])
                    item.setIcon(0, self.folder_icon)
                    item.setData(0, Qt.ItemDataRole.UserRole, "D....")
                    if parent_item:
                        parent_item.addChild(item)
                    else:
                        self.tree_widget.addTopLevelItem(item)

                    dir_dict[current_path] = item
                parent_item = dir_dict[current_path]

            # For the current entry (last part), decide whether it's a file or directory
            item_name = parts[-1]
            if 'D' in entry['attr']:
                dir_item = QTreeWidgetItem([item_name, '--', '--', entry['datetime']])
                dir_item.setData(0, Qt.ItemDataRole.UserRole, entry['attr'])
                dir_item.setIcon(0, self.folder_icon)
                if parent_item:
                    parent_item.addChild(dir_item)
                else:
                    self.tree_widget.addTopLevelItem(dir_item)
                dir_dict[entry['name']] = dir_item

                # Check if this directory has any orphan files (NEW)
                if entry['name'] in orphan_files:
                    for orphan in orphan_files[entry['name']]:
                        dir_item.addChild(orphan)
                    del orphan_files[entry['name']]
            else:
                size = self.format_size(entry['size'])
                compressed = self.format_size(entry['compressed'])
                file_item = QTreeWidgetItem([item_name, size, compressed, entry['datetime']])
                file_item.setData(0, Qt.ItemDataRole.UserRole, entry['attr'])  # Set the 'attr'
                file_item.setIcon(0, self.file_icon)  # Setting the file icon
                if parent_item:
                    parent_item.addChild(file_item)
                else:
                    self.tree_widget.addTopLevelItem(file_item)

                # If parent_item is None, this is an orphan file (NEW)
                if parent_item is None:
                    parent_path = '/'.join(parts[:-1])
                    if parent_path not in orphan_files:
                        orphan_files[parent_path] = []
                    orphan_files[parent_path].append(file_item)

    def parse_7zip_output(self, output):
        lines = output.strip().split('\n')

        # Extract lines between dashes, which contain file/folder info
        start_index = None
        end_index = None
        for idx, line in enumerate(lines):
            if "-----------" in line:
                if start_index is None:
                    start_index = idx
                else:
                    end_index = idx
                    break

        # Extract column indices based on the first dashed line
        dash_line = lines[start_index]
        date_time_end = dash_line.find(" ")
        attr_start = date_time_end + 1
        attr_end = attr_start + dash_line[attr_start:].find(" ")
        size_start = attr_end + 1
        size_end = size_start + dash_line[size_start:].find(" ")
        compressed_start = size_end + 1
        compressed_end = compressed_start + dash_line[compressed_start:].find(" ")
        name_start = compressed_end + 2  # 2 spaces before the name column

        content_lines = lines[start_index + 1:end_index]
        entries = []
        for line in content_lines:
            date_time = line[:date_time_end].strip()
            attr = line[attr_start:attr_end].strip()
            size = line[size_start:size_end].strip()
            compressed = line[compressed_start:compressed_end].strip()
            name = line[name_start:].strip()

            # for directories, set size and compressed to "--"
            if 'D' in attr:
                size = "--"
                compressed = "--"

            entry = {
                "datetime": date_time,
                "attr": attr,
                "size": size,
                "compressed": compressed,
                "name": name
            }
            entries.append(entry)

        return entries

    def current_archive_path(self):
        return self.archive_path

    def get_selected_items(self):
        """Returns a list of full file paths of the selected items."""
        selected_items = self.tree_widget.selectedItems()
        return [self.get_full_path(item) for item in selected_items]

    def is_file_item(self, item):
        # Your code to determine whether the item is a file or folder
        # For example, you could use the 'attr' value you've stored in the QTreeWidgetItem
        attr = item.data(0, Qt.ItemDataRole.UserRole)
        if attr is None:
            return False
        return 'D' not in attr

    def on_item_double_clicked(self, item, column):
        file_path = self.get_full_path(item)
        is_file = self.is_file_item(item)

        if is_file and file_path:  # Check if the path is not empty and the item is a file
            self.extract_and_open_file(file_path)

    def on_item_open(self):
        selected_items = self.tree_widget.selectedItems()
        if len(selected_items) == 0:
            return
        file_path = self.get_full_path(selected_items[0])
        is_file = self.is_file_item(selected_items[0])

        if is_file and file_path:  # Check if the path is not empty and the item is a file
            self.extract_and_open_file(file_path)

    def extract_and_open_file(self, file_path):
        self.extractor.extract_and_open_double_click_file(self.archive_path, file_path)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)

        # Add actions to context menu
        context_menu.addAction(self.openAction)
        context_menu.addAction(self.extractAction)
        context_menu.addAction(self.copy_action)

        # Add a separator line
        context_menu.addSeparator()

        context_menu.addAction(self.pasteAction)
        context_menu.addAction(self.renameAction)
        context_menu.addAction(self.deleteAction)

        context_menu.exec(event.globalPos())

    def copy_files_to_clipboard(self):
        self.extractor.extract_and_copy_files_to_clipboard(self.archive_path, self.get_selected_items())
        # print(self.get_selected_items())

    def extract_selected_item(self):
        file_path = self.current_archive_path()
        selected_items = self.get_selected_items()
        self.extractor.extract_from_main_pane(file_path, selected_items)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def dropEvent(self, event):
        file_paths = []
        for url in event.mimeData().urls():
            file_paths.append(url.toLocalFile())

        print(f"Dropped files: {file_paths}")

        # Check if self.archive_path is None
        if self.archive_path is None:
            # Check if multiple files are being dropped
            if len(file_paths) > 1:
                QMessageBox.warning(self, "Warning", "You can only open one archive at a time.")
            else:
                # Call display_archive_contents for the single dropped file
                self.display_archive_contents(file_paths[0])
        else:
            # Your existing logic for handling drops when an archive is already open
            print(self.current_inside_path)
            self.archiver.confirm_add_files(self.archive_path, file_paths, self.current_inside_path)
            pass

    def close_and_clear(self):
        self.pasteAction.setEnabled(False)
        self.renameAction.setEnabled(False)
        self.deleteAction.setEnabled(False)
        self.openAction.setEnabled(False)
        self.extractAction.setEnabled(False)
        self.copy_action.setEnabled(False)

        self.tree_widget.clear()  # Clear all items from the QTreeWidget
        self.archive_path = None  # Reset the archive path
        self.current_folder_label.setText("     Open archive from the left or Drop archive below")

    def update_folder_label(self):
        selected_items = self.tree_widget.selectedItems()
        # Extract ZIP filename from self.archive_path
        zip_filename = os.path.basename(self.archive_path)

        if selected_items:  # Check if any item is selected
            item = selected_items[0]  # Get the first selected item
            attr = item.data(0, Qt.ItemDataRole.UserRole)
            if 'D' in attr:  # Check if the item is a directory
                folder_name = self.get_full_path(item)
            else:  # It's a file
                folder_name = os.path.dirname(self.get_full_path(item))

            if folder_name == '':
                self.current_folder_label.setText(f" {zip_filename}")
            else:
                self.current_folder_label.setText(f" {zip_filename}/{folder_name}")

            self.current_inside_path = folder_name

        else:
            self.current_folder_label.setText(f" {zip_filename}")
            self.current_inside_path = None

    def reload_archive(self):
        self.display_archive_contents(self.archive_path)

    def paste_from_clipboard(self):
        # Get file paths from clipboard
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasFormat("text/uri-list"):
            # Extract file paths from the URLs
            file_paths = [url.toLocalFile() for url in mime_data.urls()]
            print(file_paths)
            self.archiver.confirm_add_files(self.archive_path, file_paths, self.current_inside_path)

    def rename_item(self):
        item = self.tree_widget.currentItem()
        item_full_path = self.get_full_path(item)
        if item:
            old_name = item.text(0)
            new_name, ok = QInputDialog.getText(self, 'Rename File', 'Enter new name:', text=old_name)

            if ok and new_name:
                # Perform the renaming operation using 7z command
                if self.archive_path:
                    # Extract the directory of the old file
                    old_file_dir = os.path.dirname(item_full_path)

                    # Create the new full path
                    new_full_path = os.path.join(old_file_dir, new_name) if old_file_dir else new_name

                    # Run the 7z command to rename the file
                    command = [self.s7zip_bin, 'rn', self.archive_path, item_full_path, new_full_path]
                    try:
                        subprocess.check_call(command)
                        # Update the item's text and full path in the tree widget
                        item.setText(0, new_name)
                    except subprocess.CalledProcessError:
                        QMessageBox.critical(self, "Error", "Failed to rename the file.")
        self.reload_archive()

    def delete_item(self):
        item = self.tree_widget.currentItem()
        item_full_path = self.get_full_path(item)
        if item:
            # Show a confirmation dialog
            reply = QMessageBox.question(self, 'Delete File',
                                         f'Are you sure you want to delete {item_full_path}?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                # Show a progress dialog
                self.progress_dialog = QProgressDialog("Deleting...", "Cancel", 0, 0, self)
                self.progress_dialog.setCancelButton(None)  # Disable the cancel button
                self.progress_dialog.setModal(True)
                self.progress_dialog.show()

                # Create a worker thread for the delete operation
                self.delete_worker = SevenZUtils.DeleteWorker(self.s7zip_bin, self.archive_path, item_full_path)
                self.delete_worker.finished.connect(self.on_delete_finished)
                self.delete_worker.start()

    def on_delete_finished(self, success, message):
        self.progress_dialog.close()  # Close the progress dialog
        if success:
            # Remove the item from the tree widget
            item = self.tree_widget.currentItem()
            root = self.tree_widget.invisibleRootItem()
            (item.parent() or root).removeChild(item)
        else:
            QMessageBox.critical(self, "Error", message)

        self.reload_archive()
