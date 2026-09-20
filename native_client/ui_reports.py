# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QLineEdit, QCheckBox,
    QTabWidget, QMessageBox, QGridLayout, QFrame, QComboBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table, export_table_csv, show_loading, make_stat_card


def _stat_box(title, value):
    return make_stat_card(title, value)



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


class DashboardTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.clicked.connect(self.reload)

        self.stats_layout = QGridLayout()
        self.cat_table = QTableWidget()
        self.cat_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.province_table = QTableWidget()
        self.province_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addWidget(self.refresh_btn)
        layout.addLayout(self.stats_layout)
        layout.addWidget(QLabel("درخواست‌های باز به تفکیک دسته"))
        layout.addWidget(self.cat_table)
        layout.addWidget(QLabel("پرکارترین استان‌ها (باز)"))
        layout.addWidget(self.province_table)
        self.setLayout(layout)

    def _clear_stats(self):
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def reload(self):
        try:
            data = self.client.reports_dashboard()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        self._clear_stats()
        self.stats_layout.addWidget(_stat_box("کل درخواست‌ها", data.get("total", 0)), 0, 0)
        self.stats_layout.addWidget(_stat_box("باز", data.get("open", 0)), 0, 1)
        self.stats_layout.addWidget(_stat_box("بسته‌شده", data.get("closed", 0)), 0, 2)
        self.stats_layout.addWidget(_stat_box("دارای تأخیر", data.get("delayed_count", 0)), 0, 3)
        self.stats_layout.addWidget(_stat_box("میانگین روز در وضعیت", data.get("avg_days", 0)), 0, 4)

        open_by_cat = data.get("open_by_cat", {})
        rows = [{"cat": k, "count": v} for k, v in open_by_cat.items()]
        fill_table(self.cat_table, rows, [("cat", "دسته"), ("count", "تعداد")])

        prov_rows = [{"prov": p, "count": c} for p, c in data.get("province_top", [])]
        fill_table(self.province_table, prov_rows, [("prov", "استان"), ("count", "تعداد")])


class ManagementTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.clicked.connect(self.reload)

        self.stats_layout = QGridLayout()
        self.tech_table = QTableWidget()
        self.tech_export = QPushButton("خروجی CSV")
        self.tech_export.clicked.connect(lambda: export_table_csv(self, self.tech_table, "management-technicians.csv"))
        self.tech_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.prov_table = QTableWidget()
        self.prov_export = QPushButton("خروجی CSV")
        self.prov_export.clicked.connect(lambda: export_table_csv(self, self.prov_table, "management-provinces.csv"))
        self.prov_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addWidget(self.refresh_btn)
        layout.addLayout(self.stats_layout)
        tech_head=QHBoxLayout(); tech_head.addWidget(QLabel("تأخیر به تفکیک تکنسین")); tech_head.addStretch(1); tech_head.addWidget(self.tech_export)
        layout.addLayout(tech_head)
        layout.addWidget(self.tech_table)
        prov_head=QHBoxLayout(); prov_head.addWidget(QLabel("تأخیر به تفکیک استان")); prov_head.addStretch(1); prov_head.addWidget(self.prov_export)
        layout.addLayout(prov_head)
        layout.addWidget(self.prov_table)
        self.setLayout(layout)
        self.reload()

    def _clear_stats(self):
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def reload(self):
        try:
            data = self.client.reports_management()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        self._clear_stats()
        self.stats_layout.addWidget(_stat_box("کل پذیرش", data.get("total_accept", 0)), 0, 0)
        self.stats_layout.addWidget(_stat_box("باز", data.get("open_total", 0)), 0, 1)
        self.stats_layout.addWidget(_stat_box("بسته‌شده", data.get("closed_total", 0)), 0, 2)
        self.stats_layout.addWidget(_stat_box("دارای تأخیر", data.get("delayed_total", 0)), 0, 3)
        self.stats_layout.addWidget(_stat_box("میانگین روز", data.get("avg_days", 0)), 0, 4)
        self.stats_layout.addWidget(_stat_box("تعمیر داخلی", data.get("n_internal", 0)), 1, 0)
        self.stats_layout.addWidget(_stat_box("تعمیر خارجی", data.get("n_external", 0)), 1, 1)
        self.stats_layout.addWidget(_stat_box("نصب و آموزش", data.get("n_install", 0)), 1, 2)
        self.stats_layout.addWidget(_stat_box("بازدید", data.get("n_visit", 0)), 1, 3)

        tech_rows = [{"tech": t, "count": c} for t, c in data.get("by_tech", [])]
        fill_table(self.tech_table, tech_rows, [("tech", "تکنسین"), ("count", "تعداد تأخیر")])

        prov_rows = [{"prov": p, "count": c} for p, c in data.get("by_prov", [])]
        fill_table(self.prov_table, prov_rows, [("prov", "استان"), ("count", "تعداد تأخیر")])



class DelayMatrixTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        from PyQt5.QtWidgets import QComboBox  # ensure available even if top-level import was stale
        self.kind=QComboBox(); self.kind.addItem("تعمیر داخلی","internal"); self.kind.addItem("تعمیر خارجی","external"); self.kind.addItem("نصب","install"); self.kind.addItem("بازدید","visit")
        self.serial=QLineEdit(); self.serial.setPlaceholderText("سریال")
        self.province=QLineEdit(); self.province.setPlaceholderText("استان")
        self.only=QCheckBox("فقط دارای تأخیر")
        btn=QPushButton("بارگذاری"); btn.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(self.kind); bar.addWidget(self.serial); bar.addWidget(self.province); bar.addWidget(self.only); bar.addWidget(btn)
        self.table=QTableWidget(); self.info=QLabel("")
        self.export_btn=QPushButton("خروجی CSV"); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "delay-matrix.csv"))
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.info); lay.addWidget(self.export_btn); lay.addWidget(self.table); self.reload()
    def reload(self):
        try: d=self.client.delay_matrix(self.kind.currentData(),self.serial.text().strip(),self.province.text().strip(),self.only.isChecked())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        stages=d.get('stages',[]); cols=[('serial','سریال'),('customer','مشتری'),('reception_no','پذیرش'),('status','وضعیت'),('total','مجموع تأخیر')]
        cols += [(f'stage_{i}',st.get('name',str(st)) if isinstance(st,dict) else str(st)) for i,st in enumerate(stages)]
        rows=[]
        for r in d.get('rows',[]):
            x=dict(r); x.update({f'stage_{i}': (r.get('stages',{}).get(st.get('name')) if isinstance(st,dict) else r.get('stages',{}).get(st)) for i,st in enumerate(stages)}); rows.append(x)
        fill_table(self.table,rows,cols); self.info.setText(f"تعداد پرونده‌ها: {len(rows)}")


class StageDelaysTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.search=QLineEdit(); self.search.setPlaceholderText('جستجو در پذیرش، مشتری، سریال، استان...'); self.btn=QPushButton('بارگذاری'); self.export_btn=QPushButton('خروجی CSV'); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "stage_delays.csv")); self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.btn.clicked.connect(self.reload); self.search.returnPressed.connect(self.reload)
        lay=QVBoxLayout(self); bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(self.export_btn); bar.addWidget(self.btn); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try:d=self.client.report_stage_delays(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        fill_table(self.table,d.get('rows',[]),[('id','شناسه'),('reception_no','پذیرش'),('customer_name','مشتری'),('serial_number','سریال'),('status','وضعیت'),('request_category','دسته'),('province','استان'),('assigned_technician','تکنسین'),('stage_count','تعداد مراحل')])


class ManagerDashboardTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.stats=QGridLayout(); self.prov=QTableWidget(); self.status=QTableWidget()
        ref=QPushButton("بارگذاری مجدد"); ref.clicked.connect(self.reload)
        lay=QVBoxLayout(self); lay.addWidget(ref); lay.addLayout(self.stats); lay.addWidget(QLabel("به تفکیک استان")); lay.addWidget(self.prov); lay.addWidget(QLabel("به تفکیک وضعیت")); lay.addWidget(self.status); self.reload()
    def reload(self):
        try:d=self.client.manager_dashboard()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        while self.stats.count():
            x=self.stats.takeAt(0); w=x.widget()
            if w:w.deleteLater()
        for i,(k,t) in enumerate((("total","کل"),("open","باز"),("rejected","رد پیش‌فاکتور"))): self.stats.addWidget(_stat_box(t,d.get(k,0)),0,i)
        fill_table(self.prov,d.get("by_province",[]),[("province","استان"),("c","تعداد")])
        fill_table(self.status,d.get("by_status",[]),[("status","وضعیت"),("c","تعداد")])

class AuditTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.q=QLineEdit(); self.q.setPlaceholderText("جستجو در کاربر، عملیات یا جزئیات...")
        self.action=QLineEdit(); self.action.setPlaceholderText("عملیات")
        self.table=QTableWidget(); self.export_btn=QPushButton("خروجی CSV"); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "audit.csv")); self.reload_btn=QPushButton("جستجو"); self.reload_btn.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(self.q,2); bar.addWidget(self.action,1); bar.addWidget(self.export_btn); bar.addWidget(self.reload_btn)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try:d=self.client.audit_filter(self.q.text().strip(),self.action.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        rows=d.get("rows",[]); cols=[("id","شناسه"),("user_name","کاربر"),("action","عملیات"),("details","جزئیات"),("created_at","تاریخ")]
        fill_table(self.table,rows,cols)


class ReportsPage(QWidget):
    """Reports support for the native client."""

    def __init__(self, client):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        tabs = QTabWidget()
        tabs.addTab(DashboardTab(client), "داشبورد آماری")
        tabs.addTab(ManagementTab(client), "گزارش مدیریتی")
        tabs.addTab(DelayMatrixTab(client), "ماتریس تأخیر (سریال)")
        tabs.addTab(StageDelaysTab(client), "گزارش تأخیر مراحل")
        tabs.addTab(ManagerDashboardTab(client), "داشبورد اجرایی")
        tabs.addTab(AuditTab(client), "ممیزی عملیات")
        self.tabs = tabs
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

    def open_tab(self, index):
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))
        page = self.tabs.currentWidget()
        if hasattr(page, "reload"):
            page.reload()
