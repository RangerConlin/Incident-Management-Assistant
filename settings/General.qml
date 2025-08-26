import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "General Settings"; font.pixelSize: 22 }

        RowLayout {
            spacing: 10
            Label { text: "Language:"; width: 150 }
            ComboBox {
                model: ["English", "Spanish", "French"]
                currentIndex: settingsBridge.getSetting("languageIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("languageIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "Date Format:"; width: 150 }
            ComboBox {
                model: ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
                currentIndex: settingsBridge.getSetting("dateFormatIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("dateFormatIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "Units:"; width: 150 }
            ComboBox {
                model: ["Imperial", "Metric"]
                currentIndex: settingsBridge.getSetting("unitIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("unitIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "Startup Behavior:"; width: 150 }
            ComboBox {
                model: ["Prompt for Incident", "Load Last Incident", "Create New Incident"]
                currentIndex: settingsBridge.getSetting("startupBehaviorIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("startupBehaviorIndex", currentIndex)
            }
        }
    }
}
