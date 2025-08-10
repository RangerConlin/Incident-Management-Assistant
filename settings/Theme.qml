import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Theme & Appearance"; font.pixelSize: 22 }

        RowLayout {
            spacing: 10
            Label { text: "Theme:"; width: 150 }
            ComboBox {
                model: ["System Default", "Dark", "Light", "Custom"]
                currentIndex: settingsBridge.getSetting("themeIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("themeIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "Font Size:"; width: 150 }
            ComboBox {
                model: ["Small", "Medium", "Large"]
                currentIndex: settingsBridge.getSetting("fontSizeIndex") ?? 1
                onCurrentIndexChanged: settingsBridge.setSetting("fontSizeIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "Color Profile:"; width: 150 }
            ComboBox {
                model: ["Standard SAR", "High Contrast", "Colorblind Safe"]
                currentIndex: settingsBridge.getSetting("colorProfileIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("colorProfileIndex", currentIndex)
            }
        }

        RowLayout {
            spacing: 10
            Label { text: "UI Template:"; width: 150 }
            ComboBox {
                model: ["Default", "Compact", "Wide", "Operator View"]
                currentIndex: settingsBridge.getSetting("uiTemplateIndex") ?? 0
                onCurrentIndexChanged: settingsBridge.setSetting("uiTemplateIndex", currentIndex)
            }
        }
    }
}
