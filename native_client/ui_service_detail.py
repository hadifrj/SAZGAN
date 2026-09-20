# -*- coding: utf-8 -*-
"""دیالوگ «نمای کامل پرونده» برای تعمیر داخلی (فاز ۶ج - اولین از ۴ نوع).

بر پایه‌ی همون دو endpoint عمومی: GET detail (خواندن state)، POST action
(هر عملیات با فیلد action=... - دقیقاً منطق وب، بدون تکرار).
"""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QWidget, QMessageBox, QFileDialog, QHeaderView, QCheckBox, QScrollArea,
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


class _RequestEditTab(QWidget):
    """ویرایش فیلدهای مجاز پرونده؛ فهرست فیلدها از منطق route وب گرفته شده است."""
    def __init__(self, parent_dialog, fields):
        super().__init__(parent_dialog)
        self.dlg = parent_dialog
        self.fields = fields
        self.inputs = {}
        self.setLayoutDirection(Qt.RightToLeft)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        for key, label, multiline, boolean in fields:
            if boolean:
                w = QCheckBox(label)
                form.addRow('', w)
            elif multiline:
                w = QPlainTextEdit()
                w.setMinimumHeight(72)
                form.addRow(label, w)
            elif key in ('city', 'device_model', 'assigned_technician'):
                # Keep the field editable (same value semantics as the web form),
                # but expose server-backed choices when available.
                w = QComboBox()
                w.setEditable(True)
                w.setInsertPolicy(QComboBox.NoInsert)
                form.addRow(label, w)
            else:
                w = QLineEdit()
                form.addRow(label, w)
            self.inputs[key] = w
        scroll.setWidget(inner)
        save = QPushButton('ذخیره تغییرات')
        save.clicked.connect(self.save)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(scroll, 1)
        lay.addWidget(save)
        lay.addWidget(self.status)
        self.save_btn = save

    def refresh(self, req):
        options = getattr(self.dlg, 'data', {}) or {}
        edit_options = options.get('edit_options') or {}
        for key, _label, _multi, _bool in self.fields:
            w = self.inputs[key]
            value = req.get(key)
            if isinstance(w, QCheckBox):
                w.setChecked(str(value or '0') in ('1', 'true', 'True'))
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText('' if value is None else str(value))
            elif isinstance(w, QComboBox):
                raw_options = edit_options.get(key) or []
                if key == 'assigned_technician':
                    raw_options = [
                        (x.get('label') or x.get('full_name') or x.get('name') or str(x.get('id')))
                        if isinstance(x, dict) else str(x)
                        for x in raw_options
                    ]
                raw_options = [str(x) for x in raw_options if str(x).strip()]
                current = '' if value is None else str(value)
                w.blockSignals(True)
                w.clear()
                if current and current not in raw_options:
                    raw_options.insert(0, current)
                w.addItem('')
                for option in raw_options:
                    if w.findText(option) < 0:
                        w.addItem(option)
                w.setCurrentText(current)
                w.blockSignals(False)
            else:
                w.setText('' if value is None else str(value))

    def save(self):
        data = {'action': 'save_fields'}
        for key, _label, _multi, _bool in self.fields:
            w = self.inputs[key]
            if isinstance(w, QCheckBox):
                data[key] = '1' if w.isChecked() else '0'
            elif isinstance(w, QPlainTextEdit):
                data[key] = w.toPlainText().strip()
            elif isinstance(w, QComboBox):
                data[key] = w.currentText().strip()
            else:
                data[key] = w.text().strip()
        self.save_btn.setEnabled(False)
        try:
            with busy(button=self.save_btn):
                self.dlg._do_action(data, 'اطلاعات پرونده با موفقیت ذخیره شد.')
        finally:
            self.save_btn.setEnabled(True)


