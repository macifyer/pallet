import QtQuick

Rectangle {
    id: root

    required property var modelData

    width: ListView.view ? ListView.view.width : 0
    height: 44
    radius: 8
    color: ListView.isCurrentItem ? "#313244" : "transparent"

    Text {
        id: icon

        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter

        text: root.modelData.icon ? "\u25c6" : "\u25c7"
        color: "#89b4fa"
        font.pixelSize: 13
    }

    Text {
        id: title

        anchors.left: icon.right
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter

        width: Math.min(implicitWidth, root.width * 0.42)
        elide: Text.ElideRight

        text: root.modelData.title ?? ""
        color: "#cdd6f4"
        font.pixelSize: 15
    }

    Text {
        anchors.left: title.right
        anchors.leftMargin: 12
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter

        elide: Text.ElideRight

        text: root.modelData.subtitle ?? ""
        color: "#6c7086"
        font.pixelSize: 13
    }
}
