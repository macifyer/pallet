# Pallet shell

The Quickshell/QML frontend.

## Run it

From the repo root:

    qs -p shell

Toggle the palette from another terminal:

    qs -p shell ipc call pallet toggle

Bind it in Hyprland (`hyprland.conf`):

    bind = SUPER, K, exec, qs -p /home/YOU/pallet/shell ipc call pallet toggle

(`-p` takes a path; symlink `shell/` into `~/.config/quickshell/pallet` to use `qs -c pallet` instead.)

## What works now (M1 slice)

- Overlay window, upper-center, click-outside dismiss, Esc closes
- Debounced search against the provider host over NDJSON stdio
- Client-side fuzzy ranking (`Fuzzy.js`, pure logic, node-testable)
- Keyboard loop: Up/Down navigate, Enter runs the first action
- `launch` / `open` / `copy` actions executed without a shell
- Freedesktop theme icons per result (absolute .desktop paths supported)

## Deliberately missing

- Action panel (alternate actions), previews, theming, window switching
- Hyprland runtime keybinding registration via `hyprctl eval` (M2) \u2014 bind statically for now
- `custom` action forwarding (M2)

## Notes

- Written against the Quickshell 0.2+ APIs (`SplitParser`, `IpcHandler`,
  `WlrLayershell`). Check https://quickshell.org/docs against your installed
  version before filing bugs against yourself.
- Icons resolve via `Quickshell.iconPath(name, true)`; if icons look wrong,
  check your active icon theme first. Do not build a raw filesystem icon
  index ahead of the themed lookup (see [basecamp/omarchy#7552](https://github.com/basecamp/omarchy/issues/7552)).
- `copy` actions shell out to `wl-copy` (package: wl-clipboard).
- `WlrLayershell.*` attached properties are Wayland-only; they sit alongside
  the platform-independent `focusable` / `aboveWindows` properties.
- A missing host process exits immediately; the stderr collector only
  surfaces it after the first attempted search.
