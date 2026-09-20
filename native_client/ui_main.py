# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
    QToolButton, QButtonGroup, QSizePolicy, QMenu, QAction, QDialog, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QApplication, QFormLayout, QLineEdit, QGroupBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QEvent, QTimer
import webbrowser
import re
from api_client import ApiError, SessionExpiredError
from ui_common import busy, show_empty
from native_icons import icon
from theme import app_icon
from ui_home import HomePage
from ui_warehouse import WarehousePage
from ui_data_hub import DataHubPage
from ui_finance import FinancePage
from ui_reports import ReportsPage
from ui_improvements import ImprovementsPage
from ui_support import SupportPage
from ui_service import ServicePage
from ui_settings import SettingsPage
from ui_customers import CustomersPage
from ui_customer_affairs import ContactsPage, AnnouncementsPage, SurveysPage
from ui_hubs import HubPage
from ui_service_detail import (
    InternalRepairDetailDialog, ExternalRepairDetailDialog,
    InstallationRequestDetailDialog, InstallationRegisterDetailDialog,
    InspectionDetailDialog,
)

WEB_SIDEBAR_ITEMS = [
    {"key":"cartable","name":"کارتابل","tip":"صفحه اصلی کارتابل","permission":None,"roles":None,"index":0},
    {"key":"search","name":"جستجو","tip":"جستجوی مشتریان، درخواست‌ها و سریال","permission":None,"roles":None,"index":1},
    {"key":"chat","name":"گفتگوی مشتری","tip":"گفتگوی مشتری","permission":None,"roles":None,"index":2},
    {"key":"notifications","name":"اعلان‌ها","tip":"اعلان‌ها","permission":None,"roles":None,"index":3},
    {"key":"customer","name":"امور مشتریان","tip":"مرکز امور مشتریان","permission":"customer_affairs","roles":None,"index":4},
    {"key":"tasks","name":"وظایف من","tip":"وظایف و کارهای اختصاص‌یافته","permission":None,"roles":["تکنسین کارخانه","تکنسین استانی","کنترل کیفیت"],"index":5},
    {"key":"warehouse","name":"رهگیری قطعات","tip":"رهگیری قطعات و انبار","permission":"warehouse","roles":None,"index":6},
    {"key":"finance","name":"امور مالی","tip":"امور مالی و دستمزد","permission":"finance","roles":None,"index":7},
    {"key":"reports","name":"گزارش‌ها","tip":"گزارش‌ها و داشبورد مدیریتی","permission":"reports_or_dashboard","roles":None,"index":8},
    {"key":"settings","name":"تنظیمات","tip":"تنظیمات سیستم","permission":"settings","roles":None,"index":9},
]


# Native-only screens remain available from the secondary tools area so the
# primary navigation is visually and structurally identical to the web app.
NATIVE_TOOL_ITEMS = [
    ("warranty", "استعلام گارانتی"),
    ("datahub", "هاب داده (Import/Export)"),
    ("improvements", "گزارش دستمزد و مدیریت"),
]



class WarrantyLookupPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        title = QLabel("استعلام گارانتی")
        title.setObjectName("pageTitle")
        sub = QLabel("شماره سریال دستگاه را وارد کنید تا وضعیت گارانتی نمایش داده شود.")
        sub.setObjectName("pageSubtitle")
        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("شماره سریال دستگاه")
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.do_search)
        self.serial_edit.returnPressed.connect(self.do_search)
        self.result_label = QLabel("نتیجه‌ای وجود ندارد.")
        self.result_label.setObjectName("resultCard")
        self.result_label.setWordWrap(True)
        form = QHBoxLayout()
        form.addWidget(self.serial_edit, 1)
        form.addWidget(self.search_btn)
        result = QFrame(); result.setObjectName("card")
        rl = QVBoxLayout(result); rl.setContentsMargins(16, 16, 16, 16); rl.addWidget(self.result_label)
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 22, 24, 28); layout.setSpacing(12)
        layout.addWidget(title); layout.addWidget(sub); layout.addLayout(form); layout.addWidget(result); layout.addStretch()

    def do_search(self):
        serial = self.serial_edit.text().strip()
        if not serial: return
        try: data = self.client.lookup_warranty(serial)
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e:
            self.result_label.setText(str(e)); return
        if not data.get("found"):
            self.result_label.setText("سریالی با این شماره پیدا نشد."); return
        lines = [
            f"مشتری: {data.get('customer_name','')}",
            f"دستگاه: {data.get('device_type','')} - {data.get('model','')}",
            f"تاریخ نصب: {data.get('installation_date','')}",
            f"پایان گارانتی: {data.get('warranty_end_date','')}",
            f"وضعیت گارانتی: {data.get('warranty_status','')}",
        ]
        self.result_label.setText("\n".join(lines))



