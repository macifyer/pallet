---
title: shell
description: Pallet modules shell.
---
# Shell

The QML frontend displays results, manages selection and confirmation, and sends JSON-line requests through `ProviderBridge` in [ProviderBridge.qml](../../shell/ProviderBridge.qml). The plugin overlay uses [PalletOverlay.qml](../../PalletOverlay.qml); the standalone entry point is [shell.qml](../../shell/shell.qml).

[PaletteWindow.qml](../../shell/PaletteWindow.qml) debounces input, handles selection and preserves results during streaming. [QueryState.js](../../shell/QueryState.js) rejects stale responses; [Fuzzy.js](../../shell/Fuzzy.js) implements [ranking](../concepts/ranking.md). [ActionPanel.qml](../../shell/ActionPanel.qml) implements [confirmation](../concepts/confirmation.md). See [search](../flows/search.md) and [execution](../flows/execute.md).
