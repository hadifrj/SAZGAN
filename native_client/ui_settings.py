# -*- coding: utf-8 -*-
"""تنظیمات Native: اتصال به سرور (فاز اولیه) + مدیریت کاربران سیستم (فاز ۸، پورت‌شده)."""
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget, QFrame, QInputDialog, QCheckBox, QPlainTextEdit,
    QDoubleSpinBox, QScrollArea, QToolButton, QGridLayout, QSizePolicy,
    QGraphicsDropShadowEffect, QSpacerItem, QApplication,
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation
from config import get_server_url, save_config, normalize_url, load_config
from api_client import ApiError, SessionExpiredError
from ui_common import fill_table, module_card_style
from theme import C, SP, R

USER_COLUMNS = [
    ("id", "شناسه"), ("full_name", "نام کامل"), ("username", "نام کاربری"),
    ("role", "نقش"), ("province", "استان"), ("created_at", "تاریخ ایجاد"),
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


class ConnectionTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        card = QFrame()
        card.setObjectName("card")
        l = QVBoxLayout(card)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(10)
        heading = QLabel("اتصال به سرور")
        heading.setObjectName("sectionTitle")
        info = QLabel("آدرس سرور در این رایانه ذخیره می‌شود و در صفحه ورود دوباره لازم نیست وارد شود.")
        info.setWordWrap(True)
        info.setObjectName("pageSubtitle")
        self.url_edit = QLineEdit(get_server_url())
        self.url_edit.setPlaceholderText("مثلاً: 192.168.1.39:5000")
        self.save_btn = QPushButton("ذخیره آدرس سرور")
        self.save_btn.clicked.connect(self.save_server)
        row = QHBoxLayout()
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.save_btn)
        l.addWidget(heading)
        l.addWidget(info)
        l.addLayout(row)

        note = QLabel("تغییر آدرس برای ورود بعدی ذخیره می‌شود. برای اعمال آدرس جدید در همین نشست، از حساب خارج شوید و دوباره وارد شوید.")
        note.setWordWrap(True)
        note.setObjectName("pageSubtitle")
        l.addWidget(note)

        self.save_status = QLabel("")
        self.save_status.setObjectName("saveStatus")
        self.save_status.setAlignment(Qt.AlignCenter)
        self.save_status.setMinimumHeight(24)
        l.addWidget(self.save_status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)
        root.addStretch()
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self.save_status.clear)

    def save_server(self):
        url = normalize_url(self.url_edit.text())
        if not url:
            self.save_status.setStyleSheet("color:#b91c1c;")
            self.save_status.setText("آدرس سرور را وارد کنید.")
            self._status_timer.start(3000)
            return
        save_config({"url": url})
        self.url_edit.setText(url)
        self.save_status.setStyleSheet("color:#15803d;")
        self.save_status.setText("آدرس IP با موفقیت ذخیره شد.")
        self._status_timer.start(2500)


