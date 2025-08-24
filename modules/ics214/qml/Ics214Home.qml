import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 800
    height: 600

    signal newEntryRequested(string text, bool critical, var tags, var files)
    property alias streamsModel: streamsView.model

    ColumnLayout {
        anchors.fill: parent
        RowLayout {
            Label { text: "ICS-214" }
        }
        RowLayout {
            ListView { id: streamsView; width: 200; Layout.fillHeight: true }
            ListView { id: feedView; Layout.fillWidth: true; Layout.fillHeight: true }
            Rectangle { width: 150; Layout.fillHeight: true }
        }
        Ics214QuickEntry {
            onSubmit: root.newEntryRequested(text, critical, tags, files)
        }
    }
}
