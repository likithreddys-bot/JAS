package ai.jas.remote

import android.content.SharedPreferences
import android.util.Log
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSession
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.X509TrustManager

/**
 * The laptop signs its own certificate, so there is no public authority to check it against.
 * Rather than making you install a certificate on the phone — or, far worse, trusting anything
 * that answers — this remembers the laptop the first time it meets it and from then on accepts
 * only that one. The same bargain SSH makes with a new host.
 *
 * What is remembered is the laptop's **public key**, not the whole certificate. The router hands
 * out a new IP every so often, and the certificate names the address, so pinning the certificate
 * meant a new address looked like a different machine and the app had to be re-paired. The key
 * outlives the address, so pinning that survives a move; it is also what certificate pinning is
 * supposed to mean.
 *
 * The fingerprint is shown in the app so it can be compared with the one the laptop prints.
 */
class JasTrust(private val prefs: SharedPreferences) : X509TrustManager {

    /** The laptop this phone has agreed to, as a readable SHA-256 fingerprint of its public key. */
    val known: String? get() = prefs.getString(KEY, null)

    /** Forget it, so the next connection pins whatever laptop answers. */
    fun forget() = prefs.edit().remove(KEY).apply()

    override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
        val leaf = chain?.firstOrNull() ?: throw CertificateException("The laptop sent no certificate")
        val seen = fingerprint(leaf)
        val remembered = known
        if (remembered == null) {
            Log.i(TAG, "Pinning this laptop: $seen")
            prefs.edit().putString(KEY, seen).apply()
            return
        }
        if (seen != remembered) {
            // The key, not the address, so a new IP does not land here. This means another machine.
            throw CertificateException(
                "This is not the laptop JAS was paired with. Expected $remembered but got $seen."
            )
        }
    }

    override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {
        throw CertificateException("This app is never a server")
    }

    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()

    companion object {
        private const val TAG = "JasTrust"
        private const val KEY = "cert"

        /** The laptop's public key, digested. Its certificate changes with its address; this does not. */
        fun fingerprint(certificate: X509Certificate): String =
            MessageDigest.getInstance("SHA-256").digest(certificate.publicKey.encoded)
                .joinToString(":") { "%02X".format(it) }

        /**
         * A socket factory that trusts only the pinned certificate, and a verifier that skips the
         * hostname check. Skipping it is safe here precisely because the certificate is pinned:
         * the name on it is the laptop's current address, which changes with the Wi-Fi, but the
         * key does not.
         */
        fun sockets(trust: JasTrust): SSLSocketFactory =
            SSLContext.getInstance("TLS").apply {
                init(null, arrayOf<X509TrustManager>(trust), java.security.SecureRandom())
            }.socketFactory

        val anyHostname = HostnameVerifier { _: String?, _: SSLSession? -> true }
    }
}
