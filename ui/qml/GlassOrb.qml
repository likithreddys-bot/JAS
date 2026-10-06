import QtQuick
import QtQuick.Shapes

// VEM's core: a sphere of smoked glass with light drifting inside it, ringed by waves of light that
// revolve around it. There is no face; the state is read from the colour, the brightness and how
// the rings move. The same look as the website (website/src/core/JasCore.tsx).
//
// Everything arrives as properties; this file decides only how each look is drawn. Geometry is
// built once and only rotation, scale and opacity animate, so it costs almost nothing at idle.
Item {
    id: core

    property color accent: "#E8BE76"
    property string look: "calm"
    property bool active: true      // false while the window is hidden: nothing animates, nothing costs
    property real voice: 0          // 0..1 microphone level, only while listening
    property real gazeX: 0          // -1..1: the light inside leans towards the mouse
    property real gazeY: 0

    readonly property real cx: width / 2
    readonly property real cy: height / 2
    readonly property real radius: 44   // the sphere; the rings sit at 1.36 to 1.9 times this

    // One entry per look (theme.py STATE_LOOKS). glow = light inside the glass, halo = glow around it,
    // rim = light caught at the edge, waves = ring brightness, spin = how fast the rings revolve.
    readonly property var looks: ({
        "waking":    { glow: 0.60, halo: 0.35, rim: 0.70, waves: 0.40, spin: 0.6, orbit: 0, arc: 0, dot: 0, pulse: 0 },
        "calm":      { glow: 1.00, halo: 0.60, rim: 0.90, waves: 0.75, spin: 1.0, orbit: 0, arc: 0, dot: 0, pulse: 0 },
        "alert":     { glow: 1.25, halo: 1.00, rim: 1.20, waves: 1.00, spin: 2.2, orbit: 0, arc: 0, dot: 0, pulse: 0 },
        "listening": { glow: 1.30, halo: 1.10, rim: 1.20, waves: 1.00, spin: 2.4, orbit: 0, arc: 0, dot: 0, pulse: 0 },
        "thinking":  { glow: 0.60, halo: 0.30, rim: 0.70, waves: 0.45, spin: 1.4, orbit: 1, arc: 0, dot: 0, pulse: 0 },
        "focused":   { glow: 0.90, halo: 0.60, rim: 1.00, waves: 0.55, spin: 1.7, orbit: 0, arc: 1, dot: 0, pulse: 0 },
        "warm":      { glow: 1.10, halo: 0.75, rim: 1.00, waves: 1.00, spin: 1.6, orbit: 0, arc: 0, dot: 0, pulse: 1 },
        "concerned": { glow: 1.00, halo: 0.80, rim: 1.20, waves: 0.65, spin: 2.6, orbit: 0, arc: 0, dot: 0, pulse: 0 },
        "asleep":    { glow: 0.30, halo: 0.12, rim: 0.45, waves: 0.15, spin: 0.0, orbit: 0, arc: 0, dot: 1, pulse: 0 }
    })
    readonly property var current: looks[look] !== undefined ? looks[look] : looks["calm"]

    // Each number eases to its new value, so a change of state is a glide and not a cut.
    property real glow: current.glow
    property real halo: current.halo
    property real rim: current.rim
    property real waves: current.waves
    property real spin: current.spin
    property real orbit: current.orbit
    property real arc: current.arc
    property real dot: current.dot
    Behavior on glow { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }
    Behavior on halo { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }
    Behavior on rim { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }
    Behavior on waves { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }
    Behavior on spin { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }
    Behavior on orbit { NumberAnimation { duration: 400 } }
    Behavior on arc { NumberAnimation { duration: 400 } }
    Behavior on dot { NumberAnimation { duration: 600 } }

    // The light inside leans towards the mouse, a little late, like a held breath.
    property real lean: 0
    property real leanY: 0
    Behavior on lean { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
    Behavior on leanY { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
    onGazeXChanged: lean = gazeX
    onGazeYChanged: leanY = gazeY
    readonly property real leanPxX: lean * radius * 0.30
    readonly property real leanPxY: leanY * radius * 0.30

    // Named colours for mixing: mixWith() needs real colours, a plain string like "white" has no channels.
    readonly property color white: "#FFFFFF"
    readonly property color glassDark: "#17130F"
    readonly property color ember: "#E2553F"

    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, Math.max(0, Math.min(1, a))) }
    function mixWith(c, other, t) {
        return Qt.rgba(c.r + (other.r - c.r) * t, c.g + (other.g - c.g) * t, c.b + (other.b - c.b) * t, 1)
    }

    /// A closed ring whose radius rises and falls, giving a wave that runs all the way round.
    function wavePoints(radius, amplitude, lobes, centre) {
        var points = []
        for (var i = 0; i <= 240; i++) {
            var t = i / 240 * 2 * Math.PI
            var r = radius + amplitude * Math.sin(lobes * t)
            points.push(Qt.point(centre + r * Math.cos(t), centre + r * Math.sin(t)))
        }
        return points
    }

    // Slow time: drives the drift of the light inside the glass.
    property real drift: 0
    NumberAnimation on drift { from: 0; to: 2 * Math.PI; duration: 24000; loops: Animation.Infinite; running: core.active }

    // 0..1 breathing, slower when paused and quicker when something is wrong.
    property real breath: 0
    SequentialAnimation on breath {
        running: core.active
        loops: Animation.Infinite
        NumberAnimation { to: 1; duration: core.look === "asleep" ? 5200 : core.look === "concerned" ? 900 : 3200; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: core.look === "asleep" ? 5200 : core.look === "concerned" ? 900 : 3200; easing.type: Easing.InOutSine }
    }
    readonly property real size: 1 + breath * (current.pulse > 0 ? 0.045 : 0.02) + voice * 0.06

    // ---- a half of a tilted, flattened ring -----------------------------------------------------
    // Rings are circles seen at an angle: tilted, squashed, and cut in two along the squashed axis, so
    // the near half can pass in front of the sphere and the far half behind it.
    component RingFrame: Item {
        id: frame
        property real tilt: 0
        property real squash: 0.35
        property bool front: false
        property real diameter: 140
        default property alias content: inner.data
        width: diameter; height: diameter
        anchors.centerIn: parent
        rotation: tilt
        transform: Scale { origin.x: frame.width / 2; origin.y: frame.height / 2; yScale: frame.squash }
        Item {
            y: frame.front ? frame.height / 2 : 0
            width: frame.width; height: frame.height / 2
            clip: true
            Item {
                id: inner
                y: frame.front ? -frame.height / 2 : 0
                width: frame.width; height: frame.height
            }
        }
    }

    readonly property var ringSpecs: [
        { "f": 1.36, "lobes": 6, "tilt": -20, "squash": 0.34, "ms": 26000, "dir":  1 },
        { "f": 1.62, "lobes": 8, "tilt":  26, "squash": 0.38, "ms": 34000, "dir": -1 },
        { "f": 1.90, "lobes": 4, "tilt":  -6, "squash": 0.26, "ms": 44000, "dir":  1 }
    ]

    component WaveRing: RingFrame {
        id: ring
        required property var spec
        readonly property real r: core.radius * spec.f
        readonly property real amp: r * 0.065
        diameter: 2 * (r + amp + 8)
        tilt: spec.tilt
        squash: spec.squash
        scale: 1 + core.voice * 0.10 + (core.look === "warm" ? core.breath * 0.03 : 0)

        Item {
            id: spinner
            anchors.fill: parent
            RotationAnimation on rotation {
                running: core.spin > 0.02 && core.active
                loops: Animation.Infinite
                from: ring.spec.dir > 0 ? 0 : 360
                to: ring.spec.dir > 0 ? 360 : 0
                duration: ring.spec.ms / Math.max(0.2, core.spin)
            }
            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                // a wide, soft bloom under a crisp line: the line is the ring, the bloom is its glow
                ShapePath {
                    strokeColor: core.withAlpha(core.accent, 0.20 * core.waves)
                    strokeWidth: 9
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathPolyline { id: bloom; path: [] }
                }
                ShapePath {
                    strokeColor: core.withAlpha(Qt.lighter(core.accent, 1.25), 0.95 * core.waves)
                    strokeWidth: 1.6
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathPolyline { id: line; path: [] }
                }
            }
            Component.onCompleted: {
                var points = core.wavePoints(ring.r, ring.amp, ring.spec.lobes, ring.diameter / 2)
                bloom.path = points
                line.path = points
            }
        }
    }

    // ---- the halo: light spilling out around the whole thing -------------------------------------
    Shape {
        anchors.centerIn: parent
        width: core.width; height: core.height
        preferredRendererType: Shape.CurveRenderer
        opacity: Math.min(1, core.halo * (0.55 + core.breath * 0.35) + core.voice * 0.5)
        scale: 0.92 + core.breath * 0.06 + core.voice * 0.14
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: core.cx; centerY: core.cy; centerRadius: core.width / 2
                focalX: core.cx; focalY: core.cy
                GradientStop { position: 0.30; color: core.withAlpha(core.accent, 0.50) }
                GradientStop { position: 1.00; color: core.withAlpha(core.accent, 0.0) }
            }
            PathAngleArc { centerX: core.cx; centerY: core.cy; radiusX: core.width / 2; radiusY: core.width / 2; sweepAngle: 360 }
        }
    }

    // ---- far halves of the rings, behind the glass ------------------------------------------------
    Repeater {
        model: core.ringSpecs
        delegate: WaveRing { required property var modelData; spec: modelData; front: false }
    }
    Repeater {  // thinking: motes of light circling behind
        model: 1
        delegate: RingFrame {
            front: false; tilt: -14; squash: 0.42; diameter: 2 * core.radius * 1.34
            opacity: core.orbit
            visible: opacity > 0.01
            Item {
                anchors.fill: parent
                RotationAnimation on rotation { running: core.orbit > 0.02 && core.active; loops: Animation.Infinite; from: 0; to: 360; duration: 1500 }
                Repeater {
                    model: 7
                    delegate: Rectangle {
                        required property int index
                        x: parent.width / 2 + Math.cos(index / 7 * 2 * Math.PI) * (core.radius * 1.34) - width / 2
                        y: parent.height / 2 + Math.sin(index / 7 * 2 * Math.PI) * (core.radius * 1.34) - height / 2
                        width: 3 + (index % 3); height: width; radius: width / 2
                        color: Qt.lighter(core.accent, 1.5)
                        opacity: 0.35 + 0.65 * (index / 6)
                    }
                }
            }
        }
    }

    // ---- the sphere ---------------------------------------------------------------------------------
    Item {
        id: sphere
        anchors.centerIn: parent
        width: core.radius * 2; height: core.radius * 2
        scale: core.size

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            // smoked glass: near-black with a warm cast, a little lighter low down where light gathers
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: sphere.width * 0.46; centerY: sphere.height * 0.40; centerRadius: sphere.width * 0.62
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.0; color: "#2C2216" }
                    GradientStop { position: 0.55; color: "#17130F" }
                    GradientStop { position: 1.0; color: "#0C0A07" }
                }
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius; radiusY: core.radius; sweepAngle: 360 }
            }
            // the light inside, drifting and leaning towards the pointer
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: sphere.width / 2 + core.radius * (0.12 * Math.sin(core.drift)) + core.leanPxX
                    centerY: sphere.height / 2 + core.radius * (0.10 * Math.cos(2 * core.drift)) + core.leanPxY + 6
                    centerRadius: core.radius * 1.05
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.00; color: core.withAlpha(core.mixWith(core.accent, core.white, 0.45), 0.95 * core.glow) }
                    GradientStop { position: 0.30; color: core.withAlpha(core.accent, 0.80 * core.glow) }
                    GradientStop { position: 0.70; color: core.withAlpha(core.mixWith(core.accent, core.glassDark, 0.55), 0.38 * core.glow) }
                    GradientStop { position: 1.00; color: core.withAlpha(core.accent, 0.0) }
                }
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius; radiusY: core.radius; sweepAngle: 360 }
            }
            // a second, slower light turning the other way, which is what makes it look alive
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: sphere.width / 2 + core.radius * 0.38 * Math.cos(core.drift * 3 + 1.2)
                    centerY: sphere.height / 2 + core.radius * 0.30 * Math.sin(core.drift * 3 + 1.2) - 4
                    centerRadius: core.radius * 0.72
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.0; color: core.withAlpha(core.mixWith(core.accent, core.ember, 0.25), 0.34 * core.glow) }
                    GradientStop { position: 1.0; color: core.withAlpha(core.accent, 0.0) }
                }
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius; radiusY: core.radius; sweepAngle: 360 }
            }
            // light caught at the edge of the glass (the Fresnel rim)
            ShapePath {
                strokeWidth: -1
                fillGradient: RadialGradient {
                    centerX: sphere.width / 2; centerY: sphere.height / 2; centerRadius: core.radius
                    focalX: centerX; focalY: centerY
                    GradientStop { position: 0.00; color: core.withAlpha(core.accent, 0.0) }
                    GradientStop { position: 0.74; color: core.withAlpha(core.accent, 0.0) }
                    GradientStop { position: 0.93; color: core.withAlpha(Qt.lighter(core.accent, 1.2), 0.40 * core.rim) }
                    GradientStop { position: 1.00; color: core.withAlpha(Qt.lighter(core.accent, 1.5), 0.85 * core.rim) }
                }
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius; radiusY: core.radius; sweepAngle: 360 }
            }
            // the curved reflection of a window along the upper left, which is what reads as glass
            ShapePath {
                strokeColor: Qt.rgba(1, 0.97, 0.9, 0.50)
                strokeWidth: 2.4
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius * 0.84; radiusY: core.radius * 0.84; startAngle: 196; sweepAngle: 50 }
            }
            ShapePath {
                strokeColor: Qt.rgba(1, 0.97, 0.9, 0.22)
                strokeWidth: 1.4
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius * 0.84; radiusY: core.radius * 0.84; startAngle: 252; sweepAngle: 16 }
            }
            // a hairline at the very edge
            ShapePath {
                strokeColor: core.withAlpha(Qt.lighter(core.accent, 1.5), 0.35 * core.rim)
                strokeWidth: 0.8
                fillColor: "transparent"
                PathAngleArc { centerX: sphere.width / 2; centerY: sphere.height / 2; radiusX: core.radius - 0.4; radiusY: core.radius - 0.4; sweepAngle: 360 }
            }
        }

        // studio highlight, upper left: a soft oval, and a smaller sharp one inside it
        Item {
            x: sphere.width * 0.17; y: sphere.height * 0.13
            width: sphere.width * 0.40; height: sphere.height * 0.40
            rotation: -34
            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeWidth: -1
                    fillGradient: RadialGradient {
                        centerX: sphere.width * 0.20; centerY: sphere.width * 0.20; centerRadius: sphere.width * 0.20
                        focalX: centerX; focalY: centerY
                        GradientStop { position: 0.0; color: Qt.rgba(1, 0.97, 0.9, 0.62) }
                        GradientStop { position: 0.55; color: Qt.rgba(1, 0.97, 0.9, 0.16) }
                        GradientStop { position: 1.0; color: Qt.rgba(1, 0.97, 0.9, 0.0) }
                    }
                    PathAngleArc { centerX: sphere.width * 0.20; centerY: sphere.width * 0.20; radiusX: sphere.width * 0.20; radiusY: sphere.width * 0.20; sweepAngle: 360 }
                }
            }
        }
        Rectangle {  // a small bright glint where the reflection is strongest
            x: sphere.width * 0.30; y: sphere.height * 0.27
            width: 4; height: 2.4; radius: 1.2
            rotation: -34
            color: Qt.rgba(1, 1, 0.96, 0.8)
            opacity: Math.min(1, 0.4 + core.glow * 0.5)
        }
    }

    // ---- near halves of the rings, in front of the glass --------------------------------------------
    Repeater {
        model: core.ringSpecs
        delegate: WaveRing { required property var modelData; spec: modelData; front: true }
    }
    Repeater {
        model: 1
        delegate: RingFrame {
            front: true; tilt: -14; squash: 0.42; diameter: 2 * core.radius * 1.34
            opacity: core.orbit
            visible: opacity > 0.01
            Item {
                anchors.fill: parent
                RotationAnimation on rotation { running: core.orbit > 0.02 && core.active; loops: Animation.Infinite; from: 0; to: 360; duration: 1500 }
                Repeater {
                    model: 7
                    delegate: Rectangle {
                        required property int index
                        x: parent.width / 2 + Math.cos(index / 7 * 2 * Math.PI) * (core.radius * 1.34) - width / 2
                        y: parent.height / 2 + Math.sin(index / 7 * 2 * Math.PI) * (core.radius * 1.34) - height / 2
                        width: 3 + (index % 3); height: width; radius: width / 2
                        color: Qt.lighter(core.accent, 1.5)
                        opacity: 0.35 + 0.65 * (index / 6)
                    }
                }
            }
        }
    }

    // working: one clean arc keeps pace with the job
    Shape {
        anchors.centerIn: parent
        width: core.radius * 2.7; height: width
        preferredRendererType: Shape.CurveRenderer
        opacity: core.arc
        visible: opacity > 0.01
        RotationAnimation on rotation { running: core.arc > 0.02 && core.active; loops: Animation.Infinite; from: 0; to: 360; duration: 1700 }
        ShapePath {
            strokeColor: core.withAlpha(Qt.lighter(core.accent, 1.3), 0.95)
            strokeWidth: 2
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: core.radius * 1.35; centerY: core.radius * 1.35; radiusX: core.radius * 1.27; radiusY: core.radius * 1.27; startAngle: -90; sweepAngle: 105 }
        }
    }

    // paused: the light is nearly out, the rings are still, and one dot says it is still here
    Rectangle {
        x: core.cx - width / 2; y: core.cy + core.radius * 1.55
        width: 5; height: 5; radius: 2.5
        color: core.accent
        opacity: core.dot * 0.85
        visible: opacity > 0.01
    }
}
