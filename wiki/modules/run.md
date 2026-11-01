---
title: run
description: Pallet modules run.
---
# run provider

Suggests PATH commands and an explicit Run action. The entry point and implementation are in [provider.py](../../providers/run/provider.py); its [manifest](../../providers/run/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `PathIndex and run_row()`. Dependencies include PATH and a visible terminal.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
