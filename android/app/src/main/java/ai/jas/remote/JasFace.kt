package ai.jas.remote

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * JAS's face, drawn the same way it is drawn on the laptop: a sphere that becomes a different
 * body in the sky for each state, two round eyes, and two thin curved brows.
 *
 * Everything is drawn relative to the radius, so the one view works as a small floating bubble
 * and as a large face on the app's own screen.
 */
class JasFace @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    // --- what the laptop told us --------------------------------------------

    private var accent = Color.parseColor("#FFC46B")
    private var body = "sun"
    private var mood = "calm"

    fun show(snapshot: Snapshot) {
        accent = try { Color.parseColor(snapshot.colour) } catch (e: IllegalArgumentException) { accent }
        body = snapshot.body
        mood = moodFor(snapshot.state)
        invalidate()
    }

    /** How loudly you are speaking, 0..1 — the eyes widen with your voice while listening. */
    var level: Float = 0f
        set(value) { field = value.coerceIn(0f, 1f) }

    /** Which way the phone is tilted, each -1..1. The eyes look that way. */
    fun tilt(x: Float, y: Float) {
        tiltX += (x.coerceIn(-1f, 1f) - tiltX) * 0.2f
        tiltY += (y.coerceIn(-1f, 1f) - tiltY) * 0.2f
    }

    private var tiltX = 0f
    private var tiltY = 0f

    // --- the clock -----------------------------------------------------------

    private var startedAt = System.nanoTime()
    private val seconds: Float get() = (System.nanoTime() - startedAt) / 1_000_000_000f

    private var nextBlinkAt = 2.5f
    private var blinkStartedAt = -1f

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val path = Path()
    private val oval = RectF()

    private var running = false

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        running = true
        postInvalidateOnAnimation()
    }

    override fun onDetachedFromWindow() {
        running = false
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val t = seconds
        val w = width.toFloat()
        val h = height.toFloat()
        val r = min(w, h) * 0.37f
        val cx = w / 2f
        val cy = h / 2f

        val asleep = mood == "asleep"
        val breathe = 1f + 0.018f * sin(t * (if (asleep) 1.1f else 1.9f))
        val radius = r * breathe

        halo(canvas, cx, cy, radius, t, asleep)
        if (body == "saturn") rings(canvas, cx, cy, radius)
        if (body == "sun") corona(canvas, cx, cy, radius, t) else sphere(canvas, cx, cy, radius)
        markings(canvas, cx, cy, radius, t)
        if (asleep) zzz(canvas, cx, cy, radius, t) else brows(canvas, cx, cy, radius)
        eyes(canvas, cx, cy, radius, t, asleep)

        if (running) postInvalidateOnAnimation()
    }

    // --- the body ------------------------------------------------------------

    private fun halo(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float, asleep: Boolean) {
        val pulse = 1f + 0.06f * sin(t * 1.6f) + level * 0.14f
        val reach = r * (if (asleep) 1.22f else 1.38f) * pulse
        fill.shader = RadialGradient(
            cx, cy, reach,
            intArrayOf(alpha(accent, if (asleep) 0.16f else 0.34f), alpha(accent, 0f)),
            floatArrayOf(0.42f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx, cy, reach, fill)
        fill.shader = null
    }

    private fun sphere(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        // Lit from the upper left, the way the reference sphere is.
        fill.shader = RadialGradient(
            cx - r * 0.28f, cy - r * 0.40f, r * 1.45f,
            intArrayOf(lighten(accent, 0.42f), accent, darken(accent, 0.52f)),
            floatArrayOf(0f, 0.55f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx, cy, r, fill)
        fill.shader = null

        line.color = alpha(lighten(accent, 0.5f), 0.55f)
        line.strokeWidth = max(1f, r * 0.02f)
        canvas.drawCircle(cx, cy, r, line)
    }

    /** The Sun has no outline — it is light, so it gets curvy waves instead of a rim. */
    private fun corona(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        for (ring in 0..1) {
            val base = r * (1.06f + ring * 0.10f)
            val wobble = r * (0.045f + ring * 0.02f)
            val speed = if (ring == 0) 1.0f else -0.7f
            path.reset()
            var a = 0f
            while (a <= 360f) {
                val rad = Math.toRadians(a.toDouble()).toFloat()
                val d = base + wobble * sin(rad * 7f + t * speed * 1.8f)
                val x = cx + d * cos(rad)
                val y = cy + d * sin(rad)
                if (a == 0f) path.moveTo(x, y) else path.lineTo(x, y)
                a += 4f
            }
            path.close()
            line.color = alpha(lighten(accent, 0.35f), if (ring == 0) 0.55f else 0.3f)
            line.strokeWidth = max(1f, r * (0.028f - ring * 0.008f))
            canvas.drawPath(path, line)
        }
        fill.shader = RadialGradient(
            cx - r * 0.24f, cy - r * 0.34f, r * 1.4f,
            intArrayOf(lighten(accent, 0.55f), accent, darken(accent, 0.30f)),
            floatArrayOf(0f, 0.6f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx, cy, r, fill)
        fill.shader = null
    }

    private fun rings(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        canvas.save()
        canvas.rotate(-18f, cx, cy)
        line.color = alpha(lighten(accent, 0.4f), 0.75f)
        line.strokeWidth = max(1f, r * 0.045f)
        oval.set(cx - r * 1.38f, cy - r * 0.38f, cx + r * 1.38f, cy + r * 0.38f)
        canvas.drawOval(oval, line)
        line.strokeWidth = max(1f, r * 0.022f)
        line.color = alpha(lighten(accent, 0.25f), 0.5f)
        oval.set(cx - r * 1.21f, cy - r * 0.33f, cx + r * 1.21f, cy + r * 0.33f)
        canvas.drawOval(oval, line)
        canvas.restore()
    }

    /**
     * The markings that make each body recognisable. They are clipped to the sphere with real
     * chord maths rather than a rectangular clip, so a band never runs off the edge.
     */
    private fun markings(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        if (body.isEmpty() || body == "sun") return
        canvas.save()
        path.reset()
        path.addCircle(cx, cy, r, Path.Direction.CW)
        canvas.clipPath(path)
        fill.style = Paint.Style.FILL
        when (body) {
            "moon", "mercury" -> craters(canvas, cx, cy, r)
            "jupiter" -> bands(canvas, cx, cy, r, 5, 0.30f, storm = true)
            "saturn" -> bands(canvas, cx, cy, r, 4, 0.18f, storm = false)
            "neptune", "uranus" -> bands(canvas, cx, cy, r, 2, 0.14f, storm = false)
            "earth" -> seas(canvas, cx, cy, r, t)
            "venus" -> bands(canvas, cx, cy, r, 3, 0.12f, storm = false)
            "mars" -> mars(canvas, cx, cy, r)
        }
        canvas.restore()
    }

    private fun craters(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        // x, y and size as fractions of the radius, chosen to sit clear of the eyes.
        val spots = floatArrayOf(
            -0.62f, -0.48f, 0.17f,
            0.55f, -0.58f, 0.12f,
            -0.30f, 0.66f, 0.15f,
            0.44f, 0.60f, 0.20f,
            0.74f, 0.16f, 0.10f,
            -0.78f, 0.20f, 0.11f,
        )
        var i = 0
        while (i < spots.size) {
            val x = cx + spots[i] * r
            val y = cy + spots[i + 1] * r
            val size = spots[i + 2] * r
            fill.color = alpha(darken(accent, 0.45f), 0.55f)
            canvas.drawCircle(x, y, size, fill)
            fill.color = alpha(lighten(accent, 0.35f), 0.35f)
            canvas.drawCircle(x - size * 0.18f, y - size * 0.22f, size * 0.62f, fill)
            i += 3
        }
    }

    private fun bands(canvas: Canvas, cx: Float, cy: Float, r: Float, count: Int,
                      strength: Float, storm: Boolean) {
        for (i in 0 until count) {
            // Spread the bands over the sphere but leave the middle, where the eyes are, alone.
            val at = -0.82f + 1.64f * (i + 0.5f) / count
            if (abs(at) < 0.30f) continue
            val thickness = r * 0.13f
            val y = cy + at * r
            val half = chord(abs(at) * r + thickness * 0.5f, r)
            fill.color = alpha(if (i % 2 == 0) darken(accent, 0.38f) else lighten(accent, 0.30f), strength)
            oval.set(cx - half, y - thickness / 2f, cx + half, y + thickness / 2f)
            canvas.drawRoundRect(oval, thickness, thickness, fill)
        }
        if (storm) {
            fill.color = alpha(Color.parseColor("#C8603A"), 0.55f)
            oval.set(cx + r * 0.20f, cy + r * 0.44f, cx + r * 0.62f, cy + r * 0.64f)
            canvas.drawOval(oval, fill)
        }
    }

    private fun seas(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        val drift = sin(t * 0.25f) * r * 0.05f
        fill.color = alpha(Color.parseColor("#2E8B6B"), 0.55f)
        oval.set(cx - r * 0.78f + drift, cy + r * 0.32f, cx - r * 0.10f + drift, cy + r * 0.74f)
        canvas.drawOval(oval, fill)
        oval.set(cx + r * 0.22f + drift, cy - r * 0.74f, cx + r * 0.76f + drift, cy - r * 0.34f)
        canvas.drawOval(oval, fill)
        fill.color = alpha(Color.WHITE, 0.32f)
        oval.set(cx - r * 0.55f, cy - r * 0.95f, cx + r * 0.10f, cy - r * 0.62f)
        canvas.drawOval(oval, fill)
    }

    private fun mars(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        fill.color = alpha(Color.WHITE, 0.40f)
        val capY = cy - r * 0.86f
        val half = chord(r * 0.86f, r)
        oval.set(cx - half, capY - r * 0.16f, cx + half, capY + r * 0.16f)
        canvas.drawOval(oval, fill)
        fill.color = alpha(darken(accent, 0.45f), 0.45f)
        oval.set(cx - r * 0.70f, cy + r * 0.34f, cx + r * 0.06f, cy + r * 0.78f)
        canvas.drawOval(oval, fill)
    }

    /** Half the width of the sphere at a given distance from its middle. */
    private fun chord(fromCentre: Float, r: Float): Float {
        val d = min(abs(fromCentre), r)
        return sqrt(r * r - d * d)
    }

    // --- the face ------------------------------------------------------------

    private fun brows(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        val m = expression()
        line.color = INK
        line.strokeWidth = max(1.5f, r * 0.055f)
        val span = r * 0.21f
        val y = cy - r * 0.50f + m.brow * r
        for (side in intArrayOf(-1, 1)) {
            val mid = cx + side * r * 0.37f
            val lift = m.angry * r * 0.10f * side
            path.reset()
            path.moveTo(mid - span, y + lift + m.arch * r * 0.04f)
            path.quadTo(mid, y - m.arch * r * 0.11f, mid + span, y - lift + m.arch * r * 0.04f)
            canvas.drawPath(path, line)
        }
    }

    private fun eyes(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float, asleep: Boolean) {
        val m = expression()
        val eyeR = r * 0.27f * (1f + level * 0.10f) * m.open
        val eyeY = cy + r * 0.05f
        val shut = blink(t, asleep)

        for (side in intArrayOf(-1, 1)) {
            val ex = cx + side * r * 0.37f
            if (shut > 0.92f) {
                line.color = INK
                line.strokeWidth = max(1.5f, r * 0.06f)
                path.reset()
                path.moveTo(ex - eyeR, eyeY)
                path.quadTo(ex, eyeY + eyeR * 0.45f, ex + eyeR, eyeY)
                canvas.drawPath(path, line)
                continue
            }
            val lid = 1f - shut
            fill.color = Color.WHITE
            oval.set(ex - eyeR, eyeY - eyeR * lid, ex + eyeR, eyeY + eyeR * lid)
            canvas.drawOval(oval, fill)

            // The pupils follow the tilt of the phone, and wander a little when thinking.
            val wanderX = if (m.wander) sin(t * 0.8f) * 0.28f else 0f
            val wanderY = if (m.wander) cos(t * 0.6f) * 0.16f else 0f
            val gx = (tiltX + wanderX).coerceIn(-1f, 1f) * eyeR * 0.42f
            val gy = (tiltY + wanderY + m.gazeY).coerceIn(-1f, 1f) * eyeR * 0.38f * lid
            val pupil = eyeR * 0.50f
            fill.color = INK
            canvas.drawCircle(ex + gx, eyeY + gy, pupil * min(1f, lid * 1.4f), fill)
            fill.color = alpha(Color.WHITE, 0.95f)
            canvas.drawCircle(ex + gx - pupil * 0.34f, eyeY + gy - pupil * 0.40f,
                pupil * 0.30f * min(1f, lid * 1.4f), fill)
        }
    }

    /** 0 = wide open, 1 = shut. Schedules the next blink as it finishes one. */
    private fun blink(t: Float, asleep: Boolean): Float {
        if (asleep) return 1f
        if (blinkStartedAt < 0f && t >= nextBlinkAt) blinkStartedAt = t
        if (blinkStartedAt < 0f) return 0f
        val into = t - blinkStartedAt
        val length = 0.16f
        if (into >= length) {
            blinkStartedAt = -1f
            nextBlinkAt = t + 2.4f + (abs(sin(t * 13.7f)) * 3.6f)
            return 0f
        }
        val half = length / 2f
        return if (into < half) into / half else (length - into) / half
    }

    private class Expression(
        val open: Float, val brow: Float, val arch: Float,
        val angry: Float, val gazeY: Float, val wander: Boolean,
    )

    private fun expression(): Expression = when (mood) {
        "waking" -> Expression(0.72f, 0.04f, 0.5f, 0f, 0.15f, false)
        "alert" -> Expression(1.12f, -0.05f, 1.2f, 0f, -0.10f, false)
        "listening" -> Expression(1.06f, -0.03f, 1.0f, 0f, 0f, false)
        "thinking" -> Expression(0.92f, 0.01f, 0.7f, 0.25f, -0.25f, true)
        "focused" -> Expression(0.88f, 0.05f, 0.3f, 0.55f, 0.05f, false)
        "warm" -> Expression(0.96f, -0.02f, 1.1f, 0f, 0.08f, false)
        "concerned" -> Expression(1.0f, 0.03f, 0.2f, -0.75f, 0.10f, false)
        "asleep" -> Expression(0.0f, 0.06f, 0f, 0f, 0f, false)
        else -> Expression(1.0f, 0f, 0.9f, 0f, 0f, false)
    }

    /** The bright z's that drift up while JAS is resting. */
    private fun zzz(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        line.color = alpha(Color.parseColor("#9FE3E8"), 1f)
        for (i in 0..2) {
            val phase = ((t * 0.42f) + i * 0.333f) % 1f
            val size = r * (0.16f + 0.14f * phase)
            val x = cx + r * (0.52f + 0.34f * phase) + sin(phase * 6f) * r * 0.05f
            val y = cy - r * (0.42f + 1.05f * phase)
            val fade = if (phase < 0.15f) phase / 0.15f else (1f - phase) / 0.85f
            line.color = alpha(Color.parseColor("#BFF3F7"), fade.coerceIn(0f, 1f))
            line.strokeWidth = max(1.2f, size * 0.17f)
            path.reset()
            path.moveTo(x - size / 2f, y - size / 2f)
            path.lineTo(x + size / 2f, y - size / 2f)
            path.lineTo(x - size / 2f, y + size / 2f)
            path.lineTo(x + size / 2f, y + size / 2f)
            canvas.drawPath(path, line)
        }
    }

    private companion object {
        val INK = Color.parseColor("#12151E")

        fun moodFor(state: String) = when (state) {
            "starting" -> "waking"
            "wake_detected" -> "alert"
            "listening" -> "listening"
            "transcribing", "thinking", "planning" -> "thinking"
            "executing", "observing" -> "focused"
            "responding" -> "warm"
            "error", "offline" -> "concerned"
            "sleeping", "resting" -> "asleep"
            else -> "calm"
        }

        fun alpha(colour: Int, a: Float) =
            Color.argb((a.coerceIn(0f, 1f) * 255).toInt(), Color.red(colour), Color.green(colour), Color.blue(colour))

        fun lighten(colour: Int, by: Float) = Color.rgb(
            Color.red(colour) + ((255 - Color.red(colour)) * by).toInt(),
            Color.green(colour) + ((255 - Color.green(colour)) * by).toInt(),
            Color.blue(colour) + ((255 - Color.blue(colour)) * by).toInt(),
        )

        fun darken(colour: Int, by: Float) = Color.rgb(
            (Color.red(colour) * (1f - by)).toInt(),
            (Color.green(colour) * (1f - by)).toInt(),
            (Color.blue(colour) * (1f - by)).toInt(),
        )
    }
}
