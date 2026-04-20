import os

from aqt.qt import (
    QApplication,
    QCheckBox,
    QCloseEvent,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.webview import AnkiWebView
from aqt.utils import openLink

from .sync_routine import SyncRoutine
from .config import AutoSyncConfigManager
from .constants import (
    CONFIG_IDLE_BEFORE_SYNC,
    CONFIG_IDLE_SYNC_TIMEOUT,
    CONFIG_STRICTLY_AVOID_INTERRUPTIONS,
    CONFIG_SYNC_ON_CHANGE_ONLY,
    CONFIG_SYNC_TIMEOUT,
    CONFIG_DISABLE_INTERNET_CHECK,
    get_auto_sync_icon,
)
from .log_window import LogManager


class AutoSyncOptionsDialog(QDialog):
    def __init__(self, config: AutoSyncConfigManager, sync_routine: SyncRoutine, log_manager: LogManager):
        super(AutoSyncOptionsDialog, self).__init__()
        self.config = config
        self.sync_routine: SyncRoutine = sync_routine
        self.log_manager = log_manager

        self.kofi_widget = None
        self.log_output = None

        # set up UI elements
        self.sync_timeout_spinbox = QSpinBox()
        self.idle_sync_timeout_spinbox = QSpinBox()
        self.sync_on_change_only_checkbox = QCheckBox()
        self.idle_before_sync_spinbox = QSpinBox()
        self.strictly_avoid_interruptions_checkbox = QCheckBox()
        self.disable_internet_check_checkbox = QCheckBox()

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
        # Enable/disable the relevant spinboxes based on this
        self.idle_before_sync_spinbox.setEnabled(bool(enabled))
        self.sync_timeout_spinbox.setEnabled(not bool(enabled))
        self.idle_sync_timeout_spinbox.setEnabled(not bool(enabled))

    def change_idle_before_sync(self, value):
        self._set_minutes_suffix(self.idle_before_sync_spinbox, value)
        self.config.set(CONFIG_IDLE_BEFORE_SYNC, value)
        self.sync_routine.reload_config()

    def change_disable_internet_check(self, enabled):
        self.config.set(CONFIG_DISABLE_INTERNET_CHECK, bool(enabled))
        self.sync_routine.reload_config()

    def setup_ui(self):
        self.setWindowTitle('Auto Sync Options')
        self.setWindowIcon(get_auto_sync_icon())
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        # Main layout with tab widget
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # --- Settings Tab ---
        settings_tab = QWidget()
        tab_widget.addTab(settings_tab, "Settings")
        self._setup_settings_tab(settings_tab)

        # --- Support Tab ---
        support_tab = QWidget()
        tab_widget.addTab(support_tab, "Support")
        self._setup_support_tab(support_tab)

        # --- Bottom buttons (shared across tabs) ---
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 0, 0)

        close_button = QPushButton("Close")
        close_button.clicked.connect(lambda *args: self.close())

        btn_layout.addStretch()
        btn_layout.addWidget(close_button)
        main_layout.addLayout(btn_layout)

    def _setup_settings_tab(self, parent: QWidget):
        """Build the settings controls inside the given parent widget."""

        # "Sync after" option
        sync_timeout_label = QLabel('Sync after')
        sync_timeout_label.setToolTip('How many minutes after you have last interacted with Anki the program will wait to start the sync')
        self.sync_timeout_spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.sync_timeout_spinbox.setMinimum(1)
        self.sync_timeout_spinbox.setValue(self.config.get(CONFIG_SYNC_TIMEOUT))
        self._set_minutes_suffix(self.sync_timeout_spinbox, self.sync_timeout_spinbox.value())
        self.sync_timeout_spinbox.setToolTip('How many minutes after you have last interacted with Anki the program will wait to start the sync')
        self.sync_timeout_spinbox.valueChanged.connect(self.change_sync_timeout)
        self.sync_timeout_spinbox.setEnabled(not self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))

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
        self.idle_sync_timeout_spinbox.setEnabled(not self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))

        # "Strictly avoid interruptions" checkbox
        strictly_avoid_interruptions_label = QLabel("Strictly avoid interruptions (recommended)")
        strictly_avoid_interruptions_label.setToolTip("Will not auto sync if cards are being reviewed, the card browser or similar windows are open <br>or the main window has focus (isn't minimized or in the background)")
        self.strictly_avoid_interruptions_checkbox.setToolTip("Will not auto sync if cards are being reviewed, the card browser or similar windows are open <br>or the main window has focus (isn't minimized or in the background)")
        self.strictly_avoid_interruptions_checkbox.setChecked(self.config.get(CONFIG_STRICTLY_AVOID_INTERRUPTIONS))
        self.strictly_avoid_interruptions_checkbox.toggled.connect(self.change_strictly_avoid_interruption)
        strictly_avoid_interruptions_label.mouseReleaseEvent = lambda *args: self.strictly_avoid_interruptions_checkbox.toggle()

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

        # "Disable internet check" checkbox
        disable_internet_check_label = QLabel("Disable pre-sync internet check")
        disable_internet_check_tooltip = (
            "When enabled, the addon will skip the connectivity check "
            "and immediately attempt to sync."
        )
        disable_internet_check_label.setToolTip(disable_internet_check_tooltip)
        self.disable_internet_check_checkbox.setToolTip(disable_internet_check_tooltip)
        self.disable_internet_check_checkbox.setChecked(self.config.get(CONFIG_DISABLE_INTERNET_CHECK))
        self.disable_internet_check_checkbox.toggled.connect(self.change_disable_internet_check)
        disable_internet_check_label.mouseReleaseEvent = lambda *args: self.disable_internet_check_checkbox.toggle()

        # Reset Defaults button
        reset_button = QPushButton("Reset Defaults")
        reset_button.clicked.connect(self.on_reset_to_defaults_call)
        reset_button.setMaximumWidth(120)

        # Grid layout for settings
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(sync_timeout_label, 0, 0)
        grid.addWidget(self.sync_timeout_spinbox, 0, 1)

        grid.addWidget(idle_sync_timeout_label, 1, 0)
        grid.addWidget(self.idle_sync_timeout_spinbox, 1, 1)

        grid.addWidget(strictly_avoid_interruptions_label, 2, 0)
        grid.addWidget(self.strictly_avoid_interruptions_checkbox, 2, 1)

        grid.addWidget(sync_on_change_only_label, 3, 0)
        grid.addWidget(self.sync_on_change_only_checkbox, 3, 1)

        grid.addWidget(idle_before_sync_label, 4, 0)
        grid.addWidget(self.idle_before_sync_spinbox, 4, 1)

        grid.addWidget(disable_internet_check_label, 5, 0)
        grid.addWidget(self.disable_internet_check_checkbox, 5, 1)

        reset_layout = QHBoxLayout()
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_layout.addStretch()
        reset_layout.addWidget(reset_button)
        grid.addLayout(reset_layout, 6, 1)

        # Inline log display
        log_label = QLabel("Sync Log")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Wrap grid + log in a vbox; log fills remaining space
        outer_layout = QVBoxLayout()
        outer_layout.addLayout(grid)
        outer_layout.addWidget(log_label)
        outer_layout.addWidget(self.log_output, 1)  # stretch factor 1 to fill space
        parent.setLayout(outer_layout)

        # Register for live log updates and show existing log
        self.log_manager.register(self)
        self.refresh_log()

    def _setup_support_tab(self, parent: QWidget):
        """Build the support / donate content inside the given parent widget."""
        main_layout = QVBoxLayout()
        parent.setLayout(main_layout)

        # Introduction
        intro_label = QLabel("If you find this add-on useful, consider supporting its development!")
        intro_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro_label.setWordWrap(True)
        main_layout.addWidget(intro_label)

        # Ko-fi Widget
        kofi_html = """
        <body style="margin: 0; padding: 8px 0;">
        <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
            <script type='text/javascript' src='https://storage.ko-fi.com/cdn/widget/Widget_2.js'></script>
            <script type='text/javascript'>
                kofiwidget2.init('Support me on Ko-fi', '#72a4f2', 'D1D01W6NQT');
                kofiwidget2.draw();
            </script>
        </div>
        </body>
        """
        self.kofi_widget = AnkiWebView(title="kofi_support")
        self.kofi_widget.stdHtml(kofi_html)
        self.kofi_widget.setFixedHeight(60)
        main_layout.addWidget(self.kofi_widget)

        # Scroll area for donation details
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)

        # Support details
        support_items = [
            {
                "title": "UPI",
                "id": "athulkrishnasv2015-2@okhdfcbank",
                "img": "UPI.jpg"
            },
            {
                "title": "Bitcoin (BTC)",
                "id": "bc1qrrek3m7sr33qujjrktj949wav6mehdsk057cfx",
                "img": "BTC.jpg"
            },
            {
                "title": "Ethereum (ETH)",
                "id": "0xce6899e4903EcB08bE5Be65E44549fadC3F45D27",
                "img": "ETH.jpg"
            }
        ]

        addon_path = os.path.dirname(__file__)

        for item in support_items:
            item_widget = QWidget()
            item_layout = QVBoxLayout()
            item_widget.setLayout(item_layout)

            # Title
            title_label = QLabel(f"<b>{item['title']}</b>")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(title_label)

            # QR Code
            qr_label = QLabel()
            qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_path = os.path.join(addon_path, "Support", item["img"])
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                pixmap = pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                qr_label.setPixmap(pixmap)
            else:
                qr_label.setText("(Image not found)")
            item_layout.addWidget(qr_label)

            # ID and Copy Button
            id_layout = QHBoxLayout()
            id_label = QLabel(item["id"])
            id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            copy_button = QPushButton("Copy")
            copy_button.setMaximumWidth(80)
            copy_button.clicked.connect(lambda checked, text=item["id"]: self._copy_to_clipboard(text))

            id_layout.addWidget(id_label)
            id_layout.addWidget(copy_button)
            item_layout.addLayout(id_layout)

            item_layout.setContentsMargins(0, 10, 0, 20)
            scroll_layout.addWidget(item_widget)

    def _copy_to_clipboard(self, text):
        cb = QApplication.clipboard()
        cb.setText(text)

    def refresh_log(self):
        """Refresh the inline log and scroll to the bottom"""
        if self.log_output:
            self.log_output.setPlainText(self.log_manager.read())
            self.log_output.verticalScrollBar().setValue(
                self.log_output.verticalScrollBar().maximum()
            )

    def on_reset_to_defaults_call(self):
        from .constants import CONFIG_DEFAULT_CONFIG
        for key, value in CONFIG_DEFAULT_CONFIG.items():
            self.config.set(key, value)
        
        self.sync_timeout_spinbox.blockSignals(True)
        self.idle_sync_timeout_spinbox.blockSignals(True)
        self.strictly_avoid_interruptions_checkbox.blockSignals(True)
        self.sync_on_change_only_checkbox.blockSignals(True)
        self.idle_before_sync_spinbox.blockSignals(True)
        self.disable_internet_check_checkbox.blockSignals(True)

        self.sync_timeout_spinbox.setValue(self.config.get(CONFIG_SYNC_TIMEOUT))
        self.idle_sync_timeout_spinbox.setValue(self.config.get(CONFIG_IDLE_SYNC_TIMEOUT))
        self.strictly_avoid_interruptions_checkbox.setChecked(self.config.get(CONFIG_STRICTLY_AVOID_INTERRUPTIONS))
        self.sync_on_change_only_checkbox.setChecked(self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))
        self.idle_before_sync_spinbox.setValue(self.config.get(CONFIG_IDLE_BEFORE_SYNC))
        self.disable_internet_check_checkbox.setChecked(self.config.get(CONFIG_DISABLE_INTERNET_CHECK))

        self.idle_before_sync_spinbox.setEnabled(self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))
        self.sync_timeout_spinbox.setEnabled(not self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))
        self.idle_sync_timeout_spinbox.setEnabled(not self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY))

        self.sync_timeout_spinbox.blockSignals(False)
        self.idle_sync_timeout_spinbox.blockSignals(False)
        self.strictly_avoid_interruptions_checkbox.blockSignals(False)
        self.sync_on_change_only_checkbox.blockSignals(False)
        self.idle_before_sync_spinbox.blockSignals(False)
        self.disable_internet_check_checkbox.blockSignals(False)

        self.sync_routine.reload_config()

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.log_manager.unregister(self)
        if self.kofi_widget:
            self.kofi_widget.cleanup()
            self.kofi_widget = None
        super().closeEvent(a0)


def on_options_call(conf, sync_routine, log_manager):
    """Open settings dialog"""
    dialog = AutoSyncOptionsDialog(conf, sync_routine, log_manager)
    dialog.exec()
