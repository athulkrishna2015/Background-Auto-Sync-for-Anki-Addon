# Background Auto Sync - Developer Notes

This repository contains the source for the **Background Auto Sync** Anki add-on.

## Project Structure

- `addon/`: Add-on package contents.
  - `__init__.py`: Entry point — imports `main`.
  - `main.py`: Initialization — sets up config, sync routine, hooks, and menu action.
  - `sync_routine.py`: Core sync logic — timer management, background sync with window-state preservation, change detection, user activity monitoring.
  - `config.py`: `AutoSyncConfigManager` — reads/writes config via Anki's collection config system.
  - `constants.py`: Config key constants, defaults, and the icon.
  - `options_dialog.py`: Options dialog UI — spinboxes and checkboxes for all settings.
  - `log_window.py`: Log manager and log viewer dialog.
  - `utils.py`: Utility functions (internet connectivity check).
  - `manifest.json`: Add-on metadata (name, version).
  - `VERSION`: Semantic version string.
- `bump.py`: Version helpers (`validate_version`, `sync_version`) and configurable semantic bumping (`major`/`minor`/`patch`, default `patch`).
- `make_ankiaddon.py`: Creates `.ankiaddon`; auto-bumps patch only when no explicit version is provided.
- `doc/`: Screenshots and documentation assets.

## Config System

Configuration is stored in Anki's collection config under the key `auto_sync_config`. Keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `sync timeout` | int (minutes) | 1 | Inactivity timeout before sync |
| `idle sync timeout` | int (minutes) | 0 | Periodic sync interval while idle (0 = Off) |
| `strictly avoid interruptions` | bool | true | Skip sync during reviews/dialogs/focus |
| `sync on change only` | bool | true | Only sync when `col.mod` has changed |
| `idle before sync` | int (minutes) | 10 | Idle wait after change before syncing |
| `config version` | int | 4 | Config schema version |

## Background Sync Architecture

The sync routine preserves window state around `mw.onSync()`:

1. **Before sync**: Saves `mw.isMinimized()`, `mw.isHidden()`, and `QApplication.activeWindow()`.
2. **After sync** (via `sync_did_finish` hook): Restores state — re-minimizes, lowers window, or re-activates the previously focused window.

Change detection uses `mw.col.mod` to track collection modifications. The timestamp is stored after each successful sync and compared before the next.

## Versioning Scheme

Version format is strictly:

```text
major.minor.patch
```

Behavior:

- `bump.py` validates semantic version format and syncs:
  - `manifest.json` keys: `version`, `human_version`
  - `addon/VERSION`
- `bump.py` can read current version and increment:
  - `patch`: `x.y.z` -> `x.y.(z+1)` (default)
  - `minor`: `x.y.z` -> `x.(y+1).0`
  - `major`: `x.y.z` -> `(x+1).0.0`
- `make_ankiaddon.py` behavior:
  - Without args: auto-bumps patch via `bump.py`, then packages.
  - With `<major.minor.patch>` arg: writes that version via `bump.py` sync helpers, then packages without bumping.

## Common Commands

Bump patch version:

```shell
python bump.py
```

Bump minor version:

```shell
python bump.py minor
```

Bump major version:

```shell
python bump.py major
```

Build `.ankiaddon` locally:

```shell
python make_ankiaddon.py
```

Build `.ankiaddon` with explicit version (no auto-bump):

```shell
python make_ankiaddon.py 2.0.0
```

Output naming format:

```text
Background_Auto_Sync_v<major.minor.patch>_<YYYYMMDDHHMM>.ankiaddon
```

## Local Testing With Symlink

Linux:

```shell
ln -s "$(pwd)/addon" ~/.local/share/Anki2/addons21/auto_sync_dev
```

Windows (PowerShell as admin):

```powershell
New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Anki2\addons21\auto_sync_dev" -Target "$pwd\addon"
```
