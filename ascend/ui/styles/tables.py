"""Tables: headers, row states, selection, sort indicators."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    return f"""
QTableWidget, QTableView {{
    background-color: {p.bg_card};
    alternate-background-color: {p.bg_secondary};
    border: 1px solid {p.border};
    border-radius: {t.radii.md}px;
    gridline-color: {p.border};
    selection-background-color: {p.accent_muted};
    selection-color: {p.text_primary};
}}

QTableWidget::item, QTableView::item {{
    padding: 6px 8px;
    border: none;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {p.accent_muted};
    color: {p.text_primary};
}}

QTableWidget::item:hover, QTableView::item:hover {{
    background-color: {p.bg_card_hover};
}}

QHeaderView::section {{
    background-color: {p.bg_secondary};
    color: {p.text_secondary};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {p.border_strong};
    border-right: 1px solid {p.border};
    font-weight: 600;
    font-size: {t.type_scale.caption[0]}px;
}}

QHeaderView::section:hover {{
    color: {p.text_primary};
    background-color: {p.bg_card_hover};
}}

QTableCornerButton::section {{
    background-color: {p.bg_secondary};
    border: none;
}}

QTableWidget QLineEdit#searchInput, QTableView QLineEdit#searchInput {{
    margin: 0px;
}}
"""
