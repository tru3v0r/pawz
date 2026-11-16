# pawz — Roadmap

Where pawz is going, one version at a time. It is a plan, not a promise: versions can move, merge or split as work shows what is needed. What each released version actually contains is in the [changelog](../CHANGELOG.md).

## How versions are numbered
- **0.x**: pawz is a prototype. Settings, default shortcuts and data formats may still change between versions, with migration when a user's settings are affected.
- **0.MINOR.0**: a new feature, one milestone below.
- **0.x.PATCH**: fixes only.
- **1.0.0**: the first version meant to be relied on (see below).

## 0.2.0 — On-screen keyboard and finding the pointer
Typing without a keyboard: an address bar, a search, a file name. It comes first because the later features need it.
- A keyboard drawn by pawz over the active window, without taking focus away from it.
- A classic layout that follows the language: AZERTY by default in French and the other languages that use it, QWERTY in those that use QWERTY (and QWERTZ…), with layouts described in `data/`.
- Keys chosen with the stick or the D-pad, typed with a face button; shortcuts for space, backspace, Enter, Shift and closing.
- Opened by a shortcut, and offered automatically when a text field takes focus (if Windows reports it reliably).
- Keyboard languages, a setting in the Display tab under the interface language: the interface language by default, others can be added; the chosen languages are shown below the field as tags, each removable. A key on the keyboard switches from one language's layout to the next.

Typing modes, so each user can pick the one that suits them best. The mode is chosen in the settings; the classic keyboard is the default.
- **Classic**: the keys of the language's layout, as above.
- **Spiral**: the letters from A to Z laid out on a spiral. Left and right move along the spiral's thread; the spiral turns, and the selected letter always stays in the centre. Up and down jump to the next or previous arm. The alphabet has landmark letters: L + left or right jumps from one vowel to the next.
- **Flick**: inspired by Japanese flick input, where a key is pressed and pushed in a direction to choose among the characters it holds. For the kana, each key holds a consonant and the directions give its five vowels. **To decide**: an equivalent for the Latin alphabet, for example keys holding a group of letters, or keys built around the vowels.

Choosing a language:
- The language lists (interface and keyboard) can be searched by typing: only the matching languages stay, with the typed text shown in bold in their names.

Finding the pointer on a large or distant screen:
- Clicking the left stick draws circles in the theme's main colour that shrink onto the pointer, on any screen and at any scaling, without catching clicks.
- A new action, `locate_pointer`, bound to the left stick click by default; application and site shortcuts on that button (subtitles on YouTube and in VLC) keep priority.

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

## 0.5.0 — Spatial navigation with the D-pad
Moving between the buttons, links and fields of any window with the D-pad, as on a television: up, down, left, right go to the nearest element in that direction, A activates it.
- The elements come from what Windows reports about the active window (the same source as magnetic buttons), so it works in most applications and in web pages; games and applications that draw their own controls may expose nothing.
- The pointer jumps to the chosen element and the element is highlighted in the theme's colours.
- Experimental first, switched on in the settings. **To decide**: how it shares the D-pad with the arrow keys, which lists, menus and text fields need (a mode toggled by a shortcut, a choice per profile or per application, or arrows whenever a text field has focus).
- What Windows already offers, to lean on rather than duplicate: Tab and Shift+Tab move focus in an application's own order (not by direction); the arrows move inside menus, lists and dialogs; Windows' modern applications (UWP, WinUI: Settings, Store, Xbox) have their own directional navigation built for the gamepad; Chrome and Edge have an experimental "Spatial Navigation" flag for web pages. A lead: send plain arrows to applications that already navigate well with them, and use pawz's navigation only elsewhere.
- Must stay fast: finding the next element has to feel immediate even in large windows.

## Later
Ideas not yet placed in a version:
- Checking for new versions through GitHub releases, with the changelog shown in pawz.
- An installer, and starting with Windows offered at installation.

## 1.0.0 — Stable
- Installed by an installer, updated without losing settings.
- A settings file format that later 1.x versions keep reading.
- Every feature above tested on real controllers (see "Validation still to do on hardware" in the [developer guide](DEVELOPER.md)).
