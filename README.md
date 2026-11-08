# HazeAudio  v1.1

Drag-and-drop audio player with a glassmorphism UI. Windows desktop app; end users need nothing installed.

## Build the app (Windows)
1. Install **Python 3.12 (64-bit)** from python.org (tick "Add to PATH").
2. Double-click **build.bat**.
3. Result: `dist\HazeAudio\HazeAudio.exe` (portable folder: zip and share it).
4. Optional: install **Inno Setup 6** (free) first and build.bat also produces `installer\HazeAudio-Setup-1.1.0.exe`.

No Python on your PC? Push this folder to GitHub and run the **Build Windows app** workflow.

## Features
- Drag and drop files, folders or .m3u/.m3u8 playlists anywhere on the window
- **Live spectrum visualizer** on the cover art (pure Python, no extra dependencies)
- **Themes**: Haze, Ocean, Sunset, Forest, Rose, Graphite, Frost (light) + optional **colors from album art**
- **Mini-player** (▭), **system tray** (keeps playing when closed), **global media keys** (Windows)
- Playlist: drag to reorder, search (Ctrl+F), right-click menu (Play, Play next, Show in folder, Remove), open/save M3U, sort A-Z
- Sleep timer (10-second fade-out), soft fade on pause/resume, output-device picker
- Remembers playlist, track **and position**, volume, theme, window position and all options
- "Open with" support and single-instance (double-clicking a song uses the open window)

Shortcuts: Space play/pause, Left/Right seek 5 s, Up/Down volume, Delete remove track, Ctrl+F search.

## Keeping it working for years
- The first build writes **requirements.lock** (exact versions). Commit it; later builds use it.
- Everything is bundled: users install nothing. Audio decoding ships inside Qt (FFmpeg).
- One third-party library (Qt for Python, LGPL). Needs Qt 6.8+ for the visualizer; older Qt still plays, minus the visualizer.
- Upgrade on purpose: edit requirements.txt, delete requirements.lock, rebuild, test, commit the new lock.
- Release: bump `AppVersion` in installer.iss and `VERSION` in haze_audio.py.

## Where things live
- Settings and playlist: `%APPDATA%\HazeAudio\state.json`
- Crash log (send this with bug reports): `%APPDATA%\HazeAudio\error.log`

## Known limits
- No equalizer, crossfade or gapless playback: Qt's player has no audio-processing hooks. These need a different audio engine.
- Global media keys take over Play/Pause/Next/Previous system-wide while HazeAudio runs. Turn off in Settings (⚙) if another app should keep them.
- Unsigned apps trigger Windows SmartScreen ("More info > Run anyway"). A code-signing certificate fixes that.
