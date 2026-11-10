package com.ferhat.sinavasistani

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Tek ekranlı uygulama: arayüz assets/index.html içinde (HTML + JS) çalışır.
 * Bu sınıf yalnızca WebView'i açar, ayarları saklar ve OpenAI'ye HTTPS isteği gönderir.
 *
 * API anahtarı bilgisayardan şu komutla verilebilir (kumandayla yazmaya gerek kalmaz):
 *   adb shell am start -n com.ferhat.sinavasistani/.MainActivity --es api_key "sk-..."
 */
class MainActivity : Activity() {

    private lateinit var webView: WebView
    private val prefs by lazy { getSharedPreferences("ayarlar", Context.MODE_PRIVATE) }
    private val io = Executors.newFixedThreadPool(2)

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        readIntentExtras(intent)

        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.allowFileAccess = false
        webView.settings.allowContentAccess = false
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()
        webView.isFocusable = true
        webView.isFocusableInTouchMode = true
        webView.addJavascriptInterface(Bridge(), "Android")
        setContentView(webView)
        webView.requestFocus(View.FOCUS_DOWN)
        webView.loadUrl("file:///android_asset/index.html")
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (readIntentExtras(intent)) {
            webView.evaluateJavascript("window.onSettingsChanged && window.onSettingsChanged()", null)
        }
    }

    /** api_key / model ekstralarını kaydeder. Bir şey kaydedildiyse true döner. */
    private fun readIntentExtras(intent: Intent?): Boolean {
        if (intent == null) return false
        var changed = false
        intent.getStringExtra("api_key")?.trim()?.takeIf { it.isNotEmpty() }?.let {
            prefs.edit().putString("api_key", it).apply()
            changed = true
        }
        intent.getStringExtra("model")?.trim()?.takeIf { it.isNotEmpty() }?.let {
            prefs.edit().putString("model", it).apply()
            changed = true
        }
        return changed
    }

    @Deprecated("Activity kullanıldığı için klasik geri tuşu yöntemi")
    override fun onBackPressed() {
        // Önce arayüze sor: bir önceki ekrana dönebiliyorsa "true" döner.
        webView.evaluateJavascript("window.handleBack ? window.handleBack() : false") { result ->
            if (result != "true") {
                @Suppress("DEPRECATION")
                super.onBackPressed()
            }
        }
    }

    override fun onDestroy() {
        io.shutdownNow()
        webView.destroy()
        super.onDestroy()
    }

    inner class Bridge {
        @JavascriptInterface
        fun hasKey(): Boolean = !prefs.getString("api_key", "").isNullOrEmpty()

        @JavascriptInterface
        fun keyHint(): String {
            val k = prefs.getString("api_key", "") ?: ""
            return if (k.length < 8) "" else k.take(3) + "…" + k.takeLast(4)
        }

        @JavascriptInterface
        fun setKey(key: String) {
            prefs.edit().putString("api_key", key.trim()).apply()
        }

        /** Yazma ekranı açılınca ekran klavyesini göster (yalnızca kullanıcı OK'ye bastığında çağrılır). */
        @JavascriptInterface
        fun showKeyboard() {
            webView.post {
                webView.requestFocus()
                val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                imm.showSoftInput(webView, InputMethodManager.SHOW_IMPLICIT)
            }
        }

        @JavascriptInterface
        fun hideKeyboard() {
            webView.post {
                val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                imm.hideSoftInputFromWindow(webView.windowToken, 0)
            }
        }

        @JavascriptInterface
        fun getModel(): String = prefs.getString("model", "") ?: ""

        @JavascriptInterface
        fun setModel(model: String) {
            prefs.edit().putString("model", model.trim()).apply()
        }

        /**
         * OpenAI API'ye istek gönderir (yalnızca https://api.openai.com/v1/ altı).
         * Sonuç JS'e window.__bridgeCb(id, httpKodu, gövde) ile döner. Ağ hatasında kod 0'dır.
         */
        @JavascriptInterface
        fun request(callbackId: String, method: String, path: String, body: String) {
            io.execute {
                var code = 0
                var text: String
                try {
                    require(path.startsWith("/") && !path.contains("..")) { "Geçersiz yol" }
                    require(method == "GET" || method == "POST") { "Geçersiz yöntem" }
                    val key = prefs.getString("api_key", "") ?: ""
                    val conn = URL("https://api.openai.com/v1$path").openConnection() as HttpURLConnection
                    conn.requestMethod = method
                    conn.connectTimeout = 30_000
                    conn.readTimeout = 300_000
                    conn.setRequestProperty("Authorization", "Bearer $key")
                    conn.setRequestProperty("Content-Type", "application/json")
                    if (method == "POST") {
                        conn.doOutput = true
                        conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                    }
                    code = conn.responseCode
                    val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                    text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
                    conn.disconnect()
                } catch (e: Exception) {
                    text = e.javaClass.simpleName + ": " + (e.message ?: "")
                }
                val js = "window.__bridgeCb(${JSONObject.quote(callbackId)},$code,${JSONObject.quote(text)})"
                webView.post { webView.evaluateJavascript(js, null) }
            }
        }
    }
}
