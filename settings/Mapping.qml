import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Mapping & GPS"; font.pixelSize: 22 }

        RowLayout {
            spacing: 10
            Label { text: "Basemap Source:"; width: 150 }
            ComboBox {
                model: ["Offline", "OpenStreetMap", "ESRI"]
                currentIndex: settingsBridge.getSetting("basemapSource") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("basemapSource", currentIndex)
            }
        }

        CheckBox {
            text: "Enable Grid Overlay"
            checked: settingsBridge.getSetting("gridOverlay") ?? true
            onCheckedChanged: settingsBridge.setSetting("gridOverlay", checked)
        }

        CheckBox {
            text: "Enable Fog of War Visualization"
            checked: settingsBridge.getSetting("fogOfWar") ?? false
            onCheckedChanged: settingsBridge.setSetting("fogOfWar", checked)
        }

        CheckBox {
            text: "Enable Live Tracking (Teams, Vehicles, Aircraft)"
            checked: settingsBridge.getSetting("liveTracking") ?? true
            onCheckedChanged: settingsBridge.setSetting("liveTracking", checked)
        }
    }
}
