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
    // Transient failure notice shown in the footer (e.g. a provider
    // refused an action). Cleared by flashTimer or on close.
    property string flashMessage: ""

    // Omarchy plugin contract: summon/hide route to open()/close(),
    // and the shell may read `opened` for lifecycle state.
    readonly property bool opened: visible

    visible: false
    focusable: true
    color: "transparent"

    aboveWindows: true
    exclusiveZone: -1

    // Wayland-specific polish; harmless on other platforms.
    WlrLayershell.namespace: "pallet"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    anchors {
        top: true
        bottom: true
        left: true
        right: true
    }

    // Click on the transparent backdrop dismisses.
    TapHandler {
        onTapped: root.close()
    }

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

        // Swallow clicks so the backdrop handler does not fire.
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
                placeholderText: qsTr("Type to search")
                placeholderTextColor: "#6c7086"
                background: Rectangle { color: "transparent" }
                focus: true

                onTextChanged: {
                    root.selectedIndex = 0;
                    debounce.restart();
                }
                onAccepted: root.executeSelection()
                Keys.onEscapePressed: root.close()
                Keys.onDownPressed: root.moveSelection(1)
                Keys.onUpPressed: root.moveSelection(-1)
                Keys.onTabPressed: root.togglePanel()
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#313244"
            }

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
                text: root.flashMessage.length > 0
                    ? root.flashMessage
                    : (root.panelOpen
                        ? qsTr("Up/Down navigate \u00b7 Enter runs \u00b7 Esc closes panel")
                        : qsTr("Up/Down navigate \u00b7 Enter runs \u00b7 Tab actions \u00b7 Esc closes"))
            }
        }
    }

    ActionPanel {
        id: actionPanel

        anchors.left: box.right
        anchors.leftMargin: 12
        anchors.top: box.top
        anchors.topMargin: 0

        visible: root.panelOpen
        result: root.filtered[root.selectedIndex]

        onActionExecuted: (action, result) => {
            bridge.execute(action, result);
            root.close();
        }
    }

    ProviderBridge {
        id: bridge

        onResultsReady: results => {
            root.filtered = Fuzzy.rank(searchInput.text, results);
            root.selectedIndex = 0;
        }
        onHostError: message => {
            root.filtered = [{
                id: "pallet.error",
                title: message,
                subtitle: qsTr("The host is expected at src/host.py \u2014 build it next (M1)"),
                actions: []
            }];
        }
        onActionFailed: {
            root.flashMessage = qsTr("That action could not be completed \u2014 the target may already be gone.");
            flashTimer.restart();
        }
    }

    Timer {
        id: debounce
        interval: 80
        onTriggered: root.runSearch()
    }

    Timer {
        id: flashTimer
        interval: 2500
        onTriggered: root.flashMessage = ""
    }

    onVisibleChanged: {
        if (visible)
            searchInput.forceActiveFocus();
        else
            root.panelOpen = false;
    }

    function open(): void {
        visible = true;
    }

    function close(): void {
        // Esc cascades: cancel an open confirmation, then the panel,
        // then the palette itself.
        if (actionPanel.confirming) {
            actionPanel.cancelConfirm();
            return;
        }
        if (root.panelOpen) {
            root.panelOpen = false;
            return;
        }
        visible = false;
        searchInput.text = "";
        root.filtered = [];
        root.selectedIndex = 0;
        root.panelOpen = false;
        root.flashMessage = "";
        actionPanel.reset();
    }

    function toggle(): void {
        if (visible)
            close();
        else
            open();
    }

    function runSearch(): void {
        const q = searchInput.text.trim();
        if (q.length === 0) {
            root.filtered = [];
            root.panelOpen = false;
            return;
        }
        bridge.search(q);
    }

    function moveSelection(step: int): void {
        if (root.panelOpen) {
            actionPanel.moveAction(step);
            return;
        }
        if (root.filtered.length === 0)
            return;
        root.selectedIndex = (root.selectedIndex + step + root.filtered.length) % root.filtered.length;
    }

    function togglePanel(): void {
        if (root.filtered.length === 0)
            return;
        const item = root.filtered[root.selectedIndex];
        if (!item || !item.actions || item.actions.length === 0)
            return;
        root.panelOpen = !root.panelOpen;
        if (!root.panelOpen)
            actionPanel.reset();
    }

    function executeSelection(): void {
        if (root.panelOpen) {
            actionPanel.executeCurrent();
            return;
        }
        const item = root.filtered[root.selectedIndex];
        if (item === undefined || item.actions === undefined || item.actions.length === 0)
            return;
        const first = item.actions[0];
        // Danger-gated primary actions cannot bypass the confirmation
        // sheet via the direct-Enter path: Enter opens the panel with the
        // sheet already showing, and only a second Enter executes.
        if (first.danger === "confirm") {
            root.panelOpen = true;
            actionPanel.openConfirm(first);
            return;
        }
        bridge.execute(first, item);
        root.close();
    }
}
