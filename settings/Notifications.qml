import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Notifications"; font.pixelSize: 22 }

        CheckBox {
            text: "Enable Sound Alerts"
            checked: settingsBridge.getSetting("soundAlerts") ?? true
            onCheckedChanged: settingsBridge.setSetting("soundAlerts", checked)
        }

        RowLayout {
            spacing: 10
            Label { text: "Volume:"; width: 150 }
            Slider {
                from: 0; to: 100
                value: settingsBridge.getSetting("volume") ?? 75
                onValueChanged: settingsBridge.setSetting("volume", value)
            }
        }

        CheckBox {
            text: "Critical Alerts Override Mute"
            checked: settingsBridge.getSetting("criticalOverride") ?? false
            onCheckedChanged: settingsBridge.setSetting("criticalOverride", checked)
        }

        CheckBox {
            text: "Notify on Task Updates"
            checked: settingsBridge.getSetting("notifyOnTasks") ?? true
            onCheckedChanged: settingsBridge.setSetting("notifyOnTasks", checked)
        }

        CheckBox {
            text: "Auto-dismiss Notifications after 10 seconds"
            checked: settingsBridge.getSetting("autoDismissNotifications") ?? true
            onCheckedChanged: settingsBridge.setSetting("autoDismissNotifications", checked)
        }
    }
}
