import datetime
import time
from aqt import dialogs as aqt_dialogs
from aqt import mw
from aqt.qt import QApplication, QEvent, QObject
from .config import AutoSyncConfigManager
from .constants import (
    CONFIG_IDLE_BEFORE_SYNC,
    CONFIG_IDLE_SYNC_FOCUSED_TIMEOUT,
    CONFIG_IDLE_SYNC_TIMEOUT,
    CONFIG_AVOID_INTERRUPTION_DIALOGS,
    CONFIG_AVOID_DIALOG_LIST,
    CONFIG_AVOID_DIALOGS_TIMEOUT,
    CONFIG_AVOID_INTERRUPTION_FOCUS,
    CONFIG_AVOID_INTERRUPTION_REVIEW,
    CONFIG_AVOID_REVIEW_TIMEOUT,
    CONFIG_AVOID_OVERRIDE_TIMEOUT,
    CONFIG_SYNC_ON_CHANGE_ONLY,
    CONFIG_SYNC_TIMEOUT,
    CONFIG_DISABLE_INTERNET_CHECK,
    CONFIG_CONFLICT_RESOLUTION,
)
from .utils import has_internet_connection
from .tabs.logs_tab import LogManager

log_to_stdout = False


class UserActivityEventListener(QObject):
    """If the user moves the mouse or presses a key within any Anki window, call the sync routine"""

    def __init__(self, sync_routine):
        super(UserActivityEventListener, self).__init__()
        self.sync_routine = sync_routine

    def eventFilter(self, obj: QObject, evt: QEvent):
        # Only react to actual clicks/keys — not mouse movement — to avoid
        # resetting the sync timer (and logging) on every cursor motion.
        if evt.type() in [QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress]:
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
        # Timestamp of the last user click/keypress, for the focused-idle grace period
        self._last_activity_time: float = time.monotonic()

        # Background sync state — saved before sync, restored after
        self._pre_sync_was_minimized: bool = False
        self._pre_sync_was_hidden: bool = False
        self._pre_sync_active_window: object = None
        # Only restore window state for syncs this addon initiated in the
        # background. Manual syncs (Sync button) must not steal or drop focus.
        self._preserve_window_state: bool = False

        # Change detection — track collection modification timestamp
        self._last_synced_mod: int = 0
        # Throttle repeated "can't start sync timer" log spam (e.g. during review)
        self._last_blocked_reason: str = None
        # Throttle repeated "waiting to start sync timer" log spam (monotonic secs)
        self._last_waiting_log_time: float = 0.0

        # set constants (load from config)
        self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT = 0.2 * 1000 * 60  # Reinstall the event listener every 0.2 minutes. If it were running all the time, it would impact performance
        self.SYNC_TIMEOUT_NO_ACTIVITY: int = None
        self.SYNC_TIMEOUT: int = None
        self.AVOID_INTERRUPTION_DIALOGS: bool = None
        self.AVOID_DIALOG_LIST: set = None
        self.AVOID_DIALOGS_TIMEOUT: int = None
        self.AVOID_INTERRUPTION_FOCUS: bool = None
        self.AVOID_INTERRUPTION_REVIEW: bool = None
        self.AVOID_REVIEW_TIMEOUT: int = None
        self.AVOID_OVERRIDE_TIMEOUT: int = None
        self.SYNC_ON_CHANGE_ONLY: bool = None
        self.IDLE_BEFORE_SYNC: int = None
        self.IDLE_SYNC_FOCUSED_TIMEOUT: int = None
        self.DISABLE_INTERNET_CHECK: bool = None
        self.CONFLICT_RESOLUTION: str = None
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
        # Throttle the "waiting" log so a long-blocked state (e.g. dialog open)
        # doesn't spam one line every 0.2 min. Only log once per 60 seconds.
        now = time.monotonic()
        if now - self._last_waiting_log_time >= 60:
            self.log(f"Waiting {self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 60000} minutes to start sync timer")
            self._last_waiting_log_time = now
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

    def _focused_idle_grace_elapsed(self) -> bool:
        """True when the focused-idle grace (specific or global) has elapsed."""
        return self._idle_grace_elapsed(self._effective_override_ms(self.IDLE_SYNC_FOCUSED_TIMEOUT))

    def _idle_grace_elapsed(self, timeout_ms) -> bool:
        """True when the user has been idle longer than the given timeout (ms), or it is disabled (<=0)."""
        if not timeout_ms or timeout_ms <= 0:
            return False
        elapsed_ms = (time.monotonic() - self._last_activity_time) * 1000
        return elapsed_ms >= timeout_ms

    def _effective_override_ms(self, specific_ms) -> int:
        """Effective override timeout = lower of (specific, global), ignoring disabled (0) values."""
        options = [t for t in (specific_ms, self.AVOID_OVERRIDE_TIMEOUT) if t and t > 0]
        return min(options) if options else 0

    @staticmethod
    def _open_dialog_names():
        dialogs = getattr(aqt_dialogs, "_dialogs", {})
        open_names = []
        try:
            for name, dialog_info in dialogs.items():
                if not isinstance(dialog_info, (tuple, list)) or len(dialog_info) < 2:
                    continue
                dialog = dialog_info[1]
                if not dialog:
                    continue

                # Anki can retain a dialog object in its registry after the
                # window has been closed. Only treat a real visible widget as
                # open; keep boolean entries supported for lightweight mocks
                # and older Anki registry representations.
                if isinstance(dialog, bool):
                    is_visible = dialog
                else:
                    is_visible_method = getattr(dialog, "isVisible", None)
                    if callable(is_visible_method):
                        try:
                            is_visible = bool(is_visible_method())
                        except (RuntimeError, TypeError):
                            is_visible = False
                    else:
                        is_visible = True

                if is_visible:
                    open_names.append(name)
        except Exception:
            return []
        return open_names

    def is_good_state(self):
        """Check that the app isn't in any state that it shouldn't automatically sync in to avoid interrupting the user's activity"""
        reasons = []  # all the reasons why it can't sync now will be collected in this
        if self.sync_in_progress:
            reasons.append("Sync in progress")
        # Avoid syncing while dialogs (browser, add-note, etc.) are open
        if self.AVOID_INTERRUPTION_DIALOGS:
            blocking = [n for n in self._open_dialog_names() if n in self.AVOID_DIALOG_LIST]
            if blocking:
                listed = ', '.join(sorted(blocking))
                noun = "Window is open" if len(blocking) == 1 else "Windows are open"
                reasons.append(f"{noun}: {listed}")
        # Avoid syncing while the main window has focus (unless idle past the grace period)
        if self.AVOID_INTERRUPTION_FOCUS and self._main_window_has_focus():
            if not self._idle_grace_elapsed(self._effective_override_ms(self.IDLE_SYNC_FOCUSED_TIMEOUT)):
                reasons.append("Main Window has focus")
        # Avoid syncing while reviewing / outside the safe screens
        if self.AVOID_INTERRUPTION_REVIEW and mw.state not in ["deckBrowser", "overview"]:
            if not self._idle_grace_elapsed(self._effective_override_ms(self.AVOID_REVIEW_TIMEOUT)):
                reasons.append("Main Window is not on deck browser or overview screen (state: " + str(mw.state) + ")")

        if len(reasons) > 0:
            reason = ", ".join(reasons)
            if reason != self._last_blocked_reason:
                self.log(f"Can't start sync timer ({reason})")
                self._last_blocked_reason = reason
            return False
        self._last_blocked_reason = None
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
        self._last_activity_time = time.monotonic()
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
        """Undo window-state changes made during sync.

        Never touches the Z-order: mw.lower() pushed the main window to the
        very bottom, dropping it behind windows that sat below it before the
        sync (#4). The headless sync raises nothing, so the original Z-order
        is still intact and there is nothing to restore."""
        try:
            if self._pre_sync_was_minimized:
                if not mw.isMinimized():
                    mw.showMinimized()
            elif self._pre_sync_was_hidden:
                if not mw.isHidden():
                    mw.hide()
            elif mw.isActiveWindow() and self._pre_sync_active_window not in (None, mw):
                # The sync stole focus from another Anki window — hand it back
                # without raising/lowering anything.
                self._pre_sync_active_window.activateWindow()
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

        # Save window state BEFORE sync to restore afterwards, and mark this
        # sync as addon-initiated so sync_finished restores window state.
        self._preserve_window_state = True
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
                self.log("Full sync required (conflict).")
                self._resolve_conflict(mw, out, gui_hooks.sync_did_finish)

        gui_hooks.sync_will_start()
        # Headless sync exactly like native, but using run_in_background instead of with_progress!
        mw.taskman.run_in_background(
            lambda: mw.col.sync_collection(auth, mw.pm.media_syncing_enabled()),
            on_future_done
        )

    def _resolve_conflict(self, mw, out, on_done):
        """Resolve a full-sync conflict, honoring the configured forced direction.

        Anki decides FULL_DOWNLOAD / FULL_UPLOAD when one side is empty — those
        are always respected. For ambiguous conflicts, the user's configured
        direction is applied automatically if set; otherwise the normal Anki
        prompt is shown."""
        from aqt.sync import full_sync, full_download, full_upload

        server_usn = out.server_media_usn if mw.pm.media_syncing_enabled() else None
        forced = self.CONFLICT_RESOLUTION

        if out.required == out.FULL_DOWNLOAD:
            if forced == "prompt":
                full_sync(mw, out, on_done)
            else:
                self.log("Conflict: downloading from AnkiWeb (local is empty)")
                full_download(mw, server_usn, on_done)
        elif out.required == out.FULL_UPLOAD:
            if forced == "prompt":
                full_sync(mw, out, on_done)
            else:
                self.log("Conflict: uploading to AnkiWeb (AnkiWeb is empty)")
                full_upload(mw, server_usn, on_done)
        elif forced == "download":
            self.log("Conflict: forcing AnkiWeb -> local (download)")
            full_download(mw, server_usn, on_done)
        elif forced == "upload":
            self.log("Conflict: forcing local -> AnkiWeb (upload)")
            full_upload(mw, server_usn, on_done)
        else:
            full_sync(mw, out, on_done)

    def sync_finished(self, *args):
        """When one sync cycle has finished, start the whole process over.
        Restore window state to prevent focus stealing (background syncs only)."""
        self.log("Sync completed")
        self.sync_in_progress = False
        self.activity_since_sync = False

        # Update change-detection mod timestamp
        try:
            self._last_synced_mod = mw.col.mod
        except Exception:
            pass

        # Only restore window state for background syncs initiated by this
        # addon. Manual syncs (Sync button) must retain focus normally.
        if self._preserve_window_state:
            self._restore_window_state()
            self._preserve_window_state = False

        self.start_countdown_to_sync_timer()

    def sync_on_close(self):
        """Perform a final sync before Anki closes so pending changes aren't lost.
        Runs synchronously (Anki is shutting down) and only if there is a change
        to upload and internet connectivity is available."""
        if self.sync_in_progress:
            return
        if not self.DISABLE_INTERNET_CHECK and not has_internet_connection():
            return
        if self.SYNC_ON_CHANGE_ONLY and not self._has_changes_since_last_sync():
            return

        auth = mw.pm.sync_auth()
        if not auth:
            return

        self.sync_in_progress = True
        try:
            self.log("Syncing before Anki closes")
            out = mw.col.sync_collection(auth, mw.pm.media_syncing_enabled())
            if out.required == out.NO_CHANGES:
                mw.pm.set_host_number(out.host_number)
                if out.new_endpoint:
                    mw.pm.set_current_sync_url(out.new_endpoint)
                try:
                    self._last_synced_mod = mw.col.mod
                except Exception:
                    pass
                self.log("Sync on close completed")
            else:
                self.log("Sync on close skipped (full sync / conflict resolution needed)")
        except Exception as e:
            self.log(f"Sync on close error: {e}")
        finally:
            self.sync_in_progress = False

    def sync_initiated(self, *args):
        """Corner case: user initiates sync but it can't finish. Set this parameter to avoid starting another failed sync attempt on top"""
        self.log("Sync initiated")
        self.sync_in_progress = True

    def load_config(self):
        """Load the constants from config manager"""
        self.SYNC_TIMEOUT_NO_ACTIVITY = int((self.config.get(CONFIG_IDLE_SYNC_TIMEOUT) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.SYNC_TIMEOUT = int((self.config.get(CONFIG_SYNC_TIMEOUT) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.AVOID_INTERRUPTION_DIALOGS = self.config.get(CONFIG_AVOID_INTERRUPTION_DIALOGS)
        self.AVOID_DIALOG_LIST = set(self.config.get(CONFIG_AVOID_DIALOG_LIST))
        self.AVOID_DIALOGS_TIMEOUT = int(self.config.get(CONFIG_AVOID_DIALOGS_TIMEOUT) * 1000 * 60)
        self.AVOID_INTERRUPTION_FOCUS = self.config.get(CONFIG_AVOID_INTERRUPTION_FOCUS)
        self.AVOID_INTERRUPTION_REVIEW = self.config.get(CONFIG_AVOID_INTERRUPTION_REVIEW)
        self.AVOID_REVIEW_TIMEOUT = int(self.config.get(CONFIG_AVOID_REVIEW_TIMEOUT) * 1000 * 60)
        self.AVOID_OVERRIDE_TIMEOUT = int(self.config.get(CONFIG_AVOID_OVERRIDE_TIMEOUT) * 1000 * 60)
        self.SYNC_ON_CHANGE_ONLY = self.config.get(CONFIG_SYNC_ON_CHANGE_ONLY)
        self.IDLE_BEFORE_SYNC = int((self.config.get(CONFIG_IDLE_BEFORE_SYNC) * 1000 * 60) - round(self.COUNTDOWN_TO_SYNC_TIMER_TIMEOUT / 2))
        self.IDLE_SYNC_FOCUSED_TIMEOUT = int(self.config.get(CONFIG_IDLE_SYNC_FOCUSED_TIMEOUT) * 1000 * 60)
        self.DISABLE_INTERNET_CHECK = self.config.get(CONFIG_DISABLE_INTERNET_CHECK)
        self.CONFLICT_RESOLUTION = self.config.get(CONFIG_CONFLICT_RESOLUTION)

        self.SYNC_TIMEOUT_NO_ACTIVITY = max(self.SYNC_TIMEOUT_NO_ACTIVITY, self.MINIMUM_TIMER_INTERVAL_MS)
        self.SYNC_TIMEOUT = max(self.SYNC_TIMEOUT, self.MINIMUM_TIMER_INTERVAL_MS)
        self.IDLE_BEFORE_SYNC = max(self.IDLE_BEFORE_SYNC, self.MINIMUM_TIMER_INTERVAL_MS)

        idle_sync_text = "off" if self.config.get(CONFIG_IDLE_SYNC_TIMEOUT) == 0 else f"{self.SYNC_TIMEOUT_NO_ACTIVITY / 60000} min"

        self.log(f"Loaded config. Sync timeout: {self.SYNC_TIMEOUT / 60000} min, "
                 f"idle sync timeout: {idle_sync_text}. "
                 f"Avoid on dialogs: {'on' if self.AVOID_INTERRUPTION_DIALOGS else 'off'}, "
                 f"on focus: {'on' if self.AVOID_INTERRUPTION_FOCUS else 'off'}, "
                 f"on review: {'on' if self.AVOID_INTERRUPTION_REVIEW else 'off'}. "
                 f"Override timeouts (min): dialogs {self.AVOID_DIALOGS_TIMEOUT / 60000}, "
                 f"focus {self.IDLE_SYNC_FOCUSED_TIMEOUT / 60000}, "
                 f"review {self.AVOID_REVIEW_TIMEOUT / 60000}, "
                 f"global {self.AVOID_OVERRIDE_TIMEOUT / 60000}. "
                 f"Effective (min): dialogs {self._effective_override_ms(self.AVOID_DIALOGS_TIMEOUT) / 60000}, "
                 f"focus {self._effective_override_ms(self.IDLE_SYNC_FOCUSED_TIMEOUT) / 60000}, "
                 f"review {self._effective_override_ms(self.AVOID_REVIEW_TIMEOUT) / 60000}. "
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
        self._preserve_window_state = False
