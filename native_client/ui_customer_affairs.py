# -*- coding: utf-8 -*-
"""فاز A: «امور مشتریان» - مخاطبین، اعلام‌های عمومی و نظرسنجی مشتریان.

مخاطبین و اعلام‌های عمومی همان منطق و داده‌های وب (`/contacts`,
`/announce/list`) را از طریق endpointهای native_api.py مصرف می‌کنند.
نظرسنجی مشتریان در خود وب هم فقط یک پوسته/foundation ثابت است
(`templates/surveys_v46.html` بدون هیچ API واقعی) - این صفحه همان
وضعیت را به‌صورت بومی و RTL بازتولید می‌کند تا به‌جای پیام «صفحه وب»
یک صفحه واقعی (هرچند هنوز بدون داده) نمایش داده شود.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QMessageBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table, make_card, make_stat_card

CONTACT_COLUMNS = [
    ("name", "نام مخاطب"), ("company", "شرکت"), ("mobile", "موبایل"),
    ("phone", "تلفن"), ("email", "ایمیل"), ("city", "شهر"),
    ("status", "وضعیت"), ("group_name", "گروه"), ("source_label", "منبع"),
]

ANNOUNCE_COLUMNS = [
    ("id", "شماره"), ("created_at", "تاریخ"), ("hospital_name", "نام مرکز/مشتری"),
    ("contact_name", "نام رابط"), ("contact_phone", "شماره تماس"),
    ("province", "استان"), ("city", "شهر"), ("problem_brief", "شرح درخواست"),
    ("status", "وضعیت"),
]



def _notify_session_expired(widget):
    """Route session-expiration to the top-level MainWindow handler.

    Walks the ``parentWidget()`` chain looking for an object exposing
    ``_handle_session_expired`` (i.e. MainWindow). Plain ``.window()``
    is deliberately NOT used: QDialog subclasses (e.g. the service
    Detail dialogs) are always their own top-level window in Qt even
    when constructed with a parent, so ``.window()`` would return the
    dialog itself and silently find no handler. ``parentWidget()``
    still returns the constructor's ``parent`` argument regardless of
    the widget's top-level/window status, so it correctly reaches
    MainWindow both for dialogs and for pages embedded directly in
    MainWindow's QStackedWidget.
    """
    node = widget
    while node is not None:
        handler = getattr(node, "_handle_session_expired", None)
        if callable(handler):
            handler()
            return
        node = node.parentWidget() if hasattr(node, "parentWidget") else None


class ContactsPage(QWidget):
    """مخاطبین - مطابق /contacts (لیست + ثبت مخاطب جدید؛ وب هم ویرایش/آرشیو ندارد)."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)

        title = QLabel("مخاطبین")
        title.setObjectName("pageTitle")
        sub = QLabel("مدیریت لیست مخاطبین و اطلاعات تماس (دستی + طرف‌حساب‌های دارای شماره)")
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)

        form_card, form_layout = make_card("مخاطب جدید")
        self.name_edit = QLineEdit()
        self.company_edit = QLineEdit()
        self.mobile_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.website_edit = QLineEdit()
        self.city_edit = QLineEdit()
        self.status_combo = QComboBox()
        for s in ("مشتری", "مشتری بالقوه", "همکار", "متعاقب شود"):
            self.status_combo.addItem(s, s)
        self.group_edit = QLineEdit()
        self.group_edit.setText("مشتریان")
        self.address_edit = QLineEdit()
        self.notes_edit = QLineEdit()

        grid = QFormLayout()
        grid.addRow("نام شخص:*", self.name_edit)
        grid.addRow("نام شرکت:", self.company_edit)
        grid.addRow("موبایل:", self.mobile_edit)
        grid.addRow("تلفن:", self.phone_edit)
        grid.addRow("ایمیل:", self.email_edit)
        grid.addRow("وب‌سایت:", self.website_edit)
        grid.addRow("شهر:", self.city_edit)
        grid.addRow("وضعیت:", self.status_combo)
        grid.addRow("گروه:", self.group_edit)
        grid.addRow("آدرس:", self.address_edit)
        grid.addRow("یادداشت:", self.notes_edit)
        form_layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("ثبت مخاطب")
        self.submit_btn.clicked.connect(self._submit)
        btn_row.addWidget(self.submit_btn)
        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form_layout.addWidget(self.status_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو در نام، شرکت، تلفن، ایمیل، شهر...")
        self.search_edit.returnPressed.connect(self.reload)
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.setProperty("variant", "secondary")
        self.reload_btn.clicked.connect(self.reload)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.reload_btn)

        self.table = QTableWidget()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(12)
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(form_card)
        root.addLayout(search_row)
        root.addWidget(self.table, 1)

        self.reload()

    def reload(self):
        q = self.search_edit.text().strip()
        try:
            data = self.client.customer_affairs_contacts(q or None)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        fill_table(self.table, data.get("contacts", []), CONTACT_COLUMNS)

    def _reset_form(self):
        for w in (self.name_edit, self.company_edit, self.mobile_edit, self.phone_edit,
                  self.email_edit, self.website_edit, self.city_edit, self.address_edit,
                  self.notes_edit):
            w.clear()
        self.status_combo.setCurrentIndex(0)
        self.group_edit.setText("مشتریان")

    def _submit(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "فیلد الزامی", "نام مخاطب الزامی است.")
            return
        data = {
            "name": name,
            "company": self.company_edit.text().strip(),
            "mobile": self.mobile_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "website": self.website_edit.text().strip(),
            "city": self.city_edit.text().strip(),
            "status": self.status_combo.currentData(),
            "group_name": self.group_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "notes": self.notes_edit.text().strip(),
        }
        self.submit_btn.setEnabled(False)
        try:
            self.client.customer_affairs_contact_new(data)
            self.status_label.setText("مخاطب با موفقیت ثبت شد.")
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "ثبت ناموفق", str(e))
            return
        finally:
            self.submit_btn.setEnabled(True)
        self._reset_form()
        self.reload()