class _NewUserForm(QWidget):
    def __init__(self, client, on_created):
        super().__init__()
        self.client = client
        self.on_created = on_created
        self.setLayoutDirection(Qt.RightToLeft)

        self.role_combo = QComboBox()
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.full_name_edit = QLineEdit()
        self.rep_combo = QComboBox()

        form = QFormLayout()
        form.addRow("نقش:", self.role_combo)
        form.addRow("نام کاربری:", self.username_edit)
        form.addRow("رمز عبور:", self.password_edit)
        self.full_name_row_label = QLabel("نام کامل:")
        form.addRow(self.full_name_row_label, self.full_name_edit)
        self.rep_row_label = QLabel("نماینده:")
        form.addRow(self.rep_row_label, self.rep_combo)

        self.submit_btn = QPushButton("ایجاد کاربر")
        self.submit_btn.clicked.connect(self._submit)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        title = QLabel("کاربر جدید")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addLayout(form)
        outer.addWidget(self.submit_btn)
        outer.addWidget(self.status_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)

    def set_options(self, roles: list, representatives: list):
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        for r in roles:
            self.role_combo.addItem(r, r)
        self.role_combo.blockSignals(False)
        self.rep_combo.clear()
        for rep in representatives:
            name = rep.get("company_name") or f"{rep.get('first_name', '')} {rep.get('last_name', '')}"
            self.rep_combo.addItem(f"{name} ({rep.get('province', '')})", rep.get("id"))
        self._on_role_changed()

    def _on_role_changed(self):
        is_provincial_tech = self.role_combo.currentData() == "تکنسین استانی"
        self.rep_row_label.setVisible(is_provincial_tech)
        self.rep_combo.setVisible(is_provincial_tech)
        self.full_name_row_label.setVisible(not is_provincial_tech)
        self.full_name_edit.setVisible(not is_provincial_tech)

    def _submit(self):
        role = self.role_combo.currentData()
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not (role and username and password):
            QMessageBox.warning(self, "فیلدهای الزامی", "نقش، نام کاربری و رمز عبور را پر کنید.")
            return
        data = {"role": role, "username": username, "password": password}
        if role == "تکنسین استانی":
            rep_id = self.rep_combo.currentData()
            if not rep_id:
                QMessageBox.warning(self, "فیلدهای الزامی", "یک نماینده انتخاب کنید.")
                return
            data["representative_id"] = rep_id
        else:
            full_name = self.full_name_edit.text().strip()
            if not full_name:
                QMessageBox.warning(self, "فیلدهای الزامی", "نام کامل را وارد کنید.")
                return
            data["full_name"] = full_name

        self.submit_btn.setEnabled(False)
        self.status_label.setText("در حال ایجاد...")
        try:
            self.client.settings_user_new(data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            self.status_label.setText(f"خطا: {e}")
            QMessageBox.critical(self, "ایجاد ناموفق", str(e))
            return
        finally:
            self.submit_btn.setEnabled(True)

        self.status_label.setText("کاربر با موفقیت ایجاد شد.")
        self.username_edit.clear()
        self.password_edit.clear()
        self.full_name_edit.clear()
        self.on_created()


class UsersActiveTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)
        self._can_manage = False

        self.new_form = _NewUserForm(client, on_created=self.reload)

        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.setProperty("variant", "secondary")
        self.reload_btn.clicked.connect(self.reload)
        self.deactivate_btn = QPushButton("غیرفعال کردن کاربر انتخاب‌شده")
        self.deactivate_btn.setProperty("variant", "danger")
        self.deactivate_btn.clicked.connect(self._deactivate_selected)

        self.table = QTableWidget()

        top = QHBoxLayout()
        top.addWidget(self.reload_btn)
        top.addStretch()
        top.addWidget(self.deactivate_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.new_form)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)

        self.reload()

    def reload(self):
        try:
            data = self.client.settings_users()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self._can_manage = bool(data.get("can_manage"))
        self.deactivate_btn.setVisible(self._can_manage)
        self.new_form.set_options(data.get("roles", []), data.get("representatives", []))
        fill_table(self.table, data.get("users", []), USER_COLUMNS)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def _deactivate_selected(self):
        user_id = self._selected_id()
        if not user_id:
            QMessageBox.information(self, "انتخاب ردیف", "ابتدا یک کاربر را از جدول انتخاب کنید.")
            return
        if QMessageBox.question(self, "تأیید", "این کاربر غیرفعال شود؟") != QMessageBox.Yes:
            return
        try:
            self.client.settings_user_deactivate(user_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.reload()


class UsersArchiveTab(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)
        self._can_manage = False

        self.reload_btn = QPushButton("بارگذاری مجدد")
        self.reload_btn.setProperty("variant", "secondary")
        self.reload_btn.clicked.connect(self.reload)
        self.activate_btn = QPushButton("فعال‌سازی کاربر انتخاب‌شده")
        self.activate_btn.clicked.connect(self._activate_selected)

        self.table = QTableWidget()

        top = QHBoxLayout()
        top.addWidget(self.reload_btn)
        top.addStretch()
        top.addWidget(self.activate_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)

        self.reload()

    def reload(self):
        try:
            data = self.client.settings_users_archive()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self._can_manage = bool(data.get("can_manage"))
        self.activate_btn.setVisible(self._can_manage)
        fill_table(self.table, data.get("users", []), USER_COLUMNS)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def _activate_selected(self):
        user_id = self._selected_id()
        if not user_id:
            QMessageBox.information(self, "انتخاب ردیف", "ابتدا یک کاربر را از جدول انتخاب کنید.")
            return
        try:
            self.client.settings_user_activate(user_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.reload()


class UsersTab(QWidget):
    """فعلاً فقط «مدیریت کاربران» - بقیه‌ی settings.py در فازهای بعدی."""

    def __init__(self, client):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        note = QLabel(
            "این بخش کاربران سیستم (پرسنل) را مدیریت می‌کند - نه طرف‌حساب‌های مشتری. "
            "برای مشتریان از «تنظیمات ← طرف حساب‌ها» استفاده کنید."
        )
        note.setWordWrap(True)
        note.setObjectName("pageSubtitle")

        inner_tabs = QTabWidget()
        inner_tabs.setLayoutDirection(Qt.RightToLeft)
        inner_tabs.addTab(UsersActiveTab(client), "کاربران فعال")
        inner_tabs.addTab(UsersArchiveTab(client), "آرشیو (غیرفعال)")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(note)
        layout.addWidget(inner_tabs, 1)



class _JsonTableTab(QWidget):
    def __init__(self, client, loader, columns, title, creator=None, editor=None, deleter=None):
        super().__init__(); self.client=client; self.loader=loader; self.columns=columns; self.creator=creator; self.editor=editor; self.deleter=deleter; self.setLayoutDirection(Qt.RightToLeft)
        self.title=title; self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search=QLineEdit(); self.search.setPlaceholderText("جستجو")
        refresh=QPushButton("بارگذاری مجدد"); refresh.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(refresh)
        if creator: add=QPushButton("افزودن"); add.clicked.connect(self.add_item); bar.addWidget(add)
        if editor: edit=QPushButton("ویرایش"); edit.clicked.connect(self.edit_item); bar.addWidget(edit)
        if deleter: delete=QPushButton("حذف/غیرفعال‌سازی"); delete.clicked.connect(self.delete_item); bar.addWidget(delete)
        lay=QVBoxLayout(self); lay.addWidget(QLabel(title)); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try: d=self.loader(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,"خطا",str(e)); return
        fill_table(self.table,d.get('rows',[]),self.columns)
    def _selected(self):
        r=self.table.currentRow()
        if r<0:return None
        return {k:(self.table.item(r,i).text() if self.table.item(r,i) else '') for i,(k,_) in enumerate(self.columns)}
    def add_item(self):
        if self.creator: self.creator(self)
    def edit_item(self):
        row=self._selected()
        if not row: QMessageBox.information(self,"انتخاب","یک ردیف را انتخاب کنید."); return
        if self.editor: self.editor(self,row)
    def delete_item(self):
        row=self._selected()
        if not row: QMessageBox.information(self,"انتخاب","یک ردیف را انتخاب کنید."); return
        if QMessageBox.question(self,"تأیید","این مورد حذف/غیرفعال شود؟") != QMessageBox.Yes:return
        if self.deleter: self.deleter(self,row)

class CalendarTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        add=QPushButton("افزودن تعطیلی"); add.clicked.connect(self.add); edit=QPushButton("ویرایش"); edit.clicked.connect(self.edit); delete=QPushButton("حذف"); delete.clicked.connect(self.delete); ref=QPushButton("بارگذاری"); ref.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(add); bar.addWidget(edit); bar.addWidget(delete); bar.addWidget(ref); bar.addStretch(1); lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try:d=self.client.calendar_holidays()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        fill_table(self.table,d.get('rows',[]),[("id","شناسه"),("holiday_date","تاریخ"),("title","عنوان")])
    def add(self):
        date,ok=QInputDialog.getText(self,"تعطیلی جدید","تاریخ (مثلاً 1405/01/01):")
        if not ok:return
        title,ok=QInputDialog.getText(self,"عنوان","عنوان:")
        if not ok:return
        try:self.client.calendar_add(date,title)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.reload()
    def _selected(self):
        r=self.table.currentRow()
        if r<0:return None
        cols=[("id","شناسه"),("holiday_date","تاریخ"),("title","عنوان")]
        return {k:(self.table.item(r,i).text() if self.table.item(r,i) else '') for i,(k,_) in enumerate(cols)}
    def edit(self):
        row=self._selected()
        if not row: QMessageBox.information(self,"انتخاب","یک ردیف را انتخاب کنید."); return
        date,ok=QInputDialog.getText(self,"ویرایش تعطیلی","تاریخ (مثلاً 1405/01/01):",text=row.get("holiday_date",""))
        if not ok:return
        title,ok=QInputDialog.getText(self,"عنوان","عنوان:",text=row.get("title",""))
        if not ok:return
        try:self.client.calendar_edit(int(row["id"]),date,title)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.reload()
    def delete(self):
        row=self._selected()
        if not row: QMessageBox.information(self,"انتخاب","یک ردیف را انتخاب کنید."); return
        if QMessageBox.question(self,"تأیید","این تعطیلی حذف شود؟") != QMessageBox.Yes:return
        try:self.client.calendar_delete(int(row["id"]))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.reload()

class CompanyTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.inputs={}
        form=QFormLayout(); fields=[('company_name','نام شرکت'),('company_mobile','موبایل'),('company_phone','تلفن'),('company_postal_code','کد پستی'),('company_address','آدرس')]
        for k,l in fields: w=QLineEdit(); self.inputs[k]=w; form.addRow(l,w)
        save=QPushButton("ذخیره"); save.clicked.connect(self.save); lay=QVBoxLayout(self); lay.addLayout(form); lay.addWidget(save); self.reload()
    def reload(self):
        try:d=self.client.company_get()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        for k,w in self.inputs.items():w.setText(str(d.get('data',{}).get(k) or ''))
    def save(self):
        try:self.client.company_save({k:w.text().strip() for k,w in self.inputs.items()})
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"ذخیره شد","اطلاعات شرکت ذخیره شد.")

class AppListsTab(_JsonTableTab):
    def __init__(self,client):
        self.active_key='internal_repair_statuses'
        super().__init__(client,lambda q:client.app_lists(self.active_key,q),[("id","شناسه"),("value","مقدار"),("is_active","فعال")],"لیست‌های سیستمی",self._add,self._edit,self._delete)
    def _edit(self, _, row):
        v,ok=QInputDialog.getText(self,"ویرایش گزینه","مقدار:",text=row.get("value", ""))
        if not ok or not v.strip(): return
        try:self.client.app_list_edit(int(row["id"]),v.strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.reload()
    def _delete(self, _, row):
        try:self.client.app_list_delete(int(row["id"]))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.reload()
    def _add(self, _):
        v,ok=QInputDialog.getText(self,"افزودن گزینه","مقدار:")
        if ok and v.strip():
            try:self.client.app_list_add(self.active_key,v.strip())
            except SessionExpiredError:
                _notify_session_expired(self)
                return
            except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
            self.reload()

class GeoTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.prov=QComboBox(); self.city=QComboBox(); self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.prov.currentTextChanged.connect(self.reload_cities); ref=QPushButton("آمار / بارگذاری"); ref.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(self.prov); bar.addWidget(self.city); bar.addWidget(ref); lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table)

        sep=QFrame(); sep.setFrameShape(QFrame.HLine); lay.addWidget(sep)
        lay.addWidget(QLabel("موتور فاصله (تخصیص تکنسین/نماینده)"))

        self.dist_table=QTableWidget(); self.dist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.dist_table)

        self.factor_spin=QDoubleSpinBox(); self.factor_spin.setRange(1.0,2.5); self.factor_spin.setSingleStep(0.05); self.factor_spin.setDecimals(2)
        factor_btn=QPushButton("ثبت ضریب"); factor_btn.clicked.connect(self.save_factor)
        factor_bar=QHBoxLayout(); factor_bar.addWidget(QLabel("ضریب جاده:")); factor_bar.addWidget(self.factor_spin); factor_bar.addWidget(factor_btn)
        lay.addLayout(factor_bar)

        self.method_combo=QComboBox(); self.method_combo.addItem("تقریبی (هوایی × ضریب)","haversine"); self.method_combo.addItem("مسیر جاده‌ای OSRM","osrm")
        self.osrm_edit=QLineEdit(); self.osrm_edit.setPlaceholderText("آدرس سرور OSRM (اختیاری)")
        method_btn=QPushButton("ثبت روش"); method_btn.clicked.connect(self.save_method)
        method_bar=QHBoxLayout(); method_bar.addWidget(QLabel("روش محاسبه:")); method_bar.addWidget(self.method_combo); method_bar.addWidget(self.osrm_edit); method_bar.addWidget(method_btn)
        lay.addLayout(method_bar)

        seed_btn=QPushButton("بارگذاری مختصات شهرها از فایل"); seed_btn.clicked.connect(self.seed_coords)
        lay.addWidget(seed_btn)

        self.reload()
    def reload(self):
        try:d=self.client.geo()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.prov.clear(); self.prov.addItems(d.get('provinces',[])); self.reload_cities(self.prov.currentText()); fill_table(self.table,[d.get('stats',{})],[("total_provinces","استان"),("total_counties","شهرستان"),("total_cities","شهر"),("with_coords","دارای مختصات")])
        self.reload_distance()
    def reload_cities(self,p):
        try:d=self.client.geo_cities(p)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError:return
        self.city.clear(); self.city.addItems(d.get('cities',[]))
    def reload_distance(self):
        try:d=self.client.distance()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.factor_spin.setValue(float(d.get('road_factor') or 1.3))
        idx=self.method_combo.findData(d.get('distance_method') or 'haversine')
        if idx>=0: self.method_combo.setCurrentIndex(idx)
        self.osrm_edit.setText(d.get('osrm_url') or '')
        fill_table(self.dist_table,[d.get('stats',{})],[("total_cities","کل شهرها"),("with_coords","دارای مختصات")])
    def save_factor(self):
        try:self.client.distance_set_factor(self.factor_spin.value())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"ذخیره شد","ضریب جاده ثبت شد.")
        self.reload_distance()
    def save_method(self):
        try:self.client.distance_set_method(self.method_combo.currentData(),self.osrm_edit.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"ذخیره شد","روش محاسبه مسافت ثبت شد.")
        self.reload_distance()
    def seed_coords(self):
        try:d=self.client.distance_seed()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"بارگذاری شد",d.get('message') or 'مختصات به‌روزرسانی شد.')
        self.reload_distance()

class HelpTipsTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.edits={}; lay=QVBoxLayout(self); ref=QPushButton("بارگذاری"); ref.clicked.connect(self.reload); lay.addWidget(ref)
        self.form=QFormLayout(); lay.addLayout(self.form); save=QPushButton("ذخیره همه"); save.clicked.connect(self.save); lay.addWidget(save); self.reload()
    def reload(self):
        try:d=self.client.help_tips()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        while self.form.count(): self.form.takeAt(0).widget().deleteLater()
        self.edits={}
        for x in d.get('rows',[]): w=QPlainTextEdit(); w.setPlainText(x.get('current') or ''); w.setFixedHeight(65); self.edits[x['key']]=w; self.form.addRow(x.get('label'),w)
    def save(self):
        try:self.client.help_tips_save({k:w.toPlainText() for k,w in self.edits.items()})
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"ذخیره شد","راهنماها ذخیره شدند.")

class ChatEmojisTab(QWidget):
    """تنظیمات ایموجی چت؛ همان مسیر وب /settings/chat-emojis، بدون endpoint جدید."""
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(self)
        title = QLabel("ایموجی‌های چت")
        title.setStyleSheet("font-weight:700;font-size:15px;")
        lay.addWidget(title)
        lay.addWidget(QLabel("ایموجی‌ها را با کاما جدا کنید. این تنظیم فقط از بخش تنظیمات سیستم در دسترس است."))
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("👍, ❤️, 😂, 😮, 😢, 😡")
        self.edit.setFixedHeight(150)
        lay.addWidget(self.edit)
        bar = QHBoxLayout()
        reload_btn = QPushButton("بارگذاری")
        save_btn = QPushButton("ذخیره")
        reload_btn.clicked.connect(self.reload)
        save_btn.clicked.connect(self.save)
        bar.addWidget(reload_btn)
        bar.addStretch()
        bar.addWidget(save_btn)
        lay.addLayout(bar)
        lay.addStretch(1)
        self.reload()

    def reload(self):
        try:
            self.edit.setPlainText(", ".join(self.client.chat_emojis_get()))
        except SessionExpiredError:
            _notify_session_expired(self)
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))

    def save(self):
        vals = [x.strip() for x in self.edit.toPlainText().replace("،", ",").split(",") if x.strip()]
        if not vals:
            QMessageBox.warning(self, "خطا", "حداقل یک ایموجی وارد کنید.")
            return
        try:
            self.client.chat_emojis_save(vals)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        QMessageBox.information(self, "ذخیره شد", "ایموجی‌های چت ذخیره شدند.")

class ProductsTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self.tabs=QTabWidget(); self.tabs.addTab(_JsonTableTab(client,lambda q:client.products_devices(q),[("id","شناسه"),("device_type","نوع دستگاه"),("model","مدل")],"دستگاه‌ها",self.add_device,self.edit_device,self.delete_device),"دستگاه‌ها"); self.tabs.addTab(_JsonTableTab(client,lambda q:client.products_warranty(q),[("id","شناسه"),("serial_number","سریال"),("customer_name","مشتری"),("device_type","نوع"),("model","مدل"),("installation_date","تاریخ نصب")],"شناسنامه کالا",self.add_warranty,self.edit_warranty,self.delete_warranty),"شناسنامه کالا"); self.tabs.addTab(_JsonTableTab(client,lambda q:client.products_parts(q),[("id","شناسه"),("warehouse_code","کد انبار"),("part_name","نام قطعه"),("device_type","نوع دستگاه"),("device_model","مدل")],"قطعات",self.add_part,self.edit_part,self.delete_part),"قطعات"); self.tabs.addTab(DeviceFoldersTab(client), "پرونده دستگاه‌ها"); lay=QVBoxLayout(self); lay.addWidget(self.tabs)
    def edit_device(self,_,x):
        a,ok=QInputDialog.getText(self,"ویرایش دستگاه","نوع دستگاه:",text=x.get("device_type",""));
        if not ok:return
        b,ok=QInputDialog.getText(self,"ویرایش دستگاه","مدل:",text=x.get("model",""));
        if ok:
            try:self.client.product_device_edit(int(x["id"]),{"device_type":a,"model":b})
            except SessionExpiredError:
                _notify_session_expired(self)
                return
            except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
            self.tabs.currentWidget().reload()
    def delete_device(self,_,x):
        try:self.client.product_device_delete(int(x["id"]))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.tabs.currentWidget().reload()
    def edit_part(self,_,x):
        vals=[]
        for k,l in (("warehouse_code","کد انبار"),("part_name","نام قطعه"),("device_type","نوع دستگاه"),("device_model","مدل دستگاه")):
            v,ok=QInputDialog.getText(self,"ویرایش قطعه",l,text=x.get(k,""));
            if not ok:return
            vals.append(v)
        try:self.client.product_part_edit(int(x["id"]),dict(zip(("warehouse_code","part_name","device_type","device_model"),vals)))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.tabs.currentWidget().reload()
    def delete_part(self,_,x):
        try:self.client.product_part_delete(int(x["id"]))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.tabs.currentWidget().reload()
    def edit_warranty(self,_,x):
        data={"serial_number":x.get("serial_number",""),"customer_name":x.get("customer_name",""),"device_type":x.get("device_type",""),"model":x.get("model",""),"production_date":x.get("production_date",""),"installation_date":x.get("installation_date","")}
        for k,l in (("serial_number","سریال"),("customer_name","مشتری"),("device_type","نوع دستگاه"),("model","مدل"),("production_date","تاریخ تولید"),("installation_date","تاریخ نصب")):
            v,ok=QInputDialog.getText(self,"ویرایش شناسنامه",l,text=data[k]);
            if not ok:return
            data[k]=v
        try:self.client.product_warranty_edit(int(x["id"]),data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.tabs.currentWidget().reload()
    def delete_warranty(self,_,x):
        try:self.client.product_warranty_delete(int(x["id"]))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.tabs.currentWidget().reload()

    def add_device(self,_):
        a,ok=QInputDialog.getText(self,"دستگاه","نوع دستگاه:");
        if not ok:return
        b,ok=QInputDialog.getText(self,"دستگاه","مدل:");
        if ok and a.strip() and b.strip(): self.client.product_device_add(a.strip(),b.strip()); self.tabs.currentWidget().reload()
    def add_part(self,_):
        a,ok=QInputDialog.getText(self,"قطعه","نام قطعه:");
        if ok and a.strip(): self.client.product_part_add(a.strip()); self.tabs.currentWidget().reload()
    def add_warranty(self,_):
        a,ok=QInputDialog.getText(self,"شناسنامه","سریال:");
        if not ok or not a.strip():return
        b,ok=QInputDialog.getText(self,"شناسنامه","نام مشتری:");
        if ok:self.client.product_warranty_add(a.strip(),b.strip()); self.tabs.currentWidget().reload()

class DeviceFoldersTab(_JsonTableTab):
    def __init__(self,client): super().__init__(client,lambda q:client.device_folders(q),[("serial_number","سریال"),("customer_name","مشتری"),("device_type","نوع دستگاه"),("model","مدل"),("status","آخرین وضعیت"),("reception_no","آخرین پذیرش")],"پرونده دستگاه")


class RepresentativesTab(QWidget):
    COLS=[('id','شناسه'),('rep_type','نوع'),('company_name','شرکت'),('first_name','نام'),('last_name','نام خانوادگی'),('phone','تماس'),('province','استان'),('city','شهر'),('status','وضعیت')]
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        self.search=QLineEdit(); self.search.setPlaceholderText('جستجو در نام، شرکت، تلفن، استان...'); self.search.returnPressed.connect(self.reload)
        self.table=QTableWidget(); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.new_btn=QPushButton('نماینده جدید'); self.edit_btn=QPushButton('ویرایش'); self.archive_btn=QPushButton('آرشیو'); self.refresh=QPushButton('بارگذاری')
        self.new_btn.clicked.connect(lambda:self._edit(None)); self.edit_btn.clicked.connect(self._edit_selected); self.archive_btn.clicked.connect(self._archive); self.refresh.clicked.connect(self.reload)
        bar=QHBoxLayout(); bar.addWidget(self.search,1); bar.addWidget(self.refresh); bar.addWidget(self.new_btn); bar.addWidget(self.edit_btn); bar.addWidget(self.archive_btn)
        lay=QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table); self.reload()
    def reload(self):
        try:d=self.client.settings_representatives(self.search.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        fill_table(self.table,d.get('rows',[]),self.COLS)
    def _row(self):
        r=self.table.currentRow();
        if r<0:return None
        return {k:(self.table.item(r,i).text() if self.table.item(r,i) else '') for i,(k,_) in enumerate(self.COLS)}
    def _edit_selected(self):
        x=self._row()
        if not x: QMessageBox.information(self,'انتخاب','یک نماینده را انتخاب کنید.'); return
        self._edit(x)
    def _edit(self,x):
        fields=[('rep_type','نوع (حقیقی/حقوقی)','حقیقی'),('company_name','نام شرکت',''),('first_name','نام',''),('last_name','نام خانوادگی',''),('father_name','نام پدر',''),('national_id','کد/شناسه ملی',''),('phone','تلفن',''),('province','استان',''),('county','شهرستان',''),('city','شهر',''),('address','آدرس',''),('guarantee_status','وضعیت ضمانت',''),('guarantee_amount','مبلغ ضمانت',''),('contact_person_name','مسئول تماس',''),('contact_person_phone','تلفن مسئول تماس',''),('status','وضعیت','فعال'),('archive_reason','علت آرشیو','')]
        data={}
        for k,label,default in fields:
            val,ok=QInputDialog.getText(self,'نماینده',label,text=str((x or {}).get(k) or default))
            if not ok:return
            data[k]=val.strip()
        try:
            if x:self.client.representative_edit(int(x['id']),data)
            else:self.client.representative_new(data)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e: QMessageBox.critical(self,'خطا',str(e)); return
        self.reload()
    def _archive(self):
        x=self._row()
        if not x:return
        if QMessageBox.question(self,'آرشیو','نماینده انتخاب‌شده آرشیو شود؟')!=QMessageBox.Yes:return
        try:self.client.representative_archive(int(x['id']))
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        self.reload()

class AccessTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft); self._data={}
        self.role=QComboBox(); self.role.currentIndexChanged.connect(self._show_role); self.table=QTableWidget(); self.save=QPushButton('ذخیره دسترسی‌های نقش'); self.save.clicked.connect(self._save)
        lay=QVBoxLayout(self); lay.addWidget(self.role); lay.addWidget(self.table); lay.addWidget(self.save); self.reload()
    def reload(self):
        try:self._data=self.client.settings_access()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        self.role.clear(); self.role.addItems(self._data.get('roles',[])); self._show_role()
    def _show_role(self,*_):
        role=self.role.currentText(); mods=self._data.get('modules',[]); amap=self._data.get('access_map',{}).get(role,{})
        self.table.setRowCount(len(mods)); self.table.setColumnCount(2); self.table.setHorizontalHeaderLabels(['ماژول','دسترسی']); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for i,m in enumerate(mods):
            self.table.setItem(i,0,QTableWidgetItem(m['label'])); cb=QCheckBox(); cb.setChecked(bool(amap.get(m['key']))); self.table.setCellWidget(i,1,cb)
    def _save(self):
        role=self.role.currentText(); amap={role:{}}
        for i,m in enumerate(self._data.get('modules',[])):
            cb=self.table.cellWidget(i,1); amap[role][m['key']]=1 if cb and cb.isChecked() else 0
        full=self._data.get('access_map',{}); full[role]=amap[role]
        try:self.client.settings_access_save({'access_map':__import__('json').dumps(full,ensure_ascii=False)})
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,'خطا',str(e));return
        QMessageBox.information(self,'ذخیره','ماتریس دسترسی ذخیره شد.'); self.reload()

class SystemInfoTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        lay=QVBoxLayout(self)
        form=QFormLayout()
        self.db_path_label=QLabel("—"); self.db_path_label.setWordWrap(True)
        self.host_label=QLabel("—")
        form.addRow("مسیر فایل دیتابیس:",self.db_path_label)
        form.addRow("آدرس host:",self.host_label)
        lay.addLayout(form)
        ref=QPushButton("بارگذاری مجدد"); ref.clicked.connect(self.reload); lay.addWidget(ref)
        lay.addStretch(1)
        self.reload()
    def reload(self):
        try:d=self.client.system_info()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.db_path_label.setText(d.get('active_db_path') or '—')
        self.host_label.setText(d.get('active_host') or '—')


class AboutTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        lay=QVBoxLayout(self)
        self.version_label=QLabel("—"); self.version_label.setStyleSheet("font-weight:700;")
        lay.addWidget(self.version_label)
        self.changelog_view=QPlainTextEdit(); self.changelog_view.setReadOnly(True)
        lay.addWidget(self.changelog_view,1)
        ref=QPushButton("بارگذاری مجدد"); ref.clicked.connect(self.reload); lay.addWidget(ref)
        self.reload()
    def reload(self):
        try:d=self.client.about_info()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        ver=d.get('version') or {}
        label=ver.get('version_label_full') or ver.get('version_label') or 'v0.0.0'
        self.version_label.setText(f"نسخه: {label}")
        lines=[]
        for entry in d.get('entries') or []:
            lines.append(f"## {entry.get('title','')}")
            for sec in entry.get('sections') or []:
                lines.append(f"### {sec.get('name','')}")
                for item in sec.get('items') or []:
                    lines.append(f"- {item}")
            lines.append("")
        self.changelog_view.setPlainText("\n".join(lines))


