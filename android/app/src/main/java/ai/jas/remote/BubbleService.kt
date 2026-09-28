package ai.jas.remote

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.Icon
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * JAS living on top of the phone: a small face you can drag anywhere, listening the whole time it
 * is showing. Tap it for Pause and Hide; drag it out of the way; it speaks the laptop's replies
 * out of the phone's own speaker.
 */
class BubbleService : Service(), SensorEventListener {

    private lateinit var windows: WindowManager
    private lateinit var laptop: Laptop
    private lateinit var face: JasFace
    private lateinit var glow: EdgeGlow
    private lateinit var label: TextView
    private lateinit var bubble: LinearLayout
    private lateinit var controls: LinearLayout
    private lateinit var bubbleWhere: WindowManager.LayoutParams

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var ears: Ears? = null
    private val mouth = Mouth()
    private var speaking: Job? = null

    private var paused = false
    private var spoken = -1          // the reply_id we have already said out loud
    private var last: Snapshot = Snapshot.offline

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windows = getSystemService(WINDOW_SERVICE) as WindowManager
        laptop = Laptop(this)
        try {
            startForeground(NOTIFICATION, notification())
        } catch (e: Exception) {
            // Android 14 refuses a microphone service if the permission was revoked while we
            // were not running, which happens after a restart. The activity asks for it again.
            Log.e(TAG, "Could not start in the foreground", e)
            stopSelf()
            return
        }

        if (!Settings.canDrawOverlays(this)) {
            // Without this we have no window to draw in; the activity asks for it, so just leave.
            Log.e(TAG, "No overlay permission — stopping")
            stopSelf()
            return
        }
        addGlow()
        addBubble()
        listen()
        watch()
        (getSystemService(SENSOR_SERVICE) as SensorManager).let { sensors ->
            sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let {
                sensors.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_HIDE) stopSelf()
        return START_STICKY
    }

    override fun onDestroy() {
        (getSystemService(SENSOR_SERVICE) as SensorManager).unregisterListener(this)
        ears?.stop()
        mouth.stop()
        scope.cancel()
        if (::bubble.isInitialized) runCatching { windows.removeView(bubble) }
        if (::glow.isInitialized) runCatching { windows.removeView(glow) }
        super.onDestroy()
    }

    // --- the windows ---------------------------------------------------------

    private fun overlayType() =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE

