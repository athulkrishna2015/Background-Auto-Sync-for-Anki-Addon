import sys
import time
import unittest
from unittest import mock

from tests import mock_aqt

aqt, mw = mock_aqt.install()

import aqt as aqt_mod
from addon.constants import CONFLICT_PROMPT, CONFLICT_DOWNLOAD, CONFLICT_UPLOAD
from addon.sync_routine import SyncRoutine


def make_routine(conflict=CONFLICT_PROMPT, config_extra=None):
    config = mock.Mock()
    config.get = mock.Mock(
        side_effect=lambda key: {
            "sync timeout": 1,
            "idle sync timeout": 0,
            "avoid sync when dialogs open": True,
            "avoid dialogs list": ["Browser", "AddCards", "EditCurrent", "DeckStats", "Preferences"],
            "avoid dialogs timeout": 0,
            "avoid sync when main window focused": True,
            "avoid sync while reviewing": True,
            "avoid review timeout": 0,
            "global avoid override timeout": 0,
            "sync on change only": True,
            "idle before sync": 2,
            "idle sync focused timeout": 0,
            "disable internet check": False,
            "on conflict": conflict,
            **(config_extra or {}),
        }[key]
    )
    log = mock.Mock()
    return SyncRoutine(config, log)


class ConflictResolutionTest(unittest.TestCase):
    def setUp(self):
        aqt.sync.full_sync.reset_mock()
        aqt.sync.full_download.reset_mock()
        aqt.sync.full_upload.reset_mock()

    def _out(self, required):
        return mock_aqt.FakeSyncOutput(required=required)

    def test_prompt_ambiguous_calls_full_sync(self):
        r = make_routine(CONFLICT_PROMPT)
        out = self._out(mock_aqt.FakeSyncOutput.CONFLICT)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_sync.assert_called_once()
        aqt.sync.full_download.assert_not_called()
        aqt.sync.full_upload.assert_not_called()

    def test_forced_download_ambiguous(self):
        r = make_routine(CONFLICT_DOWNLOAD)
        out = self._out(mock_aqt.FakeSyncOutput.CONFLICT)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_download.assert_called_once()
        aqt.sync.full_sync.assert_not_called()

    def test_forced_upload_ambiguous(self):
        r = make_routine(CONFLICT_UPLOAD)
        out = self._out(mock_aqt.FakeSyncOutput.CONFLICT)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_upload.assert_called_once()
        aqt.sync.full_sync.assert_not_called()

    def test_full_download_respected_even_if_forced_upload(self):
        # Anki decided local is empty -> must download regardless of forced direction
        r = make_routine(CONFLICT_UPLOAD)
        out = self._out(mock_aqt.FakeSyncOutput.FULL_DOWNLOAD)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_download.assert_called_once()
        aqt.sync.full_upload.assert_not_called()

    def test_full_upload_respected_even_if_forced_download(self):
        r = make_routine(CONFLICT_DOWNLOAD)
        out = self._out(mock_aqt.FakeSyncOutput.FULL_UPLOAD)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_upload.assert_called_once()
        aqt.sync.full_download.assert_not_called()

    def test_prompt_full_download_goes_through_full_sync(self):
        # In prompt mode preserve Anki's confirm behavior via full_sync
        r = make_routine(CONFLICT_PROMPT)
        out = self._out(mock_aqt.FakeSyncOutput.FULL_DOWNLOAD)
        r._resolve_conflict(mw, out, None)
        aqt.sync.full_sync.assert_called_once()

    def test_server_usn_passed_when_media_enabled(self):
        r = make_routine(CONFLICT_DOWNLOAD)
        out = self._out(mock_aqt.FakeSyncOutput.CONFLICT)
        r._resolve_conflict(mw, out, None)
        args, kwargs = aqt.sync.full_download.call_args
        self.assertEqual(args[1], 5)  # server_usn


