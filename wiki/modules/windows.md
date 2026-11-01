---
title: windows
description: Pallet modules windows.
---
# windows provider

Searches and controls live Hyprland windows. The entry point and implementation are in [provider.py](../../providers/windows/provider.py); its [manifest](../../providers/windows/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `search() and execute()`. Dependencies include Hyprland via hyprctl.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
