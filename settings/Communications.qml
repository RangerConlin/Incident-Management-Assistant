import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Communications"; font.pixelSize: 22 }

        CheckBox {
            text: "Enable Mobile App Integration"
            checked: settingsBridge.getSetting("mobileAppIntegration") ?? true
            onCheckedChanged: settingsBridge.setSetting("mobileAppIntegration", checked)
        }

        CheckBox {
            text: "Auto-generate ICS 205"
            checked: settingsBridge.getSetting("autoGenerateICS205") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoGenerateICS205", checked)
        }

        RowLayout {
            spacing: 10
            Label { text: "Comms Log Verbosity:"; width: 150 }
            ComboBox {
                model: ["None", "Summary", "Full"]
                currentIndex: settingsBridge.getSetting("commsLogVerbosity") ?? 1
                onCurrentIndexChanged: settingsBridge.setSetting("commsLogVerbosity", currentIndex)
            }
        }
    }
}
