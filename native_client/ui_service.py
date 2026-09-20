# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTabWidget, QMessageBox, QComboBox, QCheckBox, QDialog, QDialogButtonBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table
from ui_service_forms import (
    make_internal_repair_form, make_external_repair_form,
    make_installation_request_form, make_installation_register_form,
    make_inspection_request_form, make_inspection_report_form,
)
from ui_service_detail import (
    InternalRepairDetailDialog, ExternalRepairDetailDialog,
    InstallationRequestDetailDialog, InstallationRegisterDetailDialog,
    InspectionDetailDialog,
)

REQUEST_COLUMNS = [
    ("id", "شناسه"), ("reception_no", "شماره پذیرش"), ("customer_name", "مشتری"),
    ("device_type", "نوع دستگاه"), ("status", "وضعیت"), ("province", "استان"),
    ("city", "شهر"), ("assigned_technician", "تکنسین"), ("reception_date", "تاریخ پذیرش"),
    ("days_in_status", "روز در وضعیت فعلی"),
]

REGISTER_COLUMNS = [
    ("id", "شناسه"), ("reception_no", "شماره پذیرش"), ("customer_name", "مشتری"),
    ("device_type", "نوع دستگاه"), ("province", "استان"), ("city", "شهر"),
    ("assigned_technician", "تکنسین"), ("reception_date", "تاریخ ثبت"),
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


class _ArchiveListTab(QWidget):
    """یک تب فهرست/آرشیو با فیلتر جست‌وجو، وضعیت و فقط تأخیردارها.

    on_row_open (اختیاری): callable(row_dict) - وقتی روی یک ردیف دابل‌کلیک می‌شود.
    """

    def __init__(self, client, fetch_fn, columns, statuses=None, title="", on_row_open=None):
        super().__init__()
        self.client = client
        self.fetch_fn = fetch_fn
        self.columns = columns
        self.on_row_open = on_row_open
        self._rows = []
        self.setLayoutDirection(Qt.RightToLeft)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:700; font-size:13px;")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو (نام مشتری، سریال، شماره پذیرش...)")
        self.search_edit.returnPressed.connect(self.reload)

        self.status_combo = QComboBox()
        self.status_combo.addItem("همه وضعیت‌ها", "")
        for s in (statuses or []):
            self.status_combo.addItem(s, s)
        self.status_combo.currentIndexChanged.connect(self.reload)

        self.only_delayed_chk = QCheckBox("فقط تأخیردارها")
        self.only_delayed_chk.stateChanged.connect(self.reload)

        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.clicked.connect(self.reload)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#64748b;")

        top = QHBoxLayout()
        top.addWidget(self.reload_btn)
        top.addWidget(self.only_delayed_chk)
        top.addWidget(self.status_combo)
        top.addWidget(self.search_edit)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        if self.on_row_open:
            self.table.itemDoubleClicked.connect(self._handle_row_open)

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addLayout(top)
        layout.addWidget(self.count_label)
        layout.addWidget(self.table, 1)
        self.setLayout(layout)

        self.reload()

    def _filters(self):
        return {
            "q": self.search_edit.text().strip(),
            "status": self.status_combo.currentData() or "",
            "only_delayed": "1" if self.only_delayed_chk.isChecked() else "",
        }

    def reload(self):
        try:
            data = self.fetch_fn(self._filters())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        rows = data.get("requests", [])
        self._rows = rows
        pg = data.get("pagination") or {}
        fill_table(self.table, rows, self.columns)
        self.count_label.setText(
            f"{pg.get('total', len(rows))} مورد — صفحه {pg.get('page', 1)} از {pg.get('total_pages', 1)}"
        )

    def _handle_row_open(self, item):
        row = item.row()
        if 0 <= row < len(self._rows):
            self.on_row_open(self._rows[row])


class InspectionTab(_ArchiveListTab):
    """فهرست بررسی و بازدید با دو زیرتب: درخواست‌ها / انجام‌شده‌ها."""

    def __init__(self, client, tab_kind, statuses, title, on_row_open=None):
        self.tab_kind = tab_kind
        super().__init__(client, self._fetch, REQUEST_COLUMNS, statuses, title, on_row_open=on_row_open)

    def _fetch(self, filters):
        return self.client.inspection_list(tab=self.tab_kind, filters=filters)


