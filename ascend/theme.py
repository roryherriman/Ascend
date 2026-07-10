"""Ascend's theme: assembles the modular QSS fragments in ascend/ui/styles/
into one stylesheet, built from the centralized tokens in
ascend/ui/styles/tokens.py. Only dark mode ships in Phase 1; the token/QSS
split is what makes a future light mode a matter of adding
``LIGHT_TOKENS`` rather than rewriting styling.

Nothing here hardcodes a color - see ui/styles/tokens.py for the palette,
spacing, radii, typography, and control-size scales.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PySide6.QtGui import QColor

from ascend.ui.styles import base, buttons, cards, dialogs, inputs, sidebar, tables
from ascend.ui.styles.tokens import DARK_TOKENS, Tokens

# Re-exported for any code/tests that want the raw palette values.
PALETTE = DARK_TOKENS.palette


def build_stylesheet(tokens: Tokens = DARK_TOKENS) -> str:
    fragments = [
        base.build(tokens),
        buttons.build(tokens),
        inputs.build(tokens),
        cards.build(tokens),
        sidebar.build(tokens),
        tables.build(tokens),
        dialogs.build(tokens),
    ]
    return "\n".join(fragments)


DARK_STYLESHEET = build_stylesheet(DARK_TOKENS)


def apply_card_elevation(widget: QWidget, blur_radius: int = 24, y_offset: int = 4) -> None:
    """Gives a card widget a soft drop shadow. Qt's QSS has no `box-shadow`
    property, so elevation is applied programmatically via a graphics effect."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setXOffset(0)
    effect.setYOffset(y_offset)
    effect.setColor(QColor(0, 0, 0, 110))
    widget.setGraphicsEffect(effect)
