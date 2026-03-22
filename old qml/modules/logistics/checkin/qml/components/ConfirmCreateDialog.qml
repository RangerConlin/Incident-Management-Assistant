import QtQuick 2.15
import QtQuick.Controls 2.15

// Dialog asking user to confirm creation of new master record
Dialog {
    id: dlg
    property string entityType
    property var payload
    title: "Create New"
    modal: true

    Column {
        spacing: 8
        Text { text: "Record not found. Create new master record?" }
        Row {
            spacing: 8
            Button { text: "Create"; onClicked: { checkInBridge.createNew(entityType, payload); dlg.close() } }
            Button { text: "Cancel"; onClicked: dlg.close() }
        }
    }
}
