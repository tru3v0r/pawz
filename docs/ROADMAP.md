# pawz — Roadmap

Where pawz is going, one version at a time. It is a plan, not a promise: versions can move, merge or split as work shows what is needed. What each released version actually contains is in the [changelog](../CHANGELOG.md).

## How versions are numbered
- **0.x**: pawz is a prototype. Settings, default shortcuts and data formats may still change between versions, with migration when a user's settings are affected.
- **0.MINOR.0**: a new feature, one milestone below.
- **0.x.PATCH**: fixes only.
- **1.0.0**: the first version meant to be relied on (see below).

## 0.2.0 — On-screen keyboard
Typing without a keyboard: an address bar, a search, a file name. It comes first because the later features need it.
- A keyboard drawn by pawz over the active window, without taking focus away from it.
- A layout that follows the interface or Windows language (AZERTY, QWERTY, QWERTZ…), with layouts described in `data/`.
- Keys chosen with the stick or the D-pad, typed with a face button; shortcuts for space, backspace, Enter, Shift and closing.
- Opened by a shortcut, and offered automatically when a text field takes focus (if Windows reports it reliably).

## 0.3.0 — Feature wheel
A view opened from the controller: the pawz logo in the middle, circles around it for handy features, chosen with the stick.
- First circles: Applications, Favourites, Keyboard, Media and volume, Game mode, Settings.
- The circles, their order, icons and actions described in `data/`, so new ones need no code.
- Themed like the rest of the interface, in every language.
- **To decide**: which button opens it. HOME already sends the Windows key and, held, opens pawz; on Windows it may also open the Xbox Game Bar. Options: HOME pressed alone (and the Windows key moved elsewhere), HOME held (and the settings moved into the wheel), or another combination.

## 0.4.0 — Applications and favourites
What the wheel's Applications and Favourites circles open.
- A launcher listing installed applications, with their icons, browsable with the controller.
- Favourites: applications, websites, folders and files, pinned, reordered and removed from the controller.

## Later
Ideas not yet placed in a version:
- Checking for new versions through GitHub releases, with the changelog shown in pawz.
- An installer, and starting with Windows offered at installation.

## 1.0.0 — Stable
- Installed by an installer, updated without losing settings.
- A settings file format that later 1.x versions keep reading.
- Every feature above tested on real controllers (see "Validation still to do on hardware" in the [developer guide](DEVELOPER.md)).
