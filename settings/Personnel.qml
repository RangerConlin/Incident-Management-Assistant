import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Personnel & Teams"; font.pixelSize: 22 }

        CheckBox {
            text: "Auto-clear Assignment on 'Out of Service'"
            checked: settingsBridge.getSetting("clearAssignmentOutOfService") ?? true
            onCheckedChanged: settingsBridge.setSetting("clearAssignmentOutOfService", checked)
        }

        CheckBox {
            text: "Filter 'No Show' by Default"
            checked: settingsBridge.getSetting("filterNoShow") ?? true
            onCheckedChanged: settingsBridge.setSetting("filterNoShow", checked)
        }

        CheckBox {
            text: "Enable Team Templates"
            checked: settingsBridge.getSetting("teamTemplatesEnabled") ?? true
            onCheckedChanged: settingsBridge.setSetting("teamTemplatesEnabled", checked)
        }
    }
}
