package com.sazgan.app;

import android.annotation.SuppressLint;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

/**
 * اپ WebView سازگان با صفحه تنظیمات سرور داخل خود نرم‌افزار.
 * - ذخیره آدرس سرور
 * - اتصال / تلاش مجدد
 * - مخفی بودن نوار آدرس هنگام کار عادی
 */
public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private ProgressBar progressBar;
    private TextView errorView;
    private TextView toolbarTitle;
    private Button retryBtn;
    private Button settingsBtn;
    private LinearLayout errorPanel;
    private LinearLayout settingsPanel;
    private EditText urlInput;
    private String lastUrl = "";

    private static final String PREFS = "sazgan";
    private static final String KEY_URL = "server_url";
    private static final String DEFAULT_URL = "http://192.168.1.1:5000";

    // رنگ‌های سازگان
    private static final int COLOR_NAVY = Color.parseColor("#0c4a6e");
    private static final int COLOR_ACCENT = Color.parseColor("#0284c7");
    private static final int COLOR_BG = Color.parseColor("#f0f9ff");
    private static final int COLOR_TEXT = Color.parseColor("#0f172a");
    private static final int COLOR_MUTED = Color.parseColor("#64748b");
    private static final int COLOR_BORDER = Color.parseColor("#e2e8f0");

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        root.setBackgroundColor(COLOR_BG);

        // ----- نوار بالا -----
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(12), dp(12), dp(12), dp(12));
        toolbar.setBackgroundColor(COLOR_NAVY);

        toolbarTitle = new TextView(this);
        toolbarTitle.setText("سازگان");
        toolbarTitle.setTextColor(Color.WHITE);
        toolbarTitle.setTextSize(18f);
        toolbarTitle.setTypeface(Typeface.DEFAULT_BOLD);
        toolbar.addView(toolbarTitle, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        settingsBtn = new Button(this);
        settingsBtn.setText("⚙ تنظیمات سرور");
        settingsBtn.setTextSize(12f);
        settingsBtn.setAllCaps(false);
        settingsBtn.setTextColor(Color.WHITE);
        GradientDrawable sbBg = new GradientDrawable();
        sbBg.setColor(Color.parseColor("#0369a1"));
        sbBg.setCornerRadius(dp(8));
        settingsBtn.setBackground(sbBg);
        settingsBtn.setPadding(dp(12), dp(8), dp(12), dp(8));
        settingsBtn.setOnClickListener(v -> showSettings(true));
        toolbar.addView(settingsBtn, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        root.addView(toolbar, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setVisibility(View.GONE);
        root.addView(progressBar, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(3)));

        // ----- محتوای اصلی -----
        FrameLayout container = new FrameLayout(this);

        webView = new WebView(this);
        setupWebView();
        container.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        // پنل خطا
        errorPanel = new LinearLayout(this);
        errorPanel.setOrientation(LinearLayout.VERTICAL);
        errorPanel.setGravity(Gravity.CENTER);
        errorPanel.setPadding(dp(32), dp(32), dp(32), dp(32));
        errorPanel.setBackgroundColor(Color.WHITE);
        errorPanel.setVisibility(View.GONE);

        errorView = new TextView(this);
        errorView.setTextSize(15f);
        errorView.setTextColor(COLOR_TEXT);
        errorView.setGravity(Gravity.CENTER);
        errorView.setPadding(0, 0, 0, dp(20));
        errorPanel.addView(errorView);

        LinearLayout errBtns = new LinearLayout(this);
        errBtns.setOrientation(LinearLayout.HORIZONTAL);
        errBtns.setGravity(Gravity.CENTER);

        retryBtn = makePrimaryButton("تلاش مجدد");
        retryBtn.setOnClickListener(v -> {
            hideError();
            if (lastUrl != null && !lastUrl.isEmpty()) {
                webView.loadUrl(lastUrl);
            } else {
                loadUrl(getSavedUrl());
            }
        });
        errBtns.addView(retryBtn);

        Button openSettingsFromError = makeSecondaryButton("تنظیمات سرور");
        openSettingsFromError.setOnClickListener(v -> showSettings(true));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        sp.setMarginStart(dp(8));
        errBtns.addView(openSettingsFromError, sp);

        errorPanel.addView(errBtns);
        container.addView(errorPanel, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        // ----- پنل تنظیمات سرور -----
        settingsPanel = buildSettingsPanel();
        settingsPanel.setVisibility(View.GONE);
        container.addView(settingsPanel, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        root.addView(container, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);

        String saved = getSavedUrl();
        urlInput.setText(saved);
        if (saved != null && !saved.trim().isEmpty()) {
            loadUrl(saved);
        } else {
            showSettings(true);
            toolbarTitle.setText("تنظیمات سرور");
        }
    }

    private LinearLayout buildSettingsPanel() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(20), dp(24), dp(20), dp(24));
        panel.setBackgroundColor(Color.WHITE);
        panel.setGravity(Gravity.TOP | Gravity.CENTER_HORIZONTAL);

        TextView title = new TextView(this);
        title.setText("تنظیمات سرور");
        title.setTextSize(20f);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(COLOR_TEXT);
        title.setGravity(Gravity.CENTER);
        panel.addView(title);

        TextView hint = new TextView(this);
        hint.setText("آدرس کامل سرور سازگان را وارد کنید.\nمثال:\nhttp://192.168.1.10:5000\nhttps://sazgan.example.com");
        hint.setTextSize(13f);
        hint.setTextColor(COLOR_MUTED);
        hint.setGravity(Gravity.CENTER);
        hint.setPadding(0, dp(12), 0, dp(20));
        panel.addView(hint);

        TextView label = new TextView(this);
        label.setText("آدرس سرور");
        label.setTextSize(13f);
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setTextColor(COLOR_TEXT);
        label.setPadding(0, 0, 0, dp(6));
        panel.addView(label);

        urlInput = new EditText(this);
        urlInput.setHint("http://IP:PORT یا https://دامنه");
        urlInput.setSingleLine(true);
        urlInput.setTextSize(15f);
        urlInput.setPadding(dp(14), dp(14), dp(14), dp(14));
        urlInput.setTextColor(COLOR_TEXT);
        urlInput.setHintTextColor(COLOR_MUTED);
        urlInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        GradientDrawable inputBg = new GradientDrawable();
        inputBg.setColor(COLOR_BG);
        inputBg.setCornerRadius(dp(10));
        inputBg.setStroke(dp(1), COLOR_BORDER);
        urlInput.setBackground(inputBg);
        urlInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                saveAndConnect();
                return true;
            }
            return false;
        });
        panel.addView(urlInput, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        TextView tips = new TextView(this);
        tips.setText("• موبایل و سرور باید در یک شبکه باشند (Wi‑Fi)\n• برای شبکه داخلی معمولاً http کافی است\n• پورت پیش‌فرض برنامه را مطابق سرور تنظیم کنید");
        tips.setTextSize(12.5f);
        tips.setTextColor(COLOR_MUTED);
        tips.setPadding(0, dp(16), 0, dp(20));
        tips.setLineSpacing(dp(2), 1f);
        panel.addView(tips);

        Button saveConnect = makePrimaryButton("ذخیره و اتصال");
        saveConnect.setOnClickListener(v -> saveAndConnect());
        LinearLayout.LayoutParams full = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        full.bottomMargin = dp(10);
        panel.addView(saveConnect, full);

        Button justSave = makeSecondaryButton("فقط ذخیره");
        justSave.setOnClickListener(v -> {
            String u = normalizeUrl(urlInput.getText().toString());
            if (!isAllowedUrl(Uri.parse(u))) {
                Toast.makeText(this, "آدرس نامعتبر است", Toast.LENGTH_SHORT).show();
                return;
            }
            saveUrl(u);
            Toast.makeText(this, "ذخیره شد", Toast.LENGTH_SHORT).show();
            hideKeyboard();
        });
        panel.addView(justSave, full);

        Button closeBtn = makeSecondaryButton("بستن تنظیمات");
        closeBtn.setOnClickListener(v -> {
            showSettings(false);
            hideKeyboard();
        });
        panel.addView(closeBtn, full);

        TextView current = new TextView(this);
        current.setId(View.generateViewId());
        current.setText("آدرس فعلی: " + getSavedUrl());
        current.setTextSize(12f);
        current.setTextColor(COLOR_MUTED);
        current.setPadding(0, dp(16), 0, 0);
        current.setTag("current_url_label");
        panel.addView(current);

        // wrap in outer linear for FrameLayout
        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        outer.setBackgroundColor(Color.WHITE);
        scroll.addView(panel);
        outer.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT));
        return outer;
    }

    private void saveAndConnect() {
        String u = normalizeUrl(urlInput.getText().toString());
        if (!isAllowedUrl(Uri.parse(u))) {
            Toast.makeText(this, "آدرس سرور نامعتبر است. با http:// یا https:// شروع شود.", Toast.LENGTH_LONG).show();
            return;
        }
        saveUrl(u);
        hideKeyboard();
        showSettings(false);
        hideError();
        loadUrl(u);
        Toast.makeText(this, "در حال اتصال...", Toast.LENGTH_SHORT).show();
    }

    private void showSettings(boolean show) {
        if (settingsPanel != null) {
            settingsPanel.setVisibility(show ? View.VISIBLE : View.GONE);
        }
        if (show) {
            urlInput.setText(getSavedUrl());
            toolbarTitle.setText("تنظیمات سرور");
            // refresh current label
            refreshCurrentLabel();
        } else {
            toolbarTitle.setText("سازگان");
        }
    }

    private void refreshCurrentLabel() {
        if (settingsPanel == null) return;
        View v = settingsPanel.findViewWithTag("current_url_label");
        if (v instanceof TextView) {
            ((TextView) v).setText("آدرس فعلی: " + getSavedUrl());
        }
    }

    private String getSavedUrl() {
        return getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_URL, DEFAULT_URL);
    }

    private void saveUrl(String url) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_URL, url).apply();
        refreshCurrentLabel();
    }

    private void loadUrl(String raw) {
        String url = normalizeUrl(raw);
        if (!isAllowedUrl(Uri.parse(url))) {
            showError("آدرس سرور نامعتبر است.\nاز دکمه «تنظیمات سرور» آدرس صحیح را وارد کنید.");
            return;
        }
        lastUrl = url;
        hideError();
        webView.loadUrl(url);
    }

    private String normalizeUrl(String raw) {
        if (raw == null) return "";
        String u = raw.trim();
        if (u.isEmpty()) return "";
        if (!u.startsWith("http://") && !u.startsWith("https://")) {
            u = "http://" + u;
        }
        // remove trailing spaces
        while (u.endsWith("/")) {
            // keep single structure - actually trailing slash is fine for web apps
            break;
        }
        return u;
    }

    private boolean isAllowedUrl(Uri uri) {
        if (uri == null) return false;
        String scheme = uri.getScheme();
        return "http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        try {
            s.setMediaPlaybackRequiresUserGesture(true);
        } catch (Exception ignored) {
        }

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress >= 100) {
                    progressBar.setVisibility(View.GONE);
                } else {
                    progressBar.setVisibility(View.VISIBLE);
                    progressBar.setProgress(newProgress);
                }
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!isAllowedUrl(uri)) {
                    Toast.makeText(MainActivity.this, "آدرس غیرمجاز مسدود شد", Toast.LENGTH_SHORT).show();
                    return true;
                }
                return false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request != null && request.isForMainFrame()) {
                    String desc = "خطای شبکه";
                    try {
                        if (error != null && error.getDescription() != null) {
                            desc = error.getDescription().toString();
                        }
                    } catch (Exception ignored) {
                    }
                    showError("اتصال برقرار نشد.\n" + desc + "\n\nآدرس سرور و شبکه Wi‑Fi را بررسی کنید.");
                }
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
                if (request != null && request.isForMainFrame() && errorResponse != null) {
                    int code = errorResponse.getStatusCode();
                    if (code >= 400) {
                        showError("خطای سرور (کد " + code + ").\nآدرس سرور را در تنظیمات بررسی کنید.");
                    }
                }
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, android.net.http.SslError error) {
                showError("خطای گواهی SSL.\nبرای شبکه داخلی می‌توانید از http:// استفاده کنید یا گواهی معتبر نصب کنید.");
                if (handler != null) {
                    handler.cancel();
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                hideError();
                if (url != null && !url.startsWith("about:")) {
                    lastUrl = url;
                }
            }
        });
    }

    private void showError(String msg) {
        errorView.setText(msg);
        errorPanel.setVisibility(View.VISIBLE);
        webView.setVisibility(View.INVISIBLE);
    }

    private void hideError() {
        errorPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
    }

    private Button makePrimaryButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(14f);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(COLOR_ACCENT);
        bg.setCornerRadius(dp(10));
        b.setBackground(bg);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        return b;
    }

    private Button makeSecondaryButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextColor(COLOR_NAVY);
        b.setTextSize(14f);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(10));
        bg.setStroke(dp(1), COLOR_BORDER);
        b.setBackground(bg);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        return b;
    }

    private void hideKeyboard() {
        try {
            InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            View focus = getCurrentFocus();
            if (imm != null && focus != null) {
                imm.hideSoftInputFromWindow(focus.getWindowToken(), 0);
            }
        } catch (Exception ignored) {
        }
    }

    private int dp(int v) {
        float d = getResources().getDisplayMetrics().density;
        return Math.round(v * d);
    }

    @Override
    public void onBackPressed() {
        if (settingsPanel != null && settingsPanel.getVisibility() == View.VISIBLE) {
            showSettings(false);
            return;
        }
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        try {
            if (webView != null) {
                webView.stopLoading();
                webView.loadUrl("about:blank");
                webView.clearHistory();
                webView.removeAllViews();
                webView.destroy();
                webView = null;
            }
        } catch (Exception ignored) {
        }
        super.onDestroy();
    }
}
