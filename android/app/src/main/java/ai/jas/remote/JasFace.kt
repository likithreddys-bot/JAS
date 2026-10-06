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
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * VEM's core, drawn the same way as on the laptop and the website: a sphere of smoked glass with
 * light drifting inside it, ringed by waves of light that revolve around it. There is no face; the
 * state is read from the colour, the brightness and how the rings move.
 *
 * (The class keeps its old name, JasFace, because the layout and the bubble service refer to it.)
 *
 * Everything is drawn relative to the radius, so the one view works as a small floating bubble
 * and as a large orb on the app's own screen.
 */
class JasFace @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    // --- what the laptop told us --------------------------------------------

    private var accent = Color.parseColor("#E8BE76")
    private var mood = "calm"

    fun show(snapshot: Snapshot) {
        accent = try { Color.parseColor(snapshot.colour) } catch (e: IllegalArgumentException) { accent }
        mood = moodFor(snapshot.state)
        invalidate()
    }

    /** How loudly you are speaking, 0..1 — the orb swells and its rings ripple with your voice. */
    var level: Float = 0f
        set(value) { field = value.coerceIn(0f, 1f) }

    /** Which way the phone is tilted, each -1..1. The light inside the glass leans that way. */
    fun tilt(x: Float, y: Float) {
        tiltX += (x.coerceIn(-1f, 1f) - tiltX) * 0.2f
        tiltY += (y.coerceIn(-1f, 1f) - tiltY) * 0.2f
    }

    private var tiltX = 0f
    private var tiltY = 0f

    // --- the clock -----------------------------------------------------------

    private var startedAt = System.nanoTime()
    private var lastFrame = startedAt
    private val seconds: Float get() = (System.nanoTime() - startedAt) / 1_000_000_000f

    // Where each number is heading (from the mood) and where it is now. Each glides to its target,
    // so a change of state is a change of light and not a cut.
    private var glow = 1f
    private var halo = 0.6f
    private var rim = 0.9f
    private var waves = 0.75f
    private var spin = 1f
    private var orbit = 0f
    private var arc = 0f
    private var dot = 0f
    private val phase = FloatArray(RINGS.size)   // how far each ring's waves have travelled

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
        lastFrame = System.nanoTime()
        postInvalidateOnAnimation()
    }

    override fun onDetachedFromWindow() {
        running = false
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val now = System.nanoTime()
        val dt = ((now - lastFrame) / 1_000_000_000f).coerceIn(0f, 0.1f)
        lastFrame = now
        val t = seconds
        val look = lookFor(mood)
        val k = 1f - exp(-dt * 5f)
        glow += (look.glow - glow) * k
        halo += (look.halo - halo) * k
        rim += (look.rim - rim) * k
        waves += (look.waves - waves) * k
        spin += (look.spin - spin) * k
        orbit += (look.orbit - orbit) * k
        arc += (look.arc - arc) * k
        dot += (look.dot - dot) * k
        for (i in phase.indices) {
            val ring = RINGS[i]
            // one full turn of the ring takes `seconds`; the waves travel `lobes` crests per turn
            phase[i] += ring.dir * dt * TAU * ring.lobes / ring.seconds * spin
        }

        val w = width.toFloat()
        val h = height.toFloat()
        val r = min(w, h) * 0.215f
        val cx = w / 2f
        val cy = h / 2f
        val asleep = mood == "asleep"
        val breathe = 0.5f + 0.5f * sin(t * (if (asleep) 1.2f else 2.0f))
        val radius = r * (1f + breathe * (if (look.pulse) 0.045f else 0.02f) + level * 0.06f)

        halo(canvas, cx, cy, radius, breathe)
        waveRings(canvas, cx, cy, radius, front = false)
        motes(canvas, cx, cy, radius, t, front = false)
        sphere(canvas, cx, cy, radius, t)
        waveRings(canvas, cx, cy, radius, front = true)
        motes(canvas, cx, cy, radius, t, front = true)
        workingArc(canvas, cx, cy, radius, t)
        pausedDot(canvas, cx, cy, radius)

        // A paused orb hardly changes, so it does not need sixty frames a second.
        if (running) {
            if (asleep) postInvalidateDelayed(50) else postInvalidateOnAnimation()
        }
    }

    // --- the light around it -------------------------------------------------

    private fun halo(canvas: Canvas, cx: Float, cy: Float, r: Float, breathe: Float) {
        val reach = r * 2.35f * (0.92f + breathe * 0.06f + level * 0.14f)
        val a = min(1f, halo * (0.55f + breathe * 0.35f) + level * 0.5f) * 0.5f
        fill.shader = RadialGradient(
            cx, cy, reach,
            intArrayOf(alpha(accent, a), alpha(accent, 0f)),
            floatArrayOf(0.30f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx, cy, reach, fill)
        fill.shader = null
    }

    // --- the rings -----------------------------------------------------------

    /**
     * Three rings of light, each a circle seen at an angle: tilted, flattened, with a wave running
     * round it. The near half passes in front of the glass and the far half behind it.
     */
    private fun waveRings(canvas: Canvas, cx: Float, cy: Float, r: Float, front: Boolean) {
        val from = if (front) 0 else STEPS / 2
        val to = if (front) STEPS / 2 else STEPS
        for (i in RINGS.indices) {
            val ring = RINGS[i]
            val base = r * ring.factor * (1f + level * 0.10f)
            val amp = base * 0.065f
            canvas.save()
            canvas.translate(cx, cy)
            canvas.rotate(ring.tilt)
            path.reset()
            for (k in from..to) {
                val a = k * TAU / STEPS
                val rad = base + amp * sin(ring.lobes * a + phase[i])
                val x = rad * cos(a)
                val y = rad * sin(a) * ring.squash
                if (k == from) path.moveTo(x, y) else path.lineTo(x, y)
            }
            // a wide, soft bloom under a crisp line: the line is the ring, the bloom is its glow
            line.color = alpha(accent, 0.20f * waves)
            line.strokeWidth = max(2f, r * 0.19f)
            canvas.drawPath(path, line)
            line.color = alpha(lighten(accent, 0.25f), 0.95f * waves)
            line.strokeWidth = max(1f, r * 0.038f)
            canvas.drawPath(path, line)
            canvas.restore()
        }
    }

    /** Thinking: a handful of motes of light circling the glass. */
    private fun motes(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float, front: Boolean) {
        if (orbit < 0.02f) return
        canvas.save()
        canvas.translate(cx, cy)
        canvas.rotate(-14f)
        val turn = t * TAU / 1.5f
        for (i in 0 until MOTES) {
            val a = turn + i * TAU / MOTES
            val sinA = sin(a)
            if ((sinA > 0f) != front) continue
            fill.color = alpha(lighten(accent, 0.5f), orbit * (0.35f + 0.65f * i / (MOTES - 1)))
            canvas.drawCircle(r * 1.34f * cos(a), r * 1.34f * sinA * 0.42f, r * (0.05f + 0.012f * (i % 3)), fill)
        }
        canvas.restore()
    }

    /** Working: one clean arc keeps pace with the job. */
    private fun workingArc(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        if (arc < 0.02f) return
        val reach = r * 1.27f
        oval.set(cx - reach, cy - reach, cx + reach, cy + reach)
        line.color = alpha(lighten(accent, 0.3f), 0.95f * arc)
        line.strokeWidth = max(1.5f, r * 0.045f)
        canvas.drawArc(oval, -90f + t * 211f, 105f, false, line)
    }

    /** Paused: the light is nearly out, the rings are still, and one dot says it is still here. */
    private fun pausedDot(canvas: Canvas, cx: Float, cy: Float, r: Float) {
        if (dot < 0.02f) return
        fill.color = alpha(accent, 0.85f * dot)
        canvas.drawCircle(cx, cy + r * 1.55f, max(2f, r * 0.05f), fill)
    }

    // --- the glass -----------------------------------------------------------

    private fun sphere(canvas: Canvas, cx: Float, cy: Float, r: Float, t: Float) {
        val drift = t * TAU / 24f
        val leanX = tiltX * r * 0.30f
        val leanY = tiltY * r * 0.30f

        // smoked glass: near-black with a warm cast, a little lighter low down where light gathers
        radial(canvas, cx, cy, r, cx - r * 0.08f, cy - r * 0.20f, r * 1.25f,
            intArrayOf(0xFF2C2216.toInt(), 0xFF17130F.toInt(), 0xFF0C0A07.toInt()), floatArrayOf(0f, 0.55f, 1f))

        // the light inside, drifting, and leaning the way the phone is tilted
        radial(canvas, cx, cy, r,
            cx + r * 0.12f * sin(drift) + leanX, cy + r * 0.10f * cos(2f * drift) + leanY + r * 0.14f, r * 1.05f,
            intArrayOf(
                alpha(mix(accent, Color.WHITE, 0.45f), 0.95f * glow),
                alpha(accent, 0.80f * glow),
                alpha(mix(accent, GLASS, 0.55f), 0.38f * glow),
                alpha(accent, 0f),
            ),
            floatArrayOf(0f, 0.30f, 0.70f, 1f))

        // a second, slower light turning the other way, which is what makes it look alive
        radial(canvas, cx, cy, r,
            cx + r * 0.38f * cos(drift * 3f + 1.2f), cy + r * 0.30f * sin(drift * 3f + 1.2f) - r * 0.09f, r * 0.72f,
            intArrayOf(alpha(mix(accent, EMBER, 0.25f), 0.34f * glow), alpha(accent, 0f)),
            floatArrayOf(0f, 1f))

        // light caught at the edge of the glass
        radial(canvas, cx, cy, r, cx, cy, r,
            intArrayOf(alpha(accent, 0f), alpha(accent, 0f),
                alpha(lighten(accent, 0.2f), 0.40f * rim), alpha(lighten(accent, 0.5f), 0.85f * rim)),
            floatArrayOf(0f, 0.74f, 0.93f, 1f))

        // the curved reflection of a window along the upper left, which is what reads as glass
        oval.set(cx - r * 0.84f, cy - r * 0.84f, cx + r * 0.84f, cy + r * 0.84f)
        line.color = Color.argb(128, 255, 248, 230)
        line.strokeWidth = max(1.5f, r * 0.055f)
        canvas.drawArc(oval, 196f, 50f, false, line)
        line.color = Color.argb(56, 255, 248, 230)
        line.strokeWidth = max(1f, r * 0.032f)
        canvas.drawArc(oval, 252f, 16f, false, line)

        // a soft bloom of that reflection, and a small bright glint where it is strongest
        fill.shader = RadialGradient(
            cx - r * 0.42f, cy - r * 0.50f, r * 0.28f,
            intArrayOf(Color.argb(110, 255, 248, 230), Color.argb(0, 255, 248, 230)),
            floatArrayOf(0f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx - r * 0.42f, cy - r * 0.50f, r * 0.28f, fill)
        fill.shader = null
        fill.color = Color.argb((min(1f, 0.4f + glow * 0.5f) * 204).toInt(), 255, 255, 245)
        canvas.save()
        canvas.rotate(-34f, cx - r * 0.34f, cy - r * 0.44f)
        oval.set(cx - r * 0.34f - r * 0.05f, cy - r * 0.44f - r * 0.03f, cx - r * 0.34f + r * 0.05f, cy - r * 0.44f + r * 0.03f)
        canvas.drawRoundRect(oval, r * 0.03f, r * 0.03f, fill)
        canvas.restore()

        // a hairline at the very edge
        line.color = alpha(lighten(accent, 0.5f), 0.35f * rim)
        line.strokeWidth = max(1f, r * 0.018f)
        canvas.drawCircle(cx, cy, r - line.strokeWidth / 2f, line)
    }

    /** One gradient, painted only inside the sphere's circle, so a light can move without leaving the glass. */
    private fun radial(canvas: Canvas, cx: Float, cy: Float, r: Float, gx: Float, gy: Float, reach: Float,
                       colours: IntArray, stops: FloatArray) {
        fill.shader = RadialGradient(gx, gy, reach, colours, stops, Shader.TileMode.CLAMP)
        canvas.drawCircle(cx, cy, r, fill)
        fill.shader = null
    }

    // --- the looks -----------------------------------------------------------

    /**
     * How each mood looks: glow = light inside the glass, halo = glow around it, rim = light caught
     * at the edge, waves = ring brightness, spin = how fast the rings revolve. The same numbers as
     * ui/qml/GlassOrb.qml on the laptop.
     */
    private class Look(
        val glow: Float, val halo: Float, val rim: Float, val waves: Float, val spin: Float,
        val orbit: Float = 0f, val arc: Float = 0f, val dot: Float = 0f, val pulse: Boolean = false,
    )

    private fun lookFor(mood: String): Look = when (mood) {
        "waking" -> Look(0.60f, 0.35f, 0.70f, 0.40f, 0.6f)
        "alert" -> Look(1.25f, 1.00f, 1.20f, 1.00f, 2.2f)
        "listening" -> Look(1.30f, 1.10f, 1.20f, 1.00f, 2.4f)
        "thinking" -> Look(0.60f, 0.30f, 0.70f, 0.45f, 1.4f, orbit = 1f)
        "focused" -> Look(0.90f, 0.60f, 1.00f, 0.55f, 1.7f, arc = 1f)
        "warm" -> Look(1.10f, 0.75f, 1.00f, 1.00f, 1.6f, pulse = true)
        "concerned" -> Look(1.00f, 0.80f, 1.20f, 0.65f, 2.6f)
        "asleep" -> Look(0.30f, 0.12f, 0.45f, 0.15f, 0f, dot = 1f)
        else -> Look(1.00f, 0.60f, 0.90f, 0.75f, 1.0f)
    }

    private class Ring(
        val factor: Float, val lobes: Int, val tilt: Float, val squash: Float, val seconds: Float, val dir: Int,
    )

    private companion object {
        const val TAU = 6.2831855f
        const val STEPS = 120
        const val MOTES = 7
        val GLASS = Color.parseColor("#17130F")
        val EMBER = Color.parseColor("#E2553F")

        // radius as a multiple of the sphere's, waves round the ring, tilt and flattening, seconds per turn
        val RINGS = listOf(
            Ring(1.36f, 6, -20f, 0.34f, 26f, 1),
            Ring(1.62f, 8, 26f, 0.38f, 34f, -1),
            Ring(1.90f, 4, -6f, 0.26f, 44f, 1),
        )

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

        fun lighten(colour: Int, by: Float) = mix(colour, Color.WHITE, by)

        fun mix(from: Int, to: Int, by: Float) = Color.rgb(
            Color.red(from) + ((Color.red(to) - Color.red(from)) * by).toInt(),
            Color.green(from) + ((Color.green(to) - Color.green(from)) * by).toInt(),
            Color.blue(from) + ((Color.blue(to) - Color.blue(from)) * by).toInt(),
        )
    }
}
