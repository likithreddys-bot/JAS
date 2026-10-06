import QtQuick
import QtQuick.Window
import QtQuick.Shapes

// The floating VEM orb: a glass sphere ringed by waves of light (GlassOrb.qml) on a dark glass panel.
// All state comes from `bridge` (ui/bridge.py); this file only renders it.
Window {
    id: root
    width: 220
    height: Math.max(272, textColumn.y + textColumn.implicitHeight + 22)
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    title: bridge.assistantName

    readonly property string uiFont: "Segoe UI Variable Display"
    readonly property bool isPaused: bridge.state === "sleeping" || bridge.state === "resting"  // calm, still orb
    readonly property bool isBusy: ["thinking", "planning", "executing", "observing", "transcribing"].indexOf(bridge.state) >= 0
    readonly property bool isError: bridge.state === "error"
    readonly property bool isListening: bridge.state === "listening"

    // Smoothed microphone level, only meaningful while listening.
    property real voice: isListening ? bridge.level : 0
    Behavior on voice { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    property color accent: bridge.stateColor
    Behavior on accent { ColorAnimation { duration: 450; easing.type: Easing.InOutQuad } }

    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    property bool wasPaused: false
    // Waking from sleep is an event worth feeling: a ring of light breaks outward from the orb.
    property real wakeBurst: 0
    NumberAnimation { id: burstFade; target: root; property: "wakeBurst"; to: 0; duration: 900
                      easing.type: Easing.OutQuad }
    Connections {
        target: bridge
        function onStateChanged() {
            if (root.wasPaused && !root.isPaused) {
                root.wakeBurst = 1
                burstFade.restart()
            }
            root.wasPaused = root.isPaused
        }
    }

    // Grow upwards: keep the bottom edge where it was when the content changes size.
    property real lastHeight: height
    onHeightChanged: { y -= height - lastHeight; lastHeight = height }

    Component.onCompleted: {
        x = Screen.desktopAvailableWidth - width - 28
        y = Screen.desktopAvailableHeight - height - 28
    }

    // Glass panel: warm black, with the state's colour washed faintly through it
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: 28
        color: "#E0080706"
        border.width: 1
        border.color: root.withAlpha(Qt.lighter(root.accent, 1.3), 0.20)
        Behavior on border.color { ColorAnimation { duration: 450 } }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: root.withAlpha(root.accent, 0.075)
        }

        Rectangle {  // top sheen
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: parent.height * 0.5
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#10F7F1E6" }
                GradientStop { position: 1.0; color: "#00F7F1E6" }
            }
        }
    }

    DragHandler {
        target: null
        onActiveChanged: if (active) root.startSystemMove()
    }
    HoverHandler { id: hover }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: bridge.requestMenu()
    }

    Item {
        id: orbArea
        width: 180; height: 180
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 6
        scale: hover.hovered ? 1.03 : 1.0
        Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        GlassOrb {
            id: glass
            anchors.fill: parent
            accent: root.accent
            active: root.visible
            look: bridge.look
            voice: root.voice
            gazeX: bridge.gazeX
            gazeY: bridge.gazeY

            // Tell the bridge where the orb is on screen, so the light inside can lean towards the mouse.
            function reportPosition() {
                var centre = glass.mapToGlobal(glass.width / 2, glass.height / 2)
                bridge.watchFrom(centre.x, centre.y)
            }
            Component.onCompleted: reportPosition()
        }

        // A ring of light that breaks outward the moment VEM wakes.
        Shape {
            anchors.centerIn: parent
            width: 176; height: 176
            preferredRendererType: Shape.CurveRenderer
            visible: root.wakeBurst > 0.01
            opacity: root.wakeBurst
            scale: 0.72 + (1 - root.wakeBurst) * 0.55
            ShapePath {
                strokeColor: root.withAlpha(Qt.lighter(root.accent, 1.4), 0.9)
                strokeWidth: 2.5
                fillColor: "transparent"
                PathAngleArc { centerX: 88; centerY: 88; radiusX: 86; radiusY: 86; sweepAngle: 360 }
            }
        }
    }

    onXChanged: if (glass) glass.reportPosition()
    onYChanged: if (glass) glass.reportPosition()

    Column {
        id: textColumn
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: orbArea.bottom
        anchors.topMargin: 2
        spacing: 4

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: bridge.assistantName
            font.family: root.uiFont
            font.pixelSize: 13
            font.weight: Font.DemiBold
            font.letterSpacing: 5
            color: "#F7F1E6"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: bridge.stateLabel
            font.family: root.uiFont
            font.pixelSize: 12
            color: root.isError ? root.accent : "#A69C8D"
            Behavior on color { ColorAnimation { duration: 300 } }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 196
            horizontalAlignment: Text.AlignHCenter
            visible: bridge.caption.length > 0
            text: bridge.caption
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
            lineHeight: 1.1
            font.family: root.uiFont
            font.pixelSize: 11
            color: root.isError ? "#E8917F" : "#CFC5B4"
        }

        // Live task checklist
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 190
            spacing: 5
            topPadding: bridge.steps.length > 0 ? 6 : 0
            visible: bridge.steps.length > 0

            Repeater {
                model: bridge.steps
                delegate: Row {
                    required property var modelData
                    spacing: 8
                    width: 190
                    opacity: 0
                    Component.onCompleted: opacity = 1
                    Behavior on opacity { NumberAnimation { duration: 250 } }

                    Item {
                        width: 12; height: 14
                        Rectangle {  // pulsing dot while running
                            anchors.centerIn: parent
                            visible: modelData.status === "running"
                            width: 7; height: 7; radius: 3.5
                            color: root.accent
                            SequentialAnimation on opacity {
                                running: modelData.status === "running"
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.25; duration: 450 }
                                NumberAnimation { to: 1; duration: 450 }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: modelData.status !== "running"
                            text: modelData.status === "done" ? "✓" : "✕"
                            color: modelData.status === "done" ? "#A8CF78" : "#EE7A63"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                        }
                    }
                    Text {
                        width: 170
                        text: modelData.label
                        elide: Text.ElideRight
                        font.family: root.uiFont
                        font.pixelSize: 11
                        color: modelData.status === "running" ? "#F7F1E6" : "#A69C8D"
                    }
                }
            }
        }
    }
}