    private fun addGlow() {
        glow = EdgeGlow(this)
        val where = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        )
        runCatching { windows.addView(glow, where) }
            .onFailure { Log.e(TAG, "Could not add the edge glow", it) }
    }

    private fun addBubble() {
        val size = dp(74)

        face = JasFace(this).apply {
            layoutParams = LinearLayout.LayoutParams(size, size)
        }

        label = TextView(this).apply {
            setTextColor(Color.parseColor("#C9D3E4"))
            textSize = 12f
            setPadding(dp(12), dp(7), dp(12), dp(7))
            background = pill("#141A26")
            visibility = View.GONE
        }

        controls = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            addView(label)
            addView(chip("Pause") { togglePause() }, marginTop(dp(6)))
            addView(chip("Hide") { stopSelf() }, marginTop(dp(6)))
        }

        bubble = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(face)
            addView(controls, marginStart(dp(8)))
        }

        bubbleWhere = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = dp(16)
            y = dp(180)
        }

        face.setOnTouchListener(dragger())
        runCatching { windows.addView(bubble, bubbleWhere) }
            .onFailure { Log.e(TAG, "Could not add the bubble", it); stopSelf() }
    }

    /** Drag to move it anywhere; a tap without much movement opens the two controls. */
    private fun dragger() = object : View.OnTouchListener {
        private var downX = 0f
        private var downY = 0f
        private var fromX = 0
        private var fromY = 0
        private var moved = false

        override fun onTouch(view: View, event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX; downY = event.rawY
                    fromX = bubbleWhere.x; fromY = bubbleWhere.y
                    moved = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downX
                    val dy = event.rawY - downY
                    if (abs(dx) > dp(8) || abs(dy) > dp(8)) moved = true
                    if (moved) {
                        bubbleWhere.x = fromX + dx.roundToInt()
                        bubbleWhere.y = fromY + dy.roundToInt()
                        runCatching { windows.updateViewLayout(bubble, bubbleWhere) }
                    }
                }
                MotionEvent.ACTION_UP -> if (!moved) {
                    controls.visibility = if (controls.isVisible()) View.GONE else View.VISIBLE
                    label.visibility = View.VISIBLE
                    label.text = last.label
                }
            }
            return true
        }
    }

    private fun View.isVisible() = visibility == View.VISIBLE

    private fun chip(text: String, onTap: () -> Unit) = TextView(this).apply {
        this.text = text
        setTextColor(Color.parseColor("#E8ECF4"))
        textSize = 13f
        setPadding(dp(16), dp(9), dp(16), dp(9))
        background = pill("#1B2432")
        setOnClickListener { onTap() }
    }

    private fun pill(colour: String) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(999).toFloat()
        setColor(Color.parseColor(colour))
        setStroke(dp(1), Color.parseColor("#263041"))
    }

    private fun marginTop(px: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT,
    ).apply { topMargin = px }

    private fun marginStart(px: Int) = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT,
    ).apply { marginStart = px }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).roundToInt()

    // --- listening -----------------------------------------------------------

    @Volatile private var sending = false

    private fun listen() {
        ears = Ears(
            onLevel = { level -> scope.launch { face.level = level } },
            onSpeech = { wav -> scope.launch { send(wav) } },
        ).also { it.start() }
    }

    private suspend fun send(wav: ByteArray) {
        if (paused) return
        // The laptop has one Whisper model, on CPU, shared by everything that can hear it. A real
        // conversation nearby can make Ears detect several utterances in the time one POST takes to
        // answer, and sending them all at once is exactly what queued the laptop 75 seconds deep on
        // one busy night. One clip in flight at a time; a phrase spoken while this is out is simply
        // not sent - the same choice the laptop itself now makes about its own backlog.
        if (sending) return
        sending = true
        try {
            laptop.listen(wav)
            // What was heard is deliberately not shown here - voice in, voice out, nothing typed
            // on screen. The face's mood already shows JAS is working; tap it for the state word.
        } finally {
            sending = false
        }
    }

    private fun togglePause() {
        paused = !paused
        if (paused) { ears?.stop(); mouth.stop() } else ears?.start()
        (controls.getChildAt(1) as TextView).text = if (paused) "Resume" else "Pause"
        label.text = if (paused) "paused" else last.label
        label.visibility = View.VISIBLE
    }

    // --- following the laptop ------------------------------------------------

    private fun watch() = scope.launch {
        while (isActive) {
            val snapshot = laptop.state() ?: Snapshot.offline
            last = snapshot
            face.show(snapshot)
            glow.show(snapshot)
            // The reply's words are deliberately never shown here, only spoken - see send() above.
            if (label.isVisible() && !paused) label.text = snapshot.label

            if (!paused && snapshot.canSpeak && snapshot.said.isNotEmpty() && snapshot.replyId != spoken) {
                spoken = snapshot.replyId
                say()
            }
            // Ask often while it is working, rarely while it is idle, so the battery survives.
            delay(if (snapshot.busy) 350L else 900L)
        }
    }

    private fun say() {
        speaking?.cancel()
        speaking = scope.launch {
            val wav = laptop.voice() ?: return@launch
            ears?.mute(true)
            try {
                withContext(Dispatchers.IO) { mouth.say(wav) }
            } finally {
                // A moment for the room to go quiet before the microphone opens again.
                delay(250)
                if (!paused) ears?.mute(false)
            }
        }
    }

    // --- tilt ----------------------------------------------------------------

    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type != Sensor.TYPE_ACCELEROMETER) return
        // Gravity is about 9.8 on the axis pointing down; a third of that is a firm tilt.
        face.tilt(-event.values[0] / 3.5f, event.values[1] / 3.5f - 0.15f)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    // --- the notification the foreground service must have -------------------

    private fun notification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, "JAS", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Shows that JAS is on screen and listening"
                    setShowBadge(false)
                }
            )
        }
        val hide = PendingIntent.getService(
            this, 1, Intent(this, BubbleService::class.java).setAction(ACTION_HIDE),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val open = PendingIntent.getActivity(
            this, 2, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            Notification.Builder(this, CHANNEL) else @Suppress("DEPRECATION") Notification.Builder(this)
        return builder
            .setContentTitle("JAS is listening")
            .setContentText("Tap the face on screen for Pause and Hide")
            .setSmallIcon(R.drawable.ic_jas)
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(null as Icon?, "Hide", hide).build())
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val TAG = "JasBubble"
        private const val CHANNEL = "jas"
        private const val NOTIFICATION = 7
        const val ACTION_HIDE = "ai.jas.remote.HIDE"

        fun start(context: Context) {
            val intent = Intent(context, BubbleService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent)
            else context.startService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, BubbleService::class.java))
        }
    }
}
