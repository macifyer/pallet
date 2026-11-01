---
title: Plugin shell
description: Overlay window, service hotkey, and why the host stays loaded.
---
# Plugin shell

## Summary

Pallet is an Omarchy plugin with two kinds. The overlay draws the palette. The service registers the hotkey and does not draw anything. [manifest.json](../../manifest.json) sets `keepLoaded` so the Python host stays warm between summons. Lifecycle details stay in the [plugin notes](../../docs/PLUGIN.md).

## Diagram

```mermaid
flowchart LR
  Hotkey[ALT SPACE] --> Service[Service.qml]
  Service --> Toggle[omarchy-shell toggle]
  Toggle --> Overlay[PalletOverlay.qml]
  Overlay --> Window[PaletteWindow]
  Window --> Bridge[ProviderBridge]
```

## Key components

- [PalletOverlay.qml](../../PalletOverlay.qml) is the overlay entry. It hosts `PaletteWindow`. The shell routes summon, hide, and toggle to `open()`, `close()`, and `toggle()`.
- [Service.qml](../../Service.qml) is the service entry. `planBinds()` reads `hyprctl binds -j` and registers ALT+SPACE with `hyprctl eval` and `hl.bind` only when that combo is free. The bind description is `Pallet command palette`. On destruction it calls `hl.unbind` for a bind it registered.
- Hyprland drops runtime binds on reload. `reloadWatcher` tails socket2 for `configreloaded` when `socat` exists. A heartbeat every 4 seconds re-reads binds either way. `verifyTimer` re-reads 500 ms after a registration attempt.
- [shell.qml](../../shell/shell.qml) is the standalone `qs -p shell` entry. Its IPC target is `pallet`. Do not run that process beside the plugin. The plugin already lives inside omarchy-shell.

## Design decisions

The service does not edit hyprland.conf. A successful `hyprctl eval` is not treated as proof. The log line `confirmed` is printed only after a later binds read shows the description and the ALT+SPACE combo. SUPER+SPACE stays the stock Omarchy menu. `keepLoaded: true` keeps the overlay and the service loaded so [ProviderBridge.qml](../../shell/ProviderBridge.qml) does not cold-start [host.py](../../src/host.py) on every summon.

## Related

[System architecture](./system.md), [summon](../flows/summon.md), [shell](../modules/shell.md), [plugin notes](../../docs/PLUGIN.md).
