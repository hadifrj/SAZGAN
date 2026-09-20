# -*- coding: utf-8 -*-
"""فاز ۸ب (پورت‌شده روی V4.9.6): routes/settings.py - «طرف حساب‌ها» (مشتریان).

فقط مدیریت مشتریان (لیست/ایجاد/ویرایش/آرشیو) - نمایندگان و دسترسی‌ها که تو
همون هاب وب کنار «طرف حساب‌ها» هستن، هنوز جزو این فاز نیستن.
"""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table

CUSTOMER_COLUMNS = [
    ("id", "شناسه"), ("name", "نام"), ("person_type", "نوع"), ("phone", "تلفن"),
    ("province", "استان"), ("city", "شهر"),
    ("equipment_manager_name", "مسئول تجهیزات"), ("equipment_manager_mobile", "موبایل مسئول"),
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


class CustomersPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        self._editing_id = None
        self._provinces_loaded = False

        title = QLabel("طرف حساب‌ها (مشتریان)")
        title.setObjectName("pageTitle")
        sub = QLabel("لیست، ثبت، ویرایش و آرشیو مشتریان")
        sub.setObjectName("pageSubtitle")

        # ---- فرم ایجاد/ویرایش ----
        form_card = QFrame()
        form_card.setObjectName("card")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(8)
        self.form_title = QLabel("مشتری جدید")
        self.form_title.setObjectName("sectionTitle")
        form_layout.addWidget(self.form_title)

        self.name_edit = QLineEdit()
        self.person_type_combo = QComboBox()
        self.person_type_combo.addItem("حقیقی", "حقیقی")
        self.person_type_combo.addItem("حقوقی", "حقوقی")
        self.phone_edit = QLineEdit()
        self.national_id_edit = QLineEdit()
        self.economic_code_edit = QLineEdit()
        self.province_combo = QComboBox()
        self.province_combo.setEditable(True)
        self.county_edit = QLineEdit()
        self.city_edit = QLineEdit()
        self.address_edit = QLineEdit()
        self.postal_code_edit = QLineEdit()
        self.manager_name_edit = QLineEdit()
        self.manager_mobile_edit = QLineEdit()

        grid = QFormLayout()
        grid.addRow("نام:", self.name_edit)
        grid.addRow("نوع شخص:", self.person_type_combo)
        grid.addRow("تلفن:", self.phone_edit)
        grid.addRow("کد ملی/شناسه:", self.national_id_edit)
        grid.addRow("کد اقتصادی:", self.economic_code_edit)
        grid.addRow("استان:", self.province_combo)
        grid.addRow("شهرستان:", self.county_edit)
        grid.addRow("شهر:", self.city_edit)
        grid.addRow("آدرس:", self.address_edit)
        grid.addRow("کد پستی:", self.postal_code_edit)
        grid.addRow("نام مسئول تجهیزات:", self.manager_name_edit)
        grid.addRow("موبایل مسئول تجهیزات:", self.manager_mobile_edit)
        form_layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.submit_btn = QPushButton("ثبت مشتری")
        self.submit_btn.clicked.connect(self._submit)
        self.cancel_edit_btn = QPushButton("لغو ویرایش")
        self.cancel_edit_btn.setProperty("variant", "secondary")
        self.cancel_edit_btn.clicked.connect(self._reset_form)
        self.cancel_edit_btn.setVisible(False)
        btn_row.addWidget(self.submit_btn)
        btn_row.addWidget(self.cancel_edit_btn)
        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form_layout.addWidget(self.status_label)

        # ---- جست‌وجو + جدول ----
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو در نام، تلفن، شهر، کد ملی...")
        self.search_edit.returnPressed.connect(self.reload)
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(self.reload)
        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.setProperty("variant", "secondary")
        self.reload_btn.clicked.connect(self.reload)
        self.edit_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
        self.edit_btn.clicked.connect(self._load_selected_for_edit)
        self.archive_btn = QPushButton("آرشیو ردیف انتخاب‌شده")
        self.archive_btn.setProperty("variant", "danger")
        self.archive_btn.clicked.connect(self._archive_selected)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_btn)
        search_row.addWidget(self.reload_btn)

        table_actions = QHBoxLayout()
        table_actions.addWidget(self.edit_btn)
        table_actions.addWidget(self.archive_btn)
        table_actions.addStretch()

        self.table = QTableWidget()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(12)
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(form_card)
        root.addLayout(search_row)
        root.addWidget(self.table, 1)
        root.addLayout(table_actions)

        self.reload()

    # ---- data ----
    def reload(self):
        q = self.search_edit.text().strip()
        try:
            data = self.client.settings_customers(q or None)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        if not self._provinces_loaded:
            self.province_combo.clear()
            for p in data.get("provinces", []):
                self.province_combo.addItem(p, p)
            self._provinces_loaded = True
        fill_table(self.table, data.get("customers", []), CUSTOMER_COLUMNS)

    def _selected_row_dict(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        d = {}
        for col, (key, _label) in enumerate(CUSTOMER_COLUMNS):
            item = self.table.item(row, col)
            d[key] = item.text() if item else ""
        return d

    # ---- form ----
    def _reset_form(self):
        self._editing_id = None
        self.form_title.setText("مشتری جدید")
        self.submit_btn.setText("ثبت مشتری")
        self.cancel_edit_btn.setVisible(False)
        for w in (self.name_edit, self.phone_edit, self.national_id_edit, self.economic_code_edit,
                  self.county_edit, self.city_edit, self.address_edit, self.postal_code_edit,
                  self.manager_name_edit, self.manager_mobile_edit):
            w.clear()
        self.person_type_combo.setCurrentIndex(0)
        self.status_label.setText("")

    def _load_selected_for_edit(self):
        row = self._selected_row_dict()
        if not row:
            QMessageBox.information(self, "انتخاب ردیف", "ابتدا یک مشتری را از جدول انتخاب کنید.")
            return
        self._editing_id = row.get("id")
        self.form_title.setText(f"ویرایش مشتری #{self._editing_id}")
        self.submit_btn.setText("ذخیره تغییرات")
        self.cancel_edit_btn.setVisible(True)
        self.name_edit.setText(row.get("name", ""))
        idx = self.person_type_combo.findData(row.get("person_type") or "حقیقی")
        self.person_type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.phone_edit.setText(row.get("phone", ""))
        pidx = self.province_combo.findData(row.get("province") or "")
        if pidx >= 0:
            self.province_combo.setCurrentIndex(pidx)
        else:
            self.province_combo.setEditText(row.get("province", ""))
        self.city_edit.setText(row.get("city", ""))
        self.manager_name_edit.setText(row.get("equipment_manager_name", ""))
        self.manager_mobile_edit.setText(row.get("equipment_manager_mobile", ""))
        # national_id/economic_code/county/address/postal_code are not in the
        # table columns (kept short); re-fetched from the archive-less list
        # isn't necessary for a quick edit, but full values are sent back
        # untouched if left blank only when the user doesn't retype them -
        # in that case the server keeps whatever is in these fields (empty).
        self.status_label.setText(
            "توجه: کد ملی/اقتصادی، شهرستان، آدرس و کدپستی در جدول نیستند - در صورت نیاز دوباره وارد کنید."
        )

    def _form_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "person_type": self.person_type_combo.currentData(),
            "phone": self.phone_edit.text().strip(),
            "national_id": self.national_id_edit.text().strip(),
            "economic_code": self.economic_code_edit.text().strip(),
            "province": self.province_combo.currentText().strip(),
            "county": self.county_edit.text().strip(),
            "city": self.city_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "postal_code": self.postal_code_edit.text().strip(),
            "equipment_manager_name": self.manager_name_edit.text().strip(),
            "equipment_manager_mobile": self.manager_mobile_edit.text().strip(),
        }

    def _submit(self):
        data = self._form_data()
        if not data["name"] or not data["city"]:
            QMessageBox.warning(self, "فیلدهای الزامی", "نام و شهر الزامی است.")
            return
        self.submit_btn.setEnabled(False)
        try:
            if self._editing_id:
                self.client.settings_customer_edit(self._editing_id, data)
                self.status_label.setText("تغییرات ذخیره شد.")
            else:
                self.client.settings_customer_new(data)
                self.status_label.setText("مشتری با موفقیت ثبت شد.")
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

    def _archive_selected(self):
        row = self._selected_row_dict()
        if not row:
            QMessageBox.information(self, "انتخاب ردیف", "ابتدا یک مشتری را از جدول انتخاب کنید.")
            return
        if QMessageBox.question(self, "تأیید", f"مشتری «{row.get('name')}» آرشیو شود؟") != QMessageBox.Yes:
            return
        try:
            self.client.settings_customer_archive(row.get("id"))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.reload()
