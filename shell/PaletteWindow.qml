import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "Fuzzy.js" as Fuzzy
import "."

PanelWindow {
    id: root
    readonly property int boxWidth: 640
    property int selectedIndex: 0
    property var filtered: []
    property bool panelOpen: false
    property string flashMessage: ""
    property string scopeLabel: "All"
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
                placeholderText: qsTr("Type to search · files:, obsidian:, apps:")
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
                color: root.flashMessage.length > 0 ? "#f38ba8" : "#585b70"
                text: root.flashMessage.length > 0 ? root.flashMessage : ("Scope: " + root.scopeLabel + " · " + (root.panelOpen ? qsTr("Up/Down navigate · Enter runs · Esc closes panel") : qsTr("Up/Down navigate · Enter runs · Tab actions · Esc closes")))
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
        onActionExecuted: (action, result) => { bridge.execute(action, result); root.dismiss(); }
    }
    ProviderBridge {
        id: bridge
        onResultsReady: (results, scope, bare, unresolved) => {
            if (!root.visible) return;
            root.scopeLabel = scope || "All";
            root.filtered = Fuzzy.rank(bare, results);
            root.selectedIndex = 0;
            root.flashMessage = "";
            if (unresolved.length > 0) {
                root.flashMessage = qsTr("Incomplete results — no reply from: ") + unresolved.join(", ");
                flashTimer.restart();
            }
        }
        onHostError: message => {
            if (!root.visible) return;
            root.filtered = [{ id: "pallet.error", title: message, subtitle: qsTr("Check the Python host"), actions: [] }];
        }
        onActionFailed: {
            if (!root.visible) return;
            root.flashMessage = qsTr("That action could not be completed — the target may already be gone.");
            flashTimer.restart();
        }
    }
    Timer { id: debounce; interval: 80; onTriggered: root.runSearch() }
    Timer { id: flashTimer; interval: 2500; onTriggered: root.flashMessage = "" }
    onVisibleChanged: {
        if (visible) {
            searchInput.forceActiveFocus();
        } else {
            debounce.stop();
            root.invalidateSearch();
        }
    }
    function invalidateSearch(): void {
        bridge.cancel();
        root.filtered = [];
        root.selectedIndex = 0;
        root.panelOpen = false;
        root.flashMessage = "";
        root.scopeLabel = "All";
        flashTimer.stop();
        actionPanel.reset();
    }
    function inputChanged(): void {
        // Invalidate on the keystroke, not after the debounce window.
        root.invalidateSearch();
        debounce.stop();
        if (root.visible && searchInput.text.trim().length > 0)
            debounce.restart();
    }
    function open(): void { visible = true; scopeLabel = "All"; }
    function close(): void {
        if (actionPanel.confirming) { actionPanel.cancelConfirm(); return; }
        if (root.panelOpen) { root.panelOpen = false; return; }
        dismiss();
    }
    function dismiss(): void {
        debounce.stop();
        root.invalidateSearch();
        visible = false;
        searchInput.text = "";
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
    }
    function togglePanel(): void {
        if (root.filtered.length === 0) return;
        const item = root.filtered[root.selectedIndex];
        if (!item || !item.actions || item.actions.length === 0) return;
        root.panelOpen = !root.panelOpen;
        if (!root.panelOpen) actionPanel.reset();
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
