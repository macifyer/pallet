---
title: confirmation
description: Pallet concepts confirmation.
---
# Action confirmation

Actions marked `danger: "confirm"` require a second Enter. `openConfirm()` and `executeCurrent()` in [ActionPanel.qml](../../shell/ActionPanel.qml) bind confirmation to the result identity and exact query, and discard it if either changes. Tone is visual metadata separate from the gate. See the [execution flow](../flows/execute.md) and [Provider protocol](../../docs/PROVIDERS.md).
