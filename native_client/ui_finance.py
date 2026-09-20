# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QLineEdit,
    QTabWidget, QMessageBox, QGridLayout, QFrame, QComboBox, QSpinBox, QDialog, QTextEdit,
)
from PyQt5.QtCore import Qt
from api_client import ApiError, SessionExpiredError
from ui_common import busy
from ui_common import fill_table, make_stat_card, export_table_csv, busy, show_loading

REPS_DASHBOARD_COLUMNS = [
    ("name", "نماینده"), ("province", "استان"), ("month_total", "جمع این ماه"),
    ("unpaid_month", "پرداخت‌نشده"), ("paid_month", "پرداخت‌شده"),
    ("year_total", "جمع سال"), ("settle_status", "وضعیت تسویه"),
]

WAGE_HISTORY_COLUMNS = [
    ("id", "شناسه"), ("representative_name", "نماینده"), ("calc_date", "تاریخ"),
    ("description", "شرح"), ("amount", "مبلغ"), ("qty", "تعداد"),
    ("customer_name", "مشتری"), ("payment_status", "وضعیت پرداخت"),
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


class RepsDashboardTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.year=QSpinBox(); self.year.setRange(1400,1600); self.year.setValue(1405)
        self.month=QComboBox(); self.month.addItems([str(i) for i in range(1,13)])
        self.load=QPushButton("بارگذاری") ; self.load.clicked.connect(self.reload)
        self.export_btn=QPushButton("خروجی CSV"); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "settlements.csv"))
        self.search=QLineEdit(); self.search.setPlaceholderText("فیلتر نماینده / استان..."); self.search.textChanged.connect(self._filter)
        self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        bar=QHBoxLayout(); bar.addWidget(QLabel("سال")); bar.addWidget(self.year); bar.addWidget(QLabel("ماه")); bar.addWidget(self.month); bar.addWidget(self.search,1); bar.addWidget(self.export_btn); bar.addWidget(self.load)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.rows=[]; self.reload()
    def reload(self):
        try: d=self.client.finance_reps_dashboard(self.year.value(), self.month.currentIndex()+1)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        self.rows=d.get("rows",[]); self._filter()
    def _filter(self):
        q=self.search.text().strip().lower(); rows=self.rows
        if q: rows=[r for r in rows if q in f"{r.get('name','')} {r.get('province','')}".lower()]
        fill_table(self.table,rows,[("id","شناسه")]+REPS_DASHBOARD_COLUMNS)



class WageHistoryTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.search=QLineEdit(); self.search.setPlaceholderText("نماینده، مشتری، شرح کار..."); self.search.textChanged.connect(self._filter)
        self.refresh_btn=QPushButton("بارگذاری مجدد"); self.refresh_btn.clicked.connect(self.reload)
        self.export_btn=QPushButton("خروجی CSV"); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "wage-history.csv"))
        self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(self.export_btn); bar.addWidget(self.refresh_btn)
        layout=QVBoxLayout(self); layout.addLayout(bar); layout.addWidget(self.table); self.rows=[]; self.reload()
    def reload(self):
        try: data=self.client.finance_wage_history()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        self.rows=data.get("rows",[]); self._filter()
    def _filter(self):
        q=self.search.text().strip().lower(); rows=self.rows
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('representative_name','customer_name','description','work_description','calc_date')).lower()]
        fill_table(self.table,rows,WAGE_HISTORY_COLUMNS)


def _stat_box(title, value):
    return make_stat_card(title, value)


class MyWagesTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)
        self.refresh_btn = QPushButton("بارگذاری مجدد")
        self.refresh_btn.clicked.connect(self.reload)
        self.export_btn = QPushButton("خروجی CSV")
        self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "my-wages.csv"))
        self.stats_layout = QGridLayout()
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.info_label = QLabel("")

        layout = QVBoxLayout()
        top = QHBoxLayout(); top.addWidget(self.refresh_btn); top.addWidget(self.export_btn); top.addStretch(1)
        layout.addLayout(top)
        layout.addWidget(self.info_label)
        layout.addLayout(self.stats_layout)
        layout.addWidget(self.table)
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
            data = self.client.my_wages()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return

        if not data.get("has_rep_link"):
            self.info_label.setText("این حساب کاربری به هیچ نماینده‌ای متصل نیست.")
            return

        self.info_label.setText(f"ماه: {data.get('month_label','')} {data.get('year','')}")
        self._clear_stats()
        self.stats_layout.addWidget(_stat_box("جمع این ماه", data.get("month_total", 0)), 0, 0)
        self.stats_layout.addWidget(_stat_box("پرداخت‌نشده", data.get("unpaid_month", 0)), 0, 1)
        self.stats_layout.addWidget(_stat_box("پرداخت‌شده", data.get("paid_month", 0)), 0, 2)
        self.stats_layout.addWidget(_stat_box("جمع سال", data.get("year_total", 0)), 0, 3)

        fill_table(self.table, data.get("rows", []), WAGE_HISTORY_COLUMNS)



class WageRatesTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.refresh_btn=QPushButton("بارگذاری مجدد"); self.refresh_btn.clicked.connect(self.reload)
        self.add_btn=QPushButton("افزودن ردیف"); self.add_btn.clicked.connect(self.add_row)
        bar=QHBoxLayout(); bar.addWidget(self.refresh_btn); bar.addWidget(self.add_btn); bar.addStretch(1)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table)
        self.reload()
    def reload(self):
        try: d=self.client.wage_rates()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        self.rows=d.get('rows',[])
        fill_table(self.table,self.rows,[("id","شناسه"),("work_description","شرح کار"),("wage_amount","مبلغ پایه"),("amount_outside","مبلغ خارج"),("rate_code","کد"),("category","دسته"),("is_per_km","کیلومتری"),("device_type","نوع دستگاه"),("install_slot","محل نصب")])
    def add_row(self):
        from PyQt5.QtWidgets import QInputDialog
        desc,ok=QInputDialog.getText(self,"ردیف جدید","شرح کار:")
        if not ok or not desc.strip(): return
        amount,ok=QInputDialog.getInt(self,"مبلغ پایه","مبلغ:",0,0,10**12)
        if not ok: return
        try: self.client.wage_rate_create({'work_description':desc.strip(),'wage_amount':amount})
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        self.reload()

