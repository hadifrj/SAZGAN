# -*- coding: utf-8 -*-
"""Small SVG icon set mirroring the web sidebar icons."""
from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

ICONS = {
    "more": '<circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/',
    "menu": '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/>',
    "cartable": '<path d="M3 12h5l2 3h4l2-3h5"/><path d="M5 12V5a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v7"/><rect x="3" y="12" width="18" height="7" rx="1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><line x1="16.3" y1="16.3" x2="21" y2="21"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 1 1 18 0z"/>',
    "notifications": '<path d="M6 10a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "customer": '<path d="M6 3h12v18l-2-1.3L14 21l-2-1.3L10 21l-2-1.3L6 21z"/><line x1="8.5" y1="8" x2="15.5" y2="8"/><line x1="8.5" y1="11.5" x2="15.5" y2="11.5"/><line x1="8.5" y1="15" x2="13" y2="15"/>',
    "tasks": '<path d="M14.7 6.3a4 4 0 0 0-5.4 4.9L3 17.5 6.5 21l6.3-6.3a4 4 0 0 0 4.9-5.4l-2.8 2.8-2.1-2.1z"/>',
    "warehouse": '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><line x1="12" y1="11" x2="12" y2="21"/>',
    "finance": '<circle cx="12" cy="12" r="9"/><path d="M9 9.3c0-1.1 1.3-1.8 3-1.8s3 .7 3 1.8-1.3 1.3-3 1.7-3 .8-3 1.9 1.3 1.8 3 1.8 3-.7 3-1.8"/><line x1="12" y1="5.5" x2="12" y2="7.2"/><line x1="12" y1="16.8" x2="12" y2="18.5"/>',
    "reports": '<polyline points="3 17 9 11 13 15 21 6"/><polyline points="15 6 21 6 21 12"/>',
    "settings": '<path d="M21.4 12L21.2 13.8 19 14.9 18.3 16.2 18.6 18.6 17.2 19.8 14.9 19 13.5 19.5 12 21.4 10.2 21.2 9.1 19 7.8 18.3 5.4 18.6 4.2 17.2 5 14.9 4.5 13.5 2.6 12 2.8 10.2 5 9.1 5.7 7.8 5.4 5.4 6.8 4.2 9.1 5 10.5 4.5 12 2.6 13.8 2.8 14.9 5 16.2 5.7 18.6 5.4 19.8 6.8 19 9.1 19.5 10.5Z"/><circle cx="12" cy="12" r="3.2"/>',
    "user": '<circle cx="12" cy="8" r="3"/><path d="M5 21a7 7 0 0 1 14 0"/>',
    "eye": '<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.5"/>',
    "eye_off": '<path d="M3 3l18 18"/><path d="M10.6 6.2A10.9 10.9 0 0 1 12 6c6 0 9.5 6 9.5 6a16.8 16.8 0 0 1-3.2 3.7"/><path d="M6.4 6.4C3.9 8.1 2.5 12 2.5 12s3.5 6 9.5 6c1.2 0 2.3-.2 3.2-.6"/',
    "back": '<polyline points="15 18 9 12 15 6"/>',
}


def icon(name: str, size: int = 21, stroke: float = 1.8) -> QIcon:
    body = ICONS[name]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#374151" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'''
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pix)
