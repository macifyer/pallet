import QtQuick
import Quickshell
import Quickshell.Io

Process {
    id: root
    signal resultsReady(var results, string scope, string bare)
    signal hostError(string message)
    signal actionFailed()
    readonly property url hostUrl: Qt.resolvedUrl("../src/host.py")
    readonly property string localHostPath: {
        const text = hostUrl.toString();
        return text.startsWith("file://") ? text.substring(7) : text;
    }
    readonly property string hostPath: Quickshell.env("PALLET_HOST") ?? localHostPath
    property int queryCounter: 0
    command: ["python3", hostPath]
    running: true
    stdinEnabled: true
    stdout: SplitParser {
        onRead: data => {
            let msg;
            try { msg = JSON.parse(data); } catch (err) { return; }
            if (msg.results !== undefined) root.resultsReady(msg.results, msg.scope || "", msg.bare || "");
            else if (msg.error !== undefined) root.hostError(String(msg.error));
            else if (msg.executed === false) root.actionFailed();
        }
    }
    stderr: StdioCollector {
        onStreamFinished: {
            if (root.queryCounter > 0 && data.length > 0) root.hostError(data.trim());
        }
    }
    function search(query: string): void {
        root.queryCounter += 1;
        root.write(JSON.stringify({ id: "q" + root.queryCounter, op: "search", query: query }) + "\n");
    }
    function execute(action: var, result: var): void {
        if (action === undefined || action === null) return;
        switch (action.type) {
        case "launch": Quickshell.execDetached(action.argv); break;
        case "open": Quickshell.execDetached(["xdg-open", action.url]); break;
        case "copy": Quickshell.execDetached(["wl-copy", action.text]); break;
        case "custom": root.write(JSON.stringify({ id: "a" + root.queryCounter, op: "execute", provider: result.provider || "", action: action }) + "\n"); break;
        }
    }
}
