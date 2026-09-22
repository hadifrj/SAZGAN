# -*- coding: utf-8 -*-
"""Shared Native Design System — intentionally mirrors the web UI tokens."""
from pathlib import Path
from PyQt5.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QStyleFactory
from PyQt5.QtGui import QFont, QFontDatabase, QIcon
from PyQt5.QtCore import QTimer, QObject, QEvent, Qt
import json
from config import load_config

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# Sazgan brand icons shipped with the server/web app. Bundled into the
# frozen build via --add-data "static\\icons;static\\icons" so this same
# relative path resolves both when running from source and when frozen.
ICON_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"
APP_ICON_FILES = [
    "icon-512.png", "icon-256-desktop.png", "icon-128-desktop.png",
    "icon-64-desktop.png", "icon-48-desktop.png", "favicon-32.png",
]


def app_icon() -> QIcon:
    """Sazgan window/taskbar icon, built from the bundled brand PNGs."""
    qicon = QIcon()
    for name in APP_ICON_FILES:
        path = ICON_DIR / name
        if path.exists():
            qicon.addFile(str(path))
    return qicon
FONT_FILES = [
    "Vazirmatn-FD-Thin(1).ttf",
    "Vazirmatn-FD-ExtraLight(1).ttf",
    "Vazirmatn-FD-Light(1).ttf",
    "Vazirmatn-FD-Regular(1).ttf",
    "Vazirmatn-FD-Medium(1).ttf",
    "Vazirmatn-FD-SemiBold(1).ttf",
    "Vazirmatn-FD-Bold(1).ttf",
    "Vazirmatn-FD-ExtraBold(1).ttf",
    "Vazirmatn-FD-Black(1).ttf",
]

# Shared design tokens: one source used by Native and mirrored by Web CSS.
TOKEN_FILE = Path(__file__).resolve().parent.parent / "design_tokens" / "tokens.json"

def _load_tokens():
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "colors":{"bg":"#f8fafc","card":"#ffffff","text":"#0f172a","muted":"#64748b","border":"#e2e8f0","borderStrong":"#cbd5e1","accent":"#374151","accentHover":"#1f2937","accentSoft":"#f3f4f6","sidebar":"#ffffff","sidebarActive":"#f3f4f6","danger":"#b91c1c","success":"#15803d"},
            "radius":{"sm":6,"md":8,"lg":10}, "spacing":{"xs":4,"sm":8,"md":12,"lg":16,"xl":24},
            "sidebar":{"expanded":235,"collapsed":68,"itemHeight":42,"icon":21}, "header":{"height":66},
            "typography":{"family":"Vazirmatn FD","basePt":10}
        }

TOKENS = _load_tokens()
C=TOKENS["colors"]; SP=TOKENS["spacing"]; R=TOKENS["radius"]; SB=TOKENS["sidebar"]
BG=C["bg"]; CARD=C["card"]; TEXT=C["text"]; MUTED=C["muted"]; BORDER=C["border"]; BORDER_STRONG=C["borderStrong"]
ACCENT=C["accent"]; ACCENT_HOVER=C["accentHover"]; ACCENT_SOFT=C["accentSoft"]; SIDEBAR=C["sidebar"]; SIDEBAR_ACTIVE=C["sidebarActive"]; DANGER=C["danger"]; SUCCESS=C["success"]

# Backward-compatible token aliases. Older Native Client builds referenced
# lowercase token names in the stylesheet; keep them defined so a mixed/stale
# module cannot raise NameError during login startup.
background = BG
card = CARD
text = TEXT
muted = MUTED
border = BORDER
border_strong = BORDER_STRONG
accent = ACCENT
accent_hover = ACCENT_HOVER
accent_soft = ACCENT_SOFT
sidebar = SIDEBAR
sidebar_active = SIDEBAR_ACTIVE
danger = DANGER
success = SUCCESS


