# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QDialog, QMessageBox, QToolButton, QGridLayout, QFrame, QGraphicsDropShadowEffect, QMenu,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from api_client import SazganClient
from native_icons import icon
from theme import app_icon
from config import load_config, save_config, normalize_url, get_server_url


def _install_minimal_context_menu(edit: QLineEdit):
    """Replace Qt's default right-click menu (Undo/Redo/Cut/Copy/Paste/Delete/
    Select All, each with a keyboard-shortcut hint) with a short one that only
    has Cut/Copy/Paste/Select All and no shortcut text."""
    edit.setContextMenuPolicy(Qt.CustomContextMenu)

    def show_menu(pos):
        menu = QMenu(edit)
        menu.setLayoutDirection(Qt.RightToLeft)

        cut_action = menu.addAction("برش")
        cut_action.setEnabled(edit.hasSelectedText() and not edit.isReadOnly())
        cut_action.triggered.connect(edit.cut)

        copy_action = menu.addAction("کپی")
        copy_action.setEnabled(edit.hasSelectedText())
        copy_action.triggered.connect(edit.copy)

        paste_action = menu.addAction("چسباندن")
        paste_action.setEnabled(not edit.isReadOnly())
        paste_action.triggered.connect(edit.paste)

        menu.addSeparator()

        select_all_action = menu.addAction("انتخاب همه")
        select_all_action.setEnabled(bool(edit.text()))
        select_all_action.triggered.connect(edit.selectAll)

        menu.exec_(edit.mapToGlobal(pos))

    edit.customContextMenuRequested.connect(show_menu)


