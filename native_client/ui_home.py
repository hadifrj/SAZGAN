# -*- coding: utf-8 -*-
"""فاز ۷ (پورت‌شده روی V4.9.6): routes/main.py - داشبورد خانه/کارتابل.

سرور بسته به نقش کاربر یکی از این ۴ حالت رو برمی‌گردونه (همون منطق
core/cartable.py که خود وب‌اپ استفاده می‌کنه):
  - finance      : کارتابل امور مالی (فقط نمایش)
  - qc           : کارتابل کنترل کیفیت (فقط نمایش)
  - technician   : کارتابل تکنسین (دکمه‌ی «تکمیل مأموریت»)
  - reception     : کارتابل پذیرش/مدیر (دکمه‌ی «تغییر وضعیت»)
"""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QComboBox, QMessageBox, QLineEdit, QCheckBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table, make_stat_card

TASK_COLUMNS = [
    ("id", "شناسه"), ("kind", "نوع"), ("customer_name", "مشتری"),
    ("device_type", "نوع دستگاه"), ("serial_number", "سریال"), ("province", "استان"),
    ("assigned_technician", "تکنسین"), ("status", "وضعیت"),
    ("reception_date", "تاریخ پذیرش"), ("days_in_status", "روز در وضعیت فعلی"),
]

FINANCE_COLUMNS = [
    ("id", "شناسه"), ("customer_name", "مشتری"), ("device_type", "نوع دستگاه"),
    ("status", "وضعیت"), ("assigned_technician", "تکنسین"),
    ("reception_date", "تاریخ پذیرش"), ("days_in_status", "روز در وضعیت فعلی"),
]

