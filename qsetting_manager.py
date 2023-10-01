from PySide6.QtCore import QSettings

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.qsettings = QSettings("YourOrganizationName", "YourAppName")

    def get_value(self, key, default=None):
        return self.qsettings.value(key, default)

    def set_value(self, key, value):
        self.qsettings.setValue(key, value)

    def reset(self):
        self.qsettings.clear()