"""Button variants: default (secondary), primary, destructive, nav-adjacent icon buttons."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    h = t.control.button_height
    return f"""
QPushButton {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: {t.radii.md}px;
    padding: 0px 14px;
    min-height: {h}px;
    color: {p.text_primary};
}}

QPushButton:hover {{
    background-color: {p.bg_card_hover};
    border: 1px solid {p.border_strong};
}}

QPushButton:pressed {{
    background-color: {p.bg_app};
}}

QPushButton:focus {{
    border: 1px solid {p.focus_ring};
}}

QPushButton:disabled {{
    color: {p.text_disabled};
    background-color: {p.bg_secondary};
    border: 1px solid {p.border};
}}

QPushButton#primaryButton {{
    background-color: {p.accent};
    border: 1px solid {p.accent};
    color: {p.text_on_accent};
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background-color: {p.accent_hover};
    border: 1px solid {p.accent_hover};
}}

QPushButton#primaryButton:pressed {{
    background-color: {p.accent_pressed};
    border: 1px solid {p.accent_pressed};
}}

QPushButton#primaryButton:disabled {{
    background-color: {p.bg_secondary};
    border: 1px solid {p.border};
    color: {p.text_disabled};
}}

QPushButton#dangerButton {{
    background-color: transparent;
    border: 1px solid {p.error};
    color: {p.error};
    font-weight: 600;
}}

QPushButton#dangerButton:hover {{
    background-color: {p.error_muted};
}}

QPushButton#dangerButton:pressed {{
    background-color: {p.error};
    color: {p.text_on_accent};
}}

QPushButton#secondaryFlatButton {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {p.text_secondary};
}}

QPushButton#secondaryFlatButton:hover {{
    color: {p.text_primary};
    background-color: {p.bg_card_hover};
}}
"""
