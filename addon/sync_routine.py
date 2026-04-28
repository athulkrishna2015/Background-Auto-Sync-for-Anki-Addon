import datetime
from aqt import dialogs as aqt_dialogs
from aqt import mw
from aqt.qt import QApplication, QEvent, QObject
from .config import AutoSyncConfigManager
from .constants import (
    CONFIG_IDLE_BEFORE_SYNC,
    CONFIG_IDLE_SYNC_TIMEOUT,
    CONFIG_STRICTLY_AVOID_INTERRUPTIONS,
    CONFIG_SYNC_ON_CHANGE_ONLY,
    CONFIG_SYNC_TIMEOUT,
    CONFIG_DISABLE_INTERNET_CHECK,
)
from .utils import has_internet_connection
from .log_window import LogManager

log_to_stdout = False


class UserActivityEventListener(QObject):
    """If the user moves the mouse or presses a key within any Anki window, call the sync routine"""

    def __init__(self, sync_routine):
        super(UserActivityEventListener, self).__init__()
        self.sync_routine = sync_routine

    def eventFilter(self, obj: QObject, evt: QEvent):
        if evt.type() in [QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.KeyPress]:
            self.sync_routine.on_user_activity()
        # if this returns true, the event won't be propagated further
        return False


class SyncRoutine:
    MINIMUM_TIMER_INTERVAL_MS = 1000

    def __init__(self, config: AutoSyncConfigManager, log_manager: LogManager):
        self.config = config
        self.log_manager = log_manager

        # initiate instance attributes
        self.countdown_to_sync_timer: mw.progress.timer = None
        self.sync_timer: mw.progress.timer = None
        self.sync_in_progress: bool = False
        self.activity_since_sync: bool = True
        self.user_activity_event_listener = UserActivityEventListener(self)
        self._event_filter_installed: bool = False

        # Background sync state — saved before sync, restored after
        self._pre_sync_was_minimized: bool = False
        self._pre_sync_was_hidden: bool = False
        self._pre_sync_active_window: object = None

        # Change detection — track collection modification timestamp
        self._last_synced_mod: int = 0

        # set constants (load from config)
        self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT = 0.2 * 1000 * 60  # Reinstall the event listener every 0.2 minutes. If it were running all the time, it would impact performance
        self.SYNC_TIMEOUT_NO_ACTIVITY: int = None
        self.SYNC_TIMEOUT: int = None
        self.STRICTLY_AVOID_INTERRUPTIONS: bool = None
        self.SYNC_ON_CHANGE_ONLY: bool = None
        self.IDLE_BEFORE_SYNC: int = None
        self.DISABLE_INTERNET_CHECK: bool = None
        self.load_config()

        # start auto sync process
        self.start_countdown_to_sync_timer()

    def log(self, message):
        """Write message to log window and optionally stdout"""
        self.log_manager.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}")
        if log_to_stdout:
            print(f"[Auto Sync] {datetime.datetime.now().strftime('%H:%M:%S')} {message}")

    def start_countdown_to_sync_timer(self):
        """Start timer that after a few seconds starts the sync timer and installs the event listener"""
        if self.countdown_to_sync_timer is not None:
            self.countdown_to_sync_timer.stop()
        self.log(f"Waiting {self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 60000} minutes to start sync timer")
        self.countdown_to_sync_timer = mw.progress.timer(int(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT), self.start_sync_timer, False)

    def _has_changes_since_last_sync(self) -> bool:
        """Check if the collection has been modified since the last sync."""
        try:
            current_mod = mw.col.mod
            if current_mod != self._last_synced_mod:
                return True
            return False
        except Exception:
            # If we can't determine, assume there are changes (safe fallback)
            return True

    def _set_user_activity_filter(self, enabled: bool):
        if enabled and not self._event_filter_installed:
            mw.app.installEventFilter(self.user_activity_event_listener)
            self._event_filter_installed = True
        elif not enabled and self._event_filter_installed:
            try:
                mw.app.removeEventFilter(self.user_activity_event_listener)
            finally:
                self._event_filter_installed = False

    @staticmethod
    def _main_window_has_focus() -> bool:
        try:
            if QApplication.activeWindow() == mw or mw.isActiveWindow():
                return True
        except Exception:
            pass

        for widget_name in ("web", "toolbarWeb", "bottomWeb"):
            widget = getattr(mw, widget_name, None)
            try:
                if widget is not None and widget.hasFocus():
                    return True
            except (AttributeError, RuntimeError):
                continue
        return False

    @staticmethod
    def _open_dialog_names():
        dialogs = getattr(aqt_dialogs, "_dialogs", {})
        try:
            return [name for name, dialog_info in dialogs.items() if dialog_info[1]]
        except Exception:
            return []

    def is_good_state(self):
        """Check that the app isn't in any state that it shouldn't automatically sync in to avoid interrupting the user's activity"""
        reasons = []  # all the reasons why it can't sync now will be collected in this
        if self.sync_in_progress:
            reasons.append("Sync in progress")
        if self.STRICTLY_AVOID_INTERRUPTIONS:
            # check if any dialogs are open
            if not aqt_dialogs.allClosed():
                open_windows = self._open_dialog_names()
                if open_windows:
                    reasons.append(f"Windows are open: {', '.join(open_windows)}")
                else:
                    reasons.append("Windows are open")
            if self._main_window_has_focus():
                reasons.append("Main Window has focus")
            if mw.state not in ["deckBrowser", "overview"]:
                reasons.append("Main Window is not on deck browser or overview screen (state: " + str(mw.state) + ")")

        if len(reasons) > 0:
            self.log(f"Can't start sync timer ({', '.join(reasons)})")
            return False
        return True

    def start_sync_timer(self):
        """Start the background timer to automatically sync the collection and install an event filter to stop it at any user activity"""
        if self.is_good_state():
            timeout = self.SYNC_TIMEOUT if self.activity_since_sync else self.SYNC_TIMEOUT_NO_ACTIVITY

            # If change-only mode with idle-before-sync, use that timeout when change detected
            if self.SYNC_ON_CHANGE_ONLY and self.activity_since_sync:
                if not self._has_changes_since_last_sync():
                    self.log("No changes detected after recent activity, switching back to idle sync interval")
                    self.activity_since_sync = False
                    timeout = self.SYNC_TIMEOUT_NO_ACTIVITY
                elif self.IDLE_BEFORE_SYNC > 0:
                    timeout = self.IDLE_BEFORE_SYNC

            if not self.activity_since_sync and self.config.get(CONFIG_IDLE_SYNC_TIMEOUT) == 0:
                self.log("Idle periodic sync is turned off. Waiting for user activity.")
                self._set_user_activity_filter(True)
                if self.sync_timer is not None:
                    self.sync_timer.stop()
                return

            self.log(f"Started sync timer, waiting for {timeout / 60000} minutes")
            self._set_user_activity_filter(True)
            # stop any old sync_timer timers and start a new one
            if self.sync_timer is not None:
                self.sync_timer.stop()
            self.sync_timer = mw.progress.timer(max(timeout, self.MINIMUM_TIMER_INTERVAL_MS), self.do_sync, False)
        else:
            # try again in a few seconds
            self._set_user_activity_filter(False)
            self.start_countdown_to_sync_timer()

    def stop_sync_timer(self):
        """Stop the background timer to automatically sync the collection and remove the event filter that checks for user activity.
        Start timer to start it again"""
        self._set_user_activity_filter(False)
        if self.sync_timer is not None:
            self.sync_timer.stop()
        self.start_countdown_to_sync_timer()

    def on_user_activity(self):
        """Stop sync timer and register user activity (shortens timeout till next sync)"""
        self.log("User activity! Stopped sync timer")
        self.activity_since_sync = True
        self.stop_sync_timer()

    def _save_window_state(self):
        """Save the current window state before sync so we can restore it after."""
        try:
            self._pre_sync_was_minimized = mw.isMinimized()
            self._pre_sync_was_hidden = mw.isHidden()
            self._pre_sync_active_window = QApplication.activeWindow()
        except Exception:
            self._pre_sync_was_minimized = False
            self._pre_sync_was_hidden = False
            self._pre_sync_active_window = None

    def _restore_window_state(self):
        """Restore the window state after sync to prevent focus stealing."""
        try:
            if self._pre_sync_was_minimized:
                # Re-minimize if it was minimized before sync
                mw.showMinimized()
            elif self._pre_sync_was_hidden:
                mw.hide()
            elif self._pre_sync_active_window is not None and self._pre_sync_active_window != mw:
                # Anki was not the active window — don't steal focus
                # Lower the main window so it doesn't cover the previously active app
                mw.lower()
                # Try to re-activate the window that was active before sync
                try:
                    self._pre_sync_active_window.raise_()
                    self._pre_sync_active_window.activateWindow()
                except (RuntimeError, AttributeError):
                    # The window may have been closed during sync
                    pass
            elif self._pre_sync_active_window is None:
                # No Anki window was active — Anki was in background, keep it there
                mw.lower()
        except Exception as e:
            self.log(f"Warning: could not restore window state: {e}")

    def do_sync(self):
        """Force the app to sync the collection if there's an internet connection.
        Preserves window state so Anki never steals focus."""
        if not self.DISABLE_INTERNET_CHECK and not has_internet_connection():
            self.log(f"No internet connection, delaying sync for {self.SYNC_TIMEOUT / 60000} minutes")
            self.activity_since_sync = True  # shorten duration to next sync
            self.start_sync_timer()
            return

        # If sync-on-change-only is enabled, check for changes before syncing
        if self.SYNC_ON_CHANGE_ONLY and not self._has_changes_since_last_sync():
            self.log("No changes detected, skipping sync (sync-on-change-only enabled)")
            self.activity_since_sync = False
            self.start_sync_timer()
            return

        self._set_user_activity_filter(False)

        # Save window state BEFORE sync to restore afterwards
        self._save_window_state()
        self.log(f"Syncing (background: minimized={self._pre_sync_was_minimized}, hidden={self._pre_sync_was_hidden}, anki_active={self._pre_sync_active_window == mw})")

        self.sync_in_progress = True

        from aqt import gui_hooks
        auth = mw.pm.sync_auth()
        if not auth:
            self.log("Not logged in to AnkiWeb, skipping sync")
            self.sync_finished()
            return

        def on_future_done(fut):
            try:
                out = fut.result()
            except Exception as err:
                self.log(f"Sync error: {err}")
                from aqt.sync import handle_sync_error
                handle_sync_error(mw, err)
                gui_hooks.sync_did_finish()
                return

            mw.col._load_scheduler()
            mw.pm.set_host_number(out.host_number)
            if out.new_endpoint:
                mw.pm.set_current_sync_url(out.new_endpoint)
            
            if out.server_message:
                from aqt.utils import showText
                showText(out.server_message, parent=mw)

            if out.required == out.NO_CHANGES:
                mw.media_syncer.start_monitoring()
                # Properly notify all addons (including ourselves) that sync is complete
                gui_hooks.sync_did_finish()
            else:
                self.log("Full sync required (conflict). Passing to Anki UI.")
                from aqt.sync import full_sync
                full_sync(mw, out, gui_hooks.sync_did_finish)

        gui_hooks.sync_will_start()
        # Headless sync exactly like native, but using run_in_background instead of with_progress!
        mw.taskman.run_in_background(
            lambda: mw.col.sync_collection(auth, mw.pm.media_syncing_enabled()),
            on_future_done
        )

    def sync_finished(self, *args):
        """When one sync cycle has finished, start the whole process over.
        Restore window state to prevent focus stealing."""
        self.log("Sync completed")
        self.sync_in_progress = False
        self.activity_since_sync = False

        # Update change-detection mod timestamp
        try:
            self._last_synced_mod = mw.col.mod
        except Exception:
            pass

        # Restore window state so Anki doesn't stay in the foreground
        self._restore_window_state()

        self.start_countdown_to_sync_timer()

    def sync_initiated(self, *args):
        """Corner case: user initiates sync but it can't finish. Set this parameter to avoid starting another failed sync attempt on top"""
        self.log("Sync initiated")
        self.sync_in_progress = True

    def load_config(self):
        """Load the constants from config manager"""
        self.SYNC_TIMEOUT_NO_ACTIVITY = int((self.config.get(CONFIG_IDLE_SYNC_TIMEOUT) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.SYNC_TIMEOUT = int((self.config.get(CONFIG_SYNC_TIMEOUT) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.STRICTLY_AVOID_INTERRUPTIONS = self.config.get(CONFIG_STRICTLY_AVOID_INTERRUPTIONS)
        self.SYNC_ON_CHANGE_ONLY = self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY)
        self.IDLE_BEFORE_SYNC = int((self.config.get(CONFIG_IDLE_BEFORE_SYNC) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.DISABLE_INTERNET_CHECK = self.config.get(CONFIG_DISABLE_INTERNET_CHECK)

        self.SYNC_TIMEOUT_NO_ACTIVITY = max(self.SYNC_TIMEOUT_NO_ACTIVITY, self.MINIMUM_TIMER_INTERVAL_MS)
        self.SYNC_TIMEOUT = max(self.SYNC_TIMEOUT, self.MINIMUM_TIMER_INTERVAL_MS)
        self.IDLE_BEFORE_SYNC = max(self.IDLE_BEFORE_SYNC, self.MINIMUM_TIMER_INTERVAL_MS)

        idle_sync_text = "off" if self.config.get(CONFIG_IDLE_SYNC_TIMEOUT) == 0 else f"{self.SYNC_TIMEOUT_NO_ACTIVITY / 60000} min"

        self.log(f"Loaded config. Sync timeout: {self.SYNC_TIMEOUT / 60000} min, "
                 f"idle sync timeout: {idle_sync_text}. "
                 f"Strictly avoid interruptions: {'on' if self.STRICTLY_AVOID_INTERRUPTIONS else 'off'}. "
                 f"Sync on change only: {'on' if self.SYNC_ON_CHANGE_ONLY else 'off'}. "
                 f"Idle before sync: {self.IDLE_BEFORE_SYNC / 60000} min. "
                 f"Disable internet check: {'on' if self.DISABLE_INTERNET_CHECK else 'off'}")

    def reload_config(self):
        """reload the config and restart the sync timer timeout"""
        self.load_config()
        self.stop_sync_timer()

    def cleanup(self):
        """Clean up timers and listeners when profile closes"""
        if self.countdown_to_sync_timer is not None:
            self.countdown_to_sync_timer.stop()
            self.countdown_to_sync_timer = None
        if self.sync_timer is not None:
            self.sync_timer.stop()
            self.sync_timer = None
        self._set_user_activity_filter(False)
        self.sync_in_progress = False