class SearchPage(QWidget):
    """Native global search backed by the same request search data as the web app."""
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        title = QLabel("جستجوی سراسری")
        title.setObjectName("pageTitle")
        sub = QLabel("جستجو در مشتریان، درخواست‌ها، دستگاه‌ها و سایر اطلاعات ثبت‌شده")
        sub.setObjectName("pageSubtitle")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("نام مشتری، سریال، شماره پذیرش، شماره پیگیری...")
        self.edit.setMinimumHeight(40)
        btn = QPushButton("جستجو")
        btn.setMinimumHeight(40)
        self.search_btn = btn
        btn.clicked.connect(self.search)
        self.edit.returnPressed.connect(self.search)
        form = QHBoxLayout(); form.addWidget(self.edit, 1); form.addWidget(btn)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["نوع", "عنوان", "جزئیات", "وضعیت"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.open_selected)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,22,24,28); layout.setSpacing(12)
        layout.addWidget(title); layout.addWidget(sub); layout.addLayout(form); layout.addWidget(self.table,1)

    def open_selected(self, row, _col):
        item=self.table.item(row,0)
        if not item:return
        data=item.data(Qt.UserRole)
        if not data:return
        url=data.get('url') if isinstance(data,dict) else ''
        if not url:
            return

        # Prefer the real Native Detail for service records. Only unsupported
        # destinations fall back to the browser, which keeps global search
        # aligned with the final workflow rule.
        path = str(url).split('?', 1)[0]
        req_id = None
        m = re.search(r'/([0-9]+)(?:/)?$', path)
        if m:
            req_id = int(m.group(1))
        dlg_cls = None
        if '/service/internal-repair/' in path:
            dlg_cls = InternalRepairDetailDialog
        elif '/service/external-repair/' in path:
            dlg_cls = ExternalRepairDetailDialog
        elif '/service/installation/request-' in path:
            dlg_cls = InstallationRequestDetailDialog
        elif '/service/installation/register-' in path:
            dlg_cls = InstallationRegisterDetailDialog
        elif '/service/inspection/' in path:
            dlg_cls = InspectionDetailDialog

        if dlg_cls and req_id:
            try:
                dlg_cls(self.client, req_id, parent=self).exec_()
                return
            except Exception as exc:
                QMessageBox.warning(self, "جزئیات", f"باز کردن جزئیات Native ممکن نشد: {exc}")

        webbrowser.open(self.client.base_url + path if path.startswith('/') else path)

    def search(self):
        q = self.edit.text().strip()
        if not q:
            self.table.setRowCount(0); return
        try:
            with busy(button=self.search_btn):
                data = self.client.global_search(q)
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e:
            QMessageBox.warning(self, "جستجو", str(e)); return
        rows = data.get("results") or []
        if not rows:
            show_empty(self.table)
            return
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            meta = r.get("meta") or []
            meta_text = " | ".join(f"{a}: {b}" for a,b in meta) if isinstance(meta, list) else str(meta)
            vals = [r.get("type_label") or r.get("type") or "-", r.get("title") or "-", meta_text or r.get("subtitle") or "-", r.get("status") or "-"]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
            self.table.item(i,0).setData(Qt.UserRole, r)


class NotificationsPage(QWidget):
    """Native notifications screen backed by the real notifications table/API."""
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        title = QLabel("اعلان‌های من"); title.setObjectName("pageTitle")
        self.count_label = QLabel("")
        self.read_all_btn = QPushButton("خواندن همه")
        self.read_all_btn.clicked.connect(self.read_all)
        head = QHBoxLayout(); head.addWidget(title); head.addStretch(); head.addWidget(self.count_label); head.addWidget(self.read_all_btn)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["زمان", "عنوان", "شرح", "وضعیت"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.mark_selected)
        layout=QVBoxLayout(self); layout.setContentsMargins(24,22,24,28); layout.setSpacing(12); layout.addLayout(head); layout.addWidget(self.table,1)

    def reload(self):
        try: data=self.client.native_notifications()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e: self.count_label.setText(str(e)); return
        rows=data.get("rows") or []; unread=int(data.get("unread_count") or 0)
        self.count_label.setText(f"خوانده‌نشده: {unread}")
        if not rows:
            show_empty(self.table, "اعلانی برای نمایش وجود ندارد.")
            return
        self.table.setRowCount(len(rows))
        for i,n in enumerate(rows):
            vals=[n.get("created_at") or "-", n.get("title") or "-", n.get("body") or "-", "خوانده نشده" if not n.get("is_read") else "خوانده شده"]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
            self.table.item(i,0).setData(Qt.UserRole, n.get("id"))
            self.table.item(i,0).setData(Qt.UserRole+1, n.get("url") or "")

    def mark_selected(self, row, _col):
        item=self.table.item(row,0)
        if not item: return
        nid=item.data(Qt.UserRole)
        if not nid: return
        try: self.client.mark_notification_read(int(nid))
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e: QMessageBox.warning(self,"اعلان",str(e)); return
        url=item.data(Qt.UserRole+1)
        if url: webbrowser.open(self.client.base_url + url if str(url).startswith("/") else str(url))
        self.reload()

    def read_all(self):
        try:
            with busy(button=self.read_all_btn):
                self.client.mark_all_notifications_read()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e: QMessageBox.warning(self,"اعلان",str(e)); return
        self.reload()


