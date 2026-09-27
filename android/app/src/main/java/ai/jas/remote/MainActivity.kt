package ai.jas.remote

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * The setup screen and the full-size face. Everything JAS does on the phone happens in
 * [BubbleService]; this is where you point the app at the laptop and grant the two permissions
 * that make the floating face possible.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var laptop: Laptop
    private lateinit var face: JasFace
    private lateinit var label: TextView
    private lateinit var said: TextView
    private lateinit var cert: TextView
    private lateinit var hostField: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        laptop = Laptop(this)

        face = findViewById(R.id.face)
        label = findViewById(R.id.label)
        said = findViewById(R.id.said)
        cert = findViewById(R.id.cert)

        hostField = findViewById(R.id.host)
        val pin = findViewById<EditText>(R.id.pin)
        val away = findViewById<EditText>(R.id.away)
        hostField.setText(laptop.host)
        pin.setText(laptop.pin)
        away.setText(laptop.awayHost)

        findViewById<Button>(R.id.show).setOnClickListener {
            laptop.host = hostField.text.toString()
            laptop.pin = pin.text.toString()
            laptop.awayHost = away.text.toString()
            if (!laptop.configured) {
                say("Enter the PIN first — JAS prints it on the laptop when it starts.")
                return@setOnClickListener
            }
            askPermissions()
        }

        findViewById<TextView>(R.id.hide).setOnClickListener {
            BubbleService.stop(this)
            say("JAS is off the screen. The laptop carries on as normal.")
        }

        // Asking first, because a mis-tap here is exactly what stopped this working the first time.
        findViewById<TextView>(R.id.repair).setOnClickListener {
            AlertDialog.Builder(this)
                .setMessage(R.string.pair_again_ask)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.pair_again) { _, _ ->
                    laptop.trust.forget()
                    say(getString(R.string.pair_again_done))
                }
                .show()
        }

        val text = findViewById<EditText>(R.id.text)
        val send = {
            val words = text.text.toString().trim()
            if (words.isNotEmpty()) {
                text.setText("")
                lifecycleScope.launch {
                    if (!laptop.ask(words)) say("Could not reach the laptop.")
                }
            }
        }
        findViewById<Button>(R.id.send).setOnClickListener { send() }
        text.setOnEditorActionListener { _, action, _ ->
            if (action == EditorInfo.IME_ACTION_SEND) { send(); true } else false
        }

        follow()
    }

    /** Keeps the big face in step with the laptop for as long as this screen is in front. */
    private fun follow() = lifecycleScope.launch {
        repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                if (laptop.configured) {
                    val snapshot = laptop.state() ?: Snapshot.offline
                    face.show(snapshot)
                    label.text = snapshot.label
                    said.text = if (snapshot.state == "offline") laptop.lastError.orEmpty() else snapshot.said
                    cert.text = buildString {
                        append(if (laptop.host.isEmpty()) "looking for the laptop…" else laptop.host)
                        append(laptop.fingerprint?.let { "  ·  paired key ${it.take(11)}…" } ?: "  ·  not paired yet")
                    }
                    if (hostField.text.toString() != laptop.host && !hostField.hasFocus()) {
                        hostField.setText(laptop.host)  // discovery may have moved it
                    }
                    delay(if (snapshot.busy) 400L else 1000L)
                } else {
                    label.text = getString(R.string.not_set_up)
                    delay(1000L)
                }
            }
        }
    }

    // --- the two permissions -------------------------------------------------

    private fun askPermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                wanted += Manifest.permission.POST_NOTIFICATIONS
            }
            ActivityCompat.requestPermissions(this, wanted.toTypedArray(), MIC)
            return
        }
        if (!Settings.canDrawOverlays(this)) {
            say("Allow JAS to draw over other apps, then press Show again.")
            startActivity(
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
            )
            return
        }
        BubbleService.start(this)
        say("JAS is on screen and listening. Just talk.")
        moveTaskToBack(true)
    }

    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, granted: IntArray) {
        super.onRequestPermissionsResult(code, permissions, granted)
        if (code != MIC) return
        val ok = permissions.indexOf(Manifest.permission.RECORD_AUDIO).let {
            it >= 0 && it < granted.size && granted[it] == PackageManager.PERMISSION_GRANTED
        }
        if (ok) askPermissions() else say("Without the microphone JAS cannot hear you.")
    }

    private fun say(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    private companion object { const val MIC = 11 }
}
