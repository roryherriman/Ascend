"""Dialogs, wizard pages, message boxes, tab widgets, status bar."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    return f"""
QDialog {{
    background-color: {p.bg_app};
}}

QMessageBox {{
    background-color: {p.bg_card};
}}

QWizard, QWizardPage {{
    background-color: {p.bg_app};
}}

QTabWidget::pane {{
    border: 1px solid {p.border};
    border-radius: {t.radii.md}px;
    background-color: {p.bg_card};
}}

QTabBar::tab {{
    background-color: {p.bg_secondary};
    color: {p.text_secondary};
    padding: 8px 16px;
    border: 1px solid {p.border};
    border-bottom: none;
    border-top-left-radius: {t.radii.md}px;
    border-top-right-radius: {t.radii.md}px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {p.bg_card};
    color: {p.text_primary};
    font-weight: 600;
}}

QStatusBar {{
    background-color: {p.bg_sidebar};
    border-top: 1px solid {p.border};
    color: {p.text_secondary};
}}

QStatusBar::item {{
    border: none;
}}
"""
