import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    width: textItem.width + 20
    height: textItem.height + 20
    color: "#333"
    radius: 4
    opacity: 0

    Text { id: textItem; color: "white"; anchors.centerIn: parent }

    function show(message) {
        textItem.text = message
        root.opacity = 1
        SequentialAnimation {
            NumberAnimation { target: root; property: "opacity"; to: 0; duration: 3000; easing.type: Easing.InOutQuad }
        }.start()
    }
}
