import QtQuick
import QtQuick.Shapes

// JARVIS's face, after the Sphere in Las Vegas (ui/sphere.webp): a big pale lit sphere with two
// round white eyes and thin curved brows. No mouth. Everything arrives as properties; this file
// decides only how each mood looks.
Item {
    id: face

    property color accent: "#4F8CFF"
    property string expression: "calm"
    property real voice: 0          // 0..1 microphone level, only while listening
    property real gazeX: 0          // -1..1, where to look
    property real gazeY: 0
    property string sky: ""         // "sun" while ready, "moon" while asleep, "" otherwise
    property string body: ""        // which planet: moon, mars, jupiter, saturn, earth...

    // Drawn once into a texture and reused: the window repaints 60 fps for the halo, and the
    // face only changes when it blinks, glances or changes mood.
    layer.enabled: true
    layer.smooth: true

    readonly property bool awake: expression !== "asleep"
    readonly property bool asleep: sky === "moon"
    readonly property bool lookingAway: expression === "thinking"

    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }
    /// Half the width of the sphere at height `y`, so bands and caps end exactly at its edge.
    /// (clip: true would only clip to a rectangle, which let them run off the side.)
    function chord(y, radius) {
        var dy = Math.abs(radius - y)
        return dy >= radius ? 0 : Math.sqrt(radius * radius - dy * dy)
    }

    function mix(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1)
    }

    /// Waking up: two happy bounces and a gleam across the eyes.
    function celebrate() { wakeUp.restart() }

    // The sphere is lit warm white and washed with the state colour, so you can still read the
    // state across the room while it stays a pale, friendly sphere.
    readonly property color skin: mix(Qt.rgba(0.95, 0.93, 0.87, 1), accent, 0.42)
    readonly property color ink: "#12151E"

    // lids: how open the eyes are. curve: the closed/happy line, negative arches upward.
    readonly property var moods: ({
        "waking":    { open: 0.55, curve:  2, browLift:  0, browAngle:  0, pupil: 0.95 },
        "calm":      { open: 1.00, curve:  2, browLift:  0, browAngle:  0, pupil: 1.00 },
        "alert":     { open: 1.12, curve:  1, browLift:  6, browAngle: -4, pupil: 1.25 },
        "listening": { open: 1.06, curve:  1, browLift:  4, browAngle: -3, pupil: 1.15 },
        "thinking":  { open: 0.70, curve:  3, browLift: -2, browAngle: 10, pupil: 0.85 },
        "focused":   { open: 0.80, curve:  3, browLift: -1, browAngle:  7, pupil: 0.92 },
        "warm":      { open: 0.00, curve:-13, browLift:  5, browAngle: -6, pupil: 1.00 },
        "concerned": { open: 0.85, curve:  4, browLift: -4, browAngle: 15, pupil: 0.72 },
        "asleep":    { open: 0.06, curve:  3, browLift: -1, browAngle:  0, pupil: 0.80 }
    })
    readonly property var mood: moods[expression] !== undefined ? moods[expression] : moods["calm"]

    property real open: mood.open
    property real curve: mood.curve
    property real browLift: mood.browLift
    property real browAngle: mood.browAngle
    property real pupilScale: mood.pupil + face.voice * 0.30
    Behavior on open { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    Behavior on curve { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    Behavior on browLift { NumberAnimation { duration: 300; easing.type: Easing.OutBack } }
    Behavior on browAngle { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
    Behavior on pupilScale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    // Thinking looks up and away and wanders; otherwise the eyes follow the mouse.
    property real wanderX: -0.45
    SequentialAnimation on wanderX {
        running: face.lookingAway
        loops: Animation.Infinite
        NumberAnimation { to: -0.62; duration: 1500; easing.type: Easing.InOutSine }
        NumberAnimation { to: -0.16; duration: 1900; easing.type: Easing.InOutSine }
    }
    property real lookX: lookingAway ? wanderX : gazeX
    property real lookY: lookingAway ? -0.55 : gazeY
    Behavior on lookX { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }
    Behavior on lookY { NumberAnimation { duration: 140; easing.type: Easing.OutQuad } }

    // Blink: both eyes together, on a human-ish irregular rhythm.
    property real blink: 0
    Timer {
        interval: 2600
        running: face.awake
        repeat: true
        onTriggered: { blinkAnimation.restart(); interval = 2200 + Math.random() * 4200 }
    }
    SequentialAnimation {
        id: blinkAnimation
        NumberAnimation { target: face; property: "blink"; to: 1.0; duration: 70; easing.type: Easing.OutQuad }
        NumberAnimation { target: face; property: "blink"; to: 0.0; duration: 120; easing.type: Easing.InQuad }
    }

    // Waking: bounce twice, and let a gleam run across the eyes as they open.
    property real hop: 0     // 0..1, how far into a bounce
    property real shine: 0   // 0..1, the gleam in the eyes
    SequentialAnimation {
        id: wakeUp
        ParallelAnimation {
            SequentialAnimation {
                NumberAnimation { target: face; property: "hop"; to: 1; duration: 190; easing.type: Easing.OutCubic }
                NumberAnimation { target: face; property: "hop"; to: 0; duration: 240; easing.type: Easing.OutBounce }
                NumberAnimation { target: face; property: "hop"; to: 0.55; duration: 150; easing.type: Easing.OutCubic }
                NumberAnimation { target: face; property: "hop"; to: 0; duration: 260; easing.type: Easing.OutBounce }
            }
            SequentialAnimation {
                NumberAnimation { target: face; property: "shine"; to: 1; duration: 260; easing.type: Easing.OutQuad }
                PauseAnimation { duration: 260 }
                NumberAnimation { target: face; property: "shine"; to: 0; duration: 700; easing.type: Easing.InQuad }
            }
        }
    }

    // How open the eyes are right now, and how the round eye and the closed line share the screen.
    readonly property real openNow: face.open * (1 - face.blink)
    readonly property real roundEye: Math.min(1, openNow / 0.28)

    Item {
        id: body
        anchors.fill: parent
        scale: 1 + face.hop * 0.09
        transformOrigin: Item.Bottom

        Shape {  // the sphere
            id: sphere
            anchors.centerIn: parent
            width: 132; height: 132
            preferredRendererType: Shape.CurveRenderer
            scale: 1.0 + face.voice * 0.04
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: 66; centerY: 66; centerRadius: 70
                    focalX: 46; focalY: 40
                    GradientStop { position: 0.0; color: Qt.lighter(face.skin, 1.14 + face.shine * 0.14) }
                    GradientStop { position: 0.55; color: face.skin }
                    GradientStop { position: 1.0; color: Qt.darker(face.skin, 1.5) }
                }
                PathAngleArc { centerX: 66; centerY: 66; radiusX: 66; radiusY: 66; sweepAngle: 360 }
            }

            Rectangle {  // rim light, brighter when it hears you and as it wakes
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.width: 1 + face.shine
                border.color: face.withAlpha(Qt.lighter(face.accent, 1.3),
                                             0.35 + face.voice * 0.4 + face.shine * 0.5)
            }

            // What makes each body itself: craters, bands, seas, storms. Everything is clipped to
            // the sphere and fades in and out with the state, so nothing animates while it sits.
            Item {
                anchors.fill: parent

                // Craters: the Moon, and Mercury with smaller ones.
                Repeater {
                    model: [{"x": 26, "y": 34, "r": 13}, {"x": 84, "y": 24, "r": 8},
                            {"x": 92, "y": 78, "r": 16}, {"x": 40, "y": 92, "r": 10}, {"x": 62, "y": 56, "r": 6}]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property real shrink: face.body === "mercury" ? 0.62 : 1
                        x: modelData.x - modelData.r * shrink
                        y: modelData.y - modelData.r * shrink
                        width: modelData.r * 2 * shrink
                        height: width
                        radius: width / 2
                        color: Qt.darker(face.skin, 1.13)
                        opacity: (face.body === "moon" || face.body === "mercury") ? 0.75 : 0
                        Behavior on opacity { NumberAnimation { duration: 600 } }
                    }
                }

                // Jupiter's bands, and a thinner set for Neptune and Uranus.
                Repeater {
                    model: [{"y": 22, "h": 9}, {"y": 44, "h": 14}, {"y": 74, "h": 11}, {"y": 98, "h": 8}]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool gas: ["jupiter", "neptune", "uranus"].indexOf(face.body) >= 0
                        readonly property real half: face.chord(
                            modelData.y + modelData.h / 2 < 66 ? modelData.y : modelData.y + modelData.h, 66)
                        x: 66 - half; width: half * 2
                        y: modelData.y
                        height: face.body === "jupiter" ? modelData.h : modelData.h * 0.45
                        radius: height / 2
                        color: Qt.darker(face.skin, face.body === "jupiter" ? 1.16 : 1.09)
                        opacity: gas ? 0.8 : 0
                        Behavior on opacity { NumberAnimation { duration: 600 } }
                    }
                }

                // Jupiter's great storm.
                Rectangle {
                    x: 84; y: 62
                    width: 26; height: 16
                    radius: 8
                    color: Qt.darker(face.skin, 1.45)
                    opacity: face.body === "jupiter" ? 0.75 : 0
                    Behavior on opacity { NumberAnimation { duration: 600 } }
                }

                // Earth's land and Mars's dark plains, in the same blobs, tinted differently.
                Repeater {
                    model: [{"x": 18, "y": 40, "w": 34, "h": 26, "r": 12},
                            {"x": 70, "y": 22, "w": 26, "h": 20, "r": 9},
                            {"x": 80, "y": 74, "w": 34, "h": 28, "r": 13},
                            {"x": 34, "y": 86, "w": 22, "h": 16, "r": 8}]
                    delegate: Rectangle {
                        required property var modelData
                        x: modelData.x; y: modelData.y
                        width: modelData.w; height: modelData.h
                        radius: modelData.r
                        color: face.body === "earth" ? "#5FA86B" : Qt.darker(face.skin, 1.35)
                        opacity: (face.body === "earth" || face.body === "mars") ? 0.72 : 0
                        Behavior on opacity { NumberAnimation { duration: 600 } }
                    }
                }

                // Polar caps: bright on Mars, white on Earth.
                Repeater {
                    model: 2
                    delegate: Rectangle {
                        required property int index
                        readonly property real half: face.chord(index === 0 ? 3 : 129, 66)
                        x: 66 - half; width: half * 2
                        height: 11
                        y: index === 0 ? 3 : parent.height - 14
                        radius: height / 2
                        color: "#F2F7FF"
                        opacity: (face.body === "mars" || face.body === "earth") ? 0.7 : 0
                        Behavior on opacity { NumberAnimation { duration: 600 } }
                    }
                }
            }
        }

        Row {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -2
            spacing: 16

            Repeater {
                model: 2

                delegate: Item {
                    required property int index
                    readonly property real inward: index === 0 ? 1 : -1  // brows tilt towards the middle
                    width: 36
                    height: 58

                    Shape {  // brow — a thin arch, put away while JARVIS sleeps
                        y: 2 - face.browLift
                        width: 32; height: 10
                        x: 2
                        preferredRendererType: Shape.CurveRenderer
                        rotation: face.browAngle * parent.inward
                        transformOrigin: Item.Center
                        opacity: face.asleep ? 0 : 1
                        Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
                        ShapePath {
                            strokeColor: face.ink
                            strokeWidth: 3.4
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            startX: 1; startY: 7
                            PathQuad { x: 31; y: 7; controlX: 16; controlY: -1 }
                        }
                    }

                    Item {  // the eye
                        y: 20
                        width: 36; height: 36

                        Item {  // squashed as the eye closes
                            anchors.fill: parent
                            opacity: face.roundEye
                            transform: Scale {
                                origin.x: 18; origin.y: 18
                                yScale: Math.max(0.04, face.openNow)
                            }

                            Rectangle {  // the white of the eye
                                anchors.fill: parent
                                radius: width / 2
                                color: "#FFFFFF"
                            }

                            Item {  // pupil, moved by the gaze
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: face.lookX * 9
                                anchors.verticalCenterOffset: face.lookY * 7

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 18; height: 18
                                    radius: 9
                                    scale: face.pupilScale
                                    color: face.ink
                                }
                                Rectangle {  // catch-light, which flares as JARVIS wakes
                                    x: -7; y: -8
                                    width: 5; height: 5
                                    radius: 2.5
                                    color: "#FFFFFF"
                                    opacity: 0.9
                                    scale: 1 + face.shine * 1.4
                                }
                                Rectangle {  // a second, smaller spark - only while it gleams
                                    x: 3; y: 3
                                    width: 3; height: 3
                                    radius: 1.5
                                    color: "#FFFFFF"
                                    opacity: face.shine * 0.9
                                }
                            }
                        }

                        Shape {  // the closed eye, and the happy arc when it smiles
                            anchors.fill: parent
                            preferredRendererType: Shape.CurveRenderer
                            opacity: 1 - face.roundEye
                            ShapePath {
                                strokeColor: face.ink
                                strokeWidth: 3.6
                                fillColor: "transparent"
                                capStyle: ShapePath.RoundCap
                                startX: 2; startY: 18
                                PathQuad { x: 34; y: 18; controlX: 18; controlY: 18 + face.curve * 2 }
                            }
                        }
                    }
                }
            }
        }
    }
}
