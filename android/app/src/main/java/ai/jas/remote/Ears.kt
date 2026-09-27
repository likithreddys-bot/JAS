package ai.jas.remote

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import java.io.ByteArrayOutputStream
import kotlin.concurrent.thread
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Always-on listening on the phone. There is no button: it records continuously, keeps only the
 * stretches where somebody is actually talking, and hands each of those over as a 16 kHz WAV.
 *
 * The audio goes to the laptop and nowhere else, and nothing is kept once an utterance is sent.
 */
class Ears(
    private val onLevel: (Float) -> Unit,
    private val onSpeech: (ByteArray) -> Unit,
) {

    private var record: AudioRecord? = null
    @Volatile private var listening = false
    @Volatile private var muted = false

    /** Muted while JAS is talking, so it never transcribes its own voice. */
    fun mute(quiet: Boolean) {
        muted = quiet
        if (quiet) { speech.reset(); quietFor = 0; spokenFor = 0; peak = 0f }
    }

    @SuppressLint("MissingPermission")  // MainActivity will not start the service without it.
    fun start() {
        if (listening) return
        val minimum = AudioRecord.getMinBufferSize(RATE, CHANNEL, ENCODING)
        if (minimum <= 0) {
            Log.e(TAG, "This phone will not give us a 16 kHz mono recorder")
            return
        }
        val recorder = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE, CHANNEL, ENCODING,
                maxOf(minimum, CHUNK * 8))
        } catch (e: Exception) {
            Log.e(TAG, "Could not open the microphone", e)
            return
        }
        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "The microphone did not initialise")
            recorder.release()
            return
        }
        record = recorder
        listening = true
        recorder.startRecording()
        thread(name = "jas-ears", isDaemon = true) { loop(recorder) }
    }

    fun stop() {
        listening = false
        record?.let {
            try { it.stop() } catch (e: IllegalStateException) { Log.d(TAG, "already stopped") }
            it.release()
        }
        record = null
        speech.reset()
        onLevel(0f)
    }

    private val speech = ByteArrayOutputStream()
    private var quietFor = 0   // milliseconds of silence since the last speech
    private var spokenFor = 0  // milliseconds actually above the threshold
    private var peak = 0f      // the loudest frame in this utterance
    private var floor = 0.004f // what this room sounds like when nobody is talking

    private fun loop(recorder: AudioRecord) {
        val buffer = ShortArray(CHUNK)
        val chunkMs = CHUNK * 1000 / RATE
        while (listening) {
            val read = recorder.read(buffer, 0, CHUNK)
            if (read <= 0) continue
            val loudness = rms(buffer, read)
            onLevel(if (muted) 0f else loudness * 14f)
            if (muted) continue

            val mid = speech.size() > 0
            if (loudness >= startsSpeech()) {
                quietFor = 0
                spokenFor += chunkMs
                peak = max(peak, loudness)
                append(buffer, read)
            } else if (mid) {
                quietFor += chunkMs
                append(buffer, read)  // keep the tail, so the last word is not clipped
                if (quietFor >= QUIET_MS) finish()
            } else {
                // Nobody is talking, so this is what the room sounds like. Learning it means one
                // threshold works in a silent bedroom and beside a fan, and a voice from the next
                // room is not thrown away for being quiet.
                floor = floor * (1f - LEARN) + loudness * LEARN
            }
            // Never let one utterance run away with the whole heap.
            if (speech.size() > RATE * 2 * MAX_SECONDS) finish()
        }
    }

    /** Above this, the microphone is probably hearing a voice rather than the room. */
    private fun startsSpeech() = max(QUIETEST, floor * STARTS)

    private fun append(buffer: ShortArray, count: Int) {
        for (i in 0 until count) {
            val s = buffer[i].toInt()
            speech.write(s and 0xFF)
            speech.write((s shr 8) and 0xFF)
        }
    }

    private fun finish() {
        val pcm = speech.toByteArray()
        val spoken = spokenFor
        val loudest = peak
        speech.reset()
        quietFor = 0
        spokenFor = 0
        peak = 0f
        // Two tests, and both are on the speech, never on the whole clip: the clip always contains
        // the 1.1 s of silence that ended it, so measuring the clip would pass every cough. The
        // second is the peak, because a fan sits just over the threshold for a long time while a
        // real voice goes well past it - measured against the room, not a number I guessed.
        val needed = max(QUIETEST * 1.6f, floor * CLEARLY)
        val ok = spoken >= MIN_MS && loudest >= needed
        Log.i(TAG, "%dms of speech, peak %.4f, needed %.4f, room %.4f -> %s"
            .format(spoken, loudest, needed, floor, if (ok) "sent" else "dropped"))
        if (!ok) return
        onSpeech(wav(pcm))
    }

    private fun rms(buffer: ShortArray, count: Int): Float {
        var sum = 0.0
        for (i in 0 until count) {
            val v = buffer[i] / 32768.0
            sum += v * v
        }
        return sqrt(sum / count).toFloat()
    }

    private companion object {
        const val TAG = "JasEars"
        const val RATE = 16_000
        const val CHANNEL = AudioFormat.CHANNEL_IN_MONO
        const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
        const val CHUNK = 1600           // 100 ms
        const val QUIETEST = 0.006f      // never listen below this, however silent the room
        const val STARTS = 2.5f          // this much above the room means somebody is talking
        const val CLEARLY = 4.0f         // and the peak must reach this much above it to be a voice
        const val LEARN = 0.05f          // how fast the room's own level is re-learned
        const val QUIET_MS = 1100
        const val MIN_MS = 350           // of speech, not of clip
        const val MAX_SECONDS = 20

        /** A 16-bit mono WAV around raw PCM, which is what the laptop's /listen expects. */
        fun wav(pcm: ByteArray): ByteArray {
            val out = ByteArrayOutputStream(44 + pcm.size)
            fun str(s: String) = out.write(s.toByteArray())
            fun int(v: Int) {
                out.write(v and 0xFF); out.write((v shr 8) and 0xFF)
                out.write((v shr 16) and 0xFF); out.write((v shr 24) and 0xFF)
            }
            fun short(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }

            str("RIFF"); int(36 + pcm.size); str("WAVE")
            str("fmt "); int(16); short(1); short(1)
            int(RATE); int(RATE * 2); short(2); short(16)
            str("data"); int(pcm.size)
            out.write(pcm)
            return out.toByteArray()
        }
    }
}
