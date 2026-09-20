# -*- coding: utf-8 -*-
"""SAZGAN Native Client entry point.

Startup is intentionally lightweight: feature pages are imported only after a
successful login, keeping the login window responsive and reducing cold-start
latency.
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
from ui_login import LoginWindow
from theme import apply_theme, app_icon


def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    apply_theme(app)
    app.setWindowIcon(app_icon())

    windows = {}

    def show_login():
        login = LoginWindow(on_login_success)
        windows["login"] = login
        login.show()
        login.raise_()
        login.activateWindow()

    def show_login_after_session_expiry():
        old = windows.get("main")
        if old is not None:
            old.close()
            old.deleteLater()
            windows.pop("main", None)
        show_login()

    def on_login_success(client):
        # Lazy import: the feature pages are not imported during cold start.
        from ui_main import MainWindow
        win = MainWindow(client)
        windows["main"] = win
        win.sessionExpiredRequested.connect(show_login_after_session_expiry)
        windows.get("login") and windows["login"].close()
        win.show()
        win.raise_()
        win.activateWindow()

    show_login()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
