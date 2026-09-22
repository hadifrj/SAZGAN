package com.sazgan.app

import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class HomeActivity : AppCompatActivity() {

     
    private lateinit var listContainer: LinearLayout
    private lateinit var progress: ProgressBar
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var statusText: TextView

    private val COLOR_NAVY = Color.parseColor("#0c4a6e")
    private val COLOR_BG = Color.parseColor("#f0f9ff")
    private val COLOR_TEXT = Color.parseColor("#0f172a")
    private val COLOR_MUTED = Color.parseColor("#64748b")
    private val COLOR_BORDER = Color.parseColor("#e2e8f0")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ApiClient.init(this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setBackgroundColor(COLOR_BG)
        }

        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            setBackgroundColor(COLOR_NAVY)
        }
        toolbar.addView(TextView(this).apply {
            text = "کارتابل"
            textSize = 18f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.WHITE)
        })
        root.addView(toolbar)

        progress = ProgressBar(this).apply { visibility = View.GONE }
        root.addView(progress, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(12) })

        statusText = TextView(this).apply {
            textSize = 13f
            setTextColor(Color.parseColor("#dc2626"))
            gravity = Gravity.CENTER
            setPadding(dp(16), dp(12), dp(16), dp(12))
            visibility = View.GONE
        }
        root.addView(statusText)

        listContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(12), dp(12), dp(12))
        }

        val scroll = ScrollView(this)
        scroll.addView(listContainer)

        swipeRefresh = SwipeRefreshLayout(this).apply {
            addView(scroll)
            setOnRefreshListener { loadHome() }
        }

        root.addView(swipeRefresh, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        setContentView(root)
        loadHome()
    }

    private fun loadHome() {
        progress.visibility = View.VISIBLE
        statusText.visibility = View.GONE
        lifecycleScope.launch {
            try {
                val data = ApiClient.getJson("/api/native/home")
                renderHome(data)
            } catch (e: SessionExpiredError) {
                statusText.text = e.message
                statusText.visibility = View.VISIBLE
            } catch (e: Exception) {
                statusText.text = "خطا در دریافت اطلاعات: ${e.message}"
                statusText.visibility = View.VISIBLE
            } finally {
                progress.visibility = View.GONE
                swipeRefresh.isRefreshing = false
            }
        }
    }

    private fun renderHome(data: JSONObject) {
        listContainer.removeAllViews()
        val view = data.optString("view", "reception")

        if (view == "reception") {
            val requests: JSONArray = data.optJSONArray("requests") ?: JSONArray()
            if (requests.length() == 0) {
                listContainer.addView(emptyLabel("موردی برای نمایش نیست."))
            }
            for (i in 0 until requests.length()) {
                val r = requests.getJSONObject(i)
                listContainer.addView(requestCard(r))
            }
        } else {
            // سایر نقش‌ها (تکنسین، مالی، QC): فعلاً خلاصه‌ی ساده تا این صفحات هم اضافه بشن
            listContainer.addView(emptyLabel("نمای «$view» به‌زودی اضافه می‌شود."))
        }
    }

    private fun emptyLabel(text: String): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = 13f
            setTextColor(COLOR_MUTED)
            gravity = Gravity.CENTER
            setPadding(0, dp(24), 0, dp(24))
        }
    }

    private fun requestCard(r: JSONObject): LinearLayout {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(14), dp(14), dp(14))
            val bg = GradientDrawable().apply {
                setColor(Color.WHITE); cornerRadius = dp(10).toFloat()
                setStroke(dp(1), COLOR_BORDER)
            }
            background = bg
        }
        val lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = dp(10) }

        card.addView(TextView(this).apply {
            text = r.optString("device_type", "") + " — " + r.optString("customer_name", "")
            textSize = 14.5f
            setTypeface(null, Typeface.BOLD)
            setTextColor(COLOR_TEXT)
        })
        card.addView(TextView(this).apply {
            text = "شماره: " + (r.optString("reception_no").ifEmpty { "#" + r.optInt("id") })
            textSize = 12.5f
            setTextColor(COLOR_MUTED)
            setPadding(0, dp(4), 0, 0)
        })
        card.addView(TextView(this).apply {
            text = "وضعیت: " + r.optString("status", "")
            textSize = 12.5f
            setTextColor(Color.parseColor("#0284c7"))
            setPadding(0, dp(4), 0, 0)
        })

        listContainer.addView(card, lp)
        return card
    }

    private fun dp(v: Int): Int {
        val d = resources.displayMetrics.density
        return Math.round(v * d)
    }
}
