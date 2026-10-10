// Omarchy plugin entry point (kind: overlay).
//
// The Quattro shell routes lifecycle calls to this component:
//   omarchy-shell shell summon io.github.macifyer.pallet '{}'  -> open()
//   omarchy-shell shell hide   io.github.macifyer.pallet       -> close()
//
// The palette itself lives in shell/; this file is the plugin-facing
// handle. Standalone development still runs through shell/shell.qml
// (qs -p shell) — but never run both at once: as a plugin, Pallet lives
// inside the long-lived omarchy-shell process.

import "shell"

PaletteWindow {}
