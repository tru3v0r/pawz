# pawz

A Windows app that lets you control your entire PC with a gamepad. 🐾

Pointer and scrolling on the sticks, shortcuts per profile, per application and per website, magnetic window edges and buttons, an editing layer and a game mode that steps aside for games. The main window shows each controller with its held buttons lit up live; the interface comes in 30 languages (Arabic and Sorani Kurdish right to left), with three colour themes.

**Platform: Windows 10/11 · Python 3.12 · status: prototype (0.1.0).**

## Run from source

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-windows.ps1
```

The scripts use a per-machine Python environment, `%LOCALAPPDATA%\pawz\venv-py312`, outside any synced folder (override with `PAWZ_VENV_DIR`).

## Build the executable

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

The script installs the dependencies into that environment, runs the tests, builds `dist\pawz\pawz.exe` (about 70 MB) and starts it once to check it. It stops at the first error.

## Quality checks

```powershell
$py = "$env:LOCALAPPDATA\pawz\venv-py312\Scripts\python.exe"
& $py -m pytest -q
& $py -m ruff check .
```

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Controllers, mappings and profiles](docs/CONTROLLERS.md)
- [Developer guide](docs/DEVELOPER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Bundled assets and their licences](docs/ASSETS.md)

## Licence

GPL-3.0-or-later (see `LICENSE`).
