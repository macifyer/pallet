import QtQuick
import Quickshell
import Quickshell.Io

// Speaks the provider protocol (docs/PROVIDERS.md) to the core host over
// NDJSON stdio.
Process {
    id: root

    signal resultsReady(var results)
    signal hostError(string message)
    // A provider refused or failed to run a custom action (stale window,
    // dispatcher error, ...). The reply carries no detail beyond the id.
    signal actionFailed()

    // Resolved relative to THIS file, so it finds the repo's src/host.py
    // both standalone (qs -p shell) and as an Omarchy plugin, where
    // Quickshell.shellDir points at omarchy-shell's directory instead.
    readonly property url hostUrl: Qt.resolvedUrl("../src/host.py")
    readonly property string localHostPath: {
        const text = hostUrl.toString();
        return text.startsWith("file://") ? text.substring(7) : text;
    }
    readonly property string hostPath: Quickshell.env("PALLET_HOST")
        ?? localHostPath

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
            else if (msg.executed === false)
                root.actionFailed();
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

    function execute(action: var, result: var): void {
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
            root.write(JSON.stringify({
                id: "a" + root.queryCounter,
                op: "execute",
                provider: result.provider || "",
                action: action
            }) + "\n");
            break;
        }
    }
}
