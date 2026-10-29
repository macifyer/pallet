# menus provider

Search and invoke menu items of the focused application, over AT-SPI.
Adapted from [MaNi4/omarchy-search-menu-items](https://github.com/MaNi4/omarchy-search-menu-items) (MIT).

## Port scope

- Included: frame finding, level-at-a-time tree fetches, menu item collection, DoAction invocation, per-window walk cache.
- Deferred: button fallback (apps without menu bars), `org.gtk.Actions` export, multi-frame title disambiguation, Chromium `--force-renderer-accessibility` prompter.

## Latency

- Walks run on a single worker thread with a 1.2 s total budget, so stdin
  (searches, cancels) is never blocked.
- Cache-first: a window with a cached tree answers instantly; trees older
  than 8 s are re-walked in the background (stale-while-revalidate); up to
  16 windows are kept.
- Cold window: the search waits for the walk and is answered when it
  finishes, unless it was cancelled or superseded (only the newest query
  per window waits).
- The host's `warm` op (sent when the overlay opens) starts the walk for the
  focused window before the first keystroke.
- Missing `gi` or accessibility bus: the provider stays up and answers with
  no results (logged once) instead of crashing and showing up as
  "unavailable" on every query.

## Requirements

- `python-gobject` (the `gi` module)
- AT-SPI enabled (Omarchy/GNOME desktops have it on; the walker can also flip org.a11y.Bus per-session, M3)

## Protocol notes

Speaks the full PROVIDERS.md protocol. `custom` actions ride back to this provider via the host's `execute` op. The action carries the window address, menu path and label; the provider presses only an item that still matches all three in the focused window (a re-walk between search and Enter can never press a different item) and replies `executed:false` with an `error` otherwise. Scores are deliberately sub-0.55 so app launches (0.9 range) outrank menu items on shared queries.
