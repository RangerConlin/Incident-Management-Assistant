import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Label { text: "Advanced / Experimental"; font.pixelSize: 22 }

        CheckBox {
            text: "Enable Sandbox Mode"
            checked: settingsBridge.getSetting("sandboxMode") ?? false
            onCheckedChanged: settingsBridge.setSetting("sandboxMode", checked)
        }

        CheckBox {
            text: "Enable AI Recommendations"
            checked: settingsBridge.getSetting("aiRecommendations") ?? true
            onCheckedChanged: settingsBridge.setSetting("aiRecommendations", checked)
        }

        CheckBox {
            text: "Enable LAN Collaboration"
            checked: settingsBridge.getSetting("lanCollaboration") ?? true
            onCheckedChanged: settingsBridge.setSetting("lanCollaboration", checked)
        }

        CheckBox {
            text: "Enable UI Debug Tools"
            checked: settingsBridge.getSetting("uiDebugTools") ?? false
            onCheckedChanged: settingsBridge.setSetting("uiDebugTools", checked)
        }
    }
}
