import QtQuick
import Quickshell
import Quickshell.Io
import "QueryState.js" as QueryState

Process {
    id: root
    // meta: { final, pending, failed, incremental, query } — incremental is
    // true for follow-up messages under the query id already delivered, so the
    // window can merge without resetting the selection; query is the text
    // sent for that id (not whatever the input holds when the reply lands).
    signal resultsReady(var results, string scope, string bare, var unresolved, var meta)
    signal hostError(string message)
    signal actionFailed(string message)
    readonly property url hostUrl: Qt.resolvedUrl("../src/host.py")
    readonly property string localHostPath: {
        const text = hostUrl.toString();
        return text.startsWith("file://") ? text.substring(7) : text;
    }
    readonly property string hostPath: Quickshell.env("PALLET_HOST") ?? localHostPath
    property var queryState: QueryState.create()
    property string deliveredId: ""
    property string activeQuery: ""
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
                if (QueryState.accepts(root.queryState, msg)) {
                    const incremental = root.deliveredId === msg.id;
                    root.deliveredId = msg.id;
                    root.resultsReady(msg.results, String(msg.scope || ""),
                        String(msg.bare ?? ""), Array.isArray(msg.unresolved) ? msg.unresolved : [], {
                            final: msg.final !== false,
                            pending: Array.isArray(msg.pending) ? msg.pending : [],
                            failed: Array.isArray(msg.failed) ? msg.failed : [],
                            incremental: incremental,
                            query: root.activeQuery
                        });
                }
            } else if (msg.executed === false) {
                root.actionFailed(typeof msg.error === "string" ? msg.error : "");
            } else if (msg.error !== undefined) {
                if (!msg.id || msg.id === root.queryState.activeId)
                    root.hostError(String(msg.error));
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
        root.deliveredId = "";
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
        root.activeQuery = query;
        root.write(JSON.stringify({ id: id, op: "search", query: query }) + "\n");
    }
    // Overlay opened: let providers refresh caches before the first keystroke.
    function warm(): void {
        if (root.running)
            root.write(JSON.stringify({ id: "", op: "warm" }) + "\n");
    }
    // Run argv without a shell. The host launches it so a missing command is
    // reported back; if the host is down, fall back to a detached exec.
    function launch(argv: var): void {
        if (!Array.isArray(argv) || argv.length === 0) return;
        if (root.running) {
            root.actionCounter += 1;
            root.write(JSON.stringify({ id: "l" + root.actionCounter, op: "launch", argv: argv }) + "\n");
        } else {
            Quickshell.execDetached(argv);
        }
    }
    // Remember what was chosen so the host can boost it next time (frecency).
    function record(result: var): void {
        if (!root.running || !result || typeof result.provider !== "string") return;
        root.write(JSON.stringify({ id: "", op: "record", provider: result.provider,
            result: String(result.id ?? ""), title: String(result.title ?? "") }) + "\n");
    }
    function execute(action: var, result: var): void {
        if (action === undefined || action === null) return;
        root.record(result);
        switch (action.type) {
        case "launch": root.launch(action.argv); break;
        case "open": root.launch(["xdg-open", String(action.url ?? action.path ?? "")]); break;
        case "copy": root.launch(["wl-copy", "--", String(action.text ?? "")]); break;
        case "custom":
            root.actionCounter += 1;
            root.write(JSON.stringify({ id: "a" + root.actionCounter, op: "execute",
                provider: result.provider || "", action: action }) + "\n");
            break;
        }
    }
}
