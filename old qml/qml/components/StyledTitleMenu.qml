// qml/components/StyledTitleMenu.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtGraphicalEffects 1.15

Menu {
    id: root
    property alias title: root.title

    background: Rectangle {
        // Ensure the background fills the entire menu
        anchors.fill: parent

        radius: 6
        color: palette.window

        // Border settings
        border.color: "lime"  // neon green for testing
        border.width: 2       // increase width to your liking

        // Drop shadow
        layer.enabled: true
        layer.effect: DropShadow {
            color: "#80000000"
            radius: 12
            samples: 16
            verticalOffset: 2
        }
    }
}
