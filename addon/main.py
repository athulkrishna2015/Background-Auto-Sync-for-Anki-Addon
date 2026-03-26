from aqt import gui_hooks, mw
from aqt.qt import QAction
from .config import AutoSyncConfigManager
from .log_window import LogManager
from .options_dialog import on_options_call
from .sync_routine import SyncRoutine

sync_routine = None
config_manager = None
log_manager = None


_action_added = False


def _remove_sync_hooks(routine):
    if routine is None:
        return
    for hook, callback in (
        (gui_hooks.sync_will_start, routine.sync_initiated),
        (gui_hooks.sync_did_finish, routine.sync_finished),
    ):
        try:
            hook.remove(callback)
        except ValueError:
            pass


def init():
    # declare variables as global so they won't be garbage collected
    global sync_routine, config_manager, log_manager, _action_added

    if sync_routine is not None:
        sync_routine.cleanup()
        _remove_sync_hooks(sync_routine)

    # set up config manager, log manager and sync routine
    log_manager = LogManager()
    config_manager = AutoSyncConfigManager(mw)
    sync_routine = SyncRoutine(config_manager, log_manager)

    # listen to sync activity
    gui_hooks.sync_will_start.append(sync_routine.sync_initiated)
    gui_hooks.sync_did_finish.append(sync_routine.sync_finished)

    # add options entry to Anki menu
    if not _action_added:
        options_action = QAction("Auto Sync Options ...", mw)
        options_action.triggered.connect(on_menu_action)
        mw.form.menuTools.addAction(options_action)
        _action_added = True


def on_menu_action():
    if config_manager and sync_routine and log_manager:
        on_options_call(config_manager, sync_routine, log_manager)


def on_profile_will_close(*args):
    global sync_routine, config_manager, log_manager
    if sync_routine is not None:
        sync_routine.cleanup()
        _remove_sync_hooks(sync_routine)
    sync_routine = None
    config_manager = None
    log_manager = None


gui_hooks.profile_did_open.append(init)
gui_hooks.profile_will_close.append(on_profile_will_close)
