import os
import shutil
import sys
import subprocess
from PySide6.QtWidgets import QTreeView, QMenu, QTreeWidget, QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, QPushButton, \
    QStyle, QFileDialog, QMessageBox
from PySide6.QtCore import QDir, QPoint, QFileInfo, QMimeData, QSettings, QFile
from PySide6.QtWidgets import QFileSystemModel

from PySide6.QtGui import QAction
import SevenZUtils
from archiver import Archiver
from qsetting_manager import SettingsManager
from SevenZHelperMacOS import create_bookmark, resolve_bookmark



class NavigationContainer(QWidget):
    def __init__(self, parent_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.parent_instance = parent_instance

        self.settings_manager = SettingsManager()
        self.workspace_history = self.settings_manager.get_value("workspace_history", [])

        # Create the NavigationPane (tree view)
        self.nav_pane = NavigationPane()

        # Create a QLineEdit to show the current path
        self.path_line_edit = QLineEdit()
        self.path_line_edit.setReadOnly(True)
        self.path_line_edit.setText("Please Choose Workspace")

        # Create a button with a folder icon
        self.folder_button = QPushButton(self)
        self.folder_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.folder_button.clicked.connect(self.open_folder_selector)

        # Adjust the layout to include the button and line edit
        path_layout = QHBoxLayout()
        path_layout.setSpacing(3)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.folder_button)
        path_layout.addWidget(self.path_line_edit)

        # Set up the main layout
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.addLayout(path_layout)
        layout.addWidget(self.nav_pane)
        self.setLayout(layout)

        # Connect signal to update the QLineEdit
        self.nav_pane.selectionModel().currentChanged.connect(self.update_path_line_edit)

    def update_path_line_edit(self, current, previous):
        index = self.nav_pane.currentIndex()
        if index.isValid():
            file_path = self.nav_pane.model().filePath(index)
            self.path_line_edit.setText(file_path)

    def open_folder_selector(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", QDir.homePath())
        if folder_path:
            self.path_line_edit.setText(folder_path)
            # Update the navigation pane's root path
            self.nav_pane.setRootPath(folder_path)
            history = self.settings_manager.get_value("workspace_history", [])

            bookmark = None
            if os.environ.get("APP_SANDBOX_CONTAINER_ID"):
                bookmark = create_bookmark(folder_path)

            # Store paths as (path, bookmark) tuples if bookmark exists, otherwise just as paths
            history_entry = (folder_path, bookmark) if bookmark else folder_path

            if history_entry not in history:
                history.insert(0, history_entry)
                if len(history) > 5:  # Limit to 5 recent workspaces
                    history.pop()
                self.settings_manager.set_value("workspace_history", history)
            self.parent_instance.menuBarInstance.update_menu_bar()

            # Just for testing, remove in final code
            if bookmark:
                res1 = resolve_bookmark(bookmark)
                print(res1)

    def compress_files(self):
        return self.nav_pane.compress_files()

    def hasFocus(self) -> bool:
        return self.nav_pane.hasFocus()

    def get_current_selected_file(self):
        return self.nav_pane.get_current_selected_file()

    def get_current_selected_files(self):
        return self.nav_pane.get_current_selected_files()


    def clean_navigation_pane(self):
        self.path_line_edit.setText("Please Choose Workspace")
        model = QFileSystemModel()
        self.nav_pane.setModel(model)

    def open_workspace_folder(self, display_path, real_path):
        if os.path.isdir(real_path):
            self.path_line_edit.setText(display_path)
            self.nav_pane.setRootPath(real_path)
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("The path is not a folder or does not exist.")
            msg.setWindowTitle("Warning")
            msg.exec()


class NavigationPane(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.archiver = None
        self.main_pane = None
        self.setAcceptDrops(True)

        self.settings_manager = SettingsManager()
        self.workspace_history = self.settings_manager.get_value("workspace_history", [])

        model = QFileSystemModel()
        self.setModel(model)

        #recent_workspace = self.workspace_history[0] if self.workspace_history else None

        self.doubleClicked.connect(self.handle_file_open)
        self.setColumnWidth(0, int(0.3 * self.width()))
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

    def set_main_pane(self, main_pane):

        self.main_pane = main_pane

    def handle_file_open(self, index):
        # Get the full path of the clicked item
        file_path = self.model().filePath(index)

        # List of supported extensions
        supported_extensions = SevenZUtils.get_supported_extensions()

        # Check if it's a valid archive
        if file_path.endswith(supported_extensions):
            self.main_pane.display_archive_contents(file_path)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)

        compress_action = context_menu.addAction("Add to archive...")
        compress_action.triggered.connect(self.compress_files)

        open_action = context_menu.addAction("Open as Archive")
        open_action.triggered.connect(self.open_item)

        context_menu.addSeparator()

        reveal_in_finder_action = QAction("Reveal in Finder")
        reveal_in_finder_action.triggered.connect(self.reveal_in_finder)
        context_menu.addAction(reveal_in_finder_action)

        properties_action = context_menu.addAction("Properties")
        properties_action.triggered.connect(self.show_properties)

        # Show the context menu at the position of the mouse cursor
        context_menu.exec(self.mapToGlobal(event.pos()))

    def open_item(self):
        # Get the selected index from the tree view
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        index = selected_indexes[0]

        # Call handle_file_open with the selected index
        self.handle_file_open(index)

    def show_properties(self):
        # Get the path of the selected item in the tree view
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        file_path = self.model().filePath(selected_indexes[0])
        SevenZUtils.show_file_properties(file_path)

    def reveal_in_finder(self):

        # Get the path of the selected item in the tree view
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        file_path = self.model().filePath(selected_indexes[0])

        # Platform-specific commands to reveal in finder/file explorer
        if sys.platform == "win32":
            # Windows
            subprocess.Popen(["explorer", "/select,", file_path])
        elif sys.platform == "darwin":
            # macOS
            subprocess.Popen(["open", "-R", file_path])
        elif sys.platform.startswith("linux"):
            # Linux (assuming Nautilus is the file manager)
            subprocess.Popen(["nautilus", file_path])

    def get_current_selected_file(self):
        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            return self.model().filePath(selected_indexes[0])
        return None

    def get_current_selected_files(self):
        selected_files = set()  # Using a set to automatically remove duplicates
        selected_indexes = self.selectedIndexes()
        for index in selected_indexes:
            selected_files.add(self.model().filePath(index))
        return list(selected_files)

    def compress_files(self):
        self.archiver = Archiver(self)
        file_list = self.get_current_selected_files()
        if file_list:
            self.archiver.archive_file_by_archive_options(self.get_current_selected_files())

    def setRootPath(self, path):
        self.model().setRootPath(path)
        self.setRootIndex(self.model().index(path))
