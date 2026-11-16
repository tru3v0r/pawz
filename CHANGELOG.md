# Changelog

Every notable change to pawz, by version. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/): while pawz is in 0.x, the middle number goes up with each new feature and the last one with fixes. What comes next is in the [roadmap](docs/ROADMAP.md).

New entries go under **Unreleased**; `scripts/bump-version.py` turns that section into a version (see the [developer guide](docs/DEVELOPER.md#versions-and-releases)).

## [Unreleased]

## [0.1.0] - 2026-11-15

The first tagged version, covering everything built so far.

### Controlling the PC
- The left stick moves the pointer and the right stick scrolls, with dead zones, sensitivity per profile and an editing layer (ZL held).
- Shortcuts for each profile, application and website (per-site shortcuts need the browser extension for Firefox, Chrome, Edge and Brave).
- Default shortcuts for browsers (tabs), YouTube and VLC (play-pause, full screen, subtitles, and the right stick pushed sideways to jump back or forward).
- Magnetic window edges and buttons.
- Game mode, which steps aside when a game is in the foreground or with − and + held together.
- HOME held on the primary controller opens pawz.

### Controllers
- Detection by USB id and name; Xbox, PlayStation, Nintendo, Steam and generic controllers, each with button prompts for its family.
- Detailed drawings of each controller, lighting up held buttons, moved sticks and touchpad fingers live; a medallion for inputs the drawing does not show.
- A primary controller (the crown), forgetting disconnected controllers, profiles assigned per controller.
- Imported SVG drawings, with automatic detection of their inputs.

### Interface
- Interface in 30 languages, Arabic and Sorani Kurdish right to left, each with its estimated translation quality and an invitation to improve it.
- Six colour themes (Comfy Turquoise, Corporate Blue, Danger Red, Cheeky Green, Juicy Orange, Squishy Purple), changed live without a restart.
- Four controller drawing styles (Eye Candy, Dark, Light, Original).

### Project
- Everything pawz knows that is content rather than logic (shortcuts, applications, actions, controllers, themes, languages) is in JSON files under `src/pawz/data`, each checked against a JSON Schema.
- A Windows build of about 70 MB, checked by the test suite and a smoke test of the executable.

[Unreleased]: https://github.com/tru3v0r/pawz/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tru3v0r/pawz/releases/tag/v0.1.0