class ActivationTab(QWidget):
    def __init__(self,client):
        super().__init__(); self.client=client; self.setLayoutDirection(Qt.RightToLeft)
        lay=QVBoxLayout(self)
        self.status_label=QLabel("—"); self.status_label.setStyleSheet("font-weight:700;")
        self.key_label=QLabel("—")
        self.owner_label=QLabel("—")
        self.activated_label=QLabel("—")
        form=QFormLayout()
        form.addRow("وضعیت فعلی:",self.status_label)
        form.addRow("کلید ثبت‌شده:",self.key_label)
        form.addRow("نام مالک:",self.owner_label)
        form.addRow("تاریخ فعال‌سازی:",self.activated_label)
        lay.addLayout(form)

        sep=QFrame(); sep.setFrameShape(QFrame.HLine); lay.addWidget(sep)
        self.key_edit=QLineEdit(); self.key_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.owner_edit=QLineEdit(); self.owner_edit.setPlaceholderText("نام شرکت یا سازمان (اختیاری)")
        form2=QFormLayout()
        form2.addRow("کلید فعال‌سازی:",self.key_edit)
        form2.addRow("نام سازمان:",self.owner_edit)
        lay.addLayout(form2)
        activate_btn=QPushButton("ثبت و فعال‌سازی"); activate_btn.clicked.connect(self.activate)
        lay.addWidget(activate_btn)
        lay.addStretch(1)
        self.reload()
    def reload(self):
        try:d=self.client.activation()
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        status=d.get('license_status') or 'inactive'
        status_map={'active':'فعال','trial':'آزمایشی'}
        self.status_label.setText(status_map.get(status,'غیرفعال / ثبت‌نشده'))
        self.key_label.setText(d.get('license_key_masked') or '—')
        self.owner_label.setText(d.get('license_owner') or '—')
        self.activated_label.setText(d.get('license_activated_at') or '—')
    def activate(self):
        key=self.key_edit.text().strip()
        if len(key.replace(' ','')) < 8:
            QMessageBox.warning(self,"خطا","کلید فعال‌سازی معتبر نیست (حداقل ۸ کاراکتر).")
            return
        try:d=self.client.activation_activate(key,self.owner_edit.text().strip())
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        QMessageBox.information(self,"فعال شد",d.get('message') or 'نرم‌افزار با موفقیت فعال شد.')
        self.key_edit.clear(); self.owner_edit.clear()
        self.reload()



# ---------------------------------------------------------------------------
# داشبورد تنظیمات: آکاردئون + کارت‌های کوچک
# ---------------------------------------------------------------------------

