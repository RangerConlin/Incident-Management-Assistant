import QtQuick 2.15
import QtQuick.Controls 2.15

// Minimal form used when creating a new record
Item {
    id: root
    property string entityType: "personnel"
    property var payload: ({})
    signal submit(string entityType, var payload)

    Column {
        spacing: 4
        TextField { id: idField; placeholderText: "ID" }
        TextField { id: nameField; placeholderText: entityType === "aircraft" ? "Tail / Name" : "Name" }
        Button {
            text: "Create"
            onClicked: {
                payload = {id: idField.text}
                if (entityType === "personnel") {
                    var parts = nameField.text.split(" ")
                    payload.first_name = parts[0]
                    payload.last_name = parts[1] || ""
                } else if (entityType === "aircraft") {
                    payload.tail_number = nameField.text
                } else {
                    payload.name = nameField.text
                }
                submit(entityType, payload)
            }
        }
    }
}
