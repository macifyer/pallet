---
title: apps
description: Pallet modules apps.
---
# apps provider

Discovers XDG desktop entries and exposes launch and desktop actions. The entry point and implementation are in [provider.py](../../providers/apps/provider.py); its [manifest](../../providers/apps/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `parse_desktop() and load_apps()`. Dependencies include XDG desktop entries and available terminal launchers.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
