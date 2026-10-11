import QtQuick
import QtQuick.Layouts

// Action panel: a small floating list of actions for the selected result,
// positioned to the right of the palette box. Actions carrying
// "danger": "confirm" do not execute on Enter; the panel swaps to a
// confirmation sheet (“danger sheet”) and only a second Enter runs them.
Rectangle {
    id: root

    required property var result
    signal actionExecuted(var action, var result)

    width: 240
    height: confirming
        ? Math.min(confirmColumn.implicitHeight + 20, 320)
        : Math.min(column.implicitHeight + 16, 320)
    radius: 10
    color: "#1e1e2e"
    border.width: 1
    border.color: confirming ? "#f38ba8" : "#45475a"

    // Non-null while a danger-gated action awaits its second Enter.
    property var pendingConfirm: null
    readonly property bool confirming: pendingConfirm !== null

    ColumnLayout {
        id: column

        visible: !root.confirming
        anchors.fill: parent
        anchors.margins: 8
        spacing: 2

        Text {
            Layout.fillWidth: true
            text: qsTr("Actions")
            color: "#6c7086"
            font.pixelSize: 11
            font.bold: true
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#313244"
        }

        Repeater {
            model: root.result && root.result.actions ? root.result.actions : []

            Rectangle {
                id: actionDelegate

                required property var modelData
                required property int index

                Layout.fillWidth: true
                height: 32
                radius: 6
                color: root.actionIndex === index ? "#45475a" : "transparent"

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.actionLabel(modelData)
                    color: (modelData.danger === "confirm") ? "#f9e2af" : "#cdd6f4"
                    font.pixelSize: 13
                }
            }
        }
    }

    ColumnLayout {
        id: confirmColumn

        visible: root.confirming
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        Text {
            Layout.fillWidth: true
            text: root.confirmTitle()
            color: "#f38ba8"
            font.pixelSize: 14
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            text: root.confirmDetail()
            color: "#a6adc8"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        Text {
            Layout.fillWidth: true
            text: qsTr("Enter confirms \u00b7 Esc cancels")
            color: "#6c7086"
            font.pixelSize: 11
        }
    }

    property int actionIndex: 0

    function actionLabel(action: var): string {
        // Providers own their action labels; the panel only invents one when
        // a provider did not supply a title.
        if (action.title !== undefined && String(action.title).length > 0)
            return String(action.title);
        switch (action.type) {
        case "launch": return qsTr("Launch");
        case "copy":   return qsTr("Copy");
        case "open":   return qsTr("Open");
        case "custom":
            switch (action.kind) {
            case "press":             return qsTr("Run menu item");
            case "focus-window":      return qsTr("Focus window");
            case "close-window":      return qsTr("Close window");
            case "toggle-floating":   return qsTr("Toggle floating");
            case "toggle-fullscreen": return qsTr("Toggle fullscreen");
            default:                    return qsTr("Run");
            }
        default: return action.type;
        }
    }

    function confirmTitle(): string {
        const c = root.pendingConfirm ? root.pendingConfirm.confirmation : null;
        if (c && c.title && String(c.title).length > 0)
            return String(c.title);
        return qsTr("Are you sure?");
    }

    function confirmDetail(): string {
        const c = root.pendingConfirm ? root.pendingConfirm.confirmation : null;
        if (c && c.detail && String(c.detail).length > 0)
            return String(c.detail);
        return qsTr("This action cannot be undone from here.");
    }

    function moveAction(step: int): void {
        if (root.confirming)
            return;
        const count = root.result && root.result.actions ? root.result.actions.length : 0;
        if (count === 0) return;
        actionIndex = (actionIndex + step + count) % count;
    }

    function executeCurrent(): void {
        if (root.confirming) {
            const action = root.pendingConfirm;
            root.pendingConfirm = null;
            actionExecuted(action, root.result);
            return;
        }
        const actions = root.result && root.result.actions ? root.result.actions : [];
        if (actions.length === 0 || actionIndex >= actions.length) return;
        const action = actions[actionIndex];
        if (action.danger === "confirm") {
            pendingConfirm = action;
            return;
        }
        actionExecuted(action, root.result);
    }

    // Entry point for the direct-Enter path in PaletteWindow when the
    // primary action is danger-gated: opens the panel straight into the
    // confirmation sheet for that action.
    function openConfirm(action: var): void {
        pendingConfirm = action;
    }

    function cancelConfirm(): void {
        pendingConfirm = null;
    }

    function reset(): void {
        pendingConfirm = null;
        actionIndex = 0;
    }

    // A different result while a confirmation is open always cancels it —
    // a sheet for one result must never execute against another.
    onResultChanged: reset()
}
