import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    width: 600
    height: 400

    Component.onCompleted: objectiveBridge.loadObjectives()

    ListView {
        anchors.fill: parent
        model: objectiveBridge.objectivesModel
        delegate: Text { text: code + " - " + status }
    }
}