class AccountPage(QWidget):
    """پروفایل Native + تغییر نام نمایشی و رمز عبور با API واقعی."""
    def __init__(self, client):
        super().__init__(); self.client=client; self.setObjectName('page'); self.setLayoutDirection(Qt.RightToLeft)
        self.title=QLabel('حساب کاربری'); self.title.setObjectName('pageTitle')
        self.profile=QFrame(); self.profile.setObjectName('card'); pf=QFormLayout(self.profile)
        self.name=QLineEdit(); self.username=QLineEdit(); self.username.setReadOnly(True); self.role=QLineEdit(); self.role.setReadOnly(True); self.province=QLineEdit(); self.province.setReadOnly(True); self.bank_card=QLineEdit(); self.bank_sheba=QLineEdit(); self.bank_owner=QLineEdit()
        pf.addRow('نام نمایشی:',self.name); pf.addRow('نام کاربری:',self.username); pf.addRow('سمت:',self.role); pf.addRow('استان:',self.province); pf.addRow('کارت بانکی:',self.bank_card); pf.addRow('شماره شبا:',self.bank_sheba); pf.addRow('صاحب حساب:',self.bank_owner)
        self.save_profile=QPushButton('ذخیره پروفایل'); self.save_profile.clicked.connect(self.save)
        pf.addRow('',self.save_profile)
        self.password=QFrame(); self.password.setObjectName('card'); qf=QFormLayout(self.password)
        self.current=QLineEdit(); self.current.setEchoMode(QLineEdit.Password); self.new=QLineEdit(); self.new.setEchoMode(QLineEdit.Password); self.new2=QLineEdit(); self.new2.setEchoMode(QLineEdit.Password)
        qf.addRow('رمز فعلی:',self.current); qf.addRow('رمز جدید:',self.new); qf.addRow('تکرار رمز:',self.new2); self.pass_btn=QPushButton('تغییر رمز'); self.pass_btn.clicked.connect(self.change_password); qf.addRow('',self.pass_btn)
        self.status=QLabel(''); self.status.setWordWrap(True)
        lay=QVBoxLayout(self); lay.setContentsMargins(24,22,24,28); lay.setSpacing(12); lay.addWidget(self.title); lay.addWidget(self.profile); lay.addWidget(self.password); lay.addWidget(self.status); lay.addStretch()
    def reload(self):
        try:d=self.client.account_profile().get('data',{})
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e:self.status.setText(str(e)); return
        self.name.setText(str(d.get('full_name') or '')); self.username.setText(str(d.get('username') or '')); self.role.setText(str(d.get('role') or '')); self.province.setText(str(d.get('province') or '')); self.bank_card.setText(str(d.get('bank_card') or '')); self.bank_sheba.setText(str(d.get('bank_sheba') or '')); self.bank_owner.setText(str(d.get('bank_owner') or ''))
    def save(self):
        try:self.client.account_profile_save({'full_name':self.name.text().strip(), 'bank_card':self.bank_card.text().strip(), 'bank_sheba':self.bank_sheba.text().strip(), 'bank_owner':self.bank_owner.text().strip()}); self.status.setText('پروفایل ذخیره شد.')
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e:self.status.setText(f'خطا: {e}')
    def change_password(self):
        try:self.client.account_password_change({'current_password':self.current.text(),'new_password':self.new.text(),'new_password2':self.new2.text()}); self.status.setText('رمز عبور با موفقیت تغییر کرد.'); self.current.clear(); self.new.clear(); self.new2.clear()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError as e:self.status.setText(f'خطا: {e}')


