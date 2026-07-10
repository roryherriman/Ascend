"""Sidebar: grouped navigation, headers, footer."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    return f"""
QWidget#sidebar {{
    background-color: {p.bg_sidebar};
    border-right: 1px solid {p.border};
}}

QWidget#sidebarHeader {{
    background-color: transparent;
    border-bottom: 1px solid {p.border};
}}

QWidget#sidebarFooter {{
    background-color: transparent;
    border-top: 1px solid {p.border};
}}

QLabel#navGroupLabel {{
    color: {p.text_disabled};
    font-size: {t.type_scale.caption[0]}px;
    font-weight: {t.type_scale.section_title[1]};
    letter-spacing: 1.2px;
    padding: {t.spacing.sm}px {t.spacing.md}px 2px {t.spacing.md}px;
}}

QListWidget#navList {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 2px {t.spacing.sm}px;
}}

QListWidget#navList::item {{
    height: {t.control.nav_item_height}px;
    border-radius: {t.radii.md}px;
    padding-left: {t.spacing.sm}px;
    margin: 1px 2px;
    color: {p.text_secondary};
}}

QListWidget#navList::item:selected {{
    background-color: {p.accent};
    color: {p.text_on_accent};
    font-weight: 600;
}}

QListWidget#navList::item:hover:!selected {{
    background-color: {p.bg_card_hover};
    color: {p.text_primary};
}}
"""
