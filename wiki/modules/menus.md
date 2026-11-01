---
title: menus
description: Pallet modules menus.
---
# menus provider

Finds and invokes focused application menu items. The entry point and implementation are in [provider.py](../../providers/menus/provider.py); its [manifest](../../providers/menus/manifest.json) declares how the [host](./host.md) starts and routes it. Key code: `MenuService and walk_items()`. Dependencies include AT-SPI accessibility and focused-window data.

The provider participates in [search](../flows/search.md) through the [provider protocol](../concepts/provider.md); its results use the shared [ranking](../concepts/ranking.md) and [action flow](../flows/execute.md). See [Provider protocol](../../docs/PROVIDERS.md) for message and action shapes.