class HeaderBar(QFrame):
    """Native header matched to the web header.

    Physical order is intentionally LTR so the user/icon cluster stays on
    the left edge, while individual text widgets remain RTL. The account
    dropdown (profile / settings / logout) opens from the avatar button.
    """
    accountRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    logoutRequested = pyqtSignal()
    searchRequested = pyqtSignal(str)
    chatRequested = pyqtSignal()
    notificationsRequested = pyqtSignal()

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("appHeader")
        self.setLayoutDirection(Qt.LeftToRight)
        self.setFixedHeight(66)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.setContentsMargins(0, 0, 0, 0)
        self.brand_name = QLabel("سازگان")
        self.brand_name.setObjectName("brandName")
        self.brand_sub = QLabel("خدمات پس از فروش")
        self.brand_sub.setObjectName("brandSub")
        brand.addWidget(self.brand_name)
        brand.addWidget(self.brand_sub)
        brand_wrap = QWidget()
        brand_wrap.setLayout(brand)
        brand_wrap.setLayoutDirection(Qt.RightToLeft)
        brand_wrap.setMinimumWidth(165)
        self._brand_wrap = brand_wrap
        self._brand_sub = self.brand_sub

        self.search = QLineEdit()
        self.search.setObjectName("headerSearch")
        self.search.setPlaceholderText("جستجو در مشتریان، درخواست‌ها و سریال")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(430)
        self.search.setLayoutDirection(Qt.RightToLeft)
        self.search.returnPressed.connect(lambda: self._emit_search())

        self.date_label = QLabel("")
        self.date_label.setObjectName("headerDate")
        self.date_label.setLayoutDirection(Qt.RightToLeft)

        chat = QToolButton()
        chat.setObjectName("headerIconButton")
        chat.setIcon(icon("chat", 19))
        chat.setIconSize(QSize(19, 19))
        chat.setToolTip("گفتگوی مشتری")
        chat.setCursor(Qt.PointingHandCursor)
        chat.clicked.connect(self.chatRequested.emit)

        bell = QToolButton()
        bell.setObjectName("headerIconButton")
        bell.setIcon(icon("notifications", 19))
        bell.setIconSize(QSize(19, 19))
        bell.setToolTip("اعلان‌ها")
        bell.setCursor(Qt.PointingHandCursor)
        bell.clicked.connect(self.notificationsRequested.emit)
        self._bell = bell
        self.unread_badge = QLabel("0", bell)
        self.unread_badge.setObjectName("notificationBadge")
        self.unread_badge.setAlignment(Qt.AlignCenter)
        self.unread_badge.setMinimumSize(18, 18)
        self.unread_badge.move(17, -2)
        self.unread_badge.setVisible(False)

        self.avatar = QToolButton()
        self.avatar.setObjectName("headerAvatar")
        self.avatar.setIcon(icon("user", 18))
        self.avatar.setIconSize(QSize(18, 18))
        self.avatar.setFixedSize(34, 34)
        self.avatar.setToolTip("حساب کاربری")
        self.avatar.setCursor(Qt.PointingHandCursor)
        self.avatar.clicked.connect(self._show_more_menu)

        self.user_name = QLabel("")
        self.user_name.setObjectName("headerUserName")
        self.user_role = QLabel("")
        self.user_role.setObjectName("headerUserRole")
        user_text = QVBoxLayout()
        user_text.setSpacing(0)
        user_text.setContentsMargins(0, 0, 0, 0)
        user_text.addWidget(self.user_name)
        user_text.addWidget(self.user_role)
        user_wrap = QWidget()
        user_wrap.setLayout(user_text)
        user_wrap.setLayoutDirection(Qt.RightToLeft)
        self._user_wrap = user_wrap

        # Left-to-right physical layout: user/icons sit on the left, the
        # search field is centered between the icon cluster and the brand
        # name, and the brand sits at the far right - matching where a
        # right-to-left reader expects it.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 18, 8)
        layout.setSpacing(9)
        layout.addWidget(user_wrap, 0, Qt.AlignVCenter)
        layout.addWidget(self.avatar, 0, Qt.AlignVCenter)
        layout.addWidget(bell, 0, Qt.AlignVCenter)
        layout.addWidget(chat, 0, Qt.AlignVCenter)
        layout.addWidget(self.date_label, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        layout.addWidget(self.search, 0, Qt.AlignVCenter)
        layout.addStretch(1)
        layout.addWidget(brand_wrap, 0)
        self.reload()
        self.apply_responsive(1280)

    def set_unread_count(self, count):
        count = max(0, int(count or 0))
        self.unread_badge.setText(str(count) if count < 100 else "99+")
        self.unread_badge.setVisible(count > 0)

    def apply_responsive(self, width):
        # Keep the header usable on smaller desktop/laptop resolutions without
        # changing the web-matched visual hierarchy.
        compact = width < 1180
        narrow = width < 980
        self._user_wrap.setVisible(not compact)
        self.date_label.setVisible(not compact)
        self._brand_sub.setVisible(not narrow)
        self.search.setVisible(not narrow)
        self._brand_wrap.setMinimumWidth(135 if narrow else 165)
        self.search.setMaximumWidth(320 if compact else 430)

    def _emit_search(self):
        self.searchRequested.emit(self.search.text().strip())

    def _show_more_menu(self):
        menu = QMenu(self)
        menu.setObjectName("headerMoreMenu")
        menu.setLayoutDirection(Qt.RightToLeft)

        account = QAction(icon("user", 16), "حساب کاربری", self)
        account.triggered.connect(self.accountRequested.emit)
        menu.addAction(account)

        settings = QAction(icon("settings", 16), "تنظیمات", self)
        settings.triggered.connect(self.settingsRequested.emit)
        menu.addAction(settings)

        menu.addSeparator()
        logout = QAction(icon("logout", 16), "خروج", self)
        logout.setObjectName("logoutAction")
        logout.triggered.connect(self.logoutRequested.emit)
        menu.addAction(logout)

        # Anchor under the avatar button, which now opens this menu.
        pos = self.avatar.mapToGlobal(self.avatar.rect().bottomLeft())
        menu.exec_(pos)

    def _show_account_dialog(self):
        try:
            info = self.client.native_me()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError:
            info = {}
        dlg = QDialog(self)
        dlg.setWindowTitle("حساب کاربری")
        dlg.setMinimumWidth(360)
        dlg.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        title = QLabel("حساب کاربری")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        for label, value in (
            ("نام کاربری", info.get("username") or self.client.username or "-"),
            ("نام", info.get("full_name") or "-"),
            ("سمت", info.get("role") or "-"),
            ("شرکت", info.get("company_name") or "سازگان"),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label + ":"))
            val = QLabel(str(value))
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(val, 1)
            layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec_()

    def reload(self):
        try:
            info = self.client.native_me()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError:
            return
        company = info.get("company_name") or "سازگان"
        self.brand_name.setText(company)
        self.date_label.setText(info.get("header_date", ""))
        self.user_name.setText(info.get("full_name") or self.client.username)
        self.user_role.setText(info.get("role") or "")