class ChangeDetectionTest(unittest.TestCase):
    def test_no_changes_returns_false(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 100
        self.assertFalse(r._has_changes_since_last_sync())

    def test_change_returns_true(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 101
        self.assertTrue(r._has_changes_since_last_sync())

    def test_exception_returns_true(self):
        r = make_routine()
        mw.col.mod = 100
        with mock.patch.object(mw.col, "mod", side_effect=Exception("boom")):
            self.assertTrue(r._has_changes_since_last_sync())


class BlockedReasonThrottleTest(unittest.TestCase):
    def test_same_reason_only_logged_once(self):
        r = make_routine()
        r._last_blocked_reason = None
        r.is_good_state()
        count_after_first = r.log_manager.write.call_count
        r.is_good_state()
        self.assertEqual(r.log_manager.write.call_count, count_after_first)


class WaitingLogThrottleTest(unittest.TestCase):
    def test_waiting_log_throttled_by_time(self):
        r = make_routine()
        r.countdown_to_sync_timer = None
        r._last_waiting_log_time = 0.0
        r.start_countdown_to_sync_timer()
        first_count = r.log_manager.write.call_count
        # Immediately restarting should not log again within the throttle window
        r.start_countdown_to_sync_timer()
        self.assertEqual(r.log_manager.write.call_count, first_count)


class EffectiveOverrideLogTest(unittest.TestCase):
    def test_config_log_reports_effective_overrides(self):
        # dialogs 0 + global 10 -> effective 10; focus 0 + global 10 -> effective 10
        r = make_routine(config_extra={
            "avoid dialogs timeout": 0,
            "global avoid override timeout": 10,
            "idle sync focused timeout": 0,
        })
        written = [c[0][0] for c in r.log_manager.write.call_args_list]
        config_line = next(line for line in written if "Loaded config" in line)
        self.assertIn("Effective (min): dialogs 10.0", config_line)
        self.assertIn("focus 10.0", config_line)


class SyncOnCloseTest(unittest.TestCase):
    def setUp(self):
        mw.col.sync_collection = mock.Mock()
        aqt.sync.full_sync.reset_mock()
        aqt.sync.full_download.reset_mock()
        aqt.sync.full_upload.reset_mock()

    def test_skips_when_no_changes_and_change_only(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 100
        r.sync_on_close()
        mw.col.sync_collection.assert_not_called()

    def test_syncs_when_changes_present(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 999
        mw.col.sync_collection = mock.Mock(return_value=mock_aqt.FakeSyncOutput(required=0))
        r.sync_on_close()
        mw.col.sync_collection.assert_called_once()

    def test_skips_conflict(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 999
        mw.col.sync_collection = mock.Mock(
            return_value=mock_aqt.FakeSyncOutput(required=mock_aqt.FakeSyncOutput.CONFLICT)
        )
        r.sync_on_close()
        aqt.sync.full_sync.assert_not_called()

    def test_resets_sync_in_progress_on_error(self):
        r = make_routine()
        r._last_synced_mod = 100
        mw.col.mod = 999
        mw.col.sync_collection = mock.Mock(side_effect=RuntimeError("net down"))
        r.sync_on_close()
        self.assertFalse(r.sync_in_progress)


class WindowStateRestoreGateTest(unittest.TestCase):
    def test_restore_runs_for_background_sync(self):
        r = make_routine()
        r._preserve_window_state = True
        with mock.patch.object(r, "_restore_window_state") as restore:
            r.sync_finished()
        restore.assert_called_once()
        self.assertFalse(r._preserve_window_state)

    def test_no_restore_for_manual_sync(self):
        # A manual Sync-button press never sets the flag -> no window restore
        r = make_routine()
        r._preserve_window_state = False
        with mock.patch.object(r, "_restore_window_state") as restore:
            r.sync_finished()
        restore.assert_not_called()


class WindowStateRestoreTest(unittest.TestCase):
    """Issue #4: restoring state must never change the Z-order."""

    def setUp(self):
        from aqt.qt import QApplication

        self._prev_active = QApplication.active
        QApplication.active = None
        self._prev_returns = {
            name: getattr(mw, name).return_value
            for name in ("isActiveWindow", "isMinimized", "isHidden")
        }
        mw.reset_mock()

    def tearDown(self):
        from aqt.qt import QApplication

        QApplication.active = self._prev_active
        for name, value in self._prev_returns.items():
            getattr(mw, name).return_value = value
        mw.reset_mock()

    def _visible_routine(self, active_window):
        r = make_routine()
        r._pre_sync_was_minimized = False
        r._pre_sync_was_hidden = False
        r._pre_sync_active_window = active_window
        return r

    def test_background_anki_never_lowered(self):
        # Another app had focus before the sync -> Anki must stay where it was
        r = self._visible_routine(None)
        r._restore_window_state()
        mw.lower.assert_not_called()
        mw.raise_.assert_not_called()

    def test_other_anki_window_never_lowered(self):
        other = mock.Mock()
        mw.isActiveWindow.return_value = True
        r = self._visible_routine(other)
        r._restore_window_state()
        mw.lower.assert_not_called()
        other.activateWindow.assert_called_once()

    def test_no_focus_stolen_leaves_windows_alone(self):
        other = mock.Mock()
        mw.isActiveWindow.return_value = False
        r = self._visible_routine(other)
        r._restore_window_state()
        other.activateWindow.assert_not_called()
        mw.lower.assert_not_called()

    def test_minimized_stays_minimized(self):
        r = make_routine()
        r._pre_sync_was_minimized = True
        r._pre_sync_was_hidden = False
        r._pre_sync_active_window = None
        mw.isMinimized.return_value = False
        r._restore_window_state()
        mw.showMinimized.assert_called_once()
        mw.lower.assert_not_called()

    def test_hidden_stays_hidden(self):
        r = make_routine()
        r._pre_sync_was_minimized = False
        r._pre_sync_was_hidden = True
        r._pre_sync_active_window = None
        mw.isHidden.return_value = False
        r._restore_window_state()
        mw.hide.assert_called_once()
        mw.lower.assert_not_called()


class FocusedIdleGraceTest(unittest.TestCase):
    def _routine(self, minutes):
        r = make_routine(config_extra={"idle sync focused timeout": minutes})
        r.IDLE_SYNC_FOCUSED_TIMEOUT = minutes * 60 * 1000
        return r

    def test_disabled_never_elapses(self):
        r = self._routine(0)
        self.assertFalse(r._focused_idle_grace_elapsed())

    def test_elapses_after_timeout(self):
        r = self._routine(5)
        r._last_activity_time = time.monotonic() - 6 * 60
        self.assertTrue(r._focused_idle_grace_elapsed())


class GlobalOverrideTest(unittest.TestCase):
    def test_specific_lower_wins(self):
        r = make_routine(config_extra={"global avoid override timeout": 10})
        r.AVOID_OVERRIDE_TIMEOUT = 10 * 60 * 1000
        r.AVOID_DIALOGS_TIMEOUT = 3 * 60 * 1000
        self.assertEqual(r._effective_override_ms(r.AVOID_DIALOGS_TIMEOUT), 3 * 60 * 1000)

    def test_global_lower_wins(self):
        r = make_routine(config_extra={"global avoid override timeout": 5})
        r.AVOID_OVERRIDE_TIMEOUT = 5 * 60 * 1000
        r.AVOID_DIALOGS_TIMEOUT = 10 * 60 * 1000
        self.assertEqual(r._effective_override_ms(r.AVOID_DIALOGS_TIMEOUT), 5 * 60 * 1000)

    def test_disabled_specific_uses_global(self):
        r = make_routine(config_extra={"global avoid override timeout": 5})
        r.AVOID_OVERRIDE_TIMEOUT = 5 * 60 * 1000
        r.AVOID_DIALOGS_TIMEOUT = 0
        self.assertEqual(r._effective_override_ms(r.AVOID_DIALOGS_TIMEOUT), 5 * 60 * 1000)

    def test_both_disabled_no_override(self):
        r = make_routine()
        r.AVOID_OVERRIDE_TIMEOUT = 0
        r.AVOID_DIALOGS_TIMEOUT = 0
        self.assertEqual(r._effective_override_ms(r.AVOID_DIALOGS_TIMEOUT), 0)

    def test_global_override_lets_review_sync(self):
        # Review blocked, but global override (5 min) elapsed -> sync proceeds
        r = make_routine(config_extra={"global avoid override timeout": 5})
        r.AVOID_OVERRIDE_TIMEOUT = 5 * 60 * 1000
        r._last_activity_time = time.monotonic() - 6 * 60
        aqt_mod.mw.state = "review"
        with mock.patch.object(SyncRoutine, "_main_window_has_focus", return_value=False):
            self.assertTrue(r.is_good_state())
        aqt_mod.mw.state = "deckBrowser"


class FocusedIdleGraceTest(unittest.TestCase):
    def _routine(self, minutes):
        r = make_routine(config_extra={"idle sync focused timeout": minutes})
        r.IDLE_SYNC_FOCUSED_TIMEOUT = minutes * 60 * 1000
        return r

    def test_not_elapsed_before_timeout(self):
        r = self._routine(5)
        r._last_activity_time = time.monotonic() - 60
        self.assertFalse(r._focused_idle_grace_elapsed())

    def test_good_state_blocks_focused_without_grace(self):
        r = self._routine(0)
        with mock.patch.object(SyncRoutine, "_main_window_has_focus", return_value=True):
            self.assertFalse(r.is_good_state())

    def test_good_state_allows_focused_after_grace(self):
        r = self._routine(5)
        r._last_activity_time = time.monotonic() - 6 * 60
        with mock.patch.object(SyncRoutine, "_main_window_has_focus", return_value=True):
            self.assertTrue(r.is_good_state())


class InterruptionToggleTest(unittest.TestCase):
    def _no_focus(self):
        return mock.patch.object(SyncRoutine, "_main_window_has_focus", return_value=False)

    def test_review_off_allows_review_state(self):
        r = make_routine(config_extra={"avoid sync while reviewing": False})
        aqt_mod.mw.state = "review"
        with self._no_focus():
            self.assertTrue(r.is_good_state())
        aqt_mod.mw.state = "deckBrowser"

    def test_review_on_blocks_review_state(self):
        r = make_routine()
        aqt_mod.mw.state = "review"
        with self._no_focus():
            self.assertFalse(r.is_good_state())
        aqt_mod.mw.state = "deckBrowser"

    def test_dialogs_off_allows_open_dialog(self):
        r = make_routine(config_extra={"avoid sync when dialogs open": False})
        aqt_mod.dialogs._dialogs = {"Browser": (None, True)}
        with self._no_focus():
            self.assertTrue(r.is_good_state())
        aqt_mod.dialogs._dialogs = {}

    def test_dialog_list_blocks_matching_window(self):
        r = make_routine()
        aqt_mod.dialogs._dialogs = {"Browser": (None, True)}
        with self._no_focus():
            self.assertFalse(r.is_good_state())
        aqt_mod.dialogs._dialogs = {}

    def test_dialog_list_allows_unlisted_window(self):
        r = make_routine(config_extra={"avoid dialogs list": ["DeckStats"]})
        aqt_mod.dialogs._dialogs = {"Browser": (None, True)}
        with self._no_focus():
            self.assertTrue(r.is_good_state())
        aqt_mod.dialogs._dialogs = {}

    def test_hidden_dialog_registry_entry_does_not_block(self):
        r = make_routine()
        hidden_dialog = mock.Mock()
        hidden_dialog.isVisible.return_value = False
        aqt_mod.dialogs._dialogs = {"AddCards": (None, hidden_dialog)}
        with self._no_focus():
            self.assertTrue(r.is_good_state())
        aqt_mod.dialogs._dialogs = {}

    def test_visible_dialog_registry_entry_blocks(self):
        r = make_routine()
        visible_dialog = mock.Mock()
        visible_dialog.isVisible.return_value = True
        aqt_mod.dialogs._dialogs = {"AddCards": (None, visible_dialog)}
        with self._no_focus():
            self.assertFalse(r.is_good_state())
        aqt_mod.dialogs._dialogs = {}

    def test_focus_off_allows_focused(self):
        r = make_routine(config_extra={"avoid sync when main window focused": False})
        with mock.patch.object(SyncRoutine, "_main_window_has_focus", return_value=True):
            self.assertTrue(r.is_good_state())


if __name__ == "__main__":
    unittest.main()
