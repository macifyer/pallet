# menus provider

Search and invoke menu items of the focused application, over AT-SPI.
Adapted from [MaNi4/omarchy-search-menu-items](https://github.com/MaNi4/omarchy-search-menu-items) (MIT).

## Port scope

- Included: frame finding, level-at-a-time tree fetches, menu item collection, DoAction invocation, 4s per-window walk cache.
- Deferred: button fallback (apps without menu bars), `org.gtk.Actions` export, multi-frame title disambiguation, Chromium `--force-renderer-accessibility` prompter.

## Requirements

- `python-gobject` (the `gi` module)
- AT-SPI enabled (Omarchy/GNOME desktops have it on; the walker can also flip org.a11y.Bus per-session, M3)

## Protocol notes

Speaks the full PROVIDERS.md protocol. `custom` actions ride back to this provider via the host's `execute` op: it presses the cached menu item by id. Scores are deliberately sub-0.55 so app launches (0.9 range) outrank menu items on shared queries.
