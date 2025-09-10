import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    id: container
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    width: 360; height: parent.height

    property int spacing: 8

    Column {
        id: stack
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: container.spacing
        Repeater {
            id: repeater
            model: toastModel
            delegate: NotificationToast {
                mode: model.mode
                durationMs: model.durationMs
                title: model.title
                message: model.message
                severity: model.severity
                onDismissed: toastModel.remove(index)
            }
        }
    }

    ListModel { id: toastModel }

    function pushToast(payload) {
        toastModel.insert(0, payload)
    }
}
