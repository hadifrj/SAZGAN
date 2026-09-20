# -*- coding: utf-8 -*-
"""فرم‌های ثبت خدمات Native؛ هم‌راستا با فرم‌های واقعی وب."""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPlainTextEdit,
    QPushButton, QLabel, QCheckBox, QFileDialog, QMessageBox, QScrollArea, QComboBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
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


class _GenericNewForm(QWidget):
    """فرم قابل‌استفاده مجدد؛ در پنجره QDialog نمایش داده می‌شود."""
    submitted = pyqtSignal()
    def __init__(self, fields, on_submit, file_field=None, title="", client=None):
        super().__init__(); self.setLayoutDirection(Qt.RightToLeft)
        self.fields=fields; self.on_submit=on_submit; self.file_field=file_field; self.client=client
        self._file_path=None; self._inputs={}; self._options={}
        outer=QVBoxLayout(self)
        if title:
            t=QLabel(title); t.setStyleSheet("font-weight:bold;font-size:14px;padding:4px 0;"); outer.addWidget(t)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); inner=QWidget(); form=QFormLayout(inner)
        for key,label,multiline,required in fields:
            if key == 'is_paid_visit': w=QCheckBox('بازدید غیررایگان (نیاز به پیش‌فاکتور)')
            elif key in {'province','city','device_type','device_model','visit_device_type','assigned_technician'}:
                w=QComboBox(); w.setEditable(False); w.addItem('انتخاب کنید...', '')
                if key=='province': w.currentIndexChanged.connect(self._province_changed)
                if key=='device_type': w.currentIndexChanged.connect(self._device_type_changed)
            elif multiline:
                w=QPlainTextEdit(); w.setFixedHeight(80)
            else: w=QLineEdit()
            self._inputs[key]=w; form.addRow(label+(' *' if required else ''),w)
        if file_field:
            fkey,flabel=file_field; self._file_label=QLabel('فایلی انتخاب نشده'); self._file_label.setWordWrap(True)
            b=QPushButton('انتخاب فایل...'); b.clicked.connect(self._pick_file); form.addRow(flabel+' *',b); form.addRow('',self._file_label)
        scroll.setWidget(inner); outer.addWidget(scroll,1)
        self.submit_btn=QPushButton('ثبت'); self.submit_btn.clicked.connect(self._submit); outer.addWidget(self.submit_btn)
        self.status_label=QLabel(''); self.status_label.setWordWrap(True); outer.addWidget(self.status_label)
        if client: self._load_options()

    def _load_options(self):
        try: data=self.client.service_form_options()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: self.status_label.setText(f'داده‌های مرجع بارگذاری نشد: {e}'); return
        self._options=data or {}
        self._set_combo('province', self._options.get('provinces', []))
        self._set_combo('device_type', self._options.get('device_types', []))
        self._set_combo('visit_device_type', self._options.get('device_types', []))
        self._set_combo('assigned_technician', self._options.get('technicians', []), label_key='label', data_key='id')
        self._set_combo('city', [])
        self._set_combo('device_model', [])

    def _set_combo(self,key,items,label_key=None,data_key=None):
        w=self._inputs.get(key)
        if not isinstance(w,QComboBox): return
        w.blockSignals(True); w.clear(); w.addItem('انتخاب کنید...','')
        for item in items or []:
            if isinstance(item,dict):
                label=str(item.get(label_key or 'label') or item.get('name') or item.get('value') or item.get(data_key or 'id') or '')
                val=item.get(data_key or 'value', item.get('id', label))
            else: label=str(item); val=item
            if label: w.addItem(label,val)
        w.blockSignals(False)

    def _province_changed(self,*_):
        province=self._inputs.get('province').currentData() if isinstance(self._inputs.get('province'),QComboBox) else ''
        if not province: self._set_combo('city',[]); return
        try: data=self.client.geo_cities(province).get('cities',[]); self._set_combo('city',data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError: pass

    def _device_type_changed(self,*_):
        typ=self._inputs.get('device_type').currentData() if isinstance(self._inputs.get('device_type'),QComboBox) else ''
        if not typ: self._set_combo('device_model',[]); return
        models=(self._options.get('models_by_type') or {}).get(typ,[])
        self._set_combo('device_model',models)

    def _pick_file(self):
        path,_=QFileDialog.getOpenFileName(self,'انتخاب فایل گزارش')
        if path: self._file_path=path; self._file_label.setText(path.replace('\\','/').split('/')[-1])

    def _submit(self):
        data={}; missing=[]
        for key,label,multiline,required in self.fields:
            w=self._inputs[key]
            if isinstance(w,QCheckBox): data[key]='1' if w.isChecked() else '0'; continue
            if isinstance(w,QComboBox): value=w.currentData() or ''; display=w.currentText().strip();
            else: value=w.toPlainText().strip() if isinstance(w,QPlainTextEdit) else w.text().strip(); display=value
            data[key]=value
            if key == 'probable_parts' and value:
                data['probable_part_ids'] = [x.strip() for x in str(value).replace('،', ',').split(',') if x.strip()]
            if required and not value: missing.append(label)
        if self.file_field and not self._file_path: missing.append(self.file_field[1])
        if missing: QMessageBox.warning(self,'فیلدهای الزامی','این فیلدها را پر کنید:\n'+ '، '.join(missing)); return
        self.status_label.setText('در حال ثبت...')
        try:
            with busy(button=self.submit_btn, text='در حال ثبت...'):
                result=self.on_submit(data,self._file_path) if self.file_field else self.on_submit(data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: self.status_label.setText(f'خطا: {e}'); QMessageBox.critical(self,'ثبت ناموفق',str(e)); return
        self.status_label.setText(f"با موفقیت ثبت شد (شناسه: {result.get('id') if isinstance(result,dict) else None})."); self._clear(); self.submitted.emit()

    def _clear(self):
        for w in self._inputs.values():
            if isinstance(w,QCheckBox): w.setChecked(False)
            elif isinstance(w,QPlainTextEdit): w.clear()
            elif isinstance(w,QComboBox): w.setCurrentIndex(0)
            else: w.clear()
        if self.file_field: self._file_path=None; self._file_label.setText('فایلی انتخاب نشده')

_CUSTOMER_FIELDS=[
 ('customer_name','نام مشتری',False,True),('customer_phone','تلفن مشتری',False,False),('customer_address','آدرس',False,False),
 ('province','استان',False,True),('city','شهر',False,True),('equipment_manager_name','نام مسئول تجهیزات',False,False),
 ('equipment_manager_mobile','موبایل مسئول تجهیزات',False,False),('contact_name','نام تماس',False,False),('contact_phone','تلفن تماس',False,False),
]

def make_internal_repair_form(client):
 fields=_CUSTOMER_FIELDS+[('device_type','نوع دستگاه',False,True),('device_model','مدل دستگاه',False,True),('serial_number','شماره سریال',False,True),('installation_date','تاریخ نصب',False,False),('warranty_end_date','پایان گارانتی',False,False),('hospital_request_desc','شرح درخواست',True,True),('assigned_technician','تکنسین',False,False),('accompanying_items','اقلام همراه',True,False),('appearance_status','وضعیت ظاهری',True,False)]
 return _GenericNewForm(fields,client.create_internal_repair,title='ثبت تعمیر داخلی',client=client)

def make_external_repair_form(client):
 fields=_CUSTOMER_FIELDS+[('device_type','نوع دستگاه',False,True),('device_model','مدل دستگاه',False,True),('serial_number','شماره سریال',False,True),('installation_date','تاریخ نصب',False,False),('warranty_end_date','پایان گارانتی',False,False),('hospital_request_desc','شرح درخواست',True,True),('assigned_technician','تکنسین',False,False),('probable_parts','قطعات احتمالی (اختیاری؛ شناسه‌ها با کاما)',False,False)]
 return _GenericNewForm(fields,client.create_external_repair,title='ثبت تعمیر خارجی',client=client)

def make_installation_request_form(client):
 fields=_CUSTOMER_FIELDS+[('device_models_text','مدل‌ها (هر خط یک مدل)',True,True),('install_notes','یادداشت نصب',True,False),('assigned_technician','تکنسین',False,False)]
 return _GenericNewForm(fields,client.create_installation_request,title='ثبت درخواست نصب',client=client)

def make_installation_register_form(client):
 fields=_CUSTOMER_FIELDS+[('serial_number','شماره سریال (باید در گارانتی فعال باشد)',False,True),('install_unit','واحد نصب‌شده',False,False),('install_notes','یادداشت نصب',True,False),('assigned_technician','تکنسین',False,False)]
 return _GenericNewForm(fields,client.create_installation_register,file_field=('report_file','فایل گزارش نصب'),title='ثبت نصب دستگاه',client=client)

def make_inspection_request_form(client):
 fields=_CUSTOMER_FIELDS+[('visit_device_type','نوع دستگاه بازدید',False,True),('visit_device_count','تعداد دستگاه',False,False),('hospital_request_desc','شرح درخواست',True,True),('is_paid_visit','بازدید غیررایگان',False,False),('assigned_technician','تکنسین',False,False)]
 return _GenericNewForm(fields,client.create_inspection_request,title='ثبت درخواست بازدید',client=client)

def make_inspection_report_form(client):
 fields=_CUSTOMER_FIELDS+[('assigned_technician','تکنسین',False,False)]
 return _GenericNewForm(fields,client.create_inspection_report,file_field=('report_file','فایل گزارش بازدید'),title='ثبت گزارش بازدید',client=client)
