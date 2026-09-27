package ai.jas.remote

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.view.View
import kotlin.math.max
import kotlin.math.sin

/**
 * Edge lighting: the rim of the phone's screen glows in JAS's colour while it is listening or
 * working, the way a notification light would. It never takes touches, so whatever app you are
 * using carries on as normal underneath.
 */
class EdgeGlow(context: Context) : View(context) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var accent = Color.parseColor("#FFC46B")
    private var strength = 0f      // where the glow is now
    private var wanted = 0f        // where it is heading
    private var startedAt = System.nanoTime()

    fun show(snapshot: Snapshot) {
        accent = try { Color.parseColor(snapshot.colour) } catch (e: IllegalArgumentException) { accent }
        wanted = when (snapshot.state) {
            "listening", "wake_detected" -> 1f
            "transcribing", "thinking", "planning", "executing", "observing", "responding" -> 0.72f
            "error" -> 0.85f
            else -> 0f
        }
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        strength += (wanted - strength) * 0.08f
        if (strength < 0.01f && wanted == 0f) {
            strength = 0f
            return  // fully dark: draw nothing at all and stop asking for frames
        }
        val t = (System.nanoTime() - startedAt) / 1_000_000_000f
        val breath = 0.78f + 0.22f * sin(t * 2.2f)
        val a = strength * breath
        val w = width.toFloat()
        val h = height.toFloat()
        val tall = h * 0.16f
        val wide = w * 0.18f

        band(canvas, 0f, 0f, w, tall, 0f, tall, a * 0.80f)
        band(canvas, 0f, h - tall, w, h, h, h - tall, a * 0.80f)
        band(canvas, 0f, 0f, wide, h, 0f, 0f, a * 0.65f, vertical = false)
        band(canvas, w - wide, 0f, w, h, w, 0f, a * 0.65f, vertical = false)

        postInvalidateOnAnimation()
    }

    private fun band(canvas: Canvas, left: Float, top: Float, right: Float, bottom: Float,
                     fromCoord: Float, toCoord: Float, a: Float, vertical: Boolean = true) {
        paint.shader = if (vertical)
            LinearGradient(0f, fromCoord, 0f, toCoord,
                colour(a), colour(0f), Shader.TileMode.CLAMP)
        else
            LinearGradient(fromCoord, 0f, toCoord, 0f,
                colour(a), colour(0f), Shader.TileMode.CLAMP)
        canvas.drawRect(left, top, right, bottom, paint)
        paint.shader = null
    }

    private fun colour(a: Float) = Color.argb(
        (max(0f, a).coerceAtMost(1f) * 255).toInt(),
        Color.red(accent), Color.green(accent), Color.blue(accent),
    )
}
