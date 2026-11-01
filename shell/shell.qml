// Pallet entrypoint.
//
// Run from the repo root:   qs -p shell
// Toggle the palette:       qs -p shell ipc call pallet toggle
// Hyprland bind example:
//   bind = SUPER, K, exec, qs -p /path/to/pallet/shell ipc call pallet toggle
// (symlink shell/ into ~/.config/quickshell/pallet to use qs -c pallet instead)

import Quickshell
import Quickshell.Io
import "."

ShellRoot {
    PaletteWindow {
        id: palette
    }

    IpcHandler {
        target: "pallet"

        function toggle(): void {
            palette.visible = !palette.visible;
        }

        function open(): void {
            palette.visible = true;
        }

        function close(): void {
            palette.visible = false;
        }
    }
}