def load_fonts(files=None):
    """Load bundled fonts without requiring Windows installation."""
    loaded = []
    for name in (files or FONT_FILES):
        path = FONT_DIR / name
        if path.exists():
            fid = QFontDatabase.addApplicationFont(str(path))
            if fid >= 0:
                loaded.append(fid)
    return loaded


class _RtlContextMenuFilter(QObject):
    """Forces the standard right-click edit menu (Undo/Redo/Cut/Copy/Paste/...)
    to render fully right-to-left, like a native RTL Windows app.

    Qt already marks these menus RightToLeft because the app's default
    layout direction is RTL, but on Windows the standard edit menu is drawn
    by the OS theme engine ("windowsvista" style), which only mirrors which
    side the popup opens from - it does not right-align each row's label or
    move the shortcut text (Ctrl+Z, Ctrl+C, ...) to the correct side. Building
    the menu ourselves and forcing it to use Qt's own "Fusion" style hands
    all of that layout back to Qt, which does honor RTL per-row.
    """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ContextMenu and isinstance(obj, (QLineEdit, QTextEdit, QPlainTextEdit)):
            menu = obj.createStandardContextMenu()
            menu.setLayoutDirection(Qt.RightToLeft)
            fusion = QStyleFactory.create("Fusion")
            if fusion is not None:
                fusion.setParent(menu)
                menu.setStyle(fusion)
            menu.exec_(event.globalPos())
            return True
        return False


# Kept alive for the lifetime of the app (installEventFilter does not take
# ownership), otherwise the filter would be garbage-collected immediately.
_rtl_context_menu_filter = None


def install_rtl_context_menus(app):
    global _rtl_context_menu_filter
    _rtl_context_menu_filter = _RtlContextMenuFilter()
    app.installEventFilter(_rtl_context_menu_filter)


def _apply_ui_theme_tokens():
    """Keep Native colors aligned with the shared Web/PWA theme selection."""
    global BG, CARD, TEXT, MUTED, BORDER, BORDER_STRONG, ACCENT, ACCENT_HOVER, ACCENT_SOFT, SIDEBAR, SIDEBAR_ACTIVE
    ui=str(load_config().get("ui_theme", "minimal_premium") or "minimal_premium")
    palettes={
      "light_modern_indigo": {"BG":"#f8fafc","CARD":"#ffffff","TEXT":"#0f172a","MUTED":"#64748b","BORDER":"#e2e8f0","BORDER_STRONG":"#cbd5e1","ACCENT":"#4f46e5","ACCENT_HOVER":"#4338ca","ACCENT_SOFT":"#eef2ff","SIDEBAR":"#ffffff","SIDEBAR_ACTIVE":"#eef2ff"},
      "dark_modern_indigo": {"BG":"#0f172a","CARD":"#111827","TEXT":"#f8fafc","MUTED":"#94a3b8","BORDER":"#334155","BORDER_STRONG":"#475569","ACCENT":"#6366f1","ACCENT_HOVER":"#818cf8","ACCENT_SOFT":"#1e1b4b","SIDEBAR":"#111827","SIDEBAR_ACTIVE":"#1f2937"},
      "minimal_premium": {"BG":"#f8fafc","CARD":"#ffffff","TEXT":"#111827","MUTED":"#6b7280","BORDER":"#e5e7eb","BORDER_STRONG":"#9ca3af","ACCENT":"#111827","ACCENT_HOVER":"#000000","ACCENT_SOFT":"#f3f4f6","SIDEBAR":"#ffffff","SIDEBAR_ACTIVE":"#f3f4f6"},
    }.get(ui)
    if palettes:
      for k,v in palettes.items(): globals()[k]=v

