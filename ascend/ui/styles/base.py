"""Global resets, typography defaults, scrollbars, tooltips, separators."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    body_size, body_weight = t.type_scale.body
    return f"""
* {{
    font-family: {t.font_family};
    font-size: {body_size}px;
    font-weight: {body_weight};
    color: {p.text_primary};
}}

QMainWindow, QWidget#centralWidget {{
    background-color: {p.bg_app};
}}

QWidget {{
    background-color: transparent;
}}

QWidget#pageContainer {{
    background-color: {p.bg_secondary};
}}

QLabel.muted {{
    color: {p.text_secondary};
}}

QLabel.caption {{
    color: {p.text_secondary};
    font-size: {t.type_scale.caption[0]}px;
}}

QLabel#appTitle {{
    font-size: {t.type_scale.app_title[0]}px;
    font-weight: {t.type_scale.app_title[1]};
}}

QLabel#pageTitle {{
    font-size: {t.type_scale.page_title[0]}px;
    font-weight: {t.type_scale.page_title[1]};
}}

QLabel#pageDescription {{
    color: {p.text_secondary};
    font-size: {t.type_scale.secondary[0]}px;
}}

QLabel#sectionTitle {{
    font-size: {t.type_scale.section_title[0]}px;
    font-weight: {t.type_scale.section_title[1]};
    color: {p.text_secondary};
    letter-spacing: 1px;
}}

QFrame#separator {{
    background-color: {p.border};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

QToolTip {{
    background-color: {p.bg_card};
    color: {p.text_primary};
    border: 1px solid {p.border_strong};
    border-radius: {t.radii.sm}px;
    padding: 6px 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {p.scrollbar};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.border_strong};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {p.scrollbar};
    border-radius: 5px;
    min-width: 24px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}

QSplitter::handle {{
    background-color: {p.border};
}}

QProgressBar {{
    background-color: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: {t.radii.sm}px;
    text-align: center;
    color: {p.text_primary};
    min-height: 8px;
    max-height: 8px;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: {t.radii.sm}px;
}}
"""
