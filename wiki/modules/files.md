---
title: files
description: Pallet modules files.
---
# files provider

Indexes and searches home-directory files and folders. The entry point and implementation are in [provider.py](../../providers/files/provider.py); its [manifest](../../providers/files/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `build_index() and search()`. Dependencies include fd when available, otherwise filesystem walking.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
