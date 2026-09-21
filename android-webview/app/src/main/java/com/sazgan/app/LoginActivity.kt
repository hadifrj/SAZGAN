package com.sazgan.app

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    private lateinit var api: ApiClient
    private lateinit var serverInput: EditText
    private lateinit var userInput: EditText
    private lateinit var passInput: EditText
    private lateinit var statusText: TextView
    private lateinit var loginBtn: Button
    private lateinit var progress: ProgressBar

    private val COLOR_NAVY = Color.parseColor("#0c4a6e")
    private val COLOR_ACCENT = Color.parseColor("#0284c7")
    private val COLOR_BG = Color.parseColor("#f0f9ff")
    private val COLOR_TEXT = Color.parseColor("#0f172a")
    private val COLOR_MUTED = Color.parseColor("#64748b")
    private val COLOR_BORDER = Color.parseColor("#e2e8f0")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        api = ApiClient(this)

        val root = ScrollView(this).apply { setBackgroundColor(COLOR_BG) }
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(28), dp(48), dp(28), dp(28))
        }

        val title = TextView(this).apply {
            text = "سازگان"
            textSize = 26f
            setTypeface(null, Typeface.BOLD)
            setTextColor(COLOR_NAVY)
            gravity = Gravity.CENTER
        }
        panel.addView(title)

        val subtitle = TextView(this).apply {
            text = "ورود به سامانه مدیریت خدمات پس از فروش"
            textSize = 13f
            setTextColor(COLOR_MUTED)
            gravity = Gravity.CENTER
            setPadding(0, dp(6), 0, dp(28))
        }
        panel.addView(subtitle)

        serverInput = makeInput("آدرس سرور (مثال: http://192.168.1.10:5000)", InputType.TYPE_TEXT_VARIATION_URI)
        serverInput.setText(api.baseUrl)
        panel.addView(labeled("آدرس سرور", serverInput))

        userInput = makeInput("نام کاربری", InputType.TYPE_CLASS_TEXT)
        panel.addView(labeled("نام کاربری", userInput))

        passInput = makeInput("رمز عبور", InputType.TYPE_TEXT_VARIATION_PASSWORD or InputType.TYPE_CLASS_TEXT)
        panel.addView(labeled("رمز عبور", passInput))

        progress = ProgressBar(this).apply { visibility = View.GONE }
        panel.addView(progress, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(12); gravity = Gravity.CENTER })

        statusText = TextView(this).apply {
            textSize = 13f
            setTextColor(Color.parseColor("#dc2626"))
            gravity = Gravity.CENTER
            setPadding(0, dp(8), 0, dp(8))
        }
        panel.addView(statusText)

        loginBtn = Button(this).apply {
            text = "ورود"
            isAllCaps = false
            setTextColor(Color.WHITE)
            textSize = 15f
            val bg = GradientDrawable().apply { setColor(COLOR_ACCENT); cornerRadius = dp(10).toFloat() }
            background = bg
            setPadding(dp(16), dp(14), dp(16), dp(14))
            setOnClickListener { doLogin() }
        }
        panel.addView(loginBtn, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(8) })

        root.addView(panel)
        setContentView(root)
    }

    private fun labeled(labelText: String, input: EditText): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 0, 0, dp(14))
            addView(TextView(this@LoginActivity).apply {
                text = labelText
                textSize = 12.5f
                setTypeface(null, Typeface.BOLD)
                setTextColor(COLOR_TEXT)
                setPadding(0, 0, 0, dp(6))
            })
            addView(input)
        }
    }

    private fun makeInput(hintText: String, type: Int): EditText {
        return EditText(this).apply {
            hint = hintText
            inputType = type
            setSingleLine(true)
            textSize = 15f
            setTextColor(COLOR_TEXT)
            setHintTextColor(COLOR_MUTED)
            setPadding(dp(14), dp(14), dp(14), dp(14))
            val bg = GradientDrawable().apply {
                setColor(Color.WHITE); cornerRadius = dp(10).toFloat()
                setStroke(dp(1), COLOR_BORDER)
            }
            background = bg
        }
    }

    private fun doLogin() {
        val server = normalizeUrl(serverInput.text.toString().trim())
        val user = userInput.text.toString().trim()
        val pass = passInput.text.toString()

        if (server.isEmpty()) { statusText.text = "آدرس سرور را وارد کنید."; return }
        if (user.isEmpty() || pass.isEmpty()) { statusText.text = "نام کاربری و رمز عبور را وارد کنید."; return }

        api.baseUrl = server
        statusText.text = ""
        progress.visibility = View.VISIBLE
        loginBtn.isEnabled = false

        lifecycleScope.launch {
            val result = api.login(user, pass)
            progress.visibility = View.GONE
            loginBtn.isEnabled = true
            result.onSuccess {
                startActivity(Intent(this@LoginActivity, HomeActivity::class.java))
                finish()
            }.onFailure { e ->
                statusText.text = e.message ?: "ورود ناموفق بود."
            }
        }
    }

    private fun normalizeUrl(raw: String): String {
        if (raw.isEmpty()) return ""
        var u = raw
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "http://$u"
        return u.trimEnd('/')
    }

    private fun dp(v: Int): Int {
        val d = resources.displayMetrics.density
        return Math.round(v * d)
    }
}
