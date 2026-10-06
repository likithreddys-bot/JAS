import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

// VEM dashboard: status, activity timeline and settings. Data comes from `dashboard` (ui/dashboard.py).
Window {
    id: root
    width: 880
    height: 620
    minimumWidth: 700
    minimumHeight: 520
    visible: false
    title: bridge.assistantName
    color: "#080706"

    readonly property string uiFont: "Segoe UI Variable Display"
    readonly property color line: "#2A2419"
    readonly property color dim: "#A69C8D"
    readonly property color bright: "#F7F1E6"
    readonly property color gold: "#E8BE76"
    property int tab: 0

    Timer { interval: 2000; running: root.visible; repeat: true; onTriggered: dashboard.refresh() }
    onVisibleChanged: if (visible) dashboard.refresh()

    component Card: Rectangle {
        radius: 14
        color: "#15110D"
        border.width: 1
        border.color: root.line
    }
    component Heading: Text {
        color: root.dim
        font { family: root.uiFont; pixelSize: 11; letterSpacing: 1.4; capitalization: Font.AllUppercase }
    }
    component Value: Text {
        color: root.bright
        font { family: root.uiFont; pixelSize: 26; weight: Font.DemiBold }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        RowLayout {  // header
            spacing: 14
            Item {  // the orb in miniature, in the colour of the current state
                width: 44; height: 44
                Layout.alignment: Qt.AlignVCenter
                GlassOrb {
                    width: 180; height: 180
                    anchors.centerIn: parent
                    scale: 44 / 180
                    accent: dashboard.status.color
                    active: root.visible
                    look: bridge.look
                }
            }
            Text {
                text: bridge.assistantName
                color: root.bright
                font { family: root.uiFont; pixelSize: 17; weight: Font.DemiBold; letterSpacing: 5 }
            }
            Text {
                text: dashboard.status.state + "  ·  up " + dashboard.status.uptime
                color: root.dim
                font { family: root.uiFont; pixelSize: 13 }
            }
            Item { Layout.fillWidth: true }
            Repeater {
                model: ["Overview", "Activity", "Settings"]
                delegate: Button {
                    required property int index
                    required property string modelData
                    text: modelData
                    flat: true
                    onClicked: root.tab = index
                    contentItem: Text {
                        text: parent.text
                        color: root.tab === index ? root.bright : root.dim
                        font { family: root.uiFont; pixelSize: 13 }
                    }
                    background: Rectangle {
                        radius: 9
                        color: root.tab === index ? "#2A2113" : "transparent"
                    }
                }
            }
        }

        StackLayout {
            currentIndex: root.tab
            Layout.fillWidth: true
            Layout.fillHeight: true

            // ---------- Overview ----------
            ColumnLayout {
                spacing: 14
                RowLayout {
                    spacing: 14
                    Layout.fillWidth: true
                    Repeater {
                        model: [
                            {title: "Requests today", value: dashboard.status.requests},
                            {title: "Actions taken", value: dashboard.status.actions},
                            {title: "Things remembered", value: dashboard.status.facts},
                            {title: "Open to-dos", value: dashboard.status.todos},
                        ]
                        delegate: Card {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 84
                            ColumnLayout {
                                anchors { fill: parent; margins: 14 }
                                spacing: 4
                                Heading { text: modelData.title }
                                Value { text: modelData.value }
                            }
                        }
                    }
                }
                RowLayout {
                    spacing: 14
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Card {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors { fill: parent; margins: 16 }
                            spacing: 8
                            Heading { text: "Coming up" }
                            Text {
                                text: "Meetings today"
                                color: root.dim
                                font { family: root.uiFont; pixelSize: 12 }
                            }
                            Repeater {
                                model: dashboard.status.meetings.length ? dashboard.status.meetings : ["Nothing scheduled"]
                                delegate: Text {
                                    required property string modelData
                                    text: "•  " + modelData
                                    color: root.bright
                                    font { family: root.uiFont; pixelSize: 13 }
                                }
                            }
                            Item { height: 6 }
                            Text {
                                text: "Reminders"
                                color: root.dim
                                font { family: root.uiFont; pixelSize: 12 }
                            }
                            Repeater {
                                model: dashboard.status.reminders.length ? dashboard.status.reminders : ["None set"]
                                delegate: Text {
                                    required property string modelData
                                    text: "•  " + modelData
                                    color: root.bright
                                    font { family: root.uiFont; pixelSize: 13 }
                                }
                            }
                            Item { Layout.fillHeight: true }
                        }
                    }
                    Card {
                        Layout.preferredWidth: 280
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors { fill: parent; margins: 16 }
                            spacing: 10
                            Heading { text: "Connected" }
                            Repeater {
                                model: dashboard.status.services
                                delegate: RowLayout {
                                    required property var modelData
                                    spacing: 8
                                    Text {
                                        text: modelData.ok ? "✓" : "✕"
                                        color: modelData.ok ? "#A8CF78" : "#EE7A63"
                                        font { family: root.uiFont; pixelSize: 13; weight: Font.Bold }
                                    }
                                    Text {
                                        text: modelData.name
                                        color: root.bright
                                        font { family: root.uiFont; pixelSize: 13 }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                            Heading { text: "This app" }
                            Text {
                                text: "CPU " + dashboard.status.cpu + "   ·   RAM " + dashboard.status.ram
                                color: root.dim
                                font { family: root.uiFont; pixelSize: 13 }
                            }
                            Button {
                                text: "Open logs folder"
                                onClicked: dashboard.openLogs()
                                contentItem: Text {
                                    text: parent.text; color: root.dim
                                    font { family: root.uiFont; pixelSize: 12 }
                                }
                                background: Rectangle { radius: 8; color: "#1D1810"; border.width: 1; border.color: root.line }
                            }
                        }
                    }
                }
                Card {  // type to the assistant
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    RowLayout {
                        anchors { fill: parent; margins: 8 }
                        spacing: 8
                        TextField {
                            id: typeBox
                            Layout.fillWidth: true
                            placeholderText: "Type a request instead of speaking, then press Enter"
                            placeholderTextColor: root.dim
                            color: root.bright
                            font { family: root.uiFont; pixelSize: 14 }
                            background: Rectangle { color: "transparent" }
                            onAccepted: if (text.trim()) { dashboard.ask(text); text = "" }
                        }
                        Button {
                            text: "Send"
                            enabled: typeBox.text.trim().length > 0
                            onClicked: { dashboard.ask(typeBox.text); typeBox.text = "" }
                            contentItem: Text {
                                text: parent.text; color: parent.enabled ? "#080706" : root.dim
                                font { family: root.uiFont; pixelSize: 13; weight: Font.DemiBold }
                            }
                            background: Rectangle { radius: 8; color: parent.enabled ? root.gold : "#1D1810" }
                        }
                    }
                }
            }

            // ---------- Activity ----------
            Card {
                ListView {
                    anchors { fill: parent; margins: 14 }
                    clip: true
                    spacing: 10
                    model: dashboard.activity
                    ScrollBar.vertical: ScrollBar {}
                    delegate: RowLayout {
                        required property var modelData
                        width: ListView.view.width
                        spacing: 12
                        Text {
                            text: modelData.time
                            color: root.dim
                            Layout.preferredWidth: 72
                            font { family: root.uiFont; pixelSize: 12 }
                        }
                        Text {
                            text: modelData.icon
                            font { family: root.uiFont; pixelSize: 13 }
                        }
                        Text {
                            text: modelData.text
                            color: root.bright
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            font { family: root.uiFont; pixelSize: 13 }
                        }
                    }
                }
            }

            // ---------- Settings ----------
            ColumnLayout {
                spacing: 12
                Card {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ListView {
                        id: settingsView
                        anchors { fill: parent; margins: 16 }
                        clip: true
                        spacing: 12
                        model: dashboard.settingsList
                        ScrollBar.vertical: ScrollBar {}
                        property var edits: ({})
                        delegate: RowLayout {
                            required property var modelData
                            width: settingsView.width - 16
                            spacing: 14
                            ColumnLayout {
                                Layout.preferredWidth: 250
                                spacing: 2
                                Text {
                                    text: modelData.label; color: root.bright
                                    font { family: root.uiFont; pixelSize: 13 }
                                }
                                Text {
                                    text: modelData.hint; color: root.dim; wrapMode: Text.Wrap
                                    Layout.preferredWidth: 250
                                    font { family: root.uiFont; pixelSize: 11 }
                                }
                            }
                            TextField {
                                Layout.fillWidth: true
                                text: modelData.value
                                color: root.bright
                                font { family: root.uiFont; pixelSize: 13 }
                                onTextChanged: settingsView.edits[modelData.key] = text
                                background: Rectangle {
                                    radius: 8; color: "#1D1810"; border.width: 1
                                    border.color: parent.activeFocus ? root.gold : root.line
                                }
                            }
                        }
                    }
                }
                RowLayout {
                    spacing: 12
                    Text {
                        id: savedNote
                        text: ""
                        color: root.dim
                        Layout.fillWidth: true
                        font { family: root.uiFont; pixelSize: 12 }
                    }
                    Button {
                        text: "Restart " + bridge.assistantName
                        onClicked: dashboard.restart()
                        contentItem: Text { text: parent.text; color: root.dim; font { family: root.uiFont; pixelSize: 13 } }
                        background: Rectangle { radius: 8; color: "#1D1810"; border.width: 1; border.color: root.line }
                    }
                    Button {
                        text: "Save settings"
                        onClicked: dashboard.save(settingsView.edits)
                        contentItem: Text { text: parent.text; color: "#080706"; font { family: root.uiFont; pixelSize: 13; weight: Font.DemiBold } }
                        background: Rectangle { radius: 8; color: root.gold }
                    }
                }
            }
        }
    }

    Connections {
        target: dashboard
        function onSavedMessage(message) { savedNote.text = message }
    }
}
