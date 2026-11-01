import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    visible: false
    readonly property string pluginId: "io.github.macifyer.pallet"
    readonly property string description: "Pallet command palette"
    readonly property string combo: "ALT + SPACE"
    readonly property int modmask: 8
    readonly property string key: "SPACE"
    readonly property int keycode: 65
    readonly property string summon: "omarchy-shell shell toggle " + pluginId
    property bool bound: false
    property bool verifyPending: false
    Component.onCompleted: bindsReader.running = true
    Component.onDestruction: {
        if (root.bound)
            Quickshell.execDetached(["hyprctl", "eval", "hl.unbind(" + luaQuote(root.combo) + ")"]);
    }
    Process {
        id: bindsReader
        command: ["hyprctl", "binds", "-j"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: root.planBinds(String(text || ""))
        }
    }
    Timer {
        id: verifyTimer
        interval: 500
        onTriggered: {
            root.verifyPending = true;
            bindsReader.running = true;
        }
    }
    Timer {
        id: heartbeat
        interval: 4000
        repeat: true
        running: true
        onTriggered: bindsReader.running = true
    }
    Process {
        id: reloadWatcher
        running: true
        command: ["sh", "-c", "command -v socat >/dev/null && socat -U - UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | while IFS= read -r line; do case \"$line\" in configreloaded*) echo reload;; esac; done"]
        stdout: SplitParser {
            onRead: data => {
                if (data.trim() === "reload")
                    bindsReader.running = true;
            }
        }
    }
    function luaQuote(text: string): string {
        return '"' + String(text).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n") + '"';
    }
    function keyOf(bind: var): string {
        return bind.key ? String(bind.key).toUpperCase() : (bind.keycode ? "CODE:" + bind.keycode : "");
    }
    function formatCombo(mask: int, key: string): string {
        const names = [];
        if (mask & 64) names.push("SUPER");
        if (mask & 4)  names.push("CTRL");
        if (mask & 8)  names.push("ALT");
        if (mask & 1)  names.push("SHIFT");
        names.push(key);
        return names.join(" + ");
    }
    function matchesOurs(bind: var): bool {
        const sameKey = (bind.key ?? "").toUpperCase() === root.key
            || Number(bind.keycode) === root.keycode;
        const sameMods = Number(bind.modmask) === root.modmask;
        return sameKey && sameMods;
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
            if ((bind.description ?? "") !== root.description)
                continue;
            if (matchesOurs(bind)) {
                root.bound = true;
                if (root.verifyPending) {
                    root.verifyPending = false;
                    console.log("pallet: confirmed ALT+SPACE -> " + root.summon);
                }
                return;
            }
            Quickshell.execDetached(["hyprctl", "eval",
                "hl.unbind(" + luaQuote(formatCombo(Number(bind.modmask), keyOf(bind))) + ")"]);
        }
        if (root.verifyPending) {
            root.verifyPending = false;
            console.warn("pallet: ALT+SPACE registration did not land; retrying");
        }
        for (const other of binds) {
            if (matchesOurs(other)) {
                if (!root.bound)
                    console.warn("pallet: ALT+SPACE is already bound to '"
                        + (other.description || ((other.dispatcher ?? "") + " " + (other.arg ?? "")))
                        + "'; leaving it alone. Bind Pallet yourself: " + root.summon);
                root.bound = false;
                return;
            }
        }
        const lua = "hl.bind(" + luaQuote(root.combo)
            + ", hl.dsp.exec_cmd(" + luaQuote(root.summon) + ")"
            + ", { description = " + luaQuote(root.description) + " })";
        Quickshell.execDetached(["hyprctl", "eval", lua]);
        root.bound = true;
        verifyTimer.restart();
    }
}