class ServerSettingsDialog(QDialog):
    """Connection settings kept separate from the normal login form.

    The web login never needs this (its URL is fixed by whatever address the
    browser is pointed at); the native app can be pointed at any Sazgan
    server, so this is the one login-screen control the native app has that
    the web login intentionally doesn't.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنظیمات اتصال به سرور")
        self.setFixedSize(500, 230)
        self.setLayoutDirection(Qt.RightToLeft)

        cfg = load_config()
        self.url_edit = QLineEdit(cfg.get("url", ""))
        self.url_edit.setObjectName("loginField")
        self.url_edit.setPlaceholderText("مثلاً: 192.168.1.39:5000")
        self.url_edit.setClearButtonEnabled(True)
        _install_minimal_context_menu(self.url_edit)

        hint = QLabel("آدرس سرور در این رایانه ذخیره می‌شود و در ورودهای بعدی دوباره لازم نیست وارد شود.")
        hint.setWordWrap(True)
        hint.setObjectName("pageSubtitle")

        label = QLabel("آدرس سرور")
        label.setObjectName("sectionTitle")

        save_btn = QPushButton("ذخیره")
        cancel_btn = QPushButton("انصراف")
        cancel_btn.setProperty("variant", "secondary")
        save_btn.clicked.connect(self.accept_settings)
        cancel_btn.clicked.connect(self.reject)
        self.url_edit.returnPressed.connect(self.accept_settings)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)
        root.addWidget(hint)
        root.addWidget(label)
        root.addWidget(self.url_edit)
        root.addLayout(buttons)

    def accept_settings(self):
        url = normalize_url(self.url_edit.text())
        if not url:
            QMessageBox.warning(self, "تنظیمات اتصال", "آدرس سرور را وارد کنید.")
            self.url_edit.setFocus()
            return
        save_config({"url": url})
        self.accept()


class LoginWindow(QWidget):
    """Native login screen, styled to match the web login (MY SAZGAN brand
    card, blue primary button, collapsible support panel). Server address
    is configured separately via ServerSettingsDialog since (unlike the
    web login) the native app isn't pointed at a fixed address."""
    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.setWindowTitle("ورود به سازگان")
        self.setWindowIcon(app_icon())
        self.setObjectName("loginRoot")
        self.setFixedSize(560, 640)
        self.setLayoutDirection(Qt.RightToLeft)

        # ---- Card (mirrors the web login-box) ----
        card = QFrame(self)
        card.setObjectName("loginCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        brand_name = QLabel("MY SAZGAN")
        brand_name.setObjectName("brandNameBig")
        brand_name.setAlignment(Qt.AlignCenter)
        brand_sub = QLabel("سامانه خدمات پس از فروش")
        brand_sub.setObjectName("brandSubBig")
        brand_sub.setAlignment(Qt.AlignCenter)

        cfg = load_config()
        self.user_edit = QLineEdit(cfg.get("username", ""))
        self.user_edit.setObjectName("loginField")
        self.user_edit.setPlaceholderText("نام کاربری")
        self.user_edit.setMinimumHeight(42)
        _install_minimal_context_menu(self.user_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setObjectName("loginField")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("رمز عبور")
        self.pass_edit.setMinimumHeight(42)
        _install_minimal_context_menu(self.pass_edit)

        # Password visibility toggle: a real SVG icon inside the field.
        self.password_toggle = QToolButton(self.pass_edit)
        self.password_toggle.setObjectName("passwordToggle")
        self.password_toggle.setIcon(icon("eye_off", 19))
        self.password_toggle.setCheckable(True)
        self.password_toggle.setCursor(Qt.PointingHandCursor)
        self.password_toggle.setToolTip("نمایش رمز عبور")
        self.password_toggle.setFixedSize(38, 34)
        self.password_toggle.clicked.connect(self._toggle_password)
        self._position_password_toggle()

        user_label = QLabel("نام کاربری")
        user_label.setObjectName("loginLabel")
        pass_label = QLabel("رمز عبور")
        pass_label.setObjectName("loginLabel")

        # Stacked label + field rows avoid QFormLayout geometry compression and
        # make the Login layout stable even with Persian font metrics.
        form = QGridLayout()
        form.setContentsMargins(0, 8, 0, 4)
        form.setVerticalSpacing(7)
        form.setHorizontalSpacing(0)
        form.addWidget(user_label, 0, 0)
        form.addWidget(self.user_edit, 1, 0)
        form.addWidget(pass_label, 2, 0)
        form.addWidget(self.pass_edit, 3, 0)

        self.status_label = QLabel("")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(30)
        self.status_label.setAlignment(Qt.AlignCenter)

        self.login_btn = QPushButton("ورود")
        self.login_btn.setObjectName("loginPrimaryBtn")
        self.login_btn.setMinimumHeight(46)
        self.login_btn.clicked.connect(self.try_login)
        self.pass_edit.returnPressed.connect(self.try_login)

        settings_btn = QPushButton("تنظیمات اتصال")
        settings_btn.setProperty("variant", "secondary")
        settings_btn.setMinimumHeight(40)
        settings_btn.clicked.connect(self.open_server_settings)

        # ---- Support panel (mirrors the web login's collapsible panel) ----
        self.support_toggle = QPushButton("تماس با پشتیبانی ▾")
        self.support_toggle.setObjectName("supportToggle")
        self.support_toggle.setCursor(Qt.PointingHandCursor)
        self.support_toggle.setCheckable(True)
        self.support_toggle.clicked.connect(self._toggle_support)

        self.support_panel = QFrame()
        self.support_panel.setObjectName("supportPanel")
        self.support_panel.setVisible(False)
        self._support_layout = QVBoxLayout(self.support_panel)
        self._support_layout.setContentsMargins(14, 12, 14, 12)
        self._support_layout.setSpacing(4)
        self._support_placeholder = QLabel("در حال دریافت اطلاعات پشتیبانی...")
        self._support_placeholder.setObjectName("pageSubtitle")
        self._support_placeholder.setWordWrap(True)
        self._support_layout.addWidget(self._support_placeholder)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(42, 34, 42, 28)
        card_layout.setSpacing(6)
        card_layout.addWidget(brand_name)
        card_layout.addWidget(brand_sub)
        card_layout.addSpacing(16)
        card_layout.addLayout(form)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.login_btn)
        card_layout.addWidget(settings_btn)
        card_layout.addWidget(self.support_toggle)
        card_layout.addWidget(self.support_panel)
        card_layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(card)

        # Do not show the server/IP anywhere on the login screen.
        server_url = get_server_url()
        if not server_url:
            self._set_status("ابتدا آدرس سرور را از «تنظیمات اتصال» وارد کنید.", "warning")
            self.login_btn.setEnabled(False)
        else:
            self.user_edit.setFocus()

        QTimer.singleShot(150, self._load_support_info)

    def _position_password_toggle(self):
        if not hasattr(self, "password_toggle"):
            return
        # In RTL the trailing side of the field is the left side visually.
        x = 5 if self.layoutDirection() == Qt.RightToLeft else self.pass_edit.width() - self.password_toggle.width() - 5
        self.password_toggle.move(x, (self.pass_edit.height() - self.password_toggle.height()) // 2)
        self.password_toggle.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_password_toggle()

    def _toggle_password(self, checked):
        self.pass_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.password_toggle.setIcon(icon("eye", 19) if checked else icon("eye_off", 19))
        self.password_toggle.setToolTip("پنهان کردن رمز عبور" if checked else "نمایش رمز عبور")

    def _toggle_support(self, checked):
        self.support_panel.setVisible(checked)
        self.support_toggle.setText("تماس با پشتیبانی ▴" if checked else "تماس با پشتیبانی ▾")

    def _load_support_info(self):
        url = get_server_url()
        if not url:
            return
        try:
            client = SazganClient(url)
            info = client.login_info(timeout=4)
        except Exception:
            info = {}
        self._populate_support_info(info or {})

    def _populate_support_info(self, info):
        while self._support_layout.count():
            item = self._support_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        company = info.get("company_name") or ""
        mobile = info.get("company_mobile") or ""
        phone = info.get("company_phone") or ""
        address = info.get("company_address") or ""

        def add_row(label, value):
            row = QLabel(f"{label} {value}".strip())
            row.setWordWrap(True)
            row.setObjectName("pageSubtitle")
            self._support_layout.addWidget(row)

        if company:
            add_row("شرکت:", company)
        if mobile:
            add_row("موبایل:", mobile)
        if phone:
            add_row("تلفن:", phone)
        if address:
            add_row("آدرس:", address)
        if not (company or mobile or phone or address):
            add_row("", "اطلاعات پشتیبانی هنوز در تنظیمات شرکت ثبت نشده است.")

    def open_server_settings(self):
        dlg = ServerSettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            url = get_server_url()
            self.login_btn.setEnabled(bool(url))
            self._set_status("آدرس سرور ذخیره شد.", "info")
            self.user_edit.setFocus()
            QTimer.singleShot(150, self._load_support_info)

    def try_login(self):
        url = get_server_url()
        username = self.user_edit.text().strip()
        password = self.pass_edit.text()

        if not url:
            self.open_server_settings()
            return
        if not username or not password:
            self._set_status("نام کاربری و رمز عبور را وارد کنید.", "error")
            return

        self._set_status("در حال ورود...", "info")
        self.login_btn.setEnabled(False)
        self.setEnabled(False)
        try:
            client = SazganClient(url)
            ok, err = client.login(username, password)
            if ok:
                try:
                    me = client.native_me()
                    if not isinstance(me, dict) or not me.get("username"):
                        ok = False
                        err = "ورود انجام شد اما نشست کاربری تأیید نشد."
                except Exception:
                    ok = False
                    err = "ورود انجام شد اما ارتباط نشست کاربری تأیید نشد."
        except Exception:
            ok = False
            err = "ورود ناموفق بود. اطلاعات ورود و اتصال به سرور را بررسی کنید."
        finally:
            self.setEnabled(True)
            self.login_btn.setEnabled(True)

        if not ok:
            allowed = {
                "نام کاربری یا رمز عبور نادرست است.",
                "ارتباط با سرور برقرار نشد. آدرس سرور و روشن بودن سرویس سازگان را بررسی کنید.",
                "پاسخ سرور بیش از حد طول کشید. لطفاً دوباره تلاش کنید.",
                "ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
            }
            message = err if err in allowed else "ورود ناموفق بود. اطلاعات ورود و اتصال به سرور را بررسی کنید."
            self._set_status(message, "error")
            return

        save_config({"url": url, "username": username})
        try:
            self.on_success(client)
            self.close()
        except Exception as exc:
            self._set_status(
                f"ورود موفق بود اما پنجره اصلی سازگان باز نشد. لطفاً برنامه را دوباره اجرا کنید.\n\n{exc}",
                "error",
            )

    def _set_status(self, text, kind="info"):
        if kind == "error":
            # Errors are shown as a dialog the user opens and closes, not a
            # red banner that sits on the page indefinitely.
            self.status_label.setText("")
            self.status_label.setStyleSheet("")
            QMessageBox.critical(self, "خطای ورود", text)
            return
        self.status_label.setText(text)
        if kind == "warning":
            self.status_label.setStyleSheet("color:#b45309;")
        else:
            self.status_label.setStyleSheet("color:#334155;")
