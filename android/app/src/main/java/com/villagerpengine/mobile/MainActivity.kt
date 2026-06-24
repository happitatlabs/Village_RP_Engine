package com.villagerpengine.mobile

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var statusText: TextView
    private lateinit var loadingBar: ProgressBar
    private val mainHandler = Handler(Looper.getMainLooper())
    private val ioExecutor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        statusText = findViewById(R.id.statusText)
        loadingBar = findViewById(R.id.loadingBar)

        startEmbeddedServer()
        configureWebView()
        waitForServerThenLoad(attempt = 0)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                loadingBar.visibility = View.VISIBLE
                statusText.visibility = View.VISIBLE
                statusText.text = getString(R.string.loading_state)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                loadingBar.visibility = View.GONE
                statusText.visibility = View.GONE
                webView.visibility = View.VISIBLE
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?,
            ) {
                if (request?.isForMainFrame == true) {
                    statusText.text = getString(R.string.retry_state)
                }
            }
        }
    }

    private fun startEmbeddedServer() {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(applicationContext))
        }
        Python.getInstance()
            .getModule("android_bridge")
            .callAttr(
                "configure_and_start_server",
                filesDir.absolutePath,
                cacheDir.absolutePath,
                8000,
            )
    }

    private fun waitForServerThenLoad(attempt: Int) {
        ioExecutor.execute {
            val ready = isServerReady()
            mainHandler.post {
                if (ready) {
                    webView.loadUrl(BASE_URL)
                    return@post
                }
                if (attempt >= MAX_ATTEMPTS) {
                    loadingBar.visibility = View.GONE
                    statusText.text = getString(R.string.server_failed_state)
                    return@post
                }
                statusText.text = getString(R.string.booting_state, attempt + 1, MAX_ATTEMPTS)
                mainHandler.postDelayed({ waitForServerThenLoad(attempt + 1) }, RETRY_DELAY_MS)
            }
        }
    }

    private fun isServerReady(): Boolean {
        return try {
            val connection = URL("$BASE_URL/api/state").openConnection() as HttpURLConnection
            connection.connectTimeout = 1000
            connection.readTimeout = 1000
            connection.requestMethod = "GET"
            connection.connect()
            val success = connection.responseCode in 200..299
            connection.disconnect()
            success
        } catch (_: Exception) {
            false
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
            return
        }
        super.onBackPressed()
    }

    companion object {
        private const val BASE_URL = "http://127.0.0.1:8000"
        private const val MAX_ATTEMPTS = 30
        private const val RETRY_DELAY_MS = 500L
    }
}
