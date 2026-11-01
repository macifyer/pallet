---
title: Action
description: Launch, open, copy, and custom operations on a result.
---
# Action

## Definition

An action is an operation attached to a result. The types the shell dispatches are `launch`, `copy`, `open`, and `custom`.

## Why it matters

`launch`, `open`, and `copy` run on this machine through the host, without a shell. `custom` is sent back to the provider that owns the row. `danger` set to `confirm` requires a second Enter. `tone` only picks the confirmation color: positive, warning, or danger.

## Where it lives

`ProviderBridge.execute()` in [ProviderBridge.qml](../../shell/ProviderBridge.qml) switches on `action.type`. `launch` sends `action.argv`. `open` sends `xdg-open` with `action.url` or `action.path`. `copy` sends `wl-copy` with `action.text`. `custom` sends `op: execute` and the action object to `result.provider`. `Host.on_launch()` and `Host.on_execute()` in [host.py](../../src/host.py) perform those two host ops. The confirmation sheet is `openConfirm()` in [ActionPanel.qml](../../shell/ActionPanel.qml). The field shapes are in the [provider protocol](../../docs/PROVIDERS.md).

## Related

[Confirmation](./confirmation.md), [execute](../flows/execute.md), [provider](./provider.md), [provider contract](../architecture/provider-contract.md).