INTERNAL_EDIT_FIELDS = [
    ('hospital_request_desc','شرح درخواست',True,False),
    ('initial_qc_desc','گزارش QC اولیه',True,False),
    ('technician_desc','شرح فنی تکنسین',True,False),
    ('final_qc_desc','گزارش QC نهایی',True,False),
    ('actions_taken','اقدامات انجام‌شده',True,False),
    ('accompanying_items','اقلام همراه',True,False),
    ('appearance_status','وضعیت ظاهری',True,False),
    ('tracking_number','شماره پیگیری',False,False),
    ('shipping_method','روش ارسال',False,False),
    ('invoice_number','شماره فاکتور',False,False),
    ('carrier_name','نام باربری',False,False),
    ('carrier_delivery_date','تاریخ تحویل باربری',False,False),
    ('assigned_technician','تکنسین مسئول',False,False),
    ('device_model','مدل دستگاه',False,False),
    ('warranty_end_date','پایان گارانتی',False,False),
    ('installation_date','تاریخ نصب',False,False),
    ('city','شهر',False,False),
    ('customer_address','آدرس مشتری',True,False),
    ('equipment_manager_name','مسئول تجهیزات',False,False),
    ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),
    ('contact_name','نام تماس',False,False),
    ('contact_phone','تلفن تماس',False,False),
]
EXTERNAL_EDIT_FIELDS = [
    ('hospital_request_desc','شرح درخواست',True,False),
    ('technician_desc','شرح فنی تکنسین/نماینده',True,False),
    ('actions_taken','اقدامات انجام‌شده',True,False),
    ('tracking_number','شماره پیگیری',False,False),
    ('shipping_method','روش ارسال',False,False),
    ('invoice_number','شماره فاکتور',False,False),
    ('carrier_name','نام باربری',False,False),
    ('carrier_delivery_date','تاریخ تحویل باربری',False,False),
    ('assigned_technician','نماینده/تکنسین مسئول',False,False),
    ('device_model','مدل دستگاه',False,False),
    ('warranty_end_date','پایان گارانتی',False,False),
    ('installation_date','تاریخ نصب',False,False),
    ('city','شهر',False,False),
    ('customer_address','آدرس مشتری',True,False),
    ('equipment_manager_name','مسئول تجهیزات',False,False),
    ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),
    ('contact_name','نام تماس',False,False),
    ('contact_phone','تلفن تماس',False,False),
]
INSTALL_REQUEST_EDIT_FIELDS = [
    ('city','شهر',False,False), ('customer_address','آدرس مشتری',True,False),
    ('equipment_manager_name','مسئول تجهیزات',False,False), ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),
    ('contact_name','نام تماس',False,False), ('contact_phone','تلفن تماس',False,False),
    ('assigned_technician','تکنسین مسئول',False,False), ('install_notes','یادداشت نصب',True,False),
]
INSPECTION_EDIT_FIELDS = [
    ('hospital_request_desc','شرح درخواست',True,False), ('technician_desc','شرح فنی',True,False),
    ('actions_taken','اقدامات انجام‌شده',True,False), ('city','شهر',False,False),
    ('customer_address','آدرس مشتری',True,False), ('equipment_manager_name','مسئول تجهیزات',False,False),
    ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False), ('contact_name','نام تماس',False,False),
    ('contact_phone','تلفن تماس',False,False), ('assigned_technician','تکنسین مسئول',False,False),
    ('visit_device_type','نوع دستگاه بازدید',False,False), ('visit_device_count','تعداد دستگاه',False,False),
    ('is_paid_visit','بازدید غیررایگان',False,True), ('proforma_confirmed','پیش‌فاکتور تأیید شده',False,True),
]


