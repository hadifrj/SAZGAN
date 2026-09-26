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

open class ApiError(message: String, val statusCode: Int? = null) : Exception(message)
class SessionExpiredError(message: String) : ApiError(message, 401)

private class InMemoryCookieJar : CookieJar {
    private val store = mutableMapOf<String, List<Cookie>>()
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        store[url.host] = cookies
    }
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        return store[url.host] ?: emptyList()
    }

    suspend fun logout() = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/logout").get().build()
            client.newCall(req).execute().close()
        } catch (_: Exception) { }
        csrfToken = null
    }
}

object ApiClient {
    private lateinit var appContext: Context
    private lateinit var prefs: android.content.SharedPreferences

    fun init(context: Context) {
        if (!::appContext.isInitialized) {
            appContext = context.applicationContext
            prefs = appContext.getSharedPreferences("sazgan", Context.MODE_PRIVATE)
        }
    }

    var baseUrl: String
        get() = prefs.getString("server_url", "") ?: ""
        set(value) { prefs.edit().putString("server_url", value.trimEnd('/')).apply() }

    private val client = OkHttpClient.Builder()
        .cookieJar(InMemoryCookieJar())
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private var csrfToken: String? = null

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

    /**
     * قبل از لاگین، از /api/native/login-info یک csrf_token معتبر برای این
     * session می‌گیریم (سرور آن را روی همین کوکی سشن ذخیره می‌کند) و همان
     * توکن را در فرم لاگین می‌فرستیم - چون routes/auth.py:login() این
     * بررسی را جدا و همیشه (حتی خارج از معافیت عمومی CSRF مسیر /login)
     * انجام می‌دهد.
     */
    private suspend fun fetchLoginCsrfToken(): String? = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/native/login-info").get().build()
            val resp = client.newCall(req).execute()
            val body = resp.body?.string() ?: "{}"
            resp.close()
            if (resp.isSuccessful) JSONObject(body).optString("csrf_token", null) else null
        } catch (_: Exception) {
            null
        }
    }

    suspend fun login(username: String, password: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val loginCsrf = fetchLoginCsrfToken()
                ?: return@withContext Result.failure(ApiError("اتصال به سرور برای شروع ورود ناموفق بود."))

            val formBuilder = FormBody.Builder()
                .add("username", username)
                .add("password", password)
                .add("csrf_token", loginCsrf)
            val req = Request.Builder().url("$baseUrl/login").post(formBuilder.build()).build()
            val resp = client.newCall(req).execute()
            resp.body?.string()
            val code = resp.code
            resp.close()

            if (code in 200..399) {
                fetchCsrfToken()
                Result.success(Unit)
            } else {
                Result.failure(ApiError("نام کاربری یا رمز عبور اشتباه است.", code))
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

    suspend fun getJson(path: String): JSONObject = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$baseUrl$path").get().build()
        val resp = client.newCall(req).execute()
        val body = resp.body?.string() ?: "{}"
        resp.close()
        if (resp.code == 401) throw SessionExpiredError("نشست شما منقضی شده. دوباره وارد شوید.")
        if (!resp.isSuccessful) throw ApiError("خطای سرور (${resp.code})", resp.code)
        JSONObject(body)
    }

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

    suspend fun logout() = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/logout").get().build()
            client.newCall(req).execute().close()
        } catch (_: Exception) { }
        csrfToken = null
    }
}
