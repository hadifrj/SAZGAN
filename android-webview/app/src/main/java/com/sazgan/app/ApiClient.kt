package com.sazgan.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.FormBody
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ApiError(message: String, val statusCode: Int? = null) : Exception(message)
class SessionExpiredError(message: String) : ApiError(message, 401)

/** نگهداری کوکی سشن در حافظه (مثل requests.Session تو پایتون) */
private class InMemoryCookieJar : CookieJar {
    private val store = mutableMapOf<String, List<Cookie>>()
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        store[url.host] = cookies
    }
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        return store[url.host] ?: emptyList()
    }
}

class ApiClient(private val context: Context) {
    private val prefs = context.getSharedPreferences("sazgan", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString("server_url", "") ?: ""
        set(value) { prefs.edit().putString("server_url", value.trimEnd('/')).apply() }

    private val client = OkHttpClient.Builder()
        .cookieJar(InMemoryCookieJar())
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private var csrfToken: String? = null

    /** اتصال ساده - چک می‌کنه سرور جوابگوست یا نه */
    suspend fun ping(): Boolean = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/login").get().build()
            val resp = client.newCall(req).execute()
            val ok = resp.code < 500
            resp.close()
            ok
        } catch (e: Exception) {
            false
        }
    }

    /** لاگین با فرم session-cookie - دقیقاً مثل مرورگر و native_client پایتون */
    suspend fun login(username: String, password: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            // warm-up GET برای گرفتن کوکی اولیه
            client.newCall(Request.Builder().url("$baseUrl/login").get().build()).execute().close()

            val form = FormBody.Builder()
                .add("username", username)
                .add("password", password)
                .build()
            val req = Request.Builder().url("$baseUrl/login").post(form).build()
            val resp = client.newCall(req).execute()
            val bodyStr = resp.body?.string() ?: ""
            resp.close()

            // بعد از لاگین موفق، سرور یا ریدایرکت می‌کنه یا صفحه‌ی داشبورد رو برمی‌گردونه
            if (resp.isSuccessful || resp.code in 300..399) {
                fetchCsrfToken()
                Result.success(Unit)
            } else {
                Result.failure(ApiError("نام کاربری یا رمز عبور اشتباه است.", resp.code))
            }
        } catch (e: Exception) {
            Result.failure(ApiError("خطا در اتصال: ${e.message}"))
        }
    }

    private suspend fun fetchCsrfToken() = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/native/csrf-token").get().build()
            val resp = client.newCall(req).execute()
            val body = resp.body?.string() ?: "{}"
            resp.close()
            if (resp.isSuccessful) {
                csrfToken = JSONObject(body).optString("csrf_token", null)
            }
        } catch (_: Exception) { }
    }

    /** GET به یکی از endpoint های /api/native/... و برگردوندن JSONObject */
    suspend fun getJson(path: String): JSONObject = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$baseUrl$path").get().build()
        val resp = client.newCall(req).execute()
        val body = resp.body?.string() ?: "{}"
        resp.close()
        if (resp.code == 401) throw SessionExpiredError("نشست شما منقضی شده. دوباره وارد شوید.")
        if (!resp.isSuccessful) throw ApiError("خطای سرور (${resp.code})", resp.code)
        JSONObject(body)
    }

    /** POST فرم به یکی از endpoint ها (با CSRF token خودکار) */
    suspend fun postForm(path: String, fields: Map<String, String>): JSONObject = withContext(Dispatchers.IO) {
        val builder = FormBody.Builder()
        fields.forEach { (k, v) -> builder.add(k, v) }
        csrfToken?.let { builder.add("csrf_token", it) }
        val req = Request.Builder().url("$baseUrl$path").post(builder.build()).build()
        val resp = client.newCall(req).execute()
        val body = resp.body?.string() ?: "{}"
        resp.close()
        if (resp.code == 401) throw SessionExpiredError("نشست شما منقضی شده. دوباره وارد شوید.")
        JSONObject(body)
    }
}
