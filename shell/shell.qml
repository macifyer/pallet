
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
