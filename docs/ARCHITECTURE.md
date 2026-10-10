# Architecture

## Principle

Providers return structured results and actions; they never control the launcher's layout. The core routes queries, ranks results, cancels stale work, and records history. The frontend renders whatever arrives. This separation lets us swap the backend, add another desktop environment, or rebuild the UI without touching providers.

## Flow

```
Global shortcut (hyprctl eval Lua, runtime-registered, config file untouched)
        |
        v
Quickshell interface (QML)
  Search input · Results · Action panel · Preview
        |
        v  (NDJSON over stdio)
Provider host (Python)
  Query routing · Ranking · Cancellation · History
        |
        +-- Applications     (.desktop entries)
        +-- Windows          (hyprctl -j)
        +-- Calculator
        +-- Script commands  (user-declared)
        +-- Focused-app menus (AT-SPI over D-Bus)
        +-- Omarchy actions  (optional adapter)
```

## Adapters

- `adapters/hyprland/` — window discovery, focus, workspaces, runtime keybinding registration via `hyprctl eval`, re-registered after each config reload (Hyprland drops runtime bindings on reload; MaNi4's plugin demonstrated this approach).
- `adapters/omarchy/` — optional: Omarchy commands, configuration, theming. Not required by the core.

## Menu-search provider (port plan)

MaNi4's `bin/search-menu-items` walks the focused app's accessibility tree over raw D-Bus:

- `org.a11y.atspi.Accessible` — tree structure
- `org.a11y.atspi.Action` — invokable menu actions
- `org.a11y.atspi.Application`
- `org.gtk.Actions` — GTK menu export

The focused window is resolved via `hyprctl -j`. UnknownMethod / UnknownInterface D-Bus errors are expected and swallowed — coverage varies by toolkit (GTK best, Qt partial, Chromium and Electron need accessibility flags enabled). Port the walker as a provider, keeping the pure-logic/model split so search and ranking stay testable outside the UI.

## Interface views

Search to Results to Action panel, with tool views for list+preview, grid, form, detail, and conversation (later). Providers request a view by type; the frontend renders it — extension authors never implement keyboard navigation or theming.
