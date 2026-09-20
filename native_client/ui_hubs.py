# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QToolButton, QSizePolicy
from PyQt5.QtCore import Qt
from ui_common import module_card_style


class HubCard(QFrame):
    """Shared module card: theme surface + semantic accent + compact actions."""
    def __init__(self, title, description, callback, icon_text="•", accent="settings"):
        super().__init__()
        self.setObjectName("hubCard")
        self.setProperty("cardRole", "module")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(210, 154)
        self.setMinimumHeight(160)
        self.setMaximumHeight(176)
        self.setStyleSheet(module_card_style(accent))
        self._callback = callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 11)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(icon_text)
        icon.setObjectName("moduleCardIcon")
        icon.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        menu = QToolButton()
        menu.setObjectName("moduleCardMenu")
        menu.setText("⋮")
        menu.setToolTip("ورود به بخش")
        menu.clicked.connect(self._open)
        top.addWidget(icon)
        top.addStretch(1)
        top.addWidget(menu)

        title_label = QLabel(title)
        title_label.setObjectName("moduleCardTitle")
        title_label.setWordWrap(True)
        desc = QLabel(description)
        desc.setObjectName("moduleCardDescription")
        desc.setWordWrap(True)
        desc.setMinimumHeight(30)
        action = QLabel("ورود به بخش  ←")
        action.setObjectName("moduleCardAction")
        action.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout.addLayout(top)
        layout.addWidget(title_label)
        layout.addWidget(desc, 1)
        layout.addWidget(action)

    def _open(self):
        if self._callback:
            self._callback()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._open()
        super().mousePressEvent(event)


class HubPage(QWidget):
    """Native equivalent of the web hubs with one consistent responsive card system."""
    def __init__(self, title, subtitle, cards, accent="settings"):
        super().__init__()
        self.setObjectName("page")
        self.setLayoutDirection(Qt.RightToLeft)
        self.cards = cards
        self.accent = accent
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 28)
        root.setSpacing(10)
        h = QLabel(title); h.setObjectName("pageTitle")
        s = QLabel(subtitle); s.setObjectName("pageSubtitle"); s.setWordWrap(True)
        root.addWidget(h); root.addWidget(s)
        self.grid_host = QWidget(); self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 8, 0, 0)
        self.grid.setHorizontalSpacing(12); self.grid.setVerticalSpacing(12)
        self.card_widgets = [HubCard(*card, accent=accent) for card in cards]
        self._reflow()
        root.addWidget(self.grid_host, 1)

    def _column_count(self):
        width = max(self.grid_host.width(), self.width(), 1)
        return 4 if width >= 1240 else 3 if width >= 900 else 2 if width >= 600 else 1

    def _reflow(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(self.grid_host)
        cols = self._column_count()
        for i, card in enumerate(self.card_widgets):
            self.grid.addWidget(card, i // cols, i % cols)
        for col in range(cols):
            self.grid.setColumnStretch(col, 1)

    def resizeEvent(self, event):
        self._reflow()
        super().resizeEvent(event)
