import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Data & Storage"; font.pixelSize: 22 }

        CheckBox {
            text: "Enable Local Sync Backup"
            checked: settingsBridge.getSetting("localSyncBackup") ?? true
            onCheckedChanged: settingsBridge.setSetting("localSyncBackup", checked)
        }

        CheckBox {
            text: "Enable Cloud Fallback if Local Fails"
            checked: settingsBridge.getSetting("cloudFallback") ?? false
            onCheckedChanged: settingsBridge.setSetting("cloudFallback", checked)
        }

        RowLayout {
            spacing: 10
            Label { text: "Auto-Backup Interval (min):"; width: 200 }
            SpinBox {
                from: 1; to: 60
                value: settingsBridge.getSetting("autoBackupInterval") ?? 5
                onValueChanged: settingsBridge.setSetting("autoBackupInterval", value)
            }
        }
    }
}
