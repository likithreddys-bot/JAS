import QtQuick
import QtQuick.Window
import QtQuick.Shapes

// Floating JARVIS orb. All state comes from `bridge` (ui/bridge.py); this file only renders it.
Window {
    id: root
    width: 220
    height: Math.max(272, textColumn.y + textColumn.implicitHeight + 22)
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    title: "JARVIS"

    readonly property string uiFont: "Segoe UI Variable Display"
    readonly property bool isPaused: bridge.state === "sleeping"
    readonly property bool isBusy: ["thinking", "planning", "executing", "observing", "transcribing"].indexOf(bridge.state) >= 0
    readonly property bool isError: bridge.state === "error"
    readonly property bool isListening: bridge.state === "listening"

    // Smoothed microphone level, only meaningful while listening.
    property real voice: isListening ? bridge.level : 0
    Behavior on voice { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    property color accent: bridge.stateColor
    Behavior on accent { ColorAnimation { duration: 450; easing.type: Easing.InOutQuad } }

    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // 0..1 breathing phase driving halo and orb scale.
    property real breath: 0
    SequentialAnimation on breath {
        loops: Animation.Infinite
        NumberAnimation { to: 1; duration: root.isPaused ? 5200 : root.isError ? 900 : 3200; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: root.isPaused ? 5200 : root.isError ? 900 : 3200; easing.type: Easing.InOutSine }
    }

    // Grow upwards: keep the bottom edge where it was when the content changes size.
    property real lastHeight: height
    onHeightChanged: { y -= height - lastHeight; lastHeight = height }

    Component.onCompleted: {
        x = Screen.desktopAvailableWidth - width - 28
        y = Screen.desktopAvailableHeight - height - 28
    }

    // Glass panel
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: 28
        color: "#D90B0E14"
        border.width: 1
        border.color: "#14FFFFFF"

        Rectangle {  // top sheen
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: parent.height * 0.5
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#0DFFFFFF" }
                GradientStop { position: 1.0; color: "#00FFFFFF" }
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

        // Halo
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            opacity: Math.min(1, (root.isPaused ? 0.25 : 0.55) + root.breath * (root.isPaused ? 0.1 : 0.35) + root.voice * 0.6)
            scale: 0.9 + root.breath * 0.08 + root.voice * 0.14
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: 90; centerY: 90; centerRadius: 90
                    focalX: 90; focalY: 90
                    GradientStop { position: 0.35; color: root.withAlpha(root.accent, 0.45) }
                    GradientStop { position: 1.0; color: root.withAlpha(root.accent, 0.0) }
                }
                PathAngleArc { centerX: 90; centerY: 90; radiusX: 90; radiusY: 90; sweepAngle: 360 }
            }
        }

        // Orbit track
        Rectangle {
            anchors.centerIn: parent
            width: 128; height: 128; radius: 64
            color: "transparent"
            border.width: 1
            border.color: root.withAlpha(root.accent, 0.16)
        }

        // Orbit arc — slow when idle, fast when busy, still when paused.
        Shape {
            id: orbit
            anchors.centerIn: parent
            width: 128; height: 128
            preferredRendererType: Shape.CurveRenderer
            opacity: root.isPaused ? 0.35 : 0.9
            ShapePath {
                strokeColor: root.accent
                strokeWidth: 1.6
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: 64; centerY: 64; radiusX: 64; radiusY: 64; startAngle: -90; sweepAngle: root.isBusy ? 110 : 64 }
            }
            RotationAnimation on rotation {
                loops: Animation.Infinite
                from: 0; to: 360
                duration: root.isBusy ? 1400 : 9000
                running: !root.isPaused
            }
        }

        // Core orb
        Shape {
            anchors.centerIn: parent
            width: 88; height: 88
            preferredRendererType: Shape.CurveRenderer
            scale: 1.0 + root.breath * (root.isPaused ? 0.01 : 0.035) + root.voice * 0.12
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: 44; centerY: 44; centerRadius: 44
                    focalX: 32; focalY: 28
                    GradientStop { position: 0.0; color: Qt.lighter(root.accent, 1.55) }
                    GradientStop { position: 0.55; color: root.accent }
                    GradientStop { position: 1.0; color: Qt.darker(root.accent, 2.4) }
                }
                PathAngleArc { centerX: 44; centerY: 44; radiusX: 44; radiusY: 44; sweepAngle: 360 }
            }
            // Specular highlight
            Shape {
                x: 18; y: 12; width: 36; height: 24
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeWidth: -1
                    fillGradient: RadialGradient {
                        centerX: 18; centerY: 12; centerRadius: 18
                        focalX: 18; focalY: 12
                        GradientStop { position: 0.0; color: "#59FFFFFF" }
                        GradientStop { position: 1.0; color: "#00FFFFFF" }
                    }
                    PathAngleArc { centerX: 18; centerY: 12; radiusX: 18; radiusY: 12; sweepAngle: 360 }
                }
            }
        }
    }

    Column {
        id: textColumn
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: orbArea.bottom
        anchors.topMargin: 2
        spacing: 4

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "JARVIS"
            font.family: root.uiFont
            font.pixelSize: 13
            font.weight: Font.DemiBold
            font.letterSpacing: 4
            color: "#E8ECF4"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: bridge.stateLabel
            font.family: root.uiFont
            font.pixelSize: 12
            color: root.isError ? root.accent : "#9AA3B5"
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
            color: root.isError ? "#C98A92" : "#B4BCCB"
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
                            color: modelData.status === "done" ? "#6FE3B4" : "#FF7A85"
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
                        color: modelData.status === "running" ? "#E8ECF4" : "#8E97A8"
                    }
                }
            }
        }
    }
}
