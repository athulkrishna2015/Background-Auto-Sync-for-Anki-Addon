from aqt.qt import QCloseEvent, QDialog, QGridLayout, QTextEdit
from .constants import get_auto_sync_icon


class LogManager:
    def __init__(self):
        self.log = ""
        self.log_dialog = None

    def write(self, line: str):
        """Add a single line to the log"""
        self.log += line + "\n"
        # call the log dialog window to refresh it
        if self.log_dialog:
            try:
                self.log_dialog.refresh_log()
            except RuntimeError:
                self.log_dialog = None

    def read(self):
        """Get all log entries seperated by \\n"""
        return self.log

    def register(self, log_dialog):
        """Register AutoSyncLogDialog instance to listen to log output"""
        self.log_dialog = log_dialog

    def unregister(self, log_dialog):
        """Stop sending updates to the provided dialog instance."""
        if self.log_dialog is log_dialog:
            self.log_dialog = None


class AutoSyncLogDialog(QDialog):
    def __init__(self, log_manager: LogManager, parent):
        super(AutoSyncLogDialog, self).__init__(parent)
        self.log_manager = log_manager
        self._options_dialog = parent

        # set up log TextEdit
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Window layout
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.log_output, 0, 0)

        self.setLayout(grid)
        self.setWindowTitle('Background Auto Sync Log')
        self.setWindowIcon(get_auto_sync_icon())
        self.setMinimumWidth(750)
        self.refresh_log()

        # listen to the log output
        self.log_manager.register(self)

    def refresh_log(self):
        """Refresh the log and scroll the TextEdit to the bottom"""
        self.log_output.setPlainText(self.log_manager.read())
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.log_manager.unregister(self)
        self._options_dialog.on_log_dialog_close()
        super().closeEvent(a0)
