package com.sazgan.app

import android.content.Intent
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
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.GravityCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.lifecycle.lifecycleScope
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class HomeActivity : AppCompatActivity() {

    private lateinit var drawerLayout: DrawerLayout
    private lateinit var listContainer: LinearLayout
    private lateinit var progress: ProgressBar
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var statusText: TextView
    private lateinit var screenTitle: TextView

    private val COLOR_NAVY = Color.parseColor("#0c4a6e")
    private val COLOR_BG = Color.parseColor("#f0f9ff")
    private val COLOR_TEXT = Color.parseColor("#0f172a")
    private val COLOR_MUTED = Color.parseColor("#64748b")
    private val COLOR_BORDER = Color.parseColor("#e2e8f0")
    private val COLOR_ACCENT = Color.parseColor("#0284c7")

    // هر آیتم منو: عنوان، مسیر API معادلش (اگه هنوز پیاده نشده null)
    private data class MenuItem(val title: String, val apiPath: String?)

    private val menuItems = listOf(
        MenuItem("کارتابل", "/api/native/home"),
        MenuItem("جست‌وجو", null),
        MenuItem("گفتگوی مشتری", null),
        MenuItem("اعلان‌ها", null),
        MenuItem("امور مشتریان", null),
        MenuItem("رهگیری قطعات", null),
        MenuItem("امور مالی", null),
        MenuItem("گزارش‌ها", null),
        MenuItem("تنظیمات", null),
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ApiClient.init(this)

        drawerLayout = DrawerLayout(this)

        // ----- محتوای اصلی -----
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setBackgroundColor(COLOR_BG)
        }

        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(14), dp(16), dp(14))
            setBackgroundColor(COLOR_NAVY)
        }
        val menuBtn = TextView(this).apply {
            text = "☰"
            textSize = 20f
            setTextColor(Color.WHITE)
            setPadding(dp(8), dp(4), dp(16), dp(4))
            setOnClickListener { drawerLayout.openDrawer(GravityCompat.START) }
        }
        toolbar.addView(menuBtn)
        screenTitle = TextView(this).apply {
            text = "کارتابل"
            textSize = 18f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.WHITE)
        }
        toolbar.addView(screenTitle)
        content.addView(toolbar)

        progress = ProgressBar(this).apply { visibility = View.GONE }
        content.addView(progress, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(12) })

        statusText = TextView(this).apply {
            textSize = 13f
            setTextColor(Color.parseColor("#dc2626"))
            gravity = Gravity.CENTER
            setPadding(dp(16), dp(12), dp(16), dp(12))
            visibility = View.GONE
        }
        content.addView(statusText)

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
        content.addView(swipeRefresh, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        drawerLayout.addView(content, DrawerLayout.LayoutParams(
            DrawerLayout.LayoutParams.MATCH_PARENT, DrawerLayout.LayoutParams.MATCH_PARENT
        ))

        // ----- منوی کشویی -----
        val drawerScroll = ScrollView(this).apply {
            setBackgroundColor(Color.WHITE)
        }
        val drawerPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutDirection = View.LAYOUT_DIRECTION_RTL
            setPadding(0, dp(24), 0, dp(24))
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), dp(20))
        }
        header.addView(TextView(this).apply {
            text = "سازگان گستر"
            textSize = 17f
            setTypeface(null, Typeface.BOLD)
            setTextColor(COLOR_NAVY)
        })
        header.addView(TextView(this).apply {
            text = "خدمات پس از فروش"
            textSize = 12.5f
            setTextColor(COLOR_MUTED)
            setPadding(0, dp(4), 0, 0)
        })
        drawerPanel.addView(header)
        drawerPanel.addView(divider())

        menuItems.forEach { item ->
            drawerPanel.addView(menuRow(item.title) {
                drawerLayout.closeDrawers()
                if (item.apiPath == "/api/native/home") {
                    screenTitle.text = item.title
                    loadHome()
                } else {
                    screenTitle.text = item.title
                    showPlaceholder(item.title)
                }
            })
        }

        drawerPanel.addView(divider())
        drawerPanel.addView(menuRow("خروج", isDanger = true) {
            drawerLayout.closeDrawers()
            doLogout()
        })

        drawerScroll.addView(drawerPanel)
        val drawerParams = DrawerLayout.LayoutParams(
            dp(260), DrawerLayout.LayoutParams.MATCH_PARENT
        )
        drawerParams.gravity = GravityCompat.START
        drawerLayout.addView(drawerScroll, drawerParams)

        setContentView(drawerLayout)
        loadHome()
    }

    private fun divider(): View {
        return View(this).apply {
            setBackgroundColor(COLOR_BORDER)
        }.also {
            val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(1))
            lp.topMargin = dp(4); lp.bottomMargin = dp(4)
            it.layoutParams = lp
        }
    }

    private fun menuRow(title: String, isDanger: Boolean = false, onClick: () -> Unit): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            isClickable = true
            isFocusable = true
            setPadding(dp(20), dp(14), dp(20), dp(14))
            addView(TextView(this@HomeActivity).apply {
                text = title
                textSize = 14.5f
                setTextColor(if (isDanger) Color.parseColor("#dc2626") else COLOR_TEXT)
            })
            setOnClickListener { onClick() }
        }
    }

    private fun showPlaceholder(title: String) {
        listContainer.removeAllViews()
        statusText.visibility = View.GONE
        listContainer.addView(emptyLabel("بخش «$title» به‌زودی اضافه می‌شود."))
    }

    private fun doLogout() {
        progress.visibility = View.VISIBLE
        lifecycleScope.launch {
            ApiClient.logout()
            progress.visibility = View.GONE
            Toast.makeText(this@HomeActivity, "با موفقیت خارج شدید.", Toast.LENGTH_SHORT).show()
            startActivity(Intent(this@HomeActivity, LoginActivity::class.java))
            finish()
        }
    }

    override fun onBackPressed() {
        if (drawerLayout.isDrawerOpen(GravityCompat.START)) {
            drawerLayout.closeDrawer(GravityCompat.START)
        } else {
            super.onBackPressed()
        }
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
            setTextColor(COLOR_ACCENT)
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