class Sidebar(QFrame):
    """Web-equivalent primary navigation with the same SVGs, labels, order,
    permission visibility and collapse behavior as templates/base.html.
    """
    collapsedChanged = pyqtSignal(bool)
    rowSelected = pyqtSignal(int)

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.collapsed = False
        self._auto_collapsed = False
        self.setObjectName("nativeSidebar")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedWidth(235)
        self.permissions = {}
        self.role = ""
        self.visible_items = []
        root = QVBoxLayout(self); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        top = QHBoxLayout(); top.setSpacing(8)
        self.toggle = QToolButton(); self.toggle.setObjectName("sidebarToggle"); self.toggle.setIcon(icon("menu",22)); self.toggle.setIconSize(QSize(22,22))
        self.toggle.setToolTip("باز/بسته کردن منو"); self.toggle.setAccessibleName("باز و بسته کردن سایدبار"); self.toggle.setCursor(Qt.PointingHandCursor); self.toggle.setFixedSize(38,38); self.toggle.clicked.connect(self.toggle_sidebar)
        top.addWidget(self.toggle,0,Qt.AlignRight)
        # The company name is intentionally NOT repeated here; it already lives in the header.
        top.addStretch(1); root.addLayout(top)
        self.nav=QWidget(); self.nav.setObjectName("webSidebarNav"); self.nav_layout=QVBoxLayout(self.nav); self.nav_layout.setContentsMargins(0,2,0,0); self.nav_layout.setSpacing(3); root.addWidget(self.nav,1)
        self.group=QButtonGroup(self); self.group.setExclusive(True); self.buttons=[]
        self.version=QLabel("نسخه Native"); self.version.setObjectName("sidebarVersion"); self.version.setAlignment(Qt.AlignCenter); root.addWidget(self.version)
        self._build_visible_items()

    def _has_access(self, item):
        perm=item.get("permission")
        roles=item.get("roles")
        if roles and self.role not in roles: return False
        if perm == "reports_or_dashboard": return bool(self.permissions.get("reports") or self.permissions.get("dashboard"))
        if perm == "settings": return bool(self.permissions.get("parties") or self.permissions.get("system") or self.permissions.get("products"))
        if perm: return bool(self.permissions.get(perm))
        return True

    def _build_visible_items(self):
        # Clear every existing layout item, including the stretch, so repeated
        # permission syncs never accumulate hidden widgets or blank space.
        while self.nav_layout.count():
            item = self.nav_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                self.group.removeButton(w)
                w.deleteLater()
        self.buttons=[]; self.visible_items=[]
        for item in WEB_SIDEBAR_ITEMS:
            if not self._has_access(item): continue
            btn=QToolButton(); btn.setObjectName("sidebarItem"); btn.setProperty("navKey",item["key"]); btn.setProperty("navRow",item["index"]); btn.setIcon(icon(item["key"],21)); btn.setIconSize(QSize(21,21)); btn.setText(item["name"]); btn.setToolTip(item["tip"]); btn.setAccessibleName(item["name"]); btn.setCursor(Qt.PointingHandCursor); btn.setCheckable(True); btn.setAutoExclusive(True); btn.setMinimumHeight(42); btn.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.clicked.connect(lambda checked=False, row=item["index"]: self.rowSelected.emit(row)); self.group.addButton(btn); self.nav_layout.addWidget(btn); self.buttons.append(btn); self.visible_items.append(item)
        self.nav_layout.addStretch(1)
        self._set_collapsed_visuals(self.collapsed)

    def sync_identity(self, info):
        info=info or {}; self.role=info.get("role") or ""; self.permissions=info.get("permissions") or {}; self._build_visible_items()

    def set_current_row(self,row):
        for b,item in zip(self.buttons,self.visible_items):
            if item["index"]==row: b.setChecked(True); break

    def set_responsive(self, width):
        # Auto-collapse only; the user can still toggle it manually afterward.
        should_compact = width < 1080
        if should_compact and not self._auto_collapsed and not self.collapsed:
            self._auto_collapsed = True
            self.collapsed = True
            self.setFixedWidth(68)
            self._set_collapsed_visuals(True)
            self.collapsedChanged.emit(True)
        elif not should_compact and self._auto_collapsed:
            self._auto_collapsed = False
            self.collapsed = False
            self.setFixedWidth(235)
            self._set_collapsed_visuals(False)
            self.collapsedChanged.emit(False)

    def toggle_sidebar(self):
        self._auto_collapsed = False
        self.collapsed=not self.collapsed; self.setFixedWidth(68 if self.collapsed else 235); self._set_collapsed_visuals(self.collapsed); self.collapsedChanged.emit(self.collapsed)

    def _set_collapsed_visuals(self,collapsed):
        self.version.setVisible(not collapsed)
        for btn,item in zip(self.buttons,self.visible_items):
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly if collapsed else Qt.ToolButtonTextBesideIcon); btn.setText("" if collapsed else item["name"]); btn.setToolTip(item["name"] if collapsed else item["tip"]); btn.setMinimumHeight(42); btn.setFixedWidth(46 if collapsed else 16777215); btn.setIconSize(QSize(21,21))
        self.nav_layout.setContentsMargins(0,2,0,0)


