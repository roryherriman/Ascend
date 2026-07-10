"""Text inputs, combo boxes, checkboxes, spin boxes."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    h = t.control.input_height
    return f"""
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {p.bg_input};
    border: 1px solid {p.border};
    border-radius: {t.radii.md}px;
    padding: 4px 10px;
    min-height: {h}px;
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
}}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid {p.border_strong};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.focus_ring};
    background-color: {p.bg_input_focus};
}}

QLineEdit:disabled, QComboBox:disabled {{
    color: {p.text_disabled};
    background-color: {p.bg_secondary};
}}

QLineEdit#searchInput {{
    padding-left: 12px;
    background-color: {p.bg_card};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p.bg_card};
    border: 1px solid {p.border_strong};
    selection-background-color: {p.accent};
    selection-color: {p.text_on_accent};
    outline: none;
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: {t.radii.sm}px;
    border: 1px solid {p.border_strong};
    background-color: {p.bg_input};
}}

QCheckBox::indicator:hover {{
    border: 1px solid {p.accent};
}}

QCheckBox::indicator:checked {{
    background-color: {p.accent};
    border: 1px solid {p.accent};
}}

QGroupBox {{
    border: 1px solid {p.border};
    border-radius: {t.radii.lg}px;
    margin-top: 14px;
    padding: {t.spacing.lg}px {t.spacing.md}px {t.spacing.md}px {t.spacing.md}px;
    font-weight: 600;
    background-color: {p.bg_card};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {p.text_secondary};
    font-size: {t.type_scale.section_title[0]}px;
    font-weight: {t.type_scale.section_title[1]};
}}
"""
