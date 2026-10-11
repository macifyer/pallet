import QtQuick
import QtQuick.Layouts

// Action panel: a small floating list of actions for the selected result.
// Positioned to the right of the palette box, vertically centered on the row.
Rectangle {
    id: root

    required property var result
    signal actionExecuted(var action, var result)

    width: 220
    height: Math.min(column.implicitHeight + 16, 320)
    radius: 10
    color: "#1e1e2e"
    border.width: 1
    border.color: "#45475a"

    ColumnLayout {
        id: column

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
                    color: "#cdd6f4"
                    font.pixelSize: 13
                }
            }
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

    function moveAction(step: int): void {
        const count = root.result && root.result.actions ? root.result.actions.length : 0;
        if (count === 0) return;
        actionIndex = (actionIndex + step + count) % count;
    }

    function executeCurrent(): void {
        const actions = root.result && root.result.actions ? root.result.actions : [];
        if (actions.length === 0 || actionIndex >= actions.length) return;
        actionExecuted(actions[actionIndex], root.result);
    }
}
