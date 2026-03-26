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

## Installation

1. Download the latest `.ankiaddon` from [Releases](../../releases).
2. In Anki, go to **Tools → Add-ons → Install from file…** and select the downloaded file.
3. Restart Anki.

Or install via AnkiWeb addon code (if published).

## Configuration

Go to **Tools → Background Auto Sync Options…** to configure:

| Option | Default | Description |
|---|---|---|
| **Sync after** | 1 minute | Minutes of inactivity before triggering a sync *(disabled if Change mode is On)* |
| **When idle, sync every** | Off | Periodic sync interval while Anki is idle *(disabled if Change mode is On)* |
| **Strictly avoid interruptions** | ✅ On | Skip sync during reviews, browsing, or when Anki has focus |
| **Only sync when changes detected** | ✅ On | Skip idle periodic syncs if no local changes since last sync |
| **Wait idle before syncing after change** | 2 minutes | After detecting a change, wait this long idle before syncing |

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

## License

GPL-3.0 — see [LICENSE.txt](LICENSE.txt).
