---
title: plugins
description: Pallet modules plugins.
---
# plugins provider

Finds installed Omarchy shell plugins. The entry point and implementation are in [provider.py](../../providers/plugins/provider.py); its [manifest](../../providers/plugins/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `load_plugins() and search()`. Dependencies include installed plugin manifests.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
