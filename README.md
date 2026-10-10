# Pallet

A keyboard-driven command palette for Omarchy on Arch/Hyprland, built on Quickshell. Summon it, type, act — applications, windows, calculation, script commands, and the focused application's own menu items via AT-SPI.

**Status:** early but daily-drivable. App search, fuzzy ranking, theme icons, and focused-app menu search work; more providers land next.

## Install (Omarchy Quattro)

```sh
omarchy plugin add https://github.com/macifyer/pallet.git --enable
```

That's it — Pallet registers its own hotkey: ALT+SPACE toggles the palette, leaving SUPER+SPACE on the built-in Omarchy menu. If ALT+SPACE is already bound on your system, Pallet logs a warning in the shell log instead of overriding it; bind `omarchy-shell shell toggle io.github.macifyer.pallet` to a key of your choice in that case.

## Update

Installed from git:

```sh
omarchy plugin update io.github.macifyer.pallet
```

Symlinked for development (recommended while hacking):

```sh
ln -s ~/Projects/pallet ~/.config/omarchy/plugins/io.github.macifyer.pallet
omarchy-shell shell rescanPlugins && omarchy plugin enable io.github.macifyer.pallet
# from then on: git pull; the shell auto-reloads on save
```

See docs/PLUGIN.md for the lifecycle contract, validation, and publish checklist. Standalone development (any Quickshell setup) is covered in shell/README.md.

## Stack

- **Frontend:** Quickshell / QML
- **Core (prototype):** Python, JSON over stdio
- **Compositor:** Hyprland (windows, focus, runtime keybindings via `hyprctl eval`)
- **Integration:** Omarchy shell plugin (kinds: overlay + service)

## Layout

```
manifest.json      Omarchy plugin contract
PalletOverlay.qml  overlay entry point (summon/hide -> open/close)
PalletService.qml  service entry point (self-registering ALT+SPACE hotkey)
shell/             Quickshell QML (window, search, results, actions)
src/               Python core (provider host: fanout, merge, cancel)
providers/         One directory per provider (apps, menus, ...)
docs/              architecture + provider protocol + plugin guide
```

## Milestones

1. ~~The loop~~ — shortcut, search, ranked results, select, execute, close
2. Action panel — open / copy / reveal / alternate actions
3. ~~Menu search~~ — focused app menus via AT-SPI (port of MaNi4's walker, MIT); deeper coverage next
4. Persistent tools — clipboard history, snippets, timers, file search
5. Hyprland + Omarchy providers — window switching, system actions, packages
6. Workflows and AI — reviewable, confirmable actions

## Security posture

- Providers run as subprocesses with declared commands; never unrestricted QML plugins.
- Search text is never executed as a shell command.
- Privileged or destructive actions get visible confirmation; nothing silent with sudo.
- Clipboard storage is opt-in with explicit controls.
- AI proposes actions; humans confirm them.

## Credits

- [MaNi4/omarchy-search-menu-items](https://github.com/MaNi4/omarchy-search-menu-items) (MIT) — AT-SPI menu walking, hotkey registration pattern, and pure-model test pattern
- [bjarneo/omarchy-shell-plugins](https://github.com/bjarneo/omarchy-shell-plugins) (MIT) — Omni palette reference
- Raycast, Vicinae, Wox, Ueli — inspiration only (Vicinae is GPL-3.0; its code is not used)
