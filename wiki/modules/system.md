---
title: system
description: Pallet modules system.
---
# system provider

Offers system and Omarchy control actions. The entry point and implementation are in [provider.py](../../providers/system/provider.py); its [manifest](../../providers/system/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `search() and ipc()`. Dependencies include Omarchy and system control commands.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