class _SettingsCard(QFrame):
    """کارت تخت و کوچک برای ورود سریع به یک زیرصفحه تنظیمات."""
    def __init__(self, title, description, icon, accent, widget_factory, section):
        super().__init__()
        self.title = title
        self.description = description
        self.icon = icon
        self.accent = accent
        self.widget_factory = widget_factory
        self.section = section
        self.detail_widget = None
        self.setObjectName("settingsCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(210, 168)
        self.setMinimumHeight(176)
        self.setMaximumHeight(188)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        icon_label = QLabel(icon)
        icon_label.setObjectName("moduleCardIcon")
        icon_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("moduleCardTitle")
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("moduleCardDescription")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 1)
        action_label = QLabel("ورود به تنظیمات  ←")
        action_label.setObjectName("moduleCardAction")
        action_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(action_label)

        self._apply_accent(accent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(Qt.black)
        # سایه در QSS قابل کنترل دقیق نیست؛ شدت آن را کم نگه می‌داریم.
        shadow.setColor(__import__("PyQt5.QtGui", fromlist=["QColor"]).QColor(15, 23, 42, 22))
        self.setGraphicsEffect(shadow)

    def _apply_accent(self, accent):
        # Existing settings metadata passes a soft color.  Convert that legacy
        # value into the shared semantic card treatment while preserving a
        # distinct identity for the settings dashboard.
        self.setProperty("cardRole", "module")
        self.setStyleSheet(module_card_style("settings"))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.section.open_card(self)
        super().mousePressEvent(event)


class _SettingsCardGrid(QWidget):
    """گرید واکنش‌گرا؛ تعداد ستون‌ها با عرض پنل تغییر می‌کند."""
    def __init__(self, section):
        super().__init__()
        self.section = section
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 4, 0, 4)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.cards = []

    def add_card(self, card):
        self.cards.append(card)
        self.reflow()

    def reflow(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(self)
        visible = [c for c in self.cards if c.isVisible()]
        width = max(self.width(), 1)
        cols = 4 if width >= 980 else 3 if width >= 700 else 2 if width >= 440 else 1
        for i, card in enumerate(visible):
            self.grid.addWidget(card, i // cols, i % cols)

    def resizeEvent(self, event):
        self.reflow()
        super().resizeEvent(event)


class _AccordionSection(QFrame):
    """یک بخش آکاردئونی با انیمیشن نرم و امکان نمایش جزئیات کارت."""
    def __init__(self, title, icon, section_items):
        super().__init__()
        self.setObjectName("settingsAccordion")
        self.section_items = section_items
        self.expanded = False
        self.active_card = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QToolButton()
        self.header.setObjectName("settingsAccordionHeader")
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setText(f"{icon}   {title}   ·   {len(section_items)} مورد")
        self.header.setArrowType(Qt.DownArrow)
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.clicked.connect(self.toggle)
        root.addWidget(self.header)

        self.body = QFrame()
        self.body.setObjectName("settingsAccordionBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(14, 10, 14, 14)
        body_layout.setSpacing(10)

        self.card_grid = _SettingsCardGrid(self)
        body_layout.addWidget(self.card_grid)

        self.detail = QFrame()
        self.detail.setObjectName("settingsDetail")
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.setSpacing(8)
        self.back_btn = QToolButton()
        self.back_btn.setObjectName("settingsBackButton")
        self.back_btn.setText("‹  بازگشت به کارت‌ها")
        self.back_btn.clicked.connect(self.close_detail)
        detail_layout.addWidget(self.back_btn, 0, Qt.AlignRight)
        self.detail_title = QLabel()
        self.detail_title.setObjectName("settingsDetailTitle")
        detail_layout.addWidget(self.detail_title)
        self.detail_host = QFrame()
        self.detail_host.setObjectName("settingsDetailHost")
        self.detail_layout = QVBoxLayout(self.detail_host)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.detail_host)
        self.detail.hide()
        body_layout.addWidget(self.detail)

        root.addWidget(self.body)
        self.body.hide()
        self.animation = QPropertyAnimation(self.body, b"maximumHeight", self)
        self.animation.setDuration(220)
        self.body.setMaximumHeight(0)

        for item in section_items:
            card = _SettingsCard(*item, section=self)
            self.card_grid.add_card(card)

    def toggle(self, checked=None):
        if self.expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        self.expanded = True
        self.header.setChecked(True)
        self.header.setArrowType(Qt.UpArrow)
        self.body.show()
        self.card_grid.reflow()
        target = max(self.body.sizeHint().height(), self.body.minimumSizeHint().height(), 120)
        self.animation.stop()
        self.animation.setStartValue(0)
        self.animation.setEndValue(target)
        self.animation.start()

    def collapse(self):
        self.expanded = False
        self.header.setChecked(False)
        self.header.setArrowType(Qt.DownArrow)
        self.animation.stop()
        self.animation.setStartValue(self.body.height())
        self.animation.setEndValue(0)
        self.animation.finished.connect(self._hide_after_collapse)
        self.animation.start()

    def _hide_after_collapse(self):
        try:
            self.animation.finished.disconnect(self._hide_after_collapse)
        except TypeError:
            pass
        if not self.expanded:
            self.body.hide()

    def open_card(self, card):
        if not self.expanded:
            self.expand()
        self.active_card = card
        self.card_grid.hide()
        self.detail_title.setText(f"{card.icon}  {card.title}")
        if card.detail_widget is None:
            card.detail_widget = card.widget_factory()
            card.detail_widget.setParent(self.detail_host)
            card.detail_layout.addWidget(card.detail_widget)
        self.detail.show()
        QTimer.singleShot(0, self._refresh_height)

    def close_detail(self):
        self.detail.hide()
        self.card_grid.show()
        self.card_grid.reflow()
        self.active_card = None
        QTimer.singleShot(0, self._refresh_height)

    def _refresh_height(self):
        if not self.expanded:
            return
        target = max(self.body.sizeHint().height(), 120)
        self.animation.stop()
        self.animation.setStartValue(self.body.height())
        self.animation.setEndValue(target)
        self.animation.start()

    def filter_cards(self, query):
        query = (query or "").strip().lower()
        matched = 0
        for card in self.card_grid.cards:
            hay = f"{card.title} {card.description}".lower()
            visible = not query or query in hay
            card.setVisible(visible)
            if visible:
                matched += 1
        self.card_grid.reflow()
        return matched


class ThemeDisplayTab(QWidget):
    """Shared visual theme selector for Native; mirrors Web/PWA preset names."""
    def __init__(self):
        super().__init__(); self.setLayoutDirection(Qt.RightToLeft)
        root=QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(12)
        title=QLabel("تم و نمایش"); title.setObjectName("pageTitle"); root.addWidget(title)
        info=QLabel("ظاهر کامل سازگان را انتخاب کنید. انتخاب با Web و PWA هم‌نام است."); info.setObjectName("pageSubtitle"); info.setWordWrap(True); root.addWidget(info)
        self.combo=QComboBox(); self.combo.addItem("Minimal Premium — پیش‌فرض", "minimal_premium"); self.combo.addItem("Light Modern Indigo", "light_modern_indigo"); self.combo.addItem("Dark Modern Indigo", "dark_modern_indigo")
        cur=str(load_config().get("ui_theme", "minimal_premium") or "minimal_premium"); idx=self.combo.findData(cur); self.combo.setCurrentIndex(max(0,idx)); root.addWidget(self.combo)
        save=QPushButton("اعمال تم"); root.addWidget(save); root.addStretch(1)
        def apply_choice():
            save_config({"ui_theme":self.combo.currentData()});
            from theme import apply_theme
            apply_theme(QApplication.instance()); self.style().unpolish(self); self.style().polish(self); self.update()
            QMessageBox.information(self,"تم و نمایش","تم جدید اعمال شد.")
        save.clicked.connect(apply_choice)

class SettingsPage(QWidget):
    """داشبورد یکپارچه تنظیمات؛ منطق فرم‌ها و APIهای تب‌های قدیمی حفظ می‌شود."""
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        self._legacy_cards = []

        title = QLabel("تنظیمات")
        title.setObjectName("pageTitle")
        sub = QLabel("مدیریت یکپارچه هویت، داده‌ها، ارتباطات، کاربران و محصولات")
        sub.setObjectName("pageSubtitle")

        self.search = QLineEdit()
        self.search.setObjectName("settingsSearch")
        self.search.setPlaceholderText("جستجوی سریع در تنظیمات...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_settings)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 4, 24)
        content_layout.setSpacing(12)

        sections = [
            ("ظاهر", "◐", [
                ("تم و نمایش", "انتخاب Light Modern Indigo، Dark Modern Indigo یا Minimal Premium", "◐", "#eef2ff", lambda: ThemeDisplayTab()),
            ]),
            ("هویت و شرکت", "◉", [
                ("شرکت", "اطلاعات و مشخصات شرکت", "⌂", "#eff6ff", lambda: CompanyTab(client)),
                ("درباره / تاریخچه تغییرات", "نسخه و تاریخچه تغییرات", "ⓘ", "#f8fafc", lambda: AboutTab(client)),
                ("فعال‌سازی نرم‌افزار", "وضعیت مجوز و فعال‌سازی", "✓", "#f0fdf4", lambda: ActivationTab(client)),
            ]),
            ("تنظیمات نرم‌افزار و داده مرجع", "⚙", [
                ("تنظیمات نرم‌افزار", "فهرست‌ها و گزینه‌های پایه", "⚙", "#f8fafc", lambda: AppListsTab(client)),
                ("استان / شهر و مسافت", "داده‌های جغرافیایی و مسافت", "⌖", "#f0fdfa", lambda: GeoTab(client)),
                ("تقویم", "تنظیمات تقویم و تاریخ", "▣", "#f5f3ff", lambda: CalendarTab(client)),
                ("ایموجی‌های چت", "مدیریت ایموجی‌های گفتگو", "☺", "#fff7ed", lambda: ChatEmojisTab(client)),
                ("راهنماهای فرم‌ها", "راهنمای استفاده از فرم‌ها", "?", "#fefce8", lambda: HelpTipsTab(client)),
            ]),
            ("ارتباط و اتصال", "↔", [
                ("اتصال به سرور", "آدرس و تنظیمات اتصال", "⇄", "#eff6ff", lambda: ConnectionTab()),
                ("اطلاعات سیستم", "مشخصات محیط و دیتابیس", "▤", "#f8fafc", lambda: SystemInfoTab(client)),
            ]),
            ("مدیریت کاربران و دسترسی", "♙", [
                ("کاربران سیستم", "کاربران فعال و آرشیو", "♙", "#f0fdf4", lambda: UsersTab(client)),
                ("دسترسی‌ها", "مدیریت دسترسی نقش‌ها", "☷", "#faf5ff", lambda: AccessTab(client)),
            ]),
            ("محصولات و نمایندگان", "▦", [
                ("مدیریت محصولات", "دستگاه‌ها، قطعات و شناسنامه کالا", "▦", "#fff7ed", lambda: ProductsTab(client)),
                ("نمایندگان", "مدیریت نمایندگان و اطلاعات آن‌ها", "◇", "#f0fdfa", lambda: RepresentativesTab(client)),
            ]),
        ]

        self.sections = []
        for section_index, (section_title, section_icon, items) in enumerate(sections):
            section = _AccordionSection(section_title, section_icon, items)
            self.sections.append(section)
            content_layout.addWidget(section)
            self._legacy_cards.extend(section.card_grid.cards)
            if section_index == 0:
                section.expand()
            else:
                section.collapse()

        content_layout.addStretch(1)
        scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(8)
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(self.search)
        root.addWidget(scroll, 1)

        self._apply_dashboard_style()

    def _apply_dashboard_style(self):
        self.setStyleSheet(f"""
            QLineEdit#settingsSearch {{
                background: {C["card"]};
                border: 1px solid {C["border"]};
                border-radius: {R["md"]}px;
                padding: 8px 12px;
                min-height: 32px;
                color: {C["text"]};
            }}
            QLineEdit#settingsSearch:focus {{
                border-color: {C["borderStrong"]};
            }}
            QScrollArea#settingsScroll {{
                background: transparent;
            }}
            QWidget#settingsContent {{
                background: transparent;
            }}
            QFrame#settingsAccordion {{
                background: {C["card"]};
                border: 1px solid {C["border"]};
                border-radius: {R["lg"]}px;
            }}
            QToolButton#settingsAccordionHeader {{
                background: transparent;
                border: 0;
                border-radius: {R["lg"]}px;
                padding: 13px 16px;
                min-height: 30px;
                color: {C["text"]};
                font-size: 10.5pt;
                font-weight: 800;
                text-align: right;
            }}
            QToolButton#settingsAccordionHeader:hover,
            QToolButton#settingsAccordionHeader:checked {{
                background: {C["accentSoft"]};
            }}
            QFrame#settingsAccordionBody {{
                background: transparent;
                border-top: 1px solid {C["border"]};
            }}
            QFrame#settingsDetail {{
                background: {C["bg"]};
                border: 1px solid {C["border"]};
                border-radius: {R["md"]}px;
            }}
            QToolButton#settingsBackButton {{
                background: transparent;
                border: 0;
                color: {C["muted"]};
                padding: 5px 8px;
            }}
            QToolButton#settingsBackButton:hover {{
                color: {C["text"]};
                background: {C["accentSoft"]};
                border-radius: {R["sm"]}px;
            }}
            QLabel#settingsDetailTitle {{
                color: {C["text"]};
                font-size: 11pt;
                font-weight: 800;
                padding: 0 4px 4px;
            }}
        """)

    def _filter_settings(self, text):
        for section in self.sections:
            matched = section.filter_cards(text)
            section.setVisible(matched > 0)
            if matched and text.strip() and not section.expanded:
                section.expand()
        if not text.strip():
            for i, section in enumerate(self.sections):
                section.setVisible(True)
                if i == 0 and not section.expanded:
                    section.expand()

    def open_tab(self, index):
        """سازگاری با فراخوانی قدیمی بر اساس شماره تب."""
        if not self._legacy_cards:
            return
        index = max(0, min(index, len(self._legacy_cards) - 1))
        card = self._legacy_cards[index]
        for section in self.sections:
            if card in section.card_grid.cards:
                if not section.expanded:
                    section.expand()
                section.open_card(card)
                return

