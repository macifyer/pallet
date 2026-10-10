# Pallet

A keyboard-driven command palette for Omarchy on Arch/Hyprland, built on Quickshell. Summon it, type, act — applications, windows, calculation, script commands, and the focused application's own menu items via AT-SPI.

**Status:** early but daily-drivable. App search, fuzzy ranking, theme icons, and focused-app menu search work; more providers land next.

## Install (Omarchy Quattro)

```sh
omarchy plugin add https://github.com/macifyer/pallet.git --enable
```

Then bind a key in `hyprland.conf`:

```
bind = SUPER, K, exec, omarchy-shell shell summon io.github.macifyer.pallet '{}'
```

See docs/PLUGIN.md for development against the real shell and the publish checklist. Standalone development (any Quickshell setup) is covered in shell/README.md.

## Stack

- **Frontend:** Quickshell / QML
- **Core (prototype):** Python, JSON over stdio
- **Compositor:** Hyprland (windows, focus, runtime keybindings via `hyprctl eval`)
- **Integration:** Omarchy shell plugin (kind: overlay)

## Layout

```
manifest.json    Omarchy plugin contract (overlay kind)
PalletOverlay.qml  plugin entry point (summon/hide -> open/close)
shell/           Quickshell QML (window, search, results, actions)
src/             Python core (provider host: fanout, merge, cancel)
providers/       One directory per provider (apps, menus, ...)
docs/            architecture + provider protocol + plugin guide
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

- [MaNi4/omarchy-search-menu-items](https://github.com/MaNi4/omarchy-search-menu-items) (MIT) — AT-SPI menu walking and pure-model test pattern
- [bjarneo/omarchy-shell-plugins](https://github.com/bjarneo/omarchy-shell-plugins) (MIT) — Omni palette reference
- Raycast, Vicinae, Wox, Ueli — inspiration only (Vicinae is GPL-3.0; its code is not used)
