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

    /// A closed ring whose radius rises and falls, giving a wave that runs all the way round.
    function wavePoints(radius, amplitude, lobes, cx, cy) {
        var points = []
        for (var i = 0; i <= 240; i++) {
            var t = i / 240 * 2 * Math.PI
            var r = radius + amplitude * Math.sin(lobes * t)
            points.push(Qt.point(cx + r * Math.cos(t), cy + r * Math.sin(t)))
        }
        return points
    }

    // 0..1 breathing phase driving halo and orb scale.
    property real breath: 0
    SequentialAnimation on breath {
        loops: Animation.Infinite
        NumberAnimation { to: 1; duration: root.isPaused ? 5200 : root.isError ? 900 : 3200; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: root.isPaused ? 5200 : root.isError ? 900 : 3200; easing.type: Easing.InOutSine }
    }

    // Waking from sleep is an event worth feeling: the sun bounces, gleams and throws off a ring.
    property real wakeBurst: 0
    property string lastSky: bridge.sky
    NumberAnimation { id: burstFade; target: root; property: "wakeBurst"; to: 0; duration: 900
                      easing.type: Easing.OutQuad }
    Connections {
        target: bridge
        function onStateChanged() {
            if (bridge.sky === "sun" && root.lastSky === "moon") {
                root.wakeBurst = 1
                burstFade.restart()
                face.celebrate()
            }
            root.lastSky = bridge.sky
        }
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

        Rectangle {  // the body's colour, washed faintly through the glass
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: root.withAlpha(root.accent, 0.11)
        }

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

    // Night sky behind everything while JARVIS sleeps: stars drifting slowly upward.
    // Each field is cached as a texture and only its position animates, so this stays cheap.
    Item {
        id: nightSky
        anchors.fill: panel
        clip: true
        visible: opacity > 0.01
        opacity: bridge.sky === "moon" ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 900; easing.type: Easing.InOutQuad } }

        Item {
            id: drifting
            width: parent.width
            height: parent.height * 2
            y: 0
            NumberAnimation on y {
                running: nightSky.visible
                loops: Animation.Infinite
                from: 0; to: -nightSky.height
                duration: 60000
            }

            Repeater {
                model: 2
                delegate: Item {
                    required property int index
                    y: index * nightSky.height
                    width: nightSky.width
                    height: nightSky.height
                    layer.enabled: true

                    Repeater {
                        model: 34
                        delegate: Rectangle {
                            required property int index
                            // A fixed scatter: the same every run, so the sky never jumps about.
                            readonly property real seed: (index * 2654435761 % 10007) / 10007
                            readonly property real seed2: (index * 40503 % 9973) / 9973
                            x: seed * (parent.width - 3)
                            y: seed2 * (parent.height - 3)
                            width: 1 + (index % 3 === 0 ? 1.4 : 0)
                            height: width
                            radius: width / 2
                            color: "#DCE6FF"
                            opacity: 0.25 + seed * 0.55
                        }
                    }
                }
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

        // Orbit track — hidden for the sun, whose corona is the ring
        Rectangle {
            anchors.centerIn: parent
            width: 156; height: 156; radius: 78
            color: "transparent"
            border.width: 1
            border.color: root.withAlpha(root.accent, 0.16)
            opacity: bridge.sky === "sun" ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 500 } }
        }

        // Orbit arc — slow when idle, fast when busy, still when paused.
        Shape {
            id: orbit
            anchors.centerIn: parent
            width: 156; height: 156
            preferredRendererType: Shape.CurveRenderer
            opacity: bridge.sky === "sun" ? 0 : (root.isPaused ? 0.35 : 0.9)
            Behavior on opacity { NumberAnimation { duration: 500 } }
            ShapePath {
                strokeColor: root.accent
                strokeWidth: 1.6
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: 78; centerY: 78; radiusX: 78; radiusY: 78; startAngle: -90; sweepAngle: root.isBusy ? 110 : 64 }
            }
            RotationAnimation on rotation {
                loops: Animation.Infinite
                from: 0; to: 360
                duration: root.isBusy ? 1400 : 9000
                running: !root.isPaused
            }
        }

        // Corona: rays around the sphere while JARVIS is ready, turning slowly like a sun.
        Item {
            id: corona
            anchors.centerIn: parent
            width: 176; height: 176
            visible: opacity > 0.01
            opacity: bridge.sky === "sun" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }

            // Two wavy rings turning against each other. The geometry is built once and only
            // rotation, scale and opacity animate, so all this movement costs almost nothing.
            Repeater {
                model: [{"r": 74, "amp": 8.5, "lobes": 11, "w": 2.4, "a": 0.55, "spin": 26000, "dir": 1},
                        {"r": 66, "amp": 6.0, "lobes": 8,  "w": 1.6, "a": 0.32, "spin": 38000, "dir": -1}]
                delegate: Shape {
                    id: ring
                    required property var modelData
                    anchors.centerIn: parent
                    width: corona.width; height: corona.height
                    preferredRendererType: Shape.CurveRenderer
                    scale: 1 + corona.breathe * 0.045 + root.wakeBurst * 0.16

                    ShapePath {
                        strokeColor: root.withAlpha(Qt.lighter(root.accent, 1.2), ring.modelData.a)
                        strokeWidth: ring.modelData.w
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathPolyline { id: outline; path: [] }
                    }
                    Component.onCompleted: outline.path = root.wavePoints(
                        modelData.r, modelData.amp, modelData.lobes, corona.width / 2, corona.height / 2)

                    RotationAnimation on rotation {
                        running: corona.visible
                        loops: Animation.Infinite
                        from: ring.modelData.dir > 0 ? 0 : 360
                        to: ring.modelData.dir > 0 ? 360 : 0
                        duration: ring.modelData.spin
                    }
                }
            }

            // A slow swell, so the whole corona breathes with the sphere.
            property real breathe: 0
            SequentialAnimation on breathe {
                running: corona.visible
                loops: Animation.Infinite
                NumberAnimation { to: 1; duration: 2400; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0; duration: 2400; easing.type: Easing.InOutSine }
            }
        }

        // A ring of warmth that breaks outward the moment JARVIS wakes.
        Shape {
            id: burst
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

        // Saturn's rings, tilted around the sphere while JARVIS speaks.
        Item {
            anchors.centerIn: parent
            width: 190; height: 190
            rotation: -18
            visible: opacity > 0.01
            opacity: bridge.body === "saturn" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 500 } }

            Repeater {
                model: [{"w": 186, "h": 52, "t": 3.0, "a": 0.75},
                        {"w": 166, "h": 44, "t": 1.6, "a": 0.45}]
                delegate: Rectangle {
                    required property var modelData
                    anchors.centerIn: parent
                    width: modelData.w; height: modelData.h
                    radius: height / 2
                    color: "transparent"
                    border.width: modelData.t
                    border.color: root.withAlpha(Qt.lighter(root.accent, 1.25), modelData.a)
                }
            }
        }

        // The face
        Face {
            id: face
            anchors.centerIn: parent
            width: 150; height: 150
            accent: root.accent
            expression: bridge.expression
            sky: bridge.sky
            body: bridge.body
            voice: root.voice
            gazeX: bridge.gazeX
            gazeY: bridge.gazeY
            // Deliberately not tied to `breath`: the halo carries the breathing, and a face that
            // changed every frame would redraw the whole head 60 times a second for nothing.
            scale: 1.0 + root.voice * 0.06

            // Tell the bridge where the eyes are on screen, so they can follow the mouse.
            function reportPosition() {
                var centre = face.mapToGlobal(face.width / 2, face.height / 2)
                bridge.watchFrom(centre.x, centre.y)
            }
            Component.onCompleted: reportPosition()
        }

        // Sleeping: z's drifting up from the sphere's shoulder. They live out here rather than in
        // the Face, whose cached layer would clip anything that leaves the sphere.
        Repeater {
            model: 3
            delegate: Text {
                id: snore
                required property int index
                text: "z"
                color: "#BFF0FF"   // bright enough to read across the room
                font.family: root.uiFont
                font.pixelSize: 15 + index * 6
                style: Text.Outline
                styleColor: "#0A1420"
                font.italic: true
                font.bold: true
                x: 126; y: 50
                opacity: 0

                SequentialAnimation {
                    running: bridge.sky === "moon"
                    loops: Animation.Infinite
                    PauseAnimation { duration: snore.index * 850 }
                    ParallelAnimation {
                        NumberAnimation { target: snore; property: "opacity"; from: 0; to: 0.95; duration: 650 }
                        NumberAnimation { target: snore; property: "y"; from: 50; to: 24; duration: 650
                                          easing.type: Easing.OutQuad }
                        NumberAnimation { target: snore; property: "x"; from: 126; to: 140; duration: 650 }
                    }
                    ParallelAnimation {
                        NumberAnimation { target: snore; property: "opacity"; to: 0; duration: 850 }
                        NumberAnimation { target: snore; property: "y"; to: 2; duration: 850 }
                        NumberAnimation { target: snore; property: "x"; to: 156; duration: 850 }
                    }
                    PauseAnimation { duration: 2550 - snore.index * 850 }
                }
            }
        }
    }

    onXChanged: if (face) face.reportPosition()
    onYChanged: if (face) face.reportPosition()

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
