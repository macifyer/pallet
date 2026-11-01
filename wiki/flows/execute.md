---
title: execute
description: Pallet flows execute.
---
# Execute an action

```mermaid
sequenceDiagram
  participant U as User
  participant S as Shell
  participant H as Host
  participant P as Provider
  U->>S: Select action
  opt Confirmation required
    S->>U: Show confirmation
    U->>S: Confirm
  end
  S->>H: Launch argv, shell command, or custom action
  H->>P: Forward custom action
  P-->>H: Execution result
  H-->>S: Success or failure
```

`executeSelection()` in [PaletteWindow.qml](../../shell/PaletteWindow.qml) opens [confirmation](../concepts/confirmation.md) for gated actions. `execute()` in [ProviderBridge.qml](../../shell/ProviderBridge.qml) handles launch, shell, open, copy, and custom types. Those types are an [action](../concepts/action.md). The [host](../modules/host.md) runs launch argv and shell command strings through a login shell (`bash -lc`) and forwards custom actions to the owning [provider](../concepts/provider.md). Each launch is appended to `$XDG_STATE_HOME/pallet/actions.jsonl`. See [host.py](../../src/host.py), the [provider contract](../architecture/provider-contract.md), and [Provider protocol](../../docs/PROVIDERS.md).
