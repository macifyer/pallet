---
title: defaults
description: Pallet modules defaults.
---
# defaults provider

Offers Omarchy default applications and web searches. The entry point and implementation are in [provider.py](../../providers/defaults/provider.py); its [manifest](../../providers/defaults/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `search() and search_row()`. Dependencies include Omarchy launch helpers.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
