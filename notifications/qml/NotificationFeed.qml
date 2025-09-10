import QtQuick 6.5
import QtQuick.Controls 6.5

ListView {
    id: feed
    width: parent.width
    height: parent.height

    model: feedModel
    delegate: Rectangle {
        width: parent.width
        color: index % 2 === 0 ? "#2C2C2C" : "#333"
        height: content.implicitHeight + 12
        Column {
            id: content
            anchors.fill: parent
            anchors.margins: 6
            spacing: 2
            Label { text: title; color: "white"; font.bold: true }
            Label { text: message; color: "white"; wrapMode: Text.WordWrap }
        }
    }

    ListModel { id: feedModel }

    function setEntries(entries) {
        feedModel.clear()
        for (var i = 0; i < entries.length; ++i) {
            feedModel.append(entries[i])
        }
    }
}
