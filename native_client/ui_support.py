# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QTextBrowser, QComboBox, QMessageBox, QSplitter, QFileDialog,
    QDialog, QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from html import escape
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl
from api_client import ApiError, SessionExpiredError

POLL_INTERVAL_MS = 5000



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


class ThreadPanel(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.thread_id = None
        self.last_message_id = 0
        self.setLayoutDirection(Qt.RightToLeft)

        self.title_label = QLabel("گفتگویی انتخاب نشده")
        self.title_label.setObjectName("chatTitle")
        self.title_label.setStyleSheet("font-weight:700; font-size:14px;")
        self.close_btn = QPushButton("بستن گفتگو")
        self.close_btn.clicked.connect(lambda: self._do_close("close"))
        self.reopen_btn = QPushButton("بازگشایی")
        self.reopen_btn.clicked.connect(lambda: self._do_close("reopen"))

        top = QHBoxLayout()
        top.addWidget(self.close_btn)
        top.addWidget(self.reopen_btn)
        top.addWidget(self.title_label, 1)

        # QTextBrowser (not QTextEdit) is required here: setOpenExternalLinks
        # and the anchorClicked signal used below only exist on QTextBrowser.
        self.messages_view = QTextBrowser()
        self.messages_view.setObjectName("chatMessages")
        self.messages_view.setReadOnly(True)
        self.messages_view.setOpenExternalLinks(False)
        self.messages_view.anchorClicked.connect(lambda url: QDesktopServices.openUrl(QUrl(self.client.base_url + url.toString())) if hasattr(self.client, "base_url") else None)

        self.input_edit = QLineEdit()
        self.input_edit.setObjectName("chatComposer")
        self.input_edit.setPlaceholderText("پیام خود را بنویسید...")
        self.send_btn = QPushButton("ارسال")
        self.send_btn.setObjectName("chatSendButton")
        self.send_btn.clicked.connect(self.send_message)
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setToolTip("پیوست فایل")
        self.attach_btn.setObjectName("chatAttachButton")
        self.attach_btn.clicked.connect(self.send_attachment)
        self.input_edit.returnPressed.connect(self.send_message)

        bottom = QHBoxLayout()
        bottom.addWidget(self.attach_btn)
        bottom.addWidget(self.send_btn)
        bottom.addWidget(self.input_edit)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.messages_view, 1)
        layout.addLayout(bottom)
        quick_label = QLabel("جملات آماده")
        quick_label.setObjectName("chatQuickRepliesLabel")
        layout.addWidget(quick_label)
        # جملات آماده عمداً بعد از composer اضافه می‌شوند تا زیر کادر چت باشند.
        quick = QHBoxLayout(); quick.setSpacing(6)
        for label, text in (("پیگیری درخواست", "سلام، برای پیگیری درخواست پیام می‌دهم."), ("وضعیت دستگاه", "لطفاً وضعیت فعلی دستگاه را اعلام کنید."), ("مشکل برطرف نشده", "مشکل همچنان برطرف نشده است."), ("زمان مراجعه", "چه زمانی برای مراجعه یا پیگیری مناسب است؟")):
            btn = QPushButton(label); btn.setObjectName("chatQuickReply"); btn.setToolTip(text)
            btn.clicked.connect(lambda _=False, t=text: self._use_quick_reply(t)); quick.addWidget(btn)
        quick.addStretch(1)
        layout.addLayout(quick)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.timer.start(POLL_INTERVAL_MS)

    def _use_quick_reply(self, text):
        self.input_edit.setText(text)
        self.input_edit.setFocus()

    def open_thread(self, thread_id, subject=""):
        self.thread_id = thread_id
        self.last_message_id = 0
        self.messages_view.clear()
        self.title_label.setText(subject or f"گفتگو #{thread_id}")
        self.load_all()

    def load_all(self):
        if not self.thread_id:
            return
        try:
            data = self.client.support_thread_messages(self.thread_id, after=0)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.messages_view.clear()
        for m in data.get("messages", []):
            self._append_message(m)

    def poll(self):
        if not self.thread_id:
            return
        try:
            data = self.client.support_thread_messages(self.thread_id, after=self.last_message_id)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError:
            return
        for m in data.get("messages", []):
            self._append_message(m)

    def _append_message(self, m):
        self.last_message_id = max(self.last_message_id, m.get("id", 0))
        mine = m.get("sender_type") == "support"
        who = "من" if mine else (m.get("sender_name") or "کاربر")
        body = escape(str(m.get("body") or "")).replace("\n", "<br>")
        attachment = m.get("attachment_original") or m.get("attachment_filename")
        link = f'<br><a href="/support/uploads/{escape(str(attachment))}">📎 {escape(str(attachment))}</a>' if attachment else ""
        side, bg, fg = ("right", "#111827", "#ffffff") if mine else ("left", "#ffffff", "#111827")
        html = f"<div style='margin:8px 0;text-align:{side};'><span style='display:inline-block;max-width:72%;background:{bg};color:{fg};border:1px solid #e5e7eb;border-radius:14px;padding:9px 12px;text-align:right;'><b>{escape(str(who))}</b><br>{body}{link}<br><small>{escape(str(m.get('created_at','')))}</small></span></div>"
        self.messages_view.append(html)
        bar = self.messages_view.verticalScrollBar(); bar.setValue(bar.maximum())

    def send_message(self):
        if not self.thread_id:
            return
        text = self.input_edit.text().strip()
        if not text:
            return
        try:
            self.client.support_thread_send(self.thread_id, text)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        self.input_edit.clear()
        self.poll()

    def send_attachment(self):
        if not self.thread_id: return
        path,_=QFileDialog.getOpenFileName(self,"انتخاب فایل")
        if not path:return
        try:self.client.support_thread_send(self.thread_id,"",file_path=path)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:QMessageBox.critical(self,"خطا",str(e));return
        self.poll()

    def _do_close(self, action):
        if not self.thread_id:
            return
        try:
            self.client.support_thread_close(self.thread_id, action)
        except SessionExpiredError:
            _notify_session_expired(self)
            return
        except ApiError as e:
            QMessageBox.critical(self, "خطا", str(e))
            return
        QMessageBox.information(self, "انجام شد", "وضعیت گفتگو به‌روزرسانی شد.")


