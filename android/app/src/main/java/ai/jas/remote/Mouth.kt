package ai.jas.remote

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log

/**
 * Speaks a WAV the laptop rendered, so the reply comes out of the phone in JAS's own voice.
 * Plays straight from memory: no temporary files, and the caller learns exactly when it is done
 * so the microphone can be unmuted at the right moment.
 */
class Mouth {

    private var track: AudioTrack? = null

    /** Plays to the end, or until [stop]. Blocking, so call it off the main thread. */
    fun say(wav: ByteArray) {
        val sound = parse(wav) ?: return
        stop()
        val player = try {
            AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(sound.rate)
                        .setChannelMask(
                            if (sound.channels == 2) AudioFormat.CHANNEL_OUT_STEREO
                            else AudioFormat.CHANNEL_OUT_MONO
                        )
                        .build()
                )
                .setTransferMode(AudioTrack.MODE_STREAM)
                // Half a second of audio, not the whole clip. With WRITE_BLOCKING this makes write()
                // block until the speaker has room, which is what keeps us in step with playback.
                .setBufferSizeInBytes(maxOf(sound.rate * sound.channels, 8192))
                .build()
        } catch (e: Exception) {
            Log.e(TAG, "Could not open the speaker", e)
            return
        }
        track = player
        player.play()
        var written = 0
        while (written < sound.pcm.size && track === player) {
            val wrote = player.write(sound.pcm, written, sound.pcm.size - written,
                AudioTrack.WRITE_BLOCKING)
            if (wrote <= 0) break
            written += wrote
        }
        if (track === player) {
            drain(player, written / (sound.channels * 2), sound.rate)
            release(player)
            if (track === player) track = null
        }
    }

    /**
     * Waits for the speaker to actually reach the end. `write` only hands bytes to the buffer, so
     * stopping when the last write returns cuts the reply off mid-word - which is exactly what
     * turned "hey shantanu" into "hey shan.ta". The head position is the only honest answer to
     * "has it been played yet", so we watch that, with a deadline so a stalled track cannot hang us.
     */
    private fun drain(player: AudioTrack, frames: Int, rate: Int) {
        val expected = frames.toLong() * 1000L / rate
        val deadline = System.currentTimeMillis() + expected + 2000L
        while (track === player && System.currentTimeMillis() < deadline) {
            if (player.playbackHeadPosition >= frames) break
            try { Thread.sleep(20) } catch (e: InterruptedException) { return }
        }
    }

    fun stop() {
        track?.let { release(it) }
        track = null
    }

    private fun release(player: AudioTrack) {
        try {
            if (player.playState == AudioTrack.PLAYSTATE_PLAYING) player.pause()
            player.flush()
            player.stop()
        } catch (e: IllegalStateException) {
            Log.d(TAG, "already stopped")
        }
        player.release()
    }

    private class Sound(val pcm: ByteArray, val rate: Int, val channels: Int)

    /** Walks the RIFF chunks rather than assuming a 44-byte header, which is not always true. */
    private fun parse(wav: ByteArray): Sound? {
        if (wav.size < 44 || String(wav, 0, 4) != "RIFF" || String(wav, 8, 4) != "WAVE") {
            Log.e(TAG, "That was not a WAV (${wav.size} bytes)")
            return null
        }
        var rate = 22_050
        var channels = 1
        var at = 12
        while (at + 8 <= wav.size) {
            val id = String(wav, at, 4)
            val size = le32(wav, at + 4)
            val body = at + 8
            if (size < 0 || body + size > wav.size) {
                if (id == "data") return Sound(wav.copyOfRange(body, wav.size), rate, channels)
                break
            }
            when (id) {
                "fmt " -> {
                    channels = le16(wav, body + 2).coerceIn(1, 2)
                    rate = le32(wav, body + 4).let { if (it in 8000..48000) it else 22_050 }
                }
                "data" -> return Sound(wav.copyOfRange(body, body + size), rate, channels)
            }
            at = body + size + (size and 1)  // chunks are word-aligned
        }
        Log.e(TAG, "No data chunk in that WAV")
        return null
    }

    private fun le16(b: ByteArray, at: Int) = (b[at].toInt() and 0xFF) or ((b[at + 1].toInt() and 0xFF) shl 8)

    private fun le32(b: ByteArray, at: Int) = (b[at].toInt() and 0xFF) or
        ((b[at + 1].toInt() and 0xFF) shl 8) or
        ((b[at + 2].toInt() and 0xFF) shl 16) or
        ((b[at + 3].toInt() and 0xFF) shl 24)

    private companion object { const val TAG = "JasMouth" }
}
