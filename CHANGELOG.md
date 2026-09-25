# Changelog

All notable changes to **Background Auto Sync for Anki** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [5.0.3] - 2026-09-25

### Fixed
- **Background sync no longer moves the Anki window backward in the Z-order.** The post-sync restore called `mw.lower()`, which dropped the main window to the very bottom of the stack, hiding it behind windows that had been below it. Restore now never raises or lowers anything: it only re-minimizes/re-hides if the sync actually changed that, and hands focus back to another Anki window if it was stolen ([#4](https://github.com/athulkrishna2015/Background-Auto-Sync-for-Anki-Addon/issues/4)).
- **Window-restore tests** added for background, minimized, hidden, and focus-stolen cases.

### Changed
- **Dialog blocking is now unconditional** — auto-sync waits until the listed windows are closed instead of resuming after the grace timeout, which could fire a full sync mid-browsing and stall the UI on low-memory systems.

## [5.0.2] - 2026-08-15

### Added
- **Support tab opens automatically** after the add-on is updated.

## [5.0.1] - 2026-08-15

### Fixed
- **Stale dialog detection** — Hidden or closed dialog objects retained by Anki's dialog registry no longer block background sync. Only visible dialog windows are treated as open.
- **Dialog detection tests** added for visible and hidden registry entries.

## [5.0.0] - 2026-08-15

### Added
- **Session log file** written to `auto_sync.log`, cleared when Anki starts for easier bug investigation.
- **Effective override logging** showing the actual grace period after applying the global override.

### Changed
- **Settings UI reorganized** into one compact, scrollable Settings tab with grouped Sync behavior, Interruption avoidance, and Background and network sections.
- **Interruption controls** now use consistent two-column form rows, with setting names on the left and controls on the right.
- **Dialog interruption controls** remain grouped with their selected window types and per-condition grace period.
- **Blocked-state logging** now throttles repeated waiting messages to reduce session-log noise.
- **Blocked-window messages** use singular/plural wording correctly.
- **Test coverage** expanded for waiting-log throttling and effective override reporting.

### Fixed
- **Manual syncs no longer drop Anki behind other windows.** Window-state restore now only runs for background syncs initiated by the addon; pressing the Sync button retains focus normally.
- **Changes made during a session are no longer lost on quit.** A final sync runs before Anki closes (only when there is a change to upload and internet is available).
- **Removed dead `AutoSyncLogDialog` code** that referenced a nonexistent method (would crash if ever used).
- **Conflict-resolution combo is now correctly reset** by the "Reset Defaults" button without firing redundant writes.

### Added
- **"On sync conflict" option** to force a one-way sync direction (`AnkiWeb → local` or `local → AnkiWeb`) instead of prompting, so the automated pipeline keeps working when a full-sync conflict occurs. Off by default.
- **Unit tests** for config migration/sanitization, forced conflict resolution, change detection, sync-on-close, and the manual-sync window-state gate (24 tests, mock-based, no running Anki required).

### Changed
- **Activity listener no longer reacts to mouse movement** (clicks/keys only), reducing overhead and log spam during review.
- **Repeated "Can't start sync timer" messages are throttled** so they only log when the blocking reason changes.
- **Explanatory note added** under the "Strictly avoid interruptions" option clarifying when auto-sync runs vs. is deferred.
- **Sync log panel is collapsed by default** and toggled via the "Sync Log" header.

## [4.1.1] - 2026-04-28

### Fixed
- **`PoisonError` crash** — Background sync could crash the main Anki thread if it encountered a network or server error during the sync process, by delaying the scheduler load until after the sync future resolves.

## [4.1.0] - 2026-04-20

### Added
- **Option to completely disable the pre-sync internet connectivity check** (useful on extremely restrictive firewalls).

### Changed
- **Default internet connectivity ping** switched to HTTPS **Port 443** instead of TCP Port 53, eliminating false-negative "offline" errors on strict corporate and university networks.

### Documentation
- Improved rendering compatibility for AnkiWeb by using standard bulleted lists.

## [4.0.4] - 2026-03-27

### Documentation
- Added strict limitations regarding the **Undo queue** and **multi-device sync conflicts**.
- Reordered the README (Support and License sections moved above the changelog).

## [4.0.2] - 2026-03-26

### Fixed
- **Focus stealing** — Background syncs no longer interrupt your workflow by un-minimizing Anki or bringing it to the foreground.

### Changed
- Added AnkiWeb add-on link and bumped version.

## [4.0.1] - 2026-03-26

### Fixed
- **`NameError` crash** — Missing `CONFIG_` variables in `config.py`.

### Changed
- **Idle-before-sync delay** increased to 2 minutes for safety.
- **UI:** Grayed out and disabled unused sync timers when "Change Only" mode is enabled.

### Added
- **UI:** "Reset to Defaults" button in the configuration menu.

## [4.0.0] - 2026-03-26

Initial release of **Background Auto Sync for Anki**.

### Added
- **True background sync** — If Anki is minimized it stays minimized; if another app has focus, Anki won't steal it.
- **Periodic sync** after a configurable period of inactivity.
- **Idle periodic sync** to pick up changes from AnkiWeb / mobile while away.
- **Change detection** — only syncs when the collection has actually been modified.
- **Idle-before-sync delay** — waits for user inactivity after a change before syncing.
- **Strictly avoid interruptions** — won't sync while reviewing, browsing, or with Anki focused.
- **Log window** with timestamped sync activity for debugging.
- **Options dialog** and **Support** tab (Ko-fi, UPI, Bitcoin, Ethereum).

### Changed
- **Rename** to "Background Auto Sync" (fork of *Auto-Sync-Anki-Addon* by Robin-Haupt-1).
- **Ported to PyQt6**.
- **Defaults:** Idle Sync off, Only Sync on Changes on.

---

## Version History (tags)

| Version | Date       | Release notes                              |
|---------|------------|--------------------------------------------|
| v4.1.1  | 2026-04-28 | Bug fixes (PoisonError)                    |
| v4.1.0  | 2026-04-20 | Disable internet check option; HTTPS ping  |
| v4.0.4  | 2026-03-27 | Documentation (undo/conflict warnings)     |
| v4.0.2  | 2026-03-26 | Focus-stealing fix                         |
| v4.0.1  | 2026-03-26 | NameError fix; UI polish                   |
| v4.0.0  | 2026-03-26 | Initial release                            |
