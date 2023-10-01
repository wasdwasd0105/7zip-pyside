import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QSplitter, QWidget, QLineEdit, QMessageBox
from PySide6.QtCore import Qt, QDir, QEvent, QSettings

from menu_bar import MenuBar
from tool_bar import ToolBar
from navigation_pane import NavigationContainer
from main_pane import MainPane

class CustomApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.main_window = None

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FileOpen:
            file_path = event.file()
            if self.main_window:  # Just to be safe
                self.main_window.main_pane.display_archive_contents(file_path)
            return True
        return super().event(event)

class SevenZipGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('7-Zip GUI')
        self.setGeometry(100, 100, 800, 600)

        # Set up Menu Bar and Toolbar
        self.menuBarInstance = MenuBar(self)
        self.setMenuBar(self.menuBarInstance)

        self.addToolBar(ToolBar())

        # Set up Navigation Pane (Left) and Main Pane (Right)
        self.nav_pane = NavigationContainer(self)
        self.main_pane = MainPane()
        self.nav_pane.nav_pane.set_main_pane(self.main_pane)

        # Create a horizontal splitter for adjustable width
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.nav_pane)
        splitter.addWidget(self.main_pane)

        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel

        layout = QVBoxLayout()
        layout.addWidget(splitter)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.show()

if __name__ == '__main__':
    app = CustomApplication(sys.argv)
    window = SevenZipGUI()
    app.main_window = window
    sys.exit(app.exec())
