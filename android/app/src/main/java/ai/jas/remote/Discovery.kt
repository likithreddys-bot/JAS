package ai.jas.remote

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException

/**
 * Finds the laptop rather than being told where it is.
 *
 * The router reassigns the laptop's address constantly — in two days it was .131, then .118, then
 * .111 — so an app that holds a typed-in IP is broken by the next lease. This shouts "JAS?" across
 * the local network and takes the first answer.
 *
 * Learning the address grants nothing on its own: every real request still carries the PIN, and the
 * laptop is still recognised by its pinned public key, so answering this cannot impersonate it.
 */
object Discovery {

    private const val TAG = "JasFind"
    private const val PORT = 8771
    private const val ASK = "JAS?"
    private const val WAIT_MS = 1200
    private const val TRIES = 3

    /** "192.168.0.111:8770" for the laptop running JAS, or null if nothing answered. */
    suspend fun findLaptop(): String? = withContext(Dispatchers.IO) {
        val socket = try {
            DatagramSocket().apply {
                broadcast = true
                soTimeout = WAIT_MS
            }
        } catch (e: Exception) {
            Log.w(TAG, "Could not open a socket to look for the laptop", e)
            return@withContext null
        }

        socket.use {
            val question = ASK.toByteArray()
            repeat(TRIES) { attempt ->
                // A single datagram is easily lost, and some routers drop 255.255.255.255 while
                // passing the subnet's own broadcast address, so ask both, a few times.
                for (target in targets()) {
                    try {
                        socket.send(DatagramPacket(question, question.size, target, PORT))
                    } catch (e: Exception) {
                        Log.d(TAG, "Could not ask $target: ${e.message}")
                    }
                }
                val answer = listen(socket)
                if (answer != null) {
                    Log.i(TAG, "Found JAS at $answer on attempt ${attempt + 1}")
                    return@withContext answer
                }
            }
        }
        Log.i(TAG, "Nothing on this network is running JAS")
        null
    }

    private fun listen(socket: DatagramSocket): String? {
        val buffer = ByteArray(64)
        val deadline = System.currentTimeMillis() + WAIT_MS
        while (System.currentTimeMillis() < deadline) {
            val packet = DatagramPacket(buffer, buffer.size)
            try {
                socket.receive(packet)
            } catch (e: SocketTimeoutException) {
                return null
            } catch (e: Exception) {
                Log.d(TAG, "receive: ${e.message}")
                return null
            }
            // "JAS <host> <port>". Anything else on this port is not ours.
            val parts = String(packet.data, 0, packet.length).trim().split(" ")
            if (parts.size == 3 && parts[0] == "JAS" && parts[2].toIntOrNull() != null) {
                return "${parts[1]}:${parts[2]}"
            }
        }
        return null
    }

    private fun targets(): List<InetAddress> = buildList {
        runCatching { add(InetAddress.getByName("255.255.255.255")) }
        runCatching { add(InetAddress.getByName("192.168.0.255")) }
        runCatching { add(InetAddress.getByName("192.168.1.255")) }
    }
}
