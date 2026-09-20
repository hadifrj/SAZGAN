# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QTabWidget, QFileDialog, QMessageBox, QGroupBox,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import busy



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


class ExportTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.list = QListWidget()
        self.download_btn = QPushButton("دانلود خروجی اکسل")
        self.download_btn.clicked.connect(self.do_export)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("یک مورد را برای خروجی گرفتن انتخاب کنید:"))
        layout.addWidget(self.list)
        layout.addWidget(self.download_btn)
        self.setLayout(layout)

        self.targets = []

    def set_targets(self, targets):
        self.targets = targets
        self.list.clear()
        for t in targets:
            item = QListWidgetItem(t["label"])
            item.setData(Qt.UserRole, t["key"])
            self.list.addItem(item)

    def do_export(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.information(self, "خروجی", "یک مورد را از لیست انتخاب کنید.")
            return
        module = item.data(Qt.UserRole)
        try:
            filename, content = self.client.export_file(module)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل خروجی", filename, "Excel Files (*.xlsx)")
        if not save_path:
            return
        with open(save_path, "wb") as f:
            f.write(content)
        QMessageBox.information(self, "خروجی", f"فایل با موفقیت ذخیره شد:\n{save_path}")


class ImportTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.list = QListWidget()
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.upload_btn = QPushButton("انتخاب فایل xlsx و آپلود")
        self.upload_btn.clicked.connect(self.do_import)

        self.list.currentRowChanged.connect(self._show_hint)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("یک مورد را برای ورود اطلاعات انتخاب کنید:"))
        layout.addWidget(self.list)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.upload_btn)
        self.setLayout(layout)

        self.targets = []

    def set_targets(self, targets):
        self.targets = targets
        self.list.clear()
        for t in targets:
            item = QListWidgetItem(t["label"])
            item.setData(Qt.UserRole, t)
            self.list.addItem(item)

    def _show_hint(self, row):
        if row < 0 or row >= len(self.targets):
            self.hint_label.setText("")
            return
        self.hint_label.setText(self.targets[row].get("hint", ""))

    def do_import(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.information(self, "ورود اطلاعات", "یک مورد را از لیست انتخاب کنید.")
            return
        target = item.data(Qt.UserRole)
        module = target["key"]

        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل اکسل", "", "Excel Files (*.xlsx)")
        if not path:
            return

        try:
            result = self.client.import_file(module, path)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        if result["ok"]:
            QMessageBox.information(self, "ورود اطلاعات", f"با موفقیت انجام شد. تعداد رکورد: {result['count']}")
        else:
            QMessageBox.critical(self, "خطا", result["msg"] or "ورود اطلاعات ناموفق بود.")


class DataHubPage(QWidget):
    """Export/import support for the native client (no backend changes needed)."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.export_tab = ExportTab(client)
        self.import_tab = ImportTab(client)

        tabs = QTabWidget()
        tabs.addTab(self.export_tab, "خروجی (Export)")
        tabs.addTab(self.import_tab, "ورود اطلاعات (Import)")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

        self.reload()

    def reload(self):
        try:
            data = self.client.data_hub_targets()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.export_tab.set_targets(data.get("export_targets", []))
        self.import_tab.set_targets(data.get("import_targets", []))
