import QtQuick 2.15
import QtQuick.Controls 2.15

Dialog {
    id: dlg
    title: "Select Aircraft"
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    property string selectedId: ""
    signal picked(string aircraftId)

    contentItem: Column {
        spacing: 6
        ListView { id: lv; width: 400; height: 300; model: ["(stub)"] }
    }
    onAccepted: picked(selectedId)
}

