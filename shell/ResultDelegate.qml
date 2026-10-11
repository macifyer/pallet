import QtQuick
import Quickshell

Rectangle {
    id: root

    required property var modelData

    // Freedesktop icon resolution (spec-compliant lookup order):
    //   1. absolute path in the result -> file:// directly
    //   2. primary themed icon name via Quickshell.iconPath (strict fallback
    //      mode: a miss returns "" instead of a junk path)
    //   3. ordered `icons` candidate list — first name that resolves wins;
    //      icon themes are arbitrary, so plugins never hardcode one name
    //   4. per-result fallback glyph -> generic fallback diamond
    readonly property string iconSource: {
        const icon = root.modelData.icon ?? "";
        if (icon.length > 0) {
            if (icon.startsWith("/"))
                return "file://" + icon;
            const primary = Quickshell.iconPath(icon, true);
            if (primary.length > 0)
                return primary;
        }
        const extra = root.modelData.icons;
        if (extra !== undefined && extra !== null && extra.length !== undefined) {
            for (let i = 0; i < extra.length; i++) {
                const name = String(extra[i]);
                if (name.length === 0)
                    continue;
                if (name.startsWith("/"))
                    return "file://" + name;
                const resolved = Quickshell.iconPath(name, true);
                if (resolved.length > 0)
                    return resolved;
            }
        }
        return "";
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
        text: root.modelData.fallbackIcon || "\u25c6"
        color: root.modelData.fallbackColor || "#89b4fa"
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