class AnnouncementsPage(QWidget):
    """اعلام‌های عمومی - مطابق /announce/list (لیست + «تماس انجام شد»)."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)

        title = QLabel("اعلام‌های عمومی")
        title.setObjectName("pageTitle")
        sub = QLabel("اعلام‌های خرابی ثبت‌شده از فرم عمومی مشتریان و پیگیری تماس با آن‌ها")
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو در نام مرکز، رابط، تلفن، سریال...")
        self.search_edit.returnPressed.connect(self.reload)
        self.status_combo = QComboBox()
        self.status_combo.addItem("همه وضعیت‌ها", "")
        self.status_combo.currentIndexChanged.connect(self.reload)
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.setProperty("variant", "secondary")
        self.reload_btn.clicked.connect(self.reload)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.status_combo)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.reload_btn)

        self.table = QTableWidget()

        actions_row = QHBoxLayout()
        self.handled_btn = QPushButton("تماس انجام شد (ردیف انتخاب‌شده)")
        self.handled_btn.clicked.connect(self._mark_handled)
        actions_row.addWidget(self.handled_btn)
        actions_row.addStretch()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(12)
        root.addWidget(title)
        root.addWidget(sub)
        root.addLayout(search_row)
        root.addWidget(self.table, 1)
        root.addLayout(actions_row)

        self._status_loaded = False
        self.reload()

    def reload(self):
        q = self.search_edit.text().strip()
        status = self.status_combo.currentData()
        try:
            data = self.client.customer_affairs_announcements(q or None, status or None)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        if not self._status_loaded:
            self.status_combo.blockSignals(True)
            for s in data.get("status_options", []):
                self.status_combo.addItem(s, s)
            self.status_combo.blockSignals(False)
            self._status_loaded = True
        fill_table(self.table, data.get("announcements", []), ANNOUNCE_COLUMNS)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    def _mark_handled(self):
        ann_id = self._selected_id()
        if not ann_id:
            QMessageBox.information(self, "انتخاب ردیف", "ابتدا یک اعلام را از جدول انتخاب کنید.")
            return
        try:
            self.client.customer_affairs_announcement_handled(int(ann_id))
        except (ApiError, ValueError) as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.reload()


class SurveysPage(QWidget):
    """نظرسنجی مشتریان - در وب هم فعلاً فقط یک پوستهٔ ثابت بدون API واقعی است.

    این صفحه دقیقاً همان وضعیت (کارت‌های خلاصه صفر، تب‌های فیلتر، لیست خالی)
    را به‌صورت بومی نمایش می‌دهد تا کاربر Native به‌جای پیام «صفحه وب» یک
    صفحهٔ واقعی و هم‌تراز با وب ببیند؛ به محض این‌که وب یک API واقعی برای
    نظرسنجی‌ها اضافه کند، همین صفحه باید به آن وصل شود.
    """

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)

        title = QLabel("نظرسنجی مشتریان")
        title.setObjectName("pageTitle")
        sub = QLabel("سنجش رضایت مشتری و کیفیت خدمات")
        sub.setObjectName("pageSubtitle")

        stats_row = QHBoxLayout()
        stats_row.addWidget(make_stat_card("رضایت", "—"))
        stats_row.addWidget(make_stat_card("پاسخ‌ها", "0"))
        stats_row.addWidget(make_stat_card("مثبت", "0"))
        stats_row.addWidget(make_stat_card("منفی", "0"))

        tabs_row = QHBoxLayout()
        for label in ("همه پاسخ‌ها", "مثبت", "خنثی", "منفی", "در انتظار"):
            b = QPushButton(label)
            b.setProperty("variant", "secondary")
            b.setEnabled(False)
            tabs_row.addWidget(b)
        tabs_row.addStretch()

        empty_card, empty_layout = make_card(
            None,
            "این بخش هنوز در نسخهٔ وب هم فقط یک طرح اولیه (foundation) است و پاسخ "
            "نظرسنجی واقعی ثبت نمی‌شود؛ به محض افزوده‌شدن API واقعی به وب، این "
            "صفحه در Native نیز به همان داده وصل خواهد شد.",
        )
        empty_label = QLabel("هیچ پاسخ نظرسنجی‌ای بارگذاری نشده است.")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setObjectName("pageSubtitle")
        empty_layout.addWidget(empty_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(12)
        root.addWidget(title)
        root.addWidget(sub)
        root.addLayout(stats_row)
        root.addLayout(tabs_row)
        root.addWidget(empty_card)
        root.addStretch(1)

    def reload(self):
        pass
