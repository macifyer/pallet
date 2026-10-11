import QtQuick
import Quickshell
import Quickshell.Io

// Headless plugin service (kind: service): registers Pallet's hotkey in the
// running Hyprland session without editing hyprland.conf, and re-asserts it
// whenever it goes missing, because Hyprland drops runtime bindings on any
// `hyprctl reload` (which Omarchy's own toggles issue for gaps/animations).
//
// Two re-assertion paths:
//   - reloadWatcher: instant, tails socket2 via socat (only if socat exists)
//   - heartbeat: socat-independent poll every few seconds; catches every
//     reload regardless of tooling, so the bind can never stay gone
//
// Mechanism after MaNi4's omarchy-search-menu-items (MIT): `hyprctl eval`
// with hl.bind()/hl.unbind() Lua. Registration is always verified by
// re-reading the binds, so the log only reports what Hyprland holds.
// Bindings are told apart by description; user bindings are never replaced.

Item {
    id: root
    visible: false

    readonly property string pluginId: "io.github.macifyer.pallet"
    readonly property string description: "Pallet command palette"
    readonly property string combo: "ALT + SPACE"
    readonly property int modmask: 8   // ALT in Hyprland's modmask
    readonly property string key: "SPACE"
    readonly property int keycode: 65  // XKB keycode for space
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

    // eval is fire-and-forget; re-read the binds to confirm it landed.
    Timer {
        id: verifyTimer
        interval: 500
        onTriggered: {
            root.verifyPending = true;
            bindsReader.running = true;
        }
    }

    // Poll against runtime-bind loss. One cheap hyprctl read per interval;
    // planBinds() short-circuits when our bind is already present, so the
    // steady state is silent. This path works with no external tooling.
    Timer {
        id: heartbeat
        interval: 4000
        repeat: true
        running: true
        onTriggered: bindsReader.running = true
    }

    // Fast path: Hyprland's socket2 carries a configreloaded event; when
    // socat happens to be installed we re-assert instantly instead of
    // waiting for the next heartbeat tick. If socat is missing the process
    // simply exits and the heartbeat alone keeps the bind alive.
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

        // Our own binds first: confirm the live one, drop stale ones.
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

        // We asked for a bind and Hyprland doesn't hold it: whether this was
        // a verification pass or a heartbeat catch-up, (re)register below.
        if (root.verifyPending) {
            root.verifyPending = false;
            console.warn("pallet: ALT+SPACE registration did not land; retrying");
        }

        // Never stomp a user's (or Omarchy's) binding.
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
        root.bound = true;  // optimistic; verifyTimer confirms or warns
        verifyTimer.restart();
    }
}
