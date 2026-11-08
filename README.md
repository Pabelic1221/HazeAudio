# HazeAudio

Drag-and-drop audio player with a glassmorphism UI. Windows desktop app, no install of Python needed by end users.

## Build the app (Windows)
1. Install **Python 3.12 (64-bit)** from python.org (tick "Add to PATH").
2. Double-click **build.bat**.
3. Result: `dist\HazeAudio\HazeAudio.exe` (portable folder: zip and share it).
4. Optional: install **Inno Setup 6** (free) first and build.bat also produces `installer\HazeAudio-Setup-1.0.0.exe`.

No Python on your PC? Push this folder to GitHub and run the **Build Windows app** workflow: it builds the exe and installer in the cloud.

## Keeping it working for years
- The first build writes **requirements.lock** (exact versions). Commit it. Later builds use it, so the app builds the same way in 2030 as today.
- Everything is bundled into the app folder: users need nothing installed. Audio decoding ships inside Qt (FFmpeg), not from the user's PC.
- Only 1 third-party library (Qt for Python, LGPL). Keep the dependency list this short.
- Upgrade on purpose: change versions in requirements.txt, delete requirements.lock, rebuild, test, commit the new lock.
- To release: bump `AppVersion` in installer.iss, rebuild.

## Where things live
- Settings and playlist: `%APPDATA%\HazeAudio\state.json`
- Crash log (send this when reporting a bug): `%APPDATA%\HazeAudio\error.log`

## If Windows SmartScreen warns on first run
Unsigned apps trigger "unknown publisher". Fix long-term with a code-signing certificate; short-term, "More info > Run anyway".
