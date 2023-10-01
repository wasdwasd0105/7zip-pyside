from PySide6.QtWidgets import QToolBar, QStyle, QMessageBox, QWidget, QSizePolicy
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from extractor import Extractor
from SevenZUtils import ArchiveTester, show_file_properties


class ToolBar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set the button style to have text under the icon
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        # Add Action
        self.add_action = QAction("Add", self)
        self.add_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        self.addAction(self.add_action)
        self.add_action.triggered.connect(self.handle_add_action)

        # Extract Action
        self.extract_action = QAction("Extract", self)
        self.extract_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.addAction(self.extract_action)
        self.extract_action.triggered.connect(self.handle_extract)

        # Test Action
        self.test_action = QAction("Test", self)
        self.test_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.addAction(self.test_action)
        self.test_action.triggered.connect(self.handle_file_test)

        # Info Action
        self.info_action = QAction("Info", self)
        self.info_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.addAction(self.info_action)
        self.info_action.triggered.connect(self.handle_info_action)

        # Create a QWidget to act as a spacer and set its size policy
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.addWidget(spacer)  # Add spacer

        self.addSeparator()

        # Create Close Archive Action
        self.close_archive_action = QAction("Close Archive", self)
        self.close_archive_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.addAction(self.close_archive_action)  # Add action after the spacer
        self.close_archive_action.triggered.connect(self.handle_close_archive)

        self.extractor = Extractor(self.parent())
        self.archive_tester = ArchiveTester(self.parent())

    def handle_extract(self):
        # Check which pane is active
        if self.parent().nav_pane.hasFocus():
            # Get the currently selected file from the navigation pane
            file_path = self.parent().nav_pane.get_current_selected_file()
            if file_path:
                self.extractor.extract_from_navigation_pane(file_path)
            else:
                QMessageBox.warning(self.parent(), "Warning", "Please select a file to extract.")

        elif self.parent().main_pane.tree_widget.hasFocus():
            # For now, we'll just extract the whole archive. Later, we can enhance this to handle selected items.
            file_path = self.parent().main_pane.current_archive_path()
            selected_items = self.parent().main_pane.get_selected_items()
            if file_path is None:
                return
            self.extractor.extract_from_main_pane(file_path, selected_items)

    def handle_close_archive(self):
        # Add code to handle closing the archive
        self.parent().main_pane.close_and_clear()

    def handle_info_action(self):
        file_path = None

        if self.parent().nav_pane.hasFocus():
            # Get the currently selected file from the navigation pane
            file_path = self.parent().nav_pane.get_current_selected_file()

        if self.parent().main_pane.tree_widget.hasFocus():
            file_path = self.parent().main_pane.current_archive_path()

        if file_path is not None:
            show_file_properties(file_path)

    def handle_file_test(self):
        if self.parent().nav_pane.hasFocus():

            # Get the currently selected file from the navigation pane
            file_path = self.parent().nav_pane.get_current_selected_file()
            if file_path:
                self.archive_tester.test_archive(file_path)
            else:
                QMessageBox.warning(self.parent(), "Warning", "Please select a file to test.")

        if self.parent().main_pane.tree_widget.hasFocus():
            file_path = self.parent().main_pane.current_archive_path()
            self.archive_tester.test_archive(file_path)

    def handle_add_action(self):
        if self.parent().nav_pane.hasFocus():
            self.parent().nav_pane.compress_files()
        else:
            QMessageBox.information(self, "Info",
                                    "Please select files on left panel to compress files.")
