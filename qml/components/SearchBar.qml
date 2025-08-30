import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property alias text: field.text
    property string placeholder: "Search..."
    signal searchChanged(string text)

    implicitWidth: 320
    implicitHeight: 36

    Row {
        anchors.fill: parent
        spacing: 6

        TextField {
            id: field
            placeholderText: root.placeholder
            selectByMouse: true
            focus: false
            onTextEdited: debounce.restart()
            Keys.onPressed: (ev) => {
                if (ev.key === Qt.Key_Escape) {
                    field.text = "";
                    root.searchChanged("");
                    ev.accepted = true;
                }
            }
        }

        Button {
            text: field.text.length > 0 ? "Clear" : "Search"
            onClicked: {
                if (field.text.length > 0) {
                    field.text = "";
                    root.searchChanged("");
                } else {
                    root.searchChanged(field.text);
                }
            }
        }
    }

    Timer {
        id: debounce
        interval: 250
        repeat: false
        onTriggered: root.searchChanged(field.text)
    }
}