def apply_theme(app):
    _apply_ui_theme_tokens()
    # Load all bundled fonts before the first window is shown.  Delayed font
    # registration can change font metrics after the Login layout is already
    # calculated, which causes fields to visually jump/overlap on first paint.
    load_fonts()
    app.setFont(QFont("Vazirmatn FD", 10))
    install_rtl_context_menus(app)
    app.setStyleSheet(f"""
    * {{ font-family: 'Vazirmatn FD'; }}
    QWidget {{ color: {TEXT}; font-size: 10pt; }}
    QMainWindow, QDialog {{ background: {BG}; }}

    QLineEdit#loginField {{
        background: #ffffff; color: {TEXT}; border: 1px solid #94a3b8;
        border-radius: 9px; padding: 8px 42px 8px 12px; min-height: 34px;
    }}
    QLineEdit#loginField:hover {{ border-color: #64748b; }}
    QLineEdit#loginField:focus {{ border: 1px solid {ACCENT}; }}
    QToolButton#passwordToggle {{
        background: transparent; border: 0; color: {MUTED}; padding: 2px;
    }}
    QToolButton#passwordToggle:hover {{ color: {TEXT}; background: {ACCENT_SOFT}; border-radius: 6px; }}
    QLabel#loginTitle {{ font-size: 18pt; font-weight: 800; color: {TEXT}; }}
    QLabel#loginSubtitle {{ color: {MUTED}; font-size: 9pt; }}

    /* ---------- Header ---------- */
    QFrame#appHeader {{
        background: {CARD}; border: 0; border-bottom: 1px solid {BORDER};
    }}
    QLabel#brandName {{ font-size: 13pt; font-weight: 800; color: {TEXT}; }}
    QLabel#brandSub {{ font-size: 8.5pt; color: {MUTED}; }}
    QLabel#headerDate {{ color: {MUTED}; font-size: 9pt; }}
    QLabel#headerUserName {{ color: {TEXT}; font-weight: 700; }}
    QLabel#headerUserRole {{ color: {MUTED}; font-size: 8pt; }}
    QToolButton#headerIconButton {{
        background: transparent; border: 1px solid transparent; border-radius: 8px;
        padding: 7px; color: {TEXT};
    }}
    QToolButton#headerIconButton:hover {{ background: {ACCENT_SOFT}; border-color: {BORDER}; }}
    QToolButton#headerAvatar {{ background: {ACCENT_SOFT}; border: 1px solid {BORDER}; border-radius: 17px; padding: 5px; }}
    QToolButton#headerAvatar:hover {{ background: #e5e7eb; }}
    QLineEdit#headerSearch {{
        background: {BG}; border: 1px solid {BORDER}; border-radius: 9px;
        padding: 7px 12px; color: {TEXT}; selection-background-color: {ACCENT};
    }}
    QLineEdit#headerSearch:focus {{ border: 1px solid {BORDER_STRONG}; background: #fff; }}

    /* ---------- Sidebar: web-matched primary navigation ---------- */
    QFrame#nativeSidebar {{
        background: #ffffff; border: 0; border-left: 1px solid #e2e8f0;
    }}
    QToolButton#sidebarToggle {{
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
        padding: 7px; color: #111827;
    }}
    QToolButton#sidebarToggle:hover {{ background: #f3f4f6; border-color: #cbd5e1; }}
    QLabel#sidebarBrandName {{ font-size: 13pt; font-weight: 800; color: #0f172a; }}
    QLabel#sidebarBrandSub {{ font-size: 8.5pt; color: #64748b; }}
    QWidget#webSidebarNav {{ background: transparent; }}
    QToolButton#sidebarItem {{
        background: transparent; color: #374151; border: 0; border-radius: 8px;
        padding: 0 12px; margin: 0; text-align: right; font-size: 10pt; font-weight: 500;
    }}
    QToolButton#sidebarItem:hover {{
        background: rgba(15,23,42,.06); color: #111827;
    }}
    QToolButton#sidebarItem:checked {{
        background: #f3f4f6; color: #111827; font-weight: 700;
        border-right: 3px solid #374151;
    }}
    QToolButton#sidebarItem:checked:hover {{ background: #eef0f3; }}
    QLabel#sidebarVersion {{ color: #64748b; font-size: 8pt; padding: 2px 6px; }}

    /* ---------- Page shell / cards ---------- */
    QWidget#page {{ background: transparent; }}
    QFrame.card, QFrame#card {{
        background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
        min-height: 0;
    }}
    QFrame[cardRole="content"] {{ padding: 0; }}
    QFrame#statCard, QFrame[cardRole="stat"] {{
        background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    }}
    QLabel#pageTitle {{ font-size: 17pt; font-weight: 800; color: {TEXT}; }}
    QLabel#pageSubtitle {{ color: {MUTED}; font-size: 9pt; }}
    QLabel#sectionTitle {{ font-size: 11pt; font-weight: 700; color: {TEXT}; }}
    QLabel#statValue {{ font-size: 18pt; font-weight: 800; color: {TEXT}; }}
    QLabel#statTitle {{ color: {MUTED}; font-size: 9pt; }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background: {ACCENT}; color: white; border: 1px solid {ACCENT};
        border-radius: 8px; padding: 7px 14px; min-height: 30px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton:pressed {{ background: #111827; }}
    QPushButton:disabled {{ background: #cbd5e1; border-color: #cbd5e1; color: #f8fafc; }}
    QPushButton[variant="secondary"] {{ background: #fff; color: #334155; border-color: {BORDER_STRONG}; }}
    QPushButton[variant="secondary"]:hover {{ background: {BG}; }}
    QPushButton[variant="danger"] {{ background: #fff; color: {DANGER}; border-color: #fecaca; }}
    QPushButton[variant="danger"]:hover {{ background: #fef2f2; }}

    /* ---------- Native Login (mirrors the web login-box design) ---------- */
    QWidget#loginRoot {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #dbeafe, stop:0.5 #e5edf7, stop:1 #eef2f7);
    }}
    QFrame#loginCard {{
        background: #ffffff; border-radius: 20px; border: none;
    }}
    QLabel#brandNameBig {{
        font-size: 22pt; font-weight: 800; color: #0f172a;
    }}
    QLabel#brandSubBig {{ color: {MUTED}; font-size: 10pt; }}
    QLabel#loginTitle {{ font-size: 20pt; font-weight: 800; color: {TEXT}; }}
    QLabel#loginSubtitle {{ color: {MUTED}; font-size: 9.5pt; margin-bottom: 2px; }}
    QLabel#loginLabel {{ color: {TEXT}; font-size: 9.5pt; font-weight: 700; }}
    QLabel#loginStatus {{ min-height: 24px; }}
    QLineEdit#loginField {{
        background: #ffffff; color: {TEXT}; border: 1px solid #94a3b8;
        border-radius: 9px; padding: 8px 12px; min-height: 26px;
        selection-background-color: {ACCENT};
    }}
    QLineEdit#loginField:hover {{ border-color: {BORDER_STRONG}; }}
    QLineEdit#loginField:focus {{ border: 2px solid #2563eb; padding: 7px 11px; }}
    QToolButton#passwordToggle {{
        background: transparent; border: 0; border-radius: 7px; padding: 5px;
    }}
    QToolButton#passwordToggle:hover {{ background: {ACCENT_SOFT}; }}
    QLabel#saveStatus {{ min-height: 24px; font-weight: 600; }}
    /* Native's primary login action is styled with the web's blue accent,
       distinct from the app-wide neutral button color used everywhere else. */
    QPushButton#loginPrimaryBtn {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
        border: 1px solid #1d4ed8; color: #ffffff; font-weight: 800; font-size: 11pt;
        border-radius: 12px;
    }}
    QPushButton#loginPrimaryBtn:hover {{ background: #1d4ed8; border-color: #1d4ed8; }}
    QPushButton#loginPrimaryBtn:pressed {{ background: #1e40af; }}
    QPushButton#loginPrimaryBtn:disabled {{ background: #93c5fd; border-color: #93c5fd; color: #f8fafc; }}
    QPushButton#supportToggle {{
        background: transparent; border: 0; color: #2563eb; font-weight: 700;
        font-size: 9.5pt; padding: 8px; margin-top: 6px;
    }}
    QPushButton#supportToggle:hover {{ text-decoration: underline; background: transparent; }}
    QFrame#supportPanel {{
        background: {BG}; border: 1px solid {BORDER}; border-radius: 12px; margin-top: 4px;
    }}

    /* ---------- Inputs ---------- */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
        background: #fff; color: {TEXT}; border: 1px solid #94a3b8;
        border-radius: 8px; padding: 7px 9px; min-height: 30px;
        selection-background-color: {ACCENT};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{ border: 1px solid {ACCENT}; }}
    QLabel {{ background: transparent; }}

    /* ---------- Tabs ---------- */
    QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; background: {CARD}; top: -1px; }}
    QTabBar::tab {{
        background: transparent; color: {MUTED}; padding: 9px 15px;
        border: 0; border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:hover {{ color: {TEXT}; }}
    QTabBar::tab:selected {{ color: {TEXT}; font-weight: 700; border-bottom: 2px solid {ACCENT}; }}

    /* ---------- Tables ---------- */
    QTableWidget, QTableView {{
        background: {CARD}; alternate-background-color: #f8fafc;
        border: 1px solid {BORDER}; border-radius: 9px; gridline-color: transparent;
        selection-background-color: #eef0f3; selection-color: {TEXT};
    }}
    QHeaderView::section {{
        background: {BG}; color: {MUTED}; border: 0; border-bottom: 1px solid {BORDER};
        padding: 8px 10px; font-weight: 700;
    }}
    QTableWidget::item {{ padding: 7px 8px; border: 0; }}
    QTableWidget::item:selected {{ background: #eef0f3; color: {TEXT}; }}

    /* ---------- Scrollbars ---------- */
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #cbd5e1; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 4px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ---------- Modern customer chat ---------- */
    QListWidget#chatThreadList {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 16px; padding: 6px; outline: 0; }}
    QListWidget#chatThreadList::item { border: 0; border-radius: 12px; margin: 2px 0; }
    QListWidget#chatThreadList::item:hover { background: #f8fafc; }
    QListWidget#chatThreadList::item:selected {{ background: #eef2ff; color: {TEXT}; }}
    QWidget#chatThreadRow { border-radius: 12px; background: transparent; }
    QLabel#chatThreadAvatar { background: #e8eefc; color: #243b72; border-radius: 21px; font-weight: 700; font-size: 13px; }
    QLabel#chatThreadName {{ color: {TEXT}; font-weight: 700; font-size: 12px; }}
    QLabel#chatThreadPreview { color: #64748b; font-size: 10px; }
    QLabel#chatThreadTime { color: #94a3b8; font-size: 9px; }
    QLabel#chatUnreadBadge { background: #2563eb; color: white; border-radius: 11px; font-size: 9px; font-weight: 700; padding: 1px 5px; }
    QTextBrowser#chatMessages {{ background: #f8fafc; border: 1px solid {BORDER}; border-radius: 14px; padding: 10px; }}
    QLineEdit#chatComposer {{ background: #ffffff; border: 1px solid {BORDER_STRONG}; border-radius: 18px; padding: 8px 14px; min-height: 34px; }}
    QPushButton#chatSendButton {{ background: {ACCENT}; color: #ffffff; border: 0; border-radius: 18px; padding: 7px 18px; font-weight: 700; min-height: 34px; }}
    QPushButton#chatSendButton:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#chatAttachButton {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 18px; min-width: 36px; min-height: 36px; padding: 0; }}
    QPushButton#chatAttachButton:hover {{ background: {ACCENT_SOFT}; }}
    /* ---------- Messages ---------- */
    QMessageBox {{ background: {CARD}; }}
    """)
