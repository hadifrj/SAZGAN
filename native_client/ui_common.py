# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QFrame, QLabel, QVBoxLayout, QApplication, QPushButton, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from contextlib import contextmanager
import csv
from config import load_config


# ---------------------------------------------------------------------------
# Shared Native card system
# ---------------------------------------------------------------------------
# Semantic accent names keep module identity stable while card surfaces remain
# theme-driven.  Pages should use these names instead of hard-coded colors.
MODULE_ACCENTS = {
    "customers": "#2563eb",
    "warehouse": "#f59e0b",
    "finance": "#059669",
    "reports": "#7c3aed",
    "settings": "#64748b",
    "system": "#ef4444",
    "service": "#0891b2",
    "data": "#0f766e",
}


def accent_color(name, fallback="settings"):
    return MODULE_ACCENTS.get(name, MODULE_ACCENTS.get(fallback, "#64748b"))


def accent_soft(name, fallback="settings"):
    # Kept deliberately subtle so the main card surface still follows the theme.
    return {
        "customers": "#eff6ff", "warehouse": "#fff7ed",
        "finance": "#ecfdf5", "reports": "#f5f3ff",
        "settings": "#f8fafc", "system": "#fef2f2",
        "service": "#ecfeff", "data": "#f0fdfa",
    }.get(name, "#f8fafc")


def module_card_style(accent_name):
    # Shared preference with Web/PWA: default (legacy neutral), module (colored), mono.
    ui_theme = str(load_config().get("ui_theme", "minimal_premium") or "minimal_premium").lower()
    mode = {"light_modern_indigo":"default", "dark_modern_indigo":"default", "minimal_premium":"mono"}.get(ui_theme, str(load_config().get("card_theme", "default") or "default").lower())
    accent = accent_color(accent_name)
    soft = accent_soft(accent_name)
    if mode == "default":
        accent = "#4f46e5" if ui_theme == "light_modern_indigo" else "#6366f1"; soft = "#eef2ff" if ui_theme == "light_modern_indigo" else "#1f2937"
    elif mode == "mono":
        accent = "#111827"; soft = "#f3f4f6"
    if mode == "mono":
        return f"""
            QFrame[cardRole="module"] {{ background: palette(base); border: 1px solid #e5e7eb; border-radius: 12px; }}
            QFrame[cardRole="module"]:hover {{ background: palette(base); border-color: #9ca3af; }}
            QLabel#moduleCardIcon {{ color: #111827; font-size: 18pt; font-weight: 800; }}
            QLabel#moduleCardTitle {{ color: #111827; font-size: 11pt; font-weight: 800; }}
            QLabel#moduleCardDescription {{ color: #6b7280; font-size: 8.8pt; }}
            QLabel#moduleCardAction {{ color: #111827; font-size: 8.8pt; font-weight: 800; }}
            QToolButton#moduleCardMenu {{ color: #6b7280; background: transparent; border: 0; border-radius: 8px; padding: 3px 6px; }}
            QToolButton#moduleCardMenu:hover {{ background: #f3f4f6; color: #111827; }}
        """
    return f"""
        QFrame[cardRole="module"] {{
            background: palette(base); border: 1px solid #e2e8f0; border-right: 3px solid {accent}; border-radius: 12px;
        }}
        QFrame[cardRole="module"]:hover {{ background: {soft}; border-color: {accent}; border-right: 4px solid {accent}; }}
        QLabel#moduleCardIcon {{ color: {accent}; font-size: 18pt; font-weight: 800; }}
        QLabel#moduleCardTitle {{ color: #0f172a; font-size: 11pt; font-weight: 800; }}
        QLabel#moduleCardDescription {{ color: #64748b; font-size: 8.8pt; }}
        QLabel#moduleCardAction {{ color: {accent}; font-size: 8.8pt; font-weight: 800; }}
        QToolButton#moduleCardMenu {{ color: #64748b; background: transparent; border: 0; border-radius: 8px; padding: 3px 6px; }}
        QToolButton#moduleCardMenu:hover {{ background: {soft}; color: {accent}; }}
    """


def style_table(table: QTableWidget):
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setShowGrid(False)
    table.setSortingEnabled(True)
    table.setWordWrap(False)


def fill_table(table: QTableWidget, rows: list, columns: list):
    style_table(table)
    table.setSortingEnabled(False)
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([label for _, label in columns])
    table.setRowCount(len(rows) if rows else 1)
    if not rows:
        item = QTableWidgetItem("موردی برای نمایش وجود ندارد.")
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(0, 0, item)
        table.setSpan(0, 0, 1, max(1, len(columns)))
        table.setSortingEnabled(True)
        return
    for i, row in enumerate(rows):
        for j, (key, _label) in enumerate(columns):
            item = QTableWidgetItem(str(row.get(key) or ""))
            item.setTextAlignment(0x0004 | 0x0080)  # AlignRight | AlignVCenter
            table.setItem(i, j, item)
    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


def make_card(title=None, subtitle=None):
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    card.setProperty("cardRole", "content")
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
    if subtitle:
        label = QLabel(subtitle)
        label.setObjectName("pageSubtitle")
        label.setWordWrap(True)
        layout.addWidget(label)
    return card, layout


def make_stat_card(title, value):
    card = QFrame()
    card.setObjectName("statCard")
    layout = QVBoxLayout(card)
    card.setProperty("cardRole", "stat")
    card.setMinimumHeight(96)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(4)
    value_label = QLabel(str(value))
    value_label.setObjectName("statValue")
    title_label = QLabel(title)
    title_label.setObjectName("statTitle")
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    return card


@contextmanager
def busy(button=None, text=None):
    """Small shared busy state for synchronous Native requests."""
    old_text = button.text() if button is not None else None
    if button is not None:
        button.setEnabled(False)
        if text:
            button.setText(text)
    app = QApplication.instance()
    if app:
        app.setOverrideCursor(Qt.WaitCursor)
        app.processEvents()
    try:
        yield
    finally:
        if app:
            app.restoreOverrideCursor()
        if button is not None:
            button.setEnabled(True)
            if old_text is not None:
                button.setText(old_text)


def show_loading(table, message="در حال بارگذاری..."):
    table.setRowCount(1)
    table.setColumnCount(1)
    item = QTableWidgetItem(message)
    item.setTextAlignment(Qt.AlignCenter)
    table.setItem(0, 0, item)


def show_empty(table, message="نتیجه‌ای یافت نشد."):
    """Render a clear empty state instead of a blank table."""
    table.clearContents()
    table.setRowCount(1)
    if table.columnCount() < 1:
        table.setColumnCount(1)
    item = QTableWidgetItem(message)
    item.setTextAlignment(Qt.AlignCenter)
    table.setItem(0, 0, item)
    table.setSpan(0, 0, 1, max(1, table.columnCount()))


def export_table_csv(parent, table, default_name="export.csv"):
    path, _ = QFileDialog.getSaveFileName(parent, "خروجی CSV", default_name, "CSV (*.csv)")
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([table.horizontalHeaderItem(i).text() if table.horizontalHeaderItem(i) else "" for i in range(table.columnCount())])
            for r in range(table.rowCount()):
                if table.item(r, 0) and table.item(r, 0).text() == "در حال بارگذاری...":
                    continue
                writer.writerow([table.item(r, c).text() if table.item(r, c) else "" for c in range(table.columnCount())])
        QMessageBox.information(parent, "موفقیت", "خروجی CSV با موفقیت ذخیره شد.")
    except OSError as e:
        QMessageBox.critical(parent, "خطا", f"ذخیره خروجی ناموفق بود: {e}")