class FinanceFilesTab(QWidget):
    def __init__(self, client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.search=QLineEdit(); self.search.setPlaceholderText("جستجو: مشتری، سریال، شماره پذیرش، فاکتور...")
        self.search.returnPressed.connect(self.reload)
        self.refresh_btn=QPushButton("جستجو / بارگذاری"); self.refresh_btn.clicked.connect(self.reload)
        self.export_btn=QPushButton("خروجی CSV"); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, "finance-files.csv"))
        self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(self.export_btn); bar.addWidget(self.refresh_btn)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try: d=self.client.finance_files(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        fill_table(self.table,d.get('rows',[]),[("id","شناسه"),("reception_no","پذیرش"),("customer_name","مشتری"),("serial_number","سریال"),("device_type","دستگاه"),("status","وضعیت"),("invoice_number","شماره فاکتور"),("reception_date","تاریخ")])


class SettlementsTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.search=QLineEdit(); self.search.setPlaceholderText('جستجوی نماینده...'); self.year=QSpinBox(); self.year.setRange(1400,1600); self.year.setValue(1405); self.month=QComboBox(); self.month.addItems([str(i) for i in range(1,13)])
        self.load=QPushButton('بارگذاری'); self.detail=QPushButton('جزئیات'); self.settle=QPushButton('ثبت تسویه'); self.receipt=QPushButton('رسید'); self.export_btn=QPushButton('خروجی CSV')
        self.table=QTableWidget(); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.load.clicked.connect(self.reload); self.detail.clicked.connect(self.show_detail); self.settle.clicked.connect(self.pay); self.receipt.clicked.connect(self.show_receipt); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, 'settlements.csv'))
        bar=QHBoxLayout(); bar.addWidget(QLabel('سال')); bar.addWidget(self.year); bar.addWidget(QLabel('ماه')); bar.addWidget(self.month); bar.addWidget(self.search,1); bar.addWidget(self.load); bar.addWidget(self.detail); bar.addWidget(self.settle); bar.addWidget(self.receipt); bar.addWidget(self.export_btn)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try: d=self.client.finance_settlements(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        self.rows=d.get('rows',[]); fill_table(self.table,self.rows,[("id","شناسه"),("name","نماینده"),("province","استان"),("month_total","جمع ماه"),("unpaid_month","پرداخت‌نشده"),("paid_month","پرداخت‌شده"),("settle_status","وضعیت")])
    def _row(self):
        r=self.table.currentRow(); return self.rows[r] if 0<=r<len(self.rows) else None
    def show_detail(self):
        x=self._row()
        if not x: return
        try: d=self.client.finance_settlement_detail(int(x['id']),self.year.value(),self.month.currentIndex()+1)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        s=d.get('summary') or {}; b=d.get('bank') or {}
        text=f"نماینده: {x.get('name','')}\nماه: {d.get('month')}/{d.get('year')}\nجمع: {s.get('month_total',0):,}\nپرداخت‌شده: {s.get('paid_month',0):,}\nپرداخت‌نشده: {s.get('unpaid_month',0):,}\nوضعیت: {s.get('settle_status','')}\nشماره کارت: {b.get('bank_card','') or '—'}\nشبا: {b.get('bank_sheba','') or '—'}\nصاحب حساب: {b.get('bank_owner','') or '—'}"
        QMessageBox.information(self,'جزئیات تسویه',text)
    def pay(self):
        x=self._row()
        if not x:return
        if QMessageBox.question(self,'تسویه',f"تسویه «{x.get('name','')}» برای ماه جاری ثبت شود؟")!=QMessageBox.Yes:return
        try:
            with busy(button=self.settle, text='در حال ثبت تسویه...'):
                d=self.client.finance_settle(int(x['id']),{'action':'pay'})
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        QMessageBox.information(self,'تسویه',f"تسویه ثبت شد. شماره رسید: {d.get('receipt_no','—')}"); self.reload()
    def show_receipt(self):
        x=self._row()
        if not x:return
        try: d=self.client.finance_settlement_detail(int(x['id']),self.year.value(),self.month.currentIndex()+1)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        s=d.get('summary') or {}; settlement=s.get('settlement') or {}
        sid=settlement.get('id')
        if not sid:
            QMessageBox.information(self,'رسید','برای این نماینده هنوز رسیدی ثبت نشده است.'); return
        try: r=self.client.finance_settlement_receipt(int(sid))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        st=r.get('settlement') or {}; lines=r.get('lines') or []
        text=f"رسید: {st.get('receipt_no','—')}\nنماینده: {st.get('representative_name','')}\nتاریخ: {st.get('paid_at','')}\nمبلغ: {st.get('paid_amount',0):,}\n\nاقلام:\n" + '\n'.join(f"- {z.get('work_description','')} | {z.get('amount',0):,}" for z in lines)
        QMessageBox.information(self,'رسید تسویه',text)


class InvoicesTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.search=QLineEdit(); self.search.setPlaceholderText('مشتری، پذیرش، سریال یا فاکتور...'); self.table=QTableWidget(); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.load=QPushButton('جستجو'); self.edit=QPushButton('ثبت/ویرایش شماره فاکتور'); self.export_btn=QPushButton('خروجی CSV'); self.load.clicked.connect(self.reload); self.edit.clicked.connect(self.save); self.export_btn.clicked.connect(lambda: export_table_csv(self, self.table, 'invoices.csv'))
        bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(self.load); bar.addWidget(self.edit); bar.addWidget(self.export_btn); lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try:d=self.client.finance_invoices(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        self.rows=d.get('rows',[]); fill_table(self.table,self.rows,[('id','شناسه'),('reception_no','پذیرش'),('customer_name','مشتری'),('serial_number','سریال'),('device_type','دستگاه'),('status','وضعیت'),('invoice_number','شماره فاکتور'),('reception_date','تاریخ')])
    def save(self):
        r=self.table.currentRow()
        if r<0:return
        rid=int(self.table.item(r,0).text()); old=self.table.item(r,6).text() if self.table.item(r,6) else ''
        val,ok=__import__('PyQt5.QtWidgets',fromlist=['QInputDialog']).QInputDialog.getText(self,'شماره فاکتور','شماره فاکتور:',text=old)
        if not ok:return
        try:
            with busy(button=self.edit, text='در حال ذخیره...'):
                self.client.finance_invoice_save(rid,val.strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        self.reload()

class FinancePage(QWidget):
    """Finance support for the native client."""

    def __init__(self, client):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        tabs = QTabWidget()
        tabs.addTab(RepsDashboardTab(client), "خلاصه نمایندگان")
        tabs.addTab(WageHistoryTab(client), "تاریخچه دستمزد")
        tabs.addTab(MyWagesTab(client), "دستمزد من")
        tabs.addTab(WageRatesTab(client), "جدول دستمزد")
        tabs.addTab(FinanceFilesTab(client), "پرونده‌های مالی")
        tabs.addTab(SettlementsTab(client), "تسویه نمایندگان")
        tabs.addTab(InvoicesTab(client), "فاکتورها")
        self.tabs = tabs
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

    def open_tab(self, index):
        self.tabs.setCurrentIndex(max(0, min(index, self.tabs.count() - 1)))
        page = self.tabs.currentWidget()
        if hasattr(page, "reload"):
            page.reload()
