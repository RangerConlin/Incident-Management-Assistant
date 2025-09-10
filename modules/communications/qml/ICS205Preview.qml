import QtQuick 6.5
import QtQuick.Controls 6.5
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 800; height: 600

    signal back()
    signal exportPdf()
    signal printRequested()
    signal closeRequested()

    ListModel { id: previewModel }

    Component.onCompleted: {
        var rows = ics205.getPreviewRows();
        for (var i = 0; i < rows.length; ++i) {
            previewModel.append(rows[i]);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        TableView {
            id: table
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: previewModel
            clip: true
            columnSpacing: 1
            rowSpacing: 1
            delegate: Rectangle {
                implicitHeight: 28
                border.color: "#cccccc"
                Text { anchors.centerIn: parent; text: model.display || model[table.columns[column].role] }
            }
            columns: [
                TableViewColumn { role: "Function"; title: "Function"; width: 120 },
                TableViewColumn { role: "Channel"; title: "Channel"; width: 100 },
                TableViewColumn { role: "Assignment"; title: "Assignment"; width: 120 },
                TableViewColumn { role: "RX"; title: "RX"; width: 100 },
                TableViewColumn { role: "TX"; title: "TX"; width: 100 },
                TableViewColumn { role: "ToneNAC"; title: "Tone/NAC"; width: 100 },
                TableViewColumn { role: "Mode"; title: "Mode"; width: 80 },
                TableViewColumn { role: "Encryption"; title: "Encryption"; width: 100 },
                TableViewColumn { role: "Notes"; title: "Notes"; width: 160 }
            ]
        }

        Row {
            Layout.alignment: Qt.AlignRight
            spacing: 6
            Button { text: "Back"; onClicked: root.back() }
            Button { text: "Export PDF"; onClicked: root.exportPdf() }
            Button { text: "Print"; onClicked: root.printRequested() }
            Button { text: "Close"; onClicked: root.closeRequested() }
        }
    }
}
