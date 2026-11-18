from string import Template

C = dict(
    bg="#0a0e13", panel="#121922", panel2="#18212c", border="#2a3748",
    text="#d9e2ec", muted="#7f90a5", accent="#58b8e8",
    red="#ff4d5a", amber="#ffb020", green="#2ee59d",
)

QSS = Template("""
QWidget#root { background: $bg; }
QWidget { color: $text; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QFrame#panel { background: $panel; border: 1px solid $border; border-radius: 10px; }
QLabel { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 700; letter-spacing: 2px; }
QLabel#muted { color: $muted; }
QLabel#section { color: $muted; font-weight: 600; }
QLabel#simbanner { background: #3b2a05; color: $amber; border: 1px solid $amber;
                   border-radius: 6px; padding: 6px 10px; font-weight: 700; }
QLabel#result { border-radius: 8px; padding: 12px 14px; font-weight: 700; font-size: 14px; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2a3646, stop:1 #1b2430);
              border: 1px solid $border; border-radius: 6px; padding: 9px 14px; }
QPushButton:hover { border-color: $accent; }
QPushButton:pressed { background: #151c26; }
QPushButton:disabled { color: #4a5668; border-color: #1f2a37; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2d7ea8, stop:1 #1c5878);
                      border: 1px solid $accent; font-weight: 700; font-size: 14px; padding: 12px 16px; }
QPushButton#primary:disabled { background: #18222d; border-color: #1f2a37; }
QPushButton#danger { border-color: #7a2c35; }
QPushButton#danger:hover { border-color: $red; }
QComboBox { background: #0d131a; border: 1px solid $border; border-radius: 6px; padding: 6px 8px; }
QComboBox QAbstractItemView { background: #0d131a; selection-background-color: #24425a; }
QCheckBox { spacing: 8px; }
QTableWidget { background: #0d131a; border: 1px solid $border; border-radius: 6px;
               gridline-color: #1c2633; selection-background-color: #1d3347; }
QHeaderView::section { background: $panel2; color: $muted; border: none;
                       border-bottom: 1px solid $border; padding: 6px; font-weight: 600; }
QScrollBar:vertical { background: #0d131a; width: 10px; }
QScrollBar::handle:vertical { background: #2a3748; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
""").substitute(C)
