"""Dark theme (default) stylesheet for Ascend.

A light theme can be added later (Settings has a theme preference field
already); Phase 1 ships dark-only per the requirement that dark mode is the
default.
"""

BG_0 = "#1e1f22"   # window background
BG_1 = "#26272b"   # panel / sidebar background
BG_2 = "#2f3136"   # card / input background
BG_3 = "#3a3c42"   # hover
BORDER = "#3f4147"
TEXT_PRIMARY = "#e6e6e6"
TEXT_SECONDARY = "#9a9ca3"
ACCENT = "#5b8def"
ACCENT_HOVER = "#7aa2f2"
SUCCESS = "#4caf7d"
WARNING = "#e0a83e"
DANGER = "#e0545c"

DARK_STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Cantarell", sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}

QMainWindow, QWidget#centralWidget {{
    background-color: {BG_0};
}}

QWidget {{
    background-color: transparent;
}}

QWidget#sidebar {{
    background-color: {BG_1};
    border-right: 1px solid {BORDER};
}}

QWidget#pageContainer {{
    background-color: {BG_0};
}}

QLabel#pageTitle {{
    font-size: 20px;
    font-weight: 600;
    padding: 4px 0px 12px 0px;
}}

QLabel#sectionHeading {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    padding-top: 8px;
}}

QLabel.muted {{
    color: {TEXT_SECONDARY};
}}

QListWidget#navList {{
    background-color: {BG_1};
    border: none;
    outline: none;
    padding: 8px 4px;
}}

QListWidget#navList::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin: 2px 4px;
}}

QListWidget#navList::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

QListWidget#navList::item:hover:!selected {{
    background-color: {BG_3};
}}

QFrame.card {{
    background-color: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QPushButton {{
    background-color: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
}}

QPushButton:hover {{
    background-color: {BG_3};
}}

QPushButton:pressed {{
    background-color: {BORDER};
}}

QPushButton:disabled {{
    color: {TEXT_SECONDARY};
    background-color: {BG_1};
}}

QPushButton#primaryButton {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#dangerButton {{
    background-color: {DANGER};
    border: 1px solid {DANGER};
    color: white;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QTableWidget, QTableView {{
    background-color: {BG_2};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
}}

QHeaderView::section {{
    background-color: {BG_1};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    font-weight: 600;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QTabBar::tab {{
    background-color: {BG_1};
    padding: 8px 14px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background-color: {BG_2};
}}

QProgressBar {{
    background-color: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

QStatusBar {{
    background-color: {BG_1};
    border-top: 1px solid {BORDER};
}}

QScrollBar:vertical {{
    background: {BG_0};
    width: 12px;
}}

QScrollBar::handle:vertical {{
    background: {BG_3};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar:horizontal {{
    background: {BG_0};
    height: 12px;
}}

QScrollBar::handle:horizontal {{
    background: {BG_3};
    border-radius: 5px;
    min-width: 24px;
}}

QToolTip {{
    background-color: {BG_2};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

QSplitter::handle {{
    background-color: {BORDER};
}}
"""
