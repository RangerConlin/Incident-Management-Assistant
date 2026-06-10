// qml/components/ConfirmDialog.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Dialog {
    id: dlg
    modal: true
    focus: true

    // Center safely without touching implicitWidth
    parent: Overlay.overlay
    anchors.centerIn: parent

    // Avoid any implicitWidth loops: set a fixed width for the dialog
    width: 420

    // API
    property alias text: msg.text
    property var onAccept: null

    title: "Confirm"

    contentItem: Column {
        spacing: 12
        padding: 16
        Label {
            id: msg
            wrapMode: Text.WordWrap
            width: 380
            text: ""
        }
    }

    footer: DialogButtonBox {
        standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        onAccepted: { if (dlg.onAccept) dlg.onAccept(); dlg.close(); }
        onRejected: dlg.close()
    }
}
