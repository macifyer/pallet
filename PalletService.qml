import QtQuick
import Quickshell
import Quickshell.Io

// Headless plugin service (kind: service): registers Pallet's hotkey in the
// running Hyprland session without editing hyprland.conf, and re-asserts it
// after every `hyprctl reload`, because Hyprland drops runtime bindings.
//
// Pattern after MaNi4's omarchy-search-menu-items (MIT): bindings are told
// apart by description, so re-registration never duplicates and a user's
// conflicting binding is never overwritten.

Item {
    id: root

    readonly property string pluginId: "io.github.macifyer.pallet"
    readonly property string description: "Pallet command palette"
    readonly property string mods: "ALT"
    readonly property int modmask: 8   // ALT in Hyprland's modmask
    readonly property string key: "SPACE"
    readonly property int keycode: 65  // XKB keycode for space
    readonly property string summon: "omarchy-shell shell toggle " + pluginId

    property bool bound: false

    Component.onCompleted: {
        bindsReader.running = true;
        reloadWatcher.running = true;
    }

    Component.onDestruction: {
        if (root.bound)
            Quickshell.execDetached(["hyprctl", "keyword", "unbind", root.mods + ", " + root.key]);
    }

    // Read existing binds, then register only if the combo is free.
    Process {
        id: bindsReader
        command: ["hyprctl", "binds", "-j"]
        stdout: StdioCollector {
            onStreamFinished: root.planBinds(text)
        }
    }

    // socket2 carries "configreloaded"; runtime binds must be re-asserted.
    // Needs socat; without it the binding quietly vanishes on reload until
    // the plugin is reloaded.
    Process {
        id: reloadWatcher
        command: ["sh", "-c", "socat -U - UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | while IFS= read -r line; do case \"$line\" in configreloaded*) echo reload;; esac; done"]
        stdout: SplitParser {
            onRead: data => {
                if (data.trim() === "reload")
                    bindsReader.running = true;
            }
        }
    }

    function planBinds(jsonText: string): void {
        let binds = [];
        try {
            binds = JSON.parse(jsonText);
        } catch (err) {
            console.warn("pallet: cannot parse hyprctl binds -j");
            return;
        }
        for (const bind of binds) {
            const sameKey = (bind.key ?? "").toUpperCase() === root.key
                || Number(bind.keycode) === root.keycode;
            const sameMods = Number(bind.modmask) === root.modmask;
            if (!sameKey || !sameMods)
                continue;
            if ((bind.description ?? "") === root.description) {
                root.bound = true;  // already ours, nothing to do
                return;
            }
            console.warn("pallet: ALT+SPACE is already bound to '"
                + (bind.description || ((bind.dispatcher ?? "") + " " + (bind.arg ?? "")))
                + "'; leaving it alone. Free the key or bind Pallet yourself: " + root.summon);
            root.bound = false;
            return;
        }
        Quickshell.execDetached([
            "hyprctl", "keyword", "bindd",
            root.mods + ", " + root.key + ", " + root.description + ", exec, " + root.summon
        ]);
        root.bound = true;
        console.log("pallet: ALT+SPACE -> " + root.summon);
    }
}
