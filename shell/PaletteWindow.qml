import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "."

PanelWindow {
    id: root

    readonly property int boxWidth: 640

    property int selectedIndex: 0
    property var filtered: []

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
                color: "#585b70"
                text: qsTr("Up/Down navigate \u00b7 Enter runs \u00b7 Esc closes")
            }
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
    }

    Timer {
        id: debounce
        interval: 80
        onTriggered: root.runSearch()
    }

    onVisibleChanged: {
        if (visible)
            searchInput.forceActiveFocus();
    }

    function close(): void {
        visible = false;
        searchInput.text = "";
        root.filtered = [];
        root.selectedIndex = 0;
    }

    function runSearch(): void {
        const q = searchInput.text.trim();
        if (q.length === 0) {
            root.filtered = [];
            return;
        }
        bridge.search(q);
    }

    function moveSelection(step: int): void {
        if (root.filtered.length === 0)
            return;
        root.selectedIndex = (root.selectedIndex + step + root.filtered.length) % root.filtered.length;
    }

    function executeSelection(): void {
        const item = root.filtered[root.selectedIndex];
        if (item === undefined || item.actions === undefined || item.actions.length === 0)
            return;
        bridge.execute(item.actions[0]);
        root.close();
    }
}
