import QtQuick
import Quickshell

Rectangle {
    id: root

    required property var modelData

    // Freedesktop icon resolution (spec-compliant lookup order):
    //   1. absolute path in the .desktop entry -> file:// directly
    //   2. active icon theme via Quickshell.iconPath (explicit-fallback mode,
    //      so a miss returns "" instead of a junk path)
    //   3. nothing -> the fallback glyph
    // Relative paths (Wine entries like "icons/windows.png") are NOT file
    // paths; they fall through to the themed lookup, which misses cleanly.
    readonly property string iconSource: {
        const icon = root.modelData.icon ?? "";
        if (icon.length === 0)
            return "";
        if (icon.startsWith("/"))
            return "file://" + icon;
        return Quickshell.iconPath(icon, true);
    }

    width: ListView.view ? ListView.view.width : 0
    height: 44
    radius: 8
    color: ListView.isCurrentItem ? "#313244" : "transparent"

    Image {
        id: appIcon

        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter

        width: 22
        height: 22
        visible: root.iconSource.length > 0
        source: root.iconSource
        sourceSize: Qt.size(22, 22)
        smooth: true
        mipmap: true
        asynchronous: true
    }

    Text {
        id: fallbackIcon

        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        width: iconImgWidth

        readonly property int iconImgWidth: 22

        visible: !appIcon.visible
        text: "\u25c6"
        color: "#89b4fa"
        font.pixelSize: 13
        font.bold: true
    }

    Text {
        id: title

        anchors.left: appIcon.right
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