class ThreadListItem(QWidget):
    """Compact messenger-style row for the right-side desktop conversation list."""
    def __init__(self, thread, parent=None):
        super().__init__(parent)
        self.thread = thread
        self.setObjectName("chatThreadRow")
        self.setLayoutDirection(Qt.RightToLeft)
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(9)

        name = thread.get("subject") or thread.get("opened_by_name") or f"گفتگو #{thread.get('id','')}"
        initials = "".join([part[:1] for part in str(name).split()[:2]]) or "؟"
        avatar = QLabel(initials)
        avatar.setObjectName("chatThreadAvatar")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)

        middle = QVBoxLayout(); middle.setSpacing(3); middle.setContentsMargins(0, 0, 0, 0)
        title = QLabel(str(name)); title.setObjectName("chatThreadName")
        title.setWordWrap(False)
        preview = thread.get("last_message") or thread.get("last_message_preview") or thread.get("opened_by_name") or "بدون پیام"
        preview = str(preview).replace("\n", " ").strip()
        if len(preview) > 42: preview = preview[:39] + "..."
        preview_label = QLabel(preview); preview_label.setObjectName("chatThreadPreview")
        middle.addWidget(title); middle.addWidget(preview_label)

        meta = QVBoxLayout(); meta.setAlignment(Qt.AlignLeft | Qt.AlignTop); meta.setSpacing(5)
        when = thread.get("last_message_at") or thread.get("updated_at") or thread.get("created_at") or ""
        time_label = QLabel(str(when)[-8:] if when else "")
        time_label.setObjectName("chatThreadTime")
        time_label.setAlignment(Qt.AlignLeft)
        meta.addWidget(time_label)
        unread = int(thread.get("unread_support", 0) or 0)
        if unread:
            badge = QLabel(str(unread) if unread < 100 else "99+")
            badge.setObjectName("chatUnreadBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setMinimumSize(22, 22)
            meta.addWidget(badge, 0, Qt.AlignLeft)
        else:
            meta.addStretch(1)

        root.addLayout(meta)
        root.addLayout(middle, 1)
        root.addWidget(avatar)


class SupportPage(QWidget):
    """Support messaging for the native client. Uses the same support_threads
    table/API as the web inbox, so staff roles see customer conversations
    here too (not just internal staff chat) — the thread list just needs
    periodic refresh since new conversations arrive from the server."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setLayoutDirection(Qt.RightToLeft)

        self.status_combo = QComboBox()
        self.status_combo.addItem("باز", "باز")
        self.status_combo.addItem("بسته", "بسته")
        self.status_combo.addItem("همه", "all")
        self.status_combo.currentIndexChanged.connect(lambda _i: self.reload())

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("جست‌وجو...")
        self.search_btn = QPushButton("جست‌وجو")
        self.search_btn.clicked.connect(lambda: self.reload())
        self.search_edit.returnPressed.connect(lambda: self.reload())

        self.emoji_settings_btn = QPushButton("😊 تنظیم ایموجی‌ها")
        self.emoji_settings_btn.clicked.connect(self._open_emoji_settings)

        top = QHBoxLayout()
        top.addWidget(self.search_btn)
        top.addWidget(self.search_edit)
        top.addWidget(self.emoji_settings_btn)
        top.addWidget(self.status_combo)

        self.thread_list = QListWidget()
        self.thread_list.setObjectName("chatThreadList")
        self.thread_list.setMinimumWidth(260)
        self.thread_list.setMaximumWidth(340)
        self.thread_list.currentItemChanged.connect(self._on_select)

        self.thread_panel = ThreadPanel(client)

        splitter = QSplitter()
        splitter.addWidget(self.thread_panel)
        splitter.addWidget(self.thread_list)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)

        self.reload()

        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.reload(silent=True))
        self.timer.start(POLL_INTERVAL_MS)

    def _open_emoji_settings(self):
        # تنظیمات ایموجی چت هم‌جا با ارتباط با مشتری، نه در هاب مستقل تنظیمات.
        from ui_settings import ChatEmojisTab
        dlg = QDialog(self)
        dlg.setWindowTitle("ایموجی‌های چت")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(520, 480)
        layout = QVBoxLayout(dlg)
        layout.addWidget(ChatEmojisTab(self.client))
        dlg.exec_()

    def showEvent(self, event):
        super().showEvent(event)
        self.reload(silent=True)

    def reload(self, silent=False):
        status = self.status_combo.currentData() or "باز"
        try:
            data = self.client.support_inbox(status, self.search_edit.text().strip())
        except SessionExpiredError:
            if not silent:
                _notify_session_expired(self)
            return
        except ApiError as e:
            if not silent:
                QMessageBox.critical(self, "خطا", str(e))
            return

        current = self.thread_list.currentItem()
        selected_id = current.data(Qt.UserRole).get("id") if current else None

        self.thread_list.blockSignals(True)
        self.thread_list.clear()
        select_item = None
        for t in data.get("threads", []):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, t)
            item.setSizeHint(QSize(0, 68))
            row = ThreadListItem(t)
            self.thread_list.addItem(item)
            self.thread_list.setItemWidget(item, row)
            if selected_id is not None and t.get("id") == selected_id:
                select_item = item
        if select_item is not None:
            self.thread_list.setCurrentItem(select_item)
        self.thread_list.blockSignals(False)

    def _on_select(self, current, _previous):
        if not current:
            return
        t = current.data(Qt.UserRole)
        self.thread_panel.open_thread(t["id"], t.get("subject") or t.get("opened_by_name") or "")