class MainWindow(QMainWindow):
    logoutRequested = pyqtSignal()
    sessionExpiredRequested = pyqtSignal()

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._handling_session_expired = False
        self.client.sessionExpired.connect(self._handle_session_expired)
        self.setWindowTitle("سامانه جامع خدمات پس از فروش سازگان گستر")
        self.setWindowIcon(app_icon())
        self.resize(1280, 760)
        self.setMinimumSize(900, 560)
        self.setLayoutDirection(Qt.RightToLeft)

        self.stack = QStackedWidget()

        # Web-equivalent hub pages. Each hub is a card grid; cards open the
        # corresponding real Native screen/form instead of a dead placeholder.
        self.customer_hub = HubPage(
            "مرکز امور مشتریان",
            "تمام زیرمنوها و فرم‌های اصلی وب در یک هاب کارتی Native.",
            [
                ("درخواست جدید", "انتخاب نوع خدمت و ثبت درخواست جدید", lambda: self._open_service_new(0), "＋"),
                ("تعمیرات داخلی", "آرشیو و ثبت تعمیرات کارخانه", lambda: self._open_service_tab(0), "⌂"),
                ("تعمیرات خارجی", "آرشیو و ثبت تعمیرات نمایندگی", lambda: self._open_service_tab(1), "□"),
                ("درخواست نصب", "درخواست‌های نصب و آموزش", lambda: self._open_service_tab(2), "▣"),
                ("ثبت نصب", "ثبت نصب انجام‌شده", lambda: self._open_service_tab(3), "✓"),
                ("بررسی و بازدید", "درخواست‌ها و گزارش‌های بازدید", lambda: self._open_service_tab(4), "⌕"),
                ("بایگانی", "گزارش و پرونده‌های بسته‌شده", lambda: self._open_service_tab(0), "▤"),
                ("مخاطبین", "مدیریت ارتباطات مشتری", lambda: self._open_contacts(), "◉"),
                ("نظرسنجی مشتریان", "مدیریت نظرسنجی‌های مشتری", lambda: self._open_surveys(), "★"),
                ("اعلام‌های عمومی", "اعلامیه‌ها و اطلاع‌رسانی مشتری", lambda: self._open_announcements(), "!"),
            ],
            accent="customers",
        )
        self.warehouse_hub = HubPage(
            "رهگیری قطعات",
            "زیرمنوهای کنترل انبار و قطعات مطابق هاب وب.",
            [
                ("کنترل قطعات تعمیرات داخلی", "قطعات مصرف‌شده در تعمیرات داخلی", lambda: self._open_warehouse_tab(0), "▣"),
                ("کنترل قطعات نمایندگان", "قطعات تعمیرات خارج از کارخانه", lambda: self._open_warehouse_tab(1), "□"),
            ],
            accent="warehouse",
        )
        self.finance_hub = HubPage(
            "امور مالی",
            "کارت‌های مالی وب در Native با صفحات واقعی مالی.",
            [
                ("جدول دستمزد", "تعریف و مدیریت جدول دستمزد", lambda: self._open_finance_tab(3), "≡"),
                ("محاسبه دستمزد", "گزارش محاسبات دستمزد", lambda: self._open_improvements_tab(0), "Σ"),
                ("گزارش دستمزد ماهانه", "گزارش ماهانه دستمزد", lambda: self._open_improvements_tab(0), "▤"),
                ("تاریخچه دستمزد", "سوابق محاسبات دستمزد", lambda: self._open_finance_tab(1), "◷"),
                ("دستمزد من", "نمایش دستمزد حساب جاری", lambda: self._open_finance_tab(2), "﷼"),
                ("مدیریت مالی نمایندگان", "خلاصه و وضعیت تسویه نمایندگان", lambda: self._open_finance_tab(0), "◫"),
                ("پرونده‌های مالی", "پرونده‌ها و اسناد مالی", lambda: self._open_finance_tab(4), "▧"),
            ],
            accent="finance",
        )
        self.reports_hub = HubPage(
            "گزارش‌ها",
            "تمام کارت‌های هاب گزارش وب؛ هر کارت به صفحه Native مربوطه می‌رود.",
            [
                ("داشبورد آماری", "نمای کلی شاخص‌های خدمات", lambda: self._open_reports_tab(0), "▥"),
                ("داشبورد مدیر", "شاخص‌های مدیریتی", lambda: self._open_improvements_tab(1), "◫"),
                ("گزارش مدیریتی", "تجمیع عملکرد و تأخیر", lambda: self._open_reports_tab(1), "▤"),
                ("گزارش اجرایی", "خلاصه اجرایی عملیات", lambda: self._open_improvements_tab(1), "▣"),
                ("گزارش عملکرد خدمات", "عملکرد همه خدمات", lambda: self._open_reports_tab(1), "↗"),
                ("گزارش تعمیرات داخلی", "عملکرد تعمیرات کارخانه", lambda: self._open_reports_tab(1), "⌂"),
                ("گزارش تعمیرات خارجی", "عملکرد نمایندگی‌ها", lambda: self._open_reports_tab(1), "□"),
                ("گزارش نصب", "عملکرد نصب دستگاه‌ها", lambda: self._open_reports_tab(1), "✓"),
                ("گزارش بررسی و بازدید", "عملکرد بازدیدهای میدانی", lambda: self._open_reports_tab(1), "⌕"),
                ("ماتریس تأخیر (سریال)", "پیگیری تأخیر بر اساس سریال", lambda: self._open_reports_tab(2), "◷"),
            ],
            accent="reports",
        )
        self.settings_hub = HubPage(
            "تنظیمات",
            "زیرمنوهای تنظیمات وب؛ مواردی که Native API دارند مستقیماً باز می‌شوند.",
            [
                ("شرکت", "اطلاعات شرکت", lambda: self._open_settings_tab(0), "▤"),
                ("درباره / تاریخچه تغییرات", "اطلاعات نسخه و چنج‌لاگ", lambda: self._open_settings_tab(1), "ⓘ"),
                ("فعال‌سازی نرم‌افزار", "وضعیت لایسنس و فعال‌سازی", lambda: self._open_settings_tab(2), "🔑"),
                ("تنظیمات نرم‌افزار", "لیست‌ها و وضعیت‌ها", lambda: self._open_settings_tab(3), "≡"),
                ("استان / شهر و مسافت", "اطلاعات جغرافیایی", lambda: self._open_settings_tab(4), "◎"),
                ("تقویم", "تقویم و تعطیلات", lambda: self._open_settings_tab(5), "□"),
                ("ارتباط با مشتری", "گفتگو، پیام‌رسانی و ایموجی‌های چت", lambda: self._open_support(), "💬"),
                ("راهنماهای فرم‌ها", "راهنمای فرم‌ها", lambda: self._open_settings_tab(7), "?"),
                ("اطلاعات سیستم", "وضعیت و اطلاعات فنی سیستم", lambda: self._open_settings_tab(8), "🖥"),
                ("کاربران سیستم", "کاربران فعال و آرشیو کاربران", lambda: self._open_settings_tab(10), "◈"),
                ("تم و نمایش", "ظاهر Native و Design System", lambda: self._open_settings(), "◐"),
                ("Export / Import", "ورود و خروج اکسل", lambda: self._open_data_hub(), "⇅"),
                ("پشتیبان و لاگ ممیزی", "پشتیبان‌گیری و ممیزی", lambda: self._open_improvements_tab(2), "▣"),
                ("مدیریت محصولات", "شناسنامه کالا، دستگاه‌ها و قطعات", lambda: self._open_settings_tab(11), "▦"),
                ("طرف حساب‌ها", "مدیریت مشتریان", lambda: self._open_customers(), "◎"),
                ("نمایندگان", "مدیریت نمایندگی‌های تعمیرات خارجی", lambda: self._open_settings_tab(12), "☖"),
                ("دسترسی‌ها", "نقش‌ها و سطوح دسترسی کاربران", lambda: self._open_settings_tab(13), "🔒"),
            ],
            accent="settings",
        )

        self.stack.addWidget(HomePage(self.client))                  # 0 cartable
        self.stack.addWidget(SearchPage(self.client))                # 1 search
        self.stack.addWidget(SupportPage(self.client))               # 2 chat
        self.stack.addWidget(NotificationsPage(self.client))         # 3 notifications
        self.stack.addWidget(self.customer_hub)                       # 4 customer hub
        self.stack.addWidget(HomePage(self.client))                   # 5 tasks
        self.stack.addWidget(self.warehouse_hub)                      # 6 warehouse hub
        self.stack.addWidget(self.finance_hub)                        # 7 finance hub
        self.stack.addWidget(self.reports_hub)                        # 8 reports hub
        self.stack.addWidget(self.settings_hub)                       # 9 settings hub
        self.service_page = ServicePage(self.client)
        self.finance_page = FinancePage(self.client)
        self.reports_page = ReportsPage(self.client)
        self.settings_page = SettingsPage(self.client)
        self.warehouse_page = WarehousePage(self.client)
        self.data_hub_page = DataHubPage(self.client)
        self.improvements_page = ImprovementsPage(self.client)
        self.stack.addWidget(self.service_page)                       # 10
        self.stack.addWidget(self.finance_page)                       # 11
        self.stack.addWidget(self.reports_page)                       # 12
        self.stack.addWidget(self.settings_page)                      # 13
        self.stack.addWidget(WarrantyLookupPage(self.client))         # 14
        self.stack.addWidget(self.data_hub_page)                      # 15
        self.stack.addWidget(self.improvements_page)                  # 16
        self.stack.addWidget(AccountPage(self.client))                # 17
        self.stack.addWidget(self.warehouse_page)                     # 18
        self.customers_page = CustomersPage(self.client)
        self.stack.addWidget(self.customers_page)                     # 19
        self.contacts_page = ContactsPage(self.client)
        self.stack.addWidget(self.contacts_page)                      # 20
        self.announcements_page = AnnouncementsPage(self.client)
        self.stack.addWidget(self.announcements_page)                 # 21
        self.surveys_page = SurveysPage(self.client)
        self.stack.addWidget(self.surveys_page)                       # 22

        sidebar = Sidebar(self.client)
        sidebar.rowSelected.connect(self._select_web_row)
        
        try:
            info = self.client.native_me()
        except SessionExpiredError:
            self.client.logged_in = False
            self._handle_session_expired()
            return
        except ApiError:
            info = {}
        sidebar.sync_identity(info)
        sidebar.set_current_row(0)
        self.sidebar = sidebar

        body = QWidget(); h = QHBoxLayout(body); h.setContentsMargins(0,0,0,0); h.setSpacing(0)
        h.addWidget(self.sidebar); h.addWidget(self.stack, 1)
        central = QWidget(); v = QVBoxLayout(central); v.setContentsMargins(0,0,0,0); v.setSpacing(0)
        self.header = HeaderBar(self.client)
        self.header.accountRequested.connect(lambda: self._open_account())
        self.header.settingsRequested.connect(lambda: self._open_settings())
        self.header.searchRequested.connect(self._header_search)
        self.header.chatRequested.connect(lambda: self.stack.setCurrentIndex(2))
        self.header.notificationsRequested.connect(lambda: self._open_notifications())
        self.header.logoutRequested.connect(self._logout)
        v.addWidget(self.header); v.addWidget(body, 1)
        self.setCentralWidget(central)
        # Web parity: unread notification badge is refreshed every 60s.
        self.notification_timer = QTimer(self)
        self.notification_timer.setInterval(60000)
        self.notification_timer.timeout.connect(self._refresh_notification_badge)
        self.notification_timer.start()
        self._refresh_notification_badge()
        self._apply_responsive_layout()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._refresh_notification_badge()

    def _refresh_notification_badge(self):
        if self._handling_session_expired:
            return
        try:
            data = self.client.unread_notifications_count()
            if hasattr(self, "header"):
                self.header.set_unread_count(int(data.get("count") or 0))
        except SessionExpiredError:
            pass
        except ApiError:
            # Badge polling must never interrupt the current page.
            pass

    def _handle_session_expired(self):
        if self._handling_session_expired:
            return
        self._handling_session_expired = True
        QMessageBox.warning(self, "نشست", "نشست شما منقضی شده، دوباره وارد شوید")
        self.sessionExpiredRequested.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self):
        width = self.width()
        if hasattr(self, "sidebar"):
            self.sidebar.set_responsive(width)
        if hasattr(self, "header"):
            self.header.apply_responsive(width)

    def _header_search(self, query):
        self.stack.setCurrentIndex(1)
        page = self.stack.widget(1)
        if query and hasattr(page, "edit"):
            page.edit.setText(query)
            page.search()

    def _open_account(self):
        self.stack.setCurrentIndex(17)
        page=self.stack.widget(17)
        if hasattr(page, "reload"): page.reload()

    def _open_settings(self):
        # NOTE: was pointing at index 9 (self.settings_hub itself), which
        # made the "تنظیمات سیستم" hub card and the header gear icon both
        # loop back to the same hub screen instead of ever reaching the
        # real SettingsPage (index 13, connection + کاربران سیستم tabs).
        self.stack.setCurrentIndex(13)

    def _open_notifications(self):
        self.stack.setCurrentIndex(3)
        page=self.stack.widget(3)
        if hasattr(page, "reload"): page.reload()

    def _open_support(self):
        self.stack.setCurrentIndex(2)
        page=self.stack.widget(2)
        if hasattr(page, "reload"): page.reload()

    def _open_data_hub(self):
        self.stack.setCurrentIndex(15)
        page=self.stack.widget(15)
        if hasattr(page, "reload"): page.reload()

    def _open_customers(self):
        self.stack.setCurrentIndex(19)
        page=self.stack.widget(19)
        if hasattr(page, "reload"): page.reload()

    def _open_contacts(self):
        self.stack.setCurrentIndex(20)
        page=self.stack.widget(20)
        if hasattr(page, "reload"): page.reload()

    def _open_announcements(self):
        self.stack.setCurrentIndex(21)
        page=self.stack.widget(21)
        if hasattr(page, "reload"): page.reload()

    def _open_surveys(self):
        self.stack.setCurrentIndex(22)
        page=self.stack.widget(22)
        if hasattr(page, "reload"): page.reload()

    def _open_service_tab(self, index):
        self.stack.setCurrentIndex(10)
        page=self.stack.widget(10)
        if hasattr(page, "open_archive_tab"): page.open_archive_tab(index)

    def _open_service_new(self, index):
        self.stack.setCurrentIndex(10)
        page=self.stack.widget(10)
        if hasattr(page, "open_new_tab"): page.open_new_tab(index)

    def _open_warehouse_tab(self, index):
        self.stack.setCurrentIndex(18)
        page = self.stack.widget(18)
        if hasattr(page, "open_tab"):
            page.open_tab(index)

    def _open_finance_tab(self, index):
        self.stack.setCurrentIndex(11)
        page=self.stack.widget(11)
        if hasattr(page, "open_tab"): page.open_tab(index)

    def _open_reports_tab(self, index):
        self.stack.setCurrentIndex(12)
        page=self.stack.widget(12)
        if hasattr(page, "open_tab"): page.open_tab(index)

    def _open_settings_tab(self, index):
        self.stack.setCurrentIndex(13)
        page=self.stack.widget(13)
        if hasattr(page, "open_tab"): page.open_tab(index)

    def _open_improvements_tab(self, index):
        self.stack.setCurrentIndex(16)
        page=self.stack.widget(16)
        if hasattr(page, "open_tab"): page.open_tab(index)


    def _logout(self):
        self.client.logout()
        QApplication.instance().quit()

    def _select_web_row(self, row):
        # Primary sidebar now opens the same hub-card level as the Web UI.
        mapping = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
        idx = mapping.get(row)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

