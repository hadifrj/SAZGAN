# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QComboBox, QLabel, QMessageBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table as _fill_table

INTERNAL_COLUMNS = [
    ("reception_no", "شماره پذیرش"), ("device_type", "نوع دستگاه"), ("device_model", "مدل"),
    ("warehouse_code", "کد انبار"), ("part_name", "نام قطعه"), ("quantity", "تعداد"),
    ("serial_good", "سریال سالم"), ("serial_defective", "سریال معیوب"),
    ("assigned_technician", "تکنسین"), ("status", "وضعیت"), ("created_at", "تاریخ"),
]

EXTERNAL_COLUMNS = [
    ("reception_no", "شماره پذیرش"), ("province", "استان"), ("device_type", "نوع دستگاه"),
    ("device_model", "مدل"), ("warehouse_code", "کد انبار"), ("part_name", "نام قطعه"),
    ("quantity", "تعداد"), ("serial_good", "سریال سالم"), ("serial_defective", "سریال معیوب"),
    ("representative_name", "نماینده"), ("status", "وضعیت"), ("created_at", "تاریخ"),
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


class WarehouseInternalTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو (شماره پذیرش، سریال، قطعه، تکنسین...)")
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.search_edit.returnPressed.connect(self.reload)

        top = QHBoxLayout()
        top.addWidget(self.search_btn)
        top.addWidget(self.search_edit)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.reload()

    def reload(self):
        try:
            data = self.client.warehouse_internal(self.search_edit.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        _fill_table(self.table, data.get("rows", []), INTERNAL_COLUMNS)


class WarehouseExternalTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو (شماره پذیرش، سریال، قطعه، نماینده...)")
        self.province_combo = QComboBox()
        self.province_combo.addItem("همه استان‌ها", "")
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.search_edit.returnPressed.connect(self.reload)
        self.province_combo.currentIndexChanged.connect(self.reload)

        top = QHBoxLayout()
        top.addWidget(self.search_btn)
        top.addWidget(self.search_edit)
        top.addWidget(self.province_combo)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self._provinces_loaded = False
        self.reload()

    def reload(self):
        province = self.province_combo.currentData() or ""
        try:
            data = self.client.warehouse_external(self.search_edit.text().strip(), province)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        if not self._provinces_loaded:
            self._provinces_loaded = True
            self.province_combo.blockSignals(True)
            for p in data.get("provinces", []):
                self.province_combo.addItem(p, p)
            self.province_combo.blockSignals(False)

        _fill_table(self.table, data.get("rows", []), EXTERNAL_COLUMNS)


class WarehousePage(QWidget):
    """Warehouse support for the native client."""

    def __init__(self, client):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        tabs = QTabWidget()
        tabs.addTab(WarehouseInternalTab(client), "انبار داخلی (تعمیرات کارخانه)")
        tabs.addTab(WarehouseExternalTab(client), "انبار خارجی (نمایندگان)")
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.tabs = tabs
        self.setLayout(layout)

    def open_tab(self, index):
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))
        page = self.tabs.currentWidget()
        if hasattr(page, "reload"):
            page.reload()
