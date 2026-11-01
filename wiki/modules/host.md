---
title: host
description: Pallet modules host.
---
# Host

[host.py](../../src/host.py) is the Python asyncio process between the [shell](./shell.md) and [providers](../concepts/provider.md). `amain()` discovers manifests, starts providers and reads client messages; `Host.on_search()` routes queries and `Host._merge()` emits cumulative results with pending and failure state.

`History` records and annotates results for [ranking](../concepts/ranking.md). `spawn_detached()` runs an ordinary argv directly. An `omarchy-*` argv and a trusted menu command go through a login shell (`bash -lc`). Each attempt is appended to `$XDG_STATE_HOME/pallet/actions.jsonl` (`PALLET_ACTION_LOG` sets the path; `PALLET_ACTION_LOG=0` turns it off). `Host.on_execute()` forwards custom actions to their provider. See [search](../flows/search.md) and [execution](../flows/execute.md).
