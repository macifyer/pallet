# Pallet

A keyboard-driven command palette for Arch/Hyprland built on Quickshell. Summon it, type, act — applications, windows, calculation, script commands, and the focused application's own menu items via AT-SPI.

**Status:** scaffold. Architecture designed, implementation beginning.

## Stack

- **Frontend:** Quickshell / QML
- **Core (prototype):** Python, JSON over stdio
- **Compositor:** Hyprland (windows, focus, runtime keybindings via `hyprctl eval`)
- **Optional adapter:** Omarchy (theming, commands)

## Layout

```
shell/      Quickshell QML (window, search, results, action panel)
src/        Python core (registry, ranking, settings)
providers/  One directory per provider
adapters/   hyprland/ and optional omarchy/
docs/       architecture + provider protocol
```

## Milestones

1. The loop — shortcut, search, ranked results, select, execute, close (apps, calculator, one script provider)
2. Action panel — open / copy / reveal / alternate actions
3. Menu search — focused app menus via AT-SPI (port of MaNi4's walker, MIT)
4. Persistent tools — clipboard history, snippets, timers, file search
5. Provider SDK — templates, installation, diagnostics
6. Workflows and AI — reviewable, confirmable actions

## Security posture

- Providers run as subprocesses with declared commands; never unrestricted QML plugins.
- Search text is never executed as a shell command.
- Clipboard storage is opt-in with explicit controls.
- AI proposes actions; humans confirm them.

## Credits

- [MaNi4/omarchy-search-menu-items](https://github.com/MaNi4/omarchy-search-menu-items) (MIT) — AT-SPI menu walking and pure-model test pattern
- [bjarneo/omarchy-shell-plugins](https://github.com/bjarneo/omarchy-shell-plugins) (MIT) — Omni palette reference
- Raycast, Vicinae, Wox, Ueli — inspiration only (Vicinae is GPL-3.0; its code is not used)
