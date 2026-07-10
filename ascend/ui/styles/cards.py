"""Elevated cards, badges, banners, empty-state panels."""
from __future__ import annotations

from ascend.ui.styles.tokens import Tokens


def build(t: Tokens) -> str:
    p = t.palette
    return f"""
QFrame.card {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: {t.radii.lg}px;
}}

QFrame.card:hover {{
    border: 1px solid {p.border_strong};
}}

QFrame.card.elevated {{
    background-color: {p.bg_card_elevated};
    border: 1px solid {p.border_strong};
}}

QWidget#contextChip, QPushButton#contextChip {{
    background-color: {p.bg_card};
    border: 1px solid {p.border};
    border-radius: {t.radii.md}px;
    text-align: left;
}}

QPushButton#contextChip:hover, QWidget#contextChip:hover {{
    background-color: {p.bg_card_hover};
    border: 1px solid {p.border_strong};
}}

QWidget#topContextBar {{
    background-color: transparent;
}}

QFrame#emptyStatePanel {{
    background-color: {p.bg_card};
    border: 1px dashed {p.border_strong};
    border-radius: {t.radii.xl}px;
}}

QLabel.badge {{
    border-radius: {t.radii.pill}px;
    padding: 2px 10px;
    font-size: {t.type_scale.badge_text[0]}px;
    font-weight: {t.type_scale.badge_text[1]};
}}

QLabel[badgeTone="neutral"] {{
    background-color: {p.bg_secondary};
    color: {p.text_secondary};
    border: 1px solid {p.border_strong};
}}

QLabel[badgeTone="accent"] {{
    background-color: {p.accent_muted};
    color: {p.accent_hover};
}}

QLabel[badgeTone="success"] {{
    background-color: {p.success_muted};
    color: {p.success};
}}

QLabel[badgeTone="warning"] {{
    background-color: {p.warning_muted};
    color: {p.warning};
}}

QLabel[badgeTone="error"] {{
    background-color: {p.error_muted};
    color: {p.error};
}}

QLabel[badgeTone="info"] {{
    background-color: {p.info_muted};
    color: {p.info};
}}

QFrame.banner {{
    border-radius: {t.radii.md}px;
    border: 1px solid transparent;
}}

QFrame[bannerTone="success"] {{
    background-color: {p.success_muted};
    border: 1px solid {p.success};
}}

QFrame[bannerTone="warning"] {{
    background-color: {p.warning_muted};
    border: 1px solid {p.warning};
}}

QFrame[bannerTone="error"] {{
    background-color: {p.error_muted};
    border: 1px solid {p.error};
}}

QFrame[bannerTone="info"] {{
    background-color: {p.info_muted};
    border: 1px solid {p.info};
}}

QFrame#loadingOverlay {{
    background-color: {p.bg_overlay};
    border-radius: {t.radii.lg}px;
}}

QFrame#kpiDivider {{
    background-color: {p.border};
    border: none;
    max-width: 1px;
}}

QFrame#toastCard {{
    border-radius: {t.radii.md}px;
}}
"""
