import QtQuick
import QtQuick.Window

// Shown around the whole screen while JARVIS is looking at it, so it is never watching invisibly.
// The window is click-through (see ui/screenglow.py); nothing here ever takes input.
Window {
    id: glow

    property color accent: "#4DD0C8"
    property bool watching: false

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
           | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    visible: false

    readonly property int band: 78  // how far the glow reaches in from the edge

    function withAlpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // Fades in when JARVIS starts looking and out when it stops, so it never blinks on and off.
    property real strength: 0
    Behavior on strength { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
    onWatchingChanged: strength = watching ? 1 : 0

    // A slow travel along the edges, so it reads as alive rather than a static border.
    property real sweep: 0
    NumberAnimation on sweep {
        running: glow.visible
        loops: Animation.Infinite
        from: 0; to: 1
        duration: 2600
    }

    Item {
        anchors.fill: parent
        opacity: glow.strength * (0.75 + 0.25 * Math.sin(glow.sweep * 2 * Math.PI))

        // One gradient per edge: strong at the very edge, gone by `band` pixels in.
        Rectangle {
            width: parent.width; height: glow.band
            anchors.top: parent.top
            gradient: Gradient {
                GradientStop { position: 0.0; color: glow.withAlpha(glow.accent, 0.42) }
                GradientStop { position: 0.35; color: glow.withAlpha(glow.accent, 0.10) }
                GradientStop { position: 1.0; color: glow.withAlpha(glow.accent, 0.0) }
            }
        }
        Rectangle {
            width: parent.width; height: glow.band
            anchors.bottom: parent.bottom
            gradient: Gradient {
                GradientStop { position: 0.0; color: glow.withAlpha(glow.accent, 0.0) }
                GradientStop { position: 0.65; color: glow.withAlpha(glow.accent, 0.10) }
                GradientStop { position: 1.0; color: glow.withAlpha(glow.accent, 0.42) }
            }
        }
        Rectangle {
            width: glow.band; height: parent.height
            anchors.left: parent.left
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: glow.withAlpha(glow.accent, 0.42) }
                GradientStop { position: 0.35; color: glow.withAlpha(glow.accent, 0.10) }
                GradientStop { position: 1.0; color: glow.withAlpha(glow.accent, 0.0) }
            }
        }
        Rectangle {
            width: glow.band; height: parent.height
            anchors.right: parent.right
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: glow.withAlpha(glow.accent, 0.0) }
                GradientStop { position: 0.65; color: glow.withAlpha(glow.accent, 0.10) }
                GradientStop { position: 1.0; color: glow.withAlpha(glow.accent, 0.42) }
            }
        }

        // A crisp hairline right at the edge, which is what makes it read as a deliberate border.
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            border.width: 2
            border.color: glow.withAlpha(Qt.lighter(glow.accent, 1.25), 0.85)
        }
    }
}
