import QtQuick
import QtQuick.Controls

Item {
    width: 600
    height: 400
    TabView {
        anchors.fill: parent
        Tab { title: "Narrative"; ListView { anchors.fill: parent } }
        Tab { title: "Related" }
        Tab { title: "Rules" }
        Tab { title: "Export"; Ics214ExportDialog { anchors.fill: parent } }
    }
}
