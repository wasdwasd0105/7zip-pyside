import os
import sys

from PySide6.QtWidgets import QMenuBar, QMenu, QFileDialog, QMessageBox
from PySide6.QtGui import QAction
from qsetting_manager import SettingsManager
from SevenZHelperMacOS import create_bookmark, resolve_bookmark, start_accessing_resource, stop_accessing_resource


class MenuBar(QMenuBar):
    MAX_HISTORY_COUNT = 5

    def __init__(self, window):
        super().__init__()
        self.current_sandbox_bookmark = None
        self.window = window
        self.settings_manager = SettingsManager()
        self.workspace_history = self.settings_manager.get_value("workspace_history", [])
        self.create_menu()

    def create_menu(self):

        self.clear()

        # Workspace Menu
        workspace_menu = QMenu("Workspace", self)

        close_workspace = QAction("Close Workspace", self.window)
        workspace_menu.addAction(close_workspace)
        close_workspace.triggered.connect(lambda: self.close_workspace_action())

        workspace_menu.addSeparator()

        for entry in self.workspace_history:
            if self.is_sandboxed() and isinstance(entry, tuple) and len(entry) == 2:
                display_path, bookmark = entry
                real_path = resolve_bookmark(bookmark)

            else:
                bookmark = None
                display_path = real_path = entry  # In non-sandboxed environment, or if entry isn't tuple.

            action = QAction(display_path, self.window)
            action.triggered.connect(
                lambda _, d_path=display_path, r_path=real_path, b_path=bookmark: self.open_workspace(d_path, r_path,
                                                                                                      b_path))
            workspace_menu.addAction(action)

        workspace_menu.addSeparator()

        clean_all_workspace = QAction("Clean All Workspace History", self.window)
        workspace_menu.addAction(clean_all_workspace)
        clean_all_workspace.triggered.connect(lambda: self.clean_all_workspace_action())

        self.addMenu(workspace_menu)

        # File Menu
        file_menu = QMenu("Archive", self)

        open_archive_action = QAction("Open Archive", self.window)
        file_menu.addAction(open_archive_action)
        open_archive_action.triggered.connect(lambda: self.open_archive())

        close_archive_action = QAction("Close Archive", self.window)
        file_menu.addAction(close_archive_action)
        close_archive_action.triggered.connect(lambda: self.close_archive())

        self.addMenu(file_menu)

        settings_menu = QMenu("Settings", self)

        if self.get_chardet_option():
            chardet_option_text = "✔️ Use non-Unicode Encoder"
        else:
            chardet_option_text = "Use non-Unicode Encoder"

        use_chardet_option = QAction(chardet_option_text, self.window)
        settings_menu.addAction(use_chardet_option)
        use_chardet_option.triggered.connect(lambda: self.toggle_chardet())

        reset_option = QAction("Reset to default", self.window)
        settings_menu.addAction(reset_option)
        reset_option.triggered.connect(lambda: self.toggle_reset())

        about_action = QAction("About", self.window)
        settings_menu.addAction(about_action)


        self.addMenu(settings_menu)

    def open_archive(self):
        file_name, _ = QFileDialog.getOpenFileName(self.window, "Open Archive File", "",
                                                   "All Files (*)")
        if file_name:
            self.window.main_pane.display_archive_contents(file_name)

    def close_archive(self):
        self.window.main_pane.close_and_clear()

    def clean_all_workspace_action(self):
        self.settings_manager.set_value("workspace_history", [])
        self.update_menu_bar()

    def close_workspace_action(self):
        self.close_sandbox_resource()
        self.window.nav_pane.clean_navigation_pane()

    def open_workspace(self, display_path, real_path, bookmark):

        if self.is_sandboxed() and bookmark:
            res = start_accessing_resource(bookmark)
            if res is not True:
                QMessageBox.warning(self, "Error", "Failed to open the history. Please reopen the folder")
                self.clean_all_workspace_action()
                return
            self.current_sandbox_bookmark = bookmark

        self.window.nav_pane.clean_navigation_pane()
        self.window.nav_pane.open_workspace_folder(display_path, real_path)
        #print(real_path)

    def update_menu_bar(self):
        self.workspace_history = self.settings_manager.get_value("workspace_history", [])
        self.create_menu()

    def is_sandboxed(self):
        return sys.platform == "darwin" and os.environ.get("APP_SANDBOX_CONTAINER_ID") is not None

    def close_sandbox_resource(self):
        if self.is_sandboxed and self.current_sandbox_bookmark is not None:
            stop_accessing_resource(self.current_sandbox_bookmark)
            self.current_sandbox_bookmark = None

    def get_chardet_option(self):
        return self.settings_manager.get_value("chardet_option", False)

    def set_chardet_option(self, option):
        self.settings_manager.set_value("chardet_option", option)

    def toggle_chardet(self):
        option = self.get_chardet_option()
        new_option = not option
        self.set_chardet_option(new_option)
        self.update_menu_bar()
        self.window.main_pane.reload_archive()

    def toggle_reset(self):
        reply = QMessageBox.question(None, 'Reset to Default', 'Do you want to reset to default?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.reset()
            sys.exit()