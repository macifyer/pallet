---
title: host
description: Pallet modules host.
---
# Host

[host.py](../../src/host.py) is the Python asyncio process between the [shell](./shell.md) and [providers](../concepts/provider.md). `amain()` discovers manifests, starts providers and reads client messages; `Host.on_search()` routes queries and `Host._merge()` emits cumulative results with pending and failure state.

`History` records and annotates results for [ranking](../concepts/ranking.md). `spawn_detached()` launches argv without a shell, while `Host.on_execute()` forwards custom actions to their provider. See [search](../flows/search.md) and [execution](../flows/execute.md).
