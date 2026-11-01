---
title: obsidian
description: Pallet modules obsidian.
---
# obsidian provider

Offers Obsidian URI actions, including explicitly requested note creation. The entry point and implementation are in [provider.py](../../providers/obsidian/provider.py); its [manifest](../../providers/obsidian/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `search() and uri()`. Dependencies include Obsidian URI handler.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
