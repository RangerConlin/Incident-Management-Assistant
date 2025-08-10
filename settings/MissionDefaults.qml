import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Mission Defaults"; font.pixelSize: 22 }

        CheckBox {
            text: "Auto-fill ICS Forms"
            checked: settingsBridge.getSetting("autoFillForms") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoFillForms", checked)
        }

        CheckBox {
            text: "Auto-assign Equipment on Status Change"
            checked: settingsBridge.getSetting("autoAssignEquipment") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoAssignEquipment", checked)
        }

        CheckBox {
            text: "Auto-set Personnel Status to 'Available' on Check-In"
            checked: settingsBridge.getSetting("autoSetAvailable") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoSetAvailable", checked)
        }

        CheckBox {
            text: "Demobilized = Status Change to 'Demobilized'"
            checked: settingsBridge.getSetting("autoDemobilize") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoDemobilize", checked)
        }

        CheckBox {
            text: "Show Only Active Missions by Default"
            checked: settingsBridge.getSetting("filterActiveMissions") ?? true
            onCheckedChanged: settingsBridge.setSetting("filterActiveMissions", checked)
        }
    }
}
