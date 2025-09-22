import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.margins: 12
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            TextField { id: prepared; placeholderText: "Prepared By" }
            TextField { id: position; placeholderText: "Position" }
        }
        Row {
            spacing: 6
            TextField { id: approved; placeholderText: "Approved By" }
            TextField { id: date; placeholderText: "Date" }
        }
        Button {
            text: "Save"
            onClicked: ics206Bridge.save_signatures({
                    prepared_by: prepared.text,
                    position: position.text,
                    approved_by: approved.text,
                    date: date.text
                })
        }
    }
    Component.onCompleted: {
        var data = ics206Bridge.get_signatures();
        prepared.text = data.prepared_by || "";
        position.text = data.position || "";
        approved.text = data.approved_by || "";
        date.text = data.date || "";
    }
}
