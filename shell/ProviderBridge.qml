import QtQuick
import Quickshell
import Quickshell.Io
import "QueryState.js" as QueryState

Process {
    id: root
    signal resultsReady(var results, string scope, string bare, var unresolved)
    signal hostError(string message)
    signal actionFailed()
    readonly property url hostUrl: Qt.resolvedUrl("../src/host.py")
    readonly property string localHostPath: {
        const text = hostUrl.toString();
        return text.startsWith("file://") ? text.substring(7) : text;
    }
    readonly property string hostPath: Quickshell.env("PALLET_HOST") ?? localHostPath
    property var queryState: QueryState.create()
    property int actionCounter: 0
    command: ["python3", hostPath]
    running: true
    stdinEnabled: true

    stdout: SplitParser {
        onRead: data => {
            let msg;
            try { msg = JSON.parse(data); } catch (err) { return; }
            if (!msg || typeof msg !== "object") return;
            if (msg.results !== undefined) {
                if (QueryState.accepts(root.queryState, msg))
                    root.resultsReady(msg.results, String(msg.scope || ""),
                        String(msg.bare ?? ""), Array.isArray(msg.unresolved) ? msg.unresolved : []);
            } else if (msg.error !== undefined) {
                if (!msg.id || msg.id === root.queryState.activeId)
                    root.hostError(String(msg.error));
            } else if (msg.executed === false) {
                root.actionFailed();
            }
        }
    }
    stderr: StdioCollector {
        onStreamFinished: {
            if (root.queryState.serial > 0 && text.length > 0)
                console.warn("pallet host:", text.trim());
        }
    }
    function cancel(): void {
        const target = QueryState.cancel(root.queryState);
        if (target.length > 0 && root.running)
            root.write(JSON.stringify({ id: "", op: "cancel", target: target }) + "\n");
    }
    function search(query: string): void {
        cancel();
        if (!root.running) {
            root.hostError(qsTr("Pallet host is not running."));
            return;
        }
        const id = QueryState.begin(root.queryState);
        root.write(JSON.stringify({ id: id, op: "search", query: query }) + "\n");
    }
    function execute(action: var, result: var): void {
        if (action === undefined || action === null) return;
        switch (action.type) {
        case "launch": Quickshell.execDetached(action.argv); break;
        case "open": Quickshell.execDetached(["xdg-open", action.url]); break;
        case "copy": Quickshell.execDetached(["wl-copy", action.text]); break;
        case "custom":
            root.actionCounter += 1;
            root.write(JSON.stringify({ id: "a" + root.actionCounter, op: "execute",
                provider: result.provider || "", action: action }) + "\n");
            break;
        }
    }
}
