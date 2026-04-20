# [Background Auto Sync for Anki](https://github.com/athulkrishna2015/Background-Auto-Sync-for-Anki-Addon)

Automatically syncs your Anki collection in the background — without stealing focus, raising windows, or interrupting your workflow.

Install from anki [web](https://ankiweb.net/shared/info/226796325)

This addon is a fork of [Auto-Sync-Anki-Addon by Robin-Haupt-1](https://github.com/Robin-Haupt-1/Auto-Sync-Anki-Addon).

## Features

- **True background sync** — If Anki is minimized, it stays minimized. If another app has focus, Anki won't steal it. The sync happens silently.
- **Periodic sync** — Automatically syncs after a configurable period of inactivity (default: 1 minute after last interaction).
- **Idle periodic sync** — While you're away, keeps syncing periodically (default: Off) to pick up changes from AnkiWeb, mobile, or other devices.
- **Change detection** — Only syncs when the collection has actually been modified (cards added, reviewed, edited). Stops wasting bandwidth when nothing changed (enabled by default).
- **Idle-before-sync delay** — When a change is detected, waits for a configurable idle period before syncing, so it doesn't interrupt an active editing session (default: 2 minutes).
- **Strictly avoid interruptions** — Won't sync while you're reviewing cards, browsing, or have any Anki dialog open (enabled by default).
- **Log window** — View a timestamped log of all sync activity for debugging.

## Important Considerations

- **Undo Queue:** Syncing terminates Anki's "undo" queue. Periodic sync may mean that if you take a break and return, you won't be able to undo actions performed just before the break.
- **Sync Conflicts:** Auto-syncing on one device while actively using, editing, or studying on another device can lead to sync conflicts. 
- **Idle Periodic Sync:** Using "Idle periodic sync" while leaving Anki open may cause issues, especially if other add-ons with background activity are installed.

## Installation

1. Download the latest `.ankiaddon` from [Releases](../../releases).
2. In Anki, go to **Tools → Add-ons → Install from file…** and select the downloaded file.
3. Restart Anki.

Or install via AnkiWeb addon code (226796325).

## Configuration

Go to **Tools → Background Auto Sync Options…** to configure:

- **Sync after** (Default: 1 minute) — Minutes of inactivity before triggering a sync *(disabled if Change mode is On)*
- **When idle, sync every** (Default: Off) — Periodic sync interval while Anki is idle *(disabled if Change mode is On)*
- **Strictly avoid interruptions** (Default: ✅ On) — Skip sync during reviews, browsing, or when Anki has focus
- **Only sync when changes detected** (Default: ✅ On) — Skip idle periodic syncs if no local changes since last sync
- **Wait idle before syncing after change** (Default: 2 minutes) — After detecting a change, wait this long idle before syncing
- **Disable pre-sync internet check** (Default: ❌ Off) — Skip the connectivity check and trigger sync immediately (useful on extremely restrictive firewalls)

*Tip: You can restore these optimal defaults at any time using the **Reset Defaults** button in the options menu.*
<img width="896" height="484" alt="Screenshot_20260326_194454" src="https://github.com/user-attachments/assets/8ffc01e1-c339-47c6-b764-ecf8ebeb0f5a" />

## Background Sync Behavior

The addon ensures syncs **never interrupt your work**:

- If Anki is **minimized** → stays minimized during and after sync
- If Anki is **behind other windows** → stays behind, doesn't raise to foreground
- If **another app** has focus → Anki won't steal focus
- Window state is saved before sync and restored after sync completes

## How It Works

1. After user activity in Anki, a countdown timer starts.
2. Once the idle timeout expires, the addon checks:
   - Is Anki in a "safe" state? (no dialogs open, not reviewing, etc.)
   - Is there internet connectivity?
   - If change-only mode: has the collection been modified?
3. Window state is saved (minimized? focused? background?).
4. Sync triggers via Anki's built-in sync.
5. After sync completes, window state is restored exactly.
6. The cycle restarts.

## Support

If you find this add-on useful, please consider supporting its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/D1D01W6NQT)

## License

GPL-3.0 — see [LICENSE.txt](LICENSE.txt).

## Changelog

### 2026-04-20
- **Feature:** Added an option to completely disable the pre-sync internet connectivity check.
- **Improved:** Switched the default internet connectivity ping to use HTTPS Port 443 instead of TCP Port 53, eliminating false-negative "offline" errors on strict corporate and university networks.

### 2026-04-14
- **Documentation:** Improved rendering compatibility for AnkiWeb by using standard bulleted lists.

### 2026-03-27
- **Documentation:** Added strict limitations to README regarding the Undo queue and multi-device sync conflicts.
- **Support:** Added Ko-fi donation support links.

### 2026-03-26
- **Bug Fix:** Completely resolved the "focus stealing" issue where background syncs would interrupt your workflow by un-minimizing Anki or bringing it to the foreground.
- **UI:** Added a "Reset to Defaults" button in the configuration menu.
- **UI:** The settings menu now dynamically grays out and disables unused sync timers when "Change Only" mode is toggled.
- **Bug Fix:** Fixed a startup `NameError` crash due to missing configuration variables.
- **Documentation:** Major README refresh with explicit AnkiWeb installation instructions and UI behavior notes.


