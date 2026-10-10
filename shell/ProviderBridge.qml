import QtQuick
import Quickshell
import Quickshell.Io

// Speaks the provider protocol (docs/PROVIDERS.md) to the core host over
// NDJSON stdio. The host (src/host.py) does not exist yet — the next M1
// step — so until then the UI surfaces its absence instead of pretending.
Process {
    id: root

    signal resultsReady(var results)
    signal hostError(string message)

    readonly property string hostPath: Quickshell.env("PALLET_HOST")
        ?? (Quickshell.shellDir + "/../src/host.py")

    property int queryCounter: 0

    command: ["python3", hostPath]
    running: true
    stdinEnabled: true

    stdout: SplitParser {
        onRead: data => {
            let msg;
            try {
                msg = JSON.parse(data);
            } catch (err) {
                console.warn("pallet: unparseable line from host:", data);
                return;
            }
            if (msg.results !== undefined)
                root.resultsReady(msg.results);
            else if (msg.error !== undefined)
                root.hostError(msg.error);
        }
    }

    stderr: StdioCollector {
        onStreamFinished: {
            // Only surface when a search was actually attempted: a missing
            // host binary exits immediately at shell startup.
            if (root.queryCounter > 0 && data.length > 0)
                root.hostError(data.trim());
        }
    }

    function search(query: string): void {
        root.queryCounter += 1;
        root.write(JSON.stringify({
            id: "q" + root.queryCounter,
            op: "search",
            query: query
        }) + "\n");
    }

    function execute(action: var): void {
        if (action === undefined || action === null)
            return;
        switch (action.type) {
        case "launch":
            Quickshell.execDetached(action.argv);
            break;
        case "open":
            Quickshell.execDetached(["xdg-open", action.url]);
            break;
        case "copy":
            Quickshell.execDetached(["wl-copy", action.text]);
            break;
        case "custom":
            // M2: forward to the owning provider for handling.
            console.warn("pallet: custom action not yet implemented", JSON.stringify(action));
            break;
        }
    }
}