class ServicePage(QWidget):
    """لایه فهرست و آرشیو هاب امور مشتریان + تعمیرات + نصب و بازدید.

    فرم‌های ثبت/ویرایش (new/view) هنوز وب‌محور هستن؛ در ادامه‌ی همین فاز اضافه می‌شن.
    """

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.hub_info = QLabel("در حال بارگذاری...")
        self.hub_info.setWordWrap(True)
        self.hub_info.setStyleSheet(
            "padding:10px; background:#f7f9fc; border:1px solid #e6ebf1; border-radius:8px;"
        )

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)

        self.tabs.addTab(
            _ArchiveListTab(
                client, lambda f: client.service_archive("internal-repair", f),
                REQUEST_COLUMNS, title="آرشیو تعمیرات داخلی",
                on_row_open=self._open_internal_repair_detail,
            ),
            "تعمیر داخلی",
        )
        self.tabs.addTab(
            _ArchiveListTab(
                client, lambda f: client.service_archive("external-repair", f),
                REQUEST_COLUMNS, title="آرشیو تعمیرات خارجی",
                on_row_open=self._open_external_repair_detail,
            ),
            "تعمیر خارجی",
        )
        self.tabs.addTab(
            _ArchiveListTab(
                client, client.installation_requests,
                REQUEST_COLUMNS, title="درخواست‌های نصب",
                on_row_open=self._open_installation_request_detail,
            ),
            "درخواست نصب",
        )
        self.tabs.addTab(
            _ArchiveListTab(
                client, client.installation_registers,
                REGISTER_COLUMNS, title="نصب انجام‌شده",
                on_row_open=self._open_installation_register_detail,
            ),
            "ثبت نصب",
        )
        self.tabs.addTab(
            InspectionTab(client, "requests", None, "درخواست بررسی و بازدید",
                           on_row_open=self._open_inspection_detail),
            "بازدید (درخواست)",
        )
        self.tabs.addTab(
            InspectionTab(client, "reports", None, "بررسی و بازدید انجام‌شده",
                           on_row_open=self._open_inspection_detail),
            "بازدید (انجام‌شده)",
        )

        # فرم‌های «ثبت جدید» دیگر روی QStackedWidget/تب اصلی پوش نمی‌شوند؛
        # هر فرم در یک QDialog مستقل باز می‌شود تا کاربر پس از ثبت به همان فهرست برگردد.
        self._form_factories = (
            make_internal_repair_form,
            make_external_repair_form,
            make_installation_request_form,
            make_installation_register_form,
            make_inspection_request_form,
            make_inspection_report_form,
        )

        self.outer_tabs = QTabWidget()
        self.outer_tabs.setLayoutDirection(Qt.RightToLeft)
        self.outer_tabs.addTab(self.tabs, "آرشیو / فهرست‌ها")

        layout = QVBoxLayout()
        layout.addWidget(self.hub_info)
        layout.addWidget(self.outer_tabs, 1)
        self.setLayout(layout)

        self._load_hub()

    def open_archive_tab(self, index):
        self.outer_tabs.setCurrentIndex(0)
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))

    def open_new_tab(self, index):
        index = max(0, min(index, len(self._form_factories) - 1))
        self.outer_tabs.setCurrentIndex(0)
        form = self._form_factories[index](self.client)
        dlg = QDialog(self)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setWindowTitle(form.findChild(QLabel).text() if form.findChild(QLabel) else "ثبت جدید")
        dlg.setModal(True)
        dlg.resize(860, 720)
        layout = QVBoxLayout(dlg)
        layout.addWidget(form, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        form.submitted.connect(dlg.accept)
        dlg.exec_()

        # بعد از بستن دیالوگ، فهرست مربوطه را تازه‌سازی کن.
        self._reload_service_lists(index)

    def _reload_service_lists(self, index):
        # فرم‌ها و APIهای ثبت دست‌نخورده‌اند؛ فقط نمایش پس از دیالوگ تازه می‌شود.
        try:
            if index == 0:
                self.tabs.setCurrentIndex(0)
            elif index == 1:
                self.tabs.setCurrentIndex(1)
            elif index == 2:
                self.tabs.setCurrentIndex(2)
            elif index == 3:
                self.tabs.setCurrentIndex(3)
            elif index == 4:
                self.tabs.setCurrentIndex(4)
            elif index == 5:
                self.tabs.setCurrentIndex(5)
            page = self.tabs.currentWidget()
            if hasattr(page, "reload"):
                page.reload()
        except Exception:
            pass

    def _load_hub(self):
        try:
            data = self.client.service_hub()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            self.hub_info.setText(f"خطا در بارگذاری هاب امور مشتریان: {e}")
            return
        cats = data.get("categories", [])
        names = "، ".join(c.get("title", "") for c in cats)
        self.hub_info.setText(f"امور مشتریان — دسته‌های خدمات: {names}")

    def _open_internal_repair_detail(self, row: dict):
        req_id = row.get("id")
        if not req_id:
            return
        dlg = InternalRepairDetailDialog(self.client, int(req_id), parent=self)
        dlg.exec_()

    def _open_external_repair_detail(self, row: dict):
        req_id = row.get("id")
        if not req_id:
            return
        dlg = ExternalRepairDetailDialog(self.client, int(req_id), parent=self)
        dlg.exec_()

    def _open_installation_request_detail(self, row: dict):
        req_id = row.get("id")
        if not req_id:
            return
        dlg = InstallationRequestDetailDialog(self.client, int(req_id), parent=self)
        dlg.exec_()

    def _open_installation_register_detail(self, row: dict):
        req_id = row.get("id")
        if not req_id:
            return
        dlg = InstallationRegisterDetailDialog(self.client, int(req_id), parent=self)
        dlg.exec_()

    def _open_inspection_detail(self, row: dict):
        req_id = row.get("id")
        if not req_id:
            return
        dlg = InspectionDetailDialog(self.client, int(req_id), parent=self)
        dlg.exec_()