RECEPTION_COLUMNS = [
    ("id", "شناسه"), ("customer_name", "مشتری"), ("device_type", "نوع دستگاه"),
    ("serial_number", "سریال"), ("province", "استان"),
    ("assigned_technician", "تکنسین"), ("status", "وضعیت"), ("reception_date", "تاریخ پذیرش"),
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


class HomePage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        self._current_view = None

        self.title_label = QLabel("کارتابل")
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel("نمای کلی کارتابل و وظایف شما")
        self.subtitle_label.setObjectName("pageSubtitle")

        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.reload)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجوی مشتری، سریال، پذیرش...")
        self.search_edit.textChanged.connect(self._apply_filters)
        self.status_filter = QComboBox()
        self.status_filter.addItem("همه وضعیت‌ها", "")
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.kind_filter = QComboBox()
        self.kind_filter.addItem("همه انواع", "")
        self.kind_filter.currentIndexChanged.connect(self._apply_filters)
        self.province_filter = QComboBox()
        self.province_filter.addItem("همه استان‌ها", "")
        self.province_filter.currentIndexChanged.connect(self._apply_filters)
        self.technician_filter = QComboBox()
        self.technician_filter.addItem("همه مسئولان", "")
        self.technician_filter.currentIndexChanged.connect(self._apply_filters)
        self.delay_filter = QCheckBox("فقط تأخیردار")
        self.delay_filter.stateChanged.connect(self._apply_filters)
        self._all_rows = []
        self._columns = []

        head = QHBoxLayout()
        head.addWidget(self.title_label)
        head.addStretch()
        head.addWidget(self.refresh_btn)

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(10)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._open_selected)

        # تغییر وضعیت عمومی از کارتابل حذف شده است؛ عملیات فقط داخل پرونده و
        # از Action معتبر همان Workflow انجام می‌شود.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 28)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(self.subtitle_label)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.delay_filter)
        filter_row.addWidget(self.technician_filter)
        filter_row.addWidget(self.province_filter)
        filter_row.addWidget(self.kind_filter)
        filter_row.addWidget(self.status_filter)
        filter_row.addWidget(self.search_edit, 1)
        layout.addLayout(filter_row)
        layout.addLayout(self.stats_row)
        layout.addWidget(self.table, 1)

        self.reload()

    def _clear_stats(self):
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)  # ستون اول همیشه "شناسه" است
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def reload(self):
        try:
            data = self.client.home_dashboard()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        view = data.get("view")
        self._current_view = view
        self._clear_stats()

        if view == "finance":
            self.title_label.setText("کارتابل امور مالی")
            tasks = data.get("tasks", [])
            self.stats_row.addWidget(make_stat_card("پرونده‌های باز", data.get("open_count", 0)))
            self._set_rows(tasks, FINANCE_COLUMNS)

        elif view in ("qc", "technician"):
            is_qc = view == "qc"
            self.title_label.setText("کارتابل کنترل کیفیت" if is_qc else "کارتابل تکنسین")
            tasks = data.get("tasks", [])
            self.stats_row.addWidget(make_stat_card("باز", data.get("open_count", 0)))
            self.stats_row.addWidget(make_stat_card("بسته‌شده", data.get("closed_count", 0)))
            self.stats_row.addWidget(make_stat_card("مجموع", data.get("total_count", 0)))
            if is_qc:
                self.stats_row.addWidget(make_stat_card("در مرحله‌ی QC", data.get("qc_open", 0)))
            self._set_rows(tasks, TASK_COLUMNS)
            self.apply_status_btn.setVisible(False)
            self.status_combo.setVisible(False)

        else:  # reception / manager
            self.title_label.setText("کارتابل پذیرش")
            rows = data.get("requests", [])
            self.stats_row.addWidget(make_stat_card("مجموع", data.get("total_count", 0)))
            self.stats_row.addWidget(make_stat_card("در انتظار بررسی", data.get("pending_count", 0)))
            self.stats_row.addWidget(make_stat_card("در حال تعمیر", data.get("repairing_count", 0)))
            self.stats_row.addWidget(make_stat_card("تحویل‌شده", data.get("delivered_count", 0)))
            self._set_rows(rows, RECEPTION_COLUMNS)

    def _set_rows(self, rows, columns):
        self._all_rows = list(rows or [])
        self._columns = columns
        statuses = []
        kinds = []
        provinces = []
        technicians = []
        for r in self._all_rows:
            if r.get('status') and r.get('status') not in statuses: statuses.append(r.get('status'))
            kind = r.get('kind') or r.get('request_category') or r.get('service_type')
            if kind and kind not in kinds: kinds.append(kind)
            province = r.get('province')
            technician = r.get('assigned_technician') or r.get('representative_name')
            if province and province not in provinces: provinces.append(province)
            if technician and technician not in technicians: technicians.append(technician)
        self.status_filter.blockSignals(True); self.status_filter.clear(); self.status_filter.addItem('همه وضعیت‌ها','')
        for x in statuses: self.status_filter.addItem(str(x), x)
        self.status_filter.blockSignals(False)
        self.kind_filter.blockSignals(True); self.kind_filter.clear(); self.kind_filter.addItem('همه انواع','')
        for x in kinds: self.kind_filter.addItem(str(x), x)
        self.kind_filter.blockSignals(False)
        self.province_filter.blockSignals(True); self.province_filter.clear(); self.province_filter.addItem('همه استان‌ها','')
        for x in sorted(provinces, key=str): self.province_filter.addItem(str(x), x)
        self.province_filter.blockSignals(False)
        self.technician_filter.blockSignals(True); self.technician_filter.clear(); self.technician_filter.addItem('همه مسئولان','')
        for x in sorted(technicians, key=str): self.technician_filter.addItem(str(x), x)
        self.technician_filter.blockSignals(False)
        self._render_filtered()

    def _apply_filters(self, *_):
        self._render_filtered()

    def _render_filtered(self):
        q = self.search_edit.text().strip().lower()
        status = self.status_filter.currentData() or ''
        kind = self.kind_filter.currentData() or ''
        province = self.province_filter.currentData() or ''
        technician = self.technician_filter.currentData() or ''
        delayed = self.delay_filter.isChecked()
        rows = []
        for r in self._all_rows:
            hay = ' '.join(str(r.get(k) or '') for k in ('customer_name','serial_number','reception_no','id','device_type','assigned_technician','invoice_number','tracking_number')).lower()
            rk = r.get('kind') or r.get('request_category') or r.get('service_type') or ''
            if q and q not in hay: continue
            if status and r.get('status') != status: continue
            if kind and rk != kind: continue
            if province and r.get('province') != province: continue
            if technician and (r.get('assigned_technician') or r.get('representative_name')) != technician: continue
            if delayed and not r.get('is_delayed'): continue
            rows.append(r)
        self.table.setSortingEnabled(False)
        fill_table(self.table, rows, self._columns)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        if self._current_view:
            self.subtitle_label.setText(f"{len(rows)} مورد از {len(self._all_rows)} مورد")

    def _open_selected(self, row, _column):
        if row < 0:
            return
        # جدول پس از فیلتر شدن با ترتیب همان لیست filtered رندر شده است؛ دوباره آن را پیدا می‌کنیم.
        q = self.search_edit.text().strip().lower(); status=self.status_filter.currentData() or ''; kind=self.kind_filter.currentData() or ''; province=self.province_filter.currentData() or ''; technician=self.technician_filter.currentData() or ''; delayed=self.delay_filter.isChecked()
        visible=[]
        for r in self._all_rows:
            hay=' '.join(str(r.get(k) or '') for k in ('customer_name','serial_number','reception_no','id','device_type','assigned_technician','invoice_number','tracking_number')).lower()
            rk=r.get('kind') or r.get('request_category') or r.get('service_type') or ''
            if q and q not in hay: continue
            if status and r.get('status') != status: continue
            if kind and rk != kind: continue
            if province and r.get('province') != province: continue
            if technician and (r.get('assigned_technician') or r.get('representative_name')) != technician: continue
            if delayed and not r.get('is_delayed'): continue
            visible.append(r)
        if not (0 <= row < len(visible)): return
        item=visible[row]; req_id=item.get('id')
        if not req_id: return
        try:
            from PyQt5.QtWidgets import QDialog
            from ui_service_detail import (InternalRepairDetailDialog, ExternalRepairDetailDialog,
                InstallationRequestDetailDialog, InstallationRegisterDetailDialog, InspectionDetailDialog)
            subtype=item.get('request_subtype') or ''
            category=item.get('request_category') or ''
            service=item.get('service_type') or ''
            if subtype == 'درخواست نصب': dlg=InstallationRequestDetailDialog(self.client,int(req_id),self)
            elif subtype == 'ثبت نصب': dlg=InstallationRegisterDetailDialog(self.client,int(req_id),self)
            elif category == 'بررسی و بازدید': dlg=InspectionDetailDialog(self.client,int(req_id),self)
            elif service == 'در محل': dlg=ExternalRepairDetailDialog(self.client,int(req_id),self)
            else: dlg=InternalRepairDetailDialog(self.client,int(req_id),self)
            dlg.exec_()
            self.reload()
        except Exception as e:
            QMessageBox.warning(self, 'باز کردن پرونده', f'باز کردن پرونده ناموفق بود: {e}')
