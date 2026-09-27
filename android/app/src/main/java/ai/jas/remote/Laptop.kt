package ai.jas.remote

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/** What the laptop is doing right now. */
data class Snapshot(
    val state: String,
    val label: String,
    val colour: String,
    val body: String,
    val heard: String,
    val said: String,
    val replyId: Int,
    val canSpeak: Boolean,
    val busy: Boolean,
) {
    companion object {
        val offline = Snapshot("offline", "can't reach the laptop", "#7C8699", "", "", "", 0, false, false)
    }
}

/**
 * The one place that talks to JAS on the laptop. Every call is suspending and does its own
 * network work off the main thread; a failure comes back as null rather than an exception,
 * because a phone loses its Wi-Fi constantly and that is not an error worth crashing over.
 */
class Laptop(context: Context) {

    private val prefs = context.getSharedPreferences("jas", Context.MODE_PRIVATE)

    var host: String
        get() = prefs.getString("host", "") ?: ""
        set(value) = prefs.edit().putString("host", value.trim()).apply()

    /**
     * The laptop's Tailscale address, e.g. "100.70.91.55:8770" — set once, by hand, and never
     * touched by discovery. [host] is what LAN broadcast last found and is only ever right on the
     * home network; overwriting this with that would strand the app the next time you left the
     * house with no working address remembered at all.
     */
    var awayHost: String
        get() = prefs.getString("away_host", "") ?: ""
        set(value) = prefs.edit().putString("away_host", value.trim()).apply()

    var pin: String
        get() = prefs.getString("pin", "") ?: ""
        set(value) = prefs.edit().putString("pin", value.trim()).apply()

    /** Only the PIN has to be typed in. The address is found on the network. */
    val configured: Boolean get() = pin.isNotEmpty()

    private var lastLookup = 0L

    /**
     * The laptop could not be reached, so its address has most likely changed again. Ask the
     * network where it is now. Rate-limited, because a laptop that is simply asleep is not found by
     * asking harder.
     */
    private suspend fun relocate(): Boolean {
        val now = System.currentTimeMillis()
        if (now - lastLookup < LOOKUP_EVERY_MS) return false
        lastLookup = now
        val found = Discovery.findLaptop() ?: return false
        if (found == host) return false
        Log.i(TAG, "The laptop moved from '$host' to '$found'")
        host = found
        return true
    }

    /** The laptop's certificate, pinned the first time we meet it. */
    val trust = JasTrust(prefs)
    private val sockets by lazy { JasTrust.sockets(trust) }

    /** The pinned certificate's fingerprint, or null before the first connection. */
    val fingerprint: String? get() = trust.known

    /** Why the last call failed, so the app can explain it rather than just showing "offline". */
    @Volatile var lastError: String? = null
        private set

    private fun url(path: String) = URL("https://$host$path?pin=$pin")

    private fun open(path: String, method: String, timeout: Int): HttpURLConnection =
        (url(path).openConnection() as HttpsURLConnection).apply {
            sslSocketFactory = sockets
            hostnameVerifier = JasTrust.anyHostname
            requestMethod = method
            connectTimeout = 4000
            readTimeout = timeout
        }

    /**
     * Polls the laptop. Tries the last address that worked, then the Tailscale address if one is
     * set, then asks the network to find it — in that order, because the LAN is fastest when it is
     * reachable at all, and only broadcast discovery can find an address that changed.
     */
    suspend fun state(): Snapshot? {
        if (host.isNotEmpty()) fetchState()?.let { return it }

        val away = awayHost
        if (away.isNotEmpty() && away != host) {
            val before = host
            host = away  // fetchState() reads the current host; this is how it is told which one
            fetchState()?.let { return it }
            host = before  // that one did not work either - do not strand a still-good LAN address
        }

        return if (relocate()) fetchState() else null
    }

    private suspend fun fetchState(): Snapshot? = withContext(Dispatchers.IO) {
        try {
            val c = open("/state", "GET", 5000)
            if (c.responseCode != 200) return@withContext null
            val j = JSONObject(c.inputStream.bufferedReader().use { it.readText() })
            lastError = null
            Snapshot(
                state = j.optString("state", "standby"),
                label = j.optString("label", ""),
                colour = j.optString("colour", "#FFC46B"),
                body = j.optString("body", ""),
                heard = j.optString("heard", ""),
                said = j.optString("said", ""),
                replyId = j.optInt("reply_id", 0),
                canSpeak = j.optBoolean("can_speak", false),
                busy = j.optBoolean("busy", false),
            )
        } catch (e: Exception) {
            Log.d(TAG, "state: ${e.message}")
            lastError = reason(e)
            null
        }
    }

    /** Sends recorded speech. Returns what the laptop heard, or null if it could not be reached. */
    suspend fun listen(wav: ByteArray): String? = withContext(Dispatchers.IO) {
        try {
            val c = open("/listen", "POST", 30_000)
            c.doOutput = true
            c.setRequestProperty("Content-Type", "audio/wav")
            c.setFixedLengthStreamingMode(wav.size)
            c.outputStream.use { it.write(wav) }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val j = JSONObject(stream.bufferedReader().use { it.readText() })
            j.optString("heard", "")
        } catch (e: Exception) {
            Log.d(TAG, "listen: ${e.message}")
            lastError = reason(e)
            null
        }
    }

    suspend fun ask(text: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val c = open("/ask", "POST", 15_000)
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(JSONObject().put("text", text).toString().toByteArray()) }
            c.responseCode in 200..299
        } catch (e: Exception) {
            Log.d(TAG, "ask: ${e.message}")
            lastError = reason(e)
            false
        }
    }

    /** The current reply as WAV bytes, rendered in JAS's own voice on the laptop. */
    suspend fun voice(): ByteArray? = withContext(Dispatchers.IO) {
        try {
            val c = open("/voice", "GET", 20_000)
            if (c.responseCode != 200) return@withContext null
            val out = ByteArrayOutputStream()
            c.inputStream.use { it.copyTo(out) }
            out.toByteArray()
        } catch (e: Exception) {
            Log.d(TAG, "voice: ${e.message}")
            lastError = reason(e)
            null
        }
    }

    /** Plain words for the two failures that actually happen: wrong certificate, or no laptop. */
    private fun reason(e: Exception): String = when {
        e is javax.net.ssl.SSLHandshakeException || e.cause is java.security.cert.CertificateException ->
            "This is not the laptop JAS was paired with — tap Pair again if the laptop made a new certificate."
        else -> e.message ?: e.javaClass.simpleName
    }

    private companion object {
        const val TAG = "JasLaptop"
        const val LOOKUP_EVERY_MS = 8000L
    }
}
