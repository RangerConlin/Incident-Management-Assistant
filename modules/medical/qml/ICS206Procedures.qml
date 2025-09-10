import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    property alias text: procedures.text
    TextArea {
        id: procedures
        anchors.fill: parent
        wrapMode: TextArea.Wrap
        placeholderText: "Procedures..."
    }
    Component.onCompleted: {
        procedures.text = ics206Bridge.get_procedures()
    }
}
