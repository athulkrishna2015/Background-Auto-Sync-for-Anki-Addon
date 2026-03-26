from aqt.qt import (
    QCheckBox,
    QCloseEvent,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    Qt,
)
from .sync_routine import SyncRoutine
from .config import AutoSyncConfigManager
from .constants import (
    CONFIG_IDLE_BEFORE_SYNC,
    CONFIG_IDLE_SYNC_TIMEOUT,
    CONFIG_STRICTLY_AVOID_INTERRUPTIONS,
    CONFIG_SYNC_ON_CHANGE_ONLY,
    CONFIG_SYNC_TIMEOUT,
    get_auto_sync_icon,
)
from .log_window import AutoSyncLogDialog, LogManager
from .support_dialog import SupportDialog


class AutoSyncOptionsDialog(QDialog):
    def __init__(self, config: AutoSyncConfigManager, sync_routine: SyncRoutine, log_manager: LogManager):
        super(AutoSyncOptionsDialog, self).__init__()
        self.config = config
        self.sync_routine: SyncRoutine = sync_routine
        self.log_manager = log_manager

        self.log_dialog_instance = None

        # set up UI elements
        self.sync_timeout_spinbox = QSpinBox()
        self.idle_sync_timeout_spinbox = QSpinBox()
        self.sync_on_change_only_checkbox = QCheckBox()
        self.idle_before_sync_spinbox = QSpinBox()

        self.setup_ui()

    @staticmethod
    def _set_minutes_suffix(spinbox: QSpinBox, value: int):
        if value == 0:
            spinbox.setSuffix("")
        else:
            spinbox.setSuffix(" minute" if value == 1 else " minutes")

    def change_sync_timeout(self, value):
        self._set_minutes_suffix(self.sync_timeout_spinbox, value)
        self.config.set(CONFIG_SYNC_TIMEOUT, value)
        self.sync_routine.reload_config()

    def change_idle_sync_timeout(self, value):
        self._set_minutes_suffix(self.idle_sync_timeout_spinbox, value)
        self.config.set(CONFIG_IDLE_SYNC_TIMEOUT, value)
        self.sync_routine.reload_config()

    def change_strictly_avoid_interruption(self, enabled):
        self.config.set(CONFIG_STRICTLY_AVOID_INTERRUPTIONS, bool(enabled))
        self.sync_routine.reload_config()

    def change_sync_on_change_only(self, enabled):
        self.config.set(CONFIG_SYNC_ON_CHANGE_ONLY, bool(enabled))
        self.sync_routine.reload_config()
        # Enable/disable the idle-before-sync spinbox based on this
        self.idle_before_sync_spinbox.setEnabled(bool(enabled))

    def change_idle_before_sync(self, value):
        self._set_minutes_suffix(self.idle_before_sync_spinbox, value)
        self.config.set(CONFIG_IDLE_BEFORE_SYNC, value)
        self.sync_routine.reload_config()

    def setup_ui(self):
        self.setWindowTitle('Auto Sync Options')
        self.setWindowIcon(get_auto_sync_icon())
        self.setMaximumWidth(550)
        self.setMaximumHeight(300)

        # "Sync after" option

        sync_timeout_label = QLabel('Sync after')
        sync_timeout_label.setToolTip('How many minutes after you have last interacted with Anki the program will wait to start the sync')
        self.sync_timeout_spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.sync_timeout_spinbox.setMinimum(1)

        self.sync_timeout_spinbox.setValue(self.config.get(CONFIG_SYNC_TIMEOUT))
        self._set_minutes_suffix(self.sync_timeout_spinbox, self.sync_timeout_spinbox.value())
        self.sync_timeout_spinbox.setToolTip('How many minutes after you have last interacted with Anki the program will wait to start the sync')
        self.sync_timeout_spinbox.valueChanged.connect(self.change_sync_timeout)

        # "Idle Sync after" option

        idle_sync_timeout_label = QLabel('When the program is idle, sync every')
        idle_sync_timeout_label.setToolTip('While you are not using Anki, the program will keep syncing in the background (in case you are using Anki on mobile or web and there are changes to sync)')
        self.idle_sync_timeout_spinbox.setMinimum(0)
        self.idle_sync_timeout_spinbox.setSpecialValueText("Off")
        self.idle_sync_timeout_spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.idle_sync_timeout_spinbox.setValue(self.config.get(CONFIG_IDLE_SYNC_TIMEOUT))
        self._set_minutes_suffix(self.idle_sync_timeout_spinbox, self.idle_sync_timeout_spinbox.value())
        self.idle_sync_timeout_spinbox.setToolTip('While you are not using Anki, the program will keep syncing in the background (in case you are using Anki on mobile or web and there are changes to sync)')
        self.idle_sync_timeout_spinbox.valueChanged.connect(self.change_idle_sync_timeout)

        # "Strictly avoid interruptions" checkbox

        strictly_avoid_interruptions_label = QLabel("Strictly avoid interruptions (recommended)")
        strictly_avoid_interruptions_label.setToolTip("Will not auto sync if cards are being reviewed, the card browser or similar windows are open <br>or the main window has focus (isn't minimized or in the background)")
        strictly_avoid_interruptions_checkbox = QCheckBox()
        strictly_avoid_interruptions_checkbox.setToolTip("Will not auto sync if cards are being reviewed, the card browser or similar windows are open <br>or the main window has focus (isn't minimized or in the background)")
        strictly_avoid_interruptions_checkbox.setChecked(self.config.get(CONFIG_STRICTLY_AVOID_INTERRUPTIONS))
        strictly_avoid_interruptions_checkbox.toggled.connect(self.change_strictly_avoid_interruption)
        strictly_avoid_interruptions_label.mouseReleaseEvent = lambda *args: strictly_avoid_interruptions_checkbox.toggle()

        # "Only sync when changes detected" checkbox

        sync_on_change_only_label = QLabel("Only sync when changes are detected")
        sync_on_change_only_tooltip = (
            "When enabled, the addon will only sync when the collection has been modified "
            "(e.g. cards added, reviewed, edited).<br>"
            "Idle periodic syncs will be skipped if no changes are detected, "
            "reducing unnecessary network traffic."
        )
        sync_on_change_only_label.setToolTip(sync_on_change_only_tooltip)
        self.sync_on_change_only_checkbox = QCheckBox()
        self.sync_on_change_only_checkbox.setToolTip(sync_on_change_only_tooltip)
        self.sync_on_change_only_checkbox.setChecked(self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))
        self.sync_on_change_only_checkbox.toggled.connect(self.change_sync_on_change_only)
        sync_on_change_only_label.mouseReleaseEvent = lambda *args: self.sync_on_change_only_checkbox.toggle()

        # "Idle before sync after change" spinbox

        idle_before_sync_label = QLabel("After a change, wait idle before syncing")
        idle_before_sync_tooltip = (
            "When a change is detected, wait this many minutes of user inactivity "
            "before triggering a sync.<br>"
            "This prevents syncing in the middle of an editing session."
        )
        idle_before_sync_label.setToolTip(idle_before_sync_tooltip)
        self.idle_before_sync_spinbox.setMinimum(1)
        self.idle_before_sync_spinbox.setMaximum(60)
        self.idle_before_sync_spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.idle_before_sync_spinbox.setValue(self.config.get(CONFIG_IDLE_BEFORE_SYNC))
        self._set_minutes_suffix(self.idle_before_sync_spinbox, self.idle_before_sync_spinbox.value())
        self.idle_before_sync_spinbox.setToolTip(idle_before_sync_tooltip)
        self.idle_before_sync_spinbox.valueChanged.connect(self.change_idle_before_sync)
        self.idle_before_sync_spinbox.setEnabled(self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))

        # Show log button
        open_log_button = QPushButton()

        open_log_button.setText("Show log ...")
        open_log_button.clicked.connect(lambda *args: self.on_log_dialog_call())
        open_log_button.setMaximumWidth(100)

        # Support button
        support_button = QPushButton()
        support_button.setText("Support")
        support_button.clicked.connect(lambda *args: self.on_support_dialog_call())
        support_button.setMaximumWidth(100)

        # Close button

        close_button = QPushButton()
        close_button.setText("Close")
        close_button.clicked.connect(lambda *args: self.close())

        # Set up layout

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(sync_timeout_label, 0, 0)
        grid.addWidget(self.sync_timeout_spinbox, 0, 1)

        grid.addWidget(idle_sync_timeout_label, 1, 0)
        grid.addWidget(self.idle_sync_timeout_spinbox, 1, 1)

        grid.addWidget(strictly_avoid_interruptions_label, 2, 0)
        grid.addWidget(strictly_avoid_interruptions_checkbox, 2, 1)

        grid.addWidget(sync_on_change_only_label, 3, 0)
        grid.addWidget(self.sync_on_change_only_checkbox, 3, 1)

        grid.addWidget(idle_before_sync_label, 4, 0)
        grid.addWidget(self.idle_before_sync_spinbox, 4, 1)

        grid.addWidget(open_log_button, 6, 0)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(support_button)
        btn_layout.addWidget(close_button)
        grid.addLayout(btn_layout, 6, 1)

        self.setLayout(grid)

    def on_log_dialog_call(self):
        """Bring the log window to the foreground if one is open, else open a new one """
        if self.log_dialog_instance:
            self.log_dialog_instance.raise_()
            self.log_dialog_instance.activateWindow()
            return
        dialog = AutoSyncLogDialog(self.log_manager, self)
        self.log_dialog_instance = dialog
        dialog.exec()

    def on_log_dialog_close(self):
        self.log_dialog_instance = None

    def on_support_dialog_call(self):
        dialog = SupportDialog(self)
        dialog.exec()

    def closeEvent(self, a0: QCloseEvent) -> None:
        if self.log_dialog_instance:
            self.log_dialog_instance.close()
        super().closeEvent(a0)


def on_options_call(conf, sync_routine, log_manager):
    """Open settings dialog"""
    dialog = AutoSyncOptionsDialog(conf, sync_routine, log_manager)
    dialog.exec()
