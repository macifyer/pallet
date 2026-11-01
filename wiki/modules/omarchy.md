---
title: omarchy
description: Pallet modules omarchy.
---
# omarchy provider

Loads and searches the native Omarchy menu and shell panels. The entry point and implementation are in [provider.py](../../providers/omarchy/provider.py); its [manifest](../../providers/omarchy/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `Catalog and search()`. Dependencies include Omarchy menu configuration and guard commands.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
