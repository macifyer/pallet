import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "Fuzzy.js" as Fuzzy
import "QueryState.js" as QueryState
import "."

PanelWindow {
    id: root
    readonly property int boxWidth: 640
    property int selectedIndex: 0
    property var filtered: []
    property bool panelOpen: false
    property string flashMessage: ""
    property string scopeLabel: "All"
    property string statusText: ""
    property bool userMoved: false
    property var lastRaw: []
    property string lastQuery: ""
    property string lastBare: ""
    property var deferredUpdate: null
    readonly property bool opened: visible
    visible: false
    focusable: true
    color: "transparent"
    aboveWindows: true
    exclusiveZone: -1
    WlrLayershell.namespace: "pallet"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    anchors { top: true; bottom: true; left: true; right: true }
    TapHandler { onTapped: root.dismiss() }
    Rectangle {
        id: box
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.round(parent.height * 0.18)
        width: root.boxWidth
        height: Math.min(column.implicitHeight + 24, root.height * 0.6)
        radius: 12
        color: "#181825"
        border.width: 1
        border.color: "#313244"
        TapHandler {}
        ColumnLayout {
            id: column
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
            TextField {
                id: searchInput
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                font.pixelSize: 17
                color: "#cdd6f4"
                placeholderText: qsTr("Type to search · f: files · a: apps · om: omarchy · s: system · w: windows")
                placeholderTextColor: "#6c7086"
                background: Rectangle { color: "transparent" }
                focus: true
                onTextChanged: root.inputChanged()
                onAccepted: root.executeSelection()
                Keys.onEscapePressed: root.close()
                Keys.onDownPressed: root.moveSelection(1)
                Keys.onUpPressed: root.moveSelection(-1)
                Keys.onTabPressed: root.togglePanel()
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#313244" }
            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, 360)
                clip: true
                model: root.filtered
                currentIndex: root.selectedIndex
                delegate: ResultDelegate {}
            }
            Text {
                Layout.fillWidth: true
                font.pixelSize: 11
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: root.flashMessage.length > 0 ? "#f38ba8" : "#585b70"
                text: root.flashMessage.length > 0 ? root.flashMessage : ("Scope: " + root.scopeLabel + (root.statusText.length > 0 ? " · " + root.statusText : "") + " · " + (root.panelOpen ? qsTr("Up/Down navigate · Enter runs · Esc closes panel") : qsTr("Up/Down navigate · Enter runs · Tab actions · Esc closes")))
            }
        }
    }
    ActionPanel {
        id: actionPanel
        anchors.left: box.right
        anchors.leftMargin: 12
        anchors.top: box.top
        visible: root.panelOpen
        result: root.filtered[root.selectedIndex]
        query: searchInput.text
        onActionExecuted: (action, result) => { bridge.execute(action, result); root.dismiss(); }
    }
    ProviderBridge {
        id: bridge
        onResultsReady: (results, scope, bare, unresolved, meta) => {
            if (!root.visible) return;
            const info = meta || { final: true, pending: [], failed: [], incremental: false };
            if (info.incremental && root.panelOpen) {
                root.deferredUpdate = { results: results, scope: scope, bare: bare, unresolved: unresolved, meta: info };
                return;
            }
            const selected = Fuzzy.keyOf(root.filtered[root.selectedIndex]);
            root.scopeLabel = scope || "All";
            const rows = QueryState.carryOver(root.lastRaw, results, info.pending, info.final);
            root.lastRaw = rows;
            root.lastQuery = typeof info.query === "string" ? info.query : searchInput.text.trim();
            root.lastBare = bare;
            root.filtered = Fuzzy.rank(bare, rows);
            const kept = root.userMoved ? Fuzzy.indexOfKey(root.filtered, selected) : -1;
            root.selectedIndex = kept >= 0 ? kept : 0;
            if (kept < 0) root.userMoved = false;
            root.statusText = info.final ? "" : qsTr("searching…");
            if (unresolved.length > 0) {
                const failed = unresolved.filter(name => info.failed.indexOf(name) !== -1);
                const slow = unresolved.filter(name => info.failed.indexOf(name) === -1);
                const parts = [];
                if (failed.length > 0) parts.push(qsTr("unavailable: ") + failed.join(", "));
                if (slow.length > 0) parts.push(qsTr("no reply from: ") + slow.join(", "));
                root.flashMessage = qsTr("Incomplete results — ") + parts.join(" · ");
                flashTimer.restart();
            } else if (info.final && !info.incremental) {
                root.flashMessage = "";
            }
        }
        onHostError: message => {
            if (!root.visible) return;
            root.filtered = [{ id: "pallet.error", title: message, subtitle: qsTr("Check the Python host"), actions: [] }];
        }
        onActionFailed: message => {
            const text = message.length > 0 ? message : qsTr("the target may already be gone.");
            Quickshell.execDetached(["bash", "-lc", "exec \"$@\"", "bash", "omarchy-notification-send", "--app-name", "Pallet", "-u", "normal",
                qsTr("Pallet action failed"), qsTr("Error: ") + text]);
            if (!root.visible) return;
            root.flashMessage = qsTr("That action could not be completed — ") + text;
            flashTimer.restart();
        }
    }
    Timer { id: debounce; interval: 30; onTriggered: root.runSearch() }
    Timer { id: flashTimer; interval: 2500; onTriggered: root.flashMessage = "" }
    onVisibleChanged: {
        if (visible) {
            searchInput.forceActiveFocus();
            bridge.warm();
        } else {
            debounce.stop();
            root.invalidateSearch();
        }
    }
    function invalidateSearch(): void {
        bridge.cancel();
        root.filtered = [];
        root.selectedIndex = 0;
        root.userMoved = false;
        root.deferredUpdate = null;
        root.panelOpen = false;
        root.flashMessage = "";
        root.statusText = "";
        root.scopeLabel = "All";
        flashTimer.stop();
        actionPanel.reset();
    }
    function inputChanged(): void {
        const text = searchInput.text.trim();
        const raw = root.lastRaw || [];
        const shown = root.filtered.filter(r => r && r.id !== "pallet.error");
        const bare = QueryState.localBare(text, root.lastQuery, root.lastBare);
        root.invalidateSearch();
        debounce.stop();
        if (!root.visible || text.length === 0) {
            root.lastRaw = [];
            root.lastQuery = "";
            root.lastBare = "";
            return;
        }
        const local = bare !== null && raw.length > 0 ? Fuzzy.rank(bare, raw) : [];
        root.filtered = local.length > 0 ? local : shown;
        root.statusText = qsTr("searching…");
        debounce.restart();
    }
    function applyDeferred(): void {
        const update = root.deferredUpdate;
        root.deferredUpdate = null;
        if (update !== null)
            bridge.resultsReady(update.results, update.scope, update.bare, update.unresolved, update.meta);
    }
    function open(): void { visible = true; scopeLabel = "All"; }
    function close(): void {
        if (actionPanel.confirming || root.panelOpen) {
            root.panelOpen = false;
            actionPanel.reset();
            root.applyDeferred();
            return;
        }
        dismiss();
    }
    function dismiss(): void {
        debounce.stop();
        root.invalidateSearch();
        visible = false;
        searchInput.text = "";
        root.lastRaw = [];
        root.lastQuery = "";
        root.lastBare = "";
    }
    function toggle(): void { visible ? close() : open(); }
    function runSearch(): void {
        const q = searchInput.text.trim();
        if (!root.visible || q.length === 0) {
            root.invalidateSearch();
            return;
        }
        bridge.search(q);
    }
    function moveSelection(step: int): void {
        if (root.panelOpen) { actionPanel.moveAction(step); return; }
        if (root.filtered.length === 0) return;
        root.selectedIndex = (root.selectedIndex + step + root.filtered.length) % root.filtered.length;
        root.userMoved = true;
    }
    function togglePanel(): void {
        if (root.filtered.length === 0) return;
        const item = root.filtered[root.selectedIndex];
        if (!item || !item.actions || item.actions.length === 0) return;
        root.panelOpen = !root.panelOpen;
        if (!root.panelOpen) { actionPanel.reset(); root.applyDeferred(); }
    }
    function executeSelection(): void {
        if (root.panelOpen) { actionPanel.executeCurrent(); return; }
        const item = root.filtered[root.selectedIndex];
        if (item === undefined || item.actions === undefined || item.actions.length === 0) return;
        const first = item.actions[0];
        if (first.danger === "confirm") { root.panelOpen = true; actionPanel.openConfirm(first); return; }
        bridge.execute(first, item);
        root.dismiss();
    }
}