class InternalRepairDetailDialog(QDialog):
    def __init__(self, client, req_id: int, parent=None):
        super().__init__(parent)
        self.client = client
        self.req_id = req_id
        self.data = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"پرونده تعمیر داخلی #{req_id}")
        self.resize(780, 620)

        self.header_label = QLabel("")
        self.header_label.setStyleSheet("font-weight:bold; font-size:14px; padding:6px 0;")

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self._build_status_tab()
        self._build_edit_tab(INTERNAL_EDIT_FIELDS)
        self._build_parts_tab()
        self._build_reports_tab()
        self._build_attachments_tab()

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.header_label)
        layout.addWidget(self.tabs, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.reload()

    # ---- data loading -----------------------------------------------------
    def reload(self):
        try:
            self.data = self.client.internal_repair_detail(self.req_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        req = self.data["request"]
        self.header_label.setText(
            f"{req.get('customer_name','')} — {req.get('device_type','')} — وضعیت: {req.get('status','')}"
        )
        self._refresh_status_tab()
        self._refresh_edit_tab()
        self._refresh_parts_tab()
        self._refresh_attachments_tab()

    def _do_action(self, action_data: dict, success_msg: str = "با موفقیت ثبت شد."):
        button = self.sender() if isinstance(self.sender(), QPushButton) else None
        try:
            with busy(button=button):
                self.client.internal_repair_action(self.req_id, action_data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return False
        QMessageBox.information(self, "انجام شد", success_msg)
        self.reload()
        return True

    def _build_edit_tab(self, fields):
        self.edit_tab = _RequestEditTab(self, fields)
        self.tabs.addTab(self.edit_tab, 'ویرایش')

    def _refresh_edit_tab(self):
        if hasattr(self, 'edit_tab') and self.data:
            self.edit_tab.refresh(self.data.get('request', {}))
            self.edit_tab.setEnabled(bool((self.data.get('permissions') or {}).get('can_edit', self.data.get('can_edit', False))))

    # ---- تب وضعیت -----------------------------------------------------
    def _build_status_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.status_combo = QComboBox()
        self.stage_date_edit = QLineEdit()
        self.stage_date_edit.setPlaceholderText("1403/01/01 (اختیاری)")
        self.stage_notes_edit = QLineEdit()
        form.addRow("وضعیت جدید", self.status_combo)
        form.addRow("تاریخ مرحله", self.stage_date_edit)
        form.addRow("یادداشت", self.stage_notes_edit)
        change_btn = QPushButton("ثبت تغییر وضعیت")
        change_btn.clicked.connect(self._submit_status_change)
        form.addRow("", change_btn)
        self.tabs.addTab(w, "وضعیت")

    def _refresh_status_tab(self):
        self.status_combo.clear()
        for s in self.data.get("statuses", []):
            self.status_combo.addItem(s, s)
        current = self.data["request"].get("status")
        idx = self.status_combo.findData(current)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

    def _submit_status_change(self):
        self._do_action({
            "action": "change_status",
            "new_status": self.status_combo.currentData(),
            "stage_date": self.stage_date_edit.text().strip(),
            "stage_notes": self.stage_notes_edit.text().strip(),
        }, "وضعیت با موفقیت تغییر کرد.")

    # ---- تب قطعات -----------------------------------------------------
    def _build_parts_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(6)
        self.parts_table.setHorizontalHeaderLabels(
            ["شناسه", "نام قطعه", "تعداد", "سریال سالم", "سریال خراب", "یادداشت"]
        )
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.parts_table, 1)

        form = QFormLayout()
        self.part_name_edit = QLineEdit()
        self.part_qty_edit = QLineEdit()
        self.part_qty_edit.setText("1")
        self.part_serial_healthy_edit = QLineEdit()
        self.part_serial_faulty_edit = QLineEdit()
        self.part_notes_edit = QLineEdit()
        form.addRow("نام قطعه", self.part_name_edit)
        form.addRow("تعداد", self.part_qty_edit)
        form.addRow("سریال سالم *", self.part_serial_healthy_edit)
        form.addRow("سریال خراب *", self.part_serial_faulty_edit)
        form.addRow("یادداشت", self.part_notes_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("افزودن قطعه")
        add_btn.clicked.connect(self._submit_add_part)
        del_btn = QPushButton("حذف قطعه انتخاب‌شده")
        del_btn.clicked.connect(self._submit_delete_part)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        self.tabs.addTab(w, "قطعات")

    def _refresh_parts_tab(self):
        parts = self.data.get("parts", [])
        self.parts_table.setRowCount(len(parts))
        for row, p in enumerate(parts):
            vals = [
                str(p.get("id", "")), p.get("part_name", "") or "",
                str(p.get("quantity", "") or ""), p.get("serial_healthy", "") or "",
                p.get("serial_faulty", "") or "", p.get("notes", "") or "",
            ]
            for col, v in enumerate(vals):
                self.parts_table.setItem(row, col, QTableWidgetItem(v))

    def _submit_add_part(self):
        if not self.part_name_edit.text().strip():
            QMessageBox.warning(self, "فیلد الزامی", "نام قطعه را وارد کنید.")
            return
        if not self.part_serial_healthy_edit.text().strip() or not self.part_serial_faulty_edit.text().strip():
            QMessageBox.warning(self, "فیلد الزامی", "سریال سالم و سریال خراب هر دو الزامی است.")
            return
        ok = self._do_action({
            "action": "add_part",
            "part_name": self.part_name_edit.text().strip(),
            "quantity": self.part_qty_edit.text().strip() or "1",
            "serial_healthy": self.part_serial_healthy_edit.text().strip(),
            "serial_faulty": self.part_serial_faulty_edit.text().strip(),
            "part_notes": self.part_notes_edit.text().strip(),
        }, "قطعه با موفقیت ثبت شد.")
        if ok:
            self.part_name_edit.setText("")
            self.part_serial_healthy_edit.setText("")
            self.part_serial_faulty_edit.setText("")
            self.part_notes_edit.setText("")
            self.part_qty_edit.setText("1")

    def _submit_delete_part(self):
        row = self.parts_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "انتخاب نشده", "یک قطعه را از جدول انتخاب کنید.")
            return
        part_row_id = self.parts_table.item(row, 0).text()
        if QMessageBox.question(self, "تأیید حذف", "این قطعه حذف شود؟") != QMessageBox.Yes:
            return
        self._do_action({"action": "delete_part", "part_row_id": part_row_id}, "قطعه حذف شد.")

    # ---- تب گزارش‌ها (تکنسین / QC) ------------------------------------
    def _build_reports_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        tech_label = QLabel("گزارش تکنسین")
        tech_label.setStyleSheet("font-weight:bold;")
        self.tech_desc_edit = QPlainTextEdit()
        self.tech_actions_edit = QPlainTextEdit()
        tech_form = QFormLayout()
        tech_form.addRow("شرح فنی", self.tech_desc_edit)
        tech_form.addRow("اقدامات انجام‌شده", self.tech_actions_edit)
        tech_btn = QPushButton("ثبت گزارش تکنسین")
        tech_btn.clicked.connect(self._submit_tech_report)

        qc_label = QLabel("گزارش کنترل کیفیت")
        qc_label.setStyleSheet("font-weight:bold; margin-top:10px;")
        self.qc_initial_edit = QPlainTextEdit()
        self.qc_final_edit = QPlainTextEdit()
        self.qc_next_status_combo = QComboBox()
        for s in ('در انتظار تست اولیه است', 'در انتظار ارسال گزارش فنی است',
                  'در انتظار تست نهایی و تحویل است', 'در انتظار گزارش نهایی است',
                  'در انتظار خروج از کارخانه است'):
            self.qc_next_status_combo.addItem(s, s)
        qc_form = QFormLayout()
        qc_form.addRow("QC اولیه", self.qc_initial_edit)
        qc_form.addRow("QC نهایی", self.qc_final_edit)
        qc_form.addRow("وضعیت بعدی", self.qc_next_status_combo)
        qc_btn = QPushButton("ثبت گزارش QC")
        qc_btn.clicked.connect(self._submit_qc_report)

        layout.addWidget(tech_label)
        layout.addLayout(tech_form)
        layout.addWidget(tech_btn)
        layout.addWidget(qc_label)
        layout.addLayout(qc_form)
        layout.addWidget(qc_btn)
        layout.addStretch(1)

        self.tabs.addTab(w, "گزارش‌ها")

    def _submit_tech_report(self):
        self._do_action({
            "action": "tech_report",
            "technician_desc": self.tech_desc_edit.toPlainText().strip(),
            "actions_taken": self.tech_actions_edit.toPlainText().strip(),
        }, "گزارش تکنسین ثبت شد.")

    def _submit_qc_report(self):
        self._do_action({
            "action": "qc_report",
            "initial_qc_desc": self.qc_initial_edit.toPlainText().strip(),
            "final_qc_desc": self.qc_final_edit.toPlainText().strip(),
            "qc_next_status": self.qc_next_status_combo.currentData() or "",
        }, "گزارش QC ثبت شد.")

    # ---- تب پیوست‌ها ---------------------------------------------------
    def _build_attachments_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.edit_tab = _RequestEditTab(self, [
            ('city','شهر',False,False), ('customer_address','آدرس مشتری',True,False),
            ('equipment_manager_name','مسئول تجهیزات',False,False), ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),
            ('contact_name','نام تماس',False,False), ('contact_phone','تلفن تماس',False,False),
            ('install_unit','بخش / واحد نصب‌شده',False,False), ('install_notes','توضیحات نصب',True,False),
            ('assigned_technician','نماینده/تکنسین',False,False),
        ])
        self.tabs.addTab(self.edit_tab, 'ویرایش')
        attach_widget = QWidget()
        attach_layout = QVBoxLayout(attach_widget)
        self.attachments_table = QTableWidget()
        self.attachments_table.setColumnCount(4)
        self.attachments_table.setHorizontalHeaderLabels(["عنوان", "نام فایل", "تاریخ آپلود", ""])
        self.attachments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attachments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attachments_table.setColumnWidth(3, 70)
        layout.addWidget(self.attachments_table, 1)

        row = QHBoxLayout()
        self.attach_label_edit = QLineEdit()
        self.attach_label_edit.setPlaceholderText("عنوان پیوست")
        upload_btn = QPushButton("انتخاب و آپلود فایل...")
        upload_btn.clicked.connect(self._submit_attachment)
        row.addWidget(self.attach_label_edit)
        row.addWidget(upload_btn)
        layout.addLayout(row)

        self.tabs.addTab(w, "پیوست‌ها")

    def _refresh_attachments_tab(self):
        atts = self.data.get("attachments", [])
        self.attachments_table.setRowCount(len(atts))
        for row, a in enumerate(atts):
            vals = [a.get("label", "") or "", a.get("original_name", "") or "", a.get("uploaded_at", "") or ""]
            for col, v in enumerate(vals):
                self.attachments_table.setItem(row, col, QTableWidgetItem(v))
            att_id = a.get("id")
            del_btn = QPushButton("حذف")
            del_btn.clicked.connect(lambda _checked=False, aid=att_id: self._delete_attachment(aid))
            self.attachments_table.setCellWidget(row, 3, del_btn)

    def _delete_attachment(self, att_id):
        if not att_id:
            return
        confirm = QMessageBox.question(
            self, "حذف پیوست", "این پیوست حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.delete_attachment(int(att_id))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return
        self.reload()

    def _submit_attachment(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل پیوست")
        if not path:
            return
        try:
            self.client.upload_attachment(self.req_id, path, self.attach_label_edit.text().strip() or "پیوست")
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.attach_label_edit.setText("")
        self.reload()


class ExternalRepairDetailDialog(QDialog):
    """نمای کامل پرونده تعمیر خارجی (نمایندگی) - مطابق /service/external-repair/view."""

    def __init__(self, client, req_id: int, parent=None):
        super().__init__(parent)
        self.client = client
        self.req_id = req_id
        self.data = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"پرونده تعمیر خارجی #{req_id}")
        self.resize(780, 620)

        self.header_label = QLabel("")
        self.header_label.setStyleSheet("font-weight:bold; font-size:14px; padding:6px 0;")

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self._build_status_tab()
        self._build_edit_tab(EXTERNAL_EDIT_FIELDS)
        self._build_parts_tab()
        self._build_reports_tab()
        self._build_attachments_tab()

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.header_label)
        layout.addWidget(self.tabs, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.reload()

    def reload(self):
        try:
            self.data = self.client.external_repair_detail(self.req_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        req = self.data["request"]
        self.header_label.setText(
            f"{req.get('customer_name','')} — {req.get('device_type','')} — وضعیت: {req.get('status','')}"
        )
        self._refresh_status_tab()
        self._refresh_edit_tab()
        self._refresh_parts_tab()
        self._refresh_attachments_tab()

    def _do_action(self, action_data: dict, success_msg: str = "با موفقیت ثبت شد."):
        button = self.sender() if isinstance(self.sender(), QPushButton) else None
        try:
            with busy(button=button):
                self.client.external_repair_action(self.req_id, action_data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return False
        QMessageBox.information(self, "انجام شد", success_msg)
        self.reload()
        return True

    # ---- تب وضعیت -----------------------------------------------------
    def _build_status_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.status_combo = QComboBox()
        self.stage_date_edit = QLineEdit()
        self.stage_date_edit.setPlaceholderText("1403/01/01 (اختیاری)")
        self.stage_notes_edit = QLineEdit()
        form.addRow("وضعیت جدید", self.status_combo)
        form.addRow("تاریخ مرحله", self.stage_date_edit)
        form.addRow("یادداشت", self.stage_notes_edit)
        change_btn = QPushButton("ثبت تغییر وضعیت")
        change_btn.clicked.connect(self._submit_status_change)
        form.addRow("", change_btn)
        self.tabs.addTab(w, "وضعیت")

    def _refresh_status_tab(self):
        self.status_combo.clear()
        for s in self.data.get("statuses", []):
            self.status_combo.addItem(s, s)
        current = self.data["request"].get("status")
        idx = self.status_combo.findData(current)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

    def _submit_status_change(self):
        self._do_action({
            "action": "change_status",
            "new_status": self.status_combo.currentData(),
            "stage_date": self.stage_date_edit.text().strip(),
            "stage_notes": self.stage_notes_edit.text().strip(),
        }, "وضعیت با موفقیت تغییر کرد.")

    # ---- تب قطعات -----------------------------------------------------
    def _build_parts_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(5)
        self.parts_table.setHorizontalHeaderLabels(
            ["شناسه", "نام قطعه", "تعداد", "مرحله", "یادداشت"]
        )
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.parts_table, 1)

        form = QFormLayout()
        self.part_name_edit = QLineEdit()
        self.part_qty_edit = QLineEdit()
        self.part_qty_edit.setText("1")
        self.part_stage_edit = QLineEdit()
        self.part_notes_edit = QLineEdit()
        form.addRow("نام قطعه", self.part_name_edit)
        form.addRow("تعداد", self.part_qty_edit)
        form.addRow("مرحله", self.part_stage_edit)
        form.addRow("یادداشت", self.part_notes_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("افزودن قطعه")
        add_btn.clicked.connect(self._submit_add_part)
        del_btn = QPushButton("حذف قطعه انتخاب‌شده")
        del_btn.clicked.connect(self._submit_delete_part)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        self.tabs.addTab(w, "قطعات")

    def _refresh_parts_tab(self):
        parts = self.data.get("parts", [])
        self.parts_table.setRowCount(len(parts))
        for row, p in enumerate(parts):
            vals = [
                str(p.get("id", "")), p.get("part_name", "") or "",
                str(p.get("quantity", "") or ""), p.get("stage", "") or "",
                p.get("notes", "") or "",
            ]
            for col, v in enumerate(vals):
                self.parts_table.setItem(row, col, QTableWidgetItem(v))

    def _submit_add_part(self):
        if not self.part_name_edit.text().strip():
            QMessageBox.warning(self, "فیلد الزامی", "نام قطعه را وارد کنید.")
            return
        ok = self._do_action({
            "action": "add_part",
            "part_name": self.part_name_edit.text().strip(),
            "quantity": self.part_qty_edit.text().strip() or "1",
            "part_stage": self.part_stage_edit.text().strip(),
            "part_notes": self.part_notes_edit.text().strip(),
        }, "قطعه با موفقیت ثبت شد.")
        if ok:
            self.part_name_edit.setText("")
            self.part_stage_edit.setText("")
            self.part_notes_edit.setText("")
            self.part_qty_edit.setText("1")

    def _submit_delete_part(self):
        row = self.parts_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "انتخاب نشده", "یک قطعه را از جدول انتخاب کنید.")
            return
        part_row_id = self.parts_table.item(row, 0).text()
        if QMessageBox.question(self, "تأیید حذف", "این قطعه حذف شود؟") != QMessageBox.Yes:
            return
        self._do_action({"action": "delete_part", "part_row_id": part_row_id}, "قطعه حذف شد.")

    # ---- تب گزارش تکنسین (نماینده) -------------------------------------
    def _build_reports_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        tech_label = QLabel("گزارش تکنسین/نماینده")
        tech_label.setStyleSheet("font-weight:bold;")
        self.tech_desc_edit = QPlainTextEdit()
        self.tech_actions_edit = QPlainTextEdit()
        tech_form = QFormLayout()
        tech_form.addRow("شرح فنی", self.tech_desc_edit)
        tech_form.addRow("اقدامات انجام‌شده", self.tech_actions_edit)
        tech_btn = QPushButton("ثبت گزارش تکنسین")
        tech_btn.clicked.connect(self._submit_tech_report)

        layout.addWidget(tech_label)
        layout.addLayout(tech_form)
        layout.addWidget(tech_btn)
        layout.addStretch(1)
        self.tabs.addTab(w, "گزارش تکنسین")

    def _submit_tech_report(self):
        self._do_action({
            "action": "tech_report",
            "technician_desc": self.tech_desc_edit.toPlainText().strip(),
            "actions_taken": self.tech_actions_edit.toPlainText().strip(),
        }, "گزارش تکنسین ثبت شد.")

    # ---- تب پیوست‌ها ---------------------------------------------------
    def _build_attachments_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.attachments_table = QTableWidget()
        self.attachments_table.setColumnCount(4)
        self.attachments_table.setHorizontalHeaderLabels(["عنوان", "نام فایل", "تاریخ آپلود", ""])
        self.attachments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attachments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attachments_table.setColumnWidth(3, 70)
        layout.addWidget(self.attachments_table, 1)

        row = QHBoxLayout()
        self.attach_label_edit = QLineEdit()
        self.attach_label_edit.setPlaceholderText("عنوان پیوست")
        upload_btn = QPushButton("انتخاب و آپلود فایل...")
        upload_btn.clicked.connect(self._submit_attachment)
        row.addWidget(self.attach_label_edit)
        row.addWidget(upload_btn)
        layout.addLayout(row)

        self.tabs.addTab(w, "پیوست‌ها")

    def _refresh_attachments_tab(self):
        atts = self.data.get("attachments", [])
        self.attachments_table.setRowCount(len(atts))
        for row, a in enumerate(atts):
            vals = [a.get("label", "") or "", a.get("original_name", "") or "", a.get("uploaded_at", "") or ""]
            for col, v in enumerate(vals):
                self.attachments_table.setItem(row, col, QTableWidgetItem(v))
            att_id = a.get("id")
            del_btn = QPushButton("حذف")
            del_btn.clicked.connect(lambda _checked=False, aid=att_id: self._delete_attachment(aid))
            self.attachments_table.setCellWidget(row, 3, del_btn)

    def _delete_attachment(self, att_id):
        if not att_id:
            return
        confirm = QMessageBox.question(
            self, "حذف پیوست", "این پیوست حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.delete_attachment(int(att_id))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return
        self.reload()

    def _submit_attachment(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل پیوست")
        if not path:
            return
        try:
            self.client.upload_attachment(self.req_id, path, self.attach_label_edit.text().strip() or "پیوست")
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.attach_label_edit.setText("")
        self.reload()


class _SimpleStatusDetailDialog(QDialog):
    """پایه‌ی مشترک برای دیالوگ‌های سبک‌تر (درخواست نصب / بازدید) - یک تب
    وضعیت + یک تب پیوست‌ها؛ فرزندها متد ``_status_field_name`` و
    ``do_action`` را برای اتصال به endpoint اختصاصی خودشان override می‌کنند."""

    detail_fetcher_name = ""
    action_fn_name = ""
    title_prefix = "پرونده"
    edit_fields = None

    def __init__(self, client, req_id: int, parent=None):
        super().__init__(parent)
        self.client = client
        self.req_id = req_id
        self.data = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"{self.title_prefix} #{req_id}")
        self.resize(680, 520)

        self.header_label = QLabel("")
        self.header_label.setStyleSheet("font-weight:bold; font-size:14px; padding:6px 0;")

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self._build_status_tab()
        if self.edit_fields:
            self._build_edit_tab(self.edit_fields)
        self._build_attachments_tab()

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.header_label)
        layout.addWidget(self.tabs, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.reload()

    def _fetch(self):
        return getattr(self.client, self.detail_fetcher_name)(self.req_id)

    def _act(self, data):
        return getattr(self.client, self.action_fn_name)(self.req_id, data)

    def reload(self):
        try:
            self.data = self._fetch()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        req = self.data["request"]
        self.header_label.setText(
            f"{req.get('customer_name','')} — {req.get('device_type','')} — وضعیت: {req.get('status','')}"
        )
        self._refresh_status_tab()
        self._refresh_edit_tab()
        self._refresh_attachments_tab()

    def _do_action(self, data, success_msg='با موفقیت ثبت شد.'):
        button = self.sender() if isinstance(self.sender(), QPushButton) else None
        try:
            with busy(button=button):
                self._act(data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, 'خطا', str(e)); return False
        QMessageBox.information(self, 'انجام شد', success_msg)
        self.reload(); return True

    def _build_edit_tab(self, fields):
        self.edit_tab = _RequestEditTab(self, fields)
        self.tabs.addTab(self.edit_tab, 'ویرایش')

    def _refresh_edit_tab(self):
        if hasattr(self, 'edit_tab') and self.data:
            self.edit_tab.refresh(self.data.get('request', {}))
            self.edit_tab.setEnabled(bool((self.data.get('permissions') or {}).get('can_edit', self.data.get('can_edit', False))))

    def _build_status_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.status_combo = QComboBox()
        self.stage_date_edit = QLineEdit()
        self.stage_date_edit.setPlaceholderText("1403/01/01 (اختیاری)")
        self.stage_notes_edit = QLineEdit()
        form.addRow("وضعیت جدید", self.status_combo)
        form.addRow("تاریخ مرحله", self.stage_date_edit)
        form.addRow("یادداشت", self.stage_notes_edit)
        change_btn = QPushButton("ثبت تغییر وضعیت")
        change_btn.clicked.connect(self._submit_status_change)
        form.addRow("", change_btn)
        self.tabs.addTab(w, "وضعیت")

    def _refresh_status_tab(self):
        self.status_combo.clear()
        for s in self.data.get("statuses", []):
            self.status_combo.addItem(s, s)
        current = self.data["request"].get("status")
        idx = self.status_combo.findData(current)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

    def _submit_status_change(self):
        try:
            self._act({
                "action": "change_status",
                "new_status": self.status_combo.currentData(),
                "stage_date": self.stage_date_edit.text().strip(),
                "stage_notes": self.stage_notes_edit.text().strip(),
            })
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return
        QMessageBox.information(self, "انجام شد", "وضعیت با موفقیت تغییر کرد.")
        self.reload()

    def _build_attachments_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.attachments_table = QTableWidget()
        self.attachments_table.setColumnCount(4)
        self.attachments_table.setHorizontalHeaderLabels(["عنوان", "نام فایل", "تاریخ آپلود", ""])
        self.attachments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attachments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attachments_table.setColumnWidth(3, 70)
        layout.addWidget(self.attachments_table, 1)

        row = QHBoxLayout()
        self.attach_label_edit = QLineEdit()
        self.attach_label_edit.setPlaceholderText("عنوان پیوست")
        upload_btn = QPushButton("انتخاب و آپلود فایل...")
        upload_btn.clicked.connect(self._submit_attachment)
        row.addWidget(self.attach_label_edit)
        row.addWidget(upload_btn)
        layout.addLayout(row)

        self.tabs.addTab(w, "پیوست‌ها")

    def _refresh_attachments_tab(self):
        atts = self.data.get("attachments", [])
        self.attachments_table.setRowCount(len(atts))
        for row, a in enumerate(atts):
            vals = [a.get("label", "") or "", a.get("original_name", "") or "", a.get("uploaded_at", "") or ""]
            for col, v in enumerate(vals):
                self.attachments_table.setItem(row, col, QTableWidgetItem(v))
            att_id = a.get("id")
            del_btn = QPushButton("حذف")
            del_btn.clicked.connect(lambda _checked=False, aid=att_id: self._delete_attachment(aid))
            self.attachments_table.setCellWidget(row, 3, del_btn)

    def _delete_attachment(self, att_id):
        if not att_id:
            return
        confirm = QMessageBox.question(
            self, "حذف پیوست", "این پیوست حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.delete_attachment(int(att_id))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return
        self.reload()

    def _submit_attachment(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل پیوست")
        if not path:
            return
        try:
            self.client.upload_attachment(self.req_id, path, self.attach_label_edit.text().strip() or "پیوست")
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.attach_label_edit.setText("")
        self.reload()


class InstallationRequestDetailDialog(_SimpleStatusDetailDialog):
    edit_fields = INSTALL_REQUEST_EDIT_FIELDS
    """درخواست نصب - مطابق /service/installation/request-view."""
    detail_fetcher_name = "installation_request_detail"
    action_fn_name = "installation_request_action"
    title_prefix = "درخواست نصب"


class InspectionDetailDialog(_SimpleStatusDetailDialog):
    edit_fields = INSPECTION_EDIT_FIELDS
    """درخواست/گزارش بررسی و بازدید - مطابق /service/inspection/view."""
    detail_fetcher_name = "inspection_detail"
    action_fn_name = "inspection_action"
    title_prefix = "بررسی و بازدید"


class InstallationRegisterDetailDialog(QDialog):
    """نصب انجام‌شده؛ ویرایش فیلدهای مجاز پذیرش + پیوست‌ها."""

    def __init__(self, client, req_id: int, parent=None):
        super().__init__(parent)
        self.client = client
        self.req_id = req_id
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"نصب انجام‌شده #{req_id}")
        self.resize(680, 520)
        self.data = None

        self.tabs = QTabWidget()
        self.tabs.setLayoutDirection(Qt.RightToLeft)
        self.info_label = QLabel("در حال بارگذاری...")
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)

        self.edit_tab = _RequestEditTab(self, [
            ('city','شهر',False,False), ('customer_address','آدرس مشتری',True,False),
            ('equipment_manager_name','مسئول تجهیزات',False,False), ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),
            ('contact_name','نام تماس',False,False), ('contact_phone','تلفن تماس',False,False),
            ('install_unit','بخش / واحد نصب‌شده',False,False), ('install_notes','توضیحات نصب',True,False),
            ('assigned_technician','نماینده/تکنسین',False,False),
        ])
        self.tabs.addTab(self.edit_tab, 'ویرایش')
        attach_widget = QWidget()
        attach_layout = QVBoxLayout(attach_widget)
        self.attachments_table = QTableWidget()
        self.attachments_table.setColumnCount(4)
        self.attachments_table.setHorizontalHeaderLabels(["عنوان", "نام فایل", "تاریخ آپلود", ""])
        self.attachments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attachments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attachments_table.setColumnWidth(3, 70)
        attach_layout.addWidget(self.attachments_table, 1)
        self.tabs.addTab(attach_widget, 'پیوست‌ها')

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.info_label)
        layout.addWidget(self.tabs, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.reload()

    def _do_action(self, data, success_msg='با موفقیت ثبت شد.'):
        button = self.sender() if isinstance(self.sender(), QPushButton) else None
        try:
            with busy(button=button):
                self.client.installation_register_action(self.req_id, data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, 'خطا', str(e)); return False
        QMessageBox.information(self, 'انجام شد', success_msg)
        self.reload(); return True

    def reload(self):
        try:
            data = self.client.installation_register_detail(self.req_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.data = data
        req = data.get("request", {})
        self.edit_tab.refresh(req)
        self.edit_tab.setEnabled(bool(data.get('can_edit', False)))
        rows = [
            ("مشتری", req.get("customer_name")), ("نوع دستگاه", req.get("device_type")),
            ("مدل", req.get("device_model")), ("سریال", req.get("serial_number")),
            ("استان", req.get("province")), ("شهر", req.get("city")),
            ("تکنسین", req.get("assigned_technician")), ("تاریخ ثبت", req.get("reception_date")),
            ("یادداشت نصب", req.get("install_notes")), ("فایل گزارش", req.get("report_filename")),
        ]
        html = "<table cellpadding='4'>" + "".join(
            f"<tr><td style='color:#64748b;'>{label}</td><td><b>{value or '—'}</b></td></tr>"
            for label, value in rows
        ) + "</table>"
        self.info_label.setText(html)
        atts = data.get("attachments", [])
        self.attachments_table.setRowCount(len(atts))
        for row, a in enumerate(atts):
            vals = [a.get("label", "") or "", a.get("original_name", "") or "", a.get("uploaded_at", "") or ""]
            for col, v in enumerate(vals):
                self.attachments_table.setItem(row, col, QTableWidgetItem(v))
            att_id = a.get("id")
            del_btn = QPushButton("حذف")
            del_btn.clicked.connect(lambda _checked=False, aid=att_id: self._delete_attachment(aid))
            self.attachments_table.setCellWidget(row, 3, del_btn)

    def _delete_attachment(self, att_id):
        if not att_id:
            return
        confirm = QMessageBox.question(
            self, "حذف پیوست", "این پیوست حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.delete_attachment(int(att_id))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.warning(self, "خطا", str(e))
            return
        self.reload()
