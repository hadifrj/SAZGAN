# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTabWidget, QMessageBox, QGridLayout, QFrame,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table, make_stat_card

WAGE_REPORT_COLUMNS = [
    ("id", "شناسه"), ("representative_name", "نماینده"), ("work_description", "شرح"),
    ("amount", "مبلغ"), ("calc_date", "تاریخ"), ("notes", "یادداشت"),
]

AUDIT_COLUMNS = [
    ("id", "شناسه"), ("user_name", "کاربر"), ("action", "عملیات"),
    ("entity_id", "شناسه مورد"), ("details", "جزئیات"), ("created_at", "تاریخ"),
]


def _stat_box(title, value):
    # Compatibility wrapper: all summary cards now use the shared card system.
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


class WageReportTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.clicked.connect(self.reload)
        self.total_label = QLabel("")
        self.total_label.setStyleSheet("font-weight:700;")
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.total_label)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.reload()

    def reload(self):
        try:
            data = self.client.wage_report()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.total_label.setText(f"جمع کل ماه {data.get('month','')}/{data.get('year','')}: {data.get('total', 0):,.0f}")
        fill_table(self.table, data.get("rows", []), WAGE_REPORT_COLUMNS)


class ManagerDashboardTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.clicked.connect(self.reload)
        self.stats_layout = QGridLayout()
        self.prov_table = QTableWidget()
        self.prov_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table = QTableWidget()
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addWidget(self.refresh_btn)
        layout.addLayout(self.stats_layout)
        layout.addWidget(QLabel("توزیع استانی"))
        layout.addWidget(self.prov_table)
        layout.addWidget(QLabel("توزیع وضعیت"))
        layout.addWidget(self.status_table)
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
            data = self.client.manager_dashboard()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self._clear_stats()
        self.stats_layout.addWidget(_stat_box("کل", data.get("total", 0)), 0, 0)
        self.stats_layout.addWidget(_stat_box("باز", data.get("open", 0)), 0, 1)
        self.stats_layout.addWidget(_stat_box("رد پیش‌فاکتور", data.get("rejected", 0)), 0, 2)

        fill_table(self.prov_table, data.get("by_province", []), [("province", "استان"), ("c", "تعداد")])
        fill_table(self.status_table, data.get("by_status", []), [("status", "وضعیت"), ("c", "تعداد")])


class AuditLogTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.q_edit = QLineEdit()
        self.q_edit.setPlaceholderText("جست‌وجو در جزئیات/کاربر/شناسه...")
        self.action_edit = QLineEdit()
        self.action_edit.setPlaceholderText("فیلتر نوع عملیات (اختیاری)")
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.q_edit.returnPressed.connect(self.reload)

        top = QHBoxLayout()
        top.addWidget(self.search_btn)
        top.addWidget(self.q_edit)
        top.addWidget(self.action_edit)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.reload()

    def reload(self):
        try:
            data = self.client.audit_filter(self.q_edit.text().strip(), self.action_edit.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        fill_table(self.table, data.get("rows", []), AUDIT_COLUMNS)


class ImprovementsPage(QWidget):
    """Improvements support for the native client."""

    def __init__(self, client):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        tabs = QTabWidget()
        tabs.addTab(WageReportTab(client), "گزارش دستمزد")
        tabs.addTab(ManagerDashboardTab(client), "داشبورد مدیریت")
        tabs.addTab(AuditLogTab(client), "گزارش رخدادها (Audit Log)")
        self.tabs = tabs
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

    def open_tab(self, index):
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))
        page = self.tabs.currentWidget()
        if hasattr(page, "reload"):
            page.reload()
