import QtQuick 2.15
import QtQuick.Controls 2.15

// Simple lookup panel allowing search by ID or name
Item {
    property string entityType: "personnel"
    signal search(string entityType, string mode, string value)

    Column {
        spacing: 4
        Row {
            RadioButton { id: byId; text: "ID"; checked: true }
            RadioButton { id: byName; text: "Name" }
        }
        TextField { id: input; placeholderText: byId.checked ? "ID" : "Name" }
        Button {
            text: "Search"
            onClicked: {
                search(entityType, byId.checked ? "id" : "name", input.text)
                checkInBridge.lookup(entityType, byId.checked ? "id" : "name", input.text)
            }
        }
    }
}
