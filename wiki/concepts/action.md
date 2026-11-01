---
title: Action
description: Launch, open, copy, and custom operations on a result.
---
# Action

## Definition

An action is an operation attached to a result. The types the shell dispatches are `launch`, `shell`, `copy`, `open`, and `custom`.

## Why it matters

`launch`, `open`, and `copy` run on this machine through the host. An ordinary `launch` argv is executed directly. An `omarchy-*` argv uses `bash -lc 'exec "$@"'`. `shell` is a trusted command string executed as `bash -lc <command>`. `open` and `copy` use `xdg-open` and `wl-copy` directly. `custom` is sent back to the provider that owns the row. `danger` set to `confirm` requires a second Enter. `tone` only picks the confirmation color: positive, warning, or danger.

## Where it lives

`ProviderBridge.execute()` in [ProviderBridge.qml](../../shell/ProviderBridge.qml) switches on `action.type`. `launch` sends `action.argv`. `shell` sends `action.command`. `open` sends `xdg-open` with `action.url` or `action.path`. `copy` sends `wl-copy` with `action.text`. `custom` sends `op: execute` and the action object to `result.provider`. `Host.on_launch()` passes the action id into `spawn_detached()`, which appends `$XDG_STATE_HOME/pallet/actions.jsonl`. `Host.on_execute()` forwards custom actions. The confirmation sheet is `openConfirm()` in [ActionPanel.qml](../../shell/ActionPanel.qml). The field shapes are in the [provider protocol](../../docs/PROVIDERS.md).

## Related

[Confirmation](./confirmation.md), [execute](../flows/execute.md), [provider](./provider.md), [provider contract](../architecture/provider-contract.md).
