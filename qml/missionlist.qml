import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 800
    height: 500

    signal missionSelected(int missionId)

    Rectangle {
        anchors.fill: parent
        color: "#f0f0f0"
        anchors.margins: 10

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "Select Active Mission"
                font.pixelSize: 20
                Layout.alignment: Qt.AlignHCenter
            }

            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: missionModel
                spacing: 5
                 clip: true

                delegate: Rectangle {
                    width: listView.width
                    height: 40
                    color: ListView.isCurrentItem ? "#d0f0ff" : "#ffffff"
                    border.color: "#cccccc"

                    RowLayout {
                        anchors.fill: parent
                        spacing: 20

                        Text {
                            text: model.number
                            Layout.preferredWidth: 100
                        }

                        Text {
                            text: model.name
                            Layout.fillWidth: true
                        }

                        Text {
                            text: model.type
                            Layout.preferredWidth: 100
                        }

                        Text {
                            text: model.status
                            Layout.preferredWidth: 80
                        }

                        Text {
                            text: model.icp_location
                            Layout.preferredWidth: 200
                        }
                    }

                    MouseArea {
                        id: clickArea
                        anchors.fill: parent
                        property int clickCount: 0
                        property bool timerRunning: false

                        Timer {
                            id: clickTimer
                            interval: 300
                            repeat: false
                            onTriggered: clickCount = 0
                        }

                        onClicked: {
                            clickCount += 1

                            if (!clickTimer.running) {
                                clickTimer.start()
                            }

                            if (clickCount === 2) {
                                clickTimer.stop()
                                clickCount = 0
                                console.log("Double-click detected on ID:", model.id)
                                root.missionSelected(model.id)
                            }
                        }
                    }

                    }
                }
            }
        }
    }

